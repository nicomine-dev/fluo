# -*- mode: python ; coding: utf-8 -*-
# Compilar:  python -m PyInstaller fluo.spec --noconfirm
#
# Modo onedir a propósito: el onefile descomprime todo en cada arranque y en un
# disco mecánico son 15-20 segundos de espera.
#
# Dos variantes según el Python que compila:
#   - Python 3.9 o más -> PySide6 (Qt 6): Windows 10 o más, 64 bits.
#   - Python 3.8       -> PySide2 (Qt 5): build universal de 32 bits, corre en
#     Windows 7 SP1, 8, 8.1, 10 y 11 (32 y 64 bits). Es el que se publica.
import glob
import os
import platform

ROOT = os.path.abspath(SPECPATH)
RESOURCES = os.path.join(ROOT, "fluo", "resources")

try:
    import PySide6  # noqa: F401

    QT, QTV = "PySide6", "Qt6"
except ImportError:
    QT, QTV = "PySide2", "Qt5"
OTHER_QT = "PySide2" if QT == "PySide6" else "PySide6"
IS_32BIT = platform.architecture()[0] == "32bit"

QT_MODULES_UNUSED = [
    "QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngine", "QtWebEngineQuick", "QtQml",
    "QtQuick", "QtQuickWidgets", "QtQuick3D", "Qt3DCore", "Qt3DRender", "Qt3DInput",
    "Qt3DLogic", "Qt3DAnimation", "Qt3DExtras", "QtMultimedia", "QtMultimediaWidgets",
    "QtCharts", "QtDataVisualization", "QtPdf", "QtPdfWidgets", "QtBluetooth", "QtNfc",
    "QtPositioning", "QtLocation", "QtRemoteObjects", "QtSensors", "QtSerialPort",
    "QtSerialBus", "QtSql", "QtTest", "QtTextToSpeech", "QtWebChannel", "QtWebSockets",
    "QtWebView", "QtDesigner", "QtHelp", "QtUiTools", "QtOpenGL", "QtOpenGLWidgets",
    "QtNetworkAuth", "QtScxml", "QtStateMachine", "QtHttpServer", "QtSpatialAudio",
    "QtGraphs", "QtGraphsWidgets", "QtAxContainer", "QtSvgWidgets", "QtConcurrent", "QtXml",
    "QtPrintSupport", "QtXmlPatterns", "QtScript", "QtScriptTools", "QtWinExtras", "QtNetwork",
]
excludes = ["tkinter", "unittest", "pydoc", "doctest", "test", "PIL", OTHER_QT, "PyQt5", "PyQt6"]
excludes += [f"{QT}.{m}" for m in QT_MODULES_UNUSED]

# Windows 7 sin todas las actualizaciones no trae el Universal CRT: en el build
# legacy lo incluimos desde el Windows SDK, si está instalado (en GitHub Actions lo está).
binaries = []
if QT == "PySide2":
    arch = "x86" if IS_32BIT else "x64"
    for base in filter(None, (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"))):
        kits = os.path.join(base, "Windows Kits", "10", "Redist")
        found = glob.glob(os.path.join(kits, "*", "ucrt", "DLLs", arch, "*.dll")) or glob.glob(
            os.path.join(kits, "ucrt", "DLLs", arch, "*.dll")
        )
        if found:
            binaries = [(f, ".") for f in sorted(found)]
            break

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=[(RESOURCES, os.path.join("fluo", "resources"))],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# --- recorte: Qt arrastra módulos que no usamos (QML/Quick, OpenGL por software,
# teclado virtual, red, WebEngine). Sacarlos baja el paquete a la mitad.
_Q = QT + "/"
DROP_PREFIXES = tuple(
    _Q + n
    for n in (
        "opengl32sw.dll", "d3dcompiler_47.dll", "libEGL.dll", "libGLESv2.dll",
        f"{QTV}Quick", f"{QTV}Pdf.dll", f"{QTV}OpenGL.dll",
        f"{QTV}VirtualKeyboard.dll", "QtNetwork.pyd", f"{QTV}WebEngine",
        "QtWebEngineProcess.exe", "resources/", f"{QTV}Multimedia", f"{QTV}Sql.dll",
        f"{QTV}Test.dll", f"{QTV}Xml.dll", f"{QTV}XmlPatterns.dll", f"{QTV}Concurrent.dll",
        f"{QTV}PrintSupport.dll", f"{QTV}DBus.dll", f"{QTV}Positioning", f"{QTV}Location",
        f"{QTV}Sensors", f"{QTV}WebChannel", f"{QTV}WebSockets", f"{QTV}Bluetooth", f"{QTV}Nfc",
        f"{QTV}SerialPort", f"{QTV}RemoteObjects", f"{QTV}Charts", f"{QTV}DataVisualization",
        f"{QTV}3D", f"{QTV}Scxml", f"{QTV}TextToSpeech", f"{QTV}Help.dll", f"{QTV}Designer",
        f"{QTV}WinExtras", f"{QTV}Script",
        "plugins/platforminputcontexts/", "plugins/imageformats/qpdf", "plugins/tls/",
        "plugins/networkinformation/", "plugins/qmltooling/", "plugins/scenegraph/",
        "plugins/bearer/", "plugins/sqldrivers/", "plugins/mediaservice/", "plugins/audio/",
        "plugins/playlistformats/", "plugins/printsupport/", "plugins/position/",
        "plugins/sensors/", "plugins/sensorgestures/", "plugins/canbus/", "plugins/geoservices/",
        "plugins/texttospeech/", "plugins/virtualkeyboard/", "plugins/webview/",
        "plugins/designer/", "plugins/geometryloaders/", "plugins/renderers/",
        "plugins/renderplugins/", "plugins/sceneparsers/", "qml/", "translations/qtwebengine",
        "plugins/platformthemes/", "plugins/generic/qtuiotouchplugin",
        "plugins/platforms/qwebgl", "plugins/platforms/qminimal",
    )
) + ("libcrypto-3-x64.dll", "libssl-3-x64.dll")
# En Qt 5, pyside2.abi3.dll depende de Qt5Qml, y Qt5Qml de Qt5Network: hay que dejarlos.
if QT == "PySide6":
    DROP_PREFIXES += (_Q + "Qt6Qml", _Q + "Qt6Network.dll")
else:
    DROP_PREFIXES += (_Q + "Qt5QmlModels.dll", _Q + "Qt5QmlWorkerScript.dll")
KEEP_TRANSLATIONS = ("qtbase_es.qm", "qtbase_en.qm")


def _drop(entry):
    dest = entry[0].replace("\\", "/")
    if dest.startswith(DROP_PREFIXES):
        return True
    if dest.startswith(_Q + "translations/") and not dest.endswith(KEEP_TRANSLATIONS):
        return True
    return False


a.binaries = [e for e in a.binaries if not _drop(e)]
a.datas = [e for e in a.datas if not _drop(e)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Fluo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(RESOURCES, "fluo.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Fluo",
)
