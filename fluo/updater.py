"""Chequeo de actualizaciones contra GitHub Releases y descarga del instalador."""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from PySide6.QtCore import QThread, Signal

from . import APP_NAME, GITHUB_REPO, __version__

log = logging.getLogger(__name__)
API_URL = "https://api.github.com/repos/{repo}/releases/latest"
SETUP_PATTERN = re.compile(r"setup.*\.exe$", re.IGNORECASE)


def parse_version(text: str) -> tuple[int, ...]:
    text = text.strip().lstrip("vV")
    parts = []
    for chunk in text.split("."):
        m = re.match(r"\d+", chunk)
        if not m:
            break
        parts.append(int(m.group()))
    return tuple(parts) or (0,)


def is_newer(latest: str, current: str = __version__) -> bool:
    return parse_version(latest) > parse_version(current)


def fetch_latest(repo: str = GITHUB_REPO, timeout: float = 8.0) -> dict | None:
    req = urllib.request.Request(
        API_URL.format(repo=repo),
        headers={
            "User-Agent": f"{APP_NAME}/{__version__}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    tag = data.get("tag_name") or ""
    asset = next(
        (a for a in data.get("assets", []) if SETUP_PATTERN.search(a.get("name", ""))), None
    )
    if not tag or asset is None:
        return None
    return {
        "version": tag.lstrip("vV"),
        "url": asset["browser_download_url"],
        "name": asset["name"],
        "size": int(asset.get("size", 0)),
        "page": data.get("html_url", ""),
        "notes": data.get("body") or "",
    }


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


class UpdateChecker(QThread):
    available = Signal(dict)

    def run(self) -> None:
        try:
            info = fetch_latest()
        except Exception as exc:  # noqa: BLE001 - sin red o sin releases: no es un error
            log.info("No pude consultar actualizaciones: %s", exc)
            return
        if info and is_newer(info["version"]):
            self.available.emit(info)


class Downloader(QThread):
    progress = Signal(int, int)  # bytes recibidos, total
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, filename: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.filename = filename

    def run(self) -> None:
        target = os.path.join(tempfile.gettempdir(), self.filename)
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": f"{APP_NAME}/{__version__}"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(target, "wb") as out:
                total = int(resp.headers.get("Content-Length") or 0)
                received = 0
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    received += len(chunk)
                    self.progress.emit(received, total)
        except Exception as exc:  # noqa: BLE001
            log.warning("Descarga fallida", exc_info=True)
            self.failed.emit(str(exc))
            return
        self.done.emit(target)


def launch_installer(path: str) -> None:
    """Corre el instalador silencioso. Inno Setup cierra la app y la relanza al terminar."""
    subprocess.Popen([path, "/SILENT", "/SP-", "/NORESTART"], close_fds=True)
