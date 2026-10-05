from fluo.library.store import RECENT_ID, LibraryStore, norm


def test_store_roundtrip(tmp_path):
    f = tmp_path / "lib.json"
    s = LibraryStore(f)
    assert [lib.name for lib in s.libraries] == ["Mi biblioteca"]

    lib = s.add_library("Facultad")
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.PDF"
    a.write_bytes(b"%PDF-1.4")
    b.write_bytes(b"%PDF-1.4")
    assert s.add_items(lib.id, [str(a), str(b), str(tmp_path / "no.txt")]) == 2
    assert s.add_items(lib.id, [str(a)]) == 0  # sin duplicar
    s.touch_opened(str(a))
    s.set_last_page(str(a), 7)
    s.save()

    s2 = LibraryStore(f)
    lib2 = s2.get(lib.id)
    assert lib2 is not None and lib2.name == "Facultad" and len(lib2.items) == 2
    assert norm(s2.recent[0]) == norm(str(a))
    assert s2.last_page(str(a)) == 7
    assert s2.last_page(str(b)) == 0

    default_id = s2.libraries[0].id
    s2.move_item(lib.id, default_id, str(a))
    assert len(s2.get(lib.id).items) == 1
    assert s2.libraries[0].has(str(a))

    s2.rename_library(lib.id, "Trabajo")
    assert s2.get(lib.id).name == "Trabajo"
    s2.remove_library(lib.id)
    assert all(lib_.id != lib.id for lib_ in s2.libraries)
    s2.remove_recent(str(a))
    assert s2.recent == []
    assert RECENT_ID not in [lib_.id for lib_ in s2.libraries]


def test_scan_folder(tmp_path):
    (tmp_path / "x.pdf").write_bytes(b"x")
    (tmp_path / "y.txt").write_bytes(b"x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "z.pdf").write_bytes(b"x")
    assert len(LibraryStore.scan_folder(str(tmp_path), recursive=False)) == 1
    assert len(LibraryStore.scan_folder(str(tmp_path), recursive=True)) == 2


def test_corrupt_file_falls_back_to_default(tmp_path):
    f = tmp_path / "lib.json"
    f.write_text("{esto no es json", encoding="utf-8")
    s = LibraryStore(f)
    assert [lib.name for lib in s.libraries] == ["Mi biblioteca"]
