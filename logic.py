"""Pure decision functions; unit-testable without a QGIS installation."""
import math


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
              dev_b, dev_p, sim, opts):
    """One pair: report ALL failures. Equality at overlap/sim threshold fails."""
    reasons = []
    if not id_b: reasons.append('NIB_KOSONG')
    if not id_p: reasons.append('NOP_KOSONG')
    if id_b and id_dups_b > 1: reasons.append('NIB_DUPLIKAT')
    if id_p and id_dups_p > 1: reasons.append('NOP_DUPLIKAT')
    if dev_b is None or dev_b > opts['max_dev']: reasons.append('LUAS_BPN_TIDAK_SESUAI')
    if dev_p is None or dev_p > opts['max_dev']: reasons.append('LUAS_PBB_TIDAK_SESUAI')
    if sim is None or sim <= opts['min_sim']: reasons.append('LUAS_TERTULIS_TIDAK_SAMA')
    if overlap_b <= opts['min_overlap']: reasons.append('OVERLAP_KURANG')
    if n_b != 1: reasons.append('MULTI_NOP' if n_b > 1 else 'TANPA_NOP')
    if n_p != 1: reasons.append('MULTI_NIB' if n_p > 1 else 'TANPA_NIB')
    return reasons


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
