"""Shared typographic and page primitives for every module's Qt PDF renderer."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFontMetrics, QPen

from .report_font import report_font
from .report_theme import GRID, INK, MUTED, NAVY, TINT, assessment_style

try:
    ELIDE_RIGHT = Qt.TextElideMode.ElideRight
except AttributeError:
    ELIDE_RIGHT = Qt.ElideRight


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
    painter.fillRect(0, 0, width, 14, NAVY)
    painter.fillRect(0, 14, width, 45, TINT)
    painter.setFont(report_font(9, True))
    painter.setPen(QPen(NAVY))
    painter.drawText(left, 43, 'NIB–NOP INTEGRATOR  ·  MODUL %s' % module)
    stamp = 'v%s' % version()
    if layer_name and str(layer_name).upper().startswith('DATA '):
        stamp = '%s  ·  %s' % (layer_name, stamp)
    if source_hash:
        stamp += '  ·  input %s' % str(source_hash)[:10]
    painter.setPen(QPen(MUTED))
    painter.setFont(report_font(9))
    stamp_width = QFontMetrics(painter.font()).horizontalAdvance(stamp)
    painter.drawText(int(width-right-stamp_width), 43, stamp)

    y = 111
    painter.setFont(report_font(19, True))
    painter.setPen(QPen(NAVY))
    for line in wrap(painter, title, width-left-right):
        painter.drawText(left, y, line)
        y += 31
    # Keep the separator between the title and subtitle, with a clear gap
    # above the subtitle on both overview and figure pages.
    rule_y = y - 6
    painter.setPen(QPen(GRID, 1))
    painter.drawLine(left, rule_y, width-right, rule_y)
    if subtitle:
        painter.setFont(report_font(10))
        painter.setPen(QPen(MUTED))
        y = rule_y + 29
        for line in wrap(painter, subtitle, width-left-right):
            painter.drawText(left, y, line)
            y += 22

    date = datetime.now(timezone(timedelta(hours=7))).strftime('%d-%m-%Y %H:%M WIB')
    footer = 'Laporan otomatis  ·  ' + date
    painter.setFont(report_font(9))
    painter.setPen(QPen(MUTED))
    painter.setPen(QPen(GRID, 1))
    painter.drawLine(left, height-64, width-right, height-64)
    painter.setPen(QPen(MUTED))
    painter.drawText(left, height-42, footer)
    number = 'Halaman %s' % page
    number_width = QFontMetrics(painter.font()).horizontalAdvance(number)
    painter.drawText(int(width-right-number_width), height-42, number)
    return (y + 13) if subtitle else (rule_y + 25)


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


class EditorialPage:
    """Compact first-page composition shared by the six report renderers."""

    def __init__(self, owner, subtitle=''):
        self.owner = owner
        self.p = owner.p
        self.left = getattr(owner, 'l', getattr(owner, 'ml', 62))
        self.right = owner.w - getattr(owner, 'r', getattr(owner, 'mr', 62))
        self.x = self.left + 168
        self.width = self.right - self.x
        self.y = 176
        if subtitle:
            self.label(self.left, 155, subtitle, 9, color=MUTED, max_width=self.right-self.left)

    def label(self, x, y, value, size=9, bold=False, color=INK, max_width=None):
        self.p.setFont(report_font(size, bold))
        self.p.setPen(QPen(color))
        value = str(value)
        if max_width is not None:
            value = QFontMetrics(self.p.font()).elidedText(value, ELIDE_RIGHT, int(max_width))
        self.p.drawText(int(x), int(y), value)

    def paragraph(self, value, size=9, bold=False, color=INK, width=None, max_lines=3,
                  x=None, leading=19):
        x = self.x if x is None else x
        width = self.right-x if width is None else width
        self.p.setFont(report_font(size, bold))
        lines = wrap(self.p, value, width)[:max_lines]
        self.p.setPen(QPen(color))
        for line in lines:
            self.p.drawText(int(x), int(self.y), line)
            self.y += leading
        return len(lines)

    def section(self, title, gap=11):
        self.y += gap
        self.p.setPen(QPen(GRID, 1))
        self.p.drawLine(self.left, int(self.y), self.right, int(self.y))
        titles = str(title).split('\n')
        for i, line in enumerate(titles):
            self.label(self.left, self.y+27+i*18, line, 10, True, NAVY)
        self.y += 43

    def headline(self, statement, support=None, status=None, status_kind='caution'):
        self.section('Kesimpulan', 0)
        self.paragraph(statement, 12, True, INK, max_lines=2, leading=25)
        if support:
            self.y += 1
            self.paragraph(support, 10, False, INK, max_lines=2, leading=20)
        if status:
            self.y += 5
            badge_width = 183 if status_kind == 'unknown' else 152
            badge_ink,badge_background,badge_text = (
                (QColor('#4A5560'),QColor('#EDF0F2'),'? BELUM DAPAT DINILAI')
                if status_kind == 'unknown' else
                (QColor('#7A4B00'),QColor('#FFF3D6'),'▲ PERLU PERHATIAN'))
            self.p.fillRect(self.x, int(self.y-14), badge_width, 24, badge_background)
            self.label(self.x+8, self.y+3, badge_text, 8, True, badge_ink)
            self.label(self.x+badge_width+10, self.y+3, status, 9, max_width=self.width-badge_width-10)
            self.y += 23

    def limit(self, message, second=None):
        self.section('Batasan\ninterpretasi')
        self.paragraph('▪ '+str(message), 9, color=QColor('#7A1F1F'), max_lines=2)
        if second:
            self.y += 4
            self.paragraph('▪ '+str(second), 9, color=QColor('#7A1F1F'), max_lines=2)

    def table(self, headers, rows, widths, max_rows=6, size=8, row_min=29):
        widths = [self.width*f for f in widths]
        starts = [self.x]
        for width in widths[:-1]:starts.append(starts[-1]+width)
        self.y += 6
        header_y = self.y
        for x, value, width in zip(starts, headers, widths):
            self.label(x+5, header_y, value, size, True, MUTED, max_width=width-10)
        self.y += 10
        self.p.setPen(QPen(MUTED, 1))
        self.p.drawLine(self.x, int(self.y), self.right, int(self.y))
        self.y += 22
        if not rows:
            self.label(self.x+5,self.y,'Tidak ada record untuk ditampilkan.',9,color=MUTED)
            self.y += 30
            return
        for i, row in enumerate(rows[:max_rows]):
            self.p.setFont(report_font(size))
            cell_lines=[wrap(self.p,str(value).replace('\n',' '),width-12)[:2]
                        for value,width in zip(row,widths)]
            height=max(row_min,18*max(len(lines) for lines in cell_lines)+12)
            if i%2:self.p.fillRect(self.x,int(self.y-18),int(self.width),int(height),TINT)
            for x,lines in zip(starts,cell_lines):
                for line_no,line in enumerate(lines):
                    self.label(x+5,self.y+line_no*17,line,size)
            self.p.setPen(QPen(GRID,1))
            self.p.drawLine(self.x,int(self.y+height-20),self.right,int(self.y+height-20))
            self.y += height

    def meter(self, rows, maximum=100):
        """Dataset/status bars retain labels and numbers for monochrome printing."""
        for name, value, total, colour, detail in rows:
            self.label(self.x,self.y,name,9,True)
            bar_x=self.x+80;bar_w=max(100,self.width-230)
            self.p.fillRect(int(bar_x),int(self.y-12),int(bar_w),13,TINT)
            ratio=max(0,min(1,float(value)/float(maximum))) if maximum else 0
            if value:self.p.fillRect(int(bar_x),int(self.y-12),max(2,int(bar_w*ratio)),13,colour)
            self.label(bar_x+bar_w+15,self.y,detail,9,True)
            self.y += 27

    def distribution(self, categories, denominator, note=''):
        """A compact stacked result strip and labelled count/percentage rows."""
        self.p.fillRect(self.x,int(self.y),int(self.width),15,TINT)
        position=self.x
        for name,count,colour,mark in categories:
            width=self.width*count/denominator if denominator else 0
            if width:
                self.p.fillRect(int(position),int(self.y),max(1,int(width)),15,colour)
            position+=width
        self.y+=32
        self.label(self.x,self.y,'Kategori',8,True,MUTED)
        self.label(self.right-126,self.y,'Jumlah',8,True,MUTED)
        self.label(self.right-55,self.y,'Porsi',8,True,MUTED)
        self.y+=16
        for name,count,colour,mark in categories:
            self.label(self.x,self.y,mark,9,True,colour)
            self.label(self.x+18,self.y,name,9)
            self.label(self.right-117,self.y,format(int(count),',').replace(',','.'),9,True)
            pct=('%.1f %%'%(100*count/denominator)).replace('.',',') if denominator else '—'
            self.label(self.right-55,self.y,pct,9)
            self.p.setPen(QPen(GRID,1))
            self.p.drawLine(self.x,int(self.y+8),self.right,int(self.y+8))
            self.y+=28
        if note:
            self.y+=4
            self.paragraph(note,8,color=MUTED,max_lines=2,leading=17)

    def actions(self, actions, maximum=2):
        self.section('Tindak lanjut')
        if not actions:
            self.paragraph('Tidak ada tindakan tambahan yang ditandai oleh indikator modul ini.',9)
            return
        for index,(title,detail) in enumerate(actions[:maximum],1):
            self.label(self.x,self.y,'T%d  %s'%(index,title),9,True,NAVY)
            self.y+=21
            self.paragraph(detail,8,max_lines=2,leading=17)
            self.y+=10

    def audit(self, metadata=None, crs=None, extras=None):
        metadata=metadata or {}
        self.section('Parameter dan\njejak audit', 13)
        facts=[]
        for name,key in [('BPN','layer_bpn'),('PBB','layer_pbb'),('CRS','crs'),
                         ('Ambang','thresholds'),('Operator','operator'),('sha256 input','hash')]:
            value=metadata.get(key)
            if value:facts.append((name,value))
        if crs and not metadata.get('crs'):facts.append(('CRS',crs))
        facts.extend(extras or [])
        if not facts:facts=[('Sumber','Metadata input tidak dicatat.')]
        for name,value in facts[:7]:
            self.label(self.x,self.y,name,8,color=MUTED)
            self.label(self.x+104,self.y,value,8,max_width=self.width-108)
            self.y += 22
        self.owner.y=self.y+15
