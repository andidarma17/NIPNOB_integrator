"""Complete, single-file PDF reports for QGIS NIB-NOP Integrator modules 1, 2, 3, 5, 6.

Uses ONLY QGIS-bundled Qt (QPdfWriter/QPainter) and QGIS record geometries.
All figures are computed from the actual in-memory result of this execution.
Training/testing Module 4 keeps its richer specialised `ai_pdf.py` implementation.
Qt 5 and Qt 6 compatible via `qgis.PyQt`.
"""
from collections import Counter
from datetime import datetime
from pathlib import Path
from .compat import set_pdf_a4
import math
import textwrap

from qgis.PyQt.QtCore import QPointF, Qt
from qgis.PyQt.QtGui import (QPdfWriter, QPageSize, QPainter, QPen, QColor,
                              QBrush, QFont, QFontMetrics, QPolygonF)
from .logic import number, ident, empty
from .report_theme import (NAVY, INK, MUTED, GRID, TINT, BPN, PBB, LEVEL_1,
                           LEVEL_2, LEVEL_2_TEXT, NO_PAIR, NEUTRAL_EDGE,
                           OVERLAP, GAP, INVALID, GOOD_TEXT, BAD_TEXT,
                           ATTENTION_TEXT, CAUTION_TEXT, assessment_style,
                           category_style, fill_for, map_style, series_style)

try:
    ELIDE_RIGHT=Qt.TextElideMode.ElideRight
except AttributeError:
    ELIDE_RIGHT=Qt.ElideRight


def finite(value):
    x=number(value)
    return x if x is not None and math.isfinite(x) else None


def nice(value):
    if isinstance(value, float):
        return ('%.2f' % value).rstrip('0').rstrip('.')
    return str(value)


class Report:
    def __init__(self, folder, modnum, title):
        self.path=Path(folder)/('laporan_modul%d.pdf'%modnum)
        self.pdf=QPdfWriter(str(self.path));set_pdf_a4(self.pdf);self.pdf.setResolution(120)
        self.p=QPainter(self.pdf)
        if not self.p.isActive():
            raise RuntimeError('Tidak dapat membuat PDF: '+str(self.path))
        self.w=self.pdf.width();self.h=self.pdf.height();self.l=62;self.r=62
        self.cw=self.w-self.l-self.r;self.bottom=self.h-108
        self.title=title;self.num=modnum;self.page=0;self.y=0
        self.start('IKHTISAR DAN HASIL UTAMA')
    def font(self,size=10,bold=False):
        f=QFont('DejaVu Sans',size);f.setBold(bold);self.p.setFont(f)
    def wrapped(self,s,width):
        metrics=QFontMetrics(self.p.font())
        lines=[]
        for paragraph in str(s).split('\n'):
            line=''
            for word in paragraph.split():
                candidate=(line+' '+word).strip()
                if line and metrics.horizontalAdvance(candidate)>width:
                    lines.append(line);line=word
                else:line=candidate
            lines.append(line)
        return lines or ['']
    def start(self, heading, subtitle=''):
        if self.page:self.pdf.newPage()
        self.page+=1;self.y=70;self.heading=heading
        self.p.fillRect(0,0,self.w,14,NAVY)
        self.p.fillRect(0,14,self.w,61,TINT)
        self.font(10,True);self.p.setPen(QPen(NAVY))
        self.p.drawText(self.l,49,'NIB-NOP INTEGRATOR  |  MODUL %d'%self.num)
        self.font(9);self.p.setPen(QPen(MUTED))
        self.p.drawText(self.l,self.h-42,'Laporan otomatis | %s'%datetime.now().strftime('%d-%m-%Y %H:%M'))
        self.p.drawText(self.w-130,self.h-42,'Halaman %d'%self.page)
        self.y=126
        self.font(17,True);self.p.setPen(QPen(NAVY))
        for line in self.wrapped(heading,self.cw):
            self.p.drawText(self.l,self.y,line);self.y+=28
        self.y+=7
        if subtitle:self.text(subtitle,9,color=MUTED,space=20)
        self.p.setPen(QPen(GRID));self.p.drawLine(self.l,self.y,self.w-self.r,self.y);self.y+=25
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
        color,background,symbol=assessment_style(kind)
        self.font(10)
        lines=self.wrapped(message,self.cw-59)
        height=22*len(lines)+24
        if self.y+height>self.bottom:self.start('LANJUTAN - '+self.title[:35])
        top=self.y-15
        self.p.fillRect(self.l,top,self.cw,height,background)
        self.p.setPen(QPen(color));self.font(11,True)
        self.p.drawText(self.l+14,self.y+4,symbol)
        self.font(10);self.p.setPen(QPen(color))
        for line in lines:
            self.p.drawText(self.l+43,self.y+4,line)
            self.y+=22
        self.y+=height-22*len(lines)+10
    def table(self,head,rows,widths=None,limit=26):
        widths=widths or [self.cw/len(head)]*len(head)
        heights=31
        def draw_header():
            self.p.fillRect(self.l,self.y-18,self.cw,heights,NAVY)
            self.font(9,True);self.p.setPen(QPen(QColor('white')))
            x=self.l
            for col,w in zip(head,widths):
                label=QFontMetrics(self.p.font()).elidedText(str(col),ELIDE_RIGHT,int(w-16))
                self.p.drawText(int(x+8),int(self.y),label);x+=w
            self.y+=heights
        draw_header()
        for i,row in enumerate(rows[:limit]):
            if self.y>self.bottom-34:self.start('LANJUTAN TABEL');draw_header()
            if i%2==0:self.p.fillRect(self.l,self.y-19,self.cw,heights,TINT)
            self.font(9);self.p.setPen(QPen(INK));x=self.l
            for j,(val,w) in enumerate(zip(row,widths)):
                st=nice(val).replace('\n',' ')
                metrics=QFontMetrics(self.p.font())
                if metrics.horizontalAdvance(st)>w-16:
                    if str(head[j]).upper() in ('NIB','NOP'):
                        self.font(8);metrics=QFontMetrics(self.p.font())
                    else:st=metrics.elidedText(st,ELIDE_RIGHT,int(w-16))
                numeric=isinstance(val,(int,float)) and str(head[j]).upper() not in ('NIB','NOP')
                tx=x+w-8-metrics.horizontalAdvance(st) if numeric else x+8
                self.p.drawText(int(tx),int(self.y),st)
                self.font(9);x+=w
            self.y+=heights
        if len(rows)>limit:self.text('Tabel ditampilkan %d dari %d baris; data lengkap tersedia pada rekap_csv.zip.'%(limit,len(rows)),8,color=MUTED)
        self.y+=16
    def intro(self,stats,notes,warning=None):
        self.text(self.title,13,True,NAVY)
        self.sub('Ringkasan indikator utama')
        rows=[(k,nice(v)) for k,v in stats.items()]
        self.table(['Indikator','Hasil'],rows,[self.cw*.64,self.cw*.36],limit=22)
        if 'Status AI' in stats:
            status=str(stats['Status AI'])
            kind='unknown' if status in ('PREVIEW_ONLY','NO_MODEL') else 'attention'
            self.notice('Status AI: '+status+'. Periksa hasil evaluasi GOLD dan aturan promosi sebelum menerima pasangan AI.',kind)
        self.sub('Metode dan parameter')
        for msg in notes:self.text('- '+msg,9,max_chars=110,space=21)
        if warning:self.sub('Batasan interpretasi');self.notice(warning,'attention')
    def footer_recommendations(self,items,appendix=None):
        self.start('KESIMPULAN DAN TINDAK LANJUT')
        for i,s in enumerate(items,1):
            self.sub('%d. %s'%(i,s[0]))
            self.text(s[1],10,max_chars=103)
        if appendix:
            self.sub('Arsip hasil')
            for s in appendix:self.text('- '+str(s),9)
        self.sub('Catatan umum')
        self.notice('Penanda otomatis merupakan indikasi pemeriksaan, bukan bukti hukum atas status bidang atau kewajiban pajak. Konfirmasi menggunakan sumber administrasi resmi.','caution')
    def figpage(self,number,title,description):
        self.start('GRAFIK %d - %s'%(number,title),description)
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
        ytop=self.y+32;bottom=min(self.bottom-150,ytop+780)
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
                self.font(8);self.p.setPen(QPen(INK))
                self.p.drawText(int(x-4),int(bottom-barheight-9),nice(round(v,2))+value_suffix)
            self.font(8);self.p.setPen(QPen(MUTED))
            wrapped=textwrap.wrap(str(label),max(7,int(group/9)),break_long_words=True)
            marker_x=cx-group*.46
            has_marker=self.category_marker(marker_x,bottom+26,label)
            self.p.setPen(QPen(MUTED));self.font(8)
            for k,z in enumerate(wrapped[:3]):self.p.drawText(int(marker_x+(18 if has_marker else 0)),int(bottom+26+k*17),z)
        if len(series)>1:
            for j,(label,_) in enumerate(series):
                xx=xleft+j*175;color,role=series_style(label)
                self.p.fillRect(int(xx),int(bottom+105),12,12,fill_for(color,role))
                self.p.setPen(QPen(INK));self.font(9);self.p.drawText(int(xx+19),int(bottom+115),str(label)[:23])
        self.y=bottom+145
    def _axes(self,xleft,top,right,bottom,ymax):
        self.p.setPen(QPen(GRID,1))
        for k in range(5):
            val=ymax*k/4;yy=bottom-(bottom-top)*k/4
            self.p.drawLine(int(xleft),int(yy),int(right),int(yy))
            self.font(8);self.p.setPen(QPen(MUTED));self.p.drawText(int(self.l),int(yy+4),'%d'%round(val))
            self.p.setPen(QPen(GRID))
    def _bar_horizontal(self,labels,series,suffix):
        label_col=245;x0=self.l+label_col;xright=self.w-self.r-65
        vals=[max(0,float(finite(v) or 0)) for _,x in series for v in x]
        vmax=max(vals+[1]);row_h=min(48,max(29,int(780/max(1,len(labels)))))
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
                self.p.setPen(QPen(MUTED));self.font(8)
                self.p.drawText(int(x0+max(0,ww)+7),int(yy+bh-2),nice(v)+suffix)
            self.y+=row_h
        self.y+=18
        if len(series)>1:
            for i,(name,_) in enumerate(series):
                color,role=series_style(name)
                self.p.fillRect(self.l+i*230,self.y-12,12,12,fill_for(color,role));self.font(9);self.p.setPen(QPen(INK))
                self.p.drawText(self.l+i*230+19,self.y,str(name))
        self.y+=20
    def histogram(self,values,unit='m2',max_percentile=99):
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
        top=self.y+35;bottom=min(self.bottom-120,top+775)
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
    def scatter(self,values):
        vals=[(i+1,finite(v)) for i,v in enumerate(values)]
        vals=[(x,y) for x,y in vals if y is not None and y>0]
        if not vals:self.no_data('Tidak ada nilai luas positif.');return
        top=self.y+40;bottom=min(self.bottom-115,top+770)
        left=self.l+80;right=self.w-self.r-30
        lo=min(math.log10(y) for _,y in vals);hi=max(math.log10(y) for _,y in vals)
        if hi==lo:hi+=1
        maxx=max(x for x,_ in vals)
        self.p.setPen(QPen(GRID));self.p.drawRect(int(left),int(top),int(right-left),int(bottom-top))
        for k in range(5):
            zz=lo+(hi-lo)*k/4;yy=bottom-(bottom-top)*k/4
            self.p.drawLine(int(left),int(yy),int(right),int(yy))
            self.font(8);self.p.setPen(QPen(MUTED));self.p.drawText(int(self.l),int(yy+4),'%.1f'%zz)
            self.p.setPen(QPen(GRID))
        color=PBB if 'PBB' in self.heading else BPN
        self.p.setPen(QPen(color,1.4));self.p.setBrush(QBrush(color))
        for x,y in vals:
            px=left+(x/maxx)*(right-left);py=bottom-(math.log10(y)-lo)/(hi-lo)*(bottom-top)
            self.p.drawEllipse(QPointF(float(px),float(py)),1.9,1.9)
        self.p.setBrush(QBrush())
        self.y=bottom+26
        self.text('Sumbu X: urutan record. Sumbu Y: log10(luas m2). Setiap titik mewakili satu record dengan luas positif.',9,color=MUTED)
    def xy_scatter(self,xy_pairs,xlabel,ylabel,xmax=100,ymax=100):
        good=[(finite(x),finite(y)) for x,y in xy_pairs]
        good=[(x,y) for x,y in good if x is not None and y is not None]
        if not good:self.no_data('Data numerik berpasangan tidak tersedia.');return
        top=self.y+20;bottom=min(self.bottom-125,top+600)
        left=self.l+78;right=self.w-self.r-25
        self.p.setPen(QPen(GRID));self.p.drawRect(int(left),int(top),int(right-left),int(bottom-top))
        for i in range(5):
            x=left+(right-left)*i/4; y=bottom-(bottom-top)*i/4
            self.p.drawLine(int(left),int(y),int(right),int(y))
            self.font(8);self.p.setPen(QPen(MUTED))
            self.p.drawText(int(x-10),int(bottom+23),'%.0f'%(xmax*i/4))
            self.p.drawText(self.l,int(y+4),'%.0f'%(ymax*i/4))
            self.p.setPen(QPen(GRID))
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
        for j,(_rows,col,_pred,label) in enumerate(datasets):
            lx=self.l+(j%3)*self.cw/3
            if j and j%3==0:self.y+=28
            colour,role,edge=map_style(label,col)
            self.p.setPen(QPen(edge,1.2));self.p.setBrush(fill_for(colour,role))
            if role=='level2':
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
                points=poly[0]
                # Drawing outer ring: holes not coloured separately; QA map is schematic.
                step=max(1,len(points)//800)
                qpoly=QPolygonF([xy(point) for point in points[::step]])
                if len(qpoly)>=3:self.p.drawPolygon(qpoly)
        self.p.setBrush(QBrush())
        self.p.restore()
        self.y=bottom+29
        self.text('Peta indikatif tanpa peta dasar. Koordinat mengikuti CRS layer; pola dan warna menunjukkan kategori. Angka legenda menghitung fitur yang digambar (maksimal %d per kategori). Periksa lokasi detail pada layer QGIS.'%max_features,9,color=MUTED)
    def close(self):
        self.p.end();return str(self.path)


def report1(folder, b_info,p_info, stats, tables, min_area,max_area):
    """b_info/p_info=(records, identity_field, area_field) after qa_attribute."""
    rep=Report(folder,1,'Pemeriksaan kelengkapan atribut')
    rep.intro(stats,[f'Ambang awal luas: {min_area:g} - {max_area:g} m2.',
             'Identitas duplikat dihitung dengan mengabaikan nilai kosong.',
             'Kolom luas dapat bertipe teks selama nilainya dapat dikonversi menjadi angka.'],
             'Nilai luas di luar ambang perlu verifikasi; bukan otomatis salah.')
    b,bi,ba=b_info;p,pi,pa=p_info
    bs=lambda key:stats.get('BPN '+key,0)
    ps=lambda key:stats.get('PBB '+key,0)
    cats=['Jumlah record','ID kosong','Record duplikat','Luas bermasalah']
    vals=[('BPN',[bs('jumlah_record'),bs('identitas_kosong'),bs('record_duplikat'),bs('record_luas_bermasalah')]),
          ('PBB',[ps('jumlah_record'),ps('identitas_kosong'),ps('record_duplikat'),ps('record_luas_bermasalah')])]
    rep.figpage(1,'Ringkasan temuan','Jumlah record dan indikator kualitas pada kedua dataset.')
    rep.bar(cats,vals)
    rep.text('Gunakan jumlah record sebagai pembagi saat membandingkan mutu relatif BPN dan PBB.',9)
    names=[];missing=[];pct=[]
    for tag,rows in [('BPN',b),('PBB',p)]:
        fields=sorted({k for r in rows for k in r['a'] if k not in ('id_kosong','id_duplikat','luas_flag') and not k.startswith('_')})
        for f in fields:
            count=sum(1 for r in rows if empty(r['a'].get(f)))
            names.append(tag+' - '+f);missing.append(count);pct.append(100*count/max(1,len(rows)))
    rep.figpage(2,'Jumlah kosong per kolom','Nilai kosong dihitung pada setiap kolom sumber; angka nol bukan kosong.')
    rep.bar(names,[('Kosong',missing)],horizontal=True)
    rep.figpage(3,'Persentase kosong per kolom','Jumlah kosong dibagi jumlah record pada masing-masing dataset.')
    rep.bar(names,[('Persentase (%)',pct)],horizontal=True)
    for seq,rows,field,name in [(4,b,ba,'BPN'),(5,p,pa,'PBB')]:
        rep.figpage(seq,'Histogram luas '+name,'Distribusi luas tertulis; persentil ke-99 digunakan sebagai batas visual agar ekor ekstrem terbaca.')
        rep.histogram([r['a'].get(field) for r in rows])
    for seq,rows,field,name in [(6,b,ba,'BPN'),(7,p,pa,'PBB')]:
        rep.figpage(seq,'Scatter luas '+name,'Deteksi luas ekstrem menurut nomor urut record; skala Y logaritmik.')
        rep.scatter([r['a'].get(field) for r in rows])
    keys=['LUAS_KOSONG_ATAU_NONNUMERIK','LUAS_NOL_NEGATIF','LUAS_KECIL','LUAS_BESAR']
    counts=[]
    for rows in [b,p]:counts.append([sum(key in r['a'].get('luas_flag','').split(';') for r in rows) for key in keys])
    rep.figpage(8,'Kategori masalah luas','Kekosongan/non-numerik dipisah dari nol, negatif, nilai kecil, dan nilai besar.')
    rep.bar(['Kosong / tidak numerik','Nol / negatif','Di bawah ambang','Di atas ambang'],
            [('BPN',counts[0]),('PBB',counts[1])])
    rep.footer_recommendations([
        ('Periksa NIB/NOP kosong atau duplikat','Pulihkan identitas dari basis administrasi resmi sebelum pemaduan otomatis.'),
        ('Lengkapi luas tertulis','Utamakan kolom luas kosong/non-numerik, bukan menggantinya dengan luas geometri tanpa bukti.'),
        ('Tinjau luas ekstrem','Kaji bidang di luar ambang melalui layer dan dokumen pendukung, bukan menghapus otomatis.')],
        ['rekap_csv.zip: rincian kolom kosong, identitas duplikat, dan luas bermasalah.', 'Layer audit atribut disimpan dalam format spasial yang dipilih.'])
    return rep.close()


def report2(folder,b_rows,p_rows,stats,notes,overlap_b,overlap_p,gaps):
    r=Report(folder,2,'Pemeriksaan dan perbaikan kualitas spasial')
    r.intro(stats,notes,'Gap baru adalah kandidat area kosong tertutup; bukan NIB baru terverifikasi. Overlap internal ditandai, belum dikoreksi secara administratif.')
    cats=['Geometri kosong','Geometri invalid','Geometri diperbaiki','Bidang overlap','Gap ditambahkan']
    get=lambda tag:[stats.get(tag+'_'+k,0) for k in ['geom_kosong','geom_invalid','geom_fixed','overlap','gap_baru']]
    r.figpage(1,'Indikator kualitas spasial','Perbandingan jumlah kasus BPN dan PBB.')
    r.bar(cats,[('BPN',get('bpn')),('PBB',get('pbb'))])
    r.start('PETA 1 - KUALITAS BPN')
    r.map([(b_rows,NO_PAIR,lambda x:not x['a'].get('overlap') and not x['a'].get('bid_tambah'),'Bidang lainnya'),
           (b_rows,OVERLAP,lambda x:bool(x['a'].get('overlap')),'Overlap'),
           (b_rows,GAP,lambda x:bool(x['a'].get('bid_tambah')),'Gap baru')], 'Distribusi bidang terindikasi bermasalah')
    r.start('PETA 2 - KUALITAS PBB')
    r.map([(p_rows,NO_PAIR,lambda x:not x['a'].get('overlap'),'Bidang lainnya'),
           (p_rows,OVERLAP,lambda x:bool(x['a'].get('overlap')),'Overlap')],'Distribusi objek PBB yang overlap')
    r.start('PETA 3 - PERBAIKAN GEOMETRI')
    r.map([(p_rows,NO_PAIR,lambda z:not bool(z['a'].get('geom_invalid')),'PBB lainnya'),
           (p_rows,INVALID,lambda z:bool(z['a'].get('geom_invalid')),'Invalid awal / fixed')],
          'Poligon PBB yang teridentifikasi invalid sebelum perbaikan')
    newg=[x for x in b_rows if x['a'].get('bid_tambah') and not x['geom'].isNull() and not x['geom'].isEmpty()]
    if newg:
        biggest=max(newg,key=lambda z:z['geom'].area())['geom'].boundingBox()
        margin=max(biggest.width(),biggest.height())*9
        from qgis.core import QgsRectangle
        focus=QgsRectangle(biggest.xMinimum()-margin,biggest.yMinimum()-margin,biggest.xMaximum()+margin,biggest.yMaximum()+margin)
        r.start('PETA 4 - DETAIL GAP BPN')
        r.map([(b_rows,NO_PAIR,lambda x:not bool(x['a'].get('bid_tambah')),'Bidang sekitar'),
               (b_rows,GAP,lambda x:bool(x['a'].get('bid_tambah')),'Kandidat gap')],
               'Perbesaran lokasi gap terpilih',focus=focus)
        r.text('Kandidat gap dengan luas terbesar: %.2f m2. Posisi hanya indikatif; periksa detail topologi di QGIS.'%max(g['geom'].area() for g in newg),9)
    else:
        r.start('PETA 4 - DETAIL GAP BPN')
        r.no_data('Tidak ada poligon gap baru yang lolos ambang. Jumlah gap kecil tetap tersedia dalam CSV.')
    r.start('RINCIAN OVERLAP DAN GAP')
    r.sub('Overlap internal terbesar BPN')
    r.table(['Record A','Record B','Luas irisan m2'],[
        (z.get('record_a'),z.get('record_b'),z.get('luas_irisan_m2'))
        for z in sorted(overlap_b,key=lambda v:-float(v.get('luas_irisan_m2') or 0))[:12]])
    r.sub('Overlap internal terbesar PBB')
    r.table(['Record A','Record B','Luas irisan m2'],[
        (z.get('record_a'),z.get('record_b'),z.get('luas_irisan_m2'))
        for z in sorted(overlap_p,key=lambda v:-float(v.get('luas_irisan_m2') or 0))[:12]])
    r.sub('Gap tertutup yang terdeteksi')
    r.table(['ID','Luas m2','Ditambah'],[(z.get('gap_id'),z.get('luas_m2'),z.get('ditambahkan'))
            for z in sorted(gaps,key=lambda v:-float(v.get('luas_m2') or 0))[:18]])
    r.footer_recommendations([
        ('Validasi hasil perbaikan geometri','Periksa bentuk poligon yang mengalami perbaikan, termasuk potensi perubahan batas.'),
        ('Telaah konflik overlap','Bandingkan bidang yang saling menutup dengan peta/dokumen resmi.'),
        ('Verifikasi area gap tertutup','Bidang hasil delineasi hanya kandidat; tidak otomatis mendapat NIB.')],
        ['rekap_csv.zip: daftar pasangan overlap dan seluruh gap tertutup.', 'Layer QA BPN/PBB dapat dibuka kembali di QGIS.'])
    return r.close()


def report3(folder,lev1,lev2b,lev2p,pairs,stats,notes,logs,bpn_all=None,pbb_all=None,gaps=None):
    r=Report(folder,3,'Penentuan level pemaduan berbasis aturan')
    r.intro(stats,notes,'Level 2 bukan pasangan salah: data dipisah untuk verifikasi studio. Operator harus menggunakan layer terbaru hasil perbaikan.')
    r.figpage(1,'Distribusi level pemaduan','Jumlah pasangan Level 1 dan record yang memerlukan verifikasi studio.')
    r.bar(['Level 1','BPN Level 2','PBB Level 2'],[('Record',[len(lev1),len(lev2b),len(lev2p)])])
    whys=Counter(code.strip() for row in lev2b+lev2p for code in str(row['a'].get('kode_l2','')).split(';') if code.strip())
    r.figpage(2,'Alasan Level 2','Satu record dapat mempunyai lebih dari satu alasan, sehingga jumlah kategori tidak harus sama dengan jumlah record.')
    common=whys.most_common(16)
    r.bar([k for k,_ in common],[('Frekuensi',[v for _,v in common])],horizontal=True)
    passing=sum(1 for p in pairs if finite(p.get('overlap_bpn_pct')) is not None and p.get('overlap_bpn_pct')>50)
    r.figpage(3,'Seleksi pasangan berdasarkan overlap','Distribusi nilai overlap terhadap luas BPN untuk seluruh kandidat yang beririsan.')
    bounds=[0,20,40,50,60,80,100]
    vals=[sum(1 for row in pairs if (finite(row.get('overlap_bpn_pct')) or 0)>bounds[i]
                and (finite(row.get('overlap_bpn_pct')) or 0)<=bounds[i+1]) for i in range(len(bounds)-1)]
    r.bar([f'{bounds[i]}-{bounds[i+1]}%' for i in range(len(bounds)-1)],[('Kandidat',vals)])
    r.text('Ambang pemaduan aktual mengikuti parameter pilihan operator, bukan selalu 50%.',9)
    r.figpage(4,'Overlap dan kesamaan luas tertulis',
              'Hubungan overlap geometri BPN dengan kesamaan luas tertulis pada kandidat.')
    r.xy_scatter([(p.get('overlap_bpn_pct'),p.get('kesamaan_luas_tulis',p.get('kesamaan_pct')))
                  for p in pairs], 'Overlap BPN (%)','Kesamaan luas (%)')
    b_rows=bpn_all if bpn_all is not None else lev1+lev2b
    p_rows=pbb_all if pbb_all is not None else lev2p
    level1_pbb_ids={pair['record_pbb'] for pair in pairs if pair.get('status')=='LEVEL_1'}
    lev1p=[row for row in p_rows if row['idx'] in level1_pbb_ids]
    r.start('PETA 1 - LEVEL BPN')
    r.map([(lev2b,LEVEL_2,None,'BPN Level 2'),(lev1,LEVEL_1,None,'BPN Level 1')],
           'Distribusi pasangan otomatis dan bidang studio')
    r.start('PETA 2 - LEVEL PBB')
    r.map([(lev2p,LEVEL_2,None,'PBB Level 2'),
           (lev1p,LEVEL_1,None,'PBB Level 1')],
           'Distribusi pasangan otomatis dan objek PBB untuk verifikasi studio')
    r.start('REKAP PASANGAN DAN KANDIDAT')
    r.sub('Pasangan dengan overlap BPN terbesar')
    r.table(['NIB','NOP','Overlap BPN %','Overlap PBB %'],
            [(v.get('NIB',''),v.get('NOP',''),nice(v.get('overlap_bpn_pct')),nice(v.get('overlap_pbb_pct')))
             for v in sorted(pairs,key=lambda x:-(finite(x.get('overlap_bpn_pct')) or 0))[:20]])
    r.footer_recommendations([
        ('Periksa hubungan 1:N / N:1','Ambang overlap tidak otomatis menggugurkan bidang karena irisan kecil lain. Namun dua calon di atas ambang wajib diverifikasi.'),
        ('Prioritaskan atribut kosong dan kesamaan luas','Bandingkan luas tertulis BPN–PBB; nilai kosong tidak boleh dianggap sama.'),
        ('Gunakan output studio sebagai data label','Level 2 tidak boleh otomatis menjadi label negatif untuk AI.')],
        ['rekap_csv.zip: seluruh pasangan kandidat, overlap internal, gap, dan alasan Level 2.'])
    return r.close()


def report5(folder,lev1,lev2b,lev2p,pairs,scores,extras,stats,notes,model_meta,logs):
    r=Report(folder,5,'Inference AI dan penentuan Level 1/2')
    r.intro(stats,notes,'Status model dan sumber label GOLD/SILVER menentukan apakah AI boleh menambah Level 1. Skor tinggi saja tidak membuktikan kecocokan administratif.')
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
    r.start('PETA 1 - LEVEL 1 DAN BPN STUDIO')
    r.map([(lev2b,LEVEL_2,None,'BPN Level 2'),(lev1,LEVEL_1,None,'BPN Level 1')],
          'Hasil pemaduan menurut bidang BPN')
    r.start('PETA 2 - PBB STUDIO')
    r.map([(lev2p,LEVEL_2,None,'PBB Level 2')],
          'Objek PBB yang memerlukan verifikasi')
    r.start('DAFTAR REKOMENDASI INFERENCE')
    r.sub('Kandidat dengan skor AI terbesar')
    r.table(['NIB','NOP','Skor','Keputusan'],
            [(x.get('NIB'),x.get('NOP'),nice(x.get('skor_ai')),x.get('keputusan_ai'))
             for x in sorted(scores,key=lambda t:-(finite(t.get('skor_ai')) or 0))[:25]])
    r.sub('Status pengujian model')
    for k,v in (model_meta or {}).items():
        if k in ('algorithm','status','precision','model_version','test_data_source'):
            r.text('%s: %s'%(k,v),9)
    r.footer_recommendations([
        ('Pertahankan keunikan 1 NIB - 1 NOP','Periksa konflik kandidat sebelum mempromosikan pasangan berbasis AI.'),
        ('Periksa skor dan pesaing dekat','Kandidat dengan skor tertinggi tetapi margin kecil antar pasangan perlu verifikasi studio.'),
        ('Evaluasi GOLD independen','Kinerja model dan potensi tambahan Level 1 hanya boleh disimpulkan dari data operator yang diverifikasi.')],
        ['rekap_csv.zip: skor seluruh kandidat, pasangan berbasis aturan, tambahan AI.'])
    return r.close()


def report6(folder,decisions,candidates,bpn_rows=None,pbb_rows=None,notes=None):
    r=Report(folder,6,'Verifikasi studio interaktif')
    yes=sum(d.get('label')=='1' for d in decisions)
    no=sum(d.get('label')=='0' for d in decisions)
    unknown=sum(d.get('label') not in ('1','0') for d in decisions)
    r.intro({'Kandidat tersedia':len(candidates),'Keputusan tercatat':len(decisions),
             'Pasangan cocok (GOLD+)':yes,'Tidak cocok (GOLD-)':no,'Belum pasti':unknown},
            notes or ['Verifikasi menggunakan peta BPN/PBB dan bukti administratif.',
                       'Label 1 dan 0 mensyaratkan identitas operator dan sumber bukti.'],
            'Hasil Level 2 atau belum pasti bukan label negatif (0).')
    r.figpage(1,'Status keputusan studio','Ringkasan keputusan operator yang tersimpan sebagai label GOLD atau belum pasti.')
    r.bar(['Cocok (1)','Tidak cocok (0)','Belum pasti'],[('Pasangan',[yes,no,unknown])])
    r.start('PETA - PASANGAN YANG DIVERIFIKASI')
    if bpn_rows is not None and pbb_rows is not None:
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
    else:r.no_data('Layer sumber tidak tersedia saat PDF diekspor.')
    r.start('TABEL KEPUTUSAN OPERATOR')
    r.table(['NIB','NOP','Label','Sumber bukti'],
            [(row.get('NIB'),row.get('NOP'),row.get('label') or '?',row.get('sumber_verifikasi'))
             for row in decisions],limit=30)
    r.footer_recommendations([
        ('Lengkapi bukti pendukung','Sumber verifikasi harus jelas dan dapat ditelusuri.'),
        ('Prioritaskan pasangan meragukan','Periksa konflik 1:N / N:1 dan kesamaan batas dengan dokumen lapangan.'),
        ('Masukkan ke Modul 4','Gunakan label 1/0 yang terverifikasi, jangan gunakan belum pasti sebagai negatif.')],
        ['CSV keputusan berisi operator, waktu, bukti, dan label.', 'rekap_verifikasi.zip mencakup seluruh keputusan operator.'])
    return r.close()
