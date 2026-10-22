"""Shared typographic and page primitives for every module's Qt PDF renderer."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qgis.PyQt.QtGui import QColor, QFontMetrics, QPen

from .report_font import report_font
from .report_theme import GRID, INK, MUTED, NAVY, TINT, assessment_style


def version():
    metadata = Path(__file__).resolve().parent / 'metadata.txt'
    for line in metadata.read_text(encoding='utf-8').splitlines():
        if line.startswith('version='):
            return line.partition('=')[2].strip()
    return 'tidak tercatat'


def wrap(painter, text, width):
    metrics = QFontMetrics(painter.font())
    lines = []
    for paragraph in str(text).split('\n'):
        line = ''
        for word in paragraph.split():
            if metrics.horizontalAdvance(word) > width:
                if line:
                    lines.append(line);line=''
                part=''
                for character in word:
                    if part and metrics.horizontalAdvance(part+character)>width:
                        lines.append(part);part=character
                    else:part+=character
                line=part
                continue
            candidate = (line + ' ' + word).strip()
            if line and metrics.horizontalAdvance(candidate) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines or ['']


def page_head(painter, width, height, left, right, module, page, title,
              subtitle='', source_hash=None, layer_name=None):
    painter.fillRect(0, 0, width, height, QColor('#FFFFFF'))
    painter.setFont(report_font(9, True))
    painter.setPen(QPen(NAVY))
    painter.drawText(left, 42, 'NIB–NOP  /  Modul %s' % module)
    stamp = 'v%s' % version()
    if source_hash:
        stamp += '  ·  input %s' % str(source_hash)[:10]
    painter.setPen(QPen(MUTED))
    painter.setFont(report_font(9))
    stamp_width = QFontMetrics(painter.font()).horizontalAdvance(stamp)
    painter.drawText(int(width-right-stamp_width), 42, stamp)
    painter.setPen(QPen(GRID, 1))
    painter.drawLine(left, 54, width-right, 54)

    y = 103
    painter.setFont(report_font(19, True))
    painter.setPen(QPen(NAVY))
    for line in wrap(painter, title, width-left-right):
        painter.drawText(left, y, line)
        y += 31
    y += 4
    if subtitle:
        painter.setFont(report_font(10))
        painter.setPen(QPen(MUTED))
        for line in wrap(painter, subtitle, width-left-right):
            painter.drawText(left, y, line)
            y += 22
    painter.setPen(QPen(GRID, 1))
    painter.drawLine(left, y, width-right, y)

    date = datetime.now(timezone(timedelta(hours=7))).strftime('%d-%m-%Y %H:%M WIB')
    footer = (str(layer_name) + '  ·  ' if layer_name else '') + date
    painter.setFont(report_font(9))
    painter.setPen(QPen(MUTED))
    painter.drawText(left, height-42, footer)
    number = 'Hal. %s' % page
    number_width = QFontMetrics(painter.font()).horizontalAdvance(number)
    painter.drawText(int(width-right-number_width), height-42, number)
    return y + 25


def callout(painter, left, top, width, message, kind='note'):
    role = 'caution' if kind in ('warning','bad','caution') else 'unknown'
    ink, background, label = assessment_style(role)
    painter.setFont(report_font(10))
    lines = wrap(painter, message, width-32)
    height = 26 + 23*len(lines) + 14
    painter.fillRect(left, top, width, height, background)
    painter.setPen(QPen(ink))
    painter.setFont(report_font(10, True))
    painter.drawText(left+14, top+22, label)
    painter.setFont(report_font(10))
    yy = top+47
    for line in lines:
        painter.drawText(left+14, yy, line)
        yy += 23
    return height
