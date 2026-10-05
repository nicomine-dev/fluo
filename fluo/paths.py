"""Rutas de datos de la app (config, cache de miniaturas, recursos)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME


def data_dir() -> Path:
    base = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("XDG_DATA_HOME")
        or str(Path.home() / ".local" / "share")
    )
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def thumbs_dir() -> Path:
    path = data_dir() / "thumbs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def library_file() -> Path:
    return data_dir() / "library.json"


def log_file() -> Path:
    return data_dir() / "fluo.log"


def resource_path(name: str) -> Path:
    """Recurso empaquetado. Funciona en desarrollo y dentro de PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "fluo" / "resources" / name
