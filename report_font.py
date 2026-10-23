"""Load the bundled OFL typeface once for consistent PDF output on every OS."""
from pathlib import Path

from qgis.PyQt.QtGui import QFont, QFontDatabase


_FAMILY = None


def report_font(size=10, bold=False):
    global _FAMILY
    if _FAMILY is None:
        families = []
        base = Path(__file__).resolve().parent / 'fonts'
        for filename in ('SourceSans3-Regular.ttf', 'SourceSans3-Bold.ttf'):
            font_id = QFontDatabase.addApplicationFont(str(base / filename))
            if font_id >= 0:
                families.extend(QFontDatabase.applicationFontFamilies(font_id))
        _FAMILY = families[0] if families else 'Sans Serif'
    font = QFont(_FAMILY, size)
    font.setBold(bold)
    return font
