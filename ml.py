"""Optional AI: supervised/weak supervision with strict status gating.
Requires sklearn, numpy, joblib; XGBoost optional. Model files must be trusted.
"""
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from .engine import FEATURE_NAMES, FEATURE_VERSIONS, make_candidate_rows, prepare_local
from .logic import normalize_verified_label


def csv_rows(path, required_columns=()):
    if not path:return []
    if Path(path).suffix.lower()=='.zip':
        from .ai_matching import _csv_from_zip,_rows_from_csv
        rows=_rows_from_csv(_csv_from_zip(Path(path).read_bytes()))
        if not rows:
            raise ValueError('CSV dalam arsip Modul 3 tidak memiliki baris data.')
        missing=set(required_columns)-set(rows[0])
        if missing:
            raise ValueError('CSV Modul 3 tidak memiliki kolom wajib: '+', '.join(sorted(missing)))
        return [{str(k).strip():v.strip() if isinstance(v,str) else v
                 for k,v in row.items()} for row in rows]
    with open(path,encoding='utf-8-sig',newline='') as f:
        header=f.readline()
        # Some Indonesian spreadsheet exports use semicolons, while NOP may
        # itself contain a decimal comma following destructive Excel casting.
        delimiter=';' if header.count(';')>header.count(',') else ','
        f.seek(0)
        reader=csv.DictReader(f,delimiter=delimiter)
        fields=[str(v).strip() for v in (reader.fieldnames or []) if v is not None]
        if len(fields)!=len(set(fields)):
            raise ValueError('CSV mempunyai nama kolom ganda: '+str(path))
        missing=set(required_columns)-set(fields)
        if missing:
            raise ValueError('CSV %s tidak memiliki kolom wajib: %s. Periksa delimiter dan skema data.' %
                             (Path(path).name,', '.join(sorted(missing))))
        if not fields:
            raise ValueError('CSV tanpa header: '+str(path))
        result=[]
        for line,row in enumerate(reader,2):
            if None in row:
                raise ValueError('CSV %s baris %d memiliki jumlah kolom berlebih; periksa delimiter.' %
                                 (Path(path).name,line))
            result.append({str(k).strip():v.strip() if isinstance(v,str) else v
                           for k,v in row.items()})
        return result


def _candidate_lookup(candidates):
    by_pair={};by_records={};by_ids=defaultdict(list)
    for row in candidates:
        by_pair[str(row['pair_id'])]=row
        by_records[(str(row['record_bpn']),str(row['record_pbb']))]=row
        by_ids[(str(row.get('NIB','')).strip(),str(row.get('NOP','')).strip())].append(row)
    return by_pair,by_records,by_ids


def resolve_verified_pair(entry, lookups):
    """Find a verified pair while checking IDs, even if record indexes changed.

    NIB/NOP win over positional indexes when they identify exactly one pair;
    a stale pair_id is never permitted to point to contradictory IDs.
    """
    by_pair,by_records,by_ids=lookups
    nib=str(entry.get('NIB') or '').strip()
    nop=str(entry.get('NOP') or '').strip()
    if any(ch in nop.upper() for ch in ('E+', 'E-', ',')):
        return None,'NOP_RUSAK_NOTASI_ILMIAH'
    if nib and nop:
        matches=by_ids.get((nib,nop),[])
        if len(matches)==1:
            return matches[0],'NIB_NOP_UNIK'
        if len(matches)>1:
            # Rare non-unique IDs need evidence from matching record numbers.
            known=by_pair.get(str(entry.get('pair_id') or ''))
            if known in matches:return known,'NIB_NOP_DAN_PAIR_ID'
            known=by_records.get((str(entry.get('record_bpn')),str(entry.get('record_pbb'))))
            if known in matches:return known,'NIB_NOP_DAN_RECORD'
            return None,'PASANGAN_NIB_NOP_TIDAK_UNIK'
    found=by_pair.get(str(entry.get('pair_id') or ''))
    if found is None:
        found=by_records.get((str(entry.get('record_bpn')),str(entry.get('record_pbb'))))
    if found is None:return None,'PASANGAN_TIDAK_DITEMUKAN_DALAM_RADIUS'
    if nib and str(found.get('NIB','')).strip()!=nib:
        return None,'NIB_BERBEDA_DARI_KANDIDAT'
    if nop and str(found.get('NOP','')).strip()!=nop:
        return None,'NOP_BERBEDA_DARI_KANDIDAT'
    return found,'PAIR_ID_ATAU_RECORD_TERVALIDASI'


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
    lookups=_candidate_lookup(candidates)
    ref=lookups[0]
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
        input_rows=csv_rows(historical_csv,('label','status_verifikasi','sumber_verifikasi')) if label_source=='CURRENT' else []
        seen_gold=set()
        for entry in input_rows:
            label=normalize_verified_label(entry)
            if label is None:
                unresolved.append(dict(entry,alasan_penolakan='LABEL_STATUS_ATAU_BUKTI_TIDAK_VALID'))
                continue
            found,method=resolve_verified_pair(entry,lookups)
            if found:
                if found['pair_id'] in seen_gold:
                    raise ValueError('GOLD mempunyai label ganda untuk pasangan '+found['pair_id'])
                seen_gold.add(found['pair_id'])
                gold.append(dict(found,label=label,label_source='GOLD_OPERATOR',
                                 sample_weight=1.,sumber_verifikasi=entry['sumber_verifikasi'],
                                 metode_pencocokan_gold=method,
                                 group_id=entry.get('wilayah','') or ('tile_%s_%s' %
                                 (int(float(found['x_bpn'])//250),int(float(found['y_bpn'])//250)))))
            else:
                unresolved.append(dict(entry,alasan_penolakan=method))
    return silver,gold,unresolved


def add_historical_labeled_features(gold, path, features=FEATURE_NAMES):
    """Use a labelled feature CSV from another geography, if feature schema matches."""
    if not path:return 0
    good=0
    rows=csv_rows(path,('label','status_verifikasi','sumber_verifikasi',*features))
    for row_number,entry in enumerate(rows,2):
        label=normalize_verified_label(entry)
        if label is None:continue
        for key in features:
            val=entry.get(key)
            if val in ('',None,'None'):continue
            try:
                if not math.isfinite(float(val)):raise ValueError()
            except (TypeError,ValueError):
                raise ValueError('Fitur %s di baris %d CSV GOLD bukan angka valid: %s. '
                                 'Hitung ulang fitur dari geometri, jangan dari angka yang berubah di Excel.' %
                                 (key,row_number,str(val)[:30]))
        gold.append(dict(entry,label=label,label_source='GOLD_HISTORICAL',
                         sample_weight=1.,group_id=entry.get('wilayah','') or ('HIST_TILE_%s_%s' %
                         (int(float(entry.get('x_bpn',0))//250),int(float(entry.get('y_bpn',0))//250))) if entry.get('x_bpn') and entry.get('y_bpn') else 'HISTORIS_UNGROUPED',
                         pair_id=entry.get('pair_id','H'+str(good))))
        good+=1
    if rows and not good:
        raise ValueError('CSV fitur GOLD berisi %d baris tetapi nol label lolos verifikasi. '
                         'Periksa status_verifikasi dan sumber_verifikasi.' % len(rows))
    return good


def add_historical_pair_labels(gold, historical_candidates, path):
    """Historical geometry pairs + verified operator CSV."""
    if not path:return 0
    rows=csv_rows(path,('label','status_verifikasi','sumber_verifikasi'))
    lookups=_candidate_lookup(historical_candidates)
    seen=set();n=0
    for a in rows:
        label=normalize_verified_label(a)
        if label is None:continue
        candidate,_=resolve_verified_pair(a,lookups)
        if candidate is None:continue
        k=candidate['pair_id']
        if k in seen:raise ValueError('Label historis menduplikasi pasangan: '+k)
        seen.add(k);n+=1
        gold.append(dict(candidate,label=label,label_source='GOLD_HISTORICAL_GEO',
                         sample_weight=1.,group_id=a.get('wilayah','') or 'HIST_'+str(int(candidate['x_bpn']//250))+'_'+str(int(candidate['y_bpn']//250))))
    if rows and not n:
        raise ValueError('CSV pasangan historis tidak menghasilkan GOLD. '
                         'Periksa sumber label, NIB/NOP asli, dan radius kandidat.')
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


def _exclude_silver_near_gold_holdout(silver, holdout):
    """Avoid direct ID and tile leakage from an independently held-out GOLD set.

    Historical GOLD record indices may refer to a small GeoJSON subset rather
    than the current BPN/PBB layers. Their NIB/NOP and tile coordinates are
    therefore also checked, not just their local record indices.
    """
    if not holdout:
        return list(silver)
    blocked_pairs={str(r.get('pair_id')) for r in holdout}
    blocked_b={(str(r.get('label_source')),str(r.get('record_bpn'))) for r in holdout}
    blocked_p={(str(r.get('label_source')),str(r.get('record_pbb'))) for r in holdout}
    blocked_nib={str(r.get('NIB')).strip() for r in holdout if r.get('NIB') not in ('',None)}
    blocked_nop={str(r.get('NOP')).strip() for r in holdout if r.get('NOP') not in ('',None)}
    blocked_tiles={str(r.get('group_id')) for r in holdout if str(r.get('group_id','')).startswith('tile_')}
    safe=[]
    for row in silver:
        if str(row.get('pair_id')) in blocked_pairs:
            continue
        if (('GOLD_OPERATOR',str(row.get('record_bpn'))) in blocked_b or
                ('GOLD_OPERATOR',str(row.get('record_pbb'))) in blocked_p):
            continue
        if (str(row.get('NIB','')).strip() in blocked_nib or
                str(row.get('NOP','')).strip() in blocked_nop):
            continue
        try:
            tile='tile_%d_%d'%(math.floor(float(row['x_bpn'])/250),
                                math.floor(float(row['y_bpn'])/250))
            if tile in blocked_tiles:
                continue
        except (ValueError,TypeError,KeyError,OverflowError):
            pass
        safe.append(row)
    return safe


def _balance_silver_weight(silver, gold_train):
    """Cap *aggregate* SILVER influence per class at GOLD training influence.

    A nominal per-row 0.2 versus 1.0 does not protect a small GOLD dataset
    against tens of thousands of weak labels.
    """
    if not silver or not gold_train:
        return list(silver)
    result=[dict(row) for row in silver]
    for label in (0,1):
        gold_total=sum(float(row.get('sample_weight',1)) for row in gold_train
                       if int(row['label'])==label)
        silver_total=sum(float(row.get('sample_weight',.2)) for row in result
                         if int(row['label'])==label)
        factor=min(1., gold_total/silver_total) if silver_total else 1.
        for row in result:
            if int(row['label'])==label:
                row['sample_weight']=float(row.get('sample_weight',.2))*factor
    return result


def train_model(silver, gold, output_dir, min_precision=.99, version='QGIS_PLUGIN_V1',
                training_mode=None):
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

    from .ai_matching import training_mode as resolve_training_mode
    requested=training_mode or resolve_training_mode(bool(silver),bool(gold))
    if requested not in ('SILVER_ONLY','GOLD_ONLY','SILVER_GOLD'):
        raise ValueError('Mode training AI tidak dikenal.')
    if requested=='SILVER_ONLY' and gold:
        raise ValueError('Mode SILVER_ONLY tidak boleh mencampur GOLD.')
    if requested=='GOLD_ONLY' and silver:
        raise ValueError('Mode GOLD_ONLY tidak boleh mencampur SILVER.')
    if requested=='SILVER_GOLD' and (not silver or not gold):
        raise ValueError('Mode SILVER_GOLD memerlukan kedua sumber data.')
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    n_groups=len({str(r.get('group_id') or 'TANPA_GRUP') for r in gold})
    split=split_verified(gold)
    if split:
        train,val,test=split
        # Spatial GOLD holdout is truly independent of SILVER, including the
        # historical-GeoJSON case whose record indices differ from current data.
        safe_silver=_exclude_silver_near_gold_holdout(silver,val+test)
        fit=train+_balance_silver_weight(safe_silver,train)
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
    effective_silver_weight=sum(float(row.get('sample_weight',.2)) for row in fit
                                if str(row.get('label_source','')).startswith('SILVER'))
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
        'mode_training':requested,
        'bobot_efektif_silver_training':effective_silver_weight,
        'jumlah_grup_spasial_gold':n_groups,
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
            'Indikator ambang dalam laporan adalah panduan kebijakan, bukan standar ilmiah universal.',
            ('GOLD hanya mencakup %d grup spasial; uji ini bukan jaminan generalisasi '
              'ke wilayah lain.' % n_groups)
        ]
    }
    modelpath=Path(output_dir)/'model_terpilih.joblib'
    joblib.dump(selected,modelpath)
    (Path(output_dir)/'evaluasi_testing_ai.json').write_text(
        json.dumps(evaluation,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    metadata={'status':status,'feature_version':version,'features':features,
              'mode_geometri_pbb':geom_mode,
              'algorithm':best_name,'n_silver':len(silver),'n_gold':len(gold),
              'training_mode':requested,
              'effective_silver_weight':effective_silver_weight,
              'n_gold_groups':n_groups,
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
