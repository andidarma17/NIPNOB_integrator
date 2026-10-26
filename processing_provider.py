"""Processing Toolbox provider: Modul 1, 2, 3, 3.1, 4 and 5 as algorithms.

The algorithms do not reimplement the modules. ``HeadlessTool`` borrows the
``run1``..``run5`` orchestration of ``dialogs.ToolDialog`` and feeds it the
Processing parameters through small stand-ins for the dialog widgets, so the
matching rules, outputs and PDF reports stay identical to the menu tools.
Modul 6 (verifikasi studio) is interactive on the map and stays in the menu.
"""
from pathlib import Path
from qgis.core import (Qgis, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingContext,
                       QgsProcessingException, QgsProcessingParameterBoolean,
                       QgsProcessingParameterEnum, QgsProcessingParameterField,
                       QgsProcessingParameterFile, QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterNumber, QgsProcessingParameterVectorLayer,
                       QgsProcessingProvider)
from .engine import Progress, Cancelled
from .storage import FORMATS, save_layer


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
FILE_TYPE = _enum(('ProcessingFileParameterBehavior', 'File'),
                  getattr(QgsProcessingParameterFile, 'File', 0))

FORMAT_NAMES = list(FORMATS)

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

CSV = 'CSV (*.csv)'
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
    4: dict(name='modul_4_training_ai', title='4. Training AI', pbb=(POLYGON, POINT), names=True,
            reproject=True, optional_layers=True,
            params=[('f', 'silver', 'CSV kandidat Modul 3 (silver)', CSV),
                    ('b', 'name_silver', 'Sertakan padanan tahap 2 (RULE_NAMA) dari CSV Modul 3 sebagai silver',
                     False),
                    ('n', 'name_silver_weight', 'Bobot silver RULE_NAMA', .10, 0, 1., 2),
                    ('f', 'gold_features', 'CSV fitur historis terverifikasi (opsional)', CSV),
                    ('f', 'gold_operator', 'CSV label operator pada layer yang dipilih (opsional)', CSV),
                    ('b', 'hist_toggle', 'Gunakan pasangan GeoJSON historis + CSV label (opsional)', False),
                    ('s', 'hist_bpn', 'BPN historis'),
                    ('s', 'hist_pbb', 'PBB historis'),
                    ('f', 'hist_csv', 'CSV pasangan historis berlabel', CSV),
                    ('n', 'radius', 'Radius pencarian kandidat (meter)', 15, 0, 1000, 2),
                    ('n', 'target', 'Target precision GOLD', .99, .5, 1., 3)]),
    5: dict(name='modul_5_inference_ai', title='5. Inference AI dan Level 1/2', pbb=(POLYGON, POINT),
            names=True, reproject=True,
            params=OVERLAP+RULES+POINT_TOL_5+NAMES+NAME_STAGE+STAGE2_BUFFER+STAGE2_WEIGHTS+[
                ('f', 'model', 'Model terlatih (.joblib) - hanya dari sumber yang dipercaya',
                 'Joblib (*.joblib)'),
                ('f', 'meta', 'Metadata model (.json)', 'JSON (*.json)'),
                ('n', 'radius', 'Radius kandidat AI (meter)', 15, 0, 1000, 2),
                ('n', 'confidence', 'Skor minimum AI', .95, .5, 1., 3),
                ('n', 'margin', 'Selisih skor kandidat ke-1 vs ke-2', .15, 0, 1., 3),
                ('b', 'promote', 'Izinkan tambahan Level 1 berbasis AI HANYA bila GOLD telah lolos pengujian',
                 False)]),
}


class _Value:
    """Stand-in for a dialog widget: spin ``value()``, line ``text()``, check ``isChecked()``."""
    def __init__(self, v):self.v = v
    def value(self):return self.v
    def text(self):return self.v or ''
    def isChecked(self):return bool(self.v)
    def currentText(self):return self.v
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
    def __init__(self, modul, values, output, output_format, context, feedback):
        if not hasattr(HeadlessTool, 'run1'):
            from .dialogs import ToolDialog
            for name in _BORROWED:
                setattr(HeadlessTool, name, getattr(ToolDialog, name))
        self.modul = modul;self.context = context;self.feedback = feedback
        self.progress = FeedbackProgress(feedback)
        self.output = _Value(str(output));self.output_format = _Value(output_format)
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
        saved = save_layer(layer, output, basename, self.output_format.currentText())
        self.saved.append(saved)
        details = QgsProcessingContext.LayerDetails(basename, self.context.project(), basename)
        self.context.addLayerToLoadOnCompletion(saved, details)
        return saved


class NibNopAlgorithm(QgsProcessingAlgorithm):
    OUTPUT_FORMAT = 'OUTPUT_FORMAT'
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
        # Layers and reports are read/painted like the dialogs do: on the main thread.
        return super().flags() | NO_THREADING
    def shortHelpString(self):
        return ('Sama dengan menu NIB–NOP Integrator → %s: aturan, keluaran layer, rekap_csv.zip dan '
                'laporan PDF identik. Layer hasil dimuat ke proyek setelah selesai.' % self.spec['title'])

    def add_layer(self, prefix, label, types, optional=False, with_area=True, with_name=False):
        self.addParameter(QgsProcessingParameterVectorLayer(prefix, label, list(types), optional=optional))
        self.addParameter(QgsProcessingParameterField(prefix+'_ID', label+' - kolom identitas',
                                                      parentLayerParameterName=prefix, optional=optional))
        if with_area:
            self.addParameter(QgsProcessingParameterField(prefix+'_AREA', label+' - kolom luas tertulis',
                                                          parentLayerParameterName=prefix, optional=optional))
        if with_name:
            self.addParameter(QgsProcessingParameterField(prefix+'_NAME', label+' - kolom nama (opsional, validasi)',
                                                          parentLayerParameterName=prefix, optional=True))

    def initAlgorithm(self, config=None):
        spec = self.spec;optional = spec.get('optional_layers', False)
        pbb_label = {3:'Layer PBB (poligon)', 31:'Layer PBB (titik NOP)'}.get(self.modul,
                                                                              'Layer PBB (poligon atau titik)')
        self.add_layer('BPN', 'Layer BPN (poligon)', (POLYGON,), optional, with_name=spec['names'])
        self.add_layer('PBB', pbb_label, spec['pbb'], optional, with_name=spec['names'])
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
            elif kind == 's':
                self.add_layer(key.upper(), label, (POLYGON,) if key == 'hist_bpn' else (POLYGON, POINT),
                               optional=True, with_name=True)
        self.addParameter(QgsProcessingParameterEnum(self.OUTPUT_FORMAT, 'Format layer', FORMAT_NAMES,
                                                     defaultValue=0))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_FOLDER, 'Folder hasil'))

    def selector(self, prefix, parameters, context):
        def field(suffix):
            name = prefix+suffix
            if self.parameterDefinition(name) is None:return ''
            return self.parameterAsString(parameters, name, context) or ''
        return _Selector(self.parameterAsVectorLayer(parameters, prefix, context),
                         field('_ID'), field('_AREA'), field('_NAME'))

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
            elif kind == 's':
                values[key] = self.selector(name, parameters, context)
        output_format = FORMAT_NAMES[self.parameterAsEnum(parameters, self.OUTPUT_FORMAT, context)]
        folder = Path(self.parameterAsFileOutput(parameters, self.OUTPUT_FOLDER, context)).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        if output_format.startswith('ESRI Shapefile'):
            feedback.pushWarning('Shapefile dapat memotong nama atribut menjadi 10 karakter dan menyebabkan '
                                 'tabrakan kolom. GeoPackage disarankan untuk hasil integrasi.')
        tool = HeadlessTool(self.modul, values, folder, output_format, context, feedback)
        try:
            result = tool.execute()
        except Cancelled as e:
            feedback.reportError('DIBATALKAN: %s Tidak ada keluaran baru yang ditulis.' % e)
            return {}
        except Exception as e:
            raise QgsProcessingException(str(e))
        feedback.pushInfo('SELESAI\n'+'\n'.join(str(x) for x in result))
        return {self.OUTPUT_FOLDER:str(folder)}


class NibNopProvider(QgsProcessingProvider):
    def loadAlgorithms(self, *args):
        for modul in MODULES:
            self.addAlgorithm(NibNopAlgorithm(modul))
    def id(self):return 'nib_nop_integrator'
    def name(self):return 'NIB–NOP Integrator'
    def longName(self):return self.name()
