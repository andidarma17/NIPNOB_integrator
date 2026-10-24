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
               4:'04 - Training AI',5:'05 - Inference AI'}


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
    def __init__(self,label,with_area=True, optional=False, with_name=False):
        super().__init__()
        layout=QFormLayout(self)
        self.label=label
        theme = 'pbb' if 'pbb' in label.lower() else 'bpn'
        self.layer=QgsMapLayerComboBox()
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
        self.bpn=Selector('Layer BPN (poligon):',with_name=names)
        self.pbb=Selector(pbb_label,with_name=names)
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
        if m in (3,5):
            self.add_spin('overlap','Ambang irisan > (% luas BPN):',50,0,100,1)
        if m in (3,31,5):
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
        if m in (31,5):
            if m==31:
                info=QLabel('Modul 3.1 untuk PBB yang hanya tersedia sebagai titik NOP. Gerbang overlap '
                            'diganti "titik NOP berada di dalam bidang BPN"; gerbang identitas, keunikan 1:1 '
                            'dan luas tetap berlaku. Karena bukti spasial titik lebih lemah, gunakan kolom '
                            'nama untuk validasi tambahan kekuatan padanan.')
                info.setWordWrap(True);self.param_form.addRow(info)
            self.add_spin('point_tol','Toleransi titik PBB di luar bidang (m; hanya calon Level 2)'
                          +(' - bila PBB titik:' if m==5 else ' / buffer tahap 2:'),5,0,1000)
        if m in (3,31,5):
            self.add_spin('name_match','Nama COCOK bila kesamaan nama ≥ (%):',90,0,100,1)
            self.add_spin('name_partial','Nama MIRIP bila kesamaan nama ≥ (%):',60,0,100,1)
            self.require_name=QCheckBox('Nama TIDAK COCOK menurunkan pasangan ke Level 2 (NAMA_TIDAK_COCOK)')
            self.require_name.setChecked(False)
            self.param_form.addRow('',self.require_name)
        if m in (3,31,5):
            self.setup_name_stage()
        if m==4:
            info=QLabel('Bila kolom nama BPN dan PBB dipilih, model dilatih dengan fitur nama '
                        '(skor_nama, nama_tidak_dinilai; versi fitur QGIS_PLUGIN_V2) dan Modul 5 '
                        'wajib memakai kolom nama juga.')
            info.setWordWrap(True);self.param_form.addRow(info)
            self.silver=self.filepick('CSV kandidat Modul 3 (silver):')
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
            self.hist_bpn=Selector('BPN historis:',with_name=True)
            self.hist_pbb=Selector('PBB historis:',with_name=True)
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
        from .storage import zip_csv
        from collections import Counter
        silver=[];gold=[];candidates=[];unresolved=[];logs=[]
        version=feature_version(bool(self.ml_names(self.bpn,self.pbb)[0]))
        features=FEATURE_VERSIONS[version]
        name_weight=self.val('name_silver_weight') if self.name_silver.isChecked() else None
        try:
            _,_,br,pr,logs=self.prepared_ml()
            candidates=make_candidate_rows(br,pr,.01,self.val('radius'),progress=self.progress)
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
                                              silver_path,name_silver_weight=name_weight)
        except ValueError:
            # May train from an external fully labelled feature CSV only; don't hide
            # other failures when source layers were supplied.
            if not self.gold_features.text().strip():raise
        n_hist=add_historical_labeled_features(gold,self.gold_features.text().strip(),features)
        if self.hist_toggle.isChecked():
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
        gold_current_ids={x['pair_id'] for x in gold if x.get('label_source')=='GOLD_OPERATOR'}
        silver=[x for x in silver if x['pair_id'] not in gold_current_ids]
        model,metadata,metrics=train_model(silver,gold,out,self.val('target'),version)
        logs.append('Versi fitur model: %s (%d fitur%s).'%(version,len(features),
                    ', termasuk nama' if version=='QGIS_PLUGIN_V2' else ''))
        if name_weight is not None:
            logs.append('Silver RULE_NAMA (tahap 2): %d pasangan, bobot %.2f.'%(
                sum(1 for x in silver if x.get('label_source')=='SILVER_RULE_NAMA'),name_weight))
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
        archive=zip_csv(out,{'fitur_kandidat.csv':candidates,'silver_labels.csv':silver,
                     'gold_labels.csv':gold,'template_verifikasi_operator.csv':template,
                     'metrik_train_validation_test.csv':metrics,
                     'feature_importance.csv':feature_rows,
                     'panduan_ambang_metrik.csv':threshold_rows,
                     'penilaian_per_metrik.csv':interpret_rows,
                     'rekomendasi_model.csv':recomend_rows})
        pdf=make_training_report(out,evaluation,summary=summary,notes=logs)
        return [str(out/'model_terpilih.joblib'),str(out/'metadata_model.json'),
                str(out/'evaluasi_testing_ai.json'),pdf,archive]
    def run5(self,out):
        from .ml import predict
        b,p,br,pr,ob,op,_,logs=self.prepare3()
        opts=self.opts()
        lvl1,lvl2b,lvl2p,pairs,baseline=determine_levels(br,pr,opts,self.progress)
        refb={r['idx']:r for r in br};refp={r['idx']:r for r in pr}
        extras=[];meta={'status':'NO_MODEL'}
        if self.model.text().strip() or self.meta.text().strip():
            if not self.model.text().strip() or not self.meta.text().strip():
                raise ValueError('Isi path model dan metadata secara bersamaan.')
            ai_candidates=make_candidate_rows(br,pr,opts['min_irisan'],self.val('radius'),
                                              name_thresholds=(opts['name_match'],opts['name_partial']),
                                              progress=self.progress)
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
                idb=refb[i]['a']['_id_field_value'];idp=refp[j]['a']['_id_field_value']
                competitor_b=max([x['skor_ai'] for x in byb[i] if x['record_pbb']!=j] or [0.])
                competitor_p=max([x['skor_ai'] for x in byp[j] if x['record_bpn']!=i] or [0.])
                gates={
                    'model':meta['status']=='GOLD_TESTED_REVIEW_REQUIRED' and self.promote.isChecked(),
                    'skor':score>=self.val('confidence'),
                    'id_unik':bool(idb and idp and indices_b[idb]==1 and indices_p[idp]==1),
                    'overlap':not (refb[i]['a'].get('overlap') or refp[j]['a'].get('overlap')),
                    'deviasi':(r['deviasi_luas_bpn'] is not None and r['deviasi_luas_pbb'] is not None and
                               r['deviasi_luas_bpn']<=opts['max_dev'] and r['deviasi_luas_pbb']<=opts['max_dev']),
                    'margin':score-max(competitor_b,competitor_p)>=self.val('margin'),
                    'pesaing':competitor_b<self.val('confidence') and competitor_p<self.val('confidence'),
                    'tersedia':i not in occupied_b and j not in occupied_p,
                    'nama':not (opts['require_name'] and r.get('valid_nama')=='TIDAK_COCOK')}
                r.update({'gerbang_'+key:'Lolos' if passed else 'Perlu telaah'
                          for key,passed in gates.items()})
                r['alasan_tidak_promosi']='; '.join(key.replace('_',' ') for key,passed in gates.items() if not passed)
                if not all(gates.values()):continue
                occupied_b.add(i);occupied_p.add(j);r['metode_padu']='AI_VERIFIED'
                extras.append(r)
            if extras:
                # Build output for AI extras; baseline protected.
                for r in extras:
                    rb=refb[r['record_bpn']];rp=refp[r['record_pbb']]
                    lvl1.append(level1_record(rb,rp,r,'AI_VERIFIED',r['skor_ai'],
                                              names_used=bool(opts['bpn_name'])))
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
        pmode=point_mode(pr)
        stat={'Mode geometri PBB':'Titik (aturan Modul 3.1)' if pmode else 'Poligon (aturan Modul 3)',
              'Level 1':len(lvl1),'Level 1 baru dari AI':len(extras),
              'BPN Level 2':len(lvl2b),'PBB Level 2':len(lvl2p),
              'Status AI':meta['status'],'Kandidat AI berskor':len(scores)}
        stat.update(name_summary(list(baseline)+list(extras),bool(opts['bpn_name'])))
        archive=zip_csv(out,{'skor_kandidat.csv':scores,
                             'pasangan_rule.csv':pairs,'tambahan_ai.csv':extras})
        pdf=report5(out,lvl1,lvl2b,lvl2p,pairs,scores,extras,stat,
                    ['Baseline deterministik %s dipertahankan.' % ('Modul 3.1 (PBB titik)' if pmode else 'Modul 3'),
                     'AI tanpa evaluasi GOLD independen hanya memberikan rekomendasi studio.',
                     'Ambang skor minimum %.2f, selisih kandidat %.2f.' %
                       (self.val('confidence'),self.val('margin')),
                     'Satu NIB hanya boleh memiliki satu NOP dan sebaliknya.']+name_notes(opts,pmode)+
                    (['Model memakai fitur nama (QGIS_PLUGIN_V2): skor_nama dan nama_tidak_dinilai.']
                     if meta.get('feature_version')=='QGIS_PLUGIN_V2' else []),meta,logs,
                    crs=b.crs().authid(),
                    metadata=self.report_metadata(b,p,opts['bpn_id'],opts['pbb_id'],
                        opts['bpn_area'],opts['pbb_area'],
                        'Skor ≥%.2f; margin ≥%.2f'%(self.val('confidence'),self.val('margin'))))
        report={'pdf':pdf,'csv_zip':archive}
        return paths+[report['pdf'],report['csv_zip']]
