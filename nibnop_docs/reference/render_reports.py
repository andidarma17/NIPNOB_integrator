"""Render laporan PDF plugin memakai PyQt5 tanpa QGIS (untuk melihat desain saat ini).

Persiapan:   pip install PyQt5
Struktur:    <WORK>/shim/qgis/{__init__,core}.py + shim/qgis/PyQt/{__init__,QtCore,QtGui,QtWidgets}.py
             (tiap QtX.py berisi:  from PyQt5.QtX import * )
             <WORK>/pkg/nibnop_integrator  = salinan folder plugin
Jalankan:    python3 -I render_reports.py     (data sintetis; hanya untuk tata letak)
Catatan:     qgis.core cukup berisi stub QgsRectangle; geometri palsu menyediakan
             isNull/isEmpty/isMultipart/asPolygon/boundingBox/area.
Skrip lengkap: render_modul_1_2_3_5_6.py dan render_modul_4.py (path /home/claude/render_env disesuaikan).
ringkas ini mendokumentasikan caranya agar bisa direproduksi.
"""
import sys, os
WORK = os.environ.get('WORK', '/tmp/render_env')
sys.path.insert(0, WORK + '/shim'); sys.path.insert(0, WORK + '/pkg')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt5.QtGui import QGuiApplication
app = QGuiApplication(sys.argv)
from nibnop_integrator import reporting_full as rf, ai_pdf  # noqa: E402
# Panggil rf.report1/2/3/5/6(...) dan ai_pdf.make_training_report(...) dengan data sintetis
# sesuai tanda tangan di REPORT_SPEC.md. Pengukuran halaman: QPdfWriter A4 @120dpi = 958 x 1369 px.
