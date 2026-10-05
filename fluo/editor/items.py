"""Items de QGraphicsScene: página, capa de anotaciones y marcas dibujables."""
from __future__ import annotations

from ..qt import (
    QBrush,
    QColor,
    QGraphicsItem,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QPointF,
    QRectF,
    Qt,
    QTransform,
)

from .model import Annotation, InkStroke, TextMark, TextMarkKind


def qcolor(rgb, alpha: float = 1.0) -> QColor:
    c = QColor.fromRgbF(*rgb)
    c.setAlphaF(alpha)
    return c


class AnnotLayer(QGraphicsItem):
    """Capa hija de la página en coordenadas sin rotar; su transform aplica la rotación."""

    def __init__(self, rect: QRectF, parent: QGraphicsItem):
        super().__init__(parent)
        self._rect = rect
        self.setFlag(QGraphicsItem.ItemHasNoContents, True)

    def boundingRect(self) -> QRectF:
        return self._rect

    def paint(self, painter, option, widget=None) -> None:  # pragma: no cover
        pass


class PageItem(QGraphicsItem):
    """Una página: fondo blanco, pixmap renderizado (si hay) y su capa de marcas."""

    def __init__(
        self,
        index: int,
        width: float,
        height: float,
        unrotated_rect: QRectF,
        rotation: QTransform,
    ):
        super().__init__()
        self.index = index
        self._rect = QRectF(0, 0, width, height)
        self._pixmap: QPixmap | None = None
        self.pixmap_scale = 0.0
        self.layer = AnnotLayer(unrotated_rect, self)
        self.layer.setTransform(rotation)
        self.setZValue(0)

    def boundingRect(self) -> QRectF:
        return self._rect

    @property
    def has_pixmap(self) -> bool:
        return self._pixmap is not None

    def set_pixmap(self, pixmap: QPixmap, scale: float) -> None:
        self._pixmap = pixmap
        self.pixmap_scale = scale
        self.update()

    def clear_pixmap(self) -> None:
        if self._pixmap is not None:
            self._pixmap = None
            self.pixmap_scale = 0.0
            self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.fillRect(self._rect, Qt.white)
        if self._pixmap is not None:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(self._rect, self._pixmap, QRectF(self._pixmap.rect()))
        painter.setPen(QPen(QColor(0, 0, 0, 60), 0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self._rect)


class AnnotItem(QGraphicsItem):
    """Base de las marcas. Vive dentro de la AnnotLayer de su página."""

    def __init__(self, annot: Annotation, parent: QGraphicsItem | None):
        super().__init__(parent)
        self.annot = annot
        self.setZValue(1)

    @property
    def page_index(self) -> int:
        layer = self.parentItem()
        page = layer.parentItem() if layer is not None else None
        return page.index if isinstance(page, PageItem) else -1


class TextMarkItem(AnnotItem):
    annot: TextMark

    def __init__(self, annot: TextMark, parent: QGraphicsItem | None):
        super().__init__(annot, parent)
        self._bounds = QRectF()
        self._shape = QPainterPath()
        self._rebuild()

    def _rebuild(self) -> None:
        path = QPainterPath()
        bounds = QRectF()
        for x0, y0, x1, y1 in self.annot.quads:
            r = QRectF(x0, y0, x1 - x0, y1 - y0)
            path.addRect(r)
            bounds = bounds.united(r)
        self._shape = path
        self._bounds = bounds.adjusted(-2, -2, 2, 2)

    def boundingRect(self) -> QRectF:
        return self._bounds

    def shape(self) -> QPainterPath:
        return self._shape

    def paint(self, painter: QPainter, option, widget=None) -> None:
        a = self.annot
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setOpacity(a.opacity)
        color = qcolor(a.color)
        if a.kind == TextMarkKind.HIGHLIGHT:
            painter.setCompositionMode(QPainter.CompositionMode_Multiply)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            for x0, y0, x1, y1 in a.quads:
                painter.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))
            return
        for x0, y0, x1, y1 in a.quads:
            h = y1 - y0
            w = max(0.8, min(3.0, h * 0.07))
            painter.setPen(QPen(color, w, Qt.SolidLine, Qt.FlatCap))
            if a.kind == TextMarkKind.UNDERLINE:
                y = y1 - w * 1.2
            else:
                y = (y0 + y1) / 2
            painter.drawLine(QPointF(x0, y), QPointF(x1, y))


class InkItem(AnnotItem):
    annot: InkStroke

    def __init__(self, annot: InkStroke, parent: QGraphicsItem | None):
        super().__init__(annot, parent)
        self._path = QPainterPath()
        self._bounds = QRectF()
        self._rebuild()

    def _rebuild(self) -> None:
        pts = self.annot.points
        path = QPainterPath()
        if len(pts) == 1:
            x, y = pts[0]
            path.moveTo(x, y)
            path.lineTo(x + 0.01, y)
        elif len(pts) == 2:
            path.moveTo(*pts[0])
            path.lineTo(*pts[1])
        elif pts:
            path.moveTo(*pts[0])
            for i in range(1, len(pts) - 1):
                mx = (pts[i][0] + pts[i + 1][0]) / 2
                my = (pts[i][1] + pts[i + 1][1]) / 2
                path.quadTo(QPointF(*pts[i]), QPointF(mx, my))
            path.lineTo(*pts[-1])
        self._path = path
        w = self.annot.width
        self._bounds = path.boundingRect().adjusted(-w, -w, w, w)

    def append_point(self, x: float, y: float) -> None:
        self.prepareGeometryChange()
        self.annot.points.append((x, y))
        self._rebuild()
        self.update()

    def boundingRect(self) -> QRectF:
        return self._bounds

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.annot.width, 8.0))
        stroker.setCapStyle(Qt.RoundCap)
        stroker.setJoinStyle(Qt.RoundJoin)
        return stroker.createStroke(self._path)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        a = self.annot
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setOpacity(a.opacity)
        if a.marker:
            painter.setCompositionMode(QPainter.CompositionMode_Multiply)
        painter.setPen(QPen(qcolor(a.color), a.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self._path)


class SelectionItem(QGraphicsItem):
    """Resalte azul temporal mientras se arrastra sobre texto."""

    def __init__(self, parent: QGraphicsItem | None):
        super().__init__(parent)
        self._rects: list[QRectF] = []
        self._bounds = QRectF()
        self.setZValue(5)

    def set_rects(self, rects) -> None:
        self.prepareGeometryChange()
        self._rects = [QRectF(x0, y0, x1 - x0, y1 - y0) for x0, y0, x1, y1 in rects]
        bounds = QRectF()
        for r in self._rects:
            bounds = bounds.united(r)
        self._bounds = bounds.adjusted(-1, -1, 1, 1)
        self.update()

    def boundingRect(self) -> QRectF:
        return self._bounds

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(40, 120, 255, 70))
        for r in self._rects:
            painter.drawRect(r)


def make_item(annot: Annotation, parent: QGraphicsItem | None) -> AnnotItem:
    if isinstance(annot, TextMark):
        return TextMarkItem(annot, parent)
    return InkItem(annot, parent)
