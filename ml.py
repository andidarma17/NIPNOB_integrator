"""Optional AI: supervised/weak supervision with strict status gating.
Requires sklearn, numpy, joblib; XGBoost optional. Model files must be trusted.
"""
import csv
import json
import math
from collections import Counter
from pathlib import Path
from .engine import FEATURE_NAMES, FEATURE_VERSIONS, make_candidate_rows, prepare_local
from .logic import normalize_verified_label


def csv_rows(path):
    if not path:return []
    with open(path,encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def feature_version(names_used):
    """'QGIS_PLUGIN_V2' (with name features) when name columns are used."""
    return 'QGIS_PLUGIN_V2' if names_used else 'QGIS_PLUGIN_V1'


def feature_vector(row, features=FEATURE_NAMES):
    vals=[]
    for field in features:
        try:
            v=row.get(field)
            vals.append(float(v) if v not in (None,'','None') else float('nan'))
        except (ValueError,TypeError):vals.append(float('nan'))
    return vals


def geometry_mode(rows):
    """'TITIK' or 'POLIGON' for a set of candidate rows; mixing is refused.

    Rows from older CSVs without ``mode_geom`` are polygon candidates.
    """
    modes={str(r.get('mode_geom') or 'POLIGON').upper() for r in rows}
    if len(modes)>1:
        raise ValueError('Data latih mencampur kandidat PBB poligon dan PBB titik. '
                         'Latih model terpisah untuk masing-masing mode geometri.')
    return modes.pop() if modes else 'POLIGON'


def labels_for_pairs(candidates, historical_csv=None, silver_csv=None,
                     historical_candidates=None, name_silver_weight=None):
    """CSV rows keyed by pair_id/record ids/NIB+NOP; labels GOLD require evidence.

    Tahap 2 pairs (``metode_padu=RULE_NAMA``) are silver only when
    ``name_silver_weight`` is given, as ``SILVER_RULE_NAMA`` with that weight.
    """
    ref={r['pair_id']:r for r in candidates}
    gold=[];silver=[];unresolved=[]
    if silver_csv:
        existing=csv_rows(silver_csv)
        for s in existing:
            if str(s.get('status','')).upper() not in ('LEVEL_1','LEVEL 1','1'):continue
            by_name=str(s.get('metode_padu','')).upper()=='RULE_NAMA'
            # Tahap 2 pairs rest on names: opt-in, with their own (lower) weight.
            if by_name and name_silver_weight is None:continue
            r=ref.get(s.get('pair_id'))
            if r and by_name:
                silver.append(dict(r,label=1,label_source='SILVER_RULE_NAMA',
                                   sample_weight=float(name_silver_weight)))
            elif r:
                silver.append(dict(r,label=1,label_source='SILVER_RULE',sample_weight=.2))
        chosen={r['pair_id'] for r in silver}
        accepted_b={r['record_bpn'] for r in silver}
        accepted_p={r['record_pbb'] for r in silver}
        for r in candidates:
            if r['pair_id'] in chosen:continue
            if ((r['record_bpn'] in accepted_b or r['record_pbb'] in accepted_p)
                and r['overlap_bpn_pct']<20 and r['overlap_pbb_pct']<20 and r['iou']<.10):
                silver.append(dict(r,label=0,label_source='SILVER_CONTRAST',sample_weight=.2))
    for label_source, pair_set in [('CURRENT',candidates),('HISTORICAL',historical_candidates or [])]:
        if label_source=='CURRENT' and not historical_csv:continue
        input_rows=csv_rows(historical_csv) if label_source=='CURRENT' else []
        for entry in input_rows:
            label=normalize_verified_label(entry)
            if label is None:
                unresolved.append(entry)
                continue
            found=None
            if entry.get('pair_id'):
                found=next((r for r in pair_set if str(r['pair_id'])==entry['pair_id']),None)
            elif entry.get('record_bpn') and entry.get('record_pbb'):
                found=next((r for r in pair_set if str(r['record_bpn'])==entry['record_bpn']
                            and str(r['record_pbb'])==entry['record_pbb']),None)
            elif entry.get('NIB') and entry.get('NOP'):
                matching=[r for r in pair_set if str(r['NIB'])==entry['NIB'] and str(r['NOP'])==entry['NOP']]
                if len(matching)==1: found=matching[0]
            if found:
                gold.append(dict(found,label=label,label_source='GOLD_OPERATOR',
                                 sample_weight=1.,sumber_verifikasi=entry['sumber_verifikasi'],
                                 group_id=entry.get('wilayah','') or ('tile_%s_%s' %
                                 (int(float(found['x_bpn'])//250),int(float(found['y_bpn'])//250)))))
            else:
                unresolved.append(entry)
    return silver,gold,unresolved


def add_historical_labeled_features(gold, path, features=FEATURE_NAMES):
    """Use a labelled feature CSV from another geography, if feature schema matches."""
    if not path:return 0
    good=0
    for entry in csv_rows(path):
        label=normalize_verified_label(entry)
        if label is None:continue
        if not all(k in entry for k in features):
            raise ValueError('CSV historis harus memiliki seluruh nama fitur dari Modul 4.')
        gold.append(dict(entry,label=label,label_source='GOLD_HISTORICAL',
                         sample_weight=1.,group_id=entry.get('wilayah','') or ('HIST_TILE_%s_%s' %
                         (int(float(entry.get('x_bpn',0))//250),int(float(entry.get('y_bpn',0))//250))) if entry.get('x_bpn') and entry.get('y_bpn') else 'HISTORIS_UNGROUPED',
                         pair_id=entry.get('pair_id','H'+str(good))))
        good+=1
    return good


def add_historical_pair_labels(gold, historical_candidates, path):
    """Historical geometry pairs + verified operator CSV."""
    if not path:return 0
    rows=csv_rows(path)
    bypair={r['pair_id']:r for r in historical_candidates}
    byrecord={(str(r['record_bpn']),str(r['record_pbb'])):r for r in historical_candidates}
    byids={}
    for r in historical_candidates:byids.setdefault((str(r['NIB']),str(r['NOP'])),[]).append(r)
    seen=set();n=0
    for a in rows:
        label=normalize_verified_label(a)
        if label is None:continue
        candidate=bypair.get(a.get('pair_id'))
        if candidate is None:
            candidate=byrecord.get((str(a.get('record_bpn')),str(a.get('record_pbb'))))
        if candidate is None:
            matches=byids.get((str(a.get('NIB')),str(a.get('NOP'))),[])
            if len(matches)==1:candidate=matches[0]
        if candidate is None:continue
        k=candidate['pair_id']
        if k in seen:raise ValueError('Label historis menduplikasi pasangan: '+k)
        seen.add(k);n+=1
        gold.append(dict(candidate,label=label,label_source='GOLD_HISTORICAL_GEO',
                         sample_weight=1.,group_id=a.get('wilayah','') or 'HIST_'+str(int(candidate['x_bpn']//250))+'_'+str(int(candidate['y_bpn']//250))))
    return n


def split_verified(gold,seed=42):
    from sklearn.model_selection import GroupShuffleSplit
    if len(gold)<100 or min(Counter(int(r['label']) for r in gold).values())<20:
        return None
    groups=[str(r.get('group_id') or 'G_'+str(int(float(r['x_bpn'])//250))+'_'+str(int(float(r['y_bpn'])//250))) for r in gold]
    if len(set(groups))<5:return None
    for trial in range(seed,seed+40):
        try:
            a,b=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=trial).split(gold,groups=groups))
            training=[gold[i] for i in a]; test=[gold[i] for i in b]
            grtrain=[groups[i] for i in a]
            c,d=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=trial+200).split(training,groups=grtrain))
            train=[training[i] for i in c];val=[training[i] for i in d]
        except (ValueError,StopIteration):continue
        if min(len(train),len(val),len(test))<15 or any(len({x['label'] for x in z})<2 for z in (train,val,test)):
            continue
        # Exclude feature source IDs which also occur in held-out split.
        def idset(rows,typ):
            return {(str(r.get('label_source')), str(r.get('record_'+typ))) for r in rows
                    if r.get('record_'+typ) is not None}
        def prune(rows, others):
            bs=idset(others,'bpn');ps=idset(others,'pbb')
            return [r for r in rows if
                    (str(r.get('label_source')),str(r.get('record_bpn'))) not in bs and
                    (str(r.get('label_source')),str(r.get('record_pbb'))) not in ps]
        train=prune(train,val+test);val=prune(val,test)
        if min(len(train),len(val),len(test))>=15 and all(len({x['label'] for x in z})==2 for z in (train,val,test)):
            return train,val,test
    return None


def train_model(silver, gold, output_dir, min_precision=.99, version='QGIS_PLUGIN_V1'):
    """Fit models and evaluate BOTH on independent, spatially separated GOLD splits.

    Threshold 0.90 is an inference policy candidate, not an optimized threshold.
    Selection is VALIDATION-only. Never use testing to tune the selected model.
    ``version`` picks the feature set (``engine.FEATURE_VERSIONS``).
    """
    features=FEATURE_VERSIONS[version]
    import joblib
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from .evaluation import metrics_from_gold, operational_assessment, recommendations, metric_judgements

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    split=split_verified(gold)
    if split:
        train,val,test=split
        # SILVER is permitted ONLY in training; keep entire held-out BPN/NOP out
        # of fit to reduce leakage from multiple possible partners.
        held_b={(str(r.get('label_source')),str(r.get('record_bpn'))) for r in val+test}
        held_p={(str(r.get('label_source')),str(r.get('record_pbb'))) for r in val+test}
        held_pairs={str(r.get('pair_id')) for r in val+test}
        safe_silver=[r for r in silver if (str(r.get('pair_id')) not in held_pairs and
            ('GOLD_OPERATOR',str(r.get('record_bpn'))) not in held_b and
            ('GOLD_OPERATOR',str(r.get('record_pbb'))) not in held_p)]
        fit=train+safe_silver
    else:
        train=[];val=[];test=[]
        fit=list(silver)+list(gold)

    geom_mode=geometry_mode(list(fit)+list(val)+list(test))
    if len({int(r['label']) for r in fit})<2:
        raise ValueError('Training memerlukan contoh positif dan negatif. Tambahkan GOLD operator atau SILVER yang mencakup dua kelas.')

    models={'RandomForest':RandomForestClassifier(n_estimators=160,max_depth=12,
        min_samples_leaf=3,class_weight='balanced',random_state=42,n_jobs=-1)}
    try:
        from xgboost import XGBClassifier
        models['XGBoost']=XGBClassifier(n_estimators=180,max_depth=5,learning_rate=.07,
            subsample=.85,colsample_bytree=.85,random_state=42,n_jobs=2,eval_metric='logloss')
    except ImportError:
        pass

    xx=np.asarray([feature_vector(r,features) for r in fit],dtype=float)
    yy=np.asarray([int(r['label']) for r in fit],dtype=int)
    weight=np.asarray([float(r.get('sample_weight',1)) for r in fit],dtype=float)
    cutoff=.90
    metrics=[]
    detail={}
    all_models={}
    best_name=None
    best_key=None
    for name, estimator in models.items():
        model=Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=False)),
                        ('model',estimator)])
        model.fit(xx,yy,model__sample_weight=weight)
        all_models[name]=model
        per_split={}
        for stage, subset in [('TRAIN', fit),('VALIDATION',val),('TEST',test)]:
            if not subset:continue
            score=model.predict_proba(np.asarray([feature_vector(r,features) for r in subset],dtype=float))[:,1]
            truth=[int(r['label']) for r in subset]
            ev=metrics_from_gold(truth,score,threshold=cutoff,
                include_curves=(stage=='TEST'))
            ev['status_acuan']='GOLD_INDEPENDEN' if stage in ('VALIDATION','TEST') else 'TRAIN_CAMPURAN_GOLD_SILVER_TIDAK_INDEPENDEN'
            per_split[stage]=ev
            metrics.append({'algoritma':name,'split':stage,'status_acuan':ev['status_acuan'],
                **{k:v for k,v in ev.items() if k!='kurva' and k!='confusion_matrix'}})
        # Model selection uses validation ONLY (and does not look at TEST).
        v=per_split.get('VALIDATION')
        if v:
            rank=(int((v.get('precision') or 0)>=min_precision and v.get('prediksi_positif',0)>=3),
                  v.get('recall') or 0, v.get('f1') or 0, -(v.get('fp') or 0))
        else:
            rank=(0,0,0,0)  # equal -> retain deterministic first model
        if best_key is None or rank>best_key:
            best_name=name;best_key=rank
        # Feature importance from native estimator; may be absent for some models.
        native=model.named_steps['model']
        try:
            importance=native.feature_importances_
            feature_importance=sorted([
                {'fitur':str(k),'importance':float(v)}
                for k,v in zip(features, importance)],
                key=lambda x:-x['importance'])
        except (AttributeError,TypeError,ValueError):
            feature_importance=[]
        detail[name]={'split':per_split,'feature_importance':feature_importance}

    selected=all_models[best_name]
    heldout=detail[best_name]['split'].get('TEST')
    validation=detail[best_name]['split'].get('VALIDATION')
    training=detail[best_name]['split'].get('TRAIN')
    status='PREVIEW_ONLY'
    if (heldout and validation and len(gold)>=100 and
        (heldout.get('precision') or 0)>=min_precision and
        (heldout.get('prediksi_positif') or 0)>=10 and best_key[0]):
        status='GOLD_TESTED_REVIEW_REQUIRED'
    # Status is intentionally NOT equivalent to production approval.
    evaluation={
        'judul':'Training dan Testing AI - Klasifikasi Pasangan NIB-NOP',
        'jenis':'BINARY_CLASSIFICATION',
        'evaluasi_gold_tersedia':bool(test),
        'model_terpilih':best_name,
        'metode_pemilihan':'Validation GOLD saja; test GOLD tidak digunakan memilih model',
        'ambang_prediksi':cutoff,
        'target_precision_usulan':min_precision,
        'jumlah_silver':len(silver),
        'jumlah_gold':len(gold),
        'jumlah_fit':len(fit),
        'jumlah_validasi':len(val),
        'jumlah_testing':len(test),
        'status_operasional':operational_assessment(heldout,min_precision),
        'rekomendasi':recommendations(heldout,validation,training,min_precision),
        'penilaian_per_metrik':metric_judgements(heldout,min_precision),
        'models':detail,
        'catatan':[
            'Seluruh nilai testing yang sah hanya berasal dari GOLD independen.',
            'Metrik training bisa tampak tinggi karena termasuk silver labels hasil aturan; bukan estimasi generalisasi.',
            'Precision 100% pada n kecil bukan bukti jaminan tanpa kesalahan. Cek batas bawah Wilson 95%.',
            'ROC-AUC, AP, dan Brier menggunakan skor model, yang belum tentu terkalibrasi sebagai probabilitas.',
            'R2 / MAE / RMSE tidak dipakai sebagai metrik pokok karena tugasnya klasifikasi benar/salah.',
            'Indikator ambang dalam laporan adalah panduan kebijakan, bukan standar ilmiah universal.'
        ]
    }
    modelpath=Path(output_dir)/'model_terpilih.joblib'
    joblib.dump(selected,modelpath)
    (Path(output_dir)/'evaluasi_testing_ai.json').write_text(
        json.dumps(evaluation,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    metadata={'status':status,'feature_version':version,'features':features,
              'mode_geometri_pbb':geom_mode,
              'algorithm':best_name,'n_silver':len(silver),'n_gold':len(gold),
              'n_training':len(fit),'n_validation':len(val),'n_testing':len(test),
              'target_precision':min_precision,
              'holdout':{k:v for k,v in (heldout or {}).items() if k not in ('kurva',)},
              'threshold':cutoff,
              'evaluation_file':'evaluasi_testing_ai.json',
              'note':'AI assistant, NOT legal confirmation. Verify independently before accepting new Level 1.'}
    (Path(output_dir)/'metadata_model.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    return selected,metadata,metrics


def predict(candidates, model_file, metadata_file):
    import joblib
    import numpy as np
    metadata=json.loads(Path(metadata_file).read_text(encoding='utf-8'))
    version=metadata.get('feature_version')
    features=FEATURE_VERSIONS.get(version)
    if features is None or metadata.get('features')!=features:
        raise ValueError('Skema fitur model berbeda dari versi plugin saat ini.')
    if version=='QGIS_PLUGIN_V2' and candidates and all(r.get('skor_nama') is None for r in candidates):
        raise ValueError('Model dilatih dengan fitur nama. Pilih kolom nama BPN dan PBB '
                         'yang berisi nama, atau gunakan model tanpa fitur nama.')
    # Polygon and point candidates encode overlap/area features differently.
    trained=str(metadata.get('mode_geometri_pbb') or 'POLIGON').upper()
    current=geometry_mode(candidates) if candidates else trained
    if trained!=current:
        raise ValueError('Model dilatih untuk PBB %s, tetapi data sekarang PBB %s. '
                         'Gunakan model yang dilatih pada mode geometri yang sama.' %
                         (trained.lower(),current.lower()))
    # Python pickle-based joblib is unsafe from untrusted sources.
    model=joblib.load(model_file)
    matrix=np.asarray([feature_vector(r,features) for r in candidates],dtype=float)
    probs=model.predict_proba(matrix)[:,1] if candidates else []
    for row,score in zip(candidates,probs):row['skor_ai']=float(score)
    return metadata
