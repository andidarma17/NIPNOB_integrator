"""Processing provider: the seven tools (Modul 1, 2, 3, 3.1, 4, 5, 6).

Modul 1-5 and 3.1 use the standard Processing form everywhere (Toolbox, Vector menu,
Batch, Modeler, ``processing.run``, ``qgis_process``): label above each input, one
destination per spatial output (with "Open output file after running"), one folder for
the PDF report, the CSV zip and the other files, and a switch to skip every output.
``HeadlessTool`` borrows the ``run1``..``run5`` orchestration of ``dialogs.ToolDialog``
and feeds it those parameters through small stand-ins for the dialog widgets, so the
matching rules, outputs and PDF reports stay identical to earlier versions. Modul 6 is
interactive on the map (it opens the studio dock) and has no headless run.

v0.9.9: Modul 4 (SILVER Only / GOLD Only / SILVER + GOLD) and Modul 5 (Full AI or Hybrid)
expose the same choices as the v0.9.8 backend (``ml.py``, ``ai_matching.py``).
"""
import shutil
import tempfile
from pathlib import Path
from qgis.core import (Qgis, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingContext,
                       QgsProcessingException, QgsProcessingParameterBoolean,
                       QgsProcessingParameterEnum, QgsProcessingParameterField,
                       QgsProcessingParameterFile, QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterNumber, QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterVectorLayer, QgsProcessingProvider)
from .engine import Progress, Cancelled
from .storage import save_layer_to
from .ai_matching import TRAINING_MODES, INFERENCE_MODES


def _enum(new, old):
    """Qgis.* scoped enum on QGIS >= 3.36 / 4, QgsProcessing* constant before."""
    owner, name = new
    try:
        return getattr(getattr(Qgis, owner), name)
    except AttributeError:
        return old


POLYGON = _enum(('ProcessingSourceType', 'VectorPolygon'), getattr(QgsProcessing, 'TypeVectorPolygon', 2))
POINT = _enum(('ProcessingSourceType', 'VectorPoint'), getattr(QgsProcessing, 'TypeVectorPoint', 0))
DOUBLE = _enum(('ProcessingNumberParameterType', 'Double'),
               getattr(QgsProcessingParameterNumber, 'Double', 1))
NO_THREADING = _enum(('ProcessingAlgorithmFlag', 'NoThreading'),
                     getattr(QgsProcessingAlgorithm, 'FlagNoThreading', 4))
HIDE_FROM_MODELER = _enum(('ProcessingAlgorithmFlag', 'HideFromModeler'),
                          getattr(QgsProcessingAlgorithm, 'FlagHideFromModeler', 2))
FILE_TYPE = _enum(('ProcessingFileParameterBehavior', 'File'),
                  getattr(QgsProcessingParameterFile, 'File', 0))

ANY_GEOMETRY = _enum(('ProcessingSourceType', 'VectorAnyGeometry'),
                     getattr(QgsProcessing, 'TypeVectorAnyGeometry', -1))

# Conventional column names, selected when present (same idea as fieldwidgets.PREFERRED_FIELDS).
DEFAULT_FIELDS = {'BPN_ID': 'NIB', 'BPN_AREA': 'LUAS', 'PBB_ID': 'D_NOP', 'PBB_AREA': 'D_LUAS'}

# Same keys, labels and defaults as ToolDialog.setup_module / setup_name_stage.
# ('n', key, label, default, min, max, decimals) | ('b', key, label, default)
# | ('f', key, label, file filter) | ('s', key, label) = historical layer selector
NAME_STAGE = [('b', 'name_stage', 'Tahap 2: cari ulang padanan Level 2 dalam buffer dengan skor nama '
                                  '(memerlukan kolom nama BPN dan PBB)', False)]
STAGE2_WEIGHTS = [('n', 'w_name', 'Tahap 2 - bobot skor nama', .60, 0, 1., 2),
                  ('n', 'w_spatial', 'Tahap 2 - bobot skor spasial (jarak)', .25, 0, 1., 2),
                  ('n', 'w_area', 'Tahap 2 - bobot skor kesamaan luas tertulis', .15, 0, 1., 2),
                  ('n', 'stage2_min', 'Tahap 2 - skor gabungan minimum (0-100)', 80, 0, 100, 1),
                  ('n', 'stage2_min_name', 'Tahap 2 - skor nama minimum (%)', 60, 0, 100, 1),
                  ('n', 'stage2_margin', 'Tahap 2 - selisih minimum dari kandidat ke-2 (poin)', 10, 0, 100, 1)]
STAGE2_BUFFER = [('n', 'stage2_buffer', 'Tahap 2 - buffer di sekitar bidang BPN (m)', 5, 0, 1000, 2)]
RULES = [('n', 'sim', 'Kesamaan luas tertulis > (%)', 90, 0, 100, 1),
         ('n', 'dev', 'Deviasi luas-geometri maksimum (%)', 50, 0, 500, 1),
         ('n', 'min_irisan', 'Minimum luas irisan / overlap internal BPN (m²)', .01, 0, 500, 3)]
OVERLAP = [('n', 'overlap', 'Ambang irisan > (% luas BPN)', 50, 0, 100, 1)]
GAPS = [('b', 'use_gap', 'Sertakan kandidat gap BPN sebagai petunjuk (PBB_DI_ATAS_GAP; '
                         'tidak ikut pemaduan 1:1)', False),
        ('n', 'min_gap', 'Minimum luas gap layak periksa (m²) - bila gap disertakan', 1, 0, 1e8, 2),
        ('n', 'gap_warn', 'Ambang peringatan jumlah gap (bukan batas)', 2500, 0, 1e9, 0)]
NAMES = [('n', 'name_match', 'Nama COCOK bila kesamaan nama ≥ (%)', 90, 0, 100, 1),
         ('n', 'name_partial', 'Nama MIRIP bila kesamaan nama ≥ (%)', 60, 0, 100, 1),
         ('b', 'require_name', 'Nama TIDAK COCOK menurunkan pasangan ke Level 2 (NAMA_TIDAK_COCOK)', False)]
POINT_TOL_3_1 = [('n', 'point_tol', 'Toleransi titik PBB di luar bidang (m; hanya calon Level 2) '
                                    '/ buffer tahap 2', 5, 0, 1000, 2)]
POINT_TOL_5 = [('n', 'point_tol', 'Toleransi titik PBB di luar bidang (m; hanya calon Level 2) '
                                  '- bila PBB titik', 5, 0, 1000, 2)]

CSV = 'CSV (*.csv);;Semua (*)'
ZIP_CSV = 'ZIP/CSV (*.zip *.csv);;Semua (*)'
# ('e', key, label, [(value, display), ...], default index) = combo box; the first item is
# the default, in the same order as the dialog's combo boxes.
TRAINING_CHOICES = [(TRAINING_MODES[1], 'GOLD Only (terverifikasi)'),
                    (TRAINING_MODES[0], 'SILVER Only (hasil aturan)'),
                    (TRAINING_MODES[2], 'SILVER + GOLD (gabungan)')]
INFERENCE_CHOICES = [(INFERENCE_MODES[0], 'Hybrid: hasil Modul 3 + tambahan AI'),
                     (INFERENCE_MODES[1], 'Full AI: prediksi tanpa aturan Modul 3')]
MODULES = {
    1: dict(name='modul_1_kelengkapan', title='1. Pemeriksaan kelengkapan', pbb=(POLYGON, POINT),
            names=False, reproject=False,
            params=[('n', 'min_area', 'Luas minimum pemeriksaan (m²)', 5, 0, 1e9, 2),
                    ('n', 'max_area', 'Luas maksimum pemeriksaan (m²)', 10000, 1, 1e12, 2)]),
    2: dict(name='modul_2_kualitas_spasial', title='2. Kualitas spasial dan fix geometry',
            pbb=(POLYGON, POINT), names=False, reproject=True,
            params=[('n', 'overlap_area', 'Minimum luas overlap internal (m²)', .01, 0, 10000, 3),
                    ('n', 'gap_area', 'Minimum luas gap layak periksa (m²)', 1, 0, 1e8, 2),
                    ('n', 'gap_warn', 'Ambang peringatan jumlah gap (bukan batas)', 2500, 0, 1e9, 0),
                    ('b', 'use_gap', 'Delineasi gap tertutup BPN ke layer bpn_kandidat_gap', True)]),
    3: dict(name='modul_3_pemaduan_aturan', title='3. Penentuan level pemaduan berbasis aturan (PBB poligon)',
            pbb=(POLYGON,), names=True, reproject=True,
            params=OVERLAP+RULES+GAPS+NAMES+NAME_STAGE+STAGE2_BUFFER+STAGE2_WEIGHTS),
    31: dict(name='modul_3_1_pemaduan_titik', title='3.1 Penentuan level pemaduan PBB titik (NOP)',
             pbb=(POINT,), names=True, reproject=True,
             params=RULES+GAPS+POINT_TOL_3_1+NAMES+NAME_STAGE+STAGE2_WEIGHTS),
    # Modul 4 needs the current BPN/PBB layers in every mode (features are extracted from them);
    # which of SILVER / GOLD is required follows the training mode and is checked by run4.
    4: dict(name='modul_4_training_ai', title='4. Training AI', pbb=(POLYGON, POINT), names=True,
            reproject=True,
            params=[('e', 'training_mode', 'Sumber pelatihan', TRAINING_CHOICES),
                    ('f', 'silver', 'Rekap Modul 3 untuk SILVER (ZIP/CSV) - SILVER Only / SILVER + GOLD',
                     ZIP_CSV),
                    ('b', 'name_silver', 'Sertakan padanan tahap 2 (RULE_NAMA) dari CSV Modul 3 sebagai silver',
                     False),
                    ('n', 'name_silver_weight', 'Bobot silver RULE_NAMA', .10, 0, 1., 2),
                    ('f', 'gold_features', 'CSV fitur historis terverifikasi (opsional) - GOLD', CSV),
                    ('f', 'gold_operator', 'CSV label operator pada layer yang dipilih (opsional) - GOLD', CSV),
                    ('b', 'hist_toggle', 'Gunakan pasangan GeoJSON historis + CSV label (opsional) - GOLD',
                     False),
                    ('s', 'hist_bpn', 'BPN historis'),
                    ('s', 'hist_pbb', 'PBB historis'),
                    ('f', 'hist_csv', 'CSV pasangan historis berlabel', CSV),
                    ('n', 'radius', 'Radius pencarian kandidat (meter)', 15, 0, 1000, 2),
                    ('n', 'target', 'Target precision GOLD', .99, .5, 1., 3)]),
    # Modul 5 (v0.9.8): the AI scores candidates independently; overlap, area deviation and
    # name are model features, not Modul 3 gates, so only the name thresholds remain.
    5: dict(name='modul_5_inference_ai', title='5. Prediksi AI independen / Hybrid', pbb=(POLYGON, POINT),
            names=True, reproject=True,
            params=[('e', 'inference_mode', 'Mode prediksi', INFERENCE_CHOICES),
                    ('f', 'rule_source', 'Rekap Modul 3 (ZIP/CSV) - wajib untuk mode Hybrid', ZIP_CSV),
                    ('f', 'model', 'Model terlatih (.joblib) - hanya dari sumber yang dipercaya',
                     'Joblib (*.joblib);;Semua (*)'),
                    ('f', 'meta', 'Metadata model (.json)', 'JSON (*.json);;Semua (*)'),
                    ('n', 'name_match', 'Nama COCOK bila kesamaan nama ≥ (%)', 90, 0, 100, 1),
                    ('n', 'name_partial', 'Nama MIRIP bila kesamaan nama ≥ (%)', 60, 0, 100, 1),
                    ('n', 'radius', 'Radius kandidat AI (meter)', 15, 0, 1000, 2),
                    ('n', 'confidence', 'Skor minimum AI', .90, .5, 1., 3),
                    ('n', 'margin', 'Selisih skor kandidat ke-1 vs ke-2', .15, 0, 1., 3),
                    ('b', 'promote', 'Izinkan Level 1 AI otomatis hanya bila model lolos GOLD independen',
                     False)]),
}


_LEVELS = [('01_padanan_level1', 'Output layer Level 1 (padanan BPN-PBB)'),
           ('02_bpn_level2', 'Output layer BPN Level 2'),
           ('03_pbb_level2', 'Output layer PBB Level 2')]
# Spatial outputs per module: (basename used by dialogs.persist, label). Each becomes its own
# optional destination parameter OUT_<BASENAME>.
OUTPUT_LAYERS = {
    1: [('bpn_audit_atribut', 'Output layer BPN audit'), ('pbb_audit_atribut', 'Output layer PBB audit')],
    2: [('bpn_kualitas_spasial', 'Output layer BPN kualitas spasial'),
        ('pbb_kualitas_spasial', 'Output layer PBB kualitas spasial'),
        ('bpn_kandidat_gap', 'Output layer kandidat gap BPN (hanya bila delineasi gap dicentang)')],
    3: _LEVELS+[('04_kandidat_gap', 'Output layer kandidat gap BPN (hanya bila gap disertakan)')],
    31: _LEVELS+[('04_kandidat_gap', 'Output layer kandidat gap BPN (hanya bila gap disertakan)')],
    4: [],
    5: _LEVELS+[('04_rekomendasi_ai_studio', 'Output layer rekomendasi AI untuk studio'),
                ('05_usulan_ai', 'Output layer usulan pasangan AI (belum tentu Level 1)'),
                ('06_konflik_ai_rule', 'Output layer konflik AI vs aturan (hanya mode Hybrid)')],
}
FOLDER_LABELS = {
    1: 'Folder hasil (PDF laporan & ZIP rekap CSV)',
    2: 'Folder hasil (PDF laporan & ZIP rekap CSV)',
    3: 'Folder hasil (PDF laporan, ZIP rekap CSV & manifest)',
    31: 'Folder hasil (PDF laporan, ZIP rekap CSV & manifest)',
    4: 'Folder hasil (model .joblib, metadata, PDF laporan & ZIP rekap CSV)',
    5: 'Folder hasil (PDF laporan & ZIP rekap CSV)',
}
SKIP_LABEL = ('Lewati semua keluaran (uji coba: hanya menghitung dan menulis ringkasan ke log; '
              'tidak ada file yang disimpan dan tidak ada layer yang dimuat)')


def output_param(basename):
    return 'OUT_'+basename.upper()


def default_folder(modul):
    return str(Path.home()/'NIBNOP_HASIL'/('modul_'+('3_1' if modul == 31 else str(modul))))


class _Value:
    """Stand-in for a dialog widget: spin ``value()``, line ``text()``, check ``isChecked()``."""
    def __init__(self, v):self.v = v
    def value(self):return self.v
    def text(self):return self.v or ''
    def isChecked(self):return bool(self.v)
    def currentText(self):return self.v
    def currentData(self):return self.v
    def currentLayer(self):return self.v


class _Selector:
    """Stand-in for ``dialogs.Selector``."""
    def __init__(self, layer, id_field, area_field, name_field=''):
        self.layer = _Value(layer)
        self.fields = (id_field or '', area_field or '')
        self.name = name_field or ''
    def values(self):
        return (self.layer.currentLayer(),)+self.fields
    def name_field(self):
        return self.name


class _Log:
    """Stand-in for the dialog's log box (run4/run5 write notes to it)."""
    def __init__(self, feedback):self.feedback = feedback
    def appendPlainText(self, text):self.feedback.pushInfo(str(text))
    def clear(self):pass


class FeedbackProgress(Progress):
    """engine.Progress on a QgsProcessingFeedback: progress bar, log and Cancel."""
    def __init__(self, feedback):self.feedback = feedback
    def step(self, label):
        self.feedback.setProgressText(label)
    def update(self, done, total):
        if total:self.feedback.setProgress(100.*done/total)
    def cancelled(self):return self.feedback.isCanceled()


_BORROWED = ('two_layers', 'opts', 'report_metadata', 'execute', 'run1', 'run2', 'prepare3', 'run3',
             'ml_names', 'prepared_ml', 'run4', 'run5')


class HeadlessTool:
    """ToolDialog without widgets; run methods are borrowed on first use."""
    def __init__(self, modul, values, output, resolve, feedback, skip=False):
        """``resolve(basename)`` returns the destination file of a spatial output ('' = skipped)."""
        if not hasattr(HeadlessTool, 'run1'):
            from .dialogs import ToolDialog
            for name in _BORROWED:
                setattr(HeadlessTool, name, getattr(ToolDialog, name))
        self.modul = modul;self.feedback = feedback
        self.progress = FeedbackProgress(feedback);self.log = _Log(feedback)
        self.output = _Value(str(output));self.resolve = resolve;self.skip = skip
        self.param = {};self.saved = []
        for key, value in values.items():
            if isinstance(value, _Selector) or key in ('bpn', 'pbb'):
                setattr(self, key, value)
            elif isinstance(value, float):
                self.param[key] = _Value(value)
            else:
                setattr(self, key, _Value(value))

    def val(self, key):return self.param[key].value()

    def persist(self, layer, basename, output):
        destination = '' if self.skip else self.resolve(basename)
        if not destination:
            self.feedback.pushInfo('Keluaran dilewati: %s' % basename)
            return '(dilewati) %s' % basename
        if str(destination).lower().endswith('.shp'):
            self.feedback.pushWarning('Shapefile dapat memotong nama atribut menjadi 10 karakter dan '
                                      'menyebabkan tabrakan kolom (%s). GeoPackage disarankan.' % basename)
        saved = save_layer_to(layer, destination, basename)
        self.saved.append((basename, saved))
        return saved


class NibNopAlgorithm(QgsProcessingAlgorithm):
    SKIP_OUTPUT = 'SKIP_OUTPUT'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'

    def __init__(self, modul):
        super().__init__()
        self.modul = modul;self.spec = MODULES[modul]

    def createInstance(self):return NibNopAlgorithm(self.modul)
    def name(self):return self.spec['name']
    def displayName(self):return self.spec['title']
    def group(self):return 'NIB-NOP Integrator'
    def groupId(self):return 'nib_nop_integrator'
    def flags(self):
        # Layers and reports are read/painted on the main thread (Qt printing, layer access).
        return super().flags() | NO_THREADING
    def shortHelpString(self):
        return ('%s\n\nKeluaran: setiap layer spasial punya tujuan sendiri (kosongkan = file sementara, '
                '"Skip Output" = dilewati, centang "Open output file" untuk memuatnya). Folder hasil '
                'menampung laporan PDF, rekap_csv.zip dan berkas lain. "Lewati semua keluaran" '
                'menjalankan perhitungan tanpa menyimpan apa pun.' % self.spec['title'])

    def add_layer(self, prefix, label, types, short, optional=False, with_area=True, with_name=False):
        """Layer, then its field choices; every label sits above its input in the form."""
        self.addParameter(QgsProcessingParameterVectorLayer(prefix, label, list(types), optional=optional))
        self.addParameter(QgsProcessingParameterField(
            prefix+'_ID', 'Kolom identitas '+short, defaultValue=DEFAULT_FIELDS.get(prefix+'_ID'),
            parentLayerParameterName=prefix, optional=optional))
        if with_area:
            self.addParameter(QgsProcessingParameterField(
                prefix+'_AREA', 'Kolom luas tertulis '+short, defaultValue=DEFAULT_FIELDS.get(prefix+'_AREA'),
                parentLayerParameterName=prefix, optional=optional))
        if with_name:
            self.addParameter(QgsProcessingParameterField(
                prefix+'_NAME', 'Kolom nama %s (opsional, untuk validasi nama)' % short,
                parentLayerParameterName=prefix, optional=True))

    def initAlgorithm(self, config=None):
        spec = self.spec;optional = spec.get('optional_layers', False)
        pbb_label = {3:'Layer PBB (poligon)', 31:'Layer PBB (titik NOP)'}.get(self.modul,
                                                                              'Layer PBB (poligon atau titik)')
        self.add_layer('BPN', 'Layer BPN (poligon)', (POLYGON,), 'BPN', optional, with_name=spec['names'])
        self.add_layer('PBB', pbb_label, spec['pbb'], 'PBB', optional, with_name=spec['names'])
        if spec['reproject']:
            self.addParameter(QgsProcessingParameterBoolean(
                'REPROJECT', 'Jika CRS berbeda, reproyeksikan PBB sementara ke CRS BPN', defaultValue=False))
        for item in spec['params']:
            kind, key, label = item[:3]
            if kind == 'n':
                default, minimum, maximum, _ = item[3:]
                self.addParameter(QgsProcessingParameterNumber(key.upper(), label, DOUBLE, default,
                                                               False, minimum, maximum))
            elif kind == 'b':
                self.addParameter(QgsProcessingParameterBoolean(key.upper(), label, defaultValue=item[3]))
            elif kind == 'f':
                self.addParameter(QgsProcessingParameterFile(key.upper(), label, FILE_TYPE,
                                                             fileFilter=item[3], optional=True))
            elif kind == 'e':
                self.addParameter(QgsProcessingParameterEnum(key.upper(), label, [d for _, d in item[3]],
                                                             defaultValue=0))
            elif kind == 's':
                short = 'BPN historis' if key == 'hist_bpn' else 'PBB historis'
                self.add_layer(key.upper(), label, (POLYGON,) if key == 'hist_bpn' else (POLYGON, POINT),
                               short, optional=True, with_name=True)
        # Outputs: skip switch, one folder (PDF + CSV zip + other files), one destination per layer.
        self.addParameter(QgsProcessingParameterBoolean(self.SKIP_OUTPUT, SKIP_LABEL, defaultValue=False))
        self.addParameter(QgsProcessingParameterFolderDestination(
            self.OUTPUT_FOLDER, FOLDER_LABELS[self.modul], defaultValue=default_folder(self.modul),
            optional=True))
        for basename, label in OUTPUT_LAYERS[self.modul]:
            self.addParameter(QgsProcessingParameterVectorDestination(
                output_param(basename), label, ANY_GEOMETRY, optional=True))

    def selector(self, prefix, parameters, context):
        def field(suffix):
            name = prefix+suffix
            if self.parameterDefinition(name) is None:return ''
            return self.parameterAsString(parameters, name, context) or ''
        return _Selector(self.parameterAsVectorLayer(parameters, prefix, context),
                         field('_ID'), field('_AREA'), field('_NAME'))

    def checkParameterValues(self, parameters, context):
        for prefix, what in (('BPN', 'BPN'), ('PBB', 'PBB')):
            ident = self.parameterAsString(parameters, prefix+'_ID', context)
            if self.parameterDefinition(prefix+'_AREA') is not None:
                area = self.parameterAsString(parameters, prefix+'_AREA', context)
                if ident and area and ident == area:
                    return False, ('Kolom identitas dan kolom luas %s tidak boleh sama (%s). '
                                   'Pilih kolom luas tertulis yang benar.' % (what, ident))
        return super().checkParameterValues(parameters, context)

    def processAlgorithm(self, parameters, context, feedback):
        values = {'bpn':self.selector('BPN', parameters, context),
                  'pbb':self.selector('PBB', parameters, context),
                  'reproject':self.spec['reproject'] and self.parameterAsBoolean(parameters, 'REPROJECT', context)}
        for item in self.spec['params']:
            kind, key = item[:2];name = key.upper()
            if kind == 'n':
                values[key] = float(self.parameterAsDouble(parameters, name, context))
            elif kind == 'b':
                values[key] = self.parameterAsBoolean(parameters, name, context)
            elif kind == 'f':
                values[key] = self.parameterAsFile(parameters, name, context) or ''
            elif kind == 'e':
                values[key] = item[3][self.parameterAsEnum(parameters, name, context)][0]
            elif kind == 's':
                values[key] = self.selector(name, parameters, context)
        skip = self.parameterAsBoolean(parameters, self.SKIP_OUTPUT, context)
        chosen = '' if skip else (self.parameterAsFileOutput(parameters, self.OUTPUT_FOLDER, context) or '')
        scratch = None
        if chosen:
            folder = Path(chosen).expanduser();folder.mkdir(parents=True, exist_ok=True)
        else:
            # Reports/CSV/model are still produced (the run functions need a place) but discarded.
            scratch = tempfile.mkdtemp(prefix='nibnop_');folder = Path(scratch)
            feedback.pushWarning('Semua keluaran dilewati: tidak ada file yang disimpan.' if skip else
                                 'Folder hasil dilewati: PDF, ZIP rekap'+
                                 (', model dan metadata' if self.modul == 4 else '')+' tidak disimpan.')

        def resolve(basename):
            name = output_param(basename)
            if self.parameterDefinition(name) is None:return ''
            return self.parameterAsOutputLayer(parameters, name, context) or ''

        tool = HeadlessTool(self.modul, values, folder, resolve, feedback, skip)
        try:
            result = tool.execute()
        except Cancelled as e:
            feedback.reportError('DIBATALKAN: %s Tidak ada keluaran baru yang ditulis.' % e)
            return {}
        except Exception as e:
            raise QgsProcessingException(str(e))
        finally:
            if scratch:shutil.rmtree(scratch, ignore_errors=True)
        feedback.pushInfo('SELESAI\n'+'\n'.join(str(x) for x in result))
        outputs = {output_param(basename):path for basename, path in tool.saved}
        if chosen:outputs[self.OUTPUT_FOLDER] = str(folder)
        return outputs


class _OpenStudio:
    """What the Toolbox shows and exec()s for Modul 6: the plugin's studio dock."""
    def __init__(self, launch):self.launch = launch
    def show(self):self.launch(6)
    def exec(self):return 0
    exec_ = exec


class StudioAlgorithm(QgsProcessingAlgorithm):
    """Modul 6 in the Toolbox. Interactive on the map, so it only opens the dock."""
    OPEN = 'OPEN'

    def __init__(self, launch=None):
        super().__init__()
        self.launch = launch

    def createInstance(self):return StudioAlgorithm(self.launch)
    def name(self):return 'modul_6_verifikasi_studio'
    def displayName(self):return '6. Verifikasi Studio interaktif di peta'
    def group(self):return 'NIB-NOP Integrator'
    def groupId(self):return 'nib_nop_integrator'
    def flags(self):return super().flags() | NO_THREADING | HIDE_FROM_MODELER
    def shortHelpString(self):
        return 'Membuka panel Verifikasi Studio (sama dengan menu NIB–NOP Integrator → 6).'

    def initAlgorithm(self, config=None):
        # The Toolbox runs parameterless algorithms directly instead of asking
        # createCustomParametersWidget, so keep one visible parameter.
        self.addParameter(QgsProcessingParameterBoolean(self.OPEN, 'Buka panel Verifikasi Studio',
                                                        defaultValue=True))

    def createCustomParametersWidget(self, parent=None):
        return _OpenStudio(self.launch) if self.launch else None

    def processAlgorithm(self, parameters, context, feedback):
        raise QgsProcessingException('Modul 6 bersifat interaktif di peta; buka dari Processing Toolbox '
                                     'atau menu NIB–NOP Integrator.')


class NibNopProvider(QgsProcessingProvider):
    def __init__(self, launch=None):
        """``launch(modul)`` = NibNopPlugin.launch; needed for Modul 6 only."""
        super().__init__()
        self.launch = launch

    def loadAlgorithms(self, *args):
        for modul in MODULES:
            self.addAlgorithm(NibNopAlgorithm(modul))
        self.addAlgorithm(StudioAlgorithm(self.launch))
    def id(self):return 'nib_nop_integrator'
    def name(self):return 'NIB–NOP Integrator'
    def longName(self):return self.name()
