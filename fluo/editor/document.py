"""Envoltorio sobre PyMuPDF: lectura de páginas/texto y sincronización de anotaciones."""
from __future__ import annotations

import getpass
import logging
import os
import tempfile

import pymupdf

from .model import Annotation, InkStroke, TextMark, TextMarkKind

log = logging.getLogger(__name__)

SUPPORTED_TYPES = [
    pymupdf.PDF_ANNOT_HIGHLIGHT,
    pymupdf.PDF_ANNOT_UNDERLINE,
    pymupdf.PDF_ANNOT_STRIKE_OUT,
    pymupdf.PDF_ANNOT_INK,
]
KIND_BY_TYPE = {
    pymupdf.PDF_ANNOT_HIGHLIGHT: TextMarkKind.HIGHLIGHT,
    pymupdf.PDF_ANNOT_UNDERLINE: TextMarkKind.UNDERLINE,
    pymupdf.PDF_ANNOT_STRIKE_OUT: TextMarkKind.STRIKEOUT,
}
DEFAULT_COLOR = (1.0, 0.92, 0.23)


def _rgb(colors) -> tuple[float, float, float]:
    c = [float(x) for x in (colors or [])]
    if len(c) == 3:
        return (c[0], c[1], c[2])
    if len(c) == 1:
        return (c[0], c[0], c[0])
    if len(c) == 4:
        cy, m, y, k = c
        return ((1 - cy) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    return DEFAULT_COLOR


def _quads_to_rects(vertices) -> list[tuple[float, float, float, float]]:
    rects = []
    for i in range(0, len(vertices) - 3, 4):
        pts = vertices[i : i + 4]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        rects.append((min(xs), min(ys), max(xs), max(ys)))
    return rects


class PdfDocument:
    """Un PDF abierto con su modelo de anotaciones editable.

    El modelo (``annotations``) es la fuente de verdad. Las anotaciones que ya
    venían en el archivo se cargan al abrir; al guardar, las páginas tocadas se
    reescriben completas a partir del modelo.
    """

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.doc = pymupdf.open(self.path)
        if self.doc.needs_pass:
            raise ValueError("El PDF está protegido con contraseña.")
        if not self.doc.is_pdf:
            raise ValueError("Solo se pueden marcar archivos PDF.")
        self.annotations: dict[int, list[Annotation]] = {}
        self._words_cache: dict[int, list[tuple]] = {}
        self._touched: set[int] = set()
        self.had_marks_on_open = False
        self._load_annotations()

    # ----- lectura -----
    @property
    def page_count(self) -> int:
        return len(self.doc)

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    def page_rect(self, pno: int) -> pymupdf.Rect:
        """Rectángulo de la página tal como se muestra (con rotación aplicada)."""
        return self.doc[pno].rect

    def unrotated_rect(self, pno: int) -> pymupdf.Rect:
        """Rectángulo de la página en el sistema sin rotar (el de las anotaciones)."""
        page = self.doc[pno]
        return page.rect * page.derotation_matrix

    def rotation_matrix(self, pno: int) -> pymupdf.Matrix:
        """Matriz que lleva coordenadas sin rotar a coordenadas mostradas."""
        return self.doc[pno].rotation_matrix

    def words(self, pno: int) -> list[tuple]:
        """Palabras (x0, y0, x1, y1, texto, bloque, línea, nro) en orden de lectura."""
        if pno not in self._words_cache:
            try:
                words = self.doc[pno].get_text("words")
            except Exception:  # pragma: no cover - PDFs rotos
                log.exception("No pude extraer texto de la página %s", pno)
                words = []
            words.sort(key=lambda w: (w[5], w[6], w[7]))
            self._words_cache[pno] = words
        return self._words_cache[pno]

    def has_text(self, pno: int) -> bool:
        return bool(self.words(pno))

    # ----- modelo -----
    def _load_annotations(self) -> None:
        for pno in range(self.page_count):
            page = self.doc[pno]
            loaded: list[Annotation] = []
            for annot in page.annots(types=SUPPORTED_TYPES):
                try:
                    loaded.extend(self._convert(annot))
                except Exception:  # pragma: no cover
                    log.exception("Anotación ilegible en página %s", pno)
            if loaded:
                self.annotations[pno] = loaded
                self.had_marks_on_open = True

    @staticmethod
    def _convert(annot: pymupdf.Annot) -> list[Annotation]:
        atype = annot.type[0]
        color = _rgb((annot.colors or {}).get("stroke"))
        opacity = annot.opacity
        if opacity is None or opacity < 0 or opacity > 1:
            opacity = 1.0
        if atype in KIND_BY_TYPE:
            rects = _quads_to_rects(annot.vertices or [])
            if not rects:
                return []
            return [TextMark(KIND_BY_TYPE[atype], rects, color, opacity)]
        if atype == pymupdf.PDF_ANNOT_INK:
            width = float((annot.border or {}).get("width", 1.0))
            if width <= 0:
                width = 1.0
            marker = (annot.blendmode or "") == "Multiply"
            strokes = []
            for stroke in annot.vertices or []:
                pts = [(float(p[0]), float(p[1])) for p in stroke]
                if pts:
                    strokes.append(InkStroke(pts, color, width, opacity, marker))
            return strokes
        return []

    def add(self, pno: int, annot: Annotation) -> None:
        self.annotations.setdefault(pno, []).append(annot)
        self._touched.add(pno)

    def remove(self, pno: int, annot: Annotation) -> None:
        lst = self.annotations.get(pno, [])
        self.annotations[pno] = [a for a in lst if a.id != annot.id]
        self._touched.add(pno)

    def count(self) -> int:
        return sum(len(v) for v in self.annotations.values())

    # ----- escritura -----
    def _apply_to_pdf(self) -> None:
        try:
            author = getpass.getuser() or "Fluo"
        except Exception:
            author = "Fluo"
        for pno in sorted(self._touched):
            page = self.doc[pno]
            for xref in [a.xref for a in page.annots(types=SUPPORTED_TYPES)]:
                page.delete_annot(page.load_annot(xref))
            for a in self.annotations.get(pno, []):
                if isinstance(a, TextMark):
                    quads = [pymupdf.Rect(*q) for q in a.quads]
                    adder = {
                        TextMarkKind.HIGHLIGHT: page.add_highlight_annot,
                        TextMarkKind.UNDERLINE: page.add_underline_annot,
                        TextMarkKind.STRIKEOUT: page.add_strikeout_annot,
                    }[a.kind]
                    annot = adder(quads)
                    annot.set_colors(stroke=a.color)
                    if a.opacity < 1:
                        annot.set_opacity(a.opacity)
                else:
                    annot = page.add_ink_annot([a.points])
                    annot.set_border(width=a.width)
                    annot.set_colors(stroke=a.color)
                    if a.opacity < 1:
                        annot.set_opacity(a.opacity)
                    if a.marker:
                        annot.set_blendmode(pymupdf.PDF_BM_Multiply)
                annot.set_info(title=author)
                annot.update()
        self._touched.clear()

    def save(self, target: str | None = None) -> str:
        """Escribe las marcas en el PDF.

        Sin ``target`` guarda sobre el archivo actual. Con ``target`` crea un PDF
        nuevo y el documento pasa a trabajar sobre él. Devuelve la ruta final.
        """
        self._apply_to_pdf()
        if target is None or os.path.abspath(target) == self.path:
            self._save_in_place()
            return self.path
        target = os.path.abspath(target)
        self.doc.save(target, garbage=1, deflate=True)
        self._reopen(target)
        return self.path

    def _save_in_place(self) -> None:
        if self.doc.can_save_incrementally():
            try:
                self.doc.saveIncr()
                return
            except Exception:
                log.warning("Guardado incremental falló, reescribo completo", exc_info=True)
        fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=os.path.dirname(self.path))
        os.close(fd)
        try:
            self.doc.save(tmp, garbage=1, deflate=True)
            self.doc.close()
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        self._reopen(self.path)

    def _reopen(self, path: str) -> None:
        try:
            self.doc.close()
        except Exception:
            pass
        self.path = os.path.abspath(path)
        self.doc = pymupdf.open(self.path)

    def close(self) -> None:
        try:
            self.doc.close()
        except Exception:
            pass
