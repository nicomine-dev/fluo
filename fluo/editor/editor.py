"""Pantalla de edición: barras de herramientas + vista del PDF + guardado."""
from __future__ import annotations

import os

from typing import Dict, List, Tuple

from ..qt import (
    QAction,
    QActionGroup,
    QApplication,
    QButtonGroup,
    QColor,
    QColorDialog,
    QFileDialog,
    QIcon,
    QKeySequence,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPainter,
    QPixmap,
    QSize,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStyle,
    Qt,
    QTimer,
    QToolBar,
    QToolButton,
    QWidget,
    Signal,
    exec_,
)

from .document import PdfDocument
from .view import PdfView, Tool

RGB = Tuple[float, float, float]

PALETTE: List[Tuple[RGB, str]] = [
    ((1.0, 0.92, 0.23), "Amarillo"),
    ((0.55, 0.9, 0.35), "Verde"),
    ((0.45, 0.78, 1.0), "Celeste"),
    ((1.0, 0.55, 0.78), "Rosa"),
    ((1.0, 0.65, 0.2), "Naranja"),
    ((0.9, 0.18, 0.18), "Rojo"),
    ((0.15, 0.3, 0.9), "Azul"),
    ((0.12, 0.12, 0.12), "Negro"),
]
YELLOW, RED, BLUE = PALETTE[0][0], PALETTE[5][0], PALETTE[6][0]
DEFAULT_COLORS: Dict[Tool, RGB] = {
    Tool.HIGHLIGHT: YELLOW,
    Tool.UNDERLINE: RED,
    Tool.STRIKEOUT: RED,
    Tool.PEN: BLUE,
    Tool.MARKER: YELLOW,
}
DEFAULT_WIDTHS: Dict[Tool, float] = {Tool.PEN: 2.0, Tool.MARKER: 14.0}

TOOLS: List[Tuple[Tool, str, str, str]] = [
    (Tool.PAN, "Mano", "V", "Mover la página y hacer scroll"),
    (Tool.HIGHLIGHT, "Resaltar", "H", "Resaltar texto: arrastrá sobre las palabras"),
    (Tool.UNDERLINE, "Subrayar", "U", "Subrayar texto: arrastrá sobre las palabras"),
    (Tool.STRIKEOUT, "Tachar", "T", "Tachar texto: arrastrá sobre las palabras"),
    (Tool.PEN, "Lápiz", "P", "Dibujar a mano alzada"),
    (Tool.MARKER, "Marcador", "M", "Resaltador libre, ideal para páginas escaneadas"),
    (Tool.ERASER, "Goma", "E", "Borrar marcas: hacé clic o arrastrá sobre ellas"),
]


def _swatch_icon(rgb: RGB, size: int = 20) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(QColor.fromRgbF(*rgb))
    p.setPen(QColor(0, 0, 0, 90))
    p.drawRoundedRect(1, 1, size - 2, size - 2, 4, 4)
    p.end()
    return QIcon(pm)


def _same_color(a: RGB, b: RGB) -> bool:
    return all(abs(x - y) < 0.02 for x, y in zip(a, b))


def _unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem} ({n}){ext}"):
        n += 1
    return f"{stem} ({n}){ext}"


class EditorWidget(QMainWindow):
    """Se embebe dentro de la ventana principal como una página del QStackedWidget."""

    backRequested = Signal()
    savedAs = Signal(str)
    titleChanged = Signal(str)

    def __init__(self, document: PdfDocument, start_page: int = 0, parent=None):
        super().__init__(parent)
        self.document = document
        self.view = PdfView(document, self)
        self.setCentralWidget(self.view)
        self._tool_colors: dict[Tool, RGB] = dict(DEFAULT_COLORS)
        self._tool_widths: dict[Tool, float] = dict(DEFAULT_WIDTHS)
        self._overwrite_ok = document.had_marks_on_open
        self._start_page = start_page

        self._build_toolbars()
        self.view.currentPageChanged.connect(self._on_page_changed)
        self.view.zoomChanged.connect(self._on_zoom_changed)
        self.view.statusMessage.connect(lambda m: self.statusBar().showMessage(m, 5000))
        self.view.undo_stack.cleanChanged.connect(lambda _clean: self._emit_title())
        self.statusBar().showMessage(
            f"{document.filename}: {document.page_count} página"
            f"{'s' if document.page_count != 1 else ''}",
            5000,
        )
        self._select_tool(Tool.PAN)
        self._emit_title()
        QTimer.singleShot(0, self._initial_layout)

    # ------------------------------------------------------------------ armado
    def _initial_layout(self) -> None:
        self.view.fit_width()
        if self._start_page:
            self.view.scroll_to_page(self._start_page)

    def _build_toolbars(self) -> None:
        style = self.style()
        top = QToolBar("Archivo", self)
        top.setMovable(False)
        top.setIconSize(QSize(18, 18))
        top.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(top)

        back = QAction(style.standardIcon(QStyle.SP_ArrowBack), "Biblioteca", self)
        back.setShortcut(QKeySequence("Ctrl+L"))
        back.setToolTip("Volver a la biblioteca (Ctrl+L)")
        back.triggered.connect(self.backRequested.emit)
        top.addAction(back)
        top.addSeparator()

        save = QAction(style.standardIcon(QStyle.SP_DialogSaveButton), "Guardar", self)
        save.setShortcut(QKeySequence(QKeySequence.Save))
        save.setToolTip("Guardar las marcas (Ctrl+S)")
        save.triggered.connect(self.save)
        top.addAction(save)
        save_as = QAction("Guardar como…", self)
        save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as.setToolTip("Crear un PDF nuevo con las marcas (Ctrl+Shift+S)")
        save_as.triggered.connect(self.save_as)
        top.addAction(save_as)
        top.addSeparator()

        undo = self.view.undo_stack.createUndoAction(self, "Deshacer")
        undo.setShortcut(QKeySequence(QKeySequence.Undo))
        redo = self.view.undo_stack.createRedoAction(self, "Rehacer")
        redo.setShortcuts([QKeySequence(QKeySequence.Redo), QKeySequence("Ctrl+Shift+Z")])
        top.addAction(undo)
        top.addAction(redo)
        top.addSeparator()

        zoom_out = QAction("Zoom −", self)
        zoom_out.setShortcut(QKeySequence(QKeySequence.ZoomOut))
        zoom_out.triggered.connect(self.view.zoom_out)
        zoom_in = QAction("Zoom +", self)
        zoom_in.setShortcut(QKeySequence(QKeySequence.ZoomIn))
        zoom_in.triggered.connect(self.view.zoom_in)
        fit = QAction("Ajustar ancho", self)
        fit.setShortcut(QKeySequence("Ctrl+0"))
        fit.triggered.connect(self.view.fit_width)
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setMinimumWidth(52)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        top.addAction(zoom_out)
        top.addWidget(self.zoom_label)
        top.addAction(zoom_in)
        top.addAction(fit)
        top.addSeparator()

        top.addWidget(QLabel(" Página "))
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, max(1, self.document.page_count))
        self.page_spin.setKeyboardTracking(False)
        self.page_spin.valueChanged.connect(lambda v: self.view.scroll_to_page(v - 1))
        top.addWidget(self.page_spin)
        top.addWidget(QLabel(f" de {self.document.page_count}  "))

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top.addWidget(spacer)
        self.file_label = QLabel(self.document.filename)
        self.file_label.setStyleSheet("color: #666; padding-right: 6px;")
        top.addWidget(self.file_label)

        self.addToolBarBreak()
        tools = QToolBar("Herramientas", self)
        tools.setMovable(False)
        tools.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tools)

        self._tool_group = QActionGroup(self)
        self._tool_group.setExclusive(True)
        self._tool_actions: dict[Tool, QAction] = {}
        self._tool_tips: dict[Tool, str] = {}
        for tool, label, key, tip in TOOLS:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setShortcut(QKeySequence(key))
            act.setToolTip(f"{tip} ({key})")
            act.setData(tool)
            self._tool_group.addAction(act)
            tools.addAction(act)
            self._tool_actions[tool] = act
            self._tool_tips[tool] = tip
        self._tool_group.triggered.connect(lambda a: self._select_tool(a.data()))
        tools.addSeparator()

        tools.addWidget(QLabel(" Color "))
        self._color_group = QButtonGroup(self)
        self._color_group.setExclusive(True)
        self._color_buttons: list[QToolButton] = []
        for i, (rgb, name) in enumerate(PALETTE):
            b = QToolButton()
            b.setCheckable(True)
            b.setAutoRaise(True)
            b.setIcon(_swatch_icon(rgb))
            b.setIconSize(QSize(20, 20))
            b.setToolTip(name)
            self._color_group.addButton(b, i)
            tools.addWidget(b)
            self._color_buttons.append(b)
        self._color_group.idClicked.connect(self._on_palette_clicked)
        self._other_color = QToolButton()
        self._other_color.setText("Otro…")
        self._other_color.setAutoRaise(True)
        self._other_color.setToolTip("Elegir cualquier color")
        self._other_color.clicked.connect(self._pick_color)
        tools.addWidget(self._other_color)
        tools.addSeparator()

        self.width_label = QLabel(" Grosor ")
        tools.addWidget(self.width_label)
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 30)
        self.width_slider.setFixedWidth(120)
        self.width_slider.valueChanged.connect(self._on_width_changed)
        tools.addWidget(self.width_slider)
        self.width_value = QLabel("2")
        self.width_value.setMinimumWidth(24)
        tools.addWidget(self.width_value)

    # ------------------------------------------------------------------ estado
    @property
    def modified(self) -> bool:
        return not self.view.undo_stack.isClean()

    def _emit_title(self) -> None:
        prefix = "• " if self.modified else ""
        self.titleChanged.emit(f"{prefix}{self.document.filename}")

    def _on_page_changed(self, pno: int) -> None:
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(pno + 1)
        self.page_spin.blockSignals(False)

    def _on_zoom_changed(self, zoom: float) -> None:
        self.zoom_label.setText(f"{round(zoom * 100)} %")

    # ------------------------------------------------------------------ herramientas
    def _select_tool(self, tool: Tool) -> None:
        self._tool_actions[tool].setChecked(True)
        self.view.set_tool(tool)
        has_color = tool not in (Tool.PAN, Tool.ERASER)
        has_width = tool in DEFAULT_WIDTHS
        for b in self._color_buttons:
            b.setEnabled(has_color)
        self._other_color.setEnabled(has_color)
        for w in (self.width_label, self.width_slider, self.width_value):
            w.setEnabled(has_width)
        if has_color:
            rgb = self._tool_colors[tool]
            self.view.set_color(rgb)
            self._sync_palette(rgb)
        if has_width:
            width = self._tool_widths[tool]
            self.view.set_width(width)
            self.width_slider.blockSignals(True)
            self.width_slider.setValue(round(width))
            self.width_slider.blockSignals(False)
            self.width_value.setText(str(round(width)))
        self.statusBar().showMessage(self._tool_tips[tool], 3000)

    def _sync_palette(self, rgb: RGB) -> None:
        match = next((i for i, (c, _n) in enumerate(PALETTE) if _same_color(c, rgb)), None)
        self._color_group.setExclusive(False)
        for i, b in enumerate(self._color_buttons):
            b.setChecked(i == match)
        self._color_group.setExclusive(True)

    def _apply_color(self, rgb: RGB) -> None:
        tool = self.view.tool
        if tool in self._tool_colors:
            self._tool_colors[tool] = rgb
        self.view.set_color(rgb)
        self._sync_palette(rgb)

    def _on_palette_clicked(self, index: int) -> None:
        self._apply_color(PALETTE[index][0])

    def _pick_color(self) -> None:
        current = QColor.fromRgbF(*self.view.color)
        chosen = QColorDialog.getColor(current, self, "Elegir color")
        if chosen.isValid():
            self._apply_color((chosen.redF(), chosen.greenF(), chosen.blueF()))

    def _on_width_changed(self, value: int) -> None:
        tool = self.view.tool
        if tool in self._tool_widths:
            self._tool_widths[tool] = float(value)
        self.view.set_width(float(value))
        self.width_value.setText(str(value))

    # ------------------------------------------------------------------ guardado
    def save(self) -> bool:
        if not self.modified:
            self.statusBar().showMessage("No hay cambios para guardar.", 3000)
            return True
        if not self._overwrite_ok:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Question)
            box.setWindowTitle("Guardar marcas")
            box.setText("Este PDF todavía no tiene marcas guardadas.")
            box.setInformativeText(
                "¿Querés crear una copia marcada (recomendado) o guardar sobre el original?"
            )
            copy_btn = box.addButton("Crear copia marcada", QMessageBox.AcceptRole)
            over_btn = box.addButton("Sobrescribir original", QMessageBox.DestructiveRole)
            box.addButton(QMessageBox.Cancel)
            box.setDefaultButton(copy_btn)
            exec_(box)
            clicked = box.clickedButton()
            if clicked is copy_btn:
                return self.save_as()
            if clicked is not over_btn:
                return False
            self._overwrite_ok = True
        return self._do_save(None)

    def save_as(self) -> bool:
        stem, _ext = os.path.splitext(self.document.path)
        suggested = _unique_path(f"{stem} - marcado.pdf")
        path, _filter = QFileDialog.getSaveFileName(
            self, "Guardar PDF marcado como", suggested, "PDF (*.pdf)"
        )
        if not path:
            return False
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        return self._do_save(path)

    def _do_save(self, target: str | None) -> bool:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            new_path = self.document.save(target)
        except Exception as exc:  # noqa: BLE001 - se informa al usuario
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "No se pudo guardar", str(exc))
            return False
        QApplication.restoreOverrideCursor()
        self.view.undo_stack.setClean()
        self.view.on_path_changed(new_path)
        self._overwrite_ok = True
        self.file_label.setText(self.document.filename)
        self._emit_title()
        self.statusBar().showMessage(f"Guardado en {new_path}", 6000)
        if target is not None:
            self.savedAs.emit(new_path)
        return True

    def confirm_close(self) -> bool:
        """True si se puede cerrar (guardó o descartó)."""
        if not self.modified:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Cambios sin guardar")
        box.setText(f"Hay marcas sin guardar en {self.document.filename}.")
        box.setInformativeText("Si las descartás, se pierden.")
        save_btn = box.addButton("Guardar", QMessageBox.AcceptRole)
        discard_btn = box.addButton("Descartar", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(save_btn)
        exec_(box)
        clicked = box.clickedButton()
        if clicked is save_btn:
            return self.save()
        return clicked is discard_btn

    def shutdown(self) -> None:
        self.view.shutdown()
        self.document.close()
