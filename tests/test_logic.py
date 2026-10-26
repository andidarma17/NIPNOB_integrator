"""Unit tests (run with: python -m unittest discover tests -v)."""
import unittest
from nibnop_integrator.logic import ident,empty,number,dev_percent,similarity,gate_pair,normalize_verified_label

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

if __name__=='__main__':unittest.main()
