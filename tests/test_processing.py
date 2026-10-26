"""Processing provider: algorithms, dialog keys and a Modul 3 run. Needs PyQGIS (with qgis.gui).

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
                                 'modul_3_pemaduan_aturan', 'modul_4_training_ai', 'modul_5_inference_ai'])

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
                 'PBB_AREA':'D_LUAS', 'OUTPUT_FOLDER':out}, context, QgsProcessingFeedback())
            self.assertTrue(ok)
            self.assertEqual(result['OUTPUT_FOLDER'], out)
            files = {p.name for p in Path(out).iterdir()}
            for name in ('01_padanan_level1.gpkg', '02_bpn_level2.gpkg', '03_pbb_level2.gpkg',
                         'laporan_modul3.pdf', 'rekap_csv.zip', 'manifest_modul3.json'):
                self.assertIn(name, files)
            level1 = QgsVectorLayer(str(Path(out)/'01_padanan_level1.gpkg'), 'l1', 'ogr')
            self.assertEqual(level1.featureCount(), 3)
            self.assertEqual(len(context.layersToLoadOnCompletion()), 3)


if __name__ == '__main__':
    unittest.main()
