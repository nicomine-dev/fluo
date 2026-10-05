"""Modelo de anotaciones, independiente de Qt y de PyMuPDF.

Todas las coordenadas estan en puntos PDF, en el sistema de la pagina SIN rotar
(el mismo que usa PyMuPDF para anotaciones y texto). La vista aplica la
rotacion al dibujar.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple, Union

RGB = Tuple[float, float, float]
Rect = Tuple[float, float, float, float]  # x0, y0, x1, y1
Point = Tuple[float, float]


def _new_id() -> str:
    return uuid.uuid4().hex


class TextMarkKind(str, Enum):
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKEOUT = "strikeout"


@dataclass
class TextMark:
    """Marca anclada a texto: resaltado, subrayado o tachado. Un rect por linea."""

    kind: TextMarkKind
    quads: list[Rect]
    color: RGB
    opacity: float = 1.0
    id: str = field(default_factory=_new_id)


@dataclass
class InkStroke:
    """Un trazo a mano alzada. marker=True es el resaltador libre (mezcla multiplicar)."""

    points: list[Point]
    color: RGB
    width: float
    opacity: float = 1.0
    marker: bool = False
    id: str = field(default_factory=_new_id)


Annotation = Union[TextMark, InkStroke]


def union_rect(a: Rect, b: Rect) -> Rect:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
