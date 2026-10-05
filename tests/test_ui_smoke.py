"""Prueba de humo de la UI en modo offscreen: herramientas, deshacer, borrar, guardar."""
import importlib
import os

from fluo.qt import QT_PACKAGE, QApplication, QEvent, QMouseEvent, QPoint, QPointF, Qt

QTest = importlib.import_module(f"{QT_PACKAGE}.QtTest").QTest

from fluo.editor.document import PdfDocument
from fluo.editor.editor import EditorWidget
from fluo.editor.model import InkStroke, TextMark
from fluo.editor.view import Tool
from tests.conftest import wait_ms


def _vp_point(view, pno: int, x: float, y: float) -> QPoint:
    """Coordenadas de página sin rotar -> punto del viewport."""
    page = view._pages[pno]
    return view.mapFromScene(page.layer.mapToScene(QPointF(x, y)))


def _mouse(view, kind, pos: QPoint, buttons=Qt.LeftButton):
    vp = view.viewport()
    ev = QMouseEvent(
        kind,
        QPointF(pos),
        QPointF(vp.mapToGlobal(pos)),
        Qt.LeftButton,
        buttons,
        Qt.NoModifier,
    )
    QApplication.sendEvent(vp, ev)


def _drag(view, a: QPoint, b: QPoint, steps: int = 8):
    _mouse(view, QEvent.MouseButtonPress, a)
    for i in range(1, steps + 1):
        p = QPoint(
            round(a.x() + (b.x() - a.x()) * i / steps),
            round(a.y() + (b.y() - a.y()) * i / steps),
        )
        _mouse(view, QEvent.MouseMove, p)
    _mouse(view, QEvent.MouseButtonRelease, b, Qt.NoButton)


def _click(view, p: QPoint):
    _mouse(view, QEvent.MouseButtonPress, p)
    _mouse(view, QEvent.MouseButtonRelease, p, Qt.NoButton)


def test_editor_smoke(qapp, sample_pdf, tmp_path):
    doc = PdfDocument(sample_pdf)
    editor = EditorWidget(doc)
    editor.resize(1100, 720)
    editor.show()
    QTest.qWaitForWindowExposed(editor)
    wait_ms(150)  # fit_width y primer render
    view = editor.view
    assert view.zoom > 1.0  # ajustó al ancho (la página mide 400 pt)

    # --- resaltar texto arrastrando desde la primera palabra hasta una de la segunda línea
    editor._select_tool(Tool.HIGHLIGHT)
    words = doc.words(0)
    first = words[0]
    second_line = next(w for w in words if w[6] != first[6] or w[5] != first[5])
    a = _vp_point(view, 0, (first[0] + first[2]) / 2, (first[1] + first[3]) / 2)
    b = _vp_point(view, 0, (second_line[0] + second_line[2]) / 2, (second_line[1] + second_line[3]) / 2)
    _drag(view, a, b)
    marks = doc.annotations.get(0, [])
    assert len(marks) == 1 and isinstance(marks[0], TextMark)
    assert len(marks[0].quads) == 2  # dos líneas -> dos rectángulos
    assert editor.modified

    # --- herramienta de texto sobre una página sin texto: avisa y no crea nada
    view.scroll_to_page(2)
    wait_ms(80)
    messages = []
    view.statusMessage.connect(messages.append)
    _click(view, _vp_point(view, 2, 100, 100))
    assert messages and "texto" in messages[0]
    assert 2 not in doc.annotations

    # --- lápiz sobre la página rotada: los puntos quedan en coordenadas sin rotar
    view.scroll_to_page(1)
    wait_ms(80)
    editor._select_tool(Tool.PEN)
    _drag(view, _vp_point(view, 1, 50, 50), _vp_point(view, 1, 150, 120))
    strokes = doc.annotations.get(1, [])
    assert len(strokes) == 1 and isinstance(strokes[0], InkStroke)
    stroke = strokes[0]
    assert len(stroke.points) >= 3
    assert abs(stroke.points[0][0] - 50) < 1.5 and abs(stroke.points[0][1] - 50) < 1.5
    assert abs(stroke.points[-1][0] - 150) < 1.5 and abs(stroke.points[-1][1] - 120) < 1.5
    assert not stroke.marker and stroke.width == 2.0

    # --- marcador: opacidad y mezcla
    editor._select_tool(Tool.MARKER)
    _drag(view, _vp_point(view, 1, 40, 200), _vp_point(view, 1, 200, 205))
    marker = doc.annotations[1][-1]
    assert marker.marker and marker.opacity < 1 and marker.width == 14.0
    assert len(doc.annotations[1]) == 2

    # --- deshacer / rehacer
    view.undo_stack.undo()
    assert len(doc.annotations[1]) == 1
    view.undo_stack.redo()
    assert len(doc.annotations[1]) == 2

    # --- goma: clic sobre el trazo del lápiz lo borra; deshacer lo trae de vuelta
    editor._select_tool(Tool.ERASER)
    mid = stroke.points[len(stroke.points) // 2]
    _click(view, _vp_point(view, 1, mid[0], mid[1]))
    assert all(a.id != stroke.id for a in doc.annotations[1])
    assert len(doc.annotations[1]) == 1
    view.undo_stack.undo()
    assert len(doc.annotations[1]) == 2

    # --- guardar como: crea el PDF nuevo y el editor pasa a trabajar sobre él
    out = str(tmp_path / "muestra - marcado.pdf")
    saved = []
    editor.savedAs.connect(saved.append)
    assert editor._do_save(out)
    assert saved == [out]
    assert doc.path == out and not editor.modified

    shot = os.environ.get("FLUO_SHOT")
    if shot:
        view.scroll_to_page(0)
        wait_ms(400)
        editor.grab().save(shot)

    editor.shutdown()

    reopened = PdfDocument(out)
    assert reopened.count() == 3  # 1 resaltado + lápiz + marcador
    assert isinstance(reopened.annotations[0][0], TextMark)
    assert len(reopened.annotations[0][0].quads) == 2
    reopened.close()
    assert PdfDocument(sample_pdf).count() == 0
