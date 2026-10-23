"""Tests unrestricted field dropdowns without requiring installed QGIS GUI."""
import importlib.util
import pathlib
import sys
import types
import unittest

class StubSignal:
    def __init__(self): self.callbacks=[]
    def connect(self, callback): self.callbacks.append(callback)
    def disconnect(self, callback): self.callbacks.remove(callback)
    def emit(self):
        for callback in list(self.callbacks): callback()

class StubField:
    def __init__(self, name, typ): self._name=name;self._typ=typ
    def name(self): return self._name
    def type(self): return self._typ

class StubLayer:
    def __init__(self, names):
        self._fields=[StubField(name, typ) for name,typ in names]
        self.updatedFields=StubSignal()
    def isValid(self): return True
    def fields(self): return self._fields
    def rename(self, new_names):
        self._fields=[StubField(name,typ) for name,typ in new_names]
        self.updatedFields.emit()

class StubCombo:
    def __init__(self, parent=None): self.values=[];self.index=-1;self.enabled=True
    def setToolTip(self,value): pass
    def setMinimumWidth(self,value): pass
    def blockSignals(self,value): pass
    def clear(self): self.values=[];self.index=-1
    def addItems(self, names):
        self.values.extend(names)
        if names:self.index=0
    def currentIndex(self): return self.index
    def setCurrentIndex(self, index): self.index=index
    def currentText(self): return self.values[self.index] if 0 <= self.index < len(self.values) else ''
    def findText(self,name): return self.values.index(name) if name in self.values else -1
    def setEnabled(self,state): self.enabled=bool(state)

qgis = types.ModuleType('qgis')
pyqt = types.ModuleType('qgis.PyQt')
widgets = types.ModuleType('qgis.PyQt.QtWidgets')
widgets.QComboBox=StubCombo
sys.modules.setdefault('qgis',qgis)
sys.modules.setdefault('qgis.PyQt',pyqt)
sys.modules.setdefault('qgis.PyQt.QtWidgets',widgets)
path = pathlib.Path(__file__).resolve().parents[1] / 'fieldwidgets.py'
spec = importlib.util.spec_from_file_location('nibnop_fieldwidgets_under_test',path)
fieldwidgets=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fieldwidgets)

class DropdownTests(unittest.TestCase):
    def test_default_fields_and_all_field_types(self):
        layer=StubLayer([('NIB','String'),('LUAS','String'),('alamat','String'),('tanggal','Date'),('indeks', 'Int')])
        widget=fieldwidgets.LayerFieldComboBox('bpn','area')
        widget.setLayer(layer)
        self.assertEqual(widget.values,['NIB','LUAS','alamat','tanggal','indeks'])
        self.assertEqual(widget.currentField(),'LUAS')
        widget.setField('alamat')
        self.assertEqual(widget.currentField(),'alamat')
        widget.setLayer(layer)
        self.assertEqual(widget.currentField(),'alamat')

    def test_change_layer_and_renamed_field(self):
        widget=fieldwidgets.LayerFieldComboBox('pbb','area')
        old=StubLayer([('D_NOP','String'),('D_LUAS','String')])
        newer=StubLayer([('NOP_PBB','String'),('luas_pajak','Double'),('alamat','String')])
        widget.setLayer(old)
        self.assertEqual(widget.currentField(),'D_LUAS')
        widget.setLayer(newer)
        self.assertEqual(widget.values,['NOP_PBB','luas_pajak','alamat'])
        self.assertEqual(widget.currentField(),'')  # no arbitrary auto-selection
        widget.setField('luas_pajak')
        self.assertEqual(widget.currentField(),'luas_pajak')
        newer.rename([('NOP_PBB','String'),('luas_baru','Double'),('alamat','String')])
        self.assertEqual(widget.values,['NOP_PBB','luas_baru','alamat'])
        self.assertEqual(widget.currentField(),'')

    def test_identity_can_select_any_name(self):
        layer=StubLayer([('Nomor_Urut', 'Int'),('D_NOP','String'),('alamat','String')])
        widget=fieldwidgets.LayerFieldComboBox('pbb','identity')
        widget.setLayer(layer)
        self.assertEqual(widget.currentField(),'D_NOP')
        widget.setField('Nomor_Urut')
        self.assertEqual(widget.currentField(),'Nomor_Urut')

    def test_optional_name_field(self):
        layer=StubLayer([('NIB','String'),('NAMA','String'),('LUAS','Double')])
        widget=fieldwidgets.LayerFieldComboBox('bpn','name',optional=True)
        widget.setLayer(layer)
        self.assertEqual(widget.values[0],fieldwidgets.NONE_LABEL)
        self.assertEqual(widget.currentField(),'NAMA')
        widget.setCurrentIndex(0)                 # operator switches it off
        self.assertEqual(widget.currentField(),'')
        widget.setLayer(layer)                    # refresh keeps it off
        self.assertEqual(widget.currentField(),'')
        other=StubLayer([('D_NOP','String'),('alamat','String')])
        pbb=fieldwidgets.LayerFieldComboBox('pbb','name',optional=True)
        pbb.setLayer(other)
        self.assertEqual(pbb.currentField(),'')   # no familiar name field

if __name__=='__main__': unittest.main()
