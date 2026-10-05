"""Vista del PDF: páginas en scroll continuo, zoom, herramientas y deshacer."""
from __future__ import annotations

import math
from enum import Enum

from ..qt import (
    QColor,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QPainter,
    QPixmap,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QTransform,
    QUndoCommand,
    QUndoStack,
    Signal,
    event_pos,
)

from .document import PdfDocument
from .items import AnnotItem, InkItem, PageItem, SelectionItem, make_item
from .model import Annotation, InkStroke, TextMark, TextMarkKind, union_rect
from .render import RenderWorker


class Tool(str, Enum):
    PAN = "pan"
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKEOUT = "strikeout"
    PEN = "pen"
    MARKER = "marker"
    ERASER = "eraser"


TEXT_TOOLS = {
    Tool.HIGHLIGHT: TextMarkKind.HIGHLIGHT,
    Tool.UNDERLINE: TextMarkKind.UNDERLINE,
    Tool.STRIKEOUT: TextMarkKind.STRIKEOUT,
}
INK_TOOLS = {Tool.PEN, Tool.MARKER}

PAGE_GAP = 14.0
MARGIN = 10.0
MIN_ZOOM, MAX_ZOOM = 0.2, 5.0
MAX_RENDER_SCALE = 4.0
WORD_SNAP_DISTANCE = 24.0
MARKER_OPACITY = 0.5
NO_TEXT_MESSAGE = "Esta página no tiene texto seleccionable: usá el marcador o el lápiz."


def _to_qtransform(m) -> QTransform:
    """pymupdf.Matrix(a, b, c, d, e, f) -> QTransform con la misma convención."""
    return QTransform(m.a, m.b, m.c, m.d, m.e, m.f)


class _AddCommand(QUndoCommand):
    def __init__(self, view: "PdfView", pno: int, annot: Annotation, item: AnnotItem | None = None):
        super().__init__("Agregar marca")
        self.view, self.pno, self.annot, self.item = view, pno, annot, item

    def redo(self) -> None:
        self.view._add_annot(self.pno, self.annot, self.item)
        self.item = None

    def undo(self) -> None:
        self.view._remove_annot(self.pno, self.annot)


class _RemoveCommand(QUndoCommand):
    def __init__(self, view: "PdfView", pno: int, annot: Annotation):
        super().__init__("Borrar marca")
        self.view, self.pno, self.annot = view, pno, annot

    def redo(self) -> None:
        self.view._remove_annot(self.pno, self.annot)

    def undo(self) -> None:
        self.view._add_annot(self.pno, self.annot)


class PdfView(QGraphicsView):
    currentPageChanged = Signal(int)
    zoomChanged = Signal(float)
    statusMessage = Signal(str)

    def __init__(self, document: PdfDocument, parent=None):
        super().__init__(parent)
        self.document = document
        self.undo_stack = QUndoStack(self)
        self.tool = Tool.PAN
        self.color: tuple[float, float, float] = (1.0, 0.92, 0.23)
        self.width = 2.0
        self.zoom = 1.0

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing
        )
        self.setBackgroundBrush(QColor(84, 87, 92))
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.NoFrame)
        self.setMouseTracking(True)

        self._pages: list[PageItem] = []
        self._items: dict[tuple[int, str], AnnotItem] = {}
        self._max_width = 1.0
        self._current_page = 0
        self._build_pages()

        self._worker = RenderWorker(document.path, self)
        self._worker.rendered.connect(self._on_rendered)
        self._worker.start()

        self._visible_timer = QTimer(self)
        self._visible_timer.setSingleShot(True)
        self._visible_timer.setInterval(50)
        self._visible_timer.timeout.connect(self._update_visible)
        self.verticalScrollBar().valueChanged.connect(self._schedule_update)
        self.horizontalScrollBar().valueChanged.connect(self._schedule_update)

        # estado de interacción
        self._ink: tuple[PageItem, InkItem] | None = None
        self._anchor: tuple[PageItem, QPointF] | None = None
        self._selection: SelectionItem | None = None
        self._erasing = False
        self._erased: list[tuple[int, AnnotItem]] = []
        self.set_tool(Tool.PAN)

    # ------------------------------------------------------------------ páginas
    def _build_pages(self) -> None:
        doc = self.document
        rects = [doc.page_rect(i) for i in range(doc.page_count)]
        self._max_width = max((r.width for r in rects), default=1.0)
        y = MARGIN
        for i, r in enumerate(rects):
            unrot = doc.unrotated_rect(i)
            item = PageItem(
                i,
                r.width,
                r.height,
                QRectF(unrot.x0, unrot.y0, unrot.width, unrot.height),
                _to_qtransform(doc.rotation_matrix(i)),
            )
            item.setPos(MARGIN + (self._max_width - r.width) / 2, y)
            self._scene.addItem(item)
            self._pages.append(item)
            y += r.height + PAGE_GAP
        self._scene.setSceneRect(0, 0, self._max_width + 2 * MARGIN, y - PAGE_GAP + MARGIN)
        for pno, annots in doc.annotations.items():
            if pno < len(self._pages):
                for a in annots:
                    self._items[(pno, a.id)] = make_item(a, self._pages[pno].layer)

    @property
    def page_count(self) -> int:
        return len(self._pages)

    @property
    def current_page(self) -> int:
        return self._current_page

    def scroll_to_page(self, pno: int) -> None:
        if not self._pages:
            return
        pno = max(0, min(len(self._pages) - 1, pno))
        page = self._pages[pno]
        top = self.mapFromScene(QPointF(0, page.pos().y() - MARGIN / 2)).y()
        bar = self.verticalScrollBar()
        bar.setValue(bar.value() + top)
        if self._current_page != pno:
            self._current_page = pno
            self.currentPageChanged.emit(pno)

    # ------------------------------------------------------------------ render
    def _schedule_update(self, *_args) -> None:
        self._visible_timer.start()

    def _render_scale(self) -> float:
        return min(self.zoom * self.devicePixelRatioF(), MAX_RENDER_SCALE)

    def _update_visible(self) -> None:
        if not self._pages:
            return
        vis = self.mapToScene(self.viewport().rect()).boundingRect()
        visible = [p for p in self._pages if p.sceneBoundingRect().intersects(vis)]
        if not visible:
            return
        first, last = visible[0].index, visible[-1].index

        best, best_h = first, -1.0
        for p in visible:
            h = p.sceneBoundingRect().intersected(vis).height()
            if h > best_h + 0.5:
                best, best_h = p.index, h
        if best != self._current_page:
            self._current_page = best
            self.currentPageChanged.emit(best)

        scale = self._render_scale()
        order = [p.index for p in visible]
        if first > 0:
            order.append(first - 1)
        if last + 1 < len(self._pages):
            order.append(last + 1)
        jobs = [
            (i, scale)
            for i in order
            if not self._pages[i].has_pixmap or abs(self._pages[i].pixmap_scale - scale) > 1e-3
        ]
        for p in self._pages:
            if (p.index < first - 2 or p.index > last + 2) and p.has_pixmap:
                p.clear_pixmap()
        if jobs:
            self._worker.request(jobs)

    def _on_rendered(self, pno: int, scale: float, img) -> None:
        if pno >= len(self._pages):
            return
        page = self._pages[pno]
        wanted = self._render_scale()
        stale = abs(scale - wanted) > 1e-3
        if stale and page.has_pixmap and abs(page.pixmap_scale - wanted) < 1e-3:
            return
        page.set_pixmap(QPixmap.fromImage(img), scale)
        if stale:
            self._schedule_update()

    # ------------------------------------------------------------------ zoom
    def set_zoom(self, zoom: float, anchor=QGraphicsView.AnchorViewCenter) -> None:
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        if abs(zoom - self.zoom) < 1e-6:
            return
        factor = zoom / self.zoom
        self.setTransformationAnchor(anchor)
        self.scale(factor, factor)
        self.zoom = zoom
        self.zoomChanged.emit(zoom)
        self._schedule_update()

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom * 1.25)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom / 1.25)

    def fit_width(self) -> None:
        avail = self.viewport().width() - 4
        scene_w = self._scene.sceneRect().width()
        if avail > 0 and scene_w > 0:
            self.set_zoom(avail / scene_w)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.set_zoom(self.zoom * (1.15 ** (delta / 120)), QGraphicsView.AnchorUnderMouse)
            event.accept()
            return
        super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._schedule_update()

    # ------------------------------------------------------------------ herramientas
    def set_tool(self, tool: Tool) -> None:
        self.tool = tool
        self._cancel_interaction()
        if tool == Tool.PAN:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)

    def set_color(self, rgb) -> None:
        self.color = (float(rgb[0]), float(rgb[1]), float(rgb[2]))

    def set_width(self, width: float) -> None:
        self.width = float(width)

    def on_path_changed(self, path: str) -> None:
        self._worker.set_path(path)

    def shutdown(self) -> None:
        self._worker.stop()

    # ------------------------------------------------------------------ geometría
    def _page_at(self, scene_pos: QPointF) -> PageItem | None:
        for it in self._scene.items(scene_pos):
            if isinstance(it, PageItem):
                return it
        return None

    @staticmethod
    def _to_page(page: PageItem, scene_pos: QPointF) -> QPointF:
        """Coordenadas de escena -> coordenadas de página sin rotar."""
        return page.layer.mapFromScene(scene_pos)

    @staticmethod
    def _clamp(page: PageItem, pt: QPointF) -> QPointF:
        r = page.layer.boundingRect()
        return QPointF(
            min(max(pt.x(), r.left()), r.right()), min(max(pt.y(), r.top()), r.bottom())
        )

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or self.tool == Tool.PAN:
            super().mousePressEvent(event)
            return
        vp = event_pos(event)
        sp = self.mapToScene(vp)
        page = self._page_at(sp)
        if page is None:
            event.accept()
            return
        pt = self._to_page(page, sp)

        if self.tool in INK_TOOLS:
            marker = self.tool == Tool.MARKER
            stroke = InkStroke(
                [(pt.x(), pt.y())],
                self.color,
                self.width,
                MARKER_OPACITY if marker else 1.0,
                marker,
            )
            self._ink = (page, InkItem(stroke, page.layer))
        elif self.tool in TEXT_TOOLS:
            if not self.document.has_text(page.index):
                self.statusMessage.emit(NO_TEXT_MESSAGE)
                event.accept()
                return
            self._anchor = (page, pt)
            self._selection = SelectionItem(page.layer)
            self._selection.set_rects(self._selection_quads(page.index, pt, pt))
        elif self.tool == Tool.ERASER:
            self._erasing = True
            self._erased = []
            self._erase_at(vp)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._ink is not None:
            page, item = self._ink
            pt = self._clamp(page, self._to_page(page, self.mapToScene(event_pos(event))))
            last = item.annot.points[-1]
            if math.hypot(pt.x() - last[0], pt.y() - last[1]) >= 0.5 / max(self.zoom, 0.01):
                item.append_point(pt.x(), pt.y())
            event.accept()
            return
        if self._anchor is not None and self._selection is not None:
            page, anchor = self._anchor
            pt = self._to_page(page, self.mapToScene(event_pos(event)))
            self._selection.set_rects(self._selection_quads(page.index, anchor, pt))
            event.accept()
            return
        if self._erasing:
            self._erase_at(event_pos(event))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return
        if self._ink is not None:
            page, item = self._ink
            self._ink = None
            self.undo_stack.push(_AddCommand(self, page.index, item.annot, item))
            event.accept()
            return
        if self._anchor is not None:
            page, anchor = self._anchor
            pt = self._to_page(page, self.mapToScene(event_pos(event)))
            quads = self._selection_quads(page.index, anchor, pt)
            self._clear_selection()
            self._anchor = None
            if quads:
                mark = TextMark(TEXT_TOOLS[self.tool], quads, self.color, 1.0)
                self.undo_stack.push(_AddCommand(self, page.index, mark))
            event.accept()
            return
        if self._erasing:
            self._erasing = False
            hits, self._erased = self._erased, []
            if hits:
                self.undo_stack.beginMacro("Borrar marcas" if len(hits) > 1 else "Borrar marca")
                for pno, item in hits:
                    self.undo_stack.push(_RemoveCommand(self, pno, item.annot))
                self.undo_stack.endMacro()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._cancel_interaction()
            event.accept()
            return
        super().keyPressEvent(event)

    def _erase_at(self, vp: QPoint) -> None:
        rect = QRect(vp - QPoint(5, 5), QSize(11, 11))
        for it in self.items(rect):
            if isinstance(it, AnnotItem) and it.isVisible():
                it.setVisible(False)
                self._erased.append((it.page_index, it))

    def _cancel_interaction(self) -> None:
        if self._ink is not None:
            _page, item = self._ink
            self._ink = None
            self._scene.removeItem(item)
        self._clear_selection()
        self._anchor = None
        if self._erasing or self._erased:
            for _pno, it in self._erased:
                it.setVisible(True)
            self._erased = []
            self._erasing = False

    def _clear_selection(self) -> None:
        if self._selection is not None:
            self._scene.removeItem(self._selection)
            self._selection = None

    # ------------------------------------------------------------------ selección de texto
    def _selection_quads(self, pno: int, a: QPointF, b: QPointF) -> list[tuple]:
        words = self.document.words(pno)
        if not words:
            return []
        ia = self._word_index(words, a, loose=False)
        ib = self._word_index(words, b, loose=True)
        if ia is None or ib is None:
            return []
        lo, hi = min(ia, ib), max(ia, ib)
        groups: dict[tuple, tuple] = {}
        order: list[tuple] = []
        for w in words[lo : hi + 1]:
            key = (w[5], w[6])
            r = (w[0], w[1], w[2], w[3])
            if key in groups:
                groups[key] = union_rect(groups[key], r)
            else:
                groups[key] = r
                order.append(key)
        return [groups[k] for k in order]

    @staticmethod
    def _word_index(words: list[tuple], p: QPointF, loose: bool) -> int | None:
        x, y = p.x(), p.y()
        best, best_d = None, WORD_SNAP_DISTANCE
        for i, w in enumerate(words):
            x0, y0, x1, y1 = w[0], w[1], w[2], w[3]
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
            dx = max(x0 - x, 0.0, x - x1)
            dy = max(y0 - y, 0.0, y - y1)
            d = math.hypot(dx, dy * 3)  # prioriza la misma línea
            if d < best_d:
                best, best_d = i, d
        if best is not None or not loose:
            return best
        # Punto lejos de todo: última palabra que queda "antes" en orden de lectura.
        for i, w in enumerate(words):
            if w[1] <= y and (w[3] <= y or w[0] <= x):
                best = i
        return best

    # ------------------------------------------------------------------ modelo <-> escena
    def _add_annot(self, pno: int, annot: Annotation, item: AnnotItem | None = None) -> None:
        self.document.add(pno, annot)
        layer = self._pages[pno].layer
        if item is None:
            item = make_item(annot, layer)
        else:
            item.setParentItem(layer)
            item.setVisible(True)
        self._items[(pno, annot.id)] = item

    def _remove_annot(self, pno: int, annot: Annotation) -> None:
        self.document.remove(pno, annot)
        item = self._items.pop((pno, annot.id), None)
        if item is not None:
            self._scene.removeItem(item)
