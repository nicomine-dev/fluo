"""Arranque de la aplicación."""
from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, Qt, QTranslator
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME, ORG_NAME, __version__
from .paths import log_file


def _setup_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(log_file(), encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def _install_excepthook() -> None:
    def hook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        logging.getLogger("fluo").error("Error no controlado:\n%s", text)
        if QApplication.instance() is not None:
            box = QMessageBox()
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle(f"{APP_NAME}: error inesperado")
            box.setText("Pasó algo que no esperaba. Guardá tu trabajo si podés.")
            box.setDetailedText(text)
            box.exec()

    sys.excepthook = hook


def _install_qt_translations(app: QApplication) -> None:
    """Botones estándar de Qt (Cancelar, Sí, No…) en castellano."""
    translator = QTranslator(app)
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(QLocale("es"), "qtbase", "_", path):
        app.installTranslator(translator)


def main() -> int:
    _setup_logging()
    _install_excepthook()
    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(__version__)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _install_qt_translations(app)

    from .main_window import MainWindow  # import tardío: la UI tarda en cargar

    window = MainWindow()
    window.show()
    for arg in sys.argv[1:]:
        if arg.lower().endswith(".pdf"):
            window.open_pdf(arg, "")
            break
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
