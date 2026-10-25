"""Pure decision functions; unit-testable without a QGIS installation."""
import math
import re
import unicodedata
from difflib import SequenceMatcher


def empty(value):
    return value is None or str(value).strip().lower() in ('', 'null', 'none')


def ident(value):
    return '' if empty(value) else str(value).strip()


def number(value):
    if empty(value) or isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            v = value.strip().replace(' ', '')
            if ',' in v and '.' not in v:
                v = v.replace(',', '.')
            value = float(v)
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def dev_percent(recorded, geometry_area):
    a = number(recorded)
    if a is None or geometry_area is None or geometry_area <= 0:
        return None
    return 100 * abs(a - geometry_area) / geometry_area


def similarity(a, b):
    a, b = number(a), number(b)
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return 100 * min(a, b) / max(a, b)


def gate_pair(overlap_b, n_b, n_p, id_b, id_p, id_dups_b, id_dups_p,
              dev_b, dev_p, sim, opts, point_inside=None, name_state=None):
    """One pair: report ALL failures. Equality at overlap/sim threshold fails.

    ``point_inside`` (True/False) is given only when PBB is a point layer; the
    overlap gate is then replaced by "point lies inside the BPN parcel".
    ``name_state`` (see ``name_status``) gates only when ``opts['require_name']``
    is set; an unassessed name never fails a pair.
    """
    reasons = []
    if not id_b: reasons.append('NIB_KOSONG')
    if not id_p: reasons.append('NOP_KOSONG')
    if id_b and id_dups_b > 1: reasons.append('NIB_DUPLIKAT')
    if id_p and id_dups_p > 1: reasons.append('NOP_DUPLIKAT')
    if dev_b is None or dev_b > opts['max_dev']: reasons.append('LUAS_BPN_TIDAK_SESUAI')
    if dev_p is None or dev_p > opts['max_dev']: reasons.append('LUAS_PBB_TIDAK_SESUAI')
    if sim is None or sim <= opts['min_sim']: reasons.append('LUAS_TERTULIS_TIDAK_SAMA')
    if point_inside is None:
        if overlap_b <= opts['min_overlap']: reasons.append('OVERLAP_KURANG')
    elif not point_inside:
        reasons.append('TITIK_DI_LUAR_BIDANG')
    if n_b != 1: reasons.append('MULTI_NOP' if n_b > 1 else 'TANPA_NOP')
    if n_p != 1: reasons.append('MULTI_NIB' if n_p > 1 else 'TANPA_NIB')
    if opts.get('require_name') and name_state == 'TIDAK_COCOK':
        reasons.append('NAMA_TIDAK_COCOK')
    return reasons


# ---------------------------------------------------------------------------
# Name validation (nama pemegang hak BPN vs nama wajib pajak PBB)
# ---------------------------------------------------------------------------
# Titles/degrees/fillers removed anywhere in a name.
_NAME_STOP = frozenset((
    'HAJI', 'HAJJAH', 'HAJAH', 'HJ', 'DR', 'DRS', 'DRA', 'IR', 'PROF', 'DRG', 'DRH',
    'ALM', 'ALMH', 'ALMARHUM', 'ALMARHUMAH', 'BP', 'BPK', 'BAPAK', 'IBU', 'NY',
    'NYONYA', 'TN', 'TUAN', 'SDR', 'SDRI', 'SAUDARA', 'SAUDARI', 'KH', 'CS', 'DKK',
    'CQ', 'QQ', 'BIN', 'BINTI', 'PT', 'CV', 'TBK', 'PERSERO', 'UD', 'AHLI', 'WARIS',
    'SH', 'SE', 'SPD', 'SKOM', 'SKED', 'SSOS', 'SIP', 'SAG', 'SPSI', 'SHUM',
    'MM', 'MH', 'MT', 'MSI', 'MPD', 'MKES', 'MBA', 'AMD', 'AMK', 'ST', 'SP', 'SS',
    'SKM', 'SFARM', 'APT', 'SPOG', 'SPA', 'SPB'))
# Titles removed only when they open the name ("H. Ahmad", "R. Ngabehi").
_NAME_PREFIX = frozenset(('H', 'R', 'RA', 'RR', 'RM', 'KI', 'NYI', 'MAS', 'MBAH'))
_NAME_CANON = {
    'MUHAMAD': 'MUHAMAD', 'MOHAMAD': 'MUHAMAD', 'MUHAMED': 'MUHAMAD',
    'MOHAMED': 'MUHAMAD', 'MOH': 'MUHAMAD', 'MUH': 'MUHAMAD', 'MOHD': 'MUHAMAD',
    'MUHD': 'MUHAMAD', 'MHD': 'MUHAMAD', 'MHMD': 'MUHAMAD', 'MUHAMMAD': 'MUHAMAD',
    'AHMAT': 'AHMAD', 'ABD': 'ABDUL', 'ABDUL': 'ABDUL', 'ABDULAH': 'ABDULAH',
}
# Old (pre-1972) Indonesian spelling and common transliteration variants.
_NAME_SPELL = (('OE', 'U'), ('DJ', 'J'), ('TJ', 'C'), ('SJ', 'SY'), ('CH', 'H'),
               ('NJ', 'NY'))


def _clean_name_token(tok):
    for old, new in _NAME_SPELL:
        tok = tok.replace(old, new)
    tok = re.sub(r'(.)\1+', r'\1', tok)        # MUHAMMAD -> MUHAMAD
    return _NAME_CANON.get(tok, tok)


def name_tokens(value):
    """Normalised name tokens; [] when empty. Pure, deterministic."""
    if empty(value):
        return []
    text = unicodedata.normalize('NFKD', str(value))
    text = ''.join(c for c in text if not unicodedata.combining(c)).upper()
    parts = text.split(',')
    # "BUDI SANTOSO, S.H., M.H." -> degrees after a comma are dropped, but a
    # real second segment ("SANTOSO, BUDI") is kept.
    kept = [parts[0]]
    for seg in parts[1:]:
        toks = re.sub(r'[^A-Z0-9]', ' ', seg.replace('.', '')).split()
        if toks and '.' not in seg and not all(t in _NAME_STOP for t in toks):
            kept.append(seg)
    text = ' '.join(kept)
    # Dotted degrees without a comma ("S.H.", "S. Pd.", "M.Kes") -> one token.
    text = re.sub(r'\b([A-Z])\s*\.\s*([A-Z]{1,5})\b\.?',
                  lambda m: (' ' + m.group(1) + m.group(2) + ' ')
                  if (m.group(1) + m.group(2)) in _NAME_STOP else m.group(0), text)
    raw = re.sub(r'[^A-Z0-9]+', ' ', text.replace('.', '. ')).split()
    while raw and raw[0] in _NAME_PREFIX and len(raw) > 1:
        raw = raw[1:]
    tokens = [_clean_name_token(t) for t in raw if t not in _NAME_STOP]
    return [t for t in tokens if t]


def _token_similarity(a, b):
    if a == b:
        return 1.0
    if len(a) == 1 or len(b) == 1:          # initial: "M" ~ "MUHAMAD"
        return .85 if a[0] == b[0] else 0.
    return SequenceMatcher(None, a, b).ratio()


def name_similarity(a, b):
    """0-100 similarity of two personal/company names, or None if not assessable.

    Order-insensitive token matching; tokens below 0.8 similarity are
    penalised and a shorter name covering only part of a longer one is
    discounted, so "SUKARNO" vs "SUKARNO HADI" is similar but not identical.
    """
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return None
    if sorted(ta) == sorted(tb):
        return 100.
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    remaining = list(long_)
    total = 0.
    for tok in short:
        scores = [(_token_similarity(tok, other), i) for i, other in enumerate(remaining)]
        best, pos = max(scores) if scores else (0., None)
        if pos is not None and best >= .8:
            remaining.pop(pos)
        total += best if best >= .8 else best * .5
    token_score = (total / len(short)) * (.6 + .4 * len(short) / len(long_))
    whole = SequenceMatcher(None, ' '.join(ta), ' '.join(tb)).ratio() * .9
    return round(100 * max(token_score, whole), 1)


NAME_STATES = ('COCOK', 'MIRIP', 'TIDAK_COCOK', 'TIDAK_DINILAI')


def name_status(score, match=90., partial=60.):
    """COCOK (>= match), MIRIP (>= partial), TIDAK_COCOK, or TIDAK_DINILAI."""
    if score is None:
        return 'TIDAK_DINILAI'
    if score >= match:
        return 'COCOK'
    if score >= partial:
        return 'MIRIP'
    return 'TIDAK_COCOK'


def match_strength(name_state, point_mode):
    """Strength of an accepted Level 1 pair: KUAT / SEDANG / LEMAH.

    Polygon pairs already passed overlap+area gates, so they are KUAT unless
    the names contradict. A PBB point carries weaker spatial evidence; it is
    KUAT only when the names agree.
    """
    if point_mode:
        return {'COCOK': 'KUAT', 'TIDAK_COCOK': 'LEMAH'}.get(name_state, 'SEDANG')
    return 'SEDANG' if name_state == 'TIDAK_COCOK' else 'KUAT'


# ---------------------------------------------------------------------------
# Tahap 2: Level 2 rescued by a buffer search + combined (name/spatial/area) score
# ---------------------------------------------------------------------------
# Identity failures are never rescued by a name.
STAGE2_BLOCKED = frozenset(('NIB_KOSONG', 'NOP_KOSONG', 'NIB_DUPLIKAT', 'NOP_DUPLIKAT'))
STAGE2_DEFAULTS = {'stage2_buffer': 5., 'w_name': .60, 'w_spatial': .25, 'w_area': .15,
                   'stage2_min': 80., 'stage2_min_name': 60., 'stage2_margin': 10.}


def spatial_score(distance, buffer, linked=False):
    """0-100: 100 when the records touch (irisan / titik di dalam), falling
    linearly to 0 at the buffer edge."""
    if linked:
        return 100.
    if distance is None or buffer is None or buffer <= 0:
        return 0.
    return max(0., 100. * (1 - distance / buffer))


def combined_score(name_score, spatial, area_sim, weights=(.60, .25, .15)):
    """Weighted mean of name, spatial and written-area similarity (0-100).

    Weights need not sum to 1. Without an assessable name there is no score:
    the second stage exists to let the name decide, never distance alone.
    """
    if name_score is None:
        return None
    wn, ws, wl = (max(0., float(w or 0)) for w in weights)
    total = wn + ws + wl
    if total <= 0:
        return None
    return round((wn * name_score + ws * (spatial or 0.) + wl * (area_sim or 0.)) / total, 1)


def select_stage2(rows, min_score=80., min_name=60., margin=10.):
    """Pick 1:1 pairs from scored rows (``skor_gabungan``, ``skor_nama``).

    A row is accepted only when it reaches ``min_score`` and ``min_name`` and it
    is the best candidate of BOTH its BPN and its PBB record, ahead of the
    runner-up on either side by at least ``margin`` points. Every row receives
    ``alasan_tahap2`` (empty when accepted). Returns the accepted rows.
    """
    def best_of(key):
        groups = {}
        for r in rows:
            if r.get('skor_gabungan') is not None:
                groups.setdefault(r[key], []).append(r)
        return {k: sorted(v, key=lambda x: -x['skor_gabungan']) for k, v in groups.items()}
    by_b, by_p = best_of('record_bpn'), best_of('record_pbb')
    accepted = []
    for r in rows:
        score = r.get('skor_gabungan')
        reasons = []
        if score is None:
            reasons.append('NAMA_TIDAK_DINILAI')
        else:
            if score < min_score: reasons.append('SKOR_GABUNGAN_KURANG')
            if (r.get('skor_nama') or 0) < min_name: reasons.append('SKOR_NAMA_KURANG')
            for group in (by_b[r['record_bpn']], by_p[r['record_pbb']]):
                if group[0] is not r:
                    reasons.append('BUKAN_KANDIDAT_TERBAIK')
                    break
                if len(group) > 1 and score - group[1]['skor_gabungan'] < margin:
                    reasons.append('SELISIH_SKOR_KURANG')
                    break
        r['alasan_tahap2'] = ';'.join(reasons)
        if not reasons:
            accepted.append(r)
    return accepted


def normalize_verified_label(row):
    """Never convert an unresolved Level 2 into negative label 0."""
    label = str(row.get('label','')).strip()
    level = str(row.get('level','')).strip().upper().replace('_',' ')
    status = str(row.get('status_verifikasi','')).strip().upper()
    evidence = str(row.get('sumber_verifikasi','')).strip()
    if label not in ('0', '1'):
        if level in ('1', 'LEVEL 1') and status == 'DIVERIFIKASI' and evidence:
            label = '1'
        else:
            return None
    if status != 'DIVERIFIKASI' or not evidence:
        return None
    # Synthetic/demo examples must not be silently accepted as verified real data.
    if str(row.get('jenis_data','')).strip().upper() in ('SYNTHETIC','SINTETIS','DEMO'):
        return None
    if any(k in evidence.lower() for k in ('data sintetis','synthetic sample','model demo')):
        return None
    return int(label)


def model_status(n_gold, n_pos, n_neg, validated_precision, min_precision=.99):
    if n_gold < 100 or min(n_pos, n_neg) < 20 or validated_precision is None:
        return 'PREVIEW_ONLY'
    return 'ELIGIBLE_REVIEW' if validated_precision >= min_precision else 'PREVIEW_ONLY'
