"""Print and text-contrast invariants without requiring QGIS in unit tests."""
import re
from pathlib import Path

SOURCE=(Path(__file__).resolve().parents[1]/'report_theme.py').read_text()
TOKENS=dict(re.findall(r"^([A-Z0-9_]+) = QColor\('(#[0-9A-Fa-f]{6})'\)",SOURCE,re.M))


def luminance(hex_value):
    values=[int(hex_value[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
    return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))


def contrast(one,two):
    hi,lo=sorted((luminance(one),luminance(two)),reverse=True)
    return (hi+.05)/(lo+.05)


def test_small_text_contrast():
    white='#FFFFFF'
    for foreground,background in ((TOKENS['INK'],white),(TOKENS['MUTED'],white),
                                   (TOKENS['LEVEL_2_TEXT'],white),
                                   (TOKENS['CAUTION_TEXT'],TOKENS['CAUTION_BG']),
                                   (white,TOKENS['NAVY'])):
        assert contrast(foreground,background)>=4.5


def test_dataset_luminance_separation():
    assert abs(luminance(TOKENS['BPN'])-luminance(TOKENS['PBB']))>.06
    assert "'Catatan'" in SOURCE and "'Peringatan'" in SOURCE
