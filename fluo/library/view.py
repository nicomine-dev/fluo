"""Pantalla de bibliotecas: colecciones de accesos a PDFs con miniaturas."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ..qt import (
    QAbstractItemView,
    QBrush,
    QColor,
    QFileDialog,
    QFont,
    QHBoxLayout,
    QIcon,
    QImage,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPainter,
    QPen,
    QPixmap,
    QPushButton,
    QSize,
    QSplitter,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
    exec_,
)

from .store import RECENT_ID, LibraryStore, norm
from .thumbs import THUMB_H, THUMB_W, ThumbWorker


class DropList(QListWidget):
    """Grilla que acepta PDFs arrastrados desde el Explorador."""

    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


def _placeholder(text: str, color: QColor) -> QPixmap:
    pm = QPixmap(THUMB_W, THUMB_H)
    pm.fill(QColor(245, 245, 247))
    p = QPainter(pm)
    p.setPen(QPen(QColor(205, 205, 210), 2))
    p.drawRect(1, 1, THUMB_W - 3, THUMB_H - 3)
    font = QFont()
    font.setBold(True)
    font.setPointSize(11)
    p.setFont(font)
    p.setPen(color)
    p.drawText(pm.rect().adjusted(8, 8, -8, -8), Qt.AlignCenter | Qt.TextWordWrap, text)
    p.end()
    return pm


def _framed(img: QImage) -> QPixmap:
    pm = QPixmap.fromImage(img).scaled(
        THUMB_W, THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )
    p = QPainter(pm)
    p.setPen(QPen(QColor(0, 0, 0, 70), 1))
    p.drawRect(0, 0, pm.width() - 1, pm.height() - 1)
    p.end()
    return pm


class LibraryView(QWidget):
    openRequested = Signal(str, str)  # ruta, id de biblioteca
    statusMessage = Signal(str)

    def __init__(self, store: LibraryStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._current_id: str | None = None
        self._icons: dict[str, QIcon] = {}
        self._placeholder = QIcon(_placeholder("PDF", QColor(150, 150, 160)))
        self._missing = QIcon(_placeholder("Archivo no encontrado", QColor(200, 60, 60)))

        self.thumbs = ThumbWorker(self)
        self.thumbs.ready.connect(self._on_thumb)
        self.thumbs.start()

        self._build_ui()
        self.refresh_libraries()

    # ------------------------------------------------------------------ armado
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(splitter)

        left = QWidget()
        left.setMinimumWidth(190)
        left.setMaximumWidth(340)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(12, 12, 6, 12)
        title = QLabel("Bibliotecas")
        f = title.font()
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        lv.addWidget(title)
        self.lib_list = QListWidget()
        self.lib_list.currentRowChanged.connect(self._on_library_selected)
        self.lib_list.itemDoubleClicked.connect(lambda _it: self._rename_library())
        lv.addWidget(self.lib_list, 1)
        row = QHBoxLayout()
        self.new_btn = QPushButton("+ Nueva")
        self.new_btn.clicked.connect(self._new_library)
        self.rename_btn = QPushButton("Renombrar")
        self.rename_btn.clicked.connect(self._rename_library)
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.clicked.connect(self._delete_library)
        for b in (self.new_btn, self.rename_btn, self.delete_btn):
            row.addWidget(b)
        lv.addLayout(row)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(6, 12, 12, 12)
        header = QHBoxLayout()
        self.title_label = QLabel("")
        f2 = self.title_label.font()
        f2.setPointSize(15)
        f2.setBold(True)
        self.title_label.setFont(f2)
        header.addWidget(self.title_label)
        header.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(lambda _t: self.refresh_items())
        header.addWidget(self.search)
        self.add_btn = QPushButton("Agregar PDFs…")
        self.add_btn.clicked.connect(self._add_pdfs)
        self.folder_btn = QPushButton("Agregar carpeta…")
        self.folder_btn.clicked.connect(self._add_folder)
        header.addWidget(self.add_btn)
        header.addWidget(self.folder_btn)
        rv.addLayout(header)

        self.hint = QLabel("")
        self.hint.setStyleSheet("color: #777;")
        rv.addWidget(self.hint)

        self.grid = DropList()
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setIconSize(QSize(THUMB_W, THUMB_H))
        self.grid.setGridSize(QSize(THUMB_W + 34, THUMB_H + 58))
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setMovement(QListView.Static)
        self.grid.setWordWrap(True)
        self.grid.setSpacing(4)
        self.grid.setUniformItemSizes(True)
        self.grid.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._context_menu)
        self.grid.itemActivated.connect(self._open_item)
        self.grid.filesDropped.connect(self._add_paths)
        rv.addWidget(self.grid, 1)

        self.empty_label = QLabel("")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("color: #888; font-size: 14px; padding: 24px;")
        rv.addWidget(self.empty_label)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([230, 900])

    # ------------------------------------------------------------------ bibliotecas
    def refresh_libraries(self, select_id: str | None = None) -> None:
        target = select_id or self._current_id
        if target is None:
            target = self.store.libraries[0].id if self.store.libraries else RECENT_ID
        self.lib_list.blockSignals(True)
        self.lib_list.clear()
        recent = QListWidgetItem("Recientes")
        recent.setData(Qt.UserRole, RECENT_ID)
        self.lib_list.addItem(recent)
        for lib in self.store.libraries:
            it = QListWidgetItem(f"{lib.name}   ({len(lib.items)})")
            it.setData(Qt.UserRole, lib.id)
            self.lib_list.addItem(it)
        self.lib_list.blockSignals(False)
        row = 0
        for i in range(self.lib_list.count()):
            if self.lib_list.item(i).data(Qt.UserRole) == target:
                row = i
                break
        if self.lib_list.currentRow() == row:
            self._on_library_selected(row)
        else:
            self.lib_list.setCurrentRow(row)

    def refresh_all(self) -> None:
        """Al volver del editor: las miniaturas pueden haber cambiado."""
        self._icons.clear()
        self.refresh_libraries()

    def _on_library_selected(self, row: int) -> None:
        item = self.lib_list.item(row)
        if item is None:
            return
        self._current_id = item.data(Qt.UserRole)
        is_recent = self._current_id == RECENT_ID
        lib = self.store.get(self._current_id)
        self.title_label.setText("Recientes" if is_recent else (lib.name if lib else ""))
        for b in (self.rename_btn, self.delete_btn, self.add_btn, self.folder_btn):
            b.setEnabled(not is_recent)
        self.hint.setText(
            "Los últimos PDFs que abriste."
            if is_recent
            else "Accesos directos a tus PDFs. Doble clic para abrir y marcar."
        )
        self.refresh_items()

    def _new_library(self) -> None:
        name, ok = QInputDialog.getText(self, "Nueva biblioteca", "Nombre:")
        if ok and name.strip():
            lib = self.store.add_library(name)
            self.store.save()
            self.refresh_libraries(lib.id)

    def _rename_library(self) -> None:
        lib = self.store.get(self._current_id or "")
        if lib is None:
            return
        name, ok = QInputDialog.getText(self, "Renombrar biblioteca", "Nombre:", text=lib.name)
        if ok and name.strip():
            self.store.rename_library(lib.id, name)
            self.store.save()
            self.refresh_libraries(lib.id)

    def _delete_library(self) -> None:
        lib = self.store.get(self._current_id or "")
        if lib is None:
            return
        answer = QMessageBox.question(
            self,
            "Eliminar biblioteca",
            f"¿Eliminar la biblioteca «{lib.name}»?\n\n"
            "Solo se borra la lista: los PDFs quedan en tu disco.",
        )
        if answer == QMessageBox.Yes:
            self.store.remove_library(lib.id)
            self.store.save()
            self._current_id = None
            self.refresh_libraries()

    # ------------------------------------------------------------------ items
    def _entries(self) -> list[tuple[str, str]]:
        if self._current_id == RECENT_ID:
            return [(p, Path(p).stem) for p in self.store.recent]
        lib = self.store.get(self._current_id or "")
        return [(i.path, i.title) for i in lib.items] if lib else []

    def refresh_items(self) -> None:
        self.grid.clear()
        query = self.search.text().strip().lower()
        entries = [
            (p, t)
            for p, t in self._entries()
            if not query or query in t.lower() or query in os.path.basename(p).lower()
        ]
        pending: list[str] = []
        for path, title in entries:
            it = QListWidgetItem(title)
            it.setData(Qt.UserRole, path)
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            it.setSizeHint(QSize(THUMB_W + 28, THUMB_H + 52))
            if os.path.isfile(path):
                it.setToolTip(path)
                icon = self._icons.get(norm(path))
                if icon is None:
                    it.setIcon(self._placeholder)
                    pending.append(path)
                else:
                    it.setIcon(icon)
            else:
                it.setIcon(self._missing)
                it.setForeground(QBrush(QColor(150, 150, 150)))
                it.setToolTip(f"{path}\n(el archivo ya no está en esa ruta)")
            self.grid.addItem(it)

        if entries:
            self.empty_label.hide()
        else:
            if query:
                text = "Nada coincide con la búsqueda."
            elif self._current_id == RECENT_ID:
                text = "Todavía no abriste ningún PDF.\nElegí una biblioteca y hacé doble clic en un PDF."
            else:
                text = (
                    "Esta biblioteca está vacía.\n"
                    "Agregá PDFs con los botones de arriba o arrastralos acá."
                )
            self.empty_label.setText(text)
            self.empty_label.show()
        if pending:
            self.thumbs.request(pending)

    def _on_thumb(self, path: str, img: QImage) -> None:
        if img.isNull():
            return
        icon = QIcon(_framed(img))
        self._icons[norm(path)] = icon
        for i in range(self.grid.count()):
            it = self.grid.item(i)
            if norm(it.data(Qt.UserRole)) == norm(path):
                it.setIcon(icon)

    def _target_library_id(self) -> str | None:
        """Biblioteca destino para agregar: la actual o, en Recientes, una a elegir."""
        if self._current_id and self._current_id != RECENT_ID:
            return self._current_id
        names = [lib.name for lib in self.store.libraries]
        if not names:
            return None
        name, ok = QInputDialog.getItem(
            self, "Agregar a biblioteca", "¿En qué biblioteca?", names, 0, False
        )
        if not ok:
            return None
        return self.store.libraries[names.index(name)].id

    def _add_paths(self, paths: list[str]) -> None:
        pdfs: list[str] = []
        for p in paths:
            if os.path.isdir(p):
                pdfs.extend(self.store.scan_folder(p, recursive=True))
            elif p.lower().endswith(".pdf"):
                pdfs.append(p)
        if not pdfs:
            self.statusMessage.emit("No había PDFs para agregar.")
            return
        lib_id = self._target_library_id()
        if lib_id is None:
            return
        added = self.store.add_items(lib_id, pdfs)
        self.store.save()
        self.refresh_libraries(lib_id)
        skipped = len(pdfs) - added
        msg = f"Se agregaron {added} PDF{'s' if added != 1 else ''}."
        if skipped:
            msg += f" {skipped} ya estaba{'n' if skipped != 1 else ''}."
        self.statusMessage.emit(msg)

    def _add_pdfs(self) -> None:
        paths, _f = QFileDialog.getOpenFileNames(
            self, "Agregar PDFs a la biblioteca", "", "PDF (*.pdf)"
        )
        if paths:
            self._add_paths(paths)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta con PDFs")
        if not folder:
            return
        recursive = (
            QMessageBox.question(
                self, "Subcarpetas", "¿Incluir también los PDFs de las subcarpetas?"
            )
            == QMessageBox.Yes
        )
        pdfs = self.store.scan_folder(folder, recursive)
        if not pdfs:
            QMessageBox.information(self, "Sin PDFs", "No encontré PDFs en esa carpeta.")
            return
        self._add_paths(pdfs)

    def _open_item(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if not os.path.isfile(path):
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Archivo no encontrado")
            box.setText("El PDF ya no está en esa ruta:")
            box.setInformativeText(path)
            remove_btn = box.addButton("Quitar de la lista", QMessageBox.DestructiveRole)
            box.addButton(QMessageBox.Close)
            exec_(box)
            if box.clickedButton() is remove_btn:
                self._remove_paths([path])
            return
        self.openRequested.emit(path, self._current_id or "")

    def _selected_paths(self) -> list[str]:
        return [it.data(Qt.UserRole) for it in self.grid.selectedItems()]

    def _remove_paths(self, paths: list[str]) -> None:
        for p in paths:
            if self._current_id == RECENT_ID:
                self.store.remove_recent(p)
            elif self._current_id:
                self.store.remove_item(self._current_id, p)
        self.store.save()
        self.refresh_libraries()

    def _move_paths(self, paths: list[str], to_id: str) -> None:
        for p in paths:
            self.store.move_item(self._current_id or "", to_id, p)
        self.store.save()
        self.refresh_libraries()

    def _context_menu(self, pos) -> None:
        menu = QMenu(self)
        item = self.grid.itemAt(pos)
        is_recent = self._current_id == RECENT_ID
        if item is None:
            if not is_recent:
                menu.addAction("Agregar PDFs…", self._add_pdfs)
                menu.addAction("Agregar carpeta…", self._add_folder)
            if menu.actions():
                exec_(menu, self.grid.mapToGlobal(pos))
            return
        if not item.isSelected():
            self.grid.setCurrentItem(item)
        paths = self._selected_paths() or [item.data(Qt.UserRole)]
        many = len(paths) > 1
        menu.addAction("Abrir", lambda: self._open_item(item))
        menu.addSeparator()
        if is_recent:
            menu.addAction(
                "Quitar de recientes" + (f" ({len(paths)})" if many else ""),
                lambda: self._remove_paths(paths),
            )
        else:
            menu.addAction(
                "Quitar de la biblioteca" + (f" ({len(paths)})" if many else ""),
                lambda: self._remove_paths(paths),
            )
            others = [lib for lib in self.store.libraries if lib.id != self._current_id]
            if others:
                move = menu.addMenu("Mover a")
                for lib in others:
                    move.addAction(lib.name, lambda lid=lib.id: self._move_paths(paths, lid))
        menu.addSeparator()
        menu.addAction("Mostrar en el Explorador", lambda: self._show_in_explorer(paths[0]))
        exec_(menu, self.grid.mapToGlobal(pos))

    @staticmethod
    def _show_in_explorer(path: str) -> None:
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        except OSError:
            pass

    def shutdown(self) -> None:
        self.thumbs.stop()
