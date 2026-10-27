import sys, random, math
sys.path.insert(0,'/home/claude/render_env/shim'); sys.path.insert(0,'/home/claude/render_env/pkg')
import os; os.environ['QT_QPA_PLATFORM']='offscreen'
from PyQt5.QtGui import QGuiApplication
app=QGuiApplication(sys.argv)
from nibnop_integrator import reporting_full as rf
from PyQt5.QtGui import QPdfWriter
# probe page geometry
from nibnop_integrator.compat import set_pdf_a4
w=QPdfWriter('/home/claude/render_env/out/probe.pdf'); set_pdf_a4(w); w.setResolution(120)
print('PAGE', w.width(), w.height(), w.pageLayout().margins(), w.pageLayout().pageSize().size(0))
class G:
    def __init__(s,pts): s.pts=pts
    def isNull(s):return False
    def isEmpty(s):return False
    def isMultipart(s):return False
    def asPolygon(s):return [s.pts]
    def boundingBox(s):
        class B:
            def __init__(b,p):
                b.p=p
            def xMinimum(b):return min(x for x,y in b.p)
            def xMaximum(b):return max(x for x,y in b.p)
            def yMinimum(b):return min(y for x,y in b.p)
            def yMaximum(b):return max(y for x,y in b.p)
            def intersects(b,o):return True
            def width(b):return b.xMaximum()-b.xMinimum()
            def height(b):return b.yMaximum()-b.yMinimum()
        return B(s.pts)
    def area(s):
        a=0
        for i in range(len(s.pts)):
            x1,y1=s.pts[i];x2,y2=s.pts[(i+1)%len(s.pts)];a+=x1*y2-x2*y1
        return abs(a)/2
    def asPoint(s):pass
from PyQt5.QtCore import QPointF
class P:
    def __init__(s,x,y):s._x,s._y=x,y
    def x(s):return s._x
    def y(s):return s._y
random.seed(3)
def grid(n,ov=0.1,gapn=0):
    rows=[]
    side=int(math.sqrt(n))+1
    for i in range(n):
        gx,gy=i%side,i//side
        x=gx*30+random.uniform(-1,1);y=gy*30+random.uniform(-1,1)
        w=26+random.uniform(0,3);h=26+random.uniform(0,3)
        pts=[P(x,y),P(x+w,y),P(x+w,y+h),P(x,y+h),P(x,y)]
        class GG(G):
            pass
        g=GG([(p.x(),p.y()) for p in pts])
        g.asPolygon=lambda pts=pts:[pts]
        rows.append({'idx':i+1,'fid':i,'a':{'NIB':'B%05d'%i,'LUAS':random.lognormvariate(5,.6),'overlap':int(random.random()<ov),'bid_tambah':0,'geom_invalid':int(random.random()<.05),'luas_flag':random.choice(['','','','LUAS_KECIL','LUAS_BESAR'])},'geom':g})
    return rows
b=grid(180);p=grid(200)
for r in b[:3]: r['a']['bid_tambah']=1
stats={'BPN jumlah_record':180,'BPN identitas_kosong':3,'BPN record_duplikat':5,'BPN record_luas_bermasalah':20,'PBB jumlah_record':200,'PBB identitas_kosong':1,'PBB record_duplikat':8,'PBB record_luas_bermasalah':41}
rf.report1('/home/claude/render_env/out',(b,'NIB','LUAS'),(p,'NIB','LUAS'),stats,{},5,10000)
st2={'bpn_geom_kosong':0,'bpn_geom_invalid':4,'bpn_geom_fixed':4,'bpn_overlap':18,'bpn_gap_baru':3,'pbb_geom_kosong':1,'pbb_geom_invalid':9,'pbb_geom_fixed':8,'pbb_overlap':22,'pbb_gap_baru':0,'bpn_record_awal':180}
ov=[{'record_a':i,'record_b':i+1,'luas_irisan_m2':random.uniform(.1,40)} for i in range(15)]
gp=[{'gap_id':'GAP%05d'%i,'luas_m2':random.uniform(1,80),'ditambahkan':1} for i in range(5)]
rf.report2('/home/claude/render_env/out',b,p,st2,['Catatan metode satu.','Catatan metode dua.'],ov,ov,gp)
pairs=[{'NIB':'B%05d'%i,'NOP':'33.04.%05d'%i,'overlap_bpn_pct':random.uniform(5,99),'overlap_pbb_pct':random.uniform(5,99),'kesamaan_luas_tulis':random.uniform(40,100)} for i in range(120)]
for r in b[:40]: r['a']['kode_l2']=random.choice(['OVERLAP_KURANG','MULTI_NOP;LUAS_BPN_TIDAK_SESUAI','NIB_DUPLIKAT'])
rf.report3('/home/claude/render_env/out',b[:100],b[100:],p[:90],pairs,{'Level 1':100,'BPN Level 2':80,'PBB Level 2':90,'Pasangan beririsan':120},['Input wajib dari layer terbaru.','Ambang 50%'],[],bpn_all=b,pbb_all=p)
for q in pairs: q['skor_ai']=random.random(); q['keputusan_ai']='REKOMENDASI_STUDIO'
rf.report5('/home/claude/render_env/out',b[:100],b[100:],p[:90],pairs,pairs,pairs[:5],{'Level 1':100,'Status AI':'PREVIEW_ONLY'},['Baseline dipertahankan.'],{'status':'PREVIEW_ONLY','algorithm':'RandomForest'},[])
dec=[{'NIB':'B%05d'%i,'NOP':'N%d'%i,'label':random.choice(['1','0','']),'sumber_verifikasi':'Dokumen administrasi dan peta asli','record_bpn':i+1,'record_pbb':i+1} for i in range(12)]
rf.report6('/home/claude/render_env/out',dec,pairs,b,p)
print('done')
