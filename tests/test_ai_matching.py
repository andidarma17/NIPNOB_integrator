"""Tests for the independent AI decision path (no PyQGIS required)."""
import csv
import importlib.util
import io
import tempfile
import unittest
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('_nibnop_ai_matching_standalone', HERE/'ai_matching.py')
ai = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ai)


class TrainingModeTests(unittest.TestCase):
    def test_exactly_three_modes(self):
        self.assertEqual(ai.training_mode(True,False),'SILVER_ONLY')
        self.assertEqual(ai.training_mode(False,True),'GOLD_ONLY')
        self.assertEqual(ai.training_mode(True,True),'SILVER_GOLD')
        with self.assertRaisesRegex(ValueError,'setidaknya satu'):
            ai.training_mode(False,False)


class BaselineImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bp='bpn_hash_123';self.pp='pbb_hash_456'

    def rows(self):
        return [{'pair_id':'B000001_P000002','record_bpn':'1','record_pbb':'2',
                 'NIB':'00001','NOP':'00000012345','status':'LEVEL_1',
                 'metode_padu':'RULE_NAMA','overlap_bpn_pct':'5.7',
                 'src_bpn_sha':self.bp,'src_pbb_sha':self.pp},
                {'pair_id':'B000003_P000004','record_bpn':'3','record_pbb':'4',
                 'NIB':'00003','NOP':'00000012346','status':'LEVEL_2',
                 'metode_padu':'','overlap_bpn_pct':'1',
                 'src_bpn_sha':self.bp,'src_pbb_sha':self.pp}]

    def save(self,rows,archive=False):
        stream=io.StringIO()
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
        output=Path(self.temp.name)/('hasil_modul3.zip' if archive else 'pasangan_kandidat.csv')
        if archive:
            with zipfile.ZipFile(output,'w') as z:
                z.writestr('pasangan_kandidat.csv','\ufeff'+stream.getvalue())
        else:
            output.write_text(stream.getvalue(),encoding='utf-8-sig')
        return output

    def test_only_level1_preserved_and_id_zeroes(self):
        accepted,all_pairs=ai.load_rule_baseline(self.save(self.rows(),True),self.bp,self.pp)
        self.assertEqual((len(accepted),len(all_pairs)),(1,2))
        self.assertEqual(accepted[0]['NOP'],'00000012345')
        self.assertEqual(accepted[0]['metode_padu'],'RULE_NAMA')
        self.assertEqual(accepted[0]['record_bpn'],1)

    def test_stale_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'berbeda'):
            ai.load_rule_baseline(self.save(self.rows()),'wrong_hash',self.pp)

    def test_one_to_one_conflict_is_rejected(self):
        rows=self.rows()
        rows[1]['status']='LEVEL_1'
        rows[1]['record_bpn']='1'
        with self.assertRaisesRegex(ValueError,'tidak unik'):
            ai.load_rule_baseline(self.save(rows),self.bp,self.pp)


class IndependentInferenceTests(unittest.TestCase):
    def sample(self,b,p,score):
        return {'pair_id':f'B{b:06d}_P{p:06d}','record_bpn':b,'record_pbb':p,
                'NIB':f'N{b}','NOP':f'P{p}','skor_ai':score,
                'deviasi_luas_bpn':230.,'deviasi_luas_pbb':1000.,
                'overlap_bpn_pct':0.0, 'overlap_pbb_pct':0.0}

    def counts(self):
        return ({'N1':1,'N2':1},{'P1':1,'P2':1})

    def test_large_area_deviation_is_feature_not_gate(self):
        b,p=self.counts()
        proposals,accepted,scored,fail=ai.select_ai_proposals(
            [self.sample(1,1,.97)],.90,.15,b,p,allow_promotion=True)
        self.assertEqual((len(proposals),len(accepted)),(1,1))
        self.assertEqual(scored[0]['keputusan_ai'],'DITERIMA_LEVEL1')

    def test_silver_only_can_propose_without_auto_accepting(self):
        b,p=self.counts()
        proposals,accepted,scored,_=ai.select_ai_proposals(
            [self.sample(1,1,.97)],.90,.15,b,p,allow_promotion=False)
        self.assertEqual((len(proposals),len(accepted)),(1,0))
        self.assertEqual(scored[0]['keputusan_ai'],'USULAN_AI_STUDIO')

    def test_competing_candidate_and_margin(self):
        b,p=self.counts()
        proposals,accepted,scored,_=ai.select_ai_proposals(
            [self.sample(1,1,.97),self.sample(1,2,.94)],.90,.15,b,p,
            allow_promotion=True)
        self.assertEqual(len(accepted),0)
        self.assertEqual(len(proposals),0)
        self.assertTrue(all(row['gerbang_margin']=='Perlu telaah' for row in scored))

    def test_hybrid_does_not_replace_rule_or_reuse_nop(self):
        b,p=self.counts()
        existing={'record_bpn':1,'record_pbb':1,'NIB':'N1','NOP':'P1'}
        proposals,accepted,scored,_=ai.select_ai_proposals(
            [self.sample(1,2,.99),self.sample(2,1,.98),self.sample(2,2,.96)],
            .90,.15,b,p,baseline=[existing],allow_promotion=True)
        self.assertEqual([x['pair_id'] for x in accepted],['B000002_P000002'])
        self.assertEqual(len(proposals),1)
        self.assertEqual(len([r for r in scored if r['gerbang_tersedia']=='Perlu telaah']),2)

    def test_duplicate_identity_not_auto_accepted(self):
        b,p=self.counts();b['N1']=2
        proposals,accepted,_,_=ai.select_ai_proposals(
            [self.sample(1,1,.99)],.90,.15,b,p,allow_promotion=True)
        self.assertFalse(proposals or accepted)


if __name__=='__main__':
    unittest.main()
