# -*- mode: python ; coding: utf-8 -*-
# Compilar:  pyinstaller fluo.spec --noconfirm
# Modo onedir a propósito: el onefile descomprime todo en cada arranque y en un
# disco mecánico son 15-20 segundos de espera.
import os

ROOT = os.path.abspath(SPECPATH)
RESOURCES = os.path.join(ROOT, "fluo", "resources")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(RESOURCES, os.path.join("fluo", "resources"))],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "unittest", "pydoc", "doctest", "test", "PIL",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuick3D",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
        "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras", "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtBluetooth", "PySide6.QtNfc",
        "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtRemoteObjects",
        "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSerialBus", "PySide6.QtSql",
        "PySide6.QtTextToSpeech", "PySide6.QtWebChannel", "PySide6.QtWebSockets",
        "PySide6.QtWebView", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools",
        "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtNetworkAuth", "PySide6.QtScxml",
        "PySide6.QtStateMachine", "PySide6.QtHttpServer", "PySide6.QtSpatialAudio",
        "PySide6.QtGraphs", "PySide6.QtGraphsWidgets", "PySide6.QtAxContainer",
        "PySide6.QtSvgWidgets", "PySide6.QtConcurrent", "PySide6.QtXml", "PySide6.QtPrintSupport",
    ],
    noarchive=False,
)
# --- recorte: Qt arrastra módulos que no usamos (QML/Quick, OpenGL por software,
# teclado virtual, visor PDF de Qt, red). Sacarlos baja el paquete a la mitad.
DROP_PREFIXES = (
    "PySide6/opengl32sw.dll",
    "PySide6/Qt6Quick", "PySide6/Qt6Qml", "PySide6/Qt6Pdf.dll", "PySide6/Qt6OpenGL.dll",
    "PySide6/Qt6VirtualKeyboard.dll", "PySide6/Qt6Network.dll", "PySide6/QtNetwork.pyd",
    "PySide6/plugins/platforminputcontexts/", "PySide6/plugins/imageformats/qpdf",
    "PySide6/plugins/tls/", "PySide6/plugins/networkinformation/",
    "PySide6/plugins/qmltooling/", "PySide6/plugins/scenegraph/", "PySide6/qml/",
    "libcrypto-3-x64.dll", "libssl-3-x64.dll",
)
KEEP_TRANSLATIONS = ("qtbase_es.qm", "qtbase_en.qm")


def _drop(entry):
    dest = entry[0].replace("\\", "/")
    if dest.startswith(DROP_PREFIXES):
        return True
    if dest.startswith("PySide6/translations/") and not dest.endswith(KEEP_TRANSLATIONS):
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
