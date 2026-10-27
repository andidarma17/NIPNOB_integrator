"""GeoPackage/GeoJSON/Shapefile writers, zipped CSV and consolidated Qt PDF."""
import csv
import re
import zipfile
from pathlib import Path

from qgis.core import QgsProject, QgsVectorFileWriter

FORMATS = {
    'GeoPackage (.gpkg)': ('GPKG', '.gpkg'),
    'GeoJSON (.geojson)': ('GeoJSON', '.geojson'),
    'ESRI Shapefile (.shp)': ('ESRI Shapefile', '.shp'),
}


def _write_layer(layer, output, base, driver):
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
    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, output, QgsProject.instance().transformContext(), opts)
    if result[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError('Tidak dapat menyimpan layer %s: %s' % (base, str(result)))
    return output


def save_layer(layer, folder, base, format_name):
    driver, suffix = FORMATS[format_name]
    target = Path(folder) / (base + suffix)
    if target.exists():
        # Windows/QGIS may lock a layer from a previous run. Never overwrite it.
        idx=2
        while (Path(folder)/(base+'__run'+str(idx)+suffix)).exists(): idx+=1
        target=Path(folder)/(base+'__run'+str(idx)+suffix)
    return _write_layer(layer, str(target), base, driver)


def save_layer_to(layer, destination, base):
    """Write ``layer`` to the exact file chosen for one Processing output.

    The driver follows the extension (.gpkg, .geojson, .shp, ...). A path without an
    extension becomes GeoPackage. Database or other non-file destinations are refused
    with a clear message because the layer is written through OGR to a file.
    """
    destination = str(destination)
    scheme = re.match(r'^([A-Za-z][A-Za-z0-9_]+):', destination)  # postgres:, memory:, ...; not "C:"
    if scheme:
        raise RuntimeError('Keluaran "%s" harus berupa berkas (.gpkg, .geojson atau .shp), bukan %s.'
                           % (base, scheme.group(1)))
    target = Path(destination).expanduser()
    suffix = target.suffix.lower()
    if not suffix:
        target = target.with_suffix('.gpkg');suffix = '.gpkg'
    driver = QgsVectorFileWriter.driverForExtension(suffix.lstrip('.'))
    if not driver:
        raise RuntimeError('Format berkas %s untuk keluaran "%s" tidak dikenal. '
                           'Gunakan .gpkg, .geojson atau .shp.' % (suffix, base))
    target.parent.mkdir(parents=True, exist_ok=True)
    return _write_layer(layer, str(target), target.stem if driver == 'GPKG' else base, driver)


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
