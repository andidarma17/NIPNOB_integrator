"""GeoPackage/GeoJSON/Shapefile writers, zipped CSV and consolidated Qt PDF."""
import csv
import os
import zipfile
import textwrap
from pathlib import Path
from .compat import set_pdf_a4

from qgis.core import QgsProject, QgsVectorFileWriter
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPdfWriter, QPageSize, QPainter, QPen, QColor, QFont

FORMATS = {
    'GeoPackage (.gpkg)': ('GPKG', '.gpkg'),
    'GeoJSON (.geojson)': ('GeoJSON', '.geojson'),
    'ESRI Shapefile (.shp)': ('ESRI Shapefile', '.shp'),
}


def save_layer(layer, folder, base, format_name):
    driver, suffix = FORMATS[format_name]
    target = Path(folder) / (base + suffix)
    if target.exists():
        # Windows/QGIS may lock a layer from a previous run. Never overwrite it.
        idx=2
        while (Path(folder)/(base+'__run'+str(idx)+suffix)).exists(): idx+=1
        target=Path(folder)/(base+'__run'+str(idx)+suffix)
    output = str(target)
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = driver
    opts.fileEncoding = 'UTF-8'
    opts.layerName = base
    # Keep outputs separate to avoid over-writing previous GeoPackage layer tables.
    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, output, QgsProject.instance().transformContext(), opts)
    if result[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError('Tidak dapat menyimpan layer %s: %s' % (base, str(result)))
    return output


def zip_csv(output_dir, tables, zip_name='rekap_csv.zip'):
    path = Path(output_dir) / zip_name
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, rows in tables.items():
            if not rows:
                rows = [{'keterangan': 'Tidak ada temuan'}]
            fieldnames = sorted({k for r in rows for k in r})
            from io import StringIO
            io = StringIO()
            w = csv.DictWriter(io, fieldnames=fieldnames, extrasaction='ignore')
            w.writeheader()
            for r in rows:
                w.writerow({k: '' if v is None else v for k, v in r.items()})
            z.writestr(name if name.endswith('.csv') else name+'.csv',
                       '\ufeff'+io.getvalue())
    return str(path)


def create_report(output_dir, module, notes, stats, charts=None, logs=None):
    """Single readable multipage PDF; charts painted directly with Qt."""
    path = str(Path(output_dir) / ('laporan_%s.pdf' % module))
    pdf = QPdfWriter(path)
    set_pdf_a4(pdf)
    pdf.setResolution(110)
    painter = QPainter(pdf)
    W, H = pdf.width(), pdf.height()
    left = 52
    y = 76
    height_limit = H - 78
    blue = QColor('#123B62')
    gray = QColor('#4b5563')
    def newpage():
        nonlocal y
        pdf.newPage()
        y = 76
    def line(text='', size=10, bold=False, color=None, spacing=21):
        nonlocal y
        for part in textwrap.wrap(str(text), width=99 if size<=10 else 76) or ['']:
            if y > height_limit:
                newpage()
            font = QFont('DejaVu Sans', size)
            font.setBold(bold)
            painter.setFont(font)
            painter.setPen(QPen(color or gray))
            painter.drawText(left, y, part)
            y += spacing
    line('NIB - NOP | LAPORAN PEMERIKSAAN', 16, True, blue, 38)
    line(module, 13, True, blue, 30)
    line('Ringkasan proses dan tindak lanjut untuk operator', 10, color=gray, spacing=33)
    line('PARAMETER DAN METODE', 12, True, blue, 28)
    for n in notes: line('• '+str(n))
    y += 18
    line('HASIL UTAMA', 12, True, blue, 30)
    for k,v in stats.items(): line('%s : %s' % (k, v), 10, spacing=25)
    if charts:
        y+=15
        line('GRAFIK REKAP', 12, True, blue, 28)
        for title, values in charts:
            if y>height_limit-185: newpage()
            line(title, 10, True, blue, 27)
            vals = list(values.items())
            m = max([float(v) for _,v in vals]+[1])
            for label, value in vals[:12]:
                if y>height_limit-40: newpage()
                painter.setFont(QFont('DejaVu Sans', 9))
                painter.setPen(QPen(gray))
                painter.drawText(left, y, str(label)[:26])
                xbar=260
                painter.fillRect(xbar, y-12, int((W-xbar-104)*float(value)/m), 13, blue)
                painter.drawText(W-94, y, str(value))
                y+=27
            y+=13
    if logs:
        if y>height_limit-60:newpage()
        line('LOG DAN PERINGATAN', 12, True, blue, 28)
        for msg in logs[:180]: line('• '+str(msg), 9, spacing=18)
    line('Catatan: hasil otomatis perlu verifikasi sesuai prosedur dan sumber resmi.', 9,
         color=gray, spacing=24)
    painter.end()
    return path


def complete_report(output_dir, module, notes, stats, tables, charts=None, logs=None):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    zpath=zip_csv(output_dir, tables)
    ppath=create_report(output_dir,module,notes,stats,charts,logs)
    return {'csv_zip': zpath, 'pdf': ppath}
