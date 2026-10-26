"""Dropdown semua kolom atribut pada layer terpilih (QGIS 3 dan 4).

Tidak memakai QgsFieldComboBox yang dapat menerapkan proxy filter berbasis jenis
field. Pemilihan *nama* kolom selalu bebas; validitas isi (mis. luas numerik)
diperiksa terpisah oleh mesin audit.
"""
from qgis.PyQt.QtWidgets import QComboBox

PREFERRED_FIELDS = {
    ('bpn', 'identity'): ('NIB', 'D_NIB', 'ID_BIDANG'),
    ('pbb', 'identity'): ('D_NOP', 'NOP', 'NO_NOP'),
    ('bpn', 'area'): ('LUAS', 'LUAS_TANAH', 'LUASTANAH', 'LUAS_TERDAFTAR', 'LAND_AREA', 'AREA'),
    ('pbb', 'area'): ('D_LUAS', 'LUAS_TANAH', 'LUAS', 'LUASTANAH', 'LAND_AREA', 'AREA'),
    # Optional name fields: pemegang hak (BPN) vs wajib pajak (PBB).
    ('bpn', 'name'): ('NAMA', 'NAMA_PEMILIK', 'NM_PEMILIK', 'PEMILIK', 'NAMA_PEMEGANG',
                      'PEMEGANG_HAK', 'NAMA_HAK', 'NM_PEMEGANG'),
    ('pbb', 'name'): ('NM_WP', 'D_NM_WP', 'NAMA_WP', 'NM_WP_SPPT', 'NAMA_WAJIB_PAJAK',
                      'WAJIB_PAJAK', 'NAMA'),
}

# First item of an optional dropdown; currentField() returns '' for it.
NONE_LABEL = '(tidak digunakan)'


def select_default_field(names, theme='bpn', role='area', previous=''):
    """Return previous selection if available or a conventional default.

    Return '' if there is no familiar field to avoid silently taking e.g. NIB
    as the written area. All fields still appear in the dropdown.
    """
    table = {str(name).strip().casefold(): str(name) for name in names}
    if previous and previous.strip().casefold() in table:
        return table[previous.strip().casefold()]
    for suggested in PREFERRED_FIELDS.get((theme, role), ()):
        if suggested.casefold() in table:
            return table[suggested.casefold()]
    return ''


class LayerFieldComboBox(QComboBox):
    """Shows ALL attribute fields from the currently chosen vector layer.

    Accepts text/number/date/other data types in the selector; each processing
    module decides whether chosen *values* are numerically meaningful.
    """

    def __init__(self, theme='bpn', role='area', parent=None, optional=False):
        super().__init__(parent)
        self.theme = theme
        self.role = role
        self.optional = optional
        self._layer = None
        self.setMinimumWidth(180)
        self.setToolTip('Semua kolom atribut layer tersedia. Pilih kolom yang sesuai.')

    def _disconnect_previous(self):
        layer = self._layer
        if layer is not None:
            signal = getattr(layer, 'updatedFields', None)
            if signal is not None:
                try:
                    signal.disconnect(self.refresh_fields)
                except (TypeError, RuntimeError):
                    pass

    def setLayer(self, layer):
        if layer is not self._layer:
            self._disconnect_previous()
            self._layer = layer
            signal = getattr(layer, 'updatedFields', None)
            if signal is not None:
                try:
                    signal.connect(self.refresh_fields)
                except (TypeError, RuntimeError):
                    pass
            # Treat a different layer as a fresh selection. E.g. the old BPN
            # field should not overwrite the default field for the new PBB.
            self.refresh_fields(preserve_selection=False)
        else:
            self.refresh_fields(preserve_selection=True)

    def refresh_fields(self, *args, preserve_selection=True):
        previous = self.currentField() if preserve_selection else ''
        # An optional field the operator explicitly switched off stays off.
        keep_none = (preserve_selection and self.optional and
                     self.currentIndex() == 0 and self.currentText() == NONE_LABEL)
        layer = self._layer
        names = []
        # A raster/mesh layer (no fields()) gives an empty list, not a crash.
        if layer is not None and hasattr(layer, 'fields') and hasattr(layer, 'isValid') and layer.isValid():
            names = [field.name() for field in layer.fields()]
        self.blockSignals(True)
        try:
            self.clear()
            self.addItems(([NONE_LABEL] if self.optional else []) + names)
            wanted = '' if keep_none else select_default_field(
                names, self.theme, self.role, previous)
            if wanted:
                self.setCurrentIndex(self.findText(wanted))
            else:
                self.setCurrentIndex(0 if self.optional else -1)
            self.setEnabled(bool(names))
        finally:
            self.blockSignals(False)

    def currentField(self):
        if self.currentIndex() < 0:
            return ''
        if self.optional and self.currentIndex() == 0 and self.currentText() == NONE_LABEL:
            return ''
        return self.currentText().strip()

    def setField(self, name):
        idx = self.findText(name)
        if idx >= 0:
            self.setCurrentIndex(idx)

    def layer(self):
        return self._layer


# Compatibility alias for other modules/plugins that imported the old name.
class AreaFieldComboBox(LayerFieldComboBox):
    def __init__(self, theme='bpn', parent=None):
        super().__init__(theme=theme, role='area', parent=parent)
