import sys, random
sys.path.insert(0,'/home/claude/render_env/shim'); sys.path.insert(0,'/home/claude/render_env/pkg')
import os; os.environ['QT_QPA_PLATFORM']='offscreen'
from PyQt5.QtGui import QGuiApplication
app=QGuiApplication(sys.argv)
from nibnop_integrator import ai_pdf
from nibnop_integrator.evaluation import recommendations, metric_judgements, operational_assessment
FEATURE_NAMES=['overlap_bpn_pct','overlap_pbb_pct','iou','kesamaan_luas_geom','kesamaan_luas_tulis','deviasi_luas_bpn','deviasi_luas_pbb','jarak_centroid','jarak_geometri','kesamaan_bentuk','bpn_luas_kosong','pbb_luas_kosong','bpn_invalid','pbb_invalid','bpn_internal_overlap','pbb_internal_overlap','jumlah_calon_radius_bpn','jumlah_calon_radius_pbb']
random.seed(1)
def curve(n=30,conc=2):
    xs=[i/(n-1) for i in range(n)];return {'x':xs,'y':[x**(1/conc) for x in xs]}
def m(n,prec,rec):
    tp=int(rec*40);fp=int((1-prec)*tp);fn=40-tp;tn=n-40-fp
    return {'n':n,'positif':40,'negatif':n-40,'prevalensi':40/n,'tp':tp,'fp':fp,'fn':fn,'tn':tn,'confusion_matrix':[[tn,fp],[fn,tp]],
     'prediksi_positif':tp+fp,'precision':prec,'precision_ci95_bawah':prec-.05,'recall':rec,'f1':.9,'accuracy':.95,'accuracy_baseline_kelas_mayoritas':.8,
     'auc_roc':.97,'average_precision':.93,'brier':.05,'brier_baseline_prevalensi':.16,'kurva':{'roc':curve(30,3),'pr':{'x':[i/29 for i in range(30)],'y':[1-(i/29)**3*.3 for i in range(30)]},'kalibrasi':{'x':[.1,.3,.5,.7,.9],'y':[.05,.25,.55,.75,.95]}}}
def model():
    return {'split':{'TRAIN':m(300,.99,.95),'VALIDATION':m(100,.97,.9),'TEST':m(100,.96,.85)},
      'feature_importance':sorted([{'fitur':f,'importance':random.random()} for f in FEATURE_NAMES],key=lambda x:-x['importance'])}
t=model()['split']['TEST']
ev={'model_terpilih':'RandomForest','evaluasi_gold_tersedia':True,'jumlah_gold':500,'jumlah_silver':800,'jumlah_fit':900,'jumlah_validasi':100,'jumlah_testing':100,
 'ambang_prediksi':.9,'target_precision_usulan':.99,'status_operasional':operational_assessment(t),'rekomendasi':recommendations(t),'penilaian_per_metrik':metric_judgements(t),
 'models':{'RandomForest':model(),'XGBoost':model()},'catatan':['Catatan satu.','Catatan dua.']}
ai_pdf.make_training_report('/home/claude/render_env/out',ev)
