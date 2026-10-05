"""Miniaturas de la primera página, renderizadas en segundo plano y cacheadas en disco."""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import pymupdf
from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal
from PySide6.QtGui import QImage

from ..paths import thumbs_dir

log = logging.getLogger(__name__)

THUMB_W = 150
THUMB_H = 200
RENDER_W = THUMB_W * 2  # se renderiza al doble y se achica: queda nítida


def thumb_cache_path(path: str) -> Path | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = f"{os.path.normcase(os.path.abspath(path))}|{st.st_mtime_ns}|{st.st_size}"
    return thumbs_dir() / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".png")


def render_thumbnail(path: str) -> QImage:
    doc = pymupdf.open(path)
    try:
        page = doc[0]
        zoom = RENDER_W / max(page.rect.width, 1.0)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
    finally:
        doc.close()


class ThumbWorker(QThread):
    ready = Signal(str, QImage)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._queue: list[str] = []
        self._stop = False

    def request(self, paths: list[str]) -> None:
        self._mutex.lock()
        try:
            seen = set(self._queue)
            for p in paths:
                if p not in seen:
                    self._queue.append(p)
                    seen.add(p)
            self._cond.wakeOne()
        finally:
            self._mutex.unlock()

    def stop(self) -> None:
        self._mutex.lock()
        try:
            self._stop = True
            self._queue.clear()
            self._cond.wakeOne()
        finally:
            self._mutex.unlock()
        self.wait(5000)

    def run(self) -> None:
        while True:
            self._mutex.lock()
            try:
                while not self._queue and not self._stop:
                    self._cond.wait(self._mutex)
                if self._stop:
                    return
                path = self._queue.pop(0)
            finally:
                self._mutex.unlock()
            try:
                cache = thumb_cache_path(path)
                img = QImage()
                if cache is not None and cache.exists():
                    img.load(str(cache))
                if img.isNull():
                    img = render_thumbnail(path)
                    if cache is not None:
                        img.save(str(cache), "PNG")
                self.ready.emit(path, img)
            except Exception:
                log.warning("No pude generar la miniatura de %s", path, exc_info=True)
                self.failed.emit(path)
