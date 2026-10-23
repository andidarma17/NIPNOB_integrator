"""Shared, print-friendly colours and marks for all NIB-NOP PDF reports.

Dataset colours describe provenance. Level and assessment colours describe a
decision. Keep those meanings separate even when a chart has only one series.
"""
from qgis.PyQt.QtGui import QBrush, QColor, QPainter, QPen, QPixmap


NAVY = QColor('#1E2250')
INK = QColor('#1B1F33')
MUTED = QColor('#52636F')
GRID = QColor('#D5D9E4')
TINT = QColor('#F3F4F9')
BPN = QColor('#3A3F9E')
PBB = QColor('#A36A00')
PBB_EDGE = QColor('#7A4B00')
LEVEL_1 = QColor('#0B7285')
LEVEL_2 = QColor('#8F7A9E')
LEVEL_2_TEXT = QColor('#5E4B70')
NO_PAIR = QColor('#AEBBC7')
NEUTRAL_EDGE = QColor('#8696A5')
OVERLAP = QColor('#B5173A')

GOOD_TEXT = QColor('#14614F')
GOOD_BG = QColor('#E6F4EF')
ATTENTION_TEXT = QColor('#7A4B00')
ATTENTION_BG = QColor('#FFF3D6')
BAD_TEXT = QColor('#9B1C1C')
BAD_BG = QColor('#FDECEC')
UNKNOWN_TEXT = QColor('#4A5560')
UNKNOWN_BG = QColor('#EDF0F2')
CAUTION_TEXT = QColor('#7A1F1F')
CAUTION_BG = QColor('#FFF1EE')

# Additional roles absent from the supplied palette. They are intentionally
# distinct from dataset and level colours.
GAP = QColor('#788892')
INVALID = QColor('#53636E')
MODEL_RF = QColor('#096B63')
MODEL_XGB = QColor('#202831')

_BRUSHES = {}


def hatch_brush(colour, role, alpha=255):
    """Tiled white hatch: PBB 135 deg/2 px/6 px; Level 2 45 deg/3 px/9 px."""
    key = (colour.name(), role, alpha)
    if key in _BRUSHES:
        return _BRUSHES[key]
    tile, step, width = (24, 6, 2) if role == 'pbb-map' else (27, 9, 3)
    pixmap = QPixmap(tile, tile)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    base = QColor(colour)
    base.setAlpha(alpha)
    painter.fillRect(0, 0, tile, tile, base)
    hatch = QColor(255, 255, 255, 140)
    painter.setPen(QPen(hatch, width))
    for offset in range(-tile * 2, tile * 3, step):
        if role == 'pbb-map':
            painter.drawLine(offset, 0, offset - tile, tile)
        else:
            painter.drawLine(offset, 0, offset + tile, tile)
    painter.end()
    brush = QBrush(pixmap)
    _BRUSHES[key] = brush
    return brush


def fill_for(colour, role=None, alpha=255):
    if role in ('pbb-map', 'level2-map'):
        return hatch_brush(colour, role, alpha)
    plain = QColor(colour)
    plain.setAlpha(alpha)
    return QBrush(plain)


def series_style(name):
    if name == 'BPN' or name.startswith('BPN '):
        return BPN, None
    if name == 'PBB' or name.startswith('PBB '):
        return PBB, None
    return NAVY, None


def category_style(label):
    title = str(label).lower()
    if 'level 1' in title:
        return LEVEL_1, None
    if 'level 2' in title:
        return LEVEL_2, None
    if title.startswith('bpn -'):
        return BPN, None
    if title.startswith('pbb -'):
        return PBB, None
    if title.startswith('tidak cocok'):
        return BAD_TEXT, None
    if title.startswith('cocok'):
        return GOOD_TEXT, None
    if 'belum pasti' in title:
        return ATTENTION_TEXT, None
    return NAVY, None


def map_style(label, colour):
    """Resolve fill, hatch, and edge without confusing dataset and status."""
    name = str(label).lower()
    if 'level 2' in name:
        return LEVEL_2, 'level2-map', LEVEL_2_TEXT
    if 'level 1' in name:
        return LEVEL_1, None, LEVEL_1
    if 'overlap' in name:
        return OVERLAP, None, OVERLAP
    if 'gap' in name:
        return GAP, None, GAP
    if 'invalid' in name:
        return INVALID, None, INVALID
    if name.startswith('pbb diverifikasi'):
        return PBB, 'pbb-map', PBB_EDGE
    if name.startswith('bpn diverifikasi'):
        return BPN, None, BPN
    return NO_PAIR, None, NEUTRAL_EDGE


def assessment_style(kind):
    return {
        'good': (INK, TINT, 'Catatan'),
        'attention': (INK, TINT, 'Catatan'),
        'bad': (CAUTION_TEXT, CAUTION_BG, 'Peringatan'),
        'unknown': (INK, TINT, 'Catatan'),
        'caution': (CAUTION_TEXT, CAUTION_BG, 'Peringatan'),
    }[kind]
