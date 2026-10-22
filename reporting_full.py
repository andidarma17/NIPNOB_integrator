"""Complete, single-file PDF reports for QGIS NIB-NOP Integrator modules 1, 2, 3, 5, 6.

Uses ONLY QGIS-bundled Qt (QPdfWriter/QPainter) and QGIS record geometries.
All figures are computed from the actual in-memory result of this execution.
Training/testing Module 4 keeps its richer specialised `ai_pdf.py` implementation.
Qt 5 and Qt 6 compatible via `qgis.PyQt`.
"""
from collections import Counter
from pathlib import Path
from .compat import set_pdf_a4
import math
import textwrap

from qgis.PyQt.QtCore import QPointF, Qt
from qgis.PyQt.QtGui import (QPdfWriter, QPageSize, QPainter, QPen, QColor,
                              QBrush, QFont, QFontMetrics, QPolygonF, QPainterPath)
from .logic import number, ident, empty
from .report_font import report_font
from .report_frame import callout, page_head, wrap
from .report_theme import (NAVY, INK, MUTED, GRID, TINT, BPN, PBB, LEVEL_1,
                           LEVEL_2, LEVEL_2_TEXT, NO_PAIR, NEUTRAL_EDGE,
                           OVERLAP, GAP, INVALID, GOOD_TEXT, BAD_TEXT,
                           ATTENTION_TEXT, CAUTION_TEXT, assessment_style,
                           category_style, fill_for, map_style, series_style)

try:
    ELIDE_RIGHT=Qt.TextElideMode.ElideRight
    DASH_LINE=Qt.PenStyle.DashLine
    ODD_EVEN=Qt.FillRule.OddEvenFill
except AttributeError:
    ELIDE_RIGHT=Qt.ElideRight
    DASH_LINE=Qt.DashLine
    ODD_EVEN=Qt.OddEvenFill


def finite(value):
    x=number(value)
    return x if x is not None and math.isfinite(x) else None


def nice(value):
    if isinstance(value, float):
        return ('%.2f' % value).rstrip('0').rstrip('.')
    return str(value)


def metric_label(key):
    """Keep domain abbreviations while removing internal field names from the PDF."""
    label=str(key).replace('_',' ').replace('geom ','geometri ')
    if label[:4].lower() in ('bpn ','pbb '):
        return label[:3].upper()+' · '+label[4:].capitalize()
    return label[0].upper()+label[1:] if label else label


def human_status(value):
    labels={'PREVIEW_ONLY':'Hanya untuk daftar telaah studio',
            'NO_MODEL':'Model belum tersedia',
            'GOLD_TESTED_REVIEW_REQUIRED':'Telah diuji dengan GOLD; audit kandidat tetap wajib',
            'DITERIMA_LEVEL1':'Diterima sebagai tambahan Level 1',
            'REKOMENDASI_STUDIO':'Perlu telaah studio'}
    return labels.get(str(value),str(value).replace('_',' ').capitalize())


def count_text(value):
    return format(int(value), ',').replace(',', '.')


class Report:
    def __init__(self, folder, modnum, title, crs=None, metadata=None):
        self.path=Path(folder)/('laporan_modul%d.pdf'%modnum)
        self.pdf=QPdfWriter(str(self.path));set_pdf_a4(self.pdf);self.pdf.setResolution(120)
        self.p=QPainter(self.pdf)
        if not self.p.isActive():
            raise RuntimeError('Tidak dapat membuat PDF: '+str(self.path))
        self.w=self.pdf.width();self.h=self.pdf.height();self.l=62;self.r=62
        self.cw=self.w-self.l-self.r;self.bottom=self.h-108
        self.title=title;self.num=modnum;self.page=0;self.y=0;self.crs=crs
        self.metadata=metadata or {};self.stats={};self.notes=[];self.figure_count=0
        self.start(title)
    def font(self,size=10,bold=False):
        self.p.setFont(report_font(size,bold))
    def wrapped(self,s,width):
        return wrap(self.p,s,width)
    def start(self, heading, subtitle=''):
        if self.page:self.pdf.newPage()
        self.page+=1;self.heading=heading
        self.y=page_head(self.p,self.w,self.h,self.l,self.r,self.num,self.page,
                         heading,subtitle,self.metadata.get('hash'),self.metadata.get('layer_bpn'))
    def text(self,s,size=10,bold=False,color=INK,space=23,max_chars=100):
        self.font(size,bold)
        for line in self.wrapped(s,self.cw):
            if self.y>self.bottom:self.start('LANJUTAN - '+self.title[:38])
            self.font(size,bold);self.p.setPen(QPen(color));self.p.drawText(self.l,self.y,line)
            self.y+=space
        self.y+=4
    def sub(self,s):
        if self.y>self.bottom-56:self.start('LANJUTAN - '+self.title[:35])
        self.y+=19;self.text(s,12,True,NAVY,27,82)
    def notice(self,message,kind='caution'):
        self.font(10)
        height=40+23*len(self.wrapped(message,self.cw-32))
        if self.y+height>self.bottom:self.start('Lanjutan '+self.title[:35])
        self.y+=callout(self.p,self.l,self.y,self.cw,message,
                        'warning' if kind in ('caution','bad') else 'note')+18
    def table(self,head,rows,widths=None,limit=None):
        widths=widths or [self.cw/len(head)]*len(head)
        heights=33
        def draw_header():
            self.p.fillRect(self.l,self.y-18,self.cw,heights,NAVY)
            self.font(9,True);self.p.setPen(QPen(QColor('white')))
            x=self.l
            for col,w in zip(head,widths):
                label=QFontMetrics(self.p.font()).elidedText(str(col),ELIDE_RIGHT,int(w-16))
                self.p.drawText(int(x+8),int(self.y),label);x+=w
            self.y+=heights
        draw_header()
        visible=rows if limit is None else rows[:limit]
        for i,row in enumerate(visible):
            self.font(9);cells=[]
            for val,w in zip(row,widths):
                st=nice(val).replace('\n',' ')
                lines=self.wrapped(st,w-16)
                expanded=[]
                for line in lines:
                    if QFontMetrics(self.p.font()).horizontalAdvance(line)<=w-16:
                        expanded.append(line);continue
                    part=''
                    for char in line:
                        if part and QFontMetrics(self.p.font()).horizontalAdvance(part+char)>w-16:
                            expanded.append(part);part=char
                        else:part+=char
                    if part:expanded.append(part)
                cells.append(expanded or [''])
            row_h=max(heights,14+18*max(map(len,cells)))
            if self.y+row_h>self.bottom:self.start('LANJUTAN TABEL');draw_header()
            if i%2==0:self.p.fillRect(self.l,self.y-19,self.cw,row_h,TINT)
            self.p.setPen(QPen(INK));x=self.l
            for val,w,lines in zip(row,widths,cells):
                numeric=isinstance(val,(int,float))
                for k,line in enumerate(lines):
                    metrics=QFontMetrics(self.p.font())
                    tx=x+w-8-metrics.horizontalAdvance(line) if numeric else x+8
                    self.p.drawText(int(tx),int(self.y+k*18),line)
                x+=w
            self.y+=row_h
        if limit is not None and len(rows)>limit:self.text('Rincian lengkap tersedia pada rekap_csv.zip.',9,color=MUTED)
        self.y+=16
    def intro(self,stats,notes,warning=None,headline=None,next_step=None,kpis=None,actions=None):
        self.stats=dict(stats);self.notes=list(notes);self.warning=warning
        self.actions=list(actions or [])
        if headline:self.text(headline,19,True,NAVY,space=34)
        if next_step:self.text('Prioritas: '+next_step,10,color=INK,space=22)
        kpis=list(kpis or [])[:4]
        if kpis:
            self.y+=22
            cell=self.cw/len(kpis)
            for i,(label,value,context) in enumerate(kpis):
                x=self.l+i*cell
                if i:
                    self.p.setPen(QPen(GRID,1));self.p.drawLine(int(x-11),int(self.y-15),int(x-11),int(self.y+94))
                self.font(9,True);self.p.setPen(QPen(MUTED))
                self.p.drawText(int(x),int(self.y),str(label))
                value_text=count_text(value) if isinstance(value,(int,float)) else str(value)
                size=29
                while size>18:
                    self.font(size,True)
                    if QFontMetrics(self.p.font()).horizontalAdvance(value_text)<=cell-24:break
                    size-=1
                self.font(size,True);self.p.setPen(QPen(NAVY))
                self.p.drawText(int(x),int(self.y+48),value_text)
                self.font(9);self.p.setPen(QPen(MUTED))
                for line_i,line in enumerate(self.wrapped(context,cell-16)[:2]):
                    self.p.drawText(int(x),int(self.y+75+line_i*17),line)
            self.y+=122
        self.sub('Tindakan prioritas')
        for i,(title,detail) in enumerate(self.actions[:3],1):
            self.font(10,True);self.p.setPen(QPen(NAVY))
            self.p.drawText(self.l,self.y,'T%d  %s'%(i,title))
            self.y+=22
            self.text(detail,9,color=INK,space=19)
        if not self.actions:self.text('Tidak ada tindakan yang ditandai oleh indikator modul ini.',10)
        if warning:
            self.y+=9;self.notice(warning,'warning')
        self.sub('Dasar laporan')
        facts=[]
        for label,key in [('BPN','layer_bpn'),('PBB','layer_pbb'),('Kolom BPN','fields_bpn'),
                          ('Kolom PBB','fields_pbb'),('CRS','crs'),('Ambang','thresholds'),
                          ('Operator','operator'),('Sidik-jari','hash')]:
            value=self.metadata.get(key)
            if value:facts.append('%s: %s'%(label,str(value)[:95]))
        if self.crs and not self.metadata.get('crs'):facts.append('CRS: '+self.crs)
        for item in facts:self.text(item,9,color=MUTED,space=18)
        if not facts:self.text('Metadata input tidak disertakan oleh pemanggil laporan.',9,color=MUTED)
    def footer_recommendations(self,items,appendix=None):
        # The three most urgent actions are already on page one. This closing
        # section keeps provenance and the full indicator audit without repeating them.
        if appendix:
            if self.y>self.bottom-190:self.start('Arsip dan lampiran')
            self.sub('Arsip hasil')
            for s in appendix:self.text('- '+str(s),9)
        if self.stats or self.notes:
            if self.y>self.bottom-250:self.start('Lampiran · indikator dan metode')
            if self.stats:
                self.sub('Seluruh indikator')
                self.table(['Indikator','Hasil'],[(metric_label(k),nice(v)) for k,v in self.stats.items()],
                           [self.cw*.66,self.cw*.34],limit=len(self.stats))
            if self.notes:
                self.sub('Dasar pemeriksaan')
                for msg in self.notes:self.text(str(msg),9,space=20)
    def figpage(self,number,title,description):
        if self.figure_count%2==0 or self.y>self.bottom-480:
            self.start(title)
        else:
            self.sub(title)
        self.figure_count+=1
        if description:self.text(description,9,color=MUTED,space=18)
    def no_data(self,message):
        self.notice('Visualisasi tidak tersedia: '+message,'unknown')
    def category_marker(self,x,y,label):
        name=str(label).lower()
        color,role=category_style(label)
        if 'level 2' in name:
            self.p.setPen(QPen(LEVEL_2_TEXT,1.2));self.p.setBrush(fill_for(color,role))
            self.p.drawPolygon(QPolygonF([QPointF(x+6,y-12),QPointF(x+12,y-6),
                                          QPointF(x+6,y),QPointF(x,y-6)]))
        elif 'level 1' in name:
            self.p.setPen(QPen(color,1));self.p.setBrush(QBrush(color))
            self.p.drawRect(int(x),int(y-12),12,12)
        elif name.startswith('tidak cocok'):
            self.p.setPen(QPen(color,2))
            self.p.drawLine(int(x),int(y-12),int(x+12),int(y))
            self.p.drawLine(int(x+12),int(y-12),int(x),int(y))
        elif name.startswith('cocok'):
            self.p.setPen(QPen(color,2))
            self.p.drawLine(int(x),int(y-6),int(x+4),int(y-2))
            self.p.drawLine(int(x+4),int(y-2),int(x+13),int(y-13))
        elif 'belum pasti' in name:
            self.p.setPen(QPen(color,2));self.p.setBrush(QBrush())
            self.p.drawEllipse(int(x),int(y-12),12,12)
        else:return False
        self.p.setBrush(QBrush())
        return True
    def bar(self,labels,series,value_suffix='',horizontal=False):
        # grouped bar chart with value labels; one page per figure for readability
        if not labels or not series:self.no_data('Tidak ada kategori.');return
        if horizontal:
            self._bar_horizontal(labels,series,value_suffix);return
        ytop=self.y+22;bottom=min(self.bottom-125,ytop+315)
        xleft=self.l+70;xright=self.w-self.r-21
        vals=[max(0,float(finite(v) or 0)) for _,x in series for v in x]
        ymax=max(vals+[1])*1.15
        self._axes(xleft,ytop,xright,bottom,ymax)
        n=len(labels);group=(xright-xleft)/max(1,n);bw=min(42,max(8,group*.65/max(1,len(series))))
        for i,label in enumerate(labels):
            cx=xleft+(i+.5)*group
            for j,(legend,data) in enumerate(series):
                v=max(0,float(finite(data[i]) or 0))
                barheight=(v/ymax)*(bottom-ytop)
                x=cx+(j-(len(series)-1)/2)*bw*1.3-bw*.5
                color,role=(category_style(label) if len(series)==1 else series_style(legend))
                if self.num==3 and 'Alasan Level 2' in self.heading:color,role=LEVEL_2,'level2'
                self.p.fillRect(int(x),int(bottom-barheight),int(bw),int(barheight),fill_for(color,role))
                self.font(9);self.p.setPen(QPen(INK))
                self.p.drawText(int(x-4),int(bottom-barheight-9),nice(round(v,2))+value_suffix)
            self.font(9);self.p.setPen(QPen(MUTED))
            wrapped=textwrap.wrap(str(label),max(7,int(group/9)),break_long_words=True)
            marker_x=cx-group*.46
            has_marker=self.category_marker(marker_x,bottom+26,label)
            self.p.setPen(QPen(MUTED));self.font(9)
            for k,z in enumerate(wrapped[:3]):self.p.drawText(int(marker_x+(18 if has_marker else 0)),int(bottom+26+k*17),z)
        if len(series)>1:
            for j,(label,_) in enumerate(series):
                xx=xleft+j*175;color,role=series_style(label)
                self.p.fillRect(int(xx),int(bottom+105),12,12,fill_for(color,role))
                self.p.setPen(QPen(INK));self.font(9);self.p.drawText(int(xx+19),int(bottom+115),str(label)[:23])
        self.y=bottom+112
    def _axes(self,xleft,top,right,bottom,ymax):
        self.p.setPen(QPen(GRID,1))
        for k in range(5):
            val=ymax*k/4;yy=bottom-(bottom-top)*k/4
            self.p.drawLine(int(xleft),int(yy),int(right),int(yy))
            self.font(9);self.p.setPen(QPen(MUTED));self.p.drawText(int(self.l),int(yy+4),'%d'%round(val))
            self.p.setPen(QPen(GRID))
    def _bar_horizontal(self,labels,series,suffix):
        label_col=245;x0=self.l+label_col;xright=self.w-self.r-65
        vals=[max(0,float(finite(v) or 0)) for _,x in series for v in x]
        vmax=max(vals+[1]);row_h=min(36,max(28,int(390/max(1,len(labels)))))
        self.y+=15
        for i,label in enumerate(labels):
            if self.y+row_h>self.bottom-78:self.start('LANJUTAN GRAFIK')
            marker=self.num==3 and 'Alasan Level 2' in self.heading
            if marker:self.category_marker(self.l,self.y+10,'Level 2')
            self.font(9);self.p.setPen(QPen(INK));self.p.drawText(self.l+(18 if marker else 0),self.y+10,str(label)[:34])
            for j,(name,vec) in enumerate(series):
                v=max(0,float(finite(vec[i]) or 0));bh=max(5,int((row_h-8)/max(1,len(series))))
                yy=self.y+(j-.5)*bh
                ww=int((xright-x0)*v/vmax)
                color,role=(category_style(label) if len(series)==1 else series_style(name))
                if self.num==3 and 'Alasan Level 2' in self.heading:color,role=LEVEL_2,'level2'
                self.p.fillRect(int(x0),int(yy),max(0,ww),max(3,bh-1),fill_for(color,role))
                self.p.setPen(QPen(MUTED));self.font(9)
                self.p.drawText(int(x0+max(0,ww)+7),int(yy+bh-2),nice(v)+suffix)
            self.y+=row_h
        self.y+=18
        if len(series)>1:
            for i,(name,_) in enumerate(series):
                color,role=series_style(name)
                self.p.fillRect(self.l+i*230,self.y-12,12,12,fill_for(color,role));self.font(9);self.p.setPen(QPen(INK))
                self.p.drawText(self.l+i*230+19,self.y,str(name))
        self.y+=20
    def histogram(self,values,unit='m²',max_percentile=99):
        data=sorted(x for x in (finite(v) for v in values) if x is not None and x>0)
        if not data:self.no_data('Luas numerik positif tidak tersedia.');return
        k=min(len(data)-1,int(.99*(len(data)-1))) if max_percentile==99 else len(data)-1
        upper=data[k] if data[k]>0 else max(data)
        bin_count=30
        hist=[0]*bin_count
        for v in data:
            if v>upper:continue
            cell=min(bin_count-1,int(v/max(upper,1e-9)*bin_count))
            hist[cell]+=1
        ymax=max(hist+[1])*1.14
        top=self.y+22;bottom=min(self.bottom-120,top+315)
        left=self.l+75;right=self.w-self.r-25
        self._axes(left,top,right,bottom,ymax)
        barwidth=(right-left)/bin_count
        color,role=series_style('PBB' if 'PBB' in self.heading else 'BPN')
        self.p.setPen(QPen(color))
        for i,v in enumerate(hist):
            hh=(v/ymax)*(bottom-top)
            self.p.fillRect(int(left+i*barwidth+1),int(bottom-hh),max(1,int(barwidth-2)),int(hh),fill_for(color,role))
        self.font(9);self.p.setPen(QPen(MUTED))
        for i in range(6):
            value=upper*i/5
            x=left+(right-left)*i/5
            self.p.drawText(int(x-14),int(bottom+25),'%.0f'%value)
        self.y=bottom+67
        self.text('Luas tertulis (%s) pada sumbu horizontal; jumlah bidang pada sumbu vertikal.'%unit,9,color=MUTED)
        self.text('N numerik positif=%d; persentil 99=%.2f %s; %d nilai ekstrem tidak ditampilkan untuk keterbacaan.'%
                  (len(data),upper,unit,sum(v>upper for v in data)),9,color=MUTED)
    def histogram_pair(self,b_values,p_values,min_area,max_area):
        groups=[]
        for values in (b_values,p_values):
            groups.append(sorted(v for v in (finite(x) for x in values) if v is not None and v>0))
        combined=sorted(groups[0]+groups[1])
        if not combined:self.no_data('Tidak ada luas tertulis positif yang dapat dibandingkan.');return
        upper=combined[int(.99*(len(combined)-1))] or combined[-1]
        bins=16;counts=[]
        for data in groups:
            row=[0]*bins
            for value in data:
                if value<=upper:row[min(bins-1,int(value/upper*bins))]+=1
            counts.append(row)
        ymax=max(1,max(counts[0]+counts[1]))*1.15
        top=self.y+24;bottom=min(self.bottom-120,top+315)
        left=self.l+72;right=self.w-self.r-20
        self._axes(left,top,right,bottom,ymax)
        width=(right-left)/bins
        for i in range(bins):
            for j,color in enumerate((BPN,PBB)):
                value=counts[j][i];h=(value/ymax)*(bottom-top)
                self.p.fillRect(int(left+i*width+j*width*.45),int(bottom-h),
                                max(2,int(width*.39)),int(h),color)
        self.font(9);self.p.setPen(QPen(MUTED))
        for fraction in (0,.5,1):
            x=left+(right-left)*fraction
            self.p.drawText(int(x-16),int(bottom+24),'%.0f'%(upper*fraction))
        for threshold,label in ((min_area,'Min'),(max_area,'Maks')):
            if 0<threshold<=upper:
                x=left+(right-left)*threshold/upper
                self.p.setPen(QPen(OVERLAP,1))
                self.p.drawLine(int(x),int(top),int(x),int(bottom))
                self.font(9);self.p.drawText(int(x+4),int(top+15),label)
        self.y=bottom+60
        self.text('BPN gelap; PBB terang. Sumbu X: luas tertulis (m²). Batas visual P99 %.0f m²; %s nilai di atasnya tidak digambar.'%
                  (upper,count_text(sum(v>upper for v in combined))),9,color=MUTED,space=19)
    def area_comparison(self,b_rows,b_field,p_rows,p_field,min_area,max_area):
        groups=[]
        for rows,field in ((b_rows,b_field),(p_rows,p_field)):
            data=[]
            for row in rows:
                written=finite(row['a'].get(field));geom=row.get('geom')
                if written is None or written<=0 or geom is None or geom.isNull() or geom.isEmpty():continue
                actual=finite(geom.area())
                if actual is not None and actual>0:data.append((actual,written))
            groups.append(data)
        values=sorted(max(x,y) for group in groups for x,y in group)
        if not values:self.no_data('Tidak ada pasangan luas tertulis dan luas geometri positif.');return
        upper=values[int(.99*(len(values)-1))] or values[-1]
        top=self.y+22;bottom=min(self.bottom-120,top+315)
        left=self.l+72;right=self.w-self.r-22
        self.p.setPen(QPen(GRID,1));self.p.drawRect(int(left),int(top),int(right-left),int(bottom-top))
        self.p.setPen(QPen(MUTED,1));self.p.drawLine(int(left),int(bottom),int(right),int(top))
        for threshold in (min_area,max_area):
            if 0<threshold<=upper:
                x=left+threshold/upper*(right-left)
                self.p.setPen(QPen(GRID,1));self.p.drawLine(int(x),int(top),int(x),int(bottom))
        for group,color in zip(groups,(BPN,PBB)):
            self.p.setPen(QPen(color,1));self.p.setBrush(QBrush(color))
            step=max(1,len(group)//10000)
            for x,y in group[::step]:
                if x>upper or y>upper:continue
                px=left+x/upper*(right-left);py=bottom-y/upper*(bottom-top)
                self.p.drawEllipse(QPointF(px,py),2.3,2.3)
        self.p.setBrush(QBrush());self.y=bottom+61
        self.text('X: luas geometri (m²). Y: luas tertulis (m²). Garis diagonal berarti sama; garis tegak menandai ambang luas yang terlihat.',9,color=MUTED,space=19)
    def scatter(self,values):
        vals=[(i+1,finite(v)) for i,v in enumerate(values)]
        vals=[(x,y) for x,y in vals if y is not None and y>0]
        if not vals:self.no_data('Tidak ada nilai luas positif.');return
        top=self.y+22;bottom=min(self.bottom-115,top+315)
        left=self.l+80;right=self.w-self.r-30
        lo=min(math.log10(y) for _,y in vals);hi=max(math.log10(y) for _,y in vals)
        if hi==lo:hi+=1
        maxx=max(x for x,_ in vals)
        self.p.setPen(QPen(GRID));self.p.drawRect(int(left),int(top),int(right-left),int(bottom-top))
        for k in range(5):
            zz=lo+(hi-lo)*k/4;yy=bottom-(bottom-top)*k/4
            self.p.drawLine(int(left),int(yy),int(right),int(yy))
            self.font(9);self.p.setPen(QPen(MUTED));self.p.drawText(int(self.l),int(yy+4),'%.1f'%zz)
            self.p.setPen(QPen(GRID))
        color=PBB if 'PBB' in self.heading else BPN
        self.p.setPen(QPen(color,1.4));self.p.setBrush(QBrush(color))
        for x,y in vals:
            px=left+(x/maxx)*(right-left);py=bottom-(math.log10(y)-lo)/(hi-lo)*(bottom-top)
            self.p.drawEllipse(QPointF(float(px),float(py)),1.9,1.9)
        self.p.setBrush(QBrush())
        self.y=bottom+26
        self.text('Sumbu X: urutan record. Sumbu Y: log10(luas m²). Setiap titik mewakili satu record dengan luas positif.',9,color=MUTED)
    def xy_scatter(self,xy_pairs,xlabel,ylabel,xmax=100,ymax=100,x_threshold=None,y_threshold=None):
        good=[(finite(x),finite(y)) for x,y in xy_pairs]
        good=[(x,y) for x,y in good if x is not None and y is not None]
        if not good:self.no_data('Data numerik berpasangan tidak tersedia.');return
        top=self.y+20;bottom=min(self.bottom-125,top+315)
        left=self.l+78;right=self.w-self.r-25
        self.p.setPen(QPen(GRID));self.p.drawRect(int(left),int(top),int(right-left),int(bottom-top))
        for i in range(5):
            x=left+(right-left)*i/4; y=bottom-(bottom-top)*i/4
            self.p.drawLine(int(left),int(y),int(right),int(y))
            self.font(9);self.p.setPen(QPen(MUTED))
            self.p.drawText(int(x-10),int(bottom+23),'%.0f'%(xmax*i/4))
            self.p.drawText(self.l,int(y+4),'%.0f'%(ymax*i/4))
            self.p.setPen(QPen(GRID))
        self.p.setPen(QPen(OVERLAP,1.3,DASH_LINE))
        if x_threshold is not None:
            xx=left+max(0,min(1,float(x_threshold)/xmax))*(right-left)
            self.p.drawLine(int(xx),int(top),int(xx),int(bottom))
            self.font(9);self.p.drawText(int(xx+5),int(top+17),'Ambang %.1f%%'%x_threshold)
        if y_threshold is not None:
            yy=bottom-max(0,min(1,float(y_threshold)/ymax))*(bottom-top)
            self.p.drawLine(int(left),int(yy),int(right),int(yy))
            self.font(9);self.p.drawText(int(right-132),int(yy-5),'Ambang %.1f%%'%y_threshold)
        self.p.setPen(QPen(NAVY,1.2));self.p.setBrush(QBrush(NAVY))
        for x,y in good[:12000]:
            xp=left+(min(xmax,max(0,x))/xmax)*(right-left)
            yp=bottom-(min(ymax,max(0,y))/ymax)*(bottom-top)
            self.p.drawEllipse(QPointF(float(xp),float(yp)),1.6,1.6)
        self.p.setBrush(QBrush());self.y=bottom+65
        self.text('X: '+xlabel+'; Y: '+ylabel+'. Setiap titik mewakili satu calon pasangan.',9,color=MUTED)
    def map(self, datasets, title='', focus=None, max_features=4000):
        """datasets: [(records, QColor/string, predicate, label), ...]
        Geometry visualisation uses the original planar coordinates, without basemap.
        """
        self.sub(title)
        valid=[];bbox=[];group_counts=[]
        for rows,col,predicate,label in datasets:
            colour,role,edge=map_style(label,col)
            count=0
            for r in rows:
                g=r.get('geom')
                if g is None or g.isNull() or g.isEmpty():continue
                if predicate is not None and not predicate(r):continue
                bb=g.boundingBox()
                if focus is not None and not bb.intersects(focus):continue
                valid.append((g,colour,role,edge));bbox.append(bb)
                count+=1
                if count>=max_features:break
            group_counts.append(count)
        if not valid:self.no_data('Tidak ada geometri untuk batas peta ini.');return
        self.y+=10
        shown=[j for j,count in enumerate(group_counts) if count]
        for pos,j in enumerate(shown):
            _rows,col,_pred,label=datasets[j]
            lx=self.l+(pos%3)*self.cw/3
            if pos and pos%3==0:self.y+=28
            colour,role,edge=map_style(label,col)
            self.p.setPen(QPen(edge,1.2));self.p.setBrush(fill_for(colour,role))
            if role=='level2-map':
                shape=QPolygonF([QPointF(lx+7,self.y-14),QPointF(lx+14,self.y-7),
                                 QPointF(lx+7,self.y),QPointF(lx,self.y-7)])
                self.p.drawPolygon(shape)
            else:self.p.drawRect(int(lx),int(self.y-14),14,14)
            self.font(9);self.p.setPen(QPen(INK))
            self.p.drawText(int(lx+21),int(self.y-2),str(label)[:26]+' (%d)'%group_counts[j])
        self.p.setBrush(QBrush())
        self.y+=18
        x0=min(b.xMinimum() for b in bbox);x1=max(b.xMaximum() for b in bbox)
        y0=min(b.yMinimum() for b in bbox);y1=max(b.yMaximum() for b in bbox)
        if focus is not None:
            x0=focus.xMinimum();x1=focus.xMaximum();y0=focus.yMinimum();y1=focus.yMaximum()
        dx=max(x1-x0,.001);dy=max(y1-y0,.001)
        padx=.025*dx;pady=.025*dy;x0-=padx;x1+=padx;y0-=pady;y1+=pady
        dx=x1-x0;dy=y1-y0
        top=self.y+15;bottom=min(self.bottom-128,top+740)
        left=self.l+15;right=self.w-self.r-20
        self.p.fillRect(int(left),int(top),int(right-left),int(bottom-top),QColor('#FCFCFE'))
        self.p.setPen(QPen(GRID));self.p.drawRect(int(left),int(top),int(right-left),int(bottom-top))
        scale=min((right-left)/dx,(bottom-top)/dy)
        midx=(x0+x1)/2;midy=(y0+y1)/2
        xx=(left+right)/2;yy=(top+bottom)/2
        def xy(pt):return QPointF(float(xx+(pt.x()-midx)*scale),float(yy-(pt.y()-midy)*scale))
        self.p.save()
        self.p.setClipRect(int(left),int(top),int(right-left),int(bottom-top))
        for geom,color,role,edge in valid:
            geompolys=[]
            try:
                if geom.isMultipart():geompolys=geom.asMultiPolygon()
                else:geompolys=[geom.asPolygon()]
            except (TypeError,ValueError):continue
            outline=QColor(edge);outline.setAlpha(190)
            self.p.setPen(QPen(outline,1.1));self.p.setBrush(fill_for(color,role,130))
            for poly in geompolys:
                if not poly or len(poly[0])<3:continue
                path=QPainterPath();path.setFillRule(ODD_EVEN)
                for ring in poly:
                    if len(ring)<3:continue
                    step=max(1,len(ring)//800)
                    points=[xy(point) for point in ring[::step]]
                    if len(points)<3:continue
                    path.moveTo(points[0])
                    for point in points[1:]:path.lineTo(point)
                    path.closeSubpath()
                self.p.drawPath(path)
        self.p.setBrush(QBrush())
        self.p.restore()
        # All map coordinates are projected metres. The graphic scale remains
        # valid if a PDF viewer or printer resizes the page.
        target_metres=120/scale
        power=10**math.floor(math.log10(target_metres))
        bar_metres=min((unit*power for unit in (1,2,5,10)),
                       key=lambda value:abs(value-target_metres))
        bar_px=bar_metres*scale
        sx=left;sy=bottom+22
        self.p.setPen(QPen(NAVY,1))
        self.p.fillRect(int(sx),int(sy),int(bar_px/2),8,NAVY)
        self.p.drawRect(int(sx),int(sy),int(bar_px),8)
        self.font(9);self.p.setPen(QPen(MUTED))
        self.p.drawText(int(sx),int(sy+25),'0')
        self.p.drawText(int(sx+bar_px-10),int(sy+25),'%g m'%bar_metres)
        crs_label='CRS peta: '+str(self.crs) if self.crs else 'CRS peta: tidak tercatat'
        self.p.drawText(int(right-245),int(sy+25),crs_label)
        self.p.setPen(QPen(NAVY,1.5))
        self.p.drawLine(int(right-22),int(top+52),int(right-22),int(top+22))
        self.p.drawLine(int(right-22),int(top+22),int(right-28),int(top+31))
        self.p.drawLine(int(right-22),int(top+22),int(right-16),int(top+31))
        self.font(9,True);self.p.drawText(int(right-27),int(top+18),'U')
        self.font(9);self.p.setPen(QPen(MUTED))
        self.p.drawText(int(left+4),int(bottom-8),'E %.1f · N %.1f'%(x0,y0))
        upper='E %.1f · N %.1f'%(x1,y1)
        uw=QFontMetrics(self.p.font()).horizontalAdvance(upper)
        self.p.drawText(int(right-uw-4),int(bottom-8),upper)
        self.y=bottom+72
        self.text('Peta indikatif tanpa peta dasar. Legenda menghitung fitur yang digambar (maksimal %d per kategori). Periksa batas dan lokasi pada layer QGIS.'%max_features,9,color=MUTED)
    def close(self):
        self.p.end();return str(self.path)


def report1(folder, b_info,p_info, stats, tables, min_area,max_area,crs=None,metadata=None):
    """b_info/p_info=(records, identity_field, area_field) after qa_attribute."""
    rep=Report(folder,1,'Pemeriksaan kelengkapan atribut',crs,metadata)
    missing_b=stats.get('BPN identitas_kosong',0)
    missing_p=stats.get('PBB identitas_kosong',0)
    headline=('Tidak ada record BPN maupun PBB yang dapat diperiksa.'
              if not stats.get('BPN jumlah_record',0) and not stats.get('PBB jumlah_record',0) else
              '%s identitas BPN dan %s identitas PBB kosong.'%
              (count_text(missing_b),count_text(missing_p)) if missing_b or missing_p else
              'Tidak ditemukan identitas kosong pada BPN maupun PBB.')
    priority=('cocokkan identitas kosong dengan sumber administrasi.' if missing_b or missing_p
              else 'periksa duplikat dan luas tertulis sebelum melanjutkan.')
    actions=[]
    if missing_b or missing_p:
        actions.append(('Lengkapi identitas kosong',
            '%s record BPN dan %s record PBB perlu dicocokkan dengan sumber administrasi sebelum pemaduan.'%
            (count_text(missing_b),count_text(missing_p))))
    dup_b=stats.get('BPN record_duplikat',0);dup_p=stats.get('PBB record_duplikat',0)
    if dup_b or dup_p:
        actions.append(('Telaah identitas duplikat',
            '%s record BPN dan %s record PBB memakai identitas yang berulang; periksa apakah pengulangan sah.'%
            (count_text(dup_b),count_text(dup_p))))
    area_b=stats.get('BPN record_luas_bermasalah',0);area_p=stats.get('PBB record_luas_bermasalah',0)
    if area_b or area_p:
        actions.append(('Periksa luas tertulis',
            '%s record BPN dan %s record PBB memiliki luas kosong, tak numerik, atau di luar ambang. Bandingkan dengan dokumen sumber.'%
            (count_text(area_b),count_text(area_p))))
    if not actions:actions.append(('Lanjutkan pemeriksaan spasial',
        'Indikator atribut yang diperiksa tidak menandai kasus; periksa geometri sebelum menentukan pasangan.'))
    kpis=[('Jumlah record',count_text(stats.get('BPN jumlah_record',0))+' / '+count_text(stats.get('PBB jumlah_record',0)),'BPN / PBB'),
          ('Identitas kosong',count_text(missing_b)+' / '+count_text(missing_p),'BPN / PBB'),
          ('ID duplikat',count_text(dup_b)+' / '+count_text(dup_p),'BPN / PBB'),
          ('Luas bermasalah',count_text(area_b)+' / '+count_text(area_p),'BPN / PBB')]
    rep.intro(stats,[f'Ambang awal luas: {min_area:g} - {max_area:g} m².',
             'Identitas duplikat dihitung dengan mengabaikan nilai kosong.',
             'Kolom luas dapat bertipe teks selama nilainya dapat dikonversi menjadi angka.'],
             'Nilai luas di luar ambang perlu verifikasi; bukan otomatis salah.',headline,priority,kpis,actions)
    b,bi,ba=b_info;p,pi,pa=p_info
    bs=lambda key:stats.get('BPN '+key,0)
    ps=lambda key:stats.get('PBB '+key,0)
    cats=['Identitas kosong','Record duplikat','Luas bermasalah']
    keys=['identitas_kosong','record_duplikat','record_luas_bermasalah']
    rates=[('BPN',[100*bs(k)/max(1,bs('jumlah_record')) for k in keys]),
           ('PBB',[100*ps(k)/max(1,ps('jumlah_record')) for k in keys])]
    if any(value for _,series in rates for value in series):
        rep.figpage(1,'Proporsi temuan atribut','Persentase terhadap jumlah record masing-masing dataset.')
        rep.bar(cats,rates,value_suffix='%')
    entries=[]
    for tag,rows in [('BPN',b),('PBB',p)]:
        fields=sorted({k for r in rows for k in r['a'] if k not in ('id_kosong','id_duplikat','luas_flag') and not k.startswith('_')})
        for f in fields:
            count=sum(1 for r in rows if empty(r['a'].get(f)))
            if count:entries.append((tag,f,count,len(rows),100*count/max(1,len(rows))))
    entries.sort(key=lambda item:(-item[4],-item[2],item[0],item[1]))
    if entries:
        shown=entries[:12]
        rep.figpage(2,'Kolom yang memiliki nilai kosong','Diurutkan dari persentase tertinggi; label memuat jumlah kosong / jumlah record.')
        rep.bar(['%s · %s (%s/%s)'%(tag,f,count,total) for tag,f,count,total,_ in shown],
                [('Kosong (%)',[item[4] for item in shown])],value_suffix='%',horizontal=True)
    else:
        rep.text('Semua kolom sumber yang diperiksa berisi nilai; grafik kekosongan tidak diperlukan.',10)
    if any((finite(row['a'].get(field)) or 0)>0 for rows,field in ((b,ba),(p,pa)) for row in rows):
        rep.figpage(3,'Distribusi luas tertulis','BPN dan PBB memakai sumbu yang sama; nilai di atas P99 disisihkan dari grafik.')
        rep.histogram_pair([row['a'].get(ba) for row in b],[row['a'].get(pa) for row in p],min_area,max_area)
    if any((finite(row['a'].get(field)) or 0)>0 and row.get('geom') is not None and
           not row['geom'].isNull() and not row['geom'].isEmpty()
           for rows,field in ((b,ba),(p,pa)) for row in rows):
        rep.figpage(4,'Luas tertulis dibanding geometri','Titik yang jauh dari diagonal perlu ditelaah terhadap dokumen sumber.')
        rep.area_comparison(b,ba,p,pa,min_area,max_area)
    rep.footer_recommendations(actions,
        ['rekap_csv.zip: rincian kolom kosong, identitas duplikat, dan luas bermasalah.', 'Layer audit atribut disimpan dalam format spasial yang dipilih.'])
    return rep.close()


def report2(folder,b_rows,p_rows,stats,notes,overlap_b,overlap_p,gaps,crs=None,metadata=None):
    r=Report(folder,2,'Pemeriksaan dan perbaikan kualitas spasial',crs,metadata)
    overlap_count=stats.get('bpn_overlap',0)+stats.get('pbb_overlap',0)
    gap_count=stats.get('bpn_gap_baru',0)+stats.get('pbb_gap_baru',0)
    invalid_count=stats.get('bpn_geom_invalid',0)+stats.get('pbb_geom_invalid',0)
    empty_geom_count=stats.get('bpn_geom_kosong',0)+stats.get('pbb_geom_kosong',0)
    headline=('%s record terindikasi overlap internal pada BPN dan PBB.'%count_text(overlap_count)
              if overlap_count else '%s geometri awal invalid dan %s kosong.'%
              (count_text(invalid_count),count_text(empty_geom_count))
              if invalid_count or empty_geom_count else '%s kandidat gap tercatat; tidak ada overlap internal yang ditandai.'%count_text(gap_count)
              if gap_count else 'Tidak ada overlap internal atau gap baru yang ditandai.')
    priority=('telaah irisan overlap dengan dokumen sumber.' if overlap_count else
              'periksa geometri yang invalid atau kosong.' if invalid_count or empty_geom_count else
              'verifikasi kandidat gap.' if gap_count else 'lanjutkan ke pemaduan berbasis aturan.')
    actions=[]
    fixed=stats.get('bpn_geom_fixed',0)+stats.get('pbb_geom_fixed',0)
    if fixed:actions.append(('Periksa geometri yang diperbaiki',
        '%s geometri diproses untuk perbaikan. Bandingkan batas sebelum dan sesudah pada layer QA.'%count_text(fixed)))
    if invalid_count>fixed or empty_geom_count:actions.append(('Telaah geometri yang belum layak',
        '%s geometri awal invalid dan %s geometri kosong tercatat. Pastikan kasus yang belum teratasi ditangani sebelum pemaduan.'%
        (count_text(invalid_count),count_text(empty_geom_count))))
    if overlap_count:actions.append(('Telaah overlap internal',
        '%s record ditandai overlap. Bandingkan irisan terbesar dengan peta dan dokumen resmi.'%count_text(overlap_count)))
    if gap_count:actions.append(('Verifikasi kandidat gap',
        '%s poligon gap ditambahkan sebagai kandidat; belum menjadi bidang ber-NIB.'%count_text(gap_count)))
    if not actions:actions.append(('Lanjutkan ke pemaduan berbasis aturan',
        'Indikator spasial yang diperiksa tidak menandai kasus pada keluaran ini.'))
    kpis=[('Overlap',overlap_count,'record BPN + PBB'),('Geometri awal invalid',invalid_count,'record BPN + PBB'),
          ('Diperbaiki',fixed,'geometri'),('Gap baru',gap_count,'kandidat bidang')]
    r.intro(stats,notes,'Gap baru adalah kandidat area kosong tertutup; bukan NIB baru terverifikasi. Overlap internal ditandai, belum dikoreksi secara administratif.',headline,priority,kpis,actions)
    cats=['Geometri kosong','Geometri invalid','Geometri diperbaiki','Bidang overlap','Gap ditambahkan']
    get=lambda tag:[stats.get(tag+'_'+k,0) for k in ['geom_kosong','geom_invalid','geom_fixed','overlap','gap_baru']]
    if any(get('bpn')+get('pbb')):
        r.figpage(1,'Indikator kualitas spasial','Perbandingan jumlah kasus BPN dan PBB.')
        r.bar(cats,[('BPN',get('bpn')),('PBB',get('pbb'))])
    if any(not row['geom'].isNull() and not row['geom'].isEmpty() for row in b_rows):
        r.start('Kualitas spasial BPN')
        r.map([(b_rows,NO_PAIR,lambda x:not x['a'].get('overlap') and not x['a'].get('bid_tambah'),'Bidang lainnya'),
               (b_rows,OVERLAP,lambda x:bool(x['a'].get('overlap')),'Overlap'),
               (b_rows,GAP,lambda x:bool(x['a'].get('bid_tambah')),'Gap baru')], 'Distribusi bidang terindikasi bermasalah')
    if any(not row['geom'].isNull() and not row['geom'].isEmpty() for row in p_rows):
        r.start('Kualitas spasial PBB')
        r.map([(p_rows,NO_PAIR,lambda x:not x['a'].get('overlap'),'Bidang lainnya'),
               (p_rows,OVERLAP,lambda x:bool(x['a'].get('overlap')),'Overlap')],'Distribusi objek PBB yang overlap')
    if stats.get('pbb_geom_invalid',0) and p_rows:
        r.start('Perbaikan geometri PBB')
        r.map([(p_rows,NO_PAIR,lambda z:not bool(z['a'].get('geom_invalid')),'PBB lainnya'),
               (p_rows,INVALID,lambda z:bool(z['a'].get('geom_invalid')),'Invalid awal / fixed')],
              'Poligon PBB yang teridentifikasi invalid sebelum perbaikan')
    newg=[x for x in b_rows if x['a'].get('bid_tambah') and not x['geom'].isNull() and not x['geom'].isEmpty()]
    if newg:
        biggest=max(newg,key=lambda z:z['geom'].area())['geom'].boundingBox()
        margin=max(biggest.width(),biggest.height())*9
        from qgis.core import QgsRectangle
        focus=QgsRectangle(biggest.xMinimum()-margin,biggest.yMinimum()-margin,biggest.xMaximum()+margin,biggest.yMaximum()+margin)
        r.start('Lokasi kandidat gap BPN')
        r.map([(b_rows,NO_PAIR,lambda x:not bool(x['a'].get('bid_tambah')),'Bidang sekitar'),
               (b_rows,GAP,lambda x:bool(x['a'].get('bid_tambah')),'Kandidat gap')],
               'Perbesaran lokasi gap terpilih',focus=focus)
        r.text('Kandidat gap dengan luas terbesar: %.2f m². Posisi hanya indikatif; periksa detail topologi di QGIS.'%max(g['geom'].area() for g in newg),9)
    else:
        r.text('Tidak ada poligon gap baru yang lolos ambang; daftar gap kecil tersedia dalam CSV.',9)
    r.start('Rincian overlap dan gap')
    r.sub('Overlap internal terbesar BPN')
    r.table(['Record A','Record B','Luas irisan (m²)'],[
        (z.get('record_a'),z.get('record_b'),z.get('luas_irisan_m2'))
        for z in sorted(overlap_b,key=lambda v:-float(v.get('luas_irisan_m2') or 0))[:12]])
    r.sub('Overlap internal terbesar PBB')
    r.table(['Record A','Record B','Luas irisan (m²)'],[
        (z.get('record_a'),z.get('record_b'),z.get('luas_irisan_m2'))
        for z in sorted(overlap_p,key=lambda v:-float(v.get('luas_irisan_m2') or 0))[:12]])
    r.sub('Gap tertutup yang terdeteksi')
    r.table(['ID','Luas (m²)','Ditambah'],[(z.get('gap_id'),z.get('luas_m2'),z.get('ditambahkan'))
            for z in sorted(gaps,key=lambda v:-float(v.get('luas_m2') or 0))[:18]])
    r.footer_recommendations(actions[:4],
        ['rekap_csv.zip: daftar pasangan overlap dan seluruh gap tertutup.', 'Layer QA BPN/PBB dapat dibuka kembali di QGIS.'])
    return r.close()


def report3(folder,lev1,lev2b,lev2p,pairs,stats,notes,logs,bpn_all=None,pbb_all=None,gaps=None,crs=None,metadata=None,overlap_threshold=50,similarity_threshold=90):
    r=Report(folder,3,'Penentuan level pemaduan berbasis aturan',crs,metadata)
    headline=('%s pasangan Level 1; %s BPN dan %s PBB memerlukan verifikasi studio.'%
              (count_text(len(lev1)),count_text(len(lev2b)),count_text(len(lev2p))))
    priority=('verifikasi record Level 2 di studio.' if lev2b or lev2p else
              'tinjau pasangan Level 1 terhadap dokumen sumber.')
    whys=Counter(code.strip() for row in lev2b+lev2p for code in str(row['a'].get('kode_l2','')).split(';') if code.strip())
    actions=[]
    if lev2b or lev2p:
        top_reason=whys.most_common(1)
        reason=(' Alasan terbanyak: %s (%s record).'%(top_reason[0][0],count_text(top_reason[0][1]))
                if top_reason else '')
        actions.append(('Verifikasi Level 2 di studio',
            '%s BPN dan %s PBB belum memenuhi seluruh gerbang pemaduan.%s'%
            (count_text(len(lev2b)),count_text(len(lev2p)),reason)))
    conflicts_b=Counter(p.get('record_bpn') for p in pairs if p.get('record_bpn') is not None)
    conflicts_p=Counter(p.get('record_pbb') for p in pairs if p.get('record_pbb') is not None)
    conflict_count=sum(v>1 for v in conflicts_b.values())+sum(v>1 for v in conflicts_p.values())
    if conflict_count:actions.append(('Telaah calon pasangan ganda',
        '%s record memiliki lebih dari satu kandidat beririsan; periksa konflik 1:N atau N:1.'%count_text(conflict_count)))
    if lev1:actions.append(('Tinjau pasangan Level 1',
        '%s pasangan lolos aturan otomatis. Cocokkan dengan dokumen sumber sebelum keputusan administratif.'%count_text(len(lev1))))
    if not actions:actions.append(('Periksa input dan ambang',
        'Tidak ada pasangan Level 1 atau record Level 2 pada keluaran ini; pastikan layer dan parameter yang dipilih tepat.'))
    kpis=[('Level 1',len(lev1),'pasangan aturan'),('BPN Level 2',len(lev2b),'perlu studio'),
          ('PBB Level 2',len(lev2p),'perlu studio'),('Kandidat',len(pairs),'beririsan')]
    r.intro(stats,notes,'Level 2 bukan pasangan salah: data dipisah untuk verifikasi studio. Operator harus menggunakan layer terbaru hasil perbaikan.',headline,priority,kpis,actions)
    if lev1 or lev2b or lev2p:
        r.figpage(1,'Distribusi level pemaduan','Jumlah pasangan Level 1 dan record yang memerlukan verifikasi studio.')
        r.bar(['Level 1','BPN Level 2','PBB Level 2'],[('Record',[len(lev1),len(lev2b),len(lev2p)])])
    common=whys.most_common(16)
    if common:
        reasons={'TIDAK_ADA_IRISAN':'Tidak ada bidang beririsan',
                 'OVERLAP_KURANG':'Irisan di bawah ambang',
                 'MULTI_NOP':'Satu BPN memiliki beberapa calon PBB',
                 'MULTI_NIB':'Satu PBB memiliki beberapa calon BPN',
                 'NIB_KOSONG':'NIB kosong','NOP_KOSONG':'NOP kosong',
                 'NIB_DUPLIKAT':'NIB duplikat','NOP_DUPLIKAT':'NOP duplikat',
                 'LUAS_BPN_TIDAK_SESUAI':'Luas BPN tidak sesuai',
                 'LUAS_PBB_TIDAK_SESUAI':'Luas PBB tidak sesuai',
                 'LUAS_TERTULIS_TIDAK_SAMA':'Luas tertulis tidak sepadan',
                 'TANPA_NOP':'Tanpa calon NOP','TANPA_NIB':'Tanpa calon NIB'}
        r.figpage(2,'Alasan Level 2','Satu record dapat memiliki beberapa alasan.')
        r.bar([reasons.get(k,k.replace('_',' ').capitalize()) for k,_ in common],
              [('Frekuensi',[v for _,v in common])],horizontal=True)
    if pairs:
        threshold=max(0,min(100,float(overlap_threshold)))
        vals=[sum(1 for row in pairs if (finite(row.get('overlap_bpn_pct')) or 0)<=threshold),
              sum(1 for row in pairs if (finite(row.get('overlap_bpn_pct')) or 0)>threshold)]
        r.figpage(3,'Seleksi berdasarkan irisan BPN','Ambang aktual %.1f%%; ambang kesamaan luas tertulis %.1f%%.'%(threshold,similarity_threshold))
        r.bar(['≤ %.1f%%'%threshold,'> %.1f%%'%threshold],[('Kandidat',vals)])
        r.figpage(4,'Overlap dan kesamaan luas tertulis',
                  'Hubungan irisan BPN dengan kesamaan luas tertulis; ambang aktual dijelaskan di atas.')
        r.xy_scatter([(p.get('overlap_bpn_pct'),p.get('kesamaan_luas_tulis',p.get('kesamaan_pct')))
                      for p in pairs], 'Overlap BPN (%)','Kesamaan luas (%)',
                     x_threshold=overlap_threshold,y_threshold=similarity_threshold)
    b_rows=bpn_all if bpn_all is not None else lev1+lev2b
    p_rows=pbb_all if pbb_all is not None else lev2p
    level1_pbb_ids={pair['record_pbb'] for pair in pairs if pair.get('status')=='LEVEL_1'}
    lev1p=[row for row in p_rows if row['idx'] in level1_pbb_ids]
    no_pair_pbb=[row for row in lev2p if 'TIDAK_ADA_IRISAN' in str(row['a'].get('kode_l2',''))]
    no_pair_ids={row['idx'] for row in no_pair_pbb}
    studio_pbb=[row for row in lev2p if row['idx'] not in no_pair_ids]
    if lev2b or lev1:
        r.start('Level pemaduan BPN')
        r.map([(lev2b,LEVEL_2,None,'BPN Level 2'),(lev1,LEVEL_1,None,'BPN Level 1')],
               'Distribusi pasangan otomatis dan bidang studio')
    if no_pair_pbb or studio_pbb or lev1p:
        r.start('Level pemaduan PBB')
        r.map([(no_pair_pbb,NO_PAIR,None,'PBB tanpa pasangan'),
               (studio_pbb,LEVEL_2,None,'PBB Level 2'),
               (lev1p,LEVEL_1,None,'PBB Level 1')],
               'Distribusi pasangan otomatis dan objek PBB untuk verifikasi studio')
    if pairs:
        r.start('Rekap pasangan dan kandidat')
        r.sub('Pasangan dengan overlap BPN terbesar')
        r.table(['NIB','NOP','Overlap BPN %','Overlap PBB %'],
                [(v.get('NIB',''),v.get('NOP',''),nice(v.get('overlap_bpn_pct')),nice(v.get('overlap_pbb_pct')))
                 for v in sorted(pairs,key=lambda x:-(finite(x.get('overlap_bpn_pct')) or 0))[:20]])
    r.footer_recommendations(actions,
        ['rekap_csv.zip: seluruh pasangan kandidat, overlap internal, gap, dan alasan Level 2.'])
    return r.close()


def report5(folder,lev1,lev2b,lev2p,pairs,scores,extras,stats,notes,model_meta,logs,crs=None,metadata=None):
    r=Report(folder,5,'Inference AI dan penentuan Level 1/2',crs,metadata)
    headline=('%s pasangan Level 1; %s di antaranya tambahan AI.'%
              (count_text(len(lev1)),count_text(len(extras))))
    priority=('gunakan skor AI hanya untuk urutan telaah studio.' if
              str((model_meta or {}).get('status',stats.get('Status AI',''))) in ('PREVIEW_ONLY','NO_MODEL')
              else 'audit keunikan NIB–NOP dan bukti setiap tambahan AI.' if extras
              else 'telaah Level 2 dan kesiapan model sebelum penggunaan lanjut.')
    actions=[]
    status=str((model_meta or {}).get('status',stats.get('Status AI','')))
    if status in ('PREVIEW_ONLY','NO_MODEL'):
        actions.append(('Gunakan AI sebagai daftar telaah',
            'Status model belum memberi dasar untuk menambah Level 1 otomatis. Periksa kandidat di studio.'))
    if extras:actions.append(('Audit tambahan Level 1 dari AI',
        '%s pasangan tambahan perlu diperiksa terhadap keunikan NIB–NOP dan bukti administrasi.'%count_text(len(extras))))
    if lev2b or lev2p:actions.append(('Verifikasi Level 2 di studio',
        '%s BPN dan %s PBB masih memerlukan keputusan operator.'%
        (count_text(len(lev2b)),count_text(len(lev2p)))))
    if scores:actions.append(('Tinjau kandidat AI yang tersisa',
        '%s kandidat mempunyai skor; skor bukan bukti kecocokan dan tidak menggantikan pemeriksaan pasangan pesaing.'%count_text(len(scores))))
    if not actions:actions.append(('Periksa kesiapan model dan input',
        'Tidak ada kandidat AI atau Level 2 yang dapat ditindaklanjuti pada keluaran ini.'))
    kpis=[('Level 1',len(lev1),'total pasangan'),('Tambahan AI',len(extras),'pasangan'),
          ('BPN Level 2',len(lev2b),'perlu studio'),('PBB Level 2',len(lev2p),'perlu studio')]
    r.intro(stats,notes,'Status model dan sumber label GOLD/SILVER menentukan apakah AI boleh menambah Level 1. Skor tinggi saja tidak membuktikan kecocokan administratif.',headline,priority,kpis,actions[:3])
    r.figpage(1,'Hasil klasifikasi','Perbandingan Level 1 baseline, tambahan AI, dan Level 2.')
    r.bar(['Level 1 aturan','Level 1 baru AI','BPN Level 2','PBB Level 2'],
          [('Jumlah',[max(0,len(lev1)-len(extras)),len(extras),len(lev2b),len(lev2p)])])
    r.figpage(2,'Distribusi skor AI','Histogram skor seluruh kandidat yang diprediksi model. Skor hanya probabilitas apabila model sudah dikalibrasi.')
    ss=[finite(p.get('skor_ai')) for p in scores]
    ss=[x for x in ss if x is not None and 0<=x<=1]
    if ss:
        bins=[sum(1 for x in ss if x>=i/10 and (x<(i+1)/10 if i<9 else x<=1)) for i in range(10)]
        r.bar(['%02d-%02d'% (i*10,(i+1)*10) for i in range(10)],[('Kandidat',bins)])
    else:r.no_data('Model belum dipilih atau skor AI tidak tersedia.')
    r.start('Hasil pemaduan BPN')
    r.map([(lev2b,LEVEL_2,None,'BPN Level 2'),(lev1,LEVEL_1,None,'BPN Level 1')],
          'Hasil pemaduan menurut bidang BPN')
    r.start('Hasil pemaduan PBB')
    r.map([(lev2p,LEVEL_2,None,'PBB Level 2')],
          'Objek PBB yang memerlukan verifikasi')
    r.start('Kandidat AI untuk ditinjau')
    r.sub('Kandidat dengan skor AI terbesar')
    r.table(['NIB','NOP','Skor','Keputusan','Gerbang yang perlu ditelaah'],
            [(x.get('NIB'),x.get('NOP'),nice(x.get('skor_ai')),
              'Level 1 AI' if x.get('keputusan_ai')=='DITERIMA_LEVEL1' else 'Studio',
              (x.get('alasan_tidak_promosi') or 'Semua lolos') if 'alasan_tidak_promosi' in x
              else 'Gerbang tidak tercatat pada arsip lama')
             for x in sorted(scores,key=lambda t:-(finite(t.get('skor_ai')) or 0))[:25]],
            [r.cw*.23,r.cw*.23,r.cw*.08,r.cw*.13,r.cw*.33])
    r.sub('Status pengujian model')
    for k,v in (model_meta or {}).items():
        if k in ('algorithm','status','precision','model_version','test_data_source'):
            r.text('%s: %s'%(metric_label(k),human_status(v) if k=='status' else v),9)
    r.footer_recommendations(actions[:3],
        ['rekap_csv.zip: skor seluruh kandidat, pasangan berbasis aturan, tambahan AI.'])
    return r.close()


def report6(folder,decisions,candidates,bpn_rows=None,pbb_rows=None,notes=None,crs=None,metadata=None):
    r=Report(folder,6,'Verifikasi studio interaktif',crs,metadata)
    yes=sum(d.get('label')=='1' for d in decisions)
    no=sum(d.get('label')=='0' for d in decisions)
    unknown=sum(d.get('label') not in ('1','0') for d in decisions)
    headline=('%s keputusan tercatat: %s cocok, %s tidak cocok, %s belum pasti.'%
              (count_text(len(decisions)),count_text(yes),count_text(no),count_text(unknown)))
    actions=[]
    missing_evidence=sum(1 for d in decisions if d.get('label') in ('1','0') and
                         (empty(d.get('sumber_verifikasi')) or empty(d.get('operator'))))
    if missing_evidence:actions.append(('Lengkapi jejak keputusan',
        '%s label 1/0 belum mencatat sumber bukti atau operator; lengkapi sebelum dipakai sebagai GOLD.'%count_text(missing_evidence)))
    if unknown:actions.append(('Putuskan kasus belum pasti',
        '%s pasangan belum memiliki label 1/0. Periksa peta dan dokumen; jangan masukkan sebagai label negatif.'%count_text(unknown)))
    if yes or no:actions.append(('Siapkan label terverifikasi untuk Modul 4',
        '%s label 1 dan %s label 0 tercatat. Gunakan hanya keputusan dengan bukti yang dapat ditelusuri.'%
        (count_text(yes),count_text(no))))
    if not actions:actions.append(('Mulai verifikasi kandidat',
        '%s kandidat tersedia dan belum ada keputusan tercatat.'%count_text(len(candidates))))
    kpis=[('Kandidat',len(candidates),'tersedia'),('Cocok',yes,'label 1'),
          ('Tidak cocok',no,'label 0'),('Belum pasti',unknown,'tanpa label 1/0')]
    r.intro({'Kandidat tersedia':len(candidates),'Keputusan tercatat':len(decisions),
             'Cocok (label 1)':yes,'Tidak cocok (label 0)':no,'Belum pasti':unknown},
            notes or ['Verifikasi menggunakan peta BPN/PBB dan bukti administratif.',
                       'Label 1 dan 0 mensyaratkan identitas operator dan sumber bukti.'],
            'Hasil Level 2 atau belum pasti bukan label negatif (0).',headline,
            'selesaikan kasus belum pasti dengan bukti.' if unknown else
            'lengkapi jejak bukti dan operator pada label 1/0.' if decisions else
            'mulai verifikasi kandidat yang tersedia.',kpis,actions)
    if decisions:
        r.figpage(1,'Status keputusan studio','Ringkasan keputusan operator yang tersimpan sebagai label GOLD atau belum pasti.')
        r.bar(['Cocok (1)','Tidak cocok (0)','Belum pasti'],[('Pasangan',[yes,no,unknown])])
    if decisions and bpn_rows is not None and pbb_rows is not None:
        r.start('Pasangan yang diverifikasi')
        def safe_indices(field):
            vals=set()
            for row in decisions:
                try:vals.add(int(row.get(field)))
                except (TypeError,ValueError,OverflowError):pass
            return vals
        bidx=safe_indices('record_bpn')
        pidx=safe_indices('record_pbb')
        r.map([(bpn_rows,BPN,lambda row:row['idx'] in bidx,'BPN diverifikasi'),
               (pbb_rows,PBB,lambda row:row['idx'] in pidx,'PBB diverifikasi')],
               'Bidang BPN dan PBB yang sudah memperoleh keputusan')
    if decisions:
        r.start('Keputusan operator')
        r.table(['NIB','NOP','Label','Operator','Waktu','Sumber bukti'],
                [(row.get('NIB'),row.get('NOP'),
                  'Cocok' if row.get('label')=='1' else 'Tidak cocok' if row.get('label')=='0' else 'Belum pasti',
                  row.get('operator'),row.get('waktu'),row.get('sumber_verifikasi'))
                 for row in decisions],
                [r.cw*.23,r.cw*.23,r.cw*.10,r.cw*.11,r.cw*.15,r.cw*.18])
    r.footer_recommendations(actions,
        ['CSV keputusan berisi operator, waktu, bukti, dan label.', 'rekap_verifikasi.zip mencakup seluruh keputusan operator.'])
    return r.close()
