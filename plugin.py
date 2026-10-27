"""QGIS menu/toolbar plugin, seven separate tools (3.1 = PBB titik)."""
from qgis.PyQt.QtWidgets import QMenu
from qgis.PyQt.QtCore import Qt
from .compat import QAction


def _registry():
    from qgis.core import QgsApplication
    return QgsApplication.processingRegistry()


class NibNopPlugin:
    def __init__(self,iface):
        self.iface=iface;self.actions=[];self.dock=None;self.provider=None
    def initProcessing(self):
        # Called by QGIS (hasProcessingProvider=yes), also for qgis_process.
        if self.provider is None:
            from .processing_provider import NibNopProvider
            self.provider=NibNopProvider(self.launch)
            _registry().addProvider(self.provider)
    def initGui(self):
        self.initProcessing()
        self.menu=QMenu('NIB–NOP Integrator',self.iface.mainWindow())
        # Internal id 31 = Modul 3.1 (PBB titik NOP).
        names=[(1,'1. Pemeriksaan kelengkapan'),(2,'2. Kualitas spasial dan fix geometry'),
               (3,'3. Penentuan level pemaduan berbasis aturan (PBB poligon)'),
               (31,'3.1 Penentuan level pemaduan PBB titik (NOP)'),
               (4,'4. Training AI'),
               (5,'5. Prediksi AI independen / Hybrid'),
               (6,'6. Verifikasi Studio interaktif di peta')]
        for i,label in names:
            action=QAction(label,self.iface.mainWindow())
            action.triggered.connect(lambda checked=False,n=i:self.launch(n))
            self.menu.addAction(action);self.actions.append(action)
            self.iface.addPluginToVectorMenu('NIB–NOP Integrator',action)
        self.iface.mainWindow().menuBar().addMenu(self.menu)
    def toolbox_dock(self):
        """The Processing Toolbox panel, if it is in the main window."""
        from qgis.PyQt.QtWidgets import QDockWidget
        for dock in self.iface.mainWindow().findChildren(QDockWidget):
            if 'processingtoolbox' in (dock.objectName() or '').lower().replace('_',''):
                return dock
        return None
    def launch(self,module):
        if module==6:
            from .studio import VerificationDock
            if self.dock is None:
                self.dock=VerificationDock(self.iface,self.iface.mainWindow())
                try:area=Qt.DockWidgetArea.RightDockWidgetArea
                except AttributeError:area=Qt.RightDockWidgetArea
                self.iface.addDockWidget(area,self.dock)
            # Stacked under the Toolbox the panel gets only part of the window height; share
            # the Toolbox's slot as a tab so it uses the full height (the panel also scrolls).
            try:
                toolbox=self.toolbox_dock()
                if toolbox is not None and toolbox.isVisible() and not toolbox.isFloating():
                    self.iface.mainWindow().tabifyDockWidget(toolbox,self.dock)
            except Exception:
                pass
            self.dock.show();self.dock.raise_()
        elif not self.launch_processing_form(module):
            from .dialogs import ToolDialog
            dlg=ToolDialog(self.iface,module,self.iface.mainWindow())
            dlg.exec()
    def launch_processing_form(self,module):
        """Modul 1-5 and 3.1 open the standard Processing form, as in the Toolbox."""
        try:
            from qgis import processing
            from .processing_provider import MODULES
            self.initProcessing()
            processing.execAlgorithmDialog('nib_nop_integrator:'+MODULES[module]['name'])
            return True
        except Exception as exc:
            self.iface.messageBar().pushWarning('NIB–NOP Integrator',
                'Formulir Processing tidak dapat dibuka (%s); memakai jendela lama.'%exc)
            return False
    def unload(self):
        for action in self.actions:
            self.iface.removePluginVectorMenu('NIB–NOP Integrator',action)
        self.actions=[]
        if self.dock is not None:
            self.dock.close()
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater();self.dock=None
        if getattr(self,'menu',None):
            self.iface.mainWindow().menuBar().removeAction(self.menu.menuAction())
            self.menu.deleteLater()
        if self.provider is not None:
            _registry().removeProvider(self.provider)
            self.provider=None
