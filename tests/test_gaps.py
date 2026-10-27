"""Gap candidates without a hard limit, partial cancel, PBB-on-gap hints. Needs PyQGIS.

Skipped under ``discover`` once test_fieldwidgets has stubbed ``qgis``; run alone:
python -m unittest nibnop_integrator.tests.test_gaps -v
"""
import unittest

try:
    from qgis.core import QgsGeometry
    HAVE_QGIS = True
except ImportError:
    HAVE_QGIS = False


def _sq(x, y, w=10.):
    return 'POLYGON((%g %g,%g %g,%g %g,%g %g,%g %g))' % (x, y, x+w, y, x+w, y+w, x, y+w, x, y)


def _rec(i, wkt, **a):
    return {'idx': i, 'fid': i, 'a': a, 'geom': QgsGeometry.fromWkt(wkt)}


def _bpn():
    """3x3 ring of parcels around a 100 m² hole, plus one parcel with 3 big and 30 tiny holes."""
    rows = [_rec(n+1, _sq(x*10, y*10), NIB='B%d' % n, LUAS=100)
            for n, (x, y) in enumerate((x, y) for x in range(3) for y in range(3) if (x, y) != (1, 1))]
    holes = ['(%g %g,%g %g,%g %g,%g %g,%g %g)' % (x, 5, x+2, 5, x+2, 7, x, 7, x, 5)
             for x in (110, 130, 150)]
    holes += ['(%g %g,%g %g,%g %g,%g %g,%g %g)' % (x, 50, x+.1, 50, x+.1, 50.1, x, 50.1, x, 50)
              for x in range(105, 195, 3)]
    rows.append(_rec(len(rows)+1, 'POLYGON((100 0,200 0,200 100,100 100,100 0),%s)' % ','.join(holes),
                     NIB='BIG', LUAS=10000))
    return rows


@unittest.skipUnless(HAVE_QGIS, 'PyQGIS tidak tersedia')
class GapTests(unittest.TestCase):
    def test_many_gaps_warn_instead_of_error(self):
        from nibnop_integrator.engine import enclosed_gaps
        rows, summary = enclosed_gaps(_bpn(), min_gap=1., warn_gaps=2)
        self.assertEqual(summary['terdeteksi'], 34)
        self.assertEqual(summary['diproses'], 34)
        self.assertEqual(summary['layak'], 4)
        self.assertEqual(summary['status'], 'LENGKAP')
        self.assertEqual(len(summary['peringatan']), 1)
        states = {r['a']['status_periksa'] for r in rows}
        self.assertEqual(states, {'LAYAK_PERIKSA', 'DI_BAWAH_MINIMUM'})

    def test_cancel_during_gaps_is_partial(self):
        from nibnop_integrator.engine import Progress, enclosed_gaps, fix_geometry, Cancelled

        class StopAfter(Progress):
            def __init__(self, n): self.n = n; self.calls = 0; self.resumed = False
            def update(self, done, total): self.calls += 1
            def cancelled(self): return not self.resumed and self.calls > self.n
            def resume(self): self.resumed = True
        progress = StopAfter(5)
        rows, summary = enclosed_gaps(_bpn(), 1., 2500, progress)
        self.assertEqual(summary['status'], 'TIDAK_LENGKAP')
        self.assertEqual(summary['diproses'], 5)
        self.assertTrue(progress.resumed)
        with self.assertRaises(Cancelled):
            fix_geometry(_bpn(), StopAfter(0))

    def test_gap_hint_does_not_compete(self):
        from nibnop_integrator.engine import enclosed_gaps, gap_hints, determine_levels
        b = _bpn()[:8]
        # P1 matches the corner parcel; P2 lies entirely in the central 100 m² hole.
        p = [_rec(1, 'POLYGON((0 0,12 0,12 10,0 10,0 0))', NOP='P1', LUAS=100),
             _rec(2, _sq(12, 12, 6), NOP='P2', LUAS=36)]
        opts = {'bpn_id': 'NIB', 'pbb_id': 'NOP', 'bpn_area': 'LUAS', 'pbb_area': 'LUAS',
                'min_overlap': 50., 'min_sim': 90., 'max_dev': 50., 'min_irisan': .01}
        l1, _, l2p, _, _ = determine_levels(b, p, opts)
        self.assertEqual([r['a']['nop_padanan'] for r in l1], ['P1'])
        gaps, summary = enclosed_gaps(b, 1.)
        self.assertEqual(gap_hints(gaps, l2p, summary, .01), 1)
        self.assertIn('PBB_DI_ATAS_GAP', l2p[0]['a']['kode_l2'])
        self.assertEqual(l2p[0]['a']['calon_gap'], 'GAP00001')
        self.assertEqual(gaps[0]['a']['pbb_terkait'], 'P2')


if __name__ == '__main__':
    unittest.main()
