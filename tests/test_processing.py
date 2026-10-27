"""Processing provider: algorithms, outputs, borrowed dialog methods and Modul 3 runs. Needs PyQGIS (with qgis.gui).

Skipped under ``discover`` once test_fieldwidgets has stubbed ``qgis``; run alone:
python -m unittest nibnop_integrator.tests.test_processing -v
"""
import tempfile
import unittest
from pathlib import Path

try:
    from qgis.core import QgsApplication, QgsFeature, QgsGeometry, QgsVectorLayer
    import qgis.gui  # noqa: F401  (dialogs.ToolDialog supplies the run methods)
    HAVE_QGIS = hasattr(QgsApplication, 'processingRegistry')
except ImportError:
    HAVE_QGIS = False


def _layer(fields, rows):
    lyr = QgsVectorLayer('Polygon?crs=EPSG:32749&'+'&'.join('field='+f for f in fields), 'l', 'memory')
    feats = []
    for wkt, attrs in rows:
        f = QgsFeature(lyr.fields());f.setGeometry(QgsGeometry.fromWkt(wkt));f.setAttributes(attrs)
        feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    return lyr


def _sq(x, y, w=20.):
    return 'POLYGON((%g %g,%g %g,%g %g,%g %g,%g %g))' % (x, y, x+w, y, x+w, y+w, x, y+w, x, y)


@unittest.skipUnless(HAVE_QGIS, 'PyQGIS tidak tersedia')
class ProcessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication.instance() or QgsApplication([], False)
        cls.app.initQgis()
        from nibnop_integrator.processing_provider import NibNopProvider
        cls.provider = NibNopProvider()
        QgsApplication.processingRegistry().addProvider(cls.provider)

    @classmethod
    def tearDownClass(cls):
        QgsApplication.processingRegistry().removeProvider(cls.provider)

    def alg(self, name):
        return QgsApplication.processingRegistry().algorithmById('nib_nop_integrator:'+name)

    def test_modules_registered(self):
        names = sorted(a.name() for a in self.provider.algorithms())
        self.assertEqual(names, ['modul_1_kelengkapan', 'modul_2_kualitas_spasial', 'modul_3_1_pemaduan_titik',
                                 'modul_3_pemaduan_aturan', 'modul_4_training_ai', 'modul_5_inference_ai',
                                 'modul_6_verifikasi_studio'])

    def test_ai_modules_expose_v098_parameters(self):
        m4 = {d.name() for d in self.alg('modul_4_training_ai').parameterDefinitions()}
        m5 = {d.name() for d in self.alg('modul_5_inference_ai').parameterDefinitions()}
        self.assertTrue({'TRAINING_MODE', 'SILVER', 'GOLD_OPERATOR', 'GOLD_FEATURES', 'TARGET'} <= m4)
        self.assertTrue({'INFERENCE_MODE', 'RULE_SOURCE', 'MODEL', 'META', 'CONFIDENCE', 'MARGIN',
                         'PROMOTE'} <= m5)
        self.assertFalse({'OVERLAP', 'SIM', 'DEV', 'NAME_STAGE'} & m5)  # Modul 3 gates are not AI gates

    def test_toolbox_uses_standard_form(self):
        # No custom parameters widget: the Toolbox shows the standard Processing form.
        for name in ('modul_1_kelengkapan', 'modul_4_training_ai', 'modul_5_inference_ai'):
            self.assertIsNone(self.alg(name).createCustomParametersWidget(None))

    def test_borrowed_dialog_methods_exist(self):
        from nibnop_integrator.dialogs import ToolDialog
        from nibnop_integrator.processing_provider import _BORROWED
        for name in _BORROWED:
            self.assertTrue(callable(getattr(ToolDialog, name, None)), name)

    def test_modul3_matches_and_writes_outputs(self):
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProject
        bpn = _layer(['NIB:string', 'LUAS:double'], [(_sq(i*20, 0), ['B%d' % i, 400]) for i in range(4)])
        pbb = _layer(['D_NOP:string', 'D_LUAS:double'], [(_sq(i*20+.2, .2), ['P%d' % i, 401]) for i in range(3)])
        context = QgsProcessingContext();context.setProject(QgsProject.instance())
        with tempfile.TemporaryDirectory() as out:
            result, ok = self.alg('modul_3_pemaduan_aturan').run(
                {'BPN':bpn, 'BPN_ID':'NIB', 'BPN_AREA':'LUAS', 'PBB':pbb, 'PBB_ID':'D_NOP',
                 'PBB_AREA':'D_LUAS', 'OUTPUT_FOLDER':out,
                 'OUT_01_PADANAN_LEVEL1':str(Path(out)/'l1.gpkg'),
                 'OUT_02_BPN_LEVEL2':str(Path(out)/'bpn_l2.geojson'),
                 'OUT_03_PBB_LEVEL2':'TEMPORARY_OUTPUT'}, context, QgsProcessingFeedback())
            self.assertTrue(ok)
            self.assertEqual(result['OUTPUT_FOLDER'], out)
            files = {p.name for p in Path(out).iterdir()}
            for name in ('l1.gpkg', 'bpn_l2.geojson', 'laporan_modul3.pdf', 'rekap_csv.zip',
                         'manifest_modul3.json'):
                self.assertIn(name, files)
            self.assertEqual(QgsVectorLayer(str(Path(out)/'l1.gpkg'), 'l1', 'ogr').featureCount(), 3)
            self.assertIn('OUT_03_PBB_LEVEL2', result)

    def test_skip_all_outputs_writes_nothing(self):
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProject
        bpn = _layer(['NIB:string', 'LUAS:double'], [(_sq(i*20, 0), ['B%d' % i, 400]) for i in range(2)])
        pbb = _layer(['D_NOP:string', 'D_LUAS:double'], [(_sq(i*20+.2, .2), ['P%d' % i, 401]) for i in range(2)])
        context = QgsProcessingContext();context.setProject(QgsProject.instance())
        with tempfile.TemporaryDirectory() as out:
            result, ok = self.alg('modul_3_pemaduan_aturan').run(
                {'BPN':bpn, 'BPN_ID':'NIB', 'BPN_AREA':'LUAS', 'PBB':pbb, 'PBB_ID':'D_NOP',
                 'PBB_AREA':'D_LUAS', 'SKIP_OUTPUT':True, 'OUTPUT_FOLDER':out,
                 'OUT_01_PADANAN_LEVEL1':str(Path(out)/'l1.gpkg')}, context, QgsProcessingFeedback())
            self.assertTrue(ok)
            self.assertEqual(list(Path(out).iterdir()), [])
            self.assertNotIn('OUTPUT_FOLDER', result)

    def test_same_field_for_id_and_area_is_rejected(self):
        bpn = _layer(['NIB:string', 'LUAS:double'], [(_sq(0, 0), ['B0', 400])])
        ok, message = self.alg('modul_1_kelengkapan').checkParameterValues(
            {'BPN':bpn, 'BPN_ID':'NIB', 'BPN_AREA':'NIB', 'PBB':bpn, 'PBB_ID':'NIB', 'PBB_AREA':'LUAS'},
            __import__('qgis.core', fromlist=['QgsProcessingContext']).QgsProcessingContext())
        self.assertFalse(ok)
        self.assertIn('tidak boleh sama', message)

    def test_each_spatial_output_is_a_separate_optional_destination(self):
        names = {d.name(): d for d in self.alg('modul_3_pemaduan_aturan').parameterDefinitions()}
        for key in ('OUT_01_PADANAN_LEVEL1', 'OUT_02_BPN_LEVEL2', 'OUT_03_PBB_LEVEL2', 'OUTPUT_FOLDER'):
            self.assertIn(key, names)
            self.assertTrue(names[key].flags() & names[key].FlagOptional)
        self.assertIn('SKIP_OUTPUT', names)
        self.assertNotIn('OUTPUT_FORMAT', names)


if __name__ == '__main__':
    unittest.main()
