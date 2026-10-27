"""Small compatibility shim for Qt5 (QGIS 3) / Qt6 (QGIS 4)."""
from qgis.PyQt.QtCore import QVariant, Qt
try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction


def field_type(kind):
    # QgsField(QVariant.Int) on older QGIS 3; QgsField(QMetaType.Type) on 3.38+/4.
    try:
        from qgis.core import Qgis
        if getattr(Qgis, 'QGIS_VERSION_INT', 99999) < 33800:
            return getattr(QVariant,kind)
    except (ImportError,AttributeError):
        pass
    try:
        from qgis.PyQt.QtCore import QMetaType
        return getattr(QMetaType.Type, kind)
    except (ImportError, AttributeError):
        return getattr(QVariant, kind)


def layer_filter(*kinds):
    """Layer combo filter, e.g. layer_filter('PolygonLayer','PointLayer').

    Qgis.LayerFilter on QGIS 3.34+/4, QgsMapLayerProxyModel.Filter before.
    """
    try:
        from qgis.core import Qgis
        enum = Qgis.LayerFilter
    except (ImportError, AttributeError):
        from qgis.core import QgsMapLayerProxyModel as enum
    flags = getattr(enum, kinds[0])
    for kind in kinds[1:]:
        flags = flags | getattr(enum, kind)
    return flags


def user_role():
    try:
        return Qt.ItemDataRole.UserRole
    except AttributeError:
        return Qt.UserRole


def exec_dialog(dialog):
    return dialog.exec()


def set_pdf_a4(pdf):
    """Set A4 through QPageLayout, supported by older Qt5 and Qt6 bindings."""
    from qgis.PyQt.QtGui import QPageSize
    layout = pdf.pageLayout()
    layout.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    if not pdf.setPageLayout(layout):
        raise RuntimeError('Tidak dapat mengatur halaman PDF ke A4.')
