"""Hilo de renderizado: dibuja páginas con MuPDF sin bloquear la interfaz."""
from __future__ import annotations

import logging

import pymupdf

from ..qt import QImage, QMutex, QThread, QWaitCondition, Signal

log = logging.getLogger(__name__)


class RenderWorker(QThread):
    """Recibe pedidos (página, escala) y emite QImage.

    Abre su propia copia del PDF, así el hilo principal puede usar la suya para
    texto y anotaciones sin pisarse (MuPDF no es thread-safe).
    """

    rendered = Signal(int, float, QImage)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._queue: list[tuple[int, float]] = []
        self._stop = False
        self._reopen = False

    def request(self, jobs: list[tuple[int, float]]) -> None:
        """Reemplaza la cola de trabajo. El que llama pone lo visible primero."""
        self._mutex.lock()
        try:
            self._queue = list(jobs)
            self._cond.wakeOne()
        finally:
            self._mutex.unlock()

    def set_path(self, path: str) -> None:
        self._mutex.lock()
        try:
            self._path = path
            self._reopen = True
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

    def run(self) -> None:  # noqa: C901 - bucle de trabajo
        doc = None
        try:
            doc = pymupdf.open(self._path)
            while True:
                self._mutex.lock()
                try:
                    while not self._queue and not self._stop and not self._reopen:
                        self._cond.wait(self._mutex)
                    if self._stop:
                        break
                    if self._reopen:
                        self._reopen = False
                        new_path = self._path
                        job = None
                    else:
                        new_path = None
                        job = self._queue.pop(0)
                finally:
                    self._mutex.unlock()

                if new_path is not None:
                    try:
                        doc.close()
                    except Exception:
                        pass
                    doc = pymupdf.open(new_path)
                    continue

                pno, scale = job
                try:
                    page = doc[pno]
                    pix = page.get_pixmap(
                        matrix=pymupdf.Matrix(scale, scale), alpha=False, annots=False
                    )
                    # El buffer tiene que seguir vivo hasta después del copy(): Qt 5 no lo retiene.
                    data = pix.samples
                    img = QImage(data, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                    del data
                    self.rendered.emit(pno, scale, img)
                except Exception:
                    log.exception("Falló el render de la página %s", pno)
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass
