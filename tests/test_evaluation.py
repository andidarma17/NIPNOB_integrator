"""Tests independent of QGIS, require scikit-learn."""
import unittest
from nibnop_integrator.evaluation import metrics_from_gold, wilson_lower, operational_assessment, recommendations, threshold_guidance

class EvaluationTests(unittest.TestCase):
    def test_confusion_and_metrics(self):
        d=metrics_from_gold([0,0,1,1],[.1,.95,.4,.99])
        self.assertEqual(d['confusion_matrix'],[[1,1],[1,1]])
        self.assertEqual(d['fp'],1)
        self.assertAlmostEqual(d['precision'],.5)
        self.assertAlmostEqual(d['recall'],.5)
        self.assertIsNotNone(d['average_precision'])
        self.assertIn('kalibrasi',d['kurva'])
    def test_no_predicted_positive(self):
        d=metrics_from_gold([0,0,1,1],[.1,.2,.3,.4])
        self.assertIsNone(d['precision'])
        self.assertEqual(d['prediksi_positif'],0)
        self.assertIn('BELUM LAYAK',operational_assessment(d))
    def test_small_sample_precision_not_proven(self):
        self.assertLess(wilson_lower(20,20),.95)
        self.assertTrue(len(threshold_guidance())>=8)
    def test_absent_gold(self):
        self.assertIn('BELUM DAPAT DINILAI',operational_assessment(None))
        self.assertIn('GOLD',recommendations(None)[0])
if __name__=='__main__':unittest.main()
