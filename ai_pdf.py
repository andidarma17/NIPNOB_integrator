"""Modul 4: multipage PDF report drawn with bundled QGIS Qt (Qt5/Qt6).
No matplotlib/reportlab dependency inside QGIS.
"""
import textwrap
from pathlib import Path
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QPdfWriter, QPageSize, QPainter, QPen, QColor, QFont, QPolygonF
from .evaluation import threshold_guidance

NAVY=QColor('#163b5b'); INK=QColor('#222d38'); MUTED=QColor('#64748b')
BLUE=QColor('#2376b7'); ORANGE=QColor('#dc8135'); PALE=QColor('#eff5f9')
BORDER=QColor('#d7e2ed'); RED=QColor('#ae3e3e')


def fmt(value, kind='pct'):
    if value is None: return 'N/A'
    if kind=='pct':return '%.1f%%' % (100*float(value))
    if kind=='f3':return '%.3f' % float(value)
    return str(value)


class Canvas:
    def __init__(self,filepath):
        self.pdf=QPdfWriter(str(filepath))
        self.pdf.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        self.pdf.setResolution(120)
        self.p=QPainter(self.pdf)
        self.w=self.pdf.width();self.h=self.pdf.height()
        self.ml=64;self.mr=64;self.y=70;self.page_num=0
        self.cw=self.w-self.ml-self.mr
        self.font(10)
    def font(self,size=10,bold=False):
        f=QFont('DejaVu Sans',size);f.setBold(bold)
        self.p.setFont(f)
    def new(self,title,subtitle=''):
        if self.page_num:self.pdf.newPage()
        self.page_num+=1;self.y=68
        self.p.fillRect(0,0,self.w,13,NAVY)
        self.p.setPen(QPen(MUTED));self.font(8)
        self.p.drawText(self.ml,self.h-42,'NIB-NOP Integrator | Modul 4 - Training AI')
        self.p.drawText(self.w-115,self.h-42,'Hal. %d'%self.page_num)
        self.font(19,True);self.p.setPen(QPen(NAVY))
        self.p.drawText(self.ml,self.y,title);self.y+=37
        if subtitle:
            self.font(9);self.p.setPen(QPen(MUTED));self.p.drawText(self.ml,self.y,subtitle);self.y+=25
        self.p.setPen(QPen(BORDER));self.p.drawLine(self.ml,self.y,self.w-self.mr,self.y)
        self.y+=25
    def line(self,s,size=10,bold=False,color=INK,space=22):
        self.font(size,bold);self.p.setPen(QPen(color));self.p.drawText(self.ml,self.y,str(s));self.y+=space
    def para(self,t,size=9,width=109,leading=20,indent=0):
        for line in (textwrap.wrap(str(t),width=width,break_long_words=False,break_on_hyphens=False) or ['']):
            if self.y>self.h-99: self.new('Lanjutan laporan Modul 4')
            self.font(size);self.p.setPen(QPen(INK));self.p.drawText(self.ml+indent,self.y,line);self.y+=leading
        self.y+=8
    def section(self,t):
        self.y+=8
        self.font(12,True);self.p.setPen(QPen(NAVY));self.p.drawText(self.ml,self.y,t)
        self.y+=27
    def table(self,head, rows, widths=None, row_height=30, size=8):
        n=len(head)
        if widths is None:widths=[self.cw/n]*n
        xx=[self.ml]
        for w in widths:xx.append(xx[-1]+w)
        def draw_row(vals,headrow=False,i=0):
            top=self.y-18
            self.p.fillRect(self.ml,top,int(sum(widths)),row_height,
                NAVY if headrow else (PALE if i%2==0 else QColor('#ffffff')))
            self.font(size,headrow);self.p.setPen(QPen(QColor('white') if headrow else INK))
            for j,val in enumerate(vals):
                st=str(val)
                # Protect against long text spilling into adjacent columns
                max_chars=max(7,int(widths[j]/(size*0.78)))
                if len(st)>max_chars:st=st[:max_chars-2]+'..'
                self.p.drawText(int(xx[j]+7),int(self.y),st)
            self.y+=row_height
        draw_row(head,True)
        for i,row in enumerate(rows):
            if self.y>self.h-110:
                self.new('Lanjutan tabel evaluasi')
                draw_row(head,True)
            draw_row(row,False,i)
        self.y+=14
    def note(self,text, caution=False):
        lines=textwrap.wrap(text,95,break_long_words=False)
        box_h=28+20*len(lines)
        if self.y+box_h>self.h-90:self.new('Catatan evaluasi')
        self.p.fillRect(self.ml,self.y-12,self.cw,box_h, QColor('#fff6eb') if caution else PALE)
        self.p.setPen(QPen(RED if caution else INK));self.font(9)
        for s in lines:
            self.p.drawText(self.ml+13,self.y+6,s);self.y+=20
        self.y+=24
    def close(self):self.p.end()


def plot(c,x,y,width,height,series,xname,yname,baseline=None):
    # series = [(title,color, {'x':[], 'y':[]}),...]
    p=c.p
    left=x+39;top=y+23;right=x+width-11;bottom=y+height-54
    p.setPen(QPen(BORDER,1))
    p.drawRect(int(left),int(top),int(right-left),int(bottom-top))
    c.font(8);p.setPen(QPen(MUTED))
    for i in range(5):
        v=i/4
        py=bottom-v*(bottom-top);px=left+v*(right-left)
        p.drawLine(int(left),int(py),int(right),int(py))
        p.drawText(int(left-33),int(py+4),'%.2f'%v)
        p.drawText(int(px-10),int(bottom+18),'%.2f'%v)
    if baseline is not None:
        p.setPen(QPen(QColor('#98a6b4'),1))
        yy=bottom-float(baseline)*(bottom-top)
        p.drawLine(int(left),int(yy),int(right),int(yy))
    for label,color,points in series:
        xs=points.get('x',[]);ys=points.get('y',[])
        if len(xs)<2:continue
        poly=QPolygonF([QPointF(left+float(a)*(right-left),bottom-float(b)*(bottom-top))
                        for a,b in zip(xs,ys)])
        p.setPen(QPen(color,2.6));p.drawPolyline(poly)
    c.font(9);p.setPen(QPen(INK));p.drawText(int(left+25),int(bottom+41),xname)
    p.drawText(int(left-15),int(top-10),yname)
    lx=left;ly=y+height-4
    for label,color,_ in series:
        p.fillRect(int(lx),int(ly-10),10,10,color)
        p.setPen(QPen(INK));c.font(8);p.drawText(int(lx+14),int(ly),label)
        lx+=min(150,width/len(series))


def confusion(c,name,m,x,y,block=64):
    c.font(11,True);c.p.setPen(QPen(NAVY));c.p.drawText(x,y,name)
    y+=25
    c.font(8);c.p.setPen(QPen(MUTED));c.p.drawText(x+34,y,'Pred 0');c.p.drawText(x+112,y,'Pred 1')
    y+=13
    for row in range(2):
        for col in range(2):
            v=m['confusion_matrix'][row][col]
            bx=x+32+col*block;by=y+row*block
            c.p.fillRect(bx,by,block-3,block-3, QColor('#e3f0f6') if row==col else QColor('#ffe9df'))
            c.font(11,True);c.p.setPen(QPen(INK));c.p.drawText(bx+15,by+34,str(v))
    c.font(8);c.p.setPen(QPen(MUTED));c.p.drawText(x,y+32,'Real 0');c.p.drawText(x,y+96,'Real 1')
    c.font(9);c.p.setPen(QPen(INK));c.p.drawText(x+3,y+145,'FP = %s | FN = %s'%(m['fp'],m['fn']))


def featurebars(c, features, x, y, w, maxrows=10):
    subset=features[:maxrows]
    if not subset:return
    mx=max(float(z['importance']) for z in subset) or 1
    for i,item in enumerate(subset):
        yy=y+i*34
        c.font(8);c.p.setPen(QPen(INK))
        label=str(item['fitur'])[:31]
        c.p.drawText(int(x),int(yy),label)
        bar_x=x+240;bar_w=w-280
        c.p.fillRect(int(bar_x),int(yy-12),int(bar_w*float(item['importance'])/mx),14,BLUE)
        c.p.drawText(int(bar_x+bar_w+5),int(yy),'%.3f'%float(item['importance']))


def make_training_report(output_dir, evaldata, notes=None, summary=None):
    output_dir=Path(output_dir);output_dir.mkdir(exist_ok=True,parents=True)
    path=output_dir/'laporan_modul4.pdf'
    c=Canvas(path)
    try:
        models=evaldata.get('models',{})
        selected=evaldata.get('model_terpilih','N/A')
        has_test=evaldata.get('evaluasi_gold_tersedia',False)
        c.new('Laporan Evaluasi Training AI','Pemaduan NIB-NOP | Klasifikasi biner cocok/tidak cocok')
        c.note('STATUS: '+evaldata.get('status_operasional','BELUM DAPAT DINILAI'),not has_test)
        c.section('Ringkasan proses')
        rows=[['Model terpilih',selected],['Status data GOLD',str(evaldata.get('jumlah_gold',0))+' pasangan'],
            ['SILVER (hasil aturan)',str(evaldata.get('jumlah_silver',0))],
            ['Data FIT',str(evaldata.get('jumlah_fit',0))],
            ['Validasi GOLD',str(evaldata.get('jumlah_validasi',0))],
            ['Testing GOLD',str(evaldata.get('jumlah_testing',0))],
            ['Ambang skor klasifikasi',str(evaldata.get('ambang_prediksi',.9))],
            ['Target Precision (usulan)',fmt(evaldata.get('target_precision_usulan',.99))]]
        c.table(['Komponen','Hasil'],rows,[270,c.cw-270],row_height=31,size=9)
        c.section('Cara membaca laporan')
        c.para('Training mengukur kecocokan model pada data yang dipelajari, bukan akurasi data baru. Validation digunakan untuk pemilihan model; testing GOLD independen digunakan untuk estimasi kinerja di luar training.')
        c.para('SILVER berasal dari aturan Modul 3 dan tidak cukup sebagai dasar klaim akurasi. Label Level 2 tidak otomatis sama dengan salah (0).')
        c.note('Nilai R2, MAE dan RMSE tidak digunakan sebagai metrik utama: target model adalah klasifikasi pasangan (1 atau 0), bukan prediksi luas/harga.')

        c.new('Metrik model','TRAIN bersifat diagnostik; VALIDATION dan TEST hanya sah jika berasal dari GOLD independen')
        for name, detail in models.items():
            c.section(name + (' (Terpilih)' if name==selected else ''))
            rows=[]
            for split in ('TRAIN','VALIDATION','TEST'):
                m=detail['split'].get(split)
                if not m:
                    rows.append([split,'N/A']+['N/A']*6)
                else:
                    rows.append([split,str(m['n']),fmt(m['precision']),fmt(m['recall']),
                        fmt(m['f1']),fmt(m['accuracy']),fmt(m.get('auc_roc'),'f3'),fmt(m.get('average_precision'),'f3')])
            widths=[90,65,105,102,89,95,105,c.cw-(90+65+105+102+89+95+105)]
            c.table(['Split','n','Precision','Recall','F1','Accuracy','ROC-AUC','AP'],rows,widths,row_height=34,size=8)
            tests=detail['split'].get('TEST')
            if tests:
                c.para('TEST: prediksi positif %d | FP %d | FN %d | Brier %.3f (baseline %.3f) | batas bawah Precision CI95 %s.'%
                    (tests['prediksi_positif'],tests['fp'],tests['fn'],tests['brier'],tests['brier_baseline_prevalensi'],fmt(tests['precision_ci95_bawah'])))
        if not has_test:
            c.note('TEST GOLD BELUM TERSEDIA. Angka TRAIN tidak boleh dipakai menyatakan model sudah baik untuk pemaduan nyata.',True)

        c.new('Penilaian Otomatis per Metrik','Patokan di bawah adalah panduan kebijakan, bukan izin otomatis untuk pemaduan Level 1')
        judgements=evaldata.get('penilaian_per_metrik',[])
        if judgements:
            c.table(['Metrik','Hasil TEST','Patokan operator','Interpretasi'],
                    [[z['metrik'],z['nilai'],z['patokan'],z['interpretasi']] for z in judgements],
                    [170,110,260,c.cw-540],row_height=40,size=8)
            c.note('Periksa terutama Precision, jumlah FP, dan batas bawah kepercayaan Precision. Kategori MEMADAI pada metrik lain bukan izin untuk menggabungkan tanpa audit konflik pasangan.',True)
        else:
            c.note('BELUM DAPAT DINILAI - GOLD test independen belum tersedia. Training SILVER bukan pengukuran akurasi.',True)

        c.new('Confusion Matrix (GOLD testing)','Baris = label asli, kolom = prediksi model; FP berarti pasangan salah digabung')
        test_models=[(name,x['split'].get('TEST')) for name,x in models.items() if x['split'].get('TEST')]
        if test_models:
            for i,(name,metric) in enumerate(test_models):
                confusion(c,name,metric,c.ml+int((i%2)*(c.cw/2)),c.y+22+(i//2)*230)
            c.y+=240*(len(test_models)+1)//2
            c.section('Interpretasi untuk operator')
            c.para('TP = pasangan benar yang diterima; TN = pasangan salah yang ditolak; FP = pasangan salah yang diterima (risiko utama); FN = pasangan benar yang terlewat. Periksa setiap FP terhadap dokumen resmi dan geometri.')
        else:
            c.note('Belum ada matriks GOLD independen. Isikan data verifikasi operator terlebih dahulu.',True)

        if test_models:
            c.new('Kurva ROC dan Precision-Recall','Dari prediksi GOLD test; kurva PR perlu dibandingkan dengan prevalensi positif')
            roc=[(name,BLUE if i==0 else ORANGE,m['kurva'].get('roc',{})) for i,(name,m) in enumerate(test_models)]
            pr=[(name,BLUE if i==0 else ORANGE,m['kurva'].get('pr',{})) for i,(name,m) in enumerate(test_models)]
            c.section('ROC - True Positive Rate vs False Positive Rate')
            plot(c,c.ml,c.y,c.cw,370,roc,'False positive rate','TPR')
            c.y+=405
            c.section('Precision-Recall')
            plot(c,c.ml,c.y,c.cw,370,pr,'Recall','Precision',baseline=test_models[0][1]['prevalensi'])
            c.y+=390
            c.para('ROC-AUC dekat 0,50 setara pengurutan acak. Average Precision (AP) memakai ringkasan kurva PR; baseline acak kira-kira prevalensi positif, bukan angka tetap.')

            c.new('Kalibrasi dan fitur penting','Skor AI bukan otomatis probabilitas benar tanpa pengecekan kalibrasi')
            c.section('Kalibrasi probabilitas pada GOLD test')
            calibr=[(name,BLUE if i==0 else ORANGE,m['kurva'].get('kalibrasi',{})) for i,(name,m) in enumerate(test_models)]
            plot(c,c.ml,c.y,c.cw,320,calibr,'Skor rata-rata','Proporsi cocok')
            c.y+=345
            c.para('Idealnya titik berada dekat diagonal y=x. Brier Score lebih kecil lebih baik; bandingkan dengan baseline prediksi konstan prevalensi pada GOLD test.')
            c.section('Feature importance model terpilih')
            featurebars(c,models[selected].get('feature_importance',[]),c.ml,c.y+20,c.cw)
            c.y+=390
            c.para('Feature importance menunjukkan hubungan prediktif, bukan sebab-akibat atau bukti administratif. Jangan gunakan fitur turunan label atau keputusan Modul 3 sebagai prediktor.')

        c.new('Panduan interpretasi metrik','Ambang di bawah adalah target awal yang dapat diubah; bukan ketentuan hukum atau standar universal')
        for i,r in enumerate(threshold_guidance()):
            if c.y>c.h-190:c.new('Lanjutan panduan interpretasi')
            c.section('%d. %s'%(i+1,r['nama']))
            c.para(r['panduan']+'. '+r['alasan'],size=9,width=105,leading=19)
        c.note('Keputusan terbaik ditentukan oleh biaya kesalahan pemaduan, distribusi kelas, dukungan sampel, dan konsistensi pada wilayah independen.',True)

        c.new('Rekomendasi Tindak Lanjut','Rekomendasi dinamis berdasarkan evaluasi model terpilih pada data GOLD test')
        for i,line in enumerate(evaldata.get('rekomendasi',[]),1):
            c.section('%d. Rekomendasi'%i)
            c.para(line,width=109)
        c.section('Pembatasan dan tindakan operator')
        for t in evaldata.get('catatan',[]):
            c.para('- '+str(t),size=9,width=109)
        c.note('Kesimpulan: angka testing tidak otomatis mengesahkan pasangan Level 1. Audit konflik NIB/NOP 1:1 dan bukti administrasi tetap wajib.',True)
    finally:
        c.close()
    return str(path)
