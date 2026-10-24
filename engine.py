"""Native PyQGIS implementation of QA and deterministic matching.

No geopandas/shapely dependency; polygon measurement requires metric projected CRS.
Never mutates operator's source layers.
"""
from collections import Counter, defaultdict
from math import hypot, sqrt, pi
from qgis.core import (QgsFeature, QgsField, QgsSpatialIndex, QgsVectorLayer,
                       QgsGeometry, QgsCoordinateTransform, QgsProject,
                       QgsWkbTypes, QgsUnitTypes)
from .compat import field_type
from .logic import (empty, ident, number, dev_percent, similarity, gate_pair,
                    name_similarity, name_status, match_strength, spatial_score,
                    combined_score, select_stage2, STAGE2_DEFAULTS)

QA_COLUMNS = {'geom_kosong','geom_invalid','geom_fixed','overlap','bid_tambah',
              'selisih_luas','persen_selisihL','id_kosong','id_duplikat','luas_flag',
              'level','kode_l2','alasan_l2','calon_n','calon_id', 'skor_ai',
              'metode_padu','nop_padanan','skor_nama','valid_nama','kekuatan',
              'calon_nama','skor_gabungan'}

# Two PBB points closer than this (m) are flagged as coincident ("titik ganda").
POINT_COINCIDENT_TOL = .01


def is_point_geom(g):
    """True for (multi)point geometries; PBB may be delivered as points only."""
    return (g is not None and not g.isNull() and not g.isEmpty() and
            QgsWkbTypes.geometryType(g.wkbType())==QgsWkbTypes.PointGeometry)


def is_point_layer(layer):
    return layer is not None and layer.geometryType()==QgsWkbTypes.PointGeometry


def point_mode(records):
    """PBB records are points (titik NOP) rather than parcel polygons."""
    return any(is_point_geom(r['geom']) for r in records)


def output_geom_type(layer):
    return 'MultiPoint' if is_point_layer(layer) else 'MultiPolygon'


def metric_crs(layer, allow_point=False):
    if not layer or not layer.isValid():
        raise ValueError('Layer tidak valid.')
    if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
        if not allow_point:
            raise ValueError('Layer %s harus bertipe poligon.' % layer.name())
        if layer.geometryType() != QgsWkbTypes.PointGeometry:
            raise ValueError('Layer %s harus bertipe poligon atau titik.' % layer.name())
    if not layer.crs().isValid():
        raise ValueError('CRS tidak diketahui; atur CRS layer terlebih dahulu.')
    if layer.crs().mapUnits() != QgsUnitTypes.DistanceMeters:
        raise ValueError('Gunakan CRS proyeksi dengan satuan meter; data geografis derajat tidak dapat langsung dihitung m².')


def read(layer, strip_old=True, transform=None, allow_point=False):
    """Returns list of independent records with QGIS-native geometries.

    ``allow_point`` is used for PBB layers, whose NOP may only exist as points.
    """
    metric_crs(layer, allow_point)
    result=[]
    for order, feature in enumerate(layer.getFeatures(), 1):
        attrs={field.name(): feature[field.name()] for field in layer.fields()
               if not (strip_old and field.name() in QA_COLUMNS)}
        geom=QgsGeometry(feature.geometry())
        if transform and not geom.isNull() and not geom.isEmpty():
            rc=geom.transform(transform)
            if rc not in (0, None):
                raise ValueError('Gagal transformasi CRS record '+str(order))
        result.append({'idx':order, 'fid':feature.id(), 'a':attrs, 'geom':geom})
    return result


def read_pair(bpn_layer,pbb_layer,reproject=False,allow_point=True):
    """BPN must be polygons; PBB may be polygons or points (mode titik)."""
    metric_crs(bpn_layer); metric_crs(pbb_layer, allow_point)
    same=bpn_layer.crs()==pbb_layer.crs()
    if not same and not reproject:
        raise ValueError('CRS berbeda: %s vs %s. Centang opsi reproyeksi PBB.' %
                         (bpn_layer.crs().authid(),pbb_layer.crs().authid()))
    trans=None if same else QgsCoordinateTransform(pbb_layer.crs(),bpn_layer.crs(),
                                                    QgsProject.instance())
    logs=(['CRS sama: '+bpn_layer.crs().authid()] if same else
          ['PBB ditransformasi ke CRS BPN: '+bpn_layer.crs().authid()])
    if is_point_layer(pbb_layer):
        logs.append('PBB berupa titik: pemaduan memakai posisi titik di dalam bidang BPN '
                    '(bukan overlap luas), diperkuat validasi nama bila kolom nama dipilih.')
    return (read(bpn_layer), read(pbb_layer,transform=trans,allow_point=allow_point),
            logs)


def polygon_only(g):
    if g.isNull() or g.isEmpty():return g
    if QgsWkbTypes.geometryType(g.wkbType())==QgsWkbTypes.PolygonGeometry:return g
    try:
        geoms=[x for x in g.asGeometryCollection()
               if not x.isNull() and not x.isEmpty() and
                  QgsWkbTypes.geometryType(x.wkbType())==QgsWkbTypes.PolygonGeometry]
        return QgsGeometry.unaryUnion(geoms) if geoms else QgsGeometry()
    except Exception:
        return QgsGeometry()


def fix_geometry(records):
    notes=[]
    for r in records:
        geom=r['geom']; isnull=geom.isNull() or geom.isEmpty()
        invalid=0;fixed=0
        if not isnull:
            invalid=int(not geom.isGeosValid())
            if invalid and is_point_geom(geom):
                # A point cannot be "made valid" into a parcel; report only.
                notes.append('Geometri titik invalid: record %s' % r['idx'])
            elif invalid:
                try:
                    fixed_geom=polygon_only(geom.makeValid())
                    if (fixed_geom.isNull() or fixed_geom.isEmpty() or
                            not fixed_geom.isGeosValid()):
                        notes.append('Geometri gagal diperbaiki: record %s' % r['idx'])
                    else:
                        r['geom']=fixed_geom
                        fixed=1
                except Exception as e:
                    notes.append('Gagal fix geometry #%s: %s' % (r['idx'],e))
        r['a'].update(geom_kosong=int(isnull),geom_invalid=invalid,geom_fixed=fixed)
    return notes


def spatial_index(records):
    idx=QgsSpatialIndex()
    ref={}
    for r in records:
        g=r['geom']
        if g.isNull() or g.isEmpty():continue
        tmp=QgsFeature()
        tmp.setId(r['idx'])
        tmp.setGeometry(g)
        idx.addFeature(tmp)
        ref[r['idx']]=r
    return idx,ref


def internal_overlap(records,min_area=.01,point_tol=POINT_COINCIDENT_TOL):
    """Polygons: irisan > min_area. Points: coincident within point_tol m."""
    index,by_id=spatial_index(records)
    logs=[]
    for r in records:r['a']['overlap']=0
    for a in records:
        geom=a['geom']
        if geom.isNull() or geom.isEmpty():continue
        a_point=is_point_geom(geom)
        bounds=geom.boundingBox()
        if a_point:bounds.grow(point_tol)
        for j in index.intersects(bounds):
            if j<=a['idx']:continue
            b=by_id[j]
            if a_point or is_point_geom(b['geom']):
                if a_point and is_point_geom(b['geom']):
                    sep=geom.distance(b['geom'])
                    if sep<=point_tol:
                        a['a']['overlap']=1;b['a']['overlap']=1
                        logs.append({'record_a':a['idx'],'record_b':b['idx'],
                                     'luas_irisan_m2':0.,'jarak_m':round(sep,3),
                                     'jenis':'TITIK_BERIMPIT'})
                continue
            if not geom.intersects(b['geom']):continue
            inter=geom.intersection(b['geom'])
            ar=inter.area() if not inter.isNull() else 0
            if ar>min_area:
                a['a']['overlap']=1;b['a']['overlap']=1
                logs.append({'record_a':a['idx'],'record_b':b['idx'],'luas_irisan_m2':round(ar,3)})
    return logs


def enclosed_gaps(records,min_gap=1.,max_gaps=2500):
    """Extract actual interior holes of polygonal union; exterior voids excluded."""
    geoms=[r['geom'] for r in records if not r['geom'].isNull() and not r['geom'].isEmpty()]
    if not geoms:return [],[]
    union=polygon_only(QgsGeometry.unaryUnion(geoms))
    if union.isNull() or union.isEmpty():return [],[]
    polys=union.asMultiPolygon() if union.isMultipart() else [union.asPolygon()]
    gaps=[];allholes=[]
    for polygon in polys:
        for ring in polygon[1:]:
            if len(ring)<4: continue
            geo=QgsGeometry.fromPolygonXY([ring])
            area=geo.area()
            info={'gap_id':'GAP%05d'% (len(allholes)+1),'luas_m2':round(area,4),
                  'ditambahkan':int(area>=min_gap)}
            allholes.append(info)
            if area>=min_gap:gaps.append((geo,info))
            if len(allholes)>max_gaps:
                raise ValueError('Terlalu banyak celah tertutup. Periksa geometri/topologi lebih dulu.')
    return gaps,allholes


def spatial_audit(records, id_field, area_field, min_area=.01, min_gap=1., add_gaps=False):
    records=[{'idx':r['idx'],'fid':r['fid'],'a':dict(r['a']),
              'geom':QgsGeometry(r['geom'])} for r in records]
    notes=fix_geometry(records)
    overlaps=internal_overlap(records,min_area)
    gaps, holes=enclosed_gaps(records,min_gap) if add_gaps else ([],[])
    for r in records:
        g=r['geom']; a=r['a']
        area=None if g.isNull() or g.isEmpty() or is_point_geom(g) else g.area()
        written=number(a.get(area_field))
        a['bid_tambah']=int(a.get('bid_tambah',0) or 0)
        a['selisih_luas']=None if written is None or area is None else area-written
        a['persen_selisihL']=None if written is None or written<=0 or area is None else (area-written)/written*100.
    if add_gaps:
        for geom,entry in gaps:
            attrs={id_field:'',area_field:None,'bid_tambah':1,
                   'geom_kosong':0,'geom_invalid':0,'geom_fixed':0,
                   'overlap':0,'selisih_luas':None,'persen_selisihL':None,
                   'gap_id':entry['gap_id']}
            records.append({'idx':len(records)+1,'fid':-1,'a':attrs,'geom':geom})
    return records,overlaps,holes,notes


def columns(source_layer, extra=None, drop_old=True):
    result=[]; names=set()
    for field in source_layer.fields():
        if drop_old and field.name() in QA_COLUMNS:continue
        result.append((field.name(), field.type()))
        names.add(field.name())
    for name,typ in (extra or []):
        if name not in names:
            result.append((name,field_type(typ)))
            names.add(name)
    return result


def layer_from_records(records, crs, schema, name='Keluaran', geom_type=None):
    """geom_type 'MultiPolygon'/'MultiPoint'; detected from records when None."""
    if geom_type is None:
        geom_type='MultiPoint' if point_mode(records) else 'MultiPolygon'
    # Set the CRS object directly: authid() is empty for custom CRS (e.g. TM-3 .prj).
    lyr=QgsVectorLayer(geom_type, name, 'memory')
    lyr.setCrs(crs)
    if not lyr.isValid():raise RuntimeError('Gagal membuat layer hasil.')
    lyr.dataProvider().addAttributes([QgsField(k,t) for k,t in schema]);lyr.updateFields()
    feats=[]
    for row in records:
        feature=QgsFeature(lyr.fields())
        g=QgsGeometry(row['geom'])
        if not g.isNull() and not g.isEmpty():
            if not g.isMultipart():g.convertToMultiType()
            feature.setGeometry(g)
        feature.setAttributes([row['a'].get(name) for name,_ in schema])
        feats.append(feature)
    if feats:
        ok,res=lyr.dataProvider().addFeatures(feats)
        if not ok:raise RuntimeError('Gagal menambahkan feature keluaran: '+str(res)[:240])
    lyr.updateExtents()
    return lyr


def qa_attribute(rows, id_field, area_field, min_area=5,max_area=10000):
    counts=Counter(ident(r['a'].get(id_field)) for r in rows if ident(r['a'].get(id_field)))
    detail=[];dups=[];areas=[];empty_col=Counter();empty_cells=0
    for r in rows:
        a=r['a'];idval=ident(a.get(id_field));v=number(a.get(area_field))
        blanks=[k for k,value in a.items() if empty(value)]
        empty_col.update(blanks);empty_cells+=len(blanks)
        flags=[]
        if v is None:flags.append('LUAS_KOSONG_ATAU_NONNUMERIK')
        elif v<=0:flags.append('LUAS_NOL_NEGATIF')
        elif v<min_area:flags.append('LUAS_KECIL')
        elif v>max_area:flags.append('LUAS_BESAR')
        a['id_kosong']=int(not bool(idval))
        a['id_duplikat']=int(bool(idval) and counts[idval]>1)
        a['luas_flag']=';'.join(flags)
        if blanks:detail.append({'record':r['idx'],'id':idval,'kolom_kosong':';'.join(blanks)})
        if a['id_duplikat']:dups.append({'record':r['idx'],'id':idval,'jumlah':counts[idval]})
        if flags:areas.append({'record':r['idx'],'id':idval,'luas':a.get(area_field),'masalah':a['luas_flag']})
    stat={'jumlah_record':len(rows),'identitas_kosong':sum(r['a']['id_kosong'] for r in rows),
          'record_duplikat':len(dups),'jumlah_identitas_duplikat':len({e['id'] for e in dups}),
          'record_dengan_atribut_kosong':len(detail),'record_luas_bermasalah':len(areas),
          'jumlah_sel_kosong':empty_cells}
    fieldrows=[{'nama_kolom':key,'jumlah_kosong':count,
                'persentase':round(100*count/max(1,len(rows)),2)} for key,count in sorted(empty_col.items())]
    return stat,{'atribut_kosong.csv':detail,'duplikat.csv':dups,'luas_bermasalah.csv':areas,
                 'per_kolom_kosong.csv':fieldrows}


def _is_strong_near(v, area_tol):
    """Candidate that physically links both records (irisan / titik di dalam)."""
    return v['irisan_m2']>area_tol or v.get('titik_di_dalam')==1


def candidate_rank(c):
    """Ordering for calon_id: largest irisan, point inside, nearest, best name."""
    return (-(c.get('irisan_m2') or 0), -(c.get('titik_di_dalam') or 0),
            c.get('jarak_geometri') or 0, -(c.get('skor_nama') or 0))


def make_candidate_rows(b,p,area_tol=.01,radius=0.,max_near=8,point_tol=0.,
                        name_thresholds=(90.,60.)):
    """Return feature vectors shared by Modules 3,4,5 and studio.
    record indexes are stable 1-based at the moment of the run.

    PBB may be polygons or points. For a point the polygon-only measures are
    replaced by explicit point measures (documented in DOMAIN_RULES.md):
    ``overlap_*_pct`` = 100 when the point lies in the BPN parcel else 0,
    ``iou`` = 0, ``kesamaan_luas_geom`` = luas tertulis PBB vs luas geometri BPN,
    ``deviasi_luas_pbb`` = deviasi luas tertulis PBB terhadap luas geometri BPN,
    ``kesamaan_bentuk`` = kosong. With radius 0 a point outside the parcel is
    still kept as a (non-qualifying) candidate up to ``point_tol`` metres.
    Name similarity (``skor_nama``/``valid_nama``) is added when ``prepare_local``
    received name fields; it is NOT one of the 18 model features.
    """
    index, lookup=spatial_index(p)
    candidates=[]; per_b=defaultdict(list);per_p=defaultdict(list)
    name_ok,name_partial=name_thresholds
    for rb in b:
        gb=rb['geom'];a=rb['a'];
        if gb.isNull() or gb.isEmpty() or gb.area()<=0:continue
        bounds=gb.boundingBox()
        bounds.grow(max(0.,radius,point_tol))
        ids=index.intersects(bounds)
        choices=[]
        area_b=gb.area()
        ab=number(a.get('_area_field_value'))
        center_b=gb.centroid().asPoint()
        for j in ids:
            rp=lookup[j];gp=rp['geom']
            ap=number(rp['a'].get('_area_field_value'))
            if is_point_geom(gp):
                inside=gb.intersects(gp)
                sep=0. if inside else gb.distance(gp)
                limit=radius if radius>0 else point_tol
                if not inside and sep>limit:continue
                center_p=gp.centroid().asPoint()
                vals={'irisan_m2':0.,'overlap_bpn_pct':100. if inside else 0.,
                      'overlap_pbb_pct':100. if inside else 0.,'iou':0.,
                      'area_bpn_geom':area_b,'area_pbb_geom':None,
                      'kesamaan_luas_geom':similarity(ap,area_b),
                      'deviasi_luas_pbb':dev_percent(ap,area_b),
                      'jarak_geometri':sep,'kesamaan_bentuk':None,
                      'mode_geom':'TITIK','titik_di_dalam':int(inside)}
            else:
                area_p=gp.area()
                if area_p<=0:continue
                inter=gb.intersection(gp) if gb.intersects(gp) else QgsGeometry()
                intersection=0 if inter.isNull() or inter.isEmpty() else inter.area()
                if radius<=0 and intersection<=area_tol:continue
                # distance 0 for intersecting; QGIS geometries projected in metres
                sep=gb.distance(gp) if intersection<=area_tol else 0.
                if radius>0 and intersection<=area_tol and sep>radius:continue
                center_p=gp.centroid().asPoint()
                perimeter_b=max(gb.length(),1e-7);perimeter_p=max(gp.length(),1e-7)
                ratio_shapes=(min((4*pi*area_b)/(perimeter_b**2), (4*pi*area_p)/(perimeter_p**2)) /
                              max((4*pi*area_b)/(perimeter_b**2), (4*pi*area_p)/(perimeter_p**2),1e-9))
                vals={'irisan_m2':intersection,'overlap_bpn_pct':100*intersection/area_b,
                      'overlap_pbb_pct':100*intersection/area_p,
                      'iou':intersection/(area_b+area_p-intersection) if (area_b+area_p-intersection)>0 else 0,
                      'area_bpn_geom':area_b,'area_pbb_geom':area_p,
                      'kesamaan_luas_geom':100*min(area_b,area_p)/max(area_b,area_p),
                      'deviasi_luas_pbb':dev_percent(ap,area_p),
                      'jarak_geometri':sep,'kesamaan_bentuk':ratio_shapes,
                      'mode_geom':'POLIGON','titik_di_dalam':None}
            dist=hypot(center_b.x()-center_p.x(),center_b.y()-center_p.y())
            name_score=name_similarity(a.get('_name_value'),rp['a'].get('_name_value'))
            vals.update({'pair_id':'B%06d_P%06d'%(rb['idx'],rp['idx']),
                  'record_bpn':rb['idx'],'record_pbb':rp['idx'],
                  'NIB':a.get('_id_field_value',''),'NOP':rp['a'].get('_id_field_value',''),
                  'kesamaan_luas_tulis':similarity(ab,ap),
                  'deviasi_luas_bpn':dev_percent(ab,area_b),
                  'jarak_centroid':dist,
                  'bpn_luas_kosong':int(ab is None),'pbb_luas_kosong':int(ap is None),
                  'bpn_invalid':rb['a'].get('geom_invalid',0),
                  'pbb_invalid':rp['a'].get('geom_invalid',0),
                  'bpn_internal_overlap':rb['a'].get('overlap',0),
                  'pbb_internal_overlap':rp['a'].get('overlap',0),
                  'skor_nama':name_score,
                  'valid_nama':name_status(name_score,name_ok,name_partial),
                  'x_bpn':center_b.x(), 'y_bpn':center_b.y()})
            choices.append(vals)
        if radius>0 and len(choices)>max_near:
            strong=[v for v in choices if _is_strong_near(v,area_tol)]
            others=sorted([v for v in choices if not _is_strong_near(v,area_tol)],
                          key=lambda r:r['jarak_geometri'])[:max_near]
            choices=strong+others
        for c in choices:
            candidates.append(c)
            per_b[rb['idx']].append(c);per_p[c['record_pbb']].append(c)
    for c in candidates:
        c['jumlah_calon_radius_bpn']=len(per_b[c['record_bpn']])
        c['jumlah_calon_radius_pbb']=len(per_p[c['record_pbb']])
    return candidates


def prepare_local(rows,id_field,area_field,max_dev,name_field=None):
    """Cache identity/area (and optional name) values under private '_' keys."""
    counts=Counter(ident(r['a'].get(id_field)) for r in rows if ident(r['a'].get(id_field)))
    for r in rows:
        a=r['a']; code=ident(a.get(id_field));g=r['geom']
        a['_id_field_value']=code;a['_area_field_value']=a.get(area_field)
        a['_name_value']=a.get(name_field) if name_field else None
        a['_id_count']=counts[code] if code else 0
        a['_deviation']=(None if g.isNull() or g.isEmpty() or is_point_geom(g)
                         else dev_percent(a.get(area_field),g.area()))


def determine_levels(b,p,opts):
    """> threshold measured only against BPN; 1:1 uniqueness among passing candidates.

    Mode titik (PBB = points): a candidate qualifies when the NOP point lies
    inside the BPN parcel (replaces the overlap gate). Every other gate stays.
    Optional names (opts 'bpn_name'/'pbb_name') add ``valid_nama`` and
    ``kekuatan`` to accepted pairs, and fail a pair only with
    ``opts['require_name']``. With names and ``opts['name_stage']`` a second
    stage (``name_stage``) re-examines the remaining Level 2 records.
    """
    prepare_local(b,opts['bpn_id'],opts['bpn_area'],opts['max_dev'],opts.get('bpn_name'))
    prepare_local(p,opts['pbb_id'],opts['pbb_area'],opts['max_dev'],opts.get('pbb_name'))
    pmode=point_mode(p)
    names_used=bool(opts.get('bpn_name'))
    pairs=make_candidate_rows(b,p,opts['min_irisan'],radius=0.,
                              point_tol=float(opts.get('point_tol',0.) or 0.) if pmode else 0.,
                              name_thresholds=(opts.get('name_match',90.),
                                               opts.get('name_partial',60.)))
    if pmode:
        strong=[r for r in pairs if r['titik_di_dalam']==1]
    else:
        strong=[r for r in pairs if r['overlap_bpn_pct']>opts['min_overlap']]
    counts_b=Counter(x['record_bpn'] for x in strong)
    counts_p=Counter(x['record_pbb'] for x in strong)
    by_b=defaultdict(list);by_p=defaultdict(list)
    accepted=[]
    refb={r['idx']:r for r in b};refp={r['idx']:r for r in p}
    for candidate in pairs:
        i=candidate['record_bpn'];j=candidate['record_pbb']
        by_b[i].append(candidate);by_p[j].append(candidate)
        rb=refb[i];rp=refp[j]
        point_pair=candidate.get('mode_geom')=='TITIK'
        failures=gate_pair(candidate['overlap_bpn_pct'], counts_b[i],counts_p[j],
                 rb['a']['_id_field_value'],rp['a']['_id_field_value'],
                 rb['a']['_id_count'],rp['a']['_id_count'],
                 candidate['deviasi_luas_bpn'],candidate['deviasi_luas_pbb'],
                 candidate['kesamaan_luas_tulis'],opts,
                 point_inside=bool(candidate['titik_di_dalam']) if point_pair else None,
                 name_state=candidate['valid_nama'])
        candidate['status']='LEVEL_1' if not failures else 'LEVEL_2'
        candidate['alasan']=';'.join(failures)
        candidate['kekuatan']=('' if failures or not names_used
                               else match_strength(candidate['valid_nama'],point_pair))
        if not failures:accepted.append(candidate)
    # Ensure exact 1:1 and no duplicate identity values within accepted.
    seen_b=set();seen_p=set();clean=[]
    for r in accepted:
        if r['record_bpn'] in seen_b or r['record_pbb'] in seen_p:
            raise AssertionError('Pasangan tidak unik; cek aturan pemaduan')
        seen_b.add(r['record_bpn']);seen_p.add(r['record_pbb']);clean.append(r)
    stage2=[]
    if names_used and opts.get('name_stage'):
        stage2=name_stage(b,p,pairs,seen_b,seen_p,opts,pmode)
        for r in stage2:
            seen_b.add(r['record_bpn']);seen_p.add(r['record_pbb'])
    best2_b={};best2_p={}
    for r in pairs:
        score=r.get('skor_gabungan')
        if score is None:continue
        best2_b[r['record_bpn']]=max(score,best2_b.get(r['record_bpn'],score))
        best2_p[r['record_pbb']]=max(score,best2_p.get(r['record_pbb'],score))
    def name_hint(cands,key):
        return ';'.join(str(v[key]) for v in sorted(cands,key=candidate_rank)
                        if v.get('valid_nama')=='COCOK')
    none_b='TIDAK_ADA_TITIK' if pmode else 'TIDAK_ADA_IRISAN'
    none_p='TITIK_DI_LUAR_SEMUA_BIDANG' if pmode else 'TIDAK_ADA_IRISAN'
    b_level2=[];p_level2=[]
    for rb in b:
        if rb['idx'] in seen_b:continue
        reasons=sorted(set(';'.join(v['alasan'] for v in by_b[rb['idx']]).split(';'))- {''})
        if not by_b[rb['idx']]:reasons=[none_b]
        nr=dict(rb);nr['a']=dict(rb['a']);nr['a'].update(
            level=2,calon_n=counts_b[rb['idx']],
            kode_l2=';'.join(reasons),alasan_l2='; '.join(reasons),
            calon_id=';'.join(str(v['NOP']) for v in sorted(by_b[rb['idx']],key=candidate_rank)[:5]),
            calon_nama=name_hint(by_b[rb['idx']],'NOP'),
            skor_gabungan=best2_b.get(rb['idx']))
        b_level2.append(nr)
    for rp in p:
        if rp['idx'] in seen_p:continue
        reasons=sorted(set(';'.join(v['alasan'] for v in by_p[rp['idx']]).split(';'))-{''})
        if not by_p[rp['idx']]:reasons=[none_p]
        nr=dict(rp);nr['a']=dict(rp['a']);nr['a'].update(
            level=2,calon_n=counts_p[rp['idx']],kode_l2=';'.join(reasons),
            alasan_l2='; '.join(reasons),
            calon_id=';'.join(str(v['NIB']) for v in sorted(by_p[rp['idx']],key=candidate_rank)[:5]),
            calon_nama=name_hint(by_p[rp['idx']],'NIB'),
            skor_gabungan=best2_p.get(rp['idx']))
        p_level2.append(nr)
    level1=[]
    for match in clean:
        rb=refb[match['record_bpn']];rp=refp[match['record_pbb']]
        level1.append(level1_record(rb,rp,match,'RULE',names_used=names_used))
    for match in stage2:
        rb=refb[match['record_bpn']];rp=refp[match['record_pbb']]
        level1.append(level1_record(rb,rp,match,'RULE_NAMA'))
    return level1,b_level2,p_level2,pairs,clean+stage2


def name_stage(b,p,pairs,seen_b,seen_p,opts,pmode):
    """Tahap 2: Level 2 records re-examined within a buffer using names.

    Only records left unmatched by stage 1 and free of identity failures
    (``logic.STAGE2_BLOCKED``) take part. Candidates within ``stage2_buffer`` metres
    get ``skor_spasial`` and ``skor_gabungan`` (``logic.combined_score``);
    ``logic.select_stage2`` keeps strict 1:1 winners. Stage-1 rows in ``pairs``
    are updated in place, new (non-intersecting) candidates are appended.
    Accepted rows get ``status=LEVEL_1`` and ``metode_padu=RULE_NAMA``.
    """
    o=dict(STAGE2_DEFAULTS,**{k:v for k,v in opts.items() if v is not None})
    buffer=float(o['stage2_buffer'] or 0.)
    def free(rows,taken):
        return [r for r in rows if r['idx'] not in taken and r['a']['_id_field_value']
                and r['a']['_id_count']==1 and not r['geom'].isNull() and not r['geom'].isEmpty()]
    eb=free(b,seen_b);ep=free(p,seen_p)
    if not eb or not ep:return []
    rows=make_candidate_rows(eb,ep,opts['min_irisan'],radius=max(buffer,1e-6),
                             point_tol=buffer,
                             name_thresholds=(opts.get('name_match',90.),opts.get('name_partial',60.)))
    known={r['pair_id']:r for r in pairs}
    scored=[]
    weights=(o['w_name'],o['w_spatial'],o['w_area'])
    for row in rows:
        linked=_is_strong_near(row,opts['min_irisan'])
        if not linked and row['jarak_geometri']>buffer:continue
        target=known.get(row['pair_id'])
        if target is None:
            row['status']='LEVEL_2'
            row['alasan']='TITIK_DI_LUAR_BIDANG' if pmode else 'TIDAK_ADA_IRISAN'
            row['kekuatan']=''
            pairs.append(row);target=row
        spatial=spatial_score(target['jarak_geometri'],buffer,linked)
        target['skor_spasial']=round(spatial,1)
        target['skor_gabungan']=combined_score(target['skor_nama'],spatial,
                                               target['kesamaan_luas_tulis'],weights)
        scored.append(target)
    accepted=select_stage2(scored,o['stage2_min'],o['stage2_min_name'],o['stage2_margin'])
    for r in accepted:
        r['status']='LEVEL_1';r['metode_padu']='RULE_NAMA';r['alasan']=''
        # Weaker spatial evidence than stage 1: strength judged as for points.
        r['kekuatan']=match_strength(r['valid_nama'],True)
    return accepted


def level1_record(rb,rp,match,method,score=None,names_used=True):
    """BPN parcel + PBB attributes (prefix pbb_) for an accepted pair.

    Without a name column no name is assessed, so ``kekuatan`` stays empty.
    """
    if not names_used:
        match['kekuatan']=''
    elif not match.get('kekuatan'):
        match['kekuatan']=match_strength(match.get('valid_nama'),match.get('mode_geom')=='TITIK')
    attrs={k:v for k,v in rb['a'].items() if not k.startswith('_')}
    attrs.update({'nop_padanan':match['NOP'],'level':1,'metode_padu':method,
                  'overlap_pct':(None if match.get('mode_geom')=='TITIK'
                                 else match['overlap_bpn_pct']),
                  'kesamaan_pct':match['kesamaan_luas_tulis'],
                  'skor_nama':match.get('skor_nama'),
                  'valid_nama':match.get('valid_nama'),
                  'kekuatan':match['kekuatan'],
                  'skor_gabungan':match.get('skor_gabungan')})
    if score is not None:attrs['skor_ai']=score
    attrs.update({('pbb_'+k):v for k,v in rp['a'].items() if not k.startswith('_')})
    return {'idx':rb['idx'],'fid':rb['fid'],'a':attrs,'geom':rb['geom']}

FEATURE_NAMES = ['overlap_bpn_pct','overlap_pbb_pct','iou','kesamaan_luas_geom',
                'kesamaan_luas_tulis','deviasi_luas_bpn','deviasi_luas_pbb',
                'jarak_centroid','jarak_geometri','kesamaan_bentuk',
                'bpn_luas_kosong','pbb_luas_kosong','bpn_invalid','pbb_invalid',
                'bpn_internal_overlap','pbb_internal_overlap',
                'jumlah_calon_radius_bpn','jumlah_calon_radius_pbb']


def layer_fingerprint(layer):
    """Hash all feature IDs, geometry WKB and attributes; prevent stale silver labels."""
    import hashlib
    h=hashlib.sha256()
    h.update(layer.crs().authid().encode('utf-8'))
    h.update('|'.join(f.name() for f in layer.fields()).encode('utf-8'))
    for f in layer.getFeatures():
        h.update(str(f.id()).encode('ascii'))
        g=f.geometry()
        if g is not None and not g.isNull():h.update(bytes(g.asWkb()))
        for field in layer.fields():
            h.update(repr(f[field.name()]).encode('utf-8','replace'))
            h.update(b'\x00')
    return h.hexdigest()
