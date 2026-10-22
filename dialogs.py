"""Five one-at-a-time QGIS tool dialogs, with layer and field dropdowns."""
from collections import Counter
from pathlib import Path
from qgis.core import QgsVectorLayer
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtWidgets import (
    QDialog,QFormLayout,QVBoxLayout,QHBoxLayout,QGroupBox,QPushButton,QComboBox,
    QLineEdit,QCheckBox,QDoubleSpinBox,QLabel,QFileDialog,QMessageBox,QPlainTextEdit,
    QScrollArea,QWidget,QApplication)
from .engine import (read,read_pair,fix_geometry,spatial_audit,qa_attribute,columns,
                     layer_from_records,determine_levels,prepare_local,make_candidate_rows,
                     FEATURE_NAMES,internal_overlap,layer_fingerprint,QA_COLUMNS)
from .storage import FORMATS,save_layer,complete_report,zip_csv
from .reporting_full import report1,report2,report3,report5
from .logic import ident
from .fieldwidgets import LayerFieldComboBox


class Selector(QWidget):
    """Layer + unrestricted attribute-field selectors used in Tools 1 to 5."""
    def __init__(self,label,with_area=True, optional=False):
        super().__init__()
        layout=QFormLayout(self)
        self.label=label
        theme = 'pbb' if 'pbb' in label.lower() else 'bpn'
        self.layer=QgsMapLayerComboBox()
        self.id=LayerFieldComboBox(theme, 'identity')
        self.area=LayerFieldComboBox(theme, 'area') if with_area else None
        self.layer.layerChanged.connect(self.change_layer)
        layout.addRow(label,self.layer)
        layout.addRow('Kolom identitas (semua field):',self.id)
        if with_area:
            layout.addRow('Kolom luas tertulis (semua field):',self.area)
        self.change_layer(self.layer.currentLayer())

    def change_layer(self,layer):
        self.id.setLayer(layer)
        if self.area is not None:
            self.area.setLayer(layer)

    def values(self):
        return (self.layer.currentLayer(),self.id.currentField(),
                self.area.currentField() if self.area is not None else '')


def spin(value,minimum,maximum,decimals=2):
    s=QDoubleSpinBox();s.setDecimals(decimals);s.setRange(minimum,maximum);s.setValue(value)
    return s


class ToolDialog(QDialog):
    def __init__(self,iface,modul,parent=None):
        super().__init__(parent)
        self.iface=iface;self.modul=modul
        names={1:'01 - Audit Kelengkapan',2:'02 - Kualitas Spasial',
               3:'03 - Penentuan level pemaduan berbasis aturan',4:'04 - Training AI',5:'05 - Inference AI'}
        self.setWindowTitle('NIB-NOP | '+names[modul]);self.resize(640,750)
        container=QVBoxLayout(self)
        scroll=QScrollArea();scroll.setWidgetResizable(True)
        form_widget=QWidget();self.panel=QVBoxLayout(form_widget)
        scroll.setWidget(form_widget);container.addWidget(scroll)
        self.bpn=Selector('Layer BPN:');self.pbb=Selector('Layer PBB:')
        if modul!=4:
            self.panel.addWidget(self.bpn);self.panel.addWidget(self.pbb)
        else:
            hdr=QLabel('Sumber silver dari hasil Modul 3 (opsional):')
            self.panel.addWidget(hdr)
            self.panel.addWidget(self.bpn);self.panel.addWidget(self.pbb)
        self.reproject=QCheckBox('Jika CRS berbeda, reproyeksikan PBB sementara ke CRS BPN')
        self.panel.addWidget(self.reproject)
        self.param={}
        self.param_form=QFormLayout();self.panel.addLayout(self.param_form)
        self.setup_module()
        group=QGroupBox('Folder hasil dan format penyimpanan');outs=QFormLayout(group)
        self.output=QLineEdit(str(Path.home()/'NIBNOP_HASIL'/('modul_%d'%modul)))
        browse=QPushButton('Pilih folder...');browse.clicked.connect(self.choose_folder)
        rr=QHBoxLayout();rr.addWidget(self.output);rr.addWidget(browse)
        outs.addRow('Folder:',rr)
        self.output_format=QComboBox();self.output_format.addItems(FORMATS.keys())
        outs.addRow('Format layer:',self.output_format)
        self.panel.addWidget(group)
        self.panel.addWidget(QLabel('Keluaran: layer spasial pilihan, rekap_csv.zip, laporan_<modul>.pdf'))
        self.log=QPlainTextEdit();self.log.setReadOnly(True);self.log.setMaximumHeight(110)
        container.addWidget(self.log)
        buttons=QHBoxLayout()
        self.run_button=QPushButton('Jalankan Modul '+str(modul))
        self.run_button.clicked.connect(self.run)
        cancel=QPushButton('Tutup');cancel.clicked.connect(self.close)
        buttons.addWidget(self.run_button);buttons.addWidget(cancel);container.addLayout(buttons)
    def filepick(self,label,pattern='CSV (*.csv);;Semua (*)'):
        edit=QLineEdit();button=QPushButton('...')
        button.setToolTip('Pilih file')
        button.clicked.connect(lambda: self.set_file(edit,pattern))
        lay=QHBoxLayout();lay.addWidget(edit);lay.addWidget(button)
        self.param_form.addRow(label,lay)
        return edit
    def set_file(self,edit,pattern):
        result=QFileDialog.getOpenFileName(self,'Pilih file',edit.text(),pattern)[0]
        if result:edit.setText(result)
    def choose_folder(self):
        found=QFileDialog.getExistingDirectory(self,'Lokasi output',self.output.text())
        if found:self.output.setText(found)
    def add_spin(self,key,label,default,minv,maxv,decimals=2):
        el=spin(default,minv,maxv,decimals)
        self.param_form.addRow(label,el);self.param[key]=el
    def val(self,key):return self.param[key].value()
    def setup_module(self):
        m=self.modul
        if m==1:
            self.add_spin('min_area','Luas minimum pemeriksaan (m²):',5,0,1e9)
            self.add_spin('max_area','Luas maksimum pemeriksaan (m²):',10000,1,1e12)
        if m==2:
            self.add_spin('overlap_area','Minimum luas overlap internal (m²):',.01,0,10000,3)
            self.add_spin('gap_area','Minimum gap BPN ditambahkan (m²):',1,0,1e8)
            self.use_gap=QCheckBox('Delineasi gap tertutup BPN (bid_tambah=1)');self.use_gap.setChecked(True)
            self.param_form.addRow('',self.use_gap)
        if m in (3,5):
            self.add_spin('overlap','Ambang irisan > (% luas BPN):',50,0,100,1)
            self.add_spin('sim','Kesamaan luas tertulis > (%):',90,0,100,1)
            self.add_spin('dev','Deviasi luas-geometri maksimum (%):',50,0,500,1)
            self.add_spin('min_irisan','Minimum luas irisan (m²):',.01,0,500,3)
            self.add_spin('min_gap','Minimum gap tertutup BPN (m²):',1,0,1e8)
        if m==4:
            self.silver=self.filepick('CSV kandidat Modul 3 (silver):')
            self.gold_features=self.filepick('CSV fitur historis terverifikasi (opsional):')
            self.gold_operator=self.filepick('CSV label operator pada layer yang dipilih (opsional):')
            self.hist_toggle=QCheckBox('Gunakan pasangan GeoJSON historis + CSV label (opsional)')
            self.param_form.addRow(self.hist_toggle)
            self.hist_bpn=Selector('BPN historis:');self.hist_pbb=Selector('PBB historis:')
            self.hist_bpn.setVisible(False);self.hist_pbb.setVisible(False)
            self.panel.addWidget(self.hist_bpn);self.panel.addWidget(self.hist_pbb)
            self.hist_csv=self.filepick('CSV pasangan historis berlabel:')
            self.hist_toggle.toggled.connect(self.hist_bpn.setVisible)
            self.hist_toggle.toggled.connect(self.hist_pbb.setVisible)
            self.add_spin('radius','Radius pencarian kandidat (meter):',15,0,1000)
            self.add_spin('target','Target precision GOLD:',.99,.5,1.,3)
        if m==5:
            self.model=self.filepick('Model terlatih (.joblib):','Joblib (*.joblib);;Semua (*)')
            self.meta=self.filepick('Metadata model (.json):','JSON (*.json);;Semua (*)')
            self.add_spin('radius','Radius kandidat AI (meter):',15,0,1000)
            self.add_spin('confidence','Skor minimum AI:',.95,.5,1.,3)
            self.add_spin('margin','Selisih skor kandidat ke-1 vs ke-2:',.15,0,1.,3)
            self.promote=QCheckBox('Izinkan tambahan Level 1 berbasis AI HANYA bila GOLD telah lolos pengujian')
            self.param_form.addRow('',self.promote)
            self.promote.setChecked(False)
            self.param_form.addRow(QLabel('PERHATIAN: file model joblib hanya dari sumber yang dipercaya.'))
    def two_layers(self):
        b,bid,ba=self.bpn.values();p,pid,pa=self.pbb.values()
        if not b or not p or not bid or not pid or not ba or not pa:
            raise ValueError('Pilih layer BPN/PBB serta kolom NIB, NOP dan luas dari dropdown.')
        return b,p,bid,pid,ba,pa
    def opts(self):
        b,p,bid,pid,ba,pa=self.two_layers()
        return {'bpn_id':bid,'pbb_id':pid,'bpn_area':ba,'pbb_area':pa,
                'min_overlap':self.val('overlap'),'min_sim':self.val('sim'),
                'max_dev':self.val('dev'),'min_irisan':self.val('min_irisan')}
    def persist(self,layer,basename,output):
        saved=save_layer(layer,output,basename,self.output_format.currentText())
        added=self.iface.addVectorLayer(saved,basename,'ogr')
        if not added or not added.isValid():
            self.log.appendPlainText('Layer berhasil tersimpan tetapi gagal ditambahkan ke panel QGIS: '+basename)
        return saved
    def run(self):
        self.run_button.setEnabled(False)
        self.log.clear()
        if self.output_format.currentText().startswith('ESRI Shapefile'):
            QMessageBox.warning(self,'Nama kolom Shapefile','Shapefile dapat memotong nama atribut menjadi 10 karakter dan menyebabkan tabrakan kolom. GeoPackage disarankan untuk hasil integrasi.')
        try:
            result=self.execute()
            self.log.appendPlainText('SELESAI\n'+ '\n'.join(result))
            QMessageBox.information(self,'Selesai','Modul %s selesai. Hasil tersimpan pada:\n%s'%(self.modul,self.output.text()))
        except Exception as e:
            import traceback
            self.log.appendPlainText(traceback.format_exc())
            QMessageBox.critical(self,'Gagal menjalankan Modul '+str(self.modul),str(e))
        finally:self.run_button.setEnabled(True)
    def execute(self):
        folder=Path(self.output.text()).expanduser();folder.mkdir(parents=True,exist_ok=True)
        if self.modul==1:return self.run1(folder)
        if self.modul==2:return self.run2(folder)
        if self.modul==3:return self.run3(folder)
        if self.modul==4:return self.run4(folder)
        if self.modul==5:return self.run5(folder)
    def run1(self,out):
        b,p,bid,pid,ba,pa=self.two_layers()
        datasets=[];tables={};stats={};charts=[];files=[]
        for layer,tag,idcol,areacol in [(b,'BPN',bid,ba),(p,'PBB',pid,pa)]:
            rows=read(layer)
            datasets.append((rows,idcol,areacol))
            res,detail=qa_attribute(rows,idcol,areacol,self.val('min_area'),self.val('max_area'))
            stats.update({tag+' '+k:v for k,v in res.items()})
            charts.append((tag+' indikator awal',{
                'Kosong':res['identitas_kosong'],'Duplikat':res['record_duplikat'],
                'Luas':res['record_luas_bermasalah']}))
            for k,v in detail.items():tables[tag.lower()+'_'+k]=v
            charts.append((tag+' atribut kosong',{a['nama_kolom']:a['jumlah_kosong'] for a in detail.get('per_kolom_kosong.csv',[])}))
            schema=columns(layer,[('id_kosong','Int'),('id_duplikat','Int'),('luas_flag','String')])
            files.append(self.persist(layer_from_records(rows,layer.crs(),schema,tag+' M1'),tag.lower()+'_audit_atribut',out))
        archive=zip_csv(out,tables)
        pdf=report1(out,datasets[0],datasets[1],stats,tables,
                    self.val('min_area'),self.val('max_area'))
        reports={'pdf':pdf,'csv_zip':archive}
        return files+[reports['pdf'],reports['csv_zip']]
    def run2(self,out):
        b,p,bid,pid,ba,pa=self.two_layers()
        b_rows,p_rows,logs=read_pair(b,p,self.reproject.isChecked())
        results=[];tables={};stats={};charts=[];updated_by_tag={}
        for rows,layer,tag,idcol,ac,with_gaps in [
            (b_rows,b,'bpn',bid,ba,self.use_gap.isChecked()),
            (p_rows,p,'pbb',pid,pa,False)]:
            updated,ov,gaps,warn=spatial_audit(rows,idcol,ac,self.val('overlap_area'),
                                             self.val('gap_area'),with_gaps)
            updated_by_tag[tag]=updated
            extra=[('geom_kosong','Int'),('geom_invalid','Int'),('geom_fixed','Int'),
                   ('overlap','Int'),('bid_tambah','Int'),('selisih_luas','Double'),
                   ('persen_selisihL','Double'),('gap_id','String')]
            results.append(self.persist(layer_from_records(updated,b.crs(),columns(layer,extra),tag),
                                        tag+'_kualitas_spasial',out))
            tables[tag+'_overlap.csv']=ov
            tables[tag+'_gap_tertutup.csv']=gaps
            stats[tag+'_record_awal']=len(rows)
            stats[tag+'_record_akhir']=len(updated)
            for key in ['geom_kosong','geom_invalid','geom_fixed','overlap']:
                stats[tag+'_'+key]=sum(int(r['a'].get(key,0) or 0) for r in updated)
            stats[tag+'_gap_baru']=sum(int(r['a'].get('bid_tambah',0) or 0) for r in updated)
            logs+=warn
            charts.append((tag+' hasil QA',{key:stats[tag+'_'+key] for key in ['geom_kosong','geom_invalid','geom_fixed','overlap']}))
        archive=zip_csv(out,tables)
        pdf=report2(out,updated_by_tag['bpn'],updated_by_tag['pbb'],stats,
                    ['CRS kedua layer diperiksa dan transformasi hanya dilakukan bila diizinkan.',
                     'Geometri invalid diperbaiki bila memungkinkan; geometri kosong tidak direkonstruksi.',
                     'Gap = area kosong tertutup, bukan semua ruang kosong di luar batas bidang.',
                     'Irisan overlap internal ditandai; batas persil belum dikoreksi.']+logs[:10],
                    tables['bpn_overlap.csv'],tables['pbb_overlap.csv'],
                    tables['bpn_gap_tertutup.csv'])
        reports={'pdf':pdf,'csv_zip':archive}
        return results+[reports['pdf'],reports['csv_zip']]
    def prepare3(self):
        b,p,bid,pid,ba,pa=self.two_layers()
        b_rows,p_rows,logs=read_pair(b,p,self.reproject.isChecked())
        b_rows,ob,hb,lb=spatial_audit(b_rows,bid,ba,self.val('min_irisan'),self.val('min_gap'),True)
        p_rows,op,hp,lp=spatial_audit(p_rows,pid,pa,self.val('min_irisan'),self.val('min_gap'),False)
        logs+=lb+lp
        return b,p,b_rows,p_rows,ob,op,hb,logs
    def run3(self,out):
        b,p,br,pr,ob,op,hb,logs=self.prepare3()
        options=self.opts()
        fp_b,fp_p=layer_fingerprint(b),layer_fingerprint(p)
        level1,level2b,level2p,pairs,accepted=determine_levels(br,pr,options)
        for pair in pairs:
            pair['src_bpn_sha']=fp_b
            pair['src_pbb_sha']=fp_p
        import json
        (out/'manifest_modul3.json').write_text(json.dumps({'bpn_sha':fp_b,'pbb_sha':fp_p,'input_bpn':b.name(),'input_pbb':p.name()},indent=2),encoding='utf-8')
        bschema=columns(b,[('geom_kosong','Int'),('geom_invalid','Int'),('geom_fixed','Int'),
                  ('overlap','Int'),('bid_tambah','Int'),('selisih_luas','Double'),
                  ('persen_selisihL','Double'),('level','Int'),('calon_n','Int'),
                  ('kode_l2','String'),('alasan_l2','String'),('calon_id','String')])
        pschema=columns(p,[('geom_kosong','Int'),('geom_invalid','Int'),('geom_fixed','Int'),
                  ('overlap','Int'),('bid_tambah','Int'),('selisih_luas','Double'),
                  ('persen_selisihL','Double'),('level','Int'),('calon_n','Int'),
                  ('kode_l2','String'),('alasan_l2','String'),('calon_id','String')])
        joined=columns(b,[('nop_padanan','String'),('level','Int'),('metode_padu','String'),
                   ('overlap_pct','Double'),('kesamaan_pct','Double')])
        joined.extend(('pbb_'+f.name(),f.type()) for f in p.fields() if f.name() not in QA_COLUMNS)
        exported=[self.persist(layer_from_records(level1,b.crs(),joined,'Level 1'),
                               '01_padanan_level1',out),
                  self.persist(layer_from_records(level2b,b.crs(),bschema,'BPN Level 2'),
                               '02_bpn_level2',out),
                  self.persist(layer_from_records(level2p,b.crs(),pschema,'PBB Level 2'),
                               '03_pbb_level2',out)]
        from collections import Counter
        why=Counter(code for r in level2b for code in r['a'].get('kode_l2','').split(';') if code)
        summary={'Level 1':len(level1),'BPN Level 2':len(level2b),'PBB Level 2':len(level2p),
                 'Pasangan beririsan':len(pairs),'Kandidat > overlap':sum(1 for a in pairs if a['overlap_bpn_pct']>options['min_overlap'])}
        report_tables={'pasangan_kandidat.csv':pairs,'overlap_bpn.csv':ob,
                       'overlap_pbb.csv':op,'kandidat_gap.csv':hb,
                       'alasan_level2.csv':[{'record':row['idx'],
                           'id':row['a'].get(options['bpn_id']),
                           'alasan':row['a'].get('kode_l2')} for row in level2b]}
        archive=zip_csv(out,report_tables)
        pdf=report3(out,level1,level2b,level2p,pairs,summary,
                    ['Input wajib dari layer terbaru hasil perbaikan operator.',
                     'Seluruh pemeriksaan kualitas dihitung ulang pada input baru.',
                     'Seleksi overlap terhadap luas geometri BPN menggunakan ambang %.1f%%.' % options['min_overlap'],
                     'Satu NIB/NOP hanya dapat menerima satu padanan yang lolos ambang.',
                     'Kesamaan luas tertulis harus melewati ambang %.1f%%.' % options['min_sim']],
                    logs,bpn_all=br,pbb_all=pr,gaps=hb)
        reports={'pdf':pdf,'csv_zip':archive}
        return exported+[reports['pdf'],reports['csv_zip']]
    def prepared_ml(self):
        b,p,bid,pid,ba,pa=self.two_layers()
        br,pr,logs=read_pair(b,p,self.reproject.isChecked())
        fix_geometry(br);fix_geometry(pr)
        internal_overlap(br,.01);internal_overlap(pr,.01)
        prepare_local(br,bid,ba,50);prepare_local(pr,pid,pa,50)
        return b,p,br,pr,logs
    def run4(self,out):
        from .ml import (labels_for_pairs,add_historical_labeled_features,
                         add_historical_pair_labels,train_model)
        from .engine import FEATURE_NAMES
        from .storage import zip_csv
        from collections import Counter
        silver=[];gold=[];candidates=[];unresolved=[];logs=[]
        try:
            _,_,br,pr,logs=self.prepared_ml()
            candidates=make_candidate_rows(br,pr,.01,self.val('radius'))
            silver_path=self.silver.text().strip() or None
            if silver_path:
                from .ml import csv_rows
                raw=csv_rows(silver_path)
                if not raw or not all('src_bpn_sha' in v and 'src_pbb_sha' in v for v in raw):
                    raise ValueError('CSV Modul 3 harus dibuat oleh plugin ini dengan sidik-jari data operator.')
                exp_b,exp_p=layer_fingerprint(self.bpn.layer.currentLayer()),layer_fingerprint(self.pbb.layer.currentLayer())
                if any(v['src_bpn_sha']!=exp_b or v['src_pbb_sha']!=exp_p for v in raw):
                    raise ValueError('Data operator telah berubah sejak Modul 3. Jalankan ulang Modul 3 untuk file terbaru.')
            silver,gold,unresolved=labels_for_pairs(candidates,self.gold_operator.text().strip() or None,
                                              silver_path)
        except ValueError:
            # May train from an external fully labelled feature CSV only; don't hide
            # other failures when source layers were supplied.
            if not self.gold_features.text().strip():raise
        n_hist=add_historical_labeled_features(gold,self.gold_features.text().strip())
        if self.hist_toggle.isChecked():
            bl,bi,ba=self.hist_bpn.values();pl,pi,pa=self.hist_pbb.values()
            if not (bl and pl and bi and ba and pi and pa):
                raise ValueError('Layer historis dan kolomnya belum lengkap.')
            rb,rp,log=read_pair(bl,pl,self.reproject.isChecked())
            fix_geometry(rb);fix_geometry(rp)
            prepare_local(rb,bi,ba,50);prepare_local(rp,pi,pa,50)
            hist_candidates=make_candidate_rows(rb,rp,.01,self.val('radius'))
            count=add_historical_pair_labels(gold,hist_candidates,self.hist_csv.text().strip())
            logs.append('Pasangan historis GOLD: %s'%count)
        gold_current_ids={x['pair_id'] for x in gold if x.get('label_source')=='GOLD_OPERATOR'}
        silver=[x for x in silver if x['pair_id'] not in gold_current_ids]
        model,metadata,metrics=train_model(silver,gold,out,self.val('target'))
        import json
        from .ai_pdf import make_training_report
        from .evaluation import threshold_guidance
        evaluation=json.loads((out/'evaluasi_testing_ai.json').read_text(encoding='utf-8'))
        summary={'Kandidat sekarang':len(candidates),'SILVER':len(silver),'GOLD':len(gold),
                 'Historis CSV GOLD':n_hist,'Status model':metadata['status'],
                 'Algoritma terpilih':metadata['algorithm'],
                 'Status evaluasi GOLD':evaluation['status_operasional']}
        template=[{**{k:v for k,v in row.items() if k in ('pair_id','record_bpn','record_pbb','NIB','NOP',
                'overlap_bpn_pct','overlap_pbb_pct','kesamaan_luas_tulis')},
                'label':'','status_verifikasi':'','sumber_verifikasi':'','catatan':'','operator':''}
                  for row in candidates]
        feature_rows=[]
        for algo,v in evaluation['models'].items():
            for f in v.get('feature_importance',[]):
                feature_rows.append({'algoritma':algo,**f})
        threshold_rows=threshold_guidance()
        interpret_rows=evaluation.get('penilaian_per_metrik',[])
        recomend_rows=[{'urutan':i,'rekomendasi':txt}
                      for i,txt in enumerate(evaluation['rekomendasi'],1)]
        # Create packaged CSV only; replace the summary PDF by a full,
        # vector-graphics training/testing evaluation report.
        reports=complete_report(out,'modul4',
            ['SILVER bukan ground truth; GOLD independen dibutuhkan untuk testing.'],
            summary,{'fitur_kandidat.csv':candidates,'silver_labels.csv':silver,
                     'gold_labels.csv':gold,'template_verifikasi_operator.csv':template,
                     'metrik_train_validation_test.csv':metrics,
                     'feature_importance.csv':feature_rows,
                     'panduan_ambang_metrik.csv':threshold_rows,
                     'penilaian_per_metrik.csv':interpret_rows,
                     'rekomendasi_model.csv':recomend_rows},
            logs=logs)
        reports['pdf']=make_training_report(out,evaluation,summary=summary,notes=logs)
        return [str(out/'model_terpilih.joblib'),str(out/'metadata_model.json'),
                str(out/'evaluasi_testing_ai.json'),reports['pdf'],reports['csv_zip']]
    def run5(self,out):
        from .ml import predict
        b,p,br,pr,ob,op,hb,logs=self.prepare3()
        opts=self.opts()
        lvl1,lvl2b,lvl2p,pairs,baseline=determine_levels(br,pr,opts)
        refb={r['idx']:r for r in br};refp={r['idx']:r for r in pr}
        extras=[];meta={'status':'NO_MODEL'}
        if self.model.text().strip() or self.meta.text().strip():
            if not self.model.text().strip() or not self.meta.text().strip():
                raise ValueError('Isi path model dan metadata secara bersamaan.')
            ai_candidates=make_candidate_rows(br,pr,opts['min_irisan'],self.val('radius'))
            meta=predict(ai_candidates,self.model.text().strip(),self.meta.text().strip())
            occupied_b={r['record_bpn'] for r in baseline};occupied_p={r['record_pbb'] for r in baseline}
            indices_b=Counter(r['a']['_id_field_value'] for r in br)
            indices_p=Counter(r['a']['_id_field_value'] for r in pr)
            byb={};byp={}
            for r in ai_candidates:
                byb.setdefault(r['record_bpn'],[]).append(r)
                byp.setdefault(r['record_pbb'],[]).append(r)
            ranked=sorted(ai_candidates,key=lambda x:-x.get('skor_ai',0.))
            for r in ranked:
                i=r['record_bpn'];j=r['record_pbb'];score=r['skor_ai']
                if i in occupied_b or j in occupied_p:continue
                if score < self.val('confidence'):continue
                if meta['status']!='GOLD_TESTED_REVIEW_REQUIRED' or not self.promote.isChecked():continue
                idb=refb[i]['a']['_id_field_value'];idp=refp[j]['a']['_id_field_value']
                if not idb or not idp or indices_b[idb]>1 or indices_p[idp]>1:continue
                if (refb[i]['a'].get('overlap') or refp[j]['a'].get('overlap')):continue
                if (r['deviasi_luas_bpn'] is None or r['deviasi_luas_pbb'] is None or
                    r['deviasi_luas_bpn'] > opts['max_dev'] or
                    r['deviasi_luas_pbb'] > opts['max_dev']):continue
                competitor_b=max([x['skor_ai'] for x in byb[i] if x['record_pbb']!=j] or [0.])
                competitor_p=max([x['skor_ai'] for x in byp[j] if x['record_bpn']!=i] or [0.])
                if score-max(competitor_b,competitor_p)<self.val('margin'):continue
                # Extra guard: no competing high-score alternative above acceptance threshold.
                if competitor_b>=self.val('confidence') or competitor_p>=self.val('confidence'):continue
                occupied_b.add(i);occupied_p.add(j)
                extras.append(r)
            if extras:
                # Build output for AI extras; baseline protected.
                for r in extras:
                    rb=refb[r['record_bpn']];rp=refp[r['record_pbb']]
                    attrs={k:v for k,v in rb['a'].items() if not k.startswith('_')}
                    attrs.update({'nop_padanan':r['NOP'],'level':1,'metode_padu':'AI_VERIFIED',
                                  'overlap_pct':r['overlap_bpn_pct'],
                                  'kesamaan_pct':r['kesamaan_luas_tulis'],'skor_ai':r['skor_ai']})
                    attrs.update({'pbb_'+k:v for k,v in rp['a'].items() if not k.startswith('_')})
                    lvl1.append({'idx':rb['idx'],'fid':rb['fid'],'a':attrs,'geom':rb['geom']})
                lvl2b=[r for r in lvl2b if r['idx'] not in occupied_b]
                lvl2p=[r for r in lvl2p if r['idx'] not in occupied_p]
            # One complete score table, with accepted/rejected status for studio.
            scores=[]
            accepted={r['pair_id'] for r in extras}
            for candidate in ai_candidates:
                c=dict(candidate)
                c['keputusan_ai']=('DITERIMA_LEVEL1' if candidate['pair_id'] in accepted
                                 else 'REKOMENDASI_STUDIO')
                scores.append(c)
        else:scores=[]
        l1schema=columns(b,[('nop_padanan','String'),('level','Int'),('metode_padu','String'),
                             ('overlap_pct','Double'),('kesamaan_pct','Double'),('skor_ai','Double')])
        l1schema.extend(('pbb_'+f.name(),f.type()) for f in p.fields() if f.name() not in QA_COLUMNS)
        ll2=[('geom_kosong','Int'),('geom_invalid','Int'),('geom_fixed','Int'),
             ('overlap','Int'),('bid_tambah','Int'),('selisih_luas','Double'),
             ('persen_selisihL','Double'),('level','Int'),('calon_n','Int'),
             ('kode_l2','String'),('alasan_l2','String'),('calon_id','String')]
        paths=[self.persist(layer_from_records(lvl1,b.crs(),l1schema,'Level 1'),
                            '01_padanan_level1',out),
               self.persist(layer_from_records(lvl2b,b.crs(),columns(b,ll2),'BPN Level 2'),
                            '02_bpn_level2',out),
               self.persist(layer_from_records(lvl2p,b.crs(),columns(p,ll2),'PBB Level 2'),
                            '03_pbb_level2',out)]
        stat={'Level 1':len(lvl1),'Level 1 baru dari AI':len(extras),
              'BPN Level 2':len(lvl2b),'PBB Level 2':len(lvl2p),
              'Status AI':meta['status'],'Kandidat AI berskor':len(scores)}
        archive=zip_csv(out,{'skor_kandidat.csv':scores,
                             'pasangan_rule.csv':pairs,'tambahan_ai.csv':extras})
        pdf=report5(out,lvl1,lvl2b,lvl2p,pairs,scores,extras,stat,
                    ['Baseline deterministik Modul 3 dipertahankan.',
                     'AI tanpa evaluasi GOLD independen hanya memberikan rekomendasi studio.',
                     'Ambang skor minimum %.2f, selisih kandidat %.2f.' %
                       (self.val('confidence'),self.val('margin')),
                     'Satu NIB hanya boleh memiliki satu NOP dan sebaliknya.'],meta,logs)
        report={'pdf':pdf,'csv_zip':archive}
        return paths+[report['pdf'],report['csv_zip']]
