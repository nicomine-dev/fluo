"""Capa de compatibilidad Qt.

Fluo corre con PySide6 (Qt 6, Windows 10 o más) o con PySide2 (Qt 5, que llega a
Windows 7 y 8). El resto del código importa todo desde acá y no sabe cuál hay.
"""
from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets

    QT6 = True
except ImportError:  # pragma: no cover - solo en el build legacy
    from PySide2 import QtCore, QtGui, QtWidgets

    QT6 = False

QT_PACKAGE = "PySide6" if QT6 else "PySide2"

_CORE = [
    "QCoreApplication", "QEvent", "QLibraryInfo", "QLocale", "QMutex", "QObject", "QPoint",
    "QPointF", "QRect", "QRectF", "QSettings", "QSize", "Qt", "QThread", "QTimer",
    "QTranslator", "QWaitCondition", "Signal", "Slot",
]
_GUI = [
    "QBrush", "QColor", "QFont", "QGuiApplication", "QIcon", "QImage", "QKeySequence",
    "QMouseEvent", "QPainter", "QPainterPath", "QPainterPathStroker", "QPen", "QPixmap",
    "QTransform",
]
_WIDGETS = [
    "QAbstractItemView", "QApplication", "QButtonGroup", "QColorDialog", "QFileDialog",
    "QFrame", "QGraphicsItem", "QGraphicsScene", "QGraphicsView", "QHBoxLayout",
    "QInputDialog", "QLabel", "QLineEdit", "QListView", "QListWidget", "QListWidgetItem",
    "QMainWindow", "QMenu", "QMessageBox", "QProgressDialog", "QPushButton", "QSizePolicy",
    "QSlider", "QSpinBox", "QSplitter", "QStackedWidget", "QStyle", "QToolBar",
    "QToolButton", "QVBoxLayout", "QWidget",
]
# En Qt 6 estas clases se mudaron de QtWidgets a QtGui.
_MOVED = ["QAction", "QActionGroup", "QUndoCommand", "QUndoStack"]

for _name in _CORE:
    globals()[_name] = getattr(QtCore, _name)
for _name in _GUI:
    globals()[_name] = getattr(QtGui, _name)
for _name in _WIDGETS:
    globals()[_name] = getattr(QtWidgets, _name)
for _name in _MOVED:
    globals()[_name] = getattr(QtGui if QT6 else QtWidgets, _name)

__all__ = _CORE + _GUI + _WIDGETS + _MOVED + [
    "QT6", "QT_PACKAGE", "QtCore", "QtGui", "QtWidgets",
    "event_pos", "exec_", "translations_path", "setup_high_dpi",
]


def event_pos(event) -> "QPoint":
    """Posición local del mouse como QPoint: event.position() en Qt 6, event.pos() en Qt 5."""
    if hasattr(event, "position"):
        return event.position().toPoint()
    return event.pos()


def exec_(obj, *args):
    """dialog.exec() en Qt 6, dialog.exec_() en Qt 5. Sirve para QDialog, QMenu y QApplication."""
    fn = getattr(obj, "exec", None)
    if not callable(fn):
        fn = obj.exec_
    return fn(*args)


def translations_path() -> str:
    if QT6:
        return QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.TranslationsPath)
    return QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.TranslationsPath)


def setup_high_dpi() -> None:
    """Llamar antes de crear la QApplication. Qt 6 ya escala solo; Qt 5 hay que pedírselo."""
    Qt_ = QtCore.Qt
    QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt_.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    if not QT6:
        QtCore.QCoreApplication.setAttribute(Qt_.AA_EnableHighDpiScaling, True)
        QtCore.QCoreApplication.setAttribute(Qt_.AA_UseHighDpiPixmaps, True)
