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
from .logic import empty, ident, number, dev_percent, similarity, gate_pair

QA_COLUMNS = {'geom_kosong','geom_invalid','geom_fixed','overlap','bid_tambah',
              'selisih_luas','persen_selisihL','id_kosong','id_duplikat','luas_flag',
              'level','kode_l2','alasan_l2','calon_n','calon_id', 'skor_ai',
              'metode_padu','nop_padanan'}

def metric_crs(layer):
    if not layer or not layer.isValid():
        raise ValueError('Layer tidak valid.')
    if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
        raise ValueError('Layer harus bertipe poligon.')
    if not layer.crs().isValid():
        raise ValueError('CRS tidak diketahui; atur CRS layer terlebih dahulu.')
    if layer.crs().mapUnits() != QgsUnitTypes.DistanceMeters:
        raise ValueError('Gunakan CRS proyeksi dengan satuan meter; data geografis derajat tidak dapat langsung dihitung m².')


def read(layer, strip_old=True, transform=None):
    """Returns list of independent records with QGIS-native geometries."""
    metric_crs(layer)
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


def read_pair(bpn_layer,pbb_layer,reproject=False):
    metric_crs(bpn_layer); metric_crs(pbb_layer)
    same=bpn_layer.crs()==pbb_layer.crs()
    if not same and not reproject:
        raise ValueError('CRS berbeda: %s vs %s. Centang opsi reproyeksi PBB.' %
                         (bpn_layer.crs().authid(),pbb_layer.crs().authid()))
    trans=None if same else QgsCoordinateTransform(pbb_layer.crs(),bpn_layer.crs(),
                                                    QgsProject.instance())
    return read(bpn_layer), read(pbb_layer,transform=trans), (
        ['CRS sama: '+bpn_layer.crs().authid()] if same else
        ['PBB ditransformasi ke CRS BPN: '+bpn_layer.crs().authid()])


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
            if invalid:
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


def internal_overlap(records,min_area=.01):
    index,by_id=spatial_index(records)
    logs=[]
    for r in records:r['a']['overlap']=0
    for a in records:
        geom=a['geom']
        if geom.isNull() or geom.isEmpty():continue
        for j in index.intersects(geom.boundingBox()):
            if j<=a['idx']:continue
            b=by_id[j]
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
        g=r['geom']; a=r['a'];area=None if g.isNull() or g.isEmpty() else g.area()
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


def layer_from_records(records, crs, schema, name='Keluaran'):
    lyr=QgsVectorLayer('MultiPolygon?crs='+crs.authid(), name, 'memory')
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


def make_candidate_rows(b,p,area_tol=.01,radius=0.,max_near=8):
    """Return feature vectors shared by Modules 3,4,5 and studio.
    record indexes are stable 1-based at the moment of the run.
    """
    index, lookup=spatial_index(p)
    candidates=[]; per_b=defaultdict(list);per_p=defaultdict(list)
    for rb in b:
        gb=rb['geom'];a=rb['a'];
        if gb.isNull() or gb.isEmpty() or gb.area()<=0:continue
        bounds=gb.boundingBox()
        bounds.grow(max(0.,radius))
        ids=index.intersects(bounds)
        choices=[]
        for j in ids:
            rp=lookup[j];gp=rp['geom'];area_p=gp.area()
            if area_p<=0:continue
            inter=gb.intersection(gp) if gb.intersects(gp) else QgsGeometry()
            intersection=0 if inter.isNull() or inter.isEmpty() else inter.area()
            if radius<=0 and intersection<=area_tol:continue
            # distance 0 for intersecting; QGIS geometries projected in metres
            sep=gb.distance(gp) if intersection<=area_tol else 0.
            if radius>0 and intersection<=area_tol and sep>radius:continue
            area_b=gb.area()
            ab=number(a.get('_area_field_value'))
            ap=number(rp['a'].get('_area_field_value'))
            center_b=gb.centroid().asPoint();center_p=gp.centroid().asPoint()
            dist=hypot(center_b.x()-center_p.x(),center_b.y()-center_p.y())
            perimeter_b=max(gb.length(),1e-7);perimeter_p=max(gp.length(),1e-7)
            ratio_shapes=(min((4*pi*area_b)/(perimeter_b**2), (4*pi*area_p)/(perimeter_p**2)) /
                          max((4*pi*area_b)/(perimeter_b**2), (4*pi*area_p)/(perimeter_p**2),1e-9))
            vals={'pair_id':'B%06d_P%06d'%(rb['idx'],rp['idx']),
                  'record_bpn':rb['idx'],'record_pbb':rp['idx'],
                  'NIB':a.get('_id_field_value',''),'NOP':rp['a'].get('_id_field_value',''),
                  'irisan_m2':intersection,'overlap_bpn_pct':100*intersection/area_b,
                  'overlap_pbb_pct':100*intersection/area_p,
                  'iou':intersection/(area_b+area_p-intersection) if (area_b+area_p-intersection)>0 else 0,
                  'area_bpn_geom':area_b,'area_pbb_geom':area_p,
                  'kesamaan_luas_geom':100*min(area_b,area_p)/max(area_b,area_p),
                  'kesamaan_luas_tulis':similarity(ab,ap),
                  'deviasi_luas_bpn':dev_percent(ab,area_b),
                  'deviasi_luas_pbb':dev_percent(ap,area_p),
                  'jarak_centroid':dist,'jarak_geometri':sep,
                  'kesamaan_bentuk':ratio_shapes,
                  'bpn_luas_kosong':int(ab is None),'pbb_luas_kosong':int(ap is None),
                  'bpn_invalid':rb['a'].get('geom_invalid',0),
                  'pbb_invalid':rp['a'].get('geom_invalid',0),
                  'bpn_internal_overlap':rb['a'].get('overlap',0),
                  'pbb_internal_overlap':rp['a'].get('overlap',0),
                  'x_bpn':center_b.x(), 'y_bpn':center_b.y()}
            choices.append(vals)
        if radius>0 and len(choices)>max_near:
            strong=[v for v in choices if v['irisan_m2']>area_tol]
            others=sorted([v for v in choices if v['irisan_m2']<=area_tol],
                          key=lambda r:r['jarak_geometri'])[:max_near]
            choices=strong+others
        for c in choices:
            candidates.append(c)
            per_b[rb['idx']].append(c);per_p[c['record_pbb']].append(c)
    for c in candidates:
        c['jumlah_calon_radius_bpn']=len(per_b[c['record_bpn']])
        c['jumlah_calon_radius_pbb']=len(per_p[c['record_pbb']])
    return candidates


def prepare_local(rows,id_field,area_field,max_dev):
    counts=Counter(ident(r['a'].get(id_field)) for r in rows if ident(r['a'].get(id_field)))
    for r in rows:
        a=r['a']; code=ident(a.get(id_field));g=r['geom']
        a['_id_field_value']=code;a['_area_field_value']=a.get(area_field)
        a['_id_count']=counts[code] if code else 0
        a['_deviation']=None if g.isNull() or g.isEmpty() else dev_percent(a.get(area_field),g.area())


def determine_levels(b,p,opts):
    """> threshold measured only against BPN; 1:1 uniqueness among passing candidates."""
    prepare_local(b,opts['bpn_id'],opts['bpn_area'],opts['max_dev'])
    prepare_local(p,opts['pbb_id'],opts['pbb_area'],opts['max_dev'])
    pairs=make_candidate_rows(b,p,opts['min_irisan'],radius=0.)
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
        failures=gate_pair(candidate['overlap_bpn_pct'], counts_b[i],counts_p[j],
                 rb['a']['_id_field_value'],rp['a']['_id_field_value'],
                 rb['a']['_id_count'],rp['a']['_id_count'],
                 candidate['deviasi_luas_bpn'],candidate['deviasi_luas_pbb'],
                 candidate['kesamaan_luas_tulis'],opts)
        candidate['status']='LEVEL_1' if not failures else 'LEVEL_2'
        candidate['alasan']=';'.join(failures)
        if not failures:accepted.append(candidate)
    # Ensure exact 1:1 and no duplicate identity values within accepted.
    seen_b=set();seen_p=set();clean=[]
    for r in accepted:
        if r['record_bpn'] in seen_b or r['record_pbb'] in seen_p:
            raise AssertionError('Pasangan tidak unik; cek aturan pemaduan')
        seen_b.add(r['record_bpn']);seen_p.add(r['record_pbb']);clean.append(r)
    b_level2=[];p_level2=[]
    for rb in b:
        if rb['idx'] in seen_b:continue
        reasons=sorted(set(';'.join(v['alasan'] for v in by_b[rb['idx']]).split(';'))- {''})
        if not by_b[rb['idx']]:reasons=['TIDAK_ADA_IRISAN']
        nr=dict(rb);nr['a']=dict(rb['a']);nr['a'].update(
            level=2,calon_n=counts_b[rb['idx']],
            kode_l2=';'.join(reasons),alasan_l2='; '.join(reasons),
            calon_id=';'.join(str(v['NOP']) for v in sorted(by_b[rb['idx']],key=lambda x:-x['irisan_m2'])[:5]))
        b_level2.append(nr)
    for rp in p:
        if rp['idx'] in seen_p:continue
        reasons=sorted(set(';'.join(v['alasan'] for v in by_p[rp['idx']]).split(';'))-{''})
        if not by_p[rp['idx']]:reasons=['TIDAK_ADA_IRISAN']
        nr=dict(rp);nr['a']=dict(rp['a']);nr['a'].update(
            level=2,calon_n=counts_p[rp['idx']],kode_l2=';'.join(reasons),
            alasan_l2='; '.join(reasons),
            calon_id=';'.join(str(v['NIB']) for v in sorted(by_p[rp['idx']],key=lambda x:-x['irisan_m2'])[:5]))
        p_level2.append(nr)
    level1=[]
    for match in clean:
        rb=refb[match['record_bpn']];rp=refp[match['record_pbb']]
        attrs={k:v for k,v in rb['a'].items() if not k.startswith('_')}
        attrs.update({'nop_padanan':match['NOP'],'level':1,'metode_padu':'RULE',
                      'overlap_pct':match['overlap_bpn_pct'],
                      'kesamaan_pct':match['kesamaan_luas_tulis']})
        attrs.update({('pbb_'+k):v for k,v in rp['a'].items() if not k.startswith('_')})
        level1.append({'idx':rb['idx'],'fid':rb['fid'],'a':attrs,'geom':rb['geom']})
    return level1,b_level2,p_level2,pairs,clean

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
