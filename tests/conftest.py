import os

import pymupdf
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def make_sample_pdf(path: str) -> str:
    """Tres páginas: texto normal, página rotada 90° con texto, y una sin texto."""
    doc = pymupdf.open()
    p1 = doc.new_page(width=400, height=600)
    y = 80
    for line in [
        "Primera linea de prueba para resaltar",
        "Segunda linea con mas palabras",
        "Tercera linea final del parrafo",
    ]:
        p1.insert_text((40, y), line, fontsize=14)
        y += 24
    p2 = doc.new_page(width=400, height=600)
    p2.insert_text((40, 100), "Pagina rotada noventa grados", fontsize=14)
    p2.set_rotation(90)
    doc.new_page(width=300, height=300)  # sin texto (como un escaneo)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def sample_pdf(tmp_path):
    return make_sample_pdf(str(tmp_path / "muestra.pdf"))


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def wait_ms(ms: int) -> None:
    """Espera procesando eventos y soltando el GIL (QTest.qWait lo retiene y
    deja sin correr a los QThread con código Python)."""
    import time

    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + ms / 1000
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)
