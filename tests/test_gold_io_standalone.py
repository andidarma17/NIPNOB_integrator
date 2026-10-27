"""GOLD import checks that run without QGIS (read-only, no PyQGIS)."""
import csv
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
PACKAGE = '_nibnop_gold_io_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(HERE)]
sys.modules[PACKAGE] = package
engine = types.ModuleType(PACKAGE+'.engine')
engine.FEATURE_NAMES = ['overlap_bpn_pct','iou']
engine.FEATURE_VERSIONS = {'QGIS_PLUGIN_V1':engine.FEATURE_NAMES,
                           'QGIS_PLUGIN_V2':engine.FEATURE_NAMES+['skor_nama','nama_tidak_dinilai']}
engine.make_candidate_rows = lambda *a,**k:[]
engine.prepare_local = lambda *a,**k:None
sys.modules[PACKAGE+'.engine'] = engine


def load(relative):
    name=PACKAGE+'.'+relative
    spec=importlib.util.spec_from_file_location(name,HERE/(relative+'.py'))
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


logic=load('logic')
ml=load('ml')


def candidate(pair='B000001_P000002',nib='00015',nop='617103000800904320'):
    return {'pair_id':pair,'record_bpn':1,'record_pbb':2,'NIB':nib,'NOP':nop,
            'overlap_bpn_pct':80.,'overlap_pbb_pct':70.,'iou':.63,
            'x_bpn':300000.,'y_bpn':9999000.}


class GoldImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def write(self,delimiter,rows):
        path=Path(self.temp.name)/'gold.csv'
        with path.open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=delimiter)
            writer.writeheader();writer.writerows(rows)
        return str(path)

    def test_semicolon_and_status_terverifikasi(self):
        row={'pair_id':'B999999_P999999','NIB':'00015','NOP':'617103000800904320',
             'label':'1','status_verifikasi':'Terverifikasi',
             'sumber_verifikasi':'Pemeriksaan manual operator terdokumentasi'}
        path=self.write(';',[row])
        self.assertEqual(ml.csv_rows(path,('NOP','label'))[0]['NOP'],row['NOP'])
        _,gold,missing=ml.labels_for_pairs([candidate()],historical_csv=path)
        self.assertEqual((len(gold),len(missing)),(1,0))
        self.assertEqual(gold[0]['metode_pencocokan_gold'],'NIB_NOP_UNIK')

    def test_bad_evidence_is_rejected_with_reason(self):
        row={'pair_id':'B000001_P000002','NIB':'00015','NOP':'617103000800904320',
             'label':'0','status_verifikasi':'Terverifikasi','sumber_verifikasi':''}
        path=self.write(';',[row])
        _,gold,missing=ml.labels_for_pairs([candidate()],historical_csv=path)
        self.assertFalse(gold)
        self.assertEqual(missing[0]['alasan_penolakan'],'LABEL_STATUS_ATAU_BUKTI_TIDAK_VALID')

    def test_notasi_ilmiah_nop_never_joins_by_pair_id(self):
        row={'pair_id':'B000001_P000002','NIB':'00015','NOP':'6,17103E+17',
             'label':'1','status_verifikasi':'DIVERIFIKASI',
             'sumber_verifikasi':'Pemeriksaan operator'}
        path=self.write(';',[row])
        _,gold,missing=ml.labels_for_pairs([candidate()],historical_csv=path)
        self.assertFalse(gold)
        self.assertEqual(missing[0]['alasan_penolakan'],'NOP_RUSAK_NOTASI_ILMIAH')

    def test_wrong_pair_id_rejected_if_nop_disagrees(self):
        row={'pair_id':'B000001_P000002','NIB':'00015','NOP':'617103000800904330',
             'label':'1','status_verifikasi':'DIVERIFIKASI',
             'sumber_verifikasi':'Pemeriksaan operator'}
        path=self.write(',',[row])
        _,gold,missing=ml.labels_for_pairs([candidate()],historical_csv=path)
        self.assertFalse(gold)
        self.assertEqual(missing[0]['alasan_penolakan'],'NOP_BERBEDA_DARI_KANDIDAT')

    def test_feature_csv_requires_all_columns(self):
        path=self.write(',',[{'label':'1','status_verifikasi':'DIVERIFIKASI',
                              'sumber_verifikasi':'Arsip','overlap_bpn_pct':'90'}])
        with self.assertRaisesRegex(ValueError,'iou'):
            ml.add_historical_labeled_features([],path,engine.FEATURE_NAMES)

    def test_bad_numeric_feature_rejected_not_silently_nan(self):
        path=self.write(';',[{'label':'1','status_verifikasi':'DIVERIFIKASI',
                              'sumber_verifikasi':'Arsip',
                              'overlap_bpn_pct':'946.274.711.595.659','iou':'.5'}])
        with self.assertRaisesRegex(ValueError,'bukan angka'):
            ml.add_historical_labeled_features([],path,engine.FEATURE_NAMES)


if __name__=='__main__':unittest.main()
