"""Unit tests (run with: python -m unittest discover tests -v)."""
import unittest
from nibnop_integrator.logic import (ident,empty,number,dev_percent,similarity,gate_pair,normalize_verified_label,
                                    name_tokens,name_similarity,name_status,match_strength,
                                    spatial_score,combined_score,select_stage2)

O={'max_dev':50,'min_sim':90,'min_overlap':50}

class RuleTests(unittest.TestCase):
    def test_percent_area(self):
        self.assertAlmostEqual(dev_percent(90,100),10.)
        self.assertAlmostEqual(similarity(95,100),95.)
        self.assertIsNone(similarity(None,100))
        self.assertEqual(ident('00123'),'00123')
        self.assertFalse(empty(0))
    def test_only_one_qualified_candidate(self):
        self.assertEqual(gate_pair(61,1,1,'B001','P001',1,1,10,12,96,O),[])
        # A second strong overlap must invalidate automatic pairing.
        self.assertIn('MULTI_NOP',gate_pair(61,2,1,'B001','P001',1,1,10,12,96,O))
        self.assertIn('MULTI_NIB',gate_pair(61,1,2,'B001','P001',1,1,10,12,96,O))
    def test_gate_threshold_strict(self):
        self.assertIn('OVERLAP_KURANG',gate_pair(50,1,1,'B','P',1,1,10,10,95,O))
        self.assertIn('LUAS_TERTULIS_TIDAK_SAMA',gate_pair(55,1,1,'B','P',1,1,10,10,90,O))
        self.assertIn('NIB_DUPLIKAT',gate_pair(90,1,1,'B','P',2,1,10,10,99,O))
    def test_level2_not_negative(self):
        self.assertIsNone(normalize_verified_label({'level':'Level 2','status_verifikasi':'DIVERIFIKASI','sumber_verifikasi':'Peta'}))
        self.assertIsNone(normalize_verified_label({'label':'0','status_verifikasi':'','sumber_verifikasi':'Peta'}))
        self.assertEqual(normalize_verified_label({'label':'0','status_verifikasi':'DIVERIFIKASI','sumber_verifikasi':'Arsip resmi'}),0)
        self.assertEqual(normalize_verified_label({'level':'LEVEL 1','status_verifikasi':'DIVERIFIKASI','sumber_verifikasi':'Arsip'}),1)

class PointModeTests(unittest.TestCase):
    def test_point_inside_replaces_overlap_gate(self):
        # overlap value is irrelevant for a point; only "inside" counts
        self.assertEqual(gate_pair(0,1,1,'B','P',1,1,10,10,96,O,point_inside=True),[])
        out=gate_pair(100,1,1,'B','P',1,1,10,10,96,O,point_inside=False)
        self.assertIn('TITIK_DI_LUAR_BIDANG',out)
        self.assertNotIn('OVERLAP_KURANG',out)
        self.assertIn('MULTI_NOP',gate_pair(0,2,1,'B','P',1,1,10,10,96,O,point_inside=True))

    def test_name_gate_only_when_required(self):
        self.assertEqual(gate_pair(61,1,1,'B','P',1,1,10,10,96,O,name_state='TIDAK_COCOK'),[])
        req=dict(O,require_name=True)
        self.assertIn('NAMA_TIDAK_COCOK',gate_pair(61,1,1,'B','P',1,1,10,10,96,req,name_state='TIDAK_COCOK'))
        # names that cannot be assessed never fail a pair
        self.assertEqual(gate_pair(61,1,1,'B','P',1,1,10,10,96,req,name_state='TIDAK_DINILAI'),[])

    def test_strength(self):
        self.assertEqual(match_strength('COCOK',True),'KUAT')
        self.assertEqual(match_strength('TIDAK_DINILAI',True),'SEDANG')
        self.assertEqual(match_strength('MIRIP',True),'SEDANG')
        self.assertEqual(match_strength('TIDAK_COCOK',True),'LEMAH')
        self.assertEqual(match_strength('TIDAK_DINILAI',False),'KUAT')
        self.assertEqual(match_strength('TIDAK_COCOK',False),'SEDANG')


class NameTests(unittest.TestCase):
    def test_normalisation(self):
        self.assertEqual(name_tokens('H. Ahmad Dahlan, S.H., M.H.'),['AHMAD','DAHLAN'])
        self.assertEqual(name_tokens('Drs. Moch. Djoko'),['MUHAMAD','JOKO'])
        self.assertEqual(name_tokens('BUDI SANTOSO S.H.'),['BUDI','SANTOSO'])
        self.assertEqual(name_tokens('SANTOSO, BUDI'),['SANTOSO','BUDI'])
        self.assertEqual(name_tokens(None),[])

    def test_similarity_states(self):
        self.assertEqual(name_status(name_similarity('Sukarno','SOEKARNO')),'COCOK')
        self.assertEqual(name_status(name_similarity('Budi Santoso','Santoso Budi')),'COCOK')
        self.assertEqual(name_status(name_similarity('M. Saleh','Muhammad Saleh')),'COCOK')
        self.assertEqual(name_status(name_similarity('Sukarno','Sukarno Hadi')),'MIRIP')
        self.assertEqual(name_status(name_similarity('Siti Aminah','Siti Maryam')),'TIDAK_COCOK')
        self.assertEqual(name_status(name_similarity('Budi','Ani')),'TIDAK_COCOK')
        self.assertIsNone(name_similarity('','Ani'))
        self.assertEqual(name_status(None),'TIDAK_DINILAI')

def _row(b,p,score,name=95.):
    return {'record_bpn':b,'record_pbb':p,'skor_gabungan':score,'skor_nama':name}


class StageTwoTests(unittest.TestCase):
    def test_spatial_score(self):
        self.assertEqual(spatial_score(3.,5.,linked=True),100.)
        self.assertEqual(spatial_score(0.,5.),100.)
        self.assertAlmostEqual(spatial_score(2.5,5.),50.)
        self.assertEqual(spatial_score(7.,5.),0.)
        self.assertEqual(spatial_score(None,5.),0.)

    def test_combined_score(self):
        self.assertEqual(combined_score(100,100,100),100.)
        self.assertAlmostEqual(combined_score(90,50,None),.6*90+.25*50)
        # weights are normalised, so they need not sum to 1
        self.assertEqual(combined_score(80,40,0,(2,2,0)),60.)
        self.assertIsNone(combined_score(None,100,100))
        self.assertIsNone(combined_score(90,100,100,(0,0,0)))

    def test_select_one_to_one_with_margin(self):
        rows=[_row(1,1,92),_row(1,2,70),_row(2,3,85)]
        self.assertEqual(select_stage2(rows),[rows[0],rows[2]])
        self.assertEqual(rows[1]['alasan_tahap2'],'SKOR_GABUNGAN_KURANG;BUKAN_KANDIDAT_TERBAIK')

    def test_select_rejects_close_runner_up_on_either_side(self):
        rows=[_row(1,1,90),_row(1,2,85)]
        self.assertEqual(select_stage2(rows),[])
        self.assertIn('SELISIH_SKOR_KURANG',rows[0]['alasan_tahap2'])
        # runner-up on the PBB side counts too
        rows=[_row(1,1,90),_row(2,1,86)]
        self.assertEqual(select_stage2(rows),[])

    def test_select_requires_name(self):
        rows=[_row(1,1,85,name=55.),_row(2,2,None,name=None)]
        self.assertEqual(select_stage2(rows),[])
        self.assertIn('SKOR_NAMA_KURANG',rows[0]['alasan_tahap2'])
        self.assertEqual(rows[1]['alasan_tahap2'],'NAMA_TIDAK_DINILAI')

if __name__=='__main__':unittest.main()
