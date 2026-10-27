"""Smoke-test all three training modes without QGIS (scikit-learn required)."""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path


HERE=Path(__file__).resolve().parents[1]
PACKAGE='_nibnop_training_modes_test'
pkg=types.ModuleType(PACKAGE);pkg.__path__=[str(HERE)]
sys.modules[PACKAGE]=pkg
engine=types.ModuleType(PACKAGE+'.engine')
engine.FEATURE_NAMES=['overlap_bpn_pct','iou']
engine.FEATURE_VERSIONS={'QGIS_PLUGIN_V1':engine.FEATURE_NAMES}
engine.make_candidate_rows=lambda *a,**kw:[]
engine.prepare_local=lambda *a,**kw:None
sys.modules[PACKAGE+'.engine']=engine


def load(name):
    full=PACKAGE+'.'+name
    spec=importlib.util.spec_from_file_location(full,HERE/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);sys.modules[full]=mod
    spec.loader.exec_module(mod)
    return mod


load('logic')
load('ai_matching')
load('evaluation')
ml=load('ml')


def entry(i,label,group,source):
    xx=300000.+group*250.+10.
    return {'pair_id':'B%06d_P%06d'%(i,i),'record_bpn':i,'record_pbb':i,
            'NIB':'N%06d'%i,'NOP':'P%06d'%i,'label':label,
            'sample_weight':1.0 if source=='GOLD_HISTORICAL_GEO' else .2,
            'label_source':source,'group_id':'tile_%d_39996'%(1200+group),
            'overlap_bpn_pct':90. if label else 2.,
            'iou':.8 if label else .01,'x_bpn':xx,'y_bpn':9999000.,
            'mode_geom':'POLIGON'}


class TrainModesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gold=[entry(i, i%2, i//20,'GOLD_HISTORICAL_GEO') for i in range(120)]
        cls.silver=[entry(10000+i, i%2,10+i//20,'SILVER_RULE') for i in range(100)]

    def train(self,mode,silver,gold):
        with tempfile.TemporaryDirectory() as folder:
            _,metadata,metrics=ml.train_model(silver,gold,folder,.80,'QGIS_PLUGIN_V1',
                                               training_mode=mode)
            written=json.loads((Path(folder)/'metadata_model.json').read_text())
            self.assertEqual(written['training_mode'],mode)
            self.assertTrue((Path(folder)/'model_terpilih.joblib').is_file())
            self.assertTrue((Path(folder)/'evaluasi_testing_ai.json').is_file())
            return metadata,metrics

    def test_silver_only_has_no_independent_gold_approval(self):
        meta,metrics=self.train('SILVER_ONLY',self.silver,[])
        self.assertEqual(meta['status'],'PREVIEW_ONLY')
        self.assertEqual(meta['n_testing'],0)
        self.assertEqual(meta['n_gold'],0)

    def test_gold_only_has_separate_test(self):
        meta,metrics=self.train('GOLD_ONLY',[],self.gold)
        self.assertGreater(meta['n_testing'],0)
        self.assertEqual(meta['n_silver'],0)

    def test_combined_caps_aggregate_weak_label_weight(self):
        meta,metrics=self.train('SILVER_GOLD',self.silver,self.gold)
        self.assertEqual(meta['n_gold'],120)
        self.assertEqual(meta['n_silver'],100)
        self.assertLessEqual(meta['effective_silver_weight'],meta['n_training'])

    def test_mismatched_mode_fails_early(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'tidak boleh'):
                ml.train_model(self.silver,self.gold,folder,.80,'QGIS_PLUGIN_V1',
                               training_mode='SILVER_ONLY')

    def test_spatial_holdout_removes_silver_from_same_tile(self):
        hold=[entry(1,1,0,'GOLD_HISTORICAL_GEO')]
        same_tile=entry(999,0,0,'SILVER_RULE')
        far=entry(1000,0,20,'SILVER_RULE')
        safe=ml._exclude_silver_near_gold_holdout([same_tile,far],hold)
        self.assertEqual([x['record_bpn'] for x in safe],[1000])

    def test_silver_csv_can_be_read_directly_from_modul3_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'rekap_csv.zip'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('pasangan_kandidat.csv',
                    '\ufeffpair_id,NIB,NOP,status,src_bpn_sha,src_pbb_sha\n'
                    'B000001_P000001,00001,000000234,LEVEL_1,b_hash,p_hash\n')
            rows=ml.csv_rows(path,('src_bpn_sha','src_pbb_sha'))
            self.assertEqual(rows[0]['NIB'],'00001')
            self.assertEqual(rows[0]['NOP'],'000000234')


if __name__=='__main__':unittest.main()
