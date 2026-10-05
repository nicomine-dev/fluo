"""Bibliotecas de PDFs: colecciones de accesos directos a archivos, persistidas en JSON."""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

RECENT_ID = "__recent__"
MAX_RECENT = 30
FORMAT_VERSION = 1


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


@dataclass
class LibraryItem:
    path: str
    title: str
    added: str = field(default_factory=_now)

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.path)


@dataclass
class Library:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    items: list[LibraryItem] = field(default_factory=list)

    def has(self, path: str) -> bool:
        n = norm(path)
        return any(norm(i.path) == n for i in self.items)


@dataclass
class FileState:
    last_page: int = 0
    last_opened: str = field(default_factory=_now)


class LibraryStore:
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self.libraries: list[Library] = []
        self.recent: list[str] = []
        self.files: dict[str, FileState] = {}
        self.load()

    # ----- persistencia -----
    def load(self) -> None:
        if not self.file_path.exists():
            self.libraries = [Library("Mi biblioteca")]
            return
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.libraries = [Library("Mi biblioteca")]
            return
        self.libraries = [
            Library(
                name=lib.get("name", "Biblioteca"),
                id=lib.get("id") or uuid.uuid4().hex,
                items=[
                    LibraryItem(
                        path=i["path"],
                        title=i.get("title") or Path(i["path"]).stem,
                        added=i.get("added", _now()),
                    )
                    for i in lib.get("items", [])
                    if i.get("path")
                ],
            )
            for lib in data.get("libraries", [])
        ]
        self.recent = [p for p in data.get("recent", []) if isinstance(p, str)]
        self.files = {
            k: FileState(int(v.get("last_page", 0)), v.get("last_opened", _now()))
            for k, v in data.get("files", {}).items()
        }
        if not self.libraries:
            self.libraries = [Library("Mi biblioteca")]

    def save(self) -> None:
        data = {
            "version": FORMAT_VERSION,
            "libraries": [
                {"id": lib.id, "name": lib.name, "items": [asdict(i) for i in lib.items]}
                for lib in self.libraries
            ],
            "recent": self.recent[:MAX_RECENT],
            "files": {k: asdict(v) for k, v in self.files.items()},
        }
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.file_path)

    # ----- bibliotecas -----
    def get(self, library_id: str) -> Library | None:
        return next((lib for lib in self.libraries if lib.id == library_id), None)

    def add_library(self, name: str) -> Library:
        lib = Library(name.strip() or "Biblioteca")
        self.libraries.append(lib)
        return lib

    def rename_library(self, library_id: str, name: str) -> None:
        lib = self.get(library_id)
        if lib and name.strip():
            lib.name = name.strip()

    def remove_library(self, library_id: str) -> None:
        self.libraries = [lib for lib in self.libraries if lib.id != library_id]
        if not self.libraries:
            self.libraries = [Library("Mi biblioteca")]

    # ----- items -----
    def add_items(self, library_id: str, paths: list[str]) -> int:
        """Agrega accesos a PDFs (sin duplicar). Devuelve cuántos se agregaron."""
        lib = self.get(library_id)
        if lib is None:
            return 0
        added = 0
        for p in paths:
            if not p.lower().endswith(".pdf") or lib.has(p):
                continue
            lib.items.append(LibraryItem(path=os.path.abspath(p), title=Path(p).stem))
            added += 1
        return added

    def remove_item(self, library_id: str, path: str) -> None:
        lib = self.get(library_id)
        if lib:
            n = norm(path)
            lib.items = [i for i in lib.items if norm(i.path) != n]

    def move_item(self, from_id: str, to_id: str, path: str) -> None:
        src, dst = self.get(from_id), self.get(to_id)
        if not src or not dst or src is dst:
            return
        n = norm(path)
        moving = [i for i in src.items if norm(i.path) == n]
        src.items = [i for i in src.items if norm(i.path) != n]
        for item in moving:
            if not dst.has(item.path):
                dst.items.append(item)

    @staticmethod
    def scan_folder(folder: str, recursive: bool) -> list[str]:
        found: list[str] = []
        if recursive:
            for root, _dirs, files in os.walk(folder):
                found.extend(os.path.join(root, f) for f in files if f.lower().endswith(".pdf"))
        else:
            try:
                found = [
                    os.path.join(folder, f)
                    for f in os.listdir(folder)
                    if f.lower().endswith(".pdf")
                ]
            except OSError:
                found = []
        return sorted(found, key=str.lower)

    # ----- recientes y estado por archivo -----
    def touch_opened(self, path: str) -> None:
        path = os.path.abspath(path)
        n = norm(path)
        self.recent = [p for p in self.recent if norm(p) != n]
        self.recent.insert(0, path)
        del self.recent[MAX_RECENT:]
        state = self.files.setdefault(n, FileState())
        state.last_opened = _now()

    def remove_recent(self, path: str) -> None:
        n = norm(path)
        self.recent = [p for p in self.recent if norm(p) != n]

    def last_page(self, path: str) -> int:
        state = self.files.get(norm(path))
        return state.last_page if state else 0

    def set_last_page(self, path: str, page: int) -> None:
        state = self.files.setdefault(norm(path), FileState())
        state.last_page = max(0, int(page))
