"""Independent AI matching and optional import of Modul 3 baseline.

This module deliberately has no PyQGIS dependency so that decision logic can
be tested without a desktop QGIS installation. Spatial/area variables are
features of a trained model, NOT hard gates copied from Modul 3.
"""

import csv
import io
import math
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


TRAINING_MODES = ('SILVER_ONLY', 'GOLD_ONLY', 'SILVER_GOLD')
INFERENCE_MODES = ('HYBRID', 'AI_ONLY')


def training_mode(silver_enabled, gold_enabled):
    """Resolve independent source selection; empty training is forbidden."""
    if silver_enabled and gold_enabled:
        return 'SILVER_GOLD'
    if silver_enabled:
        return 'SILVER_ONLY'
    if gold_enabled:
        return 'GOLD_ONLY'
    raise ValueError('Pilih setidaknya satu sumber training: SILVER dan/atau GOLD.')


def _rows_from_csv(data):
    text = data.decode('utf-8-sig')
    first = text.partition('\n')[0]
    delimiter = ';' if first.count(';') > first.count(',') else ','
    reader = csv.DictReader(io.StringIO(text, newline=''), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError('CSV hasil Modul 3 tidak memiliki kolom.')
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError('CSV hasil Modul 3 memiliki nama kolom ganda.')
    rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError('CSV Modul 3 memiliki jumlah kolom yang tidak konsisten.')
    return rows


def _csv_from_zip(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        for candidate in ('pasangan_kandidat.csv', 'pasangan_rule.csv'):
            found = [name for name in names if name.rsplit('/', 1)[-1] == candidate]
            if found:
                info = archive.getinfo(found[0])
                if info.file_size > 180_000_000:
                    raise ValueError('CSV Modul 3 terlalu besar untuk diimpor dengan aman.')
                return archive.read(found[0])
        nested = [name for name in names if name.endswith('rekap_csv.zip')]
        if nested:
            info = archive.getinfo(nested[0])
            if info.file_size > 180_000_000:
                raise ValueError('Arsip Modul 3 terlalu besar untuk diimpor dengan aman.')
            return _csv_from_zip(archive.read(nested[0]))
    raise ValueError('Arsip tidak memiliki pasangan_kandidat.csv dari Modul 3.')


def load_rule_baseline(path, expected_bpn_sha, expected_pbb_sha):
    """Only accept source-bound, unmodified pairs from the exact input layers.

    Returns (accepted, all_rule_candidates). The hashes are produced by
    ``layer_fingerprint`` in Modul 3; stale CSVs cannot silently join new data.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError('File hasil Modul 3 tidak ditemukan: ' + str(path))
    if path.suffix.lower() == '.zip':
        source = _csv_from_zip(path.read_bytes())
    else:
        if path.stat().st_size > 180_000_000:
            raise ValueError('CSV Modul 3 terlalu besar untuk diimpor dengan aman.')
        source = path.read_bytes()
    rows = _rows_from_csv(source)
    if not rows:
        raise ValueError('CSV Modul 3 tidak berisi kandidat pasangan.')
    expected = ('record_bpn', 'record_pbb', 'NIB', 'NOP', 'status',
                'src_bpn_sha', 'src_pbb_sha')
    if not set(expected).issubset(rows[0]):
        raise ValueError('CSV Modul 3 belum memiliki kolom sidik-jari dan pasangan yang diwajibkan. '
                         'Jalankan ulang Modul 3 memakai plugin ini.')
    for row in rows:
        if (str(row.get('src_bpn_sha', '')).strip() != expected_bpn_sha or
                str(row.get('src_pbb_sha', '')).strip() != expected_pbb_sha):
            raise ValueError('Data BPN/PBB berbeda dengan input Modul 3. '
                             'Gunakan layer sumber yang sama atau jalankan ulang Modul 3.')
    accepted = []
    used_b, used_p, used_nib, used_nop = set(), set(), set(), set()
    for row in rows:
        if str(row.get('status', '')).strip().upper() not in ('LEVEL_1', 'LEVEL 1', '1'):
            continue
        try:
            b, p = int(row['record_bpn']), int(row['record_pbb'])
        except (ValueError, TypeError):
            raise ValueError('Indeks pasangan Level 1 Modul 3 tidak valid.')
        nib, nop = str(row.get('NIB') or '').strip(), str(row.get('NOP') or '').strip()
        if not nib or not nop:
            raise ValueError('Pasangan Level 1 Modul 3 memiliki NIB/NOP kosong.')
        if b in used_b or p in used_p or nib in used_nib or nop in used_nop:
            raise ValueError('Hasil Modul 3 berisi Level 1 yang tidak unik; periksa CSV sumber.')
        used_b.add(b); used_p.add(p); used_nib.add(nib); used_nop.add(nop)
        normalized = dict(row)
        normalized['record_bpn'], normalized['record_pbb'] = b, p
        normalized['metode_padu'] = row.get('metode_padu') or 'RULE'
        for key in ('overlap_bpn_pct', 'kesamaan_luas_tulis', 'skor_nama', 'skor_gabungan'):
            try:
                normalized[key] = float(row[key]) if row.get(key) not in ('', None) else None
            except (TypeError, ValueError):
                normalized[key] = None
        accepted.append(normalized)
    return accepted, rows


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _competitor_top(candidates, key):
    by_group = defaultdict(list)
    for row in candidates:
        by_group[row[key]].append(row)
    top = {}
    for group, rows in by_group.items():
        ranked = sorted(rows, key=lambda r: (-_number(r.get('skor_ai')), str(r.get('pair_id', ''))))
        first = ranked[0]
        top[group] = (first.get('pair_id'), _number(first.get('skor_ai')),
                      _number(ranked[1].get('skor_ai')) if len(ranked) > 1 else 0.0)
    return top


def select_ai_proposals(candidates, confidence, margin, id_count_b, id_count_p,
                        baseline=None, allow_promotion=False):
    """Rank model predictions independently; reconcile with baseline afterward.

    Returns (proposals, accepted, scored_rows, gate_failures). Proposals are
    one-to-one *suggestions*, not officially accepted pairs. ``accepted`` is
    populated only for operator-authorized, independently GOLD-tested models.
    """
    baseline = list(baseline or [])
    occupied_b = {row['record_bpn'] for row in baseline}
    occupied_p = {row['record_pbb'] for row in baseline}
    available = [r for r in candidates if
                 r['record_bpn'] not in occupied_b and r['record_pbb'] not in occupied_p]
    top_b = _competitor_top(available, 'record_bpn') if available else {}
    top_p = _competitor_top(available, 'record_pbb') if available else {}
    proposed_b, proposed_p = set(), set()
    proposals = []
    accepted = []
    failures = Counter()
    scored = []
    order = sorted(candidates, key=lambda r: (-_number(r.get('skor_ai')),
                                              str(r.get('pair_id', ''))))
    for item in order:
        row = dict(item)
        b, p = row['record_bpn'], row['record_pbb']
        nib, nop = str(row.get('NIB') or '').strip(), str(row.get('NOP') or '').strip()
        score = _number(row.get('skor_ai'))
        baseline_occupied = b in occupied_b or p in occupied_p
        competitor_b = 0.0
        competitor_p = 0.0
        if not baseline_occupied:
            tb = top_b[b]
            tp = top_p[p]
            competitor_b = tb[2] if tb[0] == row.get('pair_id') else tb[1]
            competitor_p = tp[2] if tp[0] == row.get('pair_id') else tp[1]
        gates = {
            'skor': score >= confidence,
            'id_unik': bool(nib and nop and id_count_b.get(nib, 0) == 1 and id_count_p.get(nop, 0) == 1),
            'margin': (not baseline_occupied and score - max(competitor_b, competitor_p) >= margin),
            'tersedia': not baseline_occupied,
            'satu_ke_satu': b not in proposed_b and p not in proposed_p,
        }
        row.update({'gerbang_' + key: 'Lolos' if value else 'Perlu telaah'
                    for key, value in gates.items()})
        row['gerbang_model'] = 'Lolos' if allow_promotion else 'Perlu telaah'
        reasons = [key.replace('_', ' ') for key, value in gates.items() if not value]
        if all(gates.values()):
            proposed_b.add(b); proposed_p.add(p)
            row['keputusan_ai'] = 'DITERIMA_LEVEL1' if allow_promotion else 'USULAN_AI_STUDIO'
            proposals.append(row)
            if allow_promotion:
                accepted.append(row)
        else:
            row['keputusan_ai'] = 'REKOMENDASI_STUDIO'
            failures.update(k for k, ok in gates.items() if not ok)
        if not allow_promotion and not reasons:
            reasons.append('model belum diizinkan untuk promosi otomatis')
        row['alasan_tidak_promosi'] = '; '.join(reasons)
        scored.append(row)
    return proposals, accepted, scored, failures
