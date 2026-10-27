"""Five one-at-a-time QGIS tool dialogs, with layer and field dropdowns."""
import time
from collections import Counter
from pathlib import Path
from qgis.core import QgsVectorLayer
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,QFormLayout,QVBoxLayout,QHBoxLayout,QGroupBox,QPushButton,QComboBox,
    QLineEdit,QCheckBox,QDoubleSpinBox,QLabel,QFileDialog,QMessageBox,QPlainTextEdit,
    QScrollArea,QWidget,QApplication,QProgressDialog)
from .engine import (read,read_pair,fix_geometry,spatial_audit,qa_attribute,columns,
                     layer_from_records,determine_levels,prepare_local,make_candidate_rows,
                     FEATURE_NAMES,internal_overlap,layer_fingerprint,QA_COLUMNS,
                     point_mode,is_point_layer,output_geom_type,level1_record,
                     Progress,NO_PROGRESS,Cancelled,gap_rows_layer,gap_hints)
from .storage import FORMATS,save_layer,zip_csv
from .reporting_full import report1,report2,report3,report3_1,report5
from .logic import ident
from .fieldwidgets import LayerFieldComboBox
from .compat import layer_filter


LEVEL2_EXTRA=[('geom_kosong','Int'),('geom_invalid','Int'),('geom_fixed','Int'),
              ('overlap','Int'),('bid_tambah','Int'),('selisih_luas','Double'),
              ('persen_selisihL','Double'),('level','Int'),('calon_n','Int'),
              ('kode_l2','String'),('alasan_l2','String'),('calon_id','String'),
              ('calon_nama','String'),('skor_gabungan','Double'),('calon_gap','String')]
LEVEL1_EXTRA=[('nop_padanan','String'),('level','Int'),('metode_padu','String'),
              ('overlap_pct','Double'),('kesamaan_pct','Double'),('skor_nama','Double'),
              ('valid_nama','String'),('kekuatan','String'),('skor_gabungan','Double')]
MODULE_TITLES={1:'01 - Audit Kelengkapan',2:'02 - Kualitas Spasial',
               3:'03 - Penentuan level pemaduan berbasis aturan (PBB poligon)',
               31:'03.1 - Penentuan level pemaduan PBB titik (NOP)',
               4:'04 - Training AI',5:'05 - Prediksi AI independen / Hybrid'}


def module_label(modul):
    """Display number: internal id 31 is Modul 3.1."""
    return '3.1' if modul==31 else str(modul)


def name_summary(accepted,names_used):
    """Counts of name validation and strength for accepted Level 1 pairs."""
    out={}
    if names_used:
        states=Counter(r.get('valid_nama') for r in accepted)
        out.update({'Level 1 nama COCOK':states.get('COCOK',0),
                    'Level 1 nama MIRIP':states.get('MIRIP',0),
                    'Level 1 nama TIDAK COCOK':states.get('TIDAK_COCOK',0),
                    'Level 1 nama tidak dapat dinilai':states.get('TIDAK_DINILAI',0)})
        strength=Counter(r.get('kekuatan') for r in accepted)
        out.update({'Kekuatan KUAT':strength.get('KUAT',0),'Kekuatan SEDANG':strength.get('SEDANG',0),
                    'Kekuatan LEMAH':strength.get('LEMAH',0)})
        stage2=sum(1 for r in accepted if r.get('metode_padu')=='RULE_NAMA')
        if stage2:
            out.update({'Level 1 tahap 1 (aturan)':sum(1 for r in accepted
                                                       if r.get('metode_padu') in (None,'','RULE')),
                        'Level 1 tahap 2 (buffer + nama)':stage2})
    return out


def name_notes(options,pmode):
    if not options.get('bpn_name'):
        return ['Validasi nama tidak digunakan; kekuatan padanan tidak dinilai.']
    return ['Validasi nama: %s (BPN) vs %s (PBB); COCOK >= %.0f%%, MIRIP >= %.0f%% '
            '(gelar/sapaan dan ejaan lama dinormalisasi).' %
            (options['bpn_name'],options['pbb_name'],options['name_match'],options['name_partial']),
            ('Nama TIDAK COCOK menurunkan pasangan ke Level 2.' if options.get('require_name') else
             'Nama hanya menentukan kekuatan padanan (KUAT/SEDANG/LEMAH), tidak menggugurkan Level 1.')]+(
            ['Tahap 2: Level 2 (tanpa masalah NIB/NOP kosong/duplikat) dicari ulang dalam buffer %g m; '
             'skor gabungan = %g·nama + %g·spasial + %g·luas tertulis (dinormalisasi). Lolos menjadi '
             'Level 1 (metode RULE_NAMA) bila skor gabungan >= %g, skor nama >= %g, unggul >= %g poin '
             'dari kandidat ke-2 di sisi BPN dan PBB, serta 1:1.' %
             (options['stage2_buffer'],options['w_name'],options['w_spatial'],options['w_area'],
              options['stage2_min'],options['stage2_min_name'],options['stage2_margin'])]
            if options.get('name_stage') else [])


class Selector(QWidget):
    """Layer + unrestricted attribute-field selectors used in Tools 1 to 5."""
    def __init__(self,label,with_area=True, optional=False, with_name=False,
                 kinds=('PolygonLayer','PointLayer')):
        super().__init__()
        layout=QFormLayout(self)
        self.label=label
        theme = 'pbb' if 'pbb' in label.lower() else 'bpn'
        self.layer=QgsMapLayerComboBox()
        # Only vector layers of the expected geometry; a raster has no fields.
        self.layer.setFilters(layer_filter(*kinds))
        self.id=LayerFieldComboBox(theme, 'identity')
        self.area=LayerFieldComboBox(theme, 'area') if with_area else None
        self.name=LayerFieldComboBox(theme, 'name', optional=True) if with_name else None
        self.layer.layerChanged.connect(self.change_layer)
        layout.addRow(label,self.layer)
        layout.addRow('Kolom identitas (semua field):',self.id)
        if with_area:
            layout.addRow('Kolom luas tertulis (semua field):',self.area)
        if with_name:
            self.name.setToolTip('Opsional. Nama pemegang hak (BPN) / wajib pajak (PBB) '
                                 'untuk validasi tambahan kekuatan padanan NIB-NOP.')
            layout.addRow('Kolom nama (opsional, validasi):',self.name)
        self.change_layer(self.layer.currentLayer())

    def change_layer(self,layer):
        self.id.setLayer(layer)
        if self.area is not None:
            self.area.setLayer(layer)
        if self.name is not None:
            self.name.setLayer(layer)

    def name_field(self):
        return self.name.currentField() if self.name is not None else ''

    def values(self):
        return (self.layer.currentLayer(),self.id.currentField(),
                self.area.currentField() if self.area is not None else '')


def spin(value,minimum,maximum,decimals=2):
    s=QDoubleSpinBox();s.setDecimals(decimals);s.setRange(minimum,maximum);s.setValue(value)
    return s


def gap_stats(summary):
    """Report lines for a gap check; ``None`` summary = check not run."""
    if summary is None:
        return {'Pemeriksaan gap':'Tidak dijalankan'}
    return {'Gap terdeteksi':summary['terdeteksi'],'Gap memenuhi luas minimum':summary['layak'],
            'Gap diproses':summary['diproses'],
            'Status pemeriksaan gap':summary['status'].replace('_',' ')}


class GuiProgress(Progress):
    """QProgressDialog with Batal for engine loops (runs in the GUI thread)."""
    def __init__(self,parent,title):
        self.dlg=QProgressDialog('Menyiapkan...','Batal',0,0,parent)
        self.dlg.setWindowTitle(title)
        try:
            self.dlg.setWindowModality(Qt.WindowModality.WindowModal)
        except AttributeError:
            self.dlg.setWindowModality(Qt.WindowModal)
        self.dlg.setMinimumDuration(0);self.dlg.setAutoClose(False);self.dlg.setAutoReset(False)
        self.flag=False;self.last=0.
        self.dlg.canceled.connect(self.cancel)
        self.dlg.show();self.pump(True)
    def cancel(self):self.flag=True
    def pump(self,force=False):
        # Repaint at most ~10x/s so progress does not slow the loops down.
        now=time.monotonic()
        if force or now-self.last>.1:
            self.last=now
            QApplication.processEvents()
    def step(self,label):
        self.dlg.setLabelText(label);self.dlg.setRange(0,0);self.pump(True)
    def update(self,done,total):
        if time.monotonic()-self.last<=.1:return
        if self.dlg.maximum()!=total:self.dlg.setRange(0,max(int(total),0))
        self.dlg.setValue(int(done));self.pump()
    def cancelled(self):
        self.pump()
        return self.flag or self.dlg.wasCanceled()
    def resume(self):
        self.flag=False
        self.dlg.reset();self.dlg.show();self.pump(True)
    def close(self):
        self.dlg.close()


class ToolDialog(QDialog):
    def __init__(self,iface,modul,parent=None):
        super().__init__(parent)
        self.iface=iface;self.modul=modul;self.progress=NO_PROGRESS
        self.setWindowTitle('NIB-NOP | '+MODULE_TITLES[modul]);self.resize(640,750)
        container=QVBoxLayout(self)
        scroll=QScrollArea();scroll.setWidgetResizable(True)
        form_widget=QWidget();self.panel=QVBoxLayout(form_widget)
        scroll.setWidget(form_widget);container.addWidget(scroll)
        names=modul in (3,31,4,5)
        pbb_label={3:'Layer PBB (poligon):',31:'Layer PBB (titik NOP):'}.get(
            modul,'Layer PBB (poligon atau titik):')
        pbb_kinds={3:('PolygonLayer',),31:('PointLayer',)}.get(modul,('PolygonLayer','PointLayer'))
        self.bpn=Selector('Layer BPN (poligon):',with_name=names,kinds=('PolygonLayer',))
        self.pbb=Selector(pbb_label,with_name=names,kinds=pbb_kinds)
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
        self.output=QLineEdit(str(Path.home()/'NIBNOP_HASIL'/('modul_'+module_label(modul).replace('.','_'))))
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
        self.run_button=QPushButton('Jalankan Modul '+module_label(modul))
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
            self.add_spin('gap_area','Minimum luas gap layak periksa (m²):',1,0,1e8)
            self.add_spin('gap_warn','Ambang peringatan jumlah gap (bukan batas):',2500,0,1e9,0)
            self.use_gap=QCheckBox('Delineasi gap tertutup BPN ke layer bpn_kandidat_gap')
            self.use_gap.setChecked(True)
            self.param_form.addRow('',self.use_gap)
        if m==3:
            self.add_spin('overlap','Ambang irisan > (% luas BPN):',50,0,100,1)
        if m in (3,31):
            self.add_spin('sim','Kesamaan luas tertulis > (%):',90,0,100,1)
            self.add_spin('dev','Deviasi luas-geometri maksimum (%):',50,0,500,1)
            self.add_spin('min_irisan','Minimum luas irisan / overlap internal BPN (m²):',.01,0,500,3)
        if m in (3,31):
            self.use_gap=QCheckBox('Sertakan kandidat gap BPN sebagai petunjuk (PBB_DI_ATAS_GAP; '
                                   'tidak ikut pemaduan 1:1)')
            self.use_gap.setToolTip('Gap tertutup BPN disimpan di layer 04_kandidat_gap; PBB Level 2 '
                                    'yang berada di atas gap ditandai sebagai calon bidang belum terdaftar.')
            self.use_gap.setChecked(False)
            self.param_form.addRow('',self.use_gap)
            self.add_spin('min_gap','Minimum luas gap layak periksa (m²):',1,0,1e8)
            self.add_spin('gap_warn','Ambang peringatan jumlah gap (bukan batas):',2500,0,1e9,0)
            for key in ('min_gap','gap_warn'):
                self.param[key].setEnabled(False)
                self.use_gap.toggled.connect(self.param[key].setEnabled)
        if m==31:
            info=QLabel('Modul 3.1 untuk PBB yang hanya tersedia sebagai titik NOP. Gerbang overlap '
                        'diganti "titik NOP berada di dalam bidang BPN"; gerbang identitas, keunikan 1:1 '
                        'dan luas tetap berlaku. Karena bukti spasial titik lebih lemah, gunakan kolom '
                        'nama untuk validasi tambahan kekuatan padanan.')
            info.setWordWrap(True);self.param_form.addRow(info)
            self.add_spin('point_tol','Toleransi titik PBB di luar bidang (m; hanya calon Level 2)'
                          ' / buffer tahap 2:',5,0,1000)
        if m in (3,31,5):
            self.add_spin('name_match','Nama COCOK bila kesamaan nama ≥ (%):',90,0,100,1)
            self.add_spin('name_partial','Nama MIRIP bila kesamaan nama ≥ (%):',60,0,100,1)
        if m in (3,31):
            self.require_name=QCheckBox('Nama TIDAK COCOK menurunkan pasangan ke Level 2 (NAMA_TIDAK_COCOK)')
            self.require_name.setChecked(False)
            self.param_form.addRow('',self.require_name)
        if m in (3,31):
            self.setup_name_stage()
        if m==4:
            from .ai_matching import TRAINING_MODES
            self.training_mode=QComboBox()
            self.training_mode.addItem('GOLD Only (terverifikasi)',TRAINING_MODES[1])
            self.training_mode.addItem('SILVER Only (hasil aturan)',TRAINING_MODES[0])
            self.training_mode.addItem('SILVER + GOLD (gabungan)',TRAINING_MODES[2])
            self.param_form.addRow('Sumber pelatihan:',self.training_mode)
            info=QLabel('Bila kolom nama BPN dan PBB dipilih, model dilatih dengan fitur nama '
                        '(skor_nama, nama_tidak_dinilai; versi fitur QGIS_PLUGIN_V2) dan Modul 5 '
                        'wajib memakai kolom nama juga.')
            info.setWordWrap(True);self.param_form.addRow(info)
            self.silver=self.filepick('Rekap Modul 3 untuk SILVER (ZIP/CSV):',
                                      'ZIP/CSV (*.zip *.csv);;Semua (*)')
            self.name_silver=QCheckBox('Sertakan padanan tahap 2 (RULE_NAMA) dari CSV Modul 3 sebagai silver')
            self.name_silver.setChecked(False)
            self.param_form.addRow('',self.name_silver)
            self.add_spin('name_silver_weight','Bobot silver RULE_NAMA:',.10,0,1.,2)
            self.param['name_silver_weight'].setEnabled(False)
            self.name_silver.toggled.connect(self.param['name_silver_weight'].setEnabled)
            self.gold_features=self.filepick('CSV fitur historis terverifikasi (opsional):')
            self.gold_operator=self.filepick('CSV label operator pada layer yang dipilih (opsional):')
            self.hist_toggle=QCheckBox('Gunakan pasangan GeoJSON historis + CSV label (opsional)')
            self.param_form.addRow(self.hist_toggle)
            self.hist_bpn=Selector('BPN historis:',with_name=True,kinds=('PolygonLayer',))
            self.hist_pbb=Selector('PBB historis:',with_name=True)
            self.hist_bpn.setVisible(False);self.hist_pbb.setVisible(False)
            self.panel.addWidget(self.hist_bpn);self.panel.addWidget(self.hist_pbb)
            self.hist_csv=self.filepick('CSV pasangan historis berlabel:')
            self.hist_toggle.toggled.connect(self.hist_bpn.setVisible)
            self.hist_toggle.toggled.connect(self.hist_pbb.setVisible)
            self.add_spin('radius','Radius pencarian kandidat (meter):',15,0,1000)
            self.add_spin('target','Target precision GOLD:',.99,.5,1.,3)
            self.training_mode.currentIndexChanged.connect(self.update_training_fields)
            self.update_training_fields()
        if m==5:
            self.inference_mode=QComboBox()
            self.inference_mode.addItem('Hybrid: hasil Modul 3 + tambahan AI','HYBRID')
            self.inference_mode.addItem('Full AI: prediksi tanpa aturan Modul 3','AI_ONLY')
            self.param_form.addRow('Mode prediksi:',self.inference_mode)
            self.rule_source=self.filepick('Rekap Modul 3 (Hybrid; ZIP/CSV):',
                                           'ZIP/CSV (*.zip *.csv);;Semua (*)')
            self.inference_mode.currentIndexChanged.connect(self.update_inference_fields)
            self.model=self.filepick('Model terlatih (.joblib):','Joblib (*.joblib);;Semua (*)')
            self.meta=self.filepick('Metadata model (.json):','JSON (*.json);;Semua (*)')
            self.add_spin('radius','Radius kandidat AI (meter):',15,0,1000)
            self.add_spin('confidence','Skor minimum AI:',.90,.5,1.,3)
            self.add_spin('margin','Selisih skor kandidat ke-1 vs ke-2:',.15,0,1.,3)
            self.promote=QCheckBox('Izinkan Level 1 AI otomatis hanya bila model lolos GOLD independen')
            self.param_form.addRow('',self.promote)
            self.promote.setChecked(False)
            info=QLabel('AI menilai kandidat secara independen. Overlap, deviasi luas dan nama adalah '
                        'fitur model, BUKAN gerbang aturan Modul 3. SILVER Only tetap bisa menghasilkan '
                        'USULAN_AI_STUDIO, tetapi tidak diterima otomatis tanpa pengujian GOLD.')
            info.setWordWrap(True);self.param_form.addRow(info)
            self.param_form.addRow(QLabel('PERHATIAN: file model joblib hanya dari sumber yang dipercaya.'))
            self.update_inference_fields()
    def update_training_fields(self,*_):
        mode=self.training_mode.currentData()
        uses_silver=mode in ('SILVER_ONLY','SILVER_GOLD')
        uses_gold=mode in ('GOLD_ONLY','SILVER_GOLD')
        for w in (self.silver,self.name_silver,self.param['name_silver_weight']):
            w.setEnabled(uses_silver)
        self.param['name_silver_weight'].setEnabled(uses_silver and self.name_silver.isChecked())
        for w in (self.gold_features,self.gold_operator,self.hist_toggle,self.hist_csv,self.param['target']):
            w.setEnabled(uses_gold)
        self.hist_bpn.setEnabled(uses_gold)
        self.hist_pbb.setEnabled(uses_gold)
    def update_inference_fields(self,*_):
        self.rule_source.setEnabled(self.inference_mode.currentData()=='HYBRID')
    def setup_name_stage(self):
        """Tahap 2 (Modul 3/3.1/5): buffer search + combined score for Level 2."""
        self.name_stage=QCheckBox('Tahap 2: cari ulang padanan Level 2 dalam buffer dengan skor nama')
        self.name_stage.setToolTip('Memerlukan kolom nama BPN dan PBB. Pasangan yang lolos menjadi '
                                   'Level 1 dengan metode_padu=RULE_NAMA.')
        self.name_stage.setChecked(False)
        self.param_form.addRow('',self.name_stage)
        keys=[]
        if self.modul!=31:
            self.add_spin('stage2_buffer','Buffer tahap 2 di sekitar bidang BPN (m):',5,0,1000);keys.append('stage2_buffer')
        for key,label,default,maxv in (
                ('w_name','Bobot skor nama:',.60,1.),('w_spatial','Bobot skor spasial (jarak):',.25,1.),
                ('w_area','Bobot skor kesamaan luas tertulis:',.15,1.),
                ('stage2_min','Skor gabungan minimum (0-100):',80,100),
                ('stage2_min_name','Skor nama minimum tahap 2 (%):',60,100),
                ('stage2_margin','Selisih minimum dari kandidat ke-2 (poin):',10,100)):
            self.add_spin(key,label,default,0,maxv,2 if maxv==1. else 1);keys.append(key)
        def toggle(on):
            for key in keys:
                self.param[key].setEnabled(on)
                self.param_form.labelForField(self.param[key]).setEnabled(on)
        self.name_stage.toggled.connect(toggle);toggle(False)
    def two_layers(self):
        b,bid,ba=self.bpn.values();p,pid,pa=self.pbb.values()
        if not b or not p or not bid or not pid or not ba or not pa:
            raise ValueError('Pilih layer BPN/PBB serta kolom NIB, NOP dan luas dari dropdown.')
        return b,p,bid,pid,ba,pa
    def opts(self):
        b,p,bid,pid,ba,pa=self.two_layers()
        if self.val('name_partial')>self.val('name_match'):
            raise ValueError('Ambang nama MIRIP tidak boleh melebihi ambang nama COCOK.')
        bname=self.bpn.name_field();pname=self.pbb.name_field()
        if bool(bname)!=bool(pname):
            raise ValueError('Validasi nama memerlukan kolom nama pada BPN dan PBB, '
                             'atau pilih "(tidak digunakan)" pada keduanya.')
        if self.require_name.isChecked() and not bname:
            raise ValueError('Opsi "Nama TIDAK COCOK menurunkan ke Level 2" memerlukan kolom nama BPN dan PBB.')
        stage2={}
        if getattr(self,'name_stage',None) is not None and self.name_stage.isChecked():
            if not bname:
                raise ValueError('Tahap 2 (buffer + skor nama) memerlukan kolom nama BPN dan PBB.')
            if self.val('w_name')+self.val('w_spatial')+self.val('w_area')<=0:
                raise ValueError('Jumlah bobot tahap 2 harus lebih dari 0.')
            stage2={'name_stage':True,
                    'stage2_buffer':self.val('stage2_buffer' if 'stage2_buffer' in self.param else 'point_tol')}
            stage2.update({k:self.val(k) for k in ('w_name','w_spatial','w_area','stage2_min',
                                                   'stage2_min_name','stage2_margin')})
        return dict(stage2,**{'bpn_id':bid,'pbb_id':pid,'bpn_area':ba,'pbb_area':pa,
                'min_overlap':self.val('overlap') if 'overlap' in self.param else 50.,
                'min_sim':self.val('sim'),
                'max_dev':self.val('dev'),'min_irisan':self.val('min_irisan'),
                'bpn_name':bname,'pbb_name':pname,
                'point_tol':self.val('point_tol') if 'point_tol' in self.param else 0.,
                'name_match':self.val('name_match'),'name_partial':self.val('name_partial'),
                'require_name':self.require_name.isChecked()})
    def report_metadata(self,b,p,bid,pid,ba,pa,thresholds=''):
        fp_b=layer_fingerprint(b);fp_p=layer_fingerprint(p)
        return {'layer_bpn':b.name(),'layer_pbb':p.name(),
                'fields_bpn':'%s (identitas), %s (luas)'%(bid,ba),
                'fields_pbb':'%s (identitas), %s (luas)'%(pid,pa),
                'crs':'%s / %s'%(b.crs().authid(),p.crs().authid()),
                'thresholds':thresholds,'hash':'BPN %s · PBB %s'%(fp_b[:12],fp_p[:12])}
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
        self.progress=GuiProgress(self,'Modul '+module_label(self.modul))
        try:
            result=self.execute()
            self.progress.close()
            self.log.appendPlainText('SELESAI\n'+ '\n'.join(result))
            QMessageBox.information(self,'Selesai','Modul %s selesai. Hasil tersimpan pada:\n%s'%(module_label(self.modul),self.output.text()))
        except Cancelled as e:
            self.progress.close()
            self.log.appendPlainText('DIBATALKAN: '+str(e)+' Tidak ada keluaran baru yang ditulis.')
            QMessageBox.information(self,'Dibatalkan','Modul %s dibatalkan; tidak ada keluaran baru yang ditulis.'
                                    % module_label(self.modul))
        except Exception as e:
            import traceback
            self.progress.close()
            self.log.appendPlainText(traceback.format_exc())
            QMessageBox.critical(self,'Gagal menjalankan Modul '+module_label(self.modul),str(e))
        finally:
            self.progress=NO_PROGRESS
            self.run_button.setEnabled(True)
    def execute(self):
        folder=Path(self.output.text()).expanduser();folder.mkdir(parents=True,exist_ok=True)
        if self.modul==1:return self.run1(folder)
        if self.modul==2:return self.run2(folder)
        if self.modul in (3,31):return self.run3(folder)
        if self.modul==4:return self.run4(folder)
        if self.modul==5:return self.run5(folder)
    def run1(self,out):
        b,p,bid,pid,ba,pa=self.two_layers()
        datasets=[];tables={};stats={};charts=[];files=[]
        for layer,tag,idcol,areacol in [(b,'BPN',bid,ba),(p,'PBB',pid,pa)]:
            rows=read(layer,allow_point=(tag=='PBB'))
            datasets.append((rows,idcol,areacol))
            res,detail=qa_attribute(rows,idcol,areacol,self.val('min_area'),self.val('max_area'))
            stats.update({tag+' '+k:v for k,v in res.items()})
            charts.append((tag+' indikator awal',{
                'Kosong':res['identitas_kosong'],'Duplikat':res['record_duplikat'],
                'Luas':res['record_luas_bermasalah']}))
            for k,v in detail.items():tables[tag.lower()+'_'+k]=v
            charts.append((tag+' atribut kosong',{a['nama_kolom']:a['jumlah_kosong'] for a in detail.get('per_kolom_kosong.csv',[])}))
            schema=columns(layer,[('id_kosong','Int'),('id_duplikat','Int'),('luas_flag','String')])
            files.append(self.persist(layer_from_records(rows,layer.crs(),schema,tag+' M1',
                                                         output_geom_type(layer)),
                                      tag.lower()+'_audit_atribut',out))
        archive=zip_csv(out,tables)
        pdf=report1(out,datasets[0],datasets[1],stats,tables,
                    self.val('min_area'),self.val('max_area'),crs=b.crs().authid(),
                    metadata=self.report_metadata(b,p,bid,pid,ba,pa,
                        'Luas %g–%g m²'%(self.val('min_area'),self.val('max_area'))))
        reports={'pdf':pdf,'csv_zip':archive}
        return files+[reports['pdf'],reports['csv_zip']]
    def run2(self,out):
        b,p,bid,pid,ba,pa=self.two_layers()
        b_rows,p_rows,logs=read_pair(b,p,self.reproject.isChecked())
        results=[];tables={};stats={};charts=[];updated_by_tag={}
        gap_rows=[];gap_summary=None
        for rows,layer,tag,idcol,ac,with_gaps in [
            (b_rows,b,'bpn',bid,ba,self.use_gap.isChecked()),
            (p_rows,p,'pbb',pid,pa,False)]:
            updated,ov,gaps,summary,warn=spatial_audit(rows,idcol,ac,self.val('overlap_area'),
                                                       self.val('gap_area'),with_gaps,
                                                       self.val('gap_warn'),self.progress)
            if with_gaps:
                gap_rows,gap_summary=gaps,summary
                results.append(self.persist(gap_rows_layer(gaps,b.crs()),'bpn_kandidat_gap',out))
            updated_by_tag[tag]=updated
            extra=[('geom_kosong','Int'),('geom_invalid','Int'),('geom_fixed','Int'),
                   ('overlap','Int'),('bid_tambah','Int'),('selisih_luas','Double'),
                   ('persen_selisihL','Double'),('gap_id','String')]
            results.append(self.persist(layer_from_records(updated,b.crs(),columns(layer,extra),tag,
                                                           output_geom_type(layer)),
                                        tag+'_kualitas_spasial',out))
            tables[tag+'_overlap.csv']=ov
            tables[tag+'_gap_tertutup.csv']=[g['a'] for g in gaps]
            stats[tag+'_record_awal']=len(rows)
            stats[tag+'_record_akhir']=len(updated)
            for key in ['geom_kosong','geom_invalid','geom_fixed','overlap']:
                stats[tag+'_'+key]=sum(int(r['a'].get(key,0) or 0) for r in updated)
            stats[tag+'_gap_baru']=summary['layak'] if summary else 0
            logs+=warn
            charts.append((tag+' hasil QA',{key:stats[tag+'_'+key] for key in ['geom_kosong','geom_invalid','geom_fixed','overlap']}))
        if point_mode(updated_by_tag['pbb']):
            logs.append('PBB titik: "overlap" PBB berarti titik berimpit (jarak <= 0,01 m); '
                        'perbaikan geometri dan selisih luas geometri tidak berlaku untuk titik.')
        archive=zip_csv(out,tables)
        stats.update(gap_stats(gap_summary))
        gap_notes=(gap_summary['peringatan'] if gap_summary else [])
        pdf=report2(out,updated_by_tag['bpn'],updated_by_tag['pbb'],stats,
                    ['CRS kedua layer diperiksa dan transformasi hanya dilakukan bila diizinkan.',
                     'Geometri invalid diperbaiki bila memungkinkan; geometri kosong tidak direkonstruksi.',
                     'Gap = area kosong tertutup, bukan semua ruang kosong di luar batas bidang; '
                     'disimpan di layer bpn_kandidat_gap, tidak ditambahkan ke layer BPN.',
                     'Irisan overlap internal ditandai; batas persil belum dikoreksi.']+gap_notes+
                    [x for x in logs if x not in gap_notes][:10],
                    tables['bpn_overlap.csv'],tables['pbb_overlap.csv'],
                    tables['bpn_gap_tertutup.csv'],crs=b.crs().authid(),
                    metadata=self.report_metadata(b,p,bid,pid,ba,pa,
                        'Overlap >%g m²; gap >=%g m²'%(self.val('overlap_area'),self.val('gap_area'))),
                    gap_rows=gap_rows,gap_summary=gap_summary)
        reports={'pdf':pdf,'csv_zip':archive}
        return results+[reports['pdf'],reports['csv_zip']]
    def prepare3(self):
        b,p,bid,pid,ba,pa=self.two_layers()
        b_rows,p_rows,logs=read_pair(b,p,self.reproject.isChecked())
        # Matching always runs on source BPN parcels; gaps only on explicit request.
        with_gaps=getattr(self,'use_gap',None) is not None and self.use_gap.isChecked()
        b_rows,ob,gaps,gap_summary,lb=spatial_audit(
            b_rows,bid,ba,self.val('min_irisan'),
            self.val('min_gap') if with_gaps else 1.,with_gaps,
            self.val('gap_warn') if with_gaps else 2500,self.progress)
        p_rows,op,_,_,lp=spatial_audit(p_rows,pid,pa,self.val('min_irisan'),progress=self.progress)
        logs+=lb+lp
        return b,p,b_rows,p_rows,ob,op,(gaps,gap_summary),logs
    def run3(self,out):
        """Modul 3 (PBB poligon) and Modul 3.1 (PBB titik NOP) share one flow."""
        point=self.modul==31
        b,p,bid,pid,ba,pa=self.two_layers()
        if point and not is_point_layer(p):
            raise ValueError('Modul 3.1 khusus PBB berupa titik NOP. Layer PBB "%s" bukan titik; '
                             'gunakan Modul 3 untuk PBB poligon.' % p.name())
        if not point and is_point_layer(p):
            raise ValueError('Layer PBB "%s" berupa titik. Gunakan Modul 3.1 (PBB titik NOP).' % p.name())
        b,p,br,pr,ob,op,(gaps,gap_summary),logs=self.prepare3()
        options=self.opts()
        fp_b,fp_p=layer_fingerprint(b),layer_fingerprint(p)
        level1,level2b,level2p,pairs,accepted=determine_levels(br,pr,options,self.progress)
        on_gap=gap_hints(gaps,level2p,gap_summary,options['min_irisan'],self.progress) if gap_summary else 0
        for pair in pairs:
            pair['src_bpn_sha']=fp_b
            pair['src_pbb_sha']=fp_p
        import json
        tag='modul3_1' if point else 'modul3'
        (out/('manifest_%s.json'%tag)).write_text(json.dumps({'bpn_sha':fp_b,'pbb_sha':fp_p,'input_bpn':b.name(),
                                                              'input_pbb':p.name(),
                                                              'mode_geometri_pbb':'TITIK' if point else 'POLIGON'},
                                                             indent=2),encoding='utf-8')
        bschema=columns(b,LEVEL2_EXTRA)
        pschema=columns(p,LEVEL2_EXTRA)
        joined=columns(b,LEVEL1_EXTRA)
        joined.extend(('pbb_'+f.name(),f.type()) for f in p.fields() if f.name() not in QA_COLUMNS)
        exported=[self.persist(layer_from_records(level1,b.crs(),joined,'Level 1','MultiPolygon'),
                               '01_padanan_level1',out),
                  self.persist(layer_from_records(level2b,b.crs(),bschema,'BPN Level 2','MultiPolygon'),
                               '02_bpn_level2',out),
                  self.persist(layer_from_records(level2p,b.crs(),pschema,'PBB Level 2',
                                                  output_geom_type(p)),
                               '03_pbb_level2',out)]
        if gap_summary:
            exported.append(self.persist(gap_rows_layer(gaps,b.crs()),'04_kandidat_gap',out))
        names_used=bool(options['bpn_name'])
        summary={'Level 1':len(level1),'BPN Level 2':len(level2b),'PBB Level 2':len(level2p)}
        if point:
            summary.update({'Kandidat titik-bidang':len(pairs),
                            'Titik di dalam bidang BPN':sum(1 for a in pairs if a.get('titik_di_dalam')==1)})
        else:
            summary.update({'Pasangan beririsan':len(pairs),
                            'Kandidat > overlap':sum(1 for a in pairs if a['overlap_bpn_pct']>options['min_overlap'])})
        summary.update(name_summary(accepted,names_used))
        summary.update(gap_stats(gap_summary))
        if gap_summary:summary['PBB Level 2 di atas gap']=on_gap
        report_tables={'pasangan_kandidat.csv':pairs,'overlap_bpn.csv':ob,
                       ('titik_berimpit_pbb.csv' if point else 'overlap_pbb.csv'):op,
                       'kandidat_gap.csv':[g['a'] for g in gaps],
                       'alasan_level2.csv':[{'record':row['idx'],
                           'id':row['a'].get(options['bpn_id']),
                           'alasan':row['a'].get('kode_l2'),
                           'calon_nama':row['a'].get('calon_nama'),
                           'skor_gabungan':row['a'].get('skor_gabungan')} for row in level2b]}
        archive=zip_csv(out,report_tables)
        common_notes=['Input wajib dari layer terbaru hasil perbaikan operator.',
                      'Seluruh pemeriksaan kualitas dihitung ulang pada input baru.',
                      'Satu NIB/NOP hanya dapat menerima satu padanan yang lolos ambang.',
                      'Kesamaan luas tertulis harus melewati ambang %.1f%%.' % options['min_sim']]
        if point:
            notes=common_notes[:2]+[
                'Syarat spasial: titik NOP berada di dalam bidang BPN; titik di luar bidang '
                'hingga %.1f m hanya menjadi calon Level 2.' % options['point_tol'],
                'Deviasi luas PBB = luas tertulis PBB terhadap luas geometri BPN yang memuat titik.']+common_notes[2:]
            thresholds='Titik di dalam bidang; toleransi %g m; kesamaan luas >%g%%'%(options['point_tol'],options['min_sim'])
        else:
            notes=common_notes[:2]+['Seleksi overlap terhadap luas geometri BPN menggunakan ambang %.1f%%.' % options['min_overlap']]+common_notes[2:]
            thresholds='Overlap >%g%%; kesamaan luas >%g%%'%(options['min_overlap'],options['min_sim'])
        notes+=name_notes(options,point)
        if options.get('name_stage'):
            thresholds+='; tahap 2 buffer %g m, skor gabungan >=%g'%(options['stage2_buffer'],options['stage2_min'])
        if gap_summary:
            notes+=['Pemaduan memakai bidang BPN sumber. Kandidat gap (>= %g m², layer 04_kandidat_gap) '
                    'hanya menjadi petunjuk: PBB Level 2 di atasnya diberi kode PBB_DI_ATAS_GAP dan '
                    'tidak memengaruhi keunikan 1:1.' % self.val('min_gap')]+gap_summary['peringatan']
        else:
            notes.append('Pemaduan memakai bidang BPN sumber; pemeriksaan gap tidak dijalankan.')
        metadata=self.report_metadata(b,p,options['bpn_id'],options['pbb_id'],
                                      options['bpn_area'],options['pbb_area'],thresholds)
        if point:
            pdf=report3_1(out,level1,level2b,level2p,pairs,summary,notes,logs,bpn_all=br,pbb_all=pr,
                          crs=b.crs().authid(),metadata=metadata,point_tol=options['point_tol'],
                          similarity_threshold=options['min_sim'],names_used=names_used)
        else:
            pdf=report3(out,level1,level2b,level2p,pairs,summary,notes,
                        logs,bpn_all=br,pbb_all=pr,gaps=gaps,crs=b.crs().authid(),metadata=metadata,
                        overlap_threshold=options['min_overlap'],similarity_threshold=options['min_sim'],
                        names_used=names_used)
        return exported+[pdf,archive]
    def ml_names(self,bpn,pbb):
        """Name columns for Modul 4: both or neither."""
        bname=bpn.name_field();pname=pbb.name_field()
        if bool(bname)!=bool(pname):
            raise ValueError('Fitur nama memerlukan kolom nama pada BPN dan PBB, '
                             'atau pilih "(tidak digunakan)" pada keduanya.')
        return bname,pname
    def prepared_ml(self):
        b,p,bid,pid,ba,pa=self.two_layers()
        bname,pname=self.ml_names(self.bpn,self.pbb)
        br,pr,logs=read_pair(b,p,self.reproject.isChecked())
        fix_geometry(br,self.progress);fix_geometry(pr,self.progress)
        internal_overlap(br,.01,progress=self.progress);internal_overlap(pr,.01,progress=self.progress)
        prepare_local(br,bid,ba,50,bname);prepare_local(pr,pid,pa,50,pname)
        return b,p,br,pr,logs
    def run4(self,out):
        from .ml import (labels_for_pairs,add_historical_labeled_features,
                         add_historical_pair_labels,train_model,feature_version)
        from .engine import FEATURE_VERSIONS
        from .ai_matching import training_mode
        from .storage import zip_csv
        from collections import Counter
        silver=[];gold=[];candidates=[];unresolved=[];logs=[]
        mode=self.training_mode.currentData()
        with_silver=mode in ('SILVER_ONLY','SILVER_GOLD')
        with_gold=mode in ('GOLD_ONLY','SILVER_GOLD')
        training_mode(with_silver,with_gold)
        version=feature_version(bool(self.ml_names(self.bpn,self.pbb)[0]))
        features=FEATURE_VERSIONS[version]
        name_weight=(self.val('name_silver_weight') if with_silver and self.name_silver.isChecked()
                     else None)
        _,_,br,pr,logs=self.prepared_ml()
        candidates=make_candidate_rows(br,pr,.01,self.val('radius'),progress=self.progress)
        silver_path=(self.silver.text().strip() or None) if with_silver else None
        if with_silver and not silver_path:
            raise ValueError('Mode %s memerlukan CSV pasangan Modul 3 sebagai sumber SILVER.'%mode)
        if silver_path:
            from .ml import csv_rows
            raw=csv_rows(silver_path)
            if not raw or not all('src_bpn_sha' in v and 'src_pbb_sha' in v for v in raw):
                raise ValueError('CSV Modul 3 harus dibuat oleh plugin ini dengan sidik-jari data operator.')
            exp_b,exp_p=layer_fingerprint(self.bpn.layer.currentLayer()),layer_fingerprint(self.pbb.layer.currentLayer())
            if any(v['src_bpn_sha']!=exp_b or v['src_pbb_sha']!=exp_p for v in raw):
                raise ValueError('Data operator telah berubah sejak Modul 3. Jalankan ulang Modul 3 untuk file terbaru.')
        silver,gold,unresolved=labels_for_pairs(candidates,(self.gold_operator.text().strip() or None)
                                          if with_gold else None,
                                          silver_path,name_silver_weight=name_weight)
        n_hist=add_historical_labeled_features(gold,self.gold_features.text().strip(),features) if with_gold else 0
        if with_gold and self.hist_toggle.isChecked():
            if not self.hist_csv.text().strip():
                raise ValueError('CSV pasangan historis berlabel wajib dipilih bila layer historis diaktifkan.')
            bl,bi,ba=self.hist_bpn.values();pl,pi,pa=self.hist_pbb.values()
            if not (bl and pl and bi and ba and pi and pa):
                raise ValueError('Layer historis dan kolomnya belum lengkap.')
            hbname,hpname=self.ml_names(self.hist_bpn,self.hist_pbb)
            if version=='QGIS_PLUGIN_V2' and not hbname:
                raise ValueError('Model dengan fitur nama memerlukan kolom nama pada layer historis juga.')
            rb,rp,log=read_pair(bl,pl,self.reproject.isChecked())
            fix_geometry(rb);fix_geometry(rp)
            prepare_local(rb,bi,ba,50,hbname);prepare_local(rp,pi,pa,50,hpname)
            hist_candidates=make_candidate_rows(rb,rp,.01,self.val('radius'))
            count=add_historical_pair_labels(gold,hist_candidates,self.hist_csv.text().strip())
            logs.append('Pasangan historis GOLD: %s'%count)
        supplied_gold=with_gold and any((self.gold_operator.text().strip(),self.gold_features.text().strip(),
                                        self.hist_toggle.isChecked() and self.hist_csv.text().strip()))
        if with_gold and not supplied_gold:
            raise ValueError('Mode %s memerlukan GOLD: pilih CSV operator, fitur historis, '
                             'atau pasangan GeoJSON historis berlabel.' % mode)
        if supplied_gold and not gold:
            reasons=Counter(x.get('alasan_penolakan','TIDAK_LOLOS') for x in unresolved)
            raise ValueError('Data GOLD sudah dipilih tetapi 0 pasangan valid/terpetakan. '
                             'Rincian penolakan: %s. Periksa status/bukti verifikasi, '
                             'NOP asli, pasangan dan radius kandidat.' % dict(reasons))
        if unresolved:
            reasons=Counter(x.get('alasan_penolakan','TIDAK_LOLOS') for x in unresolved)
            logs.append('GOLD tidak digunakan: %d baris. Alasan: %s.' %
                        (len(unresolved),dict(reasons)))
        if supplied_gold:
            logs.append('GOLD diterima: %d; GOLD ditolak: %d. Label 1=%d, label 0=%d.' %
                        (len(gold),len(unresolved),sum(x['label']==1 for x in gold),
                         sum(x['label']==0 for x in gold)))
        gold_current_ids={x['pair_id'] for x in gold if x.get('label_source')=='GOLD_OPERATOR'}
        silver=[x for x in silver if x['pair_id'] not in gold_current_ids]
        if with_silver and not silver:
            raise ValueError('CSV Modul 3 tidak menghasilkan label SILVER yang cocok. '
                             'Pastikan ada Level 1 aturan dan kandidat kontras.')
        model,metadata,metrics=train_model(silver,gold,out,self.val('target'),version,
                                           training_mode=mode)
        self.log.appendPlainText('Training selesai: %d GOLD valid, %d GOLD ditolak, '
                                 '%d SILVER; status model %s (testing GOLD: %d).' %
                                 (len(gold),len(unresolved),len(silver),metadata['status'],
                                  metadata['n_testing']))
        logs.append('Versi fitur model: %s (%d fitur%s).'%(version,len(features),
                    ', termasuk nama' if version=='QGIS_PLUGIN_V2' else ''))
        logs.append('Mode pelatihan: %s. SILVER=%d, GOLD=%d.'%(mode,len(silver),len(gold)))
        if name_weight is not None:
            logs.append('Silver RULE_NAMA (tahap 2): %d pasangan, bobot %.2f.'%(
                sum(1 for x in silver if x.get('label_source')=='SILVER_RULE_NAMA'),name_weight))
        import json
        from .ai_pdf import make_training_report
        from .evaluation import threshold_guidance
        evaluation=json.loads((out/'evaluasi_testing_ai.json').read_text(encoding='utf-8'))
        summary={'Mode training':mode,'Kandidat sekarang':len(candidates),'SILVER':len(silver),'GOLD':len(gold),
                 'GOLD ditolak':len(unresolved),
                 'GOLD positif':sum(x['label']==1 for x in gold),
                 'GOLD negatif':sum(x['label']==0 for x in gold),
                 'Grup spasial GOLD':metadata['n_gold_groups'],
                 'GOLD validasi':metadata['n_validation'],
                 'GOLD testing':metadata['n_testing'],
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
        archive=zip_csv(out,{'fitur_kandidat.csv':candidates,'silver_labels.csv':silver,
                     'gold_labels.csv':gold,'gold_ditolak.csv':unresolved,
                     'template_verifikasi_operator.csv':template,
                     'metrik_train_validation_test.csv':metrics,
                     'feature_importance.csv':feature_rows,
                     'panduan_ambang_metrik.csv':threshold_rows,
                     'penilaian_per_metrik.csv':interpret_rows,
                     'rekomendasi_model.csv':recomend_rows})
        pdf=make_training_report(out,evaluation,summary=summary,notes=logs)
        return [str(out/'model_terpilih.joblib'),str(out/'metadata_model.json'),
                str(out/'evaluasi_testing_ai.json'),pdf,archive]
    def run5(self,out):
        """Predict all spatial candidates; import rules only for optional merge.

        No call to ``determine_levels`` and no Modul 3 area/overlap hard gates.
        GOLD-independent validation remains mandatory for automatic Level 1.
        """
        from .ml import predict
        from .ai_matching import load_rule_baseline,select_ai_proposals
        b,p,bid,pid,ba,pa=self.two_layers()
        if self.val('name_partial')>self.val('name_match'):
            raise ValueError('Ambang nama MIRIP tidak boleh melebihi ambang nama COCOK.')
        if not self.model.text().strip() or not self.meta.text().strip():
            raise ValueError('Modul 5 membutuhkan model terlatih (.joblib) DAN metadata model (.json).')
        mode=self.inference_mode.currentData()
        b,p,br,pr,logs=self.prepared_ml()
        refb={r['idx']:r for r in br};refp={r['idx']:r for r in pr}
        bname,pname=self.ml_names(self.bpn,self.pbb)
        baseline=[];pairs=[]
        if mode=='HYBRID':
            path=self.rule_source.text().strip()
            if not path:
                raise ValueError('Mode Hybrid membutuhkan rekap_csv.zip hasil Modul 3 '
                                 '(atau pasangan_kandidat.csv yang sudah diekstrak).')
            baseline,pairs=load_rule_baseline(path,layer_fingerprint(b),layer_fingerprint(p))
            for row in baseline:
                i,j=row['record_bpn'],row['record_pbb']
                if i not in refb or j not in refp:
                    raise ValueError('Indeks record hasil Modul 3 tidak ditemukan pada input BPN/PBB.')
                if (ident(refb[i]['a'].get(bid))!=row['NIB'] or
                        ident(refp[j]['a'].get(pid))!=row['NOP']):
                    raise ValueError('Identitas NIB/NOP hasil Modul 3 tidak cocok dengan layer saat ini.')
            logs.append('Hybrid: %d pasangan aturan diimpor, tanpa menjalankan ulang Modul 3.'%len(baseline))
        else:
            logs.append('Full AI: prediksi independen tanpa membaca atau menjalankan aturan Modul 3.')
        ai_candidates=make_candidate_rows(br,pr,.01,self.val('radius'),
                            name_thresholds=(self.val('name_match'),self.val('name_partial')),
                            progress=self.progress)
        meta=predict(ai_candidates,self.model.text().strip(),self.meta.text().strip())
        tested=meta.get('status')=='GOLD_TESTED_REVIEW_REQUIRED'
        requested=self.promote.isChecked()
        tested_threshold=float(meta.get('threshold',.90))
        if requested and tested and self.val('confidence')+1e-9<tested_threshold:
            raise ValueError('Skor minimum Modul 5 (%.2f) lebih rendah daripada ambang '
                             'yang telah diuji menggunakan GOLD (%.2f). Gunakan minimal %.2f '
                             'untuk penambahan Level 1 otomatis.'%
                             (self.val('confidence'),tested_threshold,tested_threshold))
        allowed=requested and tested
        indices_b=Counter(ident(r['a'].get(bid)) for r in br if ident(r['a'].get(bid)))
        indices_p=Counter(ident(r['a'].get(pid)) for r in pr if ident(r['a'].get(pid)))
        proposals,extras,scores,gate_failures=select_ai_proposals(
            ai_candidates,self.val('confidence'),self.val('margin'),
            indices_b,indices_p,baseline=baseline,allow_promotion=allowed)
        lvl1=[]
        for pair in baseline:
            rb=refb[pair['record_bpn']];rp=refp[pair['record_pbb']]
            lvl1.append(level1_record(rb,rp,pair,pair.get('metode_padu') or 'RULE',
                                       names_used=bool(bname)))
        for pair in extras:
            rb=refb[pair['record_bpn']];rp=refp[pair['record_pbb']]
            pair['metode_padu']='AI_VERIFIED'
            lvl1.append(level1_record(rb,rp,pair,'AI_VERIFIED',pair['skor_ai'],
                                       names_used=bool(bname)))
        occupied_b={row['record_bpn'] for row in baseline+extras}
        occupied_p={row['record_pbb'] for row in baseline+extras}
        best_by_b={}
        for candidate in scores:
            idx=candidate['record_bpn']
            if idx not in occupied_b and idx not in best_by_b:
                best_by_b[idx]=candidate
        def studio_record(source,related=None):
            attrs=dict(source['a'])
            attrs['level']=2
            attrs['kode_l2']='VERIFIKASI_STUDIO_AI'
            attrs['alasan_l2']='Belum ada padanan otomatis yang telah memenuhi syarat penerimaan.'
            if related is not None:
                attrs['calon_n']=1
                attrs['calon_id']=str(related.get('NOP') or '')
                attrs['calon_nama']=str(related.get('valid_nama') or '')
            return {'idx':source['idx'],'fid':source['fid'],'a':attrs,'geom':source['geom']}
        lvl2b=[studio_record(r,best_by_b.get(r['idx'])) for r in br
               if r['idx'] not in occupied_b]
        lvl2p=[studio_record(r) for r in pr if r['idx'] not in occupied_p]
        model_notes=['Mode %s. Model %s: %d usulan AI satu-ke-satu, %d Level 1 AI diterima.'%
                     (mode,meta.get('training_mode','tidak tercatat'),len(proposals),len(extras))]
        if not tested:
            model_notes.append('Model tanpa pengujian GOLD independen yang memenuhi target: '
                               'usulan AI hanya untuk verifikasi studio.')
        elif not requested:
            model_notes.append('Model teruji GOLD, tetapi izin menerima Level 1 otomatis tidak dicentang.')
        if mode=='HYBRID':
            model_notes.append('Pasangan Modul 3 diimpor dari hasil sebelumnya dan tidak diubah oleh AI.')
        model_notes.append('Overlap, deviasi luas, bentuk, jarak, dan nama digunakan sebagai fitur AI, '
                           'bukan sebagai aturan penolakan Level 1.')
        if gate_failures:
            model_notes.append('Kegagalan seleksi kandidat AI (satu kandidat dapat gagal beberapa): %s.'%
                               dict(gate_failures))
        self.log.appendPlainText('Modul 5: %s; %d kandidat diberi skor; %d usulan AI; '
                                 '%d Level 1 AI otomatis.'%
                                 (mode,len(scores),len(proposals),len(extras)))
        l1schema=columns(b,LEVEL1_EXTRA+[('skor_ai','Double')])
        l1schema.extend(('pbb_'+f.name(),f.type()) for f in p.fields() if f.name() not in QA_COLUMNS)
        paths=[self.persist(layer_from_records(lvl1,b.crs(),l1schema,'Level 1','MultiPolygon'),
                            '01_padanan_level1',out),
               self.persist(layer_from_records(lvl2b,b.crs(),columns(b,LEVEL2_EXTRA),'BPN Level 2',
                                               'MultiPolygon'),
                            '02_bpn_level2',out),
               self.persist(layer_from_records(lvl2p,b.crs(),columns(p,LEVEL2_EXTRA),'PBB Level 2',
                                               output_geom_type(p)),
                            '03_pbb_level2',out)]
        # Studio suggestions are separate from accepted Level 1 layers.
        if scores:
            suggestion_rows=[]
            for idx,c in best_by_b.items():
                source=refb[idx]
                attrs=dict(source['a'])
                attrs.update({'nop_kandidat':str(c.get('NOP','')),
                              'skor_ai':c.get('skor_ai'),
                              'keputusan_ai':c.get('keputusan_ai','REKOMENDASI_STUDIO'),
                              'alasan_ai':c.get('alasan_tidak_promosi','') or 'Lolos seluruh gerbang'})
                suggestion_rows.append({'idx':idx,'fid':source['fid'],
                                        'a':attrs,'geom':source['geom']})
            schema=columns(b,[('nop_kandidat','String'),('skor_ai','Double'),
                              ('keputusan_ai','String'),('alasan_ai','String')])
            paths.append(self.persist(layer_from_records(suggestion_rows,b.crs(),schema,
                        'Saran AI untuk verifikasi','MultiPolygon'),
                        '04_rekomendasi_ai_studio',out))
        # Expose proposed one-to-one pairs even for SILVER-only PREVIEW models.
        # They are NOT auto-accepted and remain Level 2 without GOLD tests.
        suggestion_schema=columns(b,[('nop_kandidat','String'),('skor_ai','Double'),
                                   ('keputusan_ai','String'),('alasan_ai','String')])
        proposal_features=[]
        for candidate in proposals:
            source=refb[candidate['record_bpn']]
            attrs=dict(source['a'],nop_kandidat=str(candidate.get('NOP') or ''),
                       skor_ai=candidate['skor_ai'],keputusan_ai=candidate['keputusan_ai'],
                       alasan_ai=candidate.get('alasan_tidak_promosi',''))
            proposal_features.append({'idx':source['idx'],'fid':source['fid'],'a':attrs,
                                      'geom':source['geom']})
        paths.append(self.persist(layer_from_records(proposal_features,b.crs(),suggestion_schema,
                         'Usulan pasangan AI (belum tentu Level 1)','MultiPolygon'),
                         '05_usulan_ai',out))
        baseline_pairs={(r['record_bpn'],r['record_pbb']) for r in baseline}
        used_rule_b={r['record_bpn'] for r in baseline}
        used_rule_p={r['record_pbb'] for r in baseline}
        conflicts=[]
        if mode=='HYBRID':
            recorded=set()
            for candidate in scores:
                i,j=candidate['record_bpn'],candidate['record_pbb']
                if (float(candidate.get('skor_ai') or 0)<self.val('confidence') or
                        (i,j) in baseline_pairs or
                        (i not in used_rule_b and j not in used_rule_p) or i in recorded):
                    continue
                recorded.add(i)
                conflicts.append(candidate)
            conflict_features=[]
            for candidate in conflicts:
                source=refb[candidate['record_bpn']]
                attrs=dict(source['a'],nop_kandidat=str(candidate.get('NOP') or ''),
                           skor_ai=candidate.get('skor_ai'),keputusan_ai='KONFLIK_DENGAN_RULE',
                           alasan_ai='NIB/NOP sudah digunakan pasangan Modul 3')
                conflict_features.append({'idx':source['idx'],'fid':source['fid'],'a':attrs,
                                          'geom':source['geom']})
            paths.append(self.persist(layer_from_records(conflict_features,b.crs(),suggestion_schema,
                         'Konflik prediksi AI dan hasil aturan','MultiPolygon'),
                         '06_konflik_ai_rule',out))
        pmode=point_mode(pr)
        stat={'Mode Modul 5':mode,'Mode training AI':meta.get('training_mode','TIDAK_TERCATAT'),
              'Mode geometri PBB':'Titik NOP' if pmode else 'Poligon PBB',
              'Level 1':len(lvl1),'Level 1 aturan':len(baseline),
              'Level 1 baru dari AI':len(extras),'Usulan AI satu-ke-satu':len(proposals),
              'Konflik Rule-AI untuk studio':len(conflicts),
              'BPN Level 2':len(lvl2b),'PBB Level 2':len(lvl2p),
              'Status AI':meta['status'],'Kandidat AI berskor':len(scores)}
        stat['Promosi AI diizinkan operator']='Ya' if allowed else 'Tidak'
        stat['Bidang dengan rekomendasi AI']=len(best_by_b) if scores else 0
        stat['Penjelasan hasil AI']=model_notes[0]
        stat.update(name_summary(list(baseline)+list(extras),bool(bname)))
        archive=zip_csv(out,{'skor_kandidat.csv':scores,
                             'pasangan_rule.csv':pairs,'tambahan_ai.csv':extras,
                             'usulan_ai.csv':proposals,'konflik_rule_ai.csv':conflicts,
                             'rekap_gerbang_ai.csv':[{'gerbang':key,'jumlah_gagal':v}
                                                    for key,v in sorted(gate_failures.items())]})
        pdf=report5(out,lvl1,lvl2b,lvl2p,pairs,scores,extras,stat,
                    ['Mode %s, tanpa pemanggilan aturan pemaduan Modul 3.'%mode,
                     'Full AI menilai kandidat independen; Hybrid menggabungkan hasil aturan yang diimpor.',
                     'Ambang skor %.2f; margin %.2f; 1 NIB : 1 NOP.' %
                     (self.val('confidence'),self.val('margin'))]+model_notes+
                    (['Model memakai fitur nama (QGIS_PLUGIN_V2): skor_nama dan nama_tidak_dinilai.']
                     if meta.get('feature_version')=='QGIS_PLUGIN_V2' else []),meta,logs,
                    crs=b.crs().authid(),
                    metadata=self.report_metadata(b,p,bid,pid,ba,pa,
                        '%s; skor ≥%.2f; margin ≥%.2f'%(mode,self.val('confidence'),self.val('margin'))))
        report={'pdf':pdf,'csv_zip':archive}
        return paths+[report['pdf'],report['csv_zip']]
