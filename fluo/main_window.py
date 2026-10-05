"""Ventana principal: alterna entre la biblioteca y el editor."""
from __future__ import annotations

import logging
import os

from .qt import (
    QApplication,
    QIcon,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QSettings,
    QStackedWidget,
    Qt,
    QTimer,
    exec_,
)

from . import APP_NAME, __version__
from .editor.document import PdfDocument
from .editor.editor import EditorWidget
from .library.store import RECENT_ID, LibraryStore
from .library.view import LibraryView
from .paths import library_file, resource_path
from .updater import Downloader, UpdateChecker, is_frozen, launch_installer

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, check_updates: bool | None = None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        icon_path = resource_path("fluo.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1180, 760)

        self.store = LibraryStore(library_file())
        self.library = LibraryView(self.store)
        self.library.openRequested.connect(self.open_pdf)
        self.library.statusMessage.connect(lambda m: self.statusBar().showMessage(m, 5000))
        self.stack = QStackedWidget()
        self.stack.addWidget(self.library)
        self.setCentralWidget(self.stack)
        self.editor: EditorWidget | None = None
        self._editor_library_id = ""
        self.statusBar().showMessage(f"{APP_NAME} {__version__}", 4000)

        self._settings = QSettings()
        geometry = self._settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        self._checker: UpdateChecker | None = None
        self._downloader: Downloader | None = None
        if check_updates is None:
            check_updates = is_frozen()
        if check_updates:
            QTimer.singleShot(3000, self._check_updates)

    # ------------------------------------------------------------------ abrir / cerrar
    def open_pdf(self, path: str, library_id: str = "") -> None:
        if self.editor is not None:
            return
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Archivo no encontrado", f"No encuentro el archivo:\n{path}")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            document = PdfDocument(path)
        except Exception as exc:  # noqa: BLE001 - se informa al usuario
            QApplication.restoreOverrideCursor()
            log.exception("No pude abrir %s", path)
            QMessageBox.critical(self, "No se pudo abrir el PDF", f"{path}\n\n{exc}")
            return
        try:
            editor = EditorWidget(document, start_page=self.store.last_page(path))
        finally:
            QApplication.restoreOverrideCursor()
        editor.backRequested.connect(self.close_editor)
        editor.savedAs.connect(self._on_saved_as)
        editor.titleChanged.connect(lambda t: self.setWindowTitle(f"{t} — {APP_NAME}"))
        self.editor = editor
        self._editor_library_id = library_id
        self.stack.addWidget(editor)
        self.stack.setCurrentWidget(editor)
        self.setWindowTitle(f"{document.filename} — {APP_NAME}")
        self.store.touch_opened(document.path)
        self.store.save()

    def close_editor(self) -> bool:
        editor = self.editor
        if editor is None:
            return True
        if not editor.confirm_close():
            return False
        self._remember_position(editor)
        self.stack.removeWidget(editor)
        editor.shutdown()
        editor.deleteLater()
        self.editor = None
        self.library.refresh_all()
        self.stack.setCurrentWidget(self.library)
        self.setWindowTitle(APP_NAME)
        return True

    def _remember_position(self, editor: EditorWidget) -> None:
        self.store.set_last_page(editor.document.path, editor.view.current_page)
        self.store.save()

    def _on_saved_as(self, new_path: str) -> None:
        lib_id = self._editor_library_id
        if lib_id and lib_id != RECENT_ID and self.store.get(lib_id):
            if self.store.add_items(lib_id, [new_path]):
                name = self.store.get(lib_id).name
                self.statusBar().showMessage(f"La copia se agregó a la biblioteca «{name}».", 6000)
        self.store.touch_opened(new_path)
        self.store.save()

    def closeEvent(self, event) -> None:
        if self.editor is not None and not self.close_editor():
            event.ignore()
            return
        self._settings.setValue("geometry", self.saveGeometry())
        self.library.shutdown()
        event.accept()

    # ------------------------------------------------------------------ actualizaciones
    def _check_updates(self) -> None:
        self._checker = UpdateChecker(self)
        self._checker.available.connect(self._offer_update)
        self._checker.start()

    def _offer_update(self, info: dict) -> None:
        size_mb = info["size"] / (1024 * 1024) if info.get("size") else 0
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Hay una versión nueva")
        box.setText(f"{APP_NAME} {info['version']} está disponible (tenés la {__version__}).")
        detail = "¿La descargo e instalo ahora? La app se cierra y vuelve a abrir sola."
        if size_mb:
            detail += f"\nDescarga: {size_mb:.0f} MB."
        box.setInformativeText(detail)
        if info.get("notes"):
            box.setDetailedText(info["notes"])
        yes = box.addButton("Actualizar ahora", QMessageBox.AcceptRole)
        box.addButton("Más tarde", QMessageBox.RejectRole)
        box.setDefaultButton(yes)
        exec_(box)
        if box.clickedButton() is yes:
            self._download_update(info)

    def _download_update(self, info: dict) -> None:
        if self.editor is not None and not self.close_editor():
            return
        progress = QProgressDialog("Descargando la actualización…", "Cancelar", 0, 100, self)
        progress.setWindowTitle("Actualizando")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        self._downloader = Downloader(info["url"], info["name"], self)

        def on_progress(received: int, total: int) -> None:
            if total:
                progress.setMaximum(100)
                progress.setValue(int(received * 100 / total))
            else:
                progress.setMaximum(0)

        def on_done(path: str) -> None:
            progress.close()
            launch_installer(path)
            QApplication.quit()

        def on_failed(err: str) -> None:
            progress.close()
            QMessageBox.warning(
                self,
                "No se pudo descargar",
                f"Falló la descarga de la actualización.\n\n{err}\n\n"
                f"Podés bajarla a mano desde:\n{info.get('page', '')}",
            )

        self._downloader.progress.connect(on_progress)
        self._downloader.done.connect(on_done)
        self._downloader.failed.connect(on_failed)
        progress.canceled.connect(self._downloader.terminate)
        self._downloader.start()
