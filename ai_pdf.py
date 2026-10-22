"""Modul 4: multipage PDF report drawn with bundled QGIS Qt (Qt5/Qt6).
No matplotlib/reportlab dependency inside QGIS.
"""
from pathlib import Path
from .compat import set_pdf_a4
from qgis.PyQt.QtCore import QPointF, Qt
from qgis.PyQt.QtGui import QPdfWriter, QPainter, QPen, QColor, QFontMetrics, QPolygonF
from .report_theme import (NAVY, INK, MUTED, GRID as BORDER, TINT as PALE,
                           MODEL_RF, MODEL_XGB, GOOD_BG, BAD_BG)
from .report_font import report_font
from .report_frame import page_head, wrap, callout

try:
    ELIDE_RIGHT=Qt.TextElideMode.ElideRight
    DASH_LINE=Qt.PenStyle.DashLine
except AttributeError:
    ELIDE_RIGHT=Qt.ElideRight
    DASH_LINE=Qt.DashLine


def fmt(value, kind='pct'):
    if value is None: return 'N/A'
    if kind=='pct':return '%.1f%%' % (100*float(value))
    if kind=='f3':return '%.3f' % float(value)
    return str(value)


def model_colour(name):
    return MODEL_RF if str(name).lower().startswith('randomforest') else MODEL_XGB


class Canvas:
    def __init__(self,filepath):
        self.pdf=QPdfWriter(str(filepath))
        set_pdf_a4(self.pdf)
        self.pdf.setResolution(120)
        self.p=QPainter(self.pdf)
        self.w=self.pdf.width();self.h=self.pdf.height()
        self.ml=64;self.mr=64;self.y=70;self.page_num=0
        self.cw=self.w-self.ml-self.mr
        self.font(10)
    def font(self,size=10,bold=False):
        self.p.setFont(report_font(size,bold))
    def wrapped(self,text,width):
        return wrap(self.p,text,width)
    def new(self,title,subtitle=''):
        if self.page_num:self.pdf.newPage()
        self.page_num+=1
        self.y=page_head(self.p,self.w,self.h,self.ml,self.mr,4,self.page_num,title,subtitle)
    def line(self,s,size=10,bold=False,color=INK,space=22):
        self.font(size,bold);self.p.setPen(QPen(color));self.p.drawText(self.ml,self.y,str(s));self.y+=space
    def para(self,t,size=9,width=109,leading=20,indent=0):
        self.font(size)
        for line in self.wrapped(t,self.cw-indent):
            if self.y>self.h-99: self.new('Lanjutan laporan Modul 4')
            self.font(size);self.p.setPen(QPen(INK));self.p.drawText(self.ml+indent,self.y,line);self.y+=leading
        self.y+=8
    def section(self,t):
        if self.y>self.h-140:self.new('Lanjutan laporan Modul 4')
        self.y+=20
        self.font(12,True);self.p.setPen(QPen(NAVY));self.p.drawText(self.ml,self.y,t)
        self.y+=30
    def table(self,head, rows, widths=None, row_height=30, size=9):
        n=len(head)
        if widths is None:widths=[self.cw/n]*n
        xx=[self.ml]
        for w in widths:xx.append(xx[-1]+w)
        def draw_row(vals,headrow=False,i=0):
            self.font(max(9,size),headrow)
            cells=[]
            for val,w in zip(vals,widths):
                lines=self.wrapped(str(val),w-14)
                expanded=[]
                for line in lines:
                    part=''
                    for char in line:
                        if part and QFontMetrics(self.p.font()).horizontalAdvance(part+char)>w-14:
                            expanded.append(part);part=char
                        else:part+=char
                    if part:expanded.append(part)
                cells.append(expanded or [''])
            height=max(row_height,14+18*max(map(len,cells)))
            if not headrow and self.y+height>self.h-110:
                self.new('Lanjutan tabel evaluasi')
                draw_row(head,True)
            top=self.y-18
            self.p.fillRect(self.ml,top,int(sum(widths)),height,
                NAVY if headrow else (PALE if i%2==0 else QColor('#ffffff')))
            self.font(max(9,size),headrow);self.p.setPen(QPen(QColor('white') if headrow else INK))
            for j,lines in enumerate(cells):
                for k,line in enumerate(lines):
                    self.p.drawText(int(xx[j]+7),int(self.y+k*18),line)
            self.y+=height
        draw_row(head,True)
        for i,row in enumerate(rows):
            draw_row(row,False,i)
        self.y+=14
    def note(self,text, caution=False, kind=None):
        if kind is None and caution:kind='caution'
        self.font(10)
        lines=self.wrapped(text,self.cw-32)
        box_h=40+23*len(lines)
        if self.y+box_h>self.h-90:self.new('Catatan evaluasi')
        self.y+=callout(self.p,self.ml,self.y,self.cw,text,
                        'warning' if kind in ('caution','bad') else 'note')+18
    def close(self):self.p.end()


def plot(c,x,y,width,height,series,xname,yname,baseline=None,diagonal=False):
    # series = [(title,color, {'x':[], 'y':[]}),...]
    p=c.p
    left=x+39;top=y+23;right=x+width-11;bottom=y+height-54
    p.setPen(QPen(BORDER,1))
    p.drawRect(int(left),int(top),int(right-left),int(bottom-top))
    c.font(9)
    for i in range(5):
        v=i/4
        py=bottom-v*(bottom-top);px=left+v*(right-left)
        p.setPen(QPen(BORDER,1))
        p.drawLine(int(left),int(py),int(right),int(py))
        p.setPen(QPen(MUTED))
        p.drawText(int(left-33),int(py+4),'%.2f'%v)
        p.drawText(int(px-10),int(bottom+18),'%.2f'%v)
    if baseline is not None:
        p.setPen(QPen(MUTED,1.4,DASH_LINE))
        yy=bottom-float(baseline)*(bottom-top)
        p.drawLine(int(left),int(yy),int(right),int(yy))
        c.font(9);p.drawText(int(right-155),int(yy-5),'Acuan %.2f'%baseline)
    if diagonal:
        p.setPen(QPen(MUTED,1.4,DASH_LINE))
        p.drawLine(int(left),int(bottom),int(right),int(top))
    for index,(label,color,points) in enumerate(series):
        xs=points.get('x',[]);ys=points.get('y',[])
        if len(xs)<2:continue
        poly=QPolygonF([QPointF(left+float(a)*(right-left),bottom-float(b)*(bottom-top))
                        for a,b in zip(xs,ys)])
        pen=QPen(color,2.6)
        if index%2:pen.setStyle(DASH_LINE)
        p.setPen(pen);p.drawPolyline(poly)
    c.font(9);p.setPen(QPen(INK));p.drawText(int(left+25),int(bottom+37),xname)
    p.drawText(int(left),int(top-10),yname)
    lx=left;ly=y+height+17
    for index,(label,color,_) in enumerate(series):
        pen=QPen(color,2.6)
        if index%2:pen.setStyle(DASH_LINE)
        p.setPen(pen);p.drawLine(int(lx),int(ly-4),int(lx+22),int(ly-4))
        p.setPen(QPen(INK));c.font(9);p.drawText(int(lx+29),int(ly),label)
        lx+=min(190,width/max(1,len(series)))


def confusion(c,name,m,x,y,block=64):
    c.font(11,True);c.p.setPen(QPen(NAVY));c.p.drawText(x,y,name)
    y+=25
    c.font(9);c.p.setPen(QPen(MUTED));c.p.drawText(x+64,y,'Pred 0');c.p.drawText(x+128,y,'Pred 1')
    y+=13
    for row in range(2):
        for col in range(2):
            v=m['confusion_matrix'][row][col]
            bx=x+60+col*block;by=y+row*block
            c.p.fillRect(bx,by,block-3,block-3, GOOD_BG if row==col else BAD_BG)
            c.font(11,True);c.p.setPen(QPen(INK));c.p.drawText(bx+15,by+34,str(v))
    c.font(9);c.p.setPen(QPen(MUTED));c.p.drawText(x,y+36,'Real 0');c.p.drawText(x,y+100,'Real 1')
    c.font(9);c.p.setPen(QPen(INK));c.p.drawText(x+3,y+145,'FP = %s | FN = %s'%(m['fp'],m['fn']))


def featurebars(c, features, x, y, w, colour=MODEL_RF, maxrows=10):
    subset=features[:maxrows]
    if not subset:return
    mx=max(float(z['importance']) for z in subset) or 1
    for i,item in enumerate(subset):
        yy=y+i*34
        c.font(9);c.p.setPen(QPen(INK))
        label=str(item['fitur'])[:31]
        c.p.drawText(int(x),int(yy),label)
        bar_x=x+240;bar_w=w-280
        c.p.fillRect(int(bar_x),int(yy-12),int(bar_w*float(item['importance'])/mx),14,colour)
        c.p.drawText(int(bar_x+bar_w+5),int(yy),'%.3f'%float(item['importance']))


def make_training_report(output_dir, evaldata, notes=None, summary=None):
    output_dir=Path(output_dir);output_dir.mkdir(exist_ok=True,parents=True)
    path=output_dir/'laporan_modul4.pdf'
    c=Canvas(path)
    try:
        models=evaldata.get('models',{})
        selected=evaldata.get('model_terpilih','N/A')
        has_test=evaldata.get('evaluasi_gold_tersedia',False)
        c.new('Evaluasi model pemaduan','Klasifikasi pasangan NIB–NOP')
        status=evaldata.get('status_operasional','BELUM DAPAT DINILAI')
        status_kind=('unknown' if not has_test or status.startswith('BELUM DAPAT DINILAI')
                     else 'bad' if status.startswith('BELUM LAYAK')
                     else 'good' if status.startswith('LAYAK') else 'attention')
        verdict='BELUM DAPAT DINILAI' if not has_test else status.replace('_',' ').capitalize()
        c.line(verdict,19,True,NAVY,space=36)
        c.note('Belum ada data uji GOLD independen; angka TRAIN tidak mengukur kinerja pada pasangan baru.'
               if not has_test else status.replace('_',' ').capitalize(),kind=status_kind)
        c.section('Tindakan prioritas')
        for i,action in enumerate(evaldata.get('rekomendasi',[])[:3],1):
            c.para('T%d. %s'%(i,action),size=9,leading=18)
        c.section('Data yang digunakan')
        rows=[['Model terpilih',selected],['Status data GOLD',str(evaldata.get('jumlah_gold',0))+' pasangan'],
            ['SILVER (hasil aturan)',str(evaldata.get('jumlah_silver',0))],
            ['Data FIT',str(evaldata.get('jumlah_fit',0))],
            ['Validasi GOLD',str(evaldata.get('jumlah_validasi',0))],
            ['Testing GOLD',str(evaldata.get('jumlah_testing',0))],
            ['Ambang skor klasifikasi',str(evaldata.get('ambang_prediksi',.9))],
            ['Target Precision (usulan)',fmt(evaldata.get('target_precision_usulan',.99))]]
        c.table(['Komponen','Hasil'],rows,[270,c.cw-270],row_height=31,size=9)
        if not has_test:
            c.note('Belum ada GOLD testing independen. Metrik TRAIN hanya menjelaskan data latihan; kinerja pada pasangan baru belum dapat dinilai.',kind='unknown')
        else:
            c.para('Metrik TEST berasal dari GOLD independen. Utamakan Precision, false positive, dan batas bawah kepercayaan sebelum menilai kelayakan model.')
        c.para('SILVER adalah label hasil aturan. Level 2 tidak otomatis menjadi label negatif (0).')

        c.new('Metrik model','TRAIN menjelaskan data latihan; TEST memerlukan GOLD independen')
        for name, detail in models.items():
            c.section(name + (' (Terpilih)' if name==selected else ''))
            rows=[]
            for split in ('TRAIN','VALIDATION','TEST'):
                m=detail['split'].get(split)
                if m:
                    rows.append([split,str(m['n']),fmt(m['precision']),fmt(m['recall']),
                        fmt(m['f1']),fmt(m['accuracy']),fmt(m.get('auc_roc'),'f3'),fmt(m.get('average_precision'),'f3')])
            widths=[90,65,105,102,89,95,105,c.cw-(90+65+105+102+89+95+105)]
            c.table(['Split','n','Precision','Recall','F1','Accuracy','ROC-AUC','AP'],rows,widths,row_height=34,size=9)
            tests=detail['split'].get('TEST')
            if tests:
                c.para('TEST: prediksi positif %d | FP %d | FN %d | Brier %.3f (baseline %.3f) | batas bawah Precision CI95 %s.'%
                    (tests['prediksi_positif'],tests['fp'],tests['fn'],tests['brier'],tests['brier_baseline_prevalensi'],fmt(tests['precision_ci95_bawah'])))
        if not has_test:
            c.note('TEST GOLD belum tersedia. Kumpulkan keputusan studio dengan bukti dan sisihkan sebagian sebagai data uji independen.',kind='unknown')

        judgements=evaldata.get('penilaian_per_metrik',[])
        if judgements:
            c.new('Penilaian Otomatis per Metrik','Patokan di bawah adalah panduan kebijakan, bukan izin otomatis untuk pemaduan Level 1')
            c.table(['Metrik','Hasil TEST','Patokan operator','Interpretasi'],
                    [[z['metrik'],z['nilai'],z['patokan'],z['interpretasi']] for z in judgements],
                    [170,110,260,c.cw-540],row_height=40,size=9)
            c.note('Periksa terutama Precision, jumlah FP, dan batas bawah kepercayaan Precision. Kategori MEMADAI pada metrik lain bukan izin untuk menggabungkan tanpa audit konflik pasangan.',True)
        test_models=[(name,x['split'].get('TEST')) for name,x in models.items() if x['split'].get('TEST')]
        if test_models:
            c.new('Confusion Matrix (GOLD testing)','Baris = label asli, kolom = prediksi model; FP berarti pasangan salah digabung')
            for i,(name,metric) in enumerate(test_models):
                confusion(c,name,metric,c.ml+int((i%2)*(c.cw/2)),c.y+22+(i//2)*230)
            c.y+=240*(len(test_models)+1)//2
            c.section('Interpretasi untuk operator')
            c.para('TP = pasangan benar yang diterima; TN = pasangan salah yang ditolak; FP = pasangan salah yang diterima (risiko utama); FN = pasangan benar yang terlewat. Periksa setiap FP terhadap dokumen resmi dan geometri.')
        if test_models:
            c.new('Kurva ROC dan Precision-Recall','Dari prediksi GOLD test; kurva PR perlu dibandingkan dengan prevalensi positif')
            roc=[(name,model_colour(name),m['kurva'].get('roc',{})) for name,m in test_models]
            pr=[(name,model_colour(name),m['kurva'].get('pr',{})) for name,m in test_models]
            c.section('ROC - True Positive Rate vs False Positive Rate')
            plot(c,c.ml,c.y,c.cw,370,roc,'False positive rate','TPR')
            c.y+=435
            c.section('Precision-Recall')
            plot(c,c.ml,c.y,c.cw,370,pr,'Recall','Precision',baseline=test_models[0][1]['prevalensi'])
            c.y+=435
            c.para('ROC-AUC dekat 0,50 setara pengurutan acak. Average Precision (AP) memakai ringkasan kurva PR; baseline acak kira-kira prevalensi positif, bukan angka tetap.')

            c.new('Kalibrasi dan fitur penting','Skor AI bukan otomatis probabilitas benar tanpa pengecekan kalibrasi')
            c.section('Kalibrasi probabilitas pada GOLD test')
            calibr=[(name,model_colour(name),m['kurva'].get('kalibrasi',{})) for name,m in test_models]
            plot(c,c.ml,c.y,c.cw,320,calibr,'Skor rata-rata','Proporsi cocok',diagonal=True)
            c.y+=385
            c.para('Idealnya titik berada dekat diagonal y=x. Brier Score lebih kecil lebih baik; bandingkan dengan baseline prediksi konstan prevalensi pada GOLD test.')
            c.section('Feature importance model terpilih')
            featurebars(c,models[selected].get('feature_importance',[]),c.ml,c.y+20,c.cw,model_colour(selected))
            c.y+=390
            c.para('Feature importance menunjukkan hubungan prediktif, bukan sebab-akibat atau bukti administratif. Jangan gunakan fitur turunan label atau keputusan Modul 3 sebagai prediktor.')

        if has_test:c.new('Tindakan berikutnya')
        else:c.section('Tindakan berikutnya')
        recommendations=evaldata.get('rekomendasi',[])
        for i,line in enumerate(recommendations,1):
            c.para('%d. %s'%(i,line),size=10,leading=24)
        if not recommendations:
            c.note('Tidak ada rekomendasi otomatis. Tinjau hasil pengujian dan catatan di bawah sebelum memakai model.',kind='unknown')
        if has_test:
            c.section('Catatan evaluasi')
            for t in evaldata.get('catatan',[]):
                if not str(t).startswith('R2 / MAE / RMSE'):
                    c.para('- '+str(t),size=9,width=109)
            c.note('Metrik TEST tidak mengesahkan pasangan Level 1. Periksa konflik NIB–NOP 1:1 dan bukti administrasi.',True)
        else:
            c.note('Sebelum promosi otomatis, kumpulkan GOLD test independen dan periksa konflik NIB–NOP 1:1.',kind='caution')
    finally:
        c.close()
    return str(path)
