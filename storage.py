"""GeoPackage/GeoJSON/Shapefile writers, zipped CSV and consolidated Qt PDF."""
import csv
import zipfile
from pathlib import Path

from qgis.core import QgsProject, QgsVectorFileWriter

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
    if driver == 'GPKG':
        # GeoPackage reserves its FID column for an integer primary key. Keep
        # a source attribute named "fid" (which may be text or non-unique) as
        # ordinary data by assigning a different name to the generated key.
        names = {field.name().lower() for field in layer.fields()}
        if 'fid' in names:
            fid_name = '__nibnop_fid'
            suffix_number = 2
            while fid_name.lower() in names:
                fid_name = '__nibnop_fid_%d' % suffix_number
                suffix_number += 1
            opts.layerOptions = ['FID=' + fid_name]
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
