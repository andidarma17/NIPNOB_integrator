"""Name features and RULE_NAMA silver labels (Modul 4/5). Needs PyQGIS (engine).

Skipped under ``discover`` once test_fieldwidgets has stubbed ``qgis``; run alone:
python -m unittest nibnop_integrator.tests.test_ml_names -v
"""
import csv
import json
import math
import tempfile
import unittest
from pathlib import Path

try:
    import qgis.core  # noqa: F401
    HAVE_QGIS = True
except ImportError:
    HAVE_QGIS = False


def _cand(i, j, overlap=80.):
    return {'pair_id': 'B%06d_P%06d' % (i, j), 'record_bpn': i, 'record_pbb': j,
            'overlap_bpn_pct': overlap, 'overlap_pbb_pct': overlap, 'iou': overlap / 100,
            'skor_nama': 95., 'nama_tidak_dinilai': 0}


@unittest.skipUnless(HAVE_QGIS, 'PyQGIS tidak tersedia')
class NameFeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def silver_csv(self):
        path = self.dir / 'pasangan_kandidat.csv'
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, ['pair_id', 'status', 'metode_padu'])
            w.writeheader()
            w.writerow({'pair_id': 'B000001_P000001', 'status': 'LEVEL_1', 'metode_padu': ''})
            w.writerow({'pair_id': 'B000002_P000002', 'status': 'LEVEL_1', 'metode_padu': 'RULE_NAMA'})
        return str(path)

    def test_feature_versions(self):
        from nibnop_integrator.engine import FEATURE_NAMES, FEATURE_VERSIONS
        from nibnop_integrator.ml import feature_version, feature_vector
        self.assertEqual(feature_version(False), 'QGIS_PLUGIN_V1')
        self.assertEqual(feature_version(True), 'QGIS_PLUGIN_V2')
        v2 = FEATURE_VERSIONS['QGIS_PLUGIN_V2']
        self.assertEqual(v2[:len(FEATURE_NAMES)], FEATURE_NAMES)
        self.assertEqual(v2[len(FEATURE_NAMES):], ['skor_nama', 'nama_tidak_dinilai'])
        row = {'skor_nama': None, 'nama_tidak_dinilai': 1}
        vec = feature_vector(row, v2)
        self.assertEqual(len(vec), 20)
        self.assertTrue(math.isnan(vec[-2]))
        self.assertEqual(vec[-1], 1.)
        self.assertEqual(len(feature_vector(row)), 18)

    def test_rule_nama_silver_is_opt_in(self):
        from nibnop_integrator.ml import labels_for_pairs
        cands = [_cand(1, 1), _cand(2, 2)]
        silver, _, _ = labels_for_pairs(cands, silver_csv=self.silver_csv())
        self.assertEqual([r['label_source'] for r in silver], ['SILVER_RULE'])
        silver, _, _ = labels_for_pairs(cands, silver_csv=self.silver_csv(), name_silver_weight=.1)
        by = {r['pair_id']: r for r in silver}
        self.assertEqual(by['B000002_P000002']['label_source'], 'SILVER_RULE_NAMA')
        self.assertEqual(by['B000002_P000002']['sample_weight'], .1)
        self.assertEqual(by['B000001_P000001']['sample_weight'], .2)

    def test_v2_model_needs_names(self):
        from nibnop_integrator.engine import FEATURE_VERSIONS
        from nibnop_integrator.ml import predict
        meta = self.dir / 'metadata_model.json'
        meta.write_text(json.dumps({'feature_version': 'QGIS_PLUGIN_V2',
                                    'features': FEATURE_VERSIONS['QGIS_PLUGIN_V2']}), encoding='utf-8')
        no_names = [dict(_cand(1, 1), skor_nama=None, nama_tidak_dinilai=1)]
        with self.assertRaises(ValueError):
            predict(no_names, str(self.dir / 'tidak_ada.joblib'), str(meta))
        meta.write_text(json.dumps({'feature_version': 'QGIS_PLUGIN_V3', 'features': []}), encoding='utf-8')
        with self.assertRaises(ValueError):
            predict(no_names, str(self.dir / 'tidak_ada.joblib'), str(meta))


if __name__ == '__main__':
    unittest.main()
