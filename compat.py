"""Compatibility layer for QGIS 3 and QGIS 4 / PyQt5 and PyQt6."""
try:
    from qgis.PyQt.QtWidgets import QAction
except ImportError:
    from qgis.PyQt.QtGui import QAction

# Menangani perbedaan PyQt5 dan PyQt6 (QGIS 3.40 menggunakan QMetaType)
try:
    from qgis.PyQt.QtCore import QMetaType
    HAS_METATYPE = True
except ImportError:
    HAS_METATYPE = False

try:
    from qgis.PyQt.QtCore import QVariant
    HAS_VARIANT = True
except ImportError:
    HAS_VARIANT = False

def field_type(kind):
    """Menerjemahkan string tipe data ke QMetaType atau QVariant yang aman untuk QGIS."""
    if isinstance(kind, int):
        return kind
        
    k = str(kind).strip().lower()
    
    # 1. Coba gunakan QMetaType (Standar PyQt6 / QGIS 3.30+)
    if HAS_METATYPE:
        try:
            if k in ('int', 'integer'):
                return QMetaType.Type.Int
            elif k in ('double', 'float', 'real', 'decimal'):
                return QMetaType.Type.Double
            elif k in ('string', 'text', 'str', 'varchar'):
                return QMetaType.Type.QString
            elif k in ('bool', 'boolean'):
                return QMetaType.Type.Bool
        except AttributeError:
            pass
            
    # 2. Coba gunakan QVariant (Standar PyQt5 / QGIS lama)
    if HAS_VARIANT:
        try:
            if k in ('int', 'integer'):
                return getattr(QVariant, 'Int', 2)
            elif k in ('double', 'float', 'real', 'decimal'):
                return getattr(QVariant, 'Double', 6)
            elif k in ('string', 'text', 'str', 'varchar'):
                return getattr(QVariant, 'String', 10)
            elif k in ('bool', 'boolean'):
                return getattr(QVariant, 'Bool', 1)
        except AttributeError:
            pass
            
    # 3. Fallback langsung ke kode tipe data numerik QMetaType jika modul Qt gagal
    if k in ('int', 'integer'):
        return 2  # QMetaType::Int
    elif k in ('double', 'float', 'real', 'decimal'):
        return 6  # QMetaType::Double
    elif k in ('bool', 'boolean'):
        return 1  # QMetaType::Bool
        
    return 10  # QMetaType::QString (Default String)