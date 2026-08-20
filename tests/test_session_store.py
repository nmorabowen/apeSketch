"""Persistent session library tests."""

from __future__ import annotations

from pathlib import Path

from apeSketch.document import Document
from apeSketch.host.session_store import SessionStore
from apeSketch.ops import BeginStroke, EndStroke
from apeSketch.session import SketchSession
from apeSketch.types import StrokeStyle


def _stroke(doc: Document, stroke_id: str = "s1") -> None:
    doc.apply(
        BeginStroke(
            stroke_id=stroke_id,
            author="t",
            style=StrokeStyle(color="#111111", width=2),
        )
    )
    doc.apply(EndStroke(stroke_id=stroke_id))


def test_session_store_create_list_load(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions")
    doc = Document()
    _stroke(doc)
    meta = store.create(doc, title="Bridge notes")
    assert meta.title == "Bridge notes"
    assert meta.revision == 2

    listed = store.list()
    assert len(listed) == 1
    assert listed[0].id == meta.id

    loaded_meta, loaded = store.load(meta.id)
    assert loaded_meta.id == meta.id
    assert len(loaded.strokes()) == 1
    assert loaded.revision == 2


def test_session_store_loads_legacy_document_name(tmp_path):
    from apeSketch.substrate import LEGACY_SESSION_DOC_NAME, SESSION_DOC_NAME

    store = SessionStore(tmp_path / "sessions")
    doc = Document()
    meta = store.create(doc, title="Legacy")
    legacy_path = store._dir(meta.id) / LEGACY_SESSION_DOC_NAME
    current_path = store._dir(meta.id) / SESSION_DOC_NAME
    current_path.unlink()
    legacy_path.write_text(doc.to_json(), encoding="utf-8")

    loaded_meta, loaded = store.load(meta.id)
    assert loaded_meta.id == meta.id
    assert loaded.revision == doc.revision


def test_session_store_save_migrates_legacy_document_name(tmp_path):
    from apeSketch.substrate import LEGACY_SESSION_DOC_NAME, SESSION_DOC_NAME

    store = SessionStore(tmp_path / "sessions")
    doc = Document()
    meta = store.create(doc, title="Migrate")
    folder = store._dir(meta.id)
    legacy_path = folder / LEGACY_SESSION_DOC_NAME
    current_path = folder / SESSION_DOC_NAME
    current_path.unlink()
    legacy_path.write_text(doc.to_json(), encoding="utf-8")

    store.save(meta.id, doc, title="Migrate")
    assert current_path.is_file()
    assert not legacy_path.is_file()


def test_session_store_save_rename_delete(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions")
    doc = Document()
    meta = store.create(doc, title="Draft")
    _stroke(doc, "a")
    saved = store.save(meta.id, doc)
    assert saved.revision == 2

    renamed = store.rename(meta.id, "Final")
    assert renamed.title == "Final"

    store.delete(meta.id)
    assert store.list() == []


def test_replace_document_broadcasts_snapshot() -> None:
    session = SketchSession()
    seen: list[dict] = []
    session.subscribe(seen.append)
    doc = Document()
    _stroke(doc)
    message = session.replace_document(doc, session_id="sdeadbeef", session_title="Kept")
    assert message["type"] == "snapshot"
    assert message["session"]["id"] == "sdeadbeef"
    assert message["session"]["title"] == "Kept"
    assert len(seen) == 1
    assert session.document.revision == 2
