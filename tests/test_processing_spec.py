"""Processing Toolbox parameters vs. the methods borrowed from ToolDialog. No PyQGIS needed.

HeadlessTool lends ``ToolDialog.run1..run5`` to Batch / Modeler / ``qgis_process``. Those
methods read dialog widgets as ``self.<widget>`` and numbers as ``self.val('<key>')``. If a
module gains a widget (as Modul 4/5 did in v0.9.8) and the Toolbox spec is not updated, a
headless run would crash with AttributeError/KeyError. This test reads ``dialogs.py`` with
``ast`` and checks every attribute and ``val`` key against what the provider supplies.
"""
import ast
import importlib.util
import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PACKAGE = '_nibnop_provider_spec_test'

# Methods ToolDialog lends to a module, plus what they call on ``self``.
USED_BY = {1: ('run1', 'two_layers'),
           2: ('run2', 'two_layers'),
           3: ('run3', 'prepare3', 'opts', 'two_layers', 'report_metadata'),
           31: ('run3', 'prepare3', 'opts', 'two_layers', 'report_metadata'),
           4: ('run4', 'prepared_ml', 'ml_names', 'two_layers'),
           5: ('run5', 'prepared_ml', 'ml_names', 'two_layers')}


class _Dummy:
    def __init__(self, *a, **k):pass


def _stub_qgis():
    core = types.ModuleType('qgis.core')
    core.__getattr__ = lambda name: type(name, (_Dummy,), {})  # any Qgs* name
    qgis = types.ModuleType('qgis');qgis.core = core
    return {'qgis': qgis, 'qgis.core': core}


def _load_provider():
    saved = {k: sys.modules.get(k) for k in ('qgis', 'qgis.core')}
    try:
        sys.modules.update(_stub_qgis())
        pkg = types.ModuleType(PACKAGE);pkg.__path__ = [str(HERE)]
        sys.modules[PACKAGE] = pkg
        engine = types.ModuleType(PACKAGE+'.engine')
        engine.Progress = type('Progress', (), {});engine.Cancelled = type('Cancelled', (Exception,), {})
        storage = types.ModuleType(PACKAGE+'.storage')
        storage.save_layer_to = lambda layer, path, base: path
        sys.modules[PACKAGE+'.engine'] = engine;sys.modules[PACKAGE+'.storage'] = storage
        for name in ('ai_matching', 'processing_provider'):
            spec = importlib.util.spec_from_file_location(PACKAGE+'.'+name, HERE/(name+'.py'))
            mod = importlib.util.module_from_spec(spec);sys.modules[PACKAGE+'.'+name] = mod
            spec.loader.exec_module(mod)
        return sys.modules[PACKAGE+'.processing_provider']
    finally:
        for k, v in saved.items():
            if v is None:sys.modules.pop(k, None)
            else:sys.modules[k] = v


class _Feedback:
    messages = []
    def pushInfo(self, text):self.messages.append(text)
    def pushWarning(self, text):self.messages.append(text)


def _tool_dialog_methods():
    tree = ast.parse((HERE/'dialogs.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ToolDialog')
    return {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}


def _reads(func):
    attrs, keys, guarded = set(), set(), set()
    for node in ast.walk(func):
        # ``self.val('k') if 'k' in self.param else ...`` is optional by design.
        if (isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.In)
                and isinstance(node.left, ast.Constant)):
            guarded.add(node.left.value)
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == 'self'):
            attrs.add(node.attr)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'self'
                and node.func.attr == 'val' and node.args and isinstance(node.args[0], ast.Constant)):
            keys.add(node.args[0].value)
    return attrs, keys - guarded


class ProcessingSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pp = _load_provider()
        cls.methods = _tool_dialog_methods()

    def tool(self, modul):
        pp = self.pp
        values = {'bpn': pp._Selector(None, '', ''), 'pbb': pp._Selector(None, '', ''),
                  'reproject': False}
        for item in pp.MODULES[modul]['params']:
            kind, key = item[:2]
            values[key] = {'n': lambda: float(item[3]), 'b': lambda: item[3], 'f': lambda: '',
                           'e': lambda: item[3][0][0],
                           's': lambda: pp._Selector(None, '', '')}[kind]()
        pp.HeadlessTool.run1 = True  # skip importing the Qt dialogs
        return pp.HeadlessTool(modul, values, '/tmp/out', lambda base: '/tmp/%s.gpkg' % base, _Feedback())

    def test_every_widget_read_by_borrowed_methods_is_supplied(self):
        pp = self.pp
        for modul, names in USED_BY.items():
            tool = self.tool(modul)
            for name in names:
                attrs, keys = _reads(self.methods[name])
                for attr in attrs:
                    ok = hasattr(tool, attr) or attr in pp._BORROWED or attr in ('iface', 'dlg')
                    self.assertTrue(ok, 'Modul %s: %s memakai self.%s yang tidak disediakan Toolbox'
                                    % (modul, name, attr))
                for key in keys:
                    self.assertIn(key, tool.param, 'Modul %s: %s memakai self.val(%r) tanpa parameter'
                                  % (modul, name, key))

    def test_modul4_modul5_expose_v098_choices(self):
        pp = self.pp
        self.assertEqual([v for v, _ in pp.TRAINING_CHOICES], ['GOLD_ONLY', 'SILVER_ONLY', 'SILVER_GOLD'])
        self.assertEqual([v for v, _ in pp.INFERENCE_CHOICES], ['HYBRID', 'AI_ONLY'])
        t4, t5 = self.tool(4), self.tool(5)
        self.assertEqual(t4.training_mode.currentData(), 'GOLD_ONLY')
        self.assertEqual(t5.inference_mode.currentData(), 'HYBRID')
        self.assertEqual(t5.val('confidence'), .90)
        self.assertFalse(t5.promote.isChecked())  # no automatic Level 1 unless the operator opts in

    def test_modul5_has_no_modul3_rule_gates(self):
        keys = {item[1] for item in self.pp.MODULES[5]['params']}
        for gate in ('sim', 'dev', 'overlap', 'min_irisan', 'require_name', 'name_stage'):
            self.assertNotIn(gate, keys)

    def test_modul4_requires_layers(self):
        self.assertFalse(self.pp.MODULES[4].get('optional_layers', False))

    def test_every_persisted_layer_has_its_own_output_parameter(self):
        """run1..run5 save layers with ``self.persist(layer, <basename>, out)``; each basename
        needs an ``OUT_<BASENAME>`` destination in the module's form."""
        pp = self.pp
        for modul, names in USED_BY.items():
            declared = [b for b, _ in pp.OUTPUT_LAYERS[modul]]
            for name in names:
                for node in ast.walk(self.methods[name]):
                    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                            and node.func.attr == 'persist' and len(node.args) >= 2):
                        continue
                    arg = node.args[1]
                    if isinstance(arg, ast.Constant):
                        self.assertIn(arg.value, declared, 'Modul %s menyimpan %r tanpa parameter keluaran'
                                      % (modul, arg.value))
                    else:  # tag + '_suffix'
                        suffix = arg.right.value
                        self.assertTrue(any(d.endswith(suffix) for d in declared),
                                        'Modul %s menyimpan *%s tanpa parameter keluaran' % (modul, suffix))
        # and nothing is declared that no run function writes
        for modul, names in USED_BY.items():
            source = ' '.join(ast.unparse(self.methods[n]) for n in names)
            for base, _ in pp.OUTPUT_LAYERS[modul]:
                tail = base.split('_', 1)[1] if base.startswith(('bpn_', 'pbb_')) else base  # tag + suffix
                self.assertIn(tail, source, 'Modul %s mendeklarasikan keluaran %s yang tidak ditulis' % (modul, base))

    def test_persist_skips_and_records(self):
        tool = self.tool(3)
        self.assertEqual(tool.persist(object(), '01_padanan_level1', None), '/tmp/01_padanan_level1.gpkg')
        self.assertEqual(tool.saved, [('01_padanan_level1', '/tmp/01_padanan_level1.gpkg')])
        tool.resolve = lambda base: ''  # user chose "Skip Output" for this layer
        self.assertTrue(tool.persist(object(), '02_bpn_level2', None).startswith('(dilewati)'))
        tool.resolve = lambda base: '/tmp/x.gpkg';tool.skip = True  # "Lewati semua keluaran"
        self.assertTrue(tool.persist(object(), '03_pbb_level2', None).startswith('(dilewati)'))
        self.assertEqual(len(tool.saved), 1)

    def test_output_names_are_unique_per_module_and_valid(self):
        pp = self.pp
        for modul, outs in pp.OUTPUT_LAYERS.items():
            names = [pp.output_param(b) for b, _ in outs]
            self.assertEqual(len(names), len(set(names)))
            self.assertNotIn('OUTPUT_FOLDER', names)
            self.assertIn(modul, pp.FOLDER_LABELS)
        self.assertEqual(pp.OUTPUT_LAYERS[4], [])  # training writes model/PDF/ZIP to the folder only

    def test_log_is_forwarded_to_feedback(self):
        tool = self.tool(5)
        tool.log.appendPlainText('uji')
        self.assertIn('uji', _Feedback.messages)


if __name__ == '__main__':
    unittest.main()
