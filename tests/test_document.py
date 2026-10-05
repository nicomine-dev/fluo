import pytest

from fluo.editor.document import PdfDocument
from fluo.editor.model import InkStroke, TextMark, TextMarkKind


def _close(a, b, tol=0.6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_sample_has_text_where_expected(sample_pdf):
    doc = PdfDocument(sample_pdf)
    assert doc.page_count == 3
    assert doc.has_text(0)
    assert doc.has_text(1)
    assert not doc.has_text(2)
    assert not doc.had_marks_on_open
    doc.close()


def test_rotated_page_geometry(sample_pdf):
    doc = PdfDocument(sample_pdf)
    shown = doc.page_rect(1)
    unrot = doc.unrotated_rect(1)
    assert (round(shown.width), round(shown.height)) == (600, 400)
    assert (round(unrot.width), round(unrot.height)) == (400, 600)
    # una palabra en coordenadas sin rotar cae dentro del rect sin rotar
    w = doc.words(1)[0]
    assert unrot.x0 <= w[0] <= w[2] <= unrot.x1
    assert unrot.y0 <= w[1] <= w[3] <= unrot.y1
    doc.close()


def test_roundtrip_save_as_then_save_in_place(sample_pdf, tmp_path):
    doc = PdfDocument(sample_pdf)
    words = doc.words(0)
    quads = [(words[0][0], words[0][1], words[2][2], words[2][3])]
    doc.add(0, TextMark(TextMarkKind.HIGHLIGHT, quads, (1.0, 0.9, 0.2)))
    doc.add(0, TextMark(TextMarkKind.UNDERLINE, quads, (0.9, 0.2, 0.2)))
    doc.add(0, TextMark(TextMarkKind.STRIKEOUT, quads, (0.1, 0.1, 0.1)))
    doc.add(1, InkStroke([(10.0, 10.0), (50.0, 60.0), (90.0, 20.0)], (0.2, 0.3, 0.9), 3.0))
    doc.add(1, InkStroke([(20.0, 100.0), (120.0, 110.0)], (1.0, 0.9, 0.2), 14.0, 0.5, True))
    assert doc.count() == 5

    out = str(tmp_path / "copia.pdf")
    assert doc.save(out) == out
    assert doc.path == out
    doc.close()

    # el original queda intacto
    original = PdfDocument(sample_pdf)
    assert original.count() == 0
    original.close()

    d2 = PdfDocument(out)
    assert d2.had_marks_on_open
    p0 = d2.annotations[0]
    kinds = sorted(a.kind.value for a in p0 if isinstance(a, TextMark))
    assert kinds == ["highlight", "strikeout", "underline"]
    hl = next(a for a in p0 if a.kind == TextMarkKind.HIGHLIGHT)
    assert len(hl.quads) == 1 and _close(hl.quads[0], quads[0])
    assert _close(hl.color, (1.0, 0.9, 0.2), 0.02)

    inks = [a for a in d2.annotations[1] if isinstance(a, InkStroke)]
    assert len(inks) == 2
    marker = next(a for a in inks if a.marker)
    pen = next(a for a in inks if not a.marker)
    assert marker.width == pytest.approx(14.0) and marker.opacity == pytest.approx(0.5, abs=0.01)
    assert _close(marker.points[0], (20.0, 100.0)) and _close(marker.points[1], (120.0, 110.0))
    assert pen.width == pytest.approx(3.0) and pen.opacity == pytest.approx(1.0)
    assert len(pen.points) == 3 and _close(pen.points[1], (50.0, 60.0))

    # borrar una y guardar en el mismo archivo (incremental)
    underline = next(a for a in p0 if a.kind == TextMarkKind.UNDERLINE)
    d2.remove(0, underline)
    assert d2.save() == out
    d2.close()

    d3 = PdfDocument(out)
    assert len(d3.annotations[0]) == 2
    assert len(d3.annotations[1]) == 2
    d3.close()
