"""QGIS-independent evaluation helpers for supervised pair classification.
All test/validation results must be calculated from verified GOLD labels.
"""
import math
from collections import Counter


def _limited(xs, ys, cap=101):
    if len(xs)==0: return {'x': [], 'y': []}
    idx = list(dict.fromkeys(round(i*(len(xs)-1)/(min(cap,len(xs))-1)) for i in range(min(cap,len(xs))))) if len(xs)>1 else [0]
    return {'x': [round(float(xs[i]), 5) for i in idx], 'y': [round(float(ys[i]), 5) for i in idx]}


def wilson_lower(successes, n, z=1.95996398454):
    if n <= 0: return None
    p=successes/n
    return float((p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/(1+z*z/n))


def metrics_from_gold(y, probabilities, threshold=.90, include_curves=True):
    """Binary metrics for independent verified labels; probabilities are uncalibrated model scores."""
    import numpy as np
    from sklearn.metrics import (confusion_matrix, accuracy_score, balanced_accuracy_score,
        precision_score, recall_score, f1_score, roc_auc_score, average_precision_score,
        brier_score_loss, roc_curve, precision_recall_curve)
    from sklearn.calibration import calibration_curve
    yt=np.asarray(y, dtype=int)
    ps=np.asarray(probabilities, dtype=float)
    if len(yt)==0 or len(ps)!=len(yt) or np.any(~np.isfinite(ps)) or np.any((ps<0)|(ps>1)):
        raise ValueError('Label atau skor model tidak valid untuk evaluasi.')
    if set(yt.tolist()) - {0,1}:
        raise ValueError('Label evaluasi wajib hanya 0/1.')
    pred=(ps>=float(threshold)).astype(int)
    tn,fp,fn,tp=map(int,confusion_matrix(yt,pred,labels=[0,1]).ravel())
    n=len(yt); positive=tp+fn; predicted=tp+fp
    prevalence=positive/n
    d={
        'n':n, 'positif':positive, 'negatif':n-positive,
        'prevalensi':float(prevalence), 'threshold':float(threshold),
        'tp':tp, 'tn':tn, 'fp':fp, 'fn':fn,
        'prediksi_positif':predicted,
        'confusion_matrix':[[tn,fp],[fn,tp]],
        'precision':float(precision_score(yt,pred,zero_division=0)) if predicted else None,
        'precision_ci95_bawah':wilson_lower(tp,predicted),
        'recall':float(recall_score(yt,pred,zero_division=0)) if positive else None,
        'f1':float(f1_score(yt,pred,zero_division=0)) if positive else None,
        'accuracy':float(accuracy_score(yt,pred)),
        'balanced_accuracy':float(balanced_accuracy_score(yt,pred)) if len(set(yt.tolist()))==2 else None,
        'specificity':float(tn/(tn+fp)) if tn+fp else None,
        'accuracy_baseline_kelas_mayoritas':max(prevalence,1-prevalence),
        'brier':float(brier_score_loss(yt,ps)),
        'brier_baseline_prevalensi':float(prevalence*(1-prevalence)),
        'auc_roc':None,
        'average_precision':None,
        'kurva':{}
    }
    if len(set(yt.tolist()))==2:
        d['auc_roc']=float(roc_auc_score(yt,ps))
        d['average_precision']=float(average_precision_score(yt,ps))
        if include_curves:
            fpr,tpr,_=roc_curve(yt,ps)
            pre,rec,_=precision_recall_curve(yt,ps)
            frac,mean=calibration_curve(yt,ps,n_bins=8,strategy='quantile')
            d['kurva']={
                'roc': _limited(fpr,tpr),
                'pr': _limited(rec[::-1],pre[::-1]),
                'kalibrasi': _limited(mean,frac,cap=8)
            }
    return d


def threshold_guidance():
    """Policy proposals, NOT scientific/legal universal pass/fail thresholds."""
    return [
        {'nama':'Precision', 'panduan':'Target >=99% di GOLD test; periksa batas bawah CI 95% >=95%',
         'alasan':'Salah menggabungkan NIB-NOP (false positive) paling berisiko.'},
        {'nama':'Recall', 'panduan':'Target awal >=80% dengan precision tetap terpenuhi',
         'alasan':'Mengukur pasangan benar yang berhasil ditemukan; target disesuaikan biaya verifikasi.'},
        {'nama':'F1-score', 'panduan':'Panduan >=90%; tidak cukup sebagai satu-satunya ukuran',
         'alasan':'Menyeimbangkan precision dan recall, dapat menyembunyikan FP.'},
        {'nama':'Accuracy', 'panduan':'Harus melebihi baseline kelas mayoritas',
         'alasan':'Accuracy tinggi dapat menyesatkan bila pasangan benar sedikit.'},
        {'nama':'ROC-AUC', 'panduan':'Indikasi kuat >=0,90; nilai 0,50 mendekati acak',
         'alasan':'Kualitas peringkat semua ambang; PR lebih penting saat imbalance.'},
        {'nama':'Average Precision (AP)', 'panduan':'Harus jauh melebihi prevalensi positif data GOLD test',
         'alasan':'Baseline AP sekitar prevalensi. Ini ringkasan kurva precision-recall, bukan ROC-AUC.'},
        {'nama':'Brier Score', 'panduan':'Lebih kecil lebih baik dan idealnya < baseline prevalensi',
         'alasan':'Mengukur kecocokan skor probabilitas terhadap label; skor mentah mungkin belum terkalibrasi.'},
        {'nama':'Jumlah GOLD', 'panduan':'Uji independen dua kelas, lintas kelompok spasial; target >=50 prediksi positif',
         'alasan':'Precision 100% dari sedikit sampel belum berarti risiko salah rendah.'},
    ]


def operational_assessment(m, target_precision=.99):
    """Advisory evaluation based ONLY on valid independent GOLD test."""
    if not m: return 'BELUM DAPAT DINILAI - tidak ada GOLD testing independen'
    if not m.get('n') or not m.get('positif') or not m.get('negatif'):
        return 'BELUM DAPAT DINILAI - data GOLD testing tidak berisi dua kelas'
    if not m.get('prediksi_positif'):
        return 'BELUM LAYAK - model tidak menerima pasangan positif'
    if (m.get('precision',0)>=target_precision and
        (m.get('precision_ci95_bawah') or 0)>=.95 and
        (m.get('recall') or 0)>=.80 and m['prediksi_positif']>=50):
        return 'LAYAK MASUK PENINJAUAN OPERASIONAL - belum otomatis disetujui'
    return 'PERLU PERBAIKAN / VERIFIKASI TAMBAHAN - target belum terbukti'


def recommendations(test, validation=None, training=None, target_precision=.99):
    if not test:
        return [
            'Belum tersedia GOLD test independen. Lengkapi label 1/0 yang diverifikasi beserta sumber bukti.',
            'Jangan memakai SILVER dari aturan Modul 3 sebagai acuan testing akurasi.',
            'Kumpulkan sampel sulit: overlap di bawah 50%, pergeseran batas, ukuran berbeda, dan hubungan 1:N.',
            'Pisahkan wilayah/kelompok bidang antara training, validation, dan testing untuk menghindari kebocoran.'
        ]
    out=[]
    if not test.get('prediksi_positif'):
        out.append('Tidak ada pasangan diprediksi cocok. Periksa ambang 0,90, cakupan kandidat, dan keterwakilan data training; jangan menurunkan ambang tanpa mengevaluasi precision GOLD.')
    if (test.get('precision') is not None and test['precision']<target_precision) or test.get('fp',0)>0:
        out.append('Ada risiko false match (FP). Telaah pasangan salah, tambah negatif sulit, tingkatkan kualitas fitur bentuk/tetangga, dan optimalkan ambang pada validation GOLD.')
    if test.get('recall') is not None and test['recall']<.8:
        out.append('Recall rendah. Perluas kandidat spasial, periksa kasus bergeser/tanpa irisan, dan tambahkan positif sulit. Evaluasi ulang agar Precision tidak turun.')
    if test.get('precision_ci95_bawah') is None or test['precision_ci95_bawah']<.95:
        out.append('Kepastian Precision masih terbatas. Tingkatkan jumlah kandidat positif pada sampel GOLD independen dari beberapa kelompok/wilayah.')
    if test.get('average_precision') is not None and test['average_precision'] < max(.6,test['prevalensi']+.15):
        out.append('Average Precision belum cukup jauh dari baseline prevalensi. Tambah fitur pemisah dan contoh negatif yang sulit.')
    if test.get('brier') is not None and test['brier']>=test['brier_baseline_prevalensi']:
        out.append('Brier tidak mengungguli prediktor konstan prevalensi. Uji kalibrasi probabilitas pada validation GOLD, jangan menggunakan test untuk kalibrasi.')
    elif test.get('brier') is not None:
        out.append('Periksa kurva kalibrasi sebelum menyebut skor AI sebagai probabilitas kebenaran; Brier yang lebih rendah belum menjamin kalibrasi per kelompok.')
    if training and (training.get('f1') or 0)-(test.get('f1') or 0)>.10:
        out.append('Indikasi overfitting: selisih F1 training-testing >0,10. Sederhanakan model, perkuat regularisasi, tambah GOLD dari wilayah berbeda.')
    if validation and (validation.get('precision') or 0)-(test.get('precision') or 0)>.10:
        out.append('Precision turun tajam dari validation ke testing. Audit distribusi wilayah serta fitur dan pastikan tidak ada leakage.')
    if not out:
        out.append('Hasil cukup menjanjikan; lanjutkan audit manual false positive, evaluasi di wilayah lain, dan pemantauan drift sebelum otomatisasi Level 1.')
    out.append('Status Level 1 tetap tunduk pada kebijakan 1 NIB : 1 NOP, kualitas data, dan verifikasi administrasi; metrik AI bukan bukti hukum.')
    return out


def metric_judgements(test, target_precision=.99):
    """Operator-friendly interpretation using advisory policy, never approval."""
    if not test: return []
    def g(k):return test.get(k)
    out=[]
    checks=[
        ('Precision', g('precision'),'>= %.0f%% (target awal)'%(100*target_precision),
          'DI BAWAH TARGET' if g('precision') is None or g('precision')<target_precision else
          ('SAMPEL BELUM KUAT' if (g('precision_ci95_bawah') or 0)<.95 else 'TARGET TERCAPAI')),
        ('CI95 Precision bawah',g('precision_ci95_bawah'),'>= 95% (keyakinan sampel)',
          'MEMADAI' if (g('precision_ci95_bawah') or 0)>=.95 else 'TAMBAH GOLD'),
        ('Recall',g('recall'),'>= 80% (target awal)',
          'MEMADAI' if (g('recall') or 0)>=.8 else 'PERLU PERBAIKAN'),
        ('F1-score',g('f1'),'>= 90% (panduan)',
          'MEMADAI' if (g('f1') or 0)>=.9 else 'PERLU PERBAIKAN'),
        ('Accuracy',g('accuracy'),'Lebih besar baseline %.1f%%'%(100*g('accuracy_baseline_kelas_mayoritas')),
          'LEBIH BAIK BASELINE' if (g('accuracy') or 0)>g('accuracy_baseline_kelas_mayoritas') else 'PERLU PERBAIKAN'),
        ('ROC-AUC',g('auc_roc'),'>= 0,90 (panduan)',
          'MEMADAI' if (g('auc_roc') or 0)>=.9 else 'PERLU PERBAIKAN'),
        ('Average Precision',g('average_precision'),'Di atas prevalensi %.1f%%'%(100*g('prevalensi')),
          'DI ATAS BASELINE' if (g('average_precision') or 0)>g('prevalensi') else 'PERLU PERBAIKAN'),
        ('Brier Score',g('brier'),'Lebih kecil baseline %.3f'%g('brier_baseline_prevalensi'),
          'LEBIH BAIK BASELINE' if g('brier') is not None and g('brier')<g('brier_baseline_prevalensi') else 'PERLU PERBAIKAN'),
    ]
    for title,v,ref,status in checks:
        display=('N/A' if v is None else ('%.3f'%v if title in ('ROC-AUC','Average Precision','Brier Score') else '%.1f%%'%(100*v)))
        out.append({'metrik':title,'nilai':display,'patokan':ref,'interpretasi':status})
    return out
