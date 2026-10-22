"""QGIS plugin entry point."""

def classFactory(iface):
    from .plugin import NibNopPlugin
    return NibNopPlugin(iface)
