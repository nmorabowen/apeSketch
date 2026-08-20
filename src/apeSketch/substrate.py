"""Shared ape* document file conventions.

Minimal helpers for the consolidated ``.ape.json`` substrate (ADR 0007).
Designed to move into a shared package when multiple ape* products import
them; apeSketch is the first consumer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

APE_FILE_EXTENSION = ".ape.json"
LEGACY_SKETCH_EXTENSION = ".apesketch.json"
PLAIN_JSON_EXTENSION = ".json"

SESSION_DOC_NAME = f"document{APE_FILE_EXTENSION}"
LEGACY_SESSION_DOC_NAME = f"document{LEGACY_SKETCH_EXTENSION}"


def title_from_filename(filename: str | None) -> str | None:
    """Derive a human title from a document filename stem."""
    if not isinstance(filename, str) or not filename.strip():
        return None
    name = Path(filename.strip()).name
    for suffix in (APE_FILE_EXTENSION, LEGACY_SKETCH_EXTENSION, PLAIN_JSON_EXTENSION):
        if name.endswith(suffix):
            stem = name[: -len(suffix)]
            return stem.strip() or None
    stem = Path(name).stem.strip()
    return stem or None


def title_from_open_request(title: str | None, filename: str | None) -> str:
    if isinstance(title, str) and title.strip():
        return title.strip()
    from_name = title_from_filename(filename)
    return from_name if from_name else "Untitled"


def is_ape_envelope(data: dict[str, Any]) -> bool:
    schema = data.get("schema")
    return isinstance(schema, str) and ".document." in schema


def product_from_schema(schema: str) -> str | None:
    """Return product id from e.g. ``apeSketch.document.v0``."""
    parts = schema.split(".")
    if len(parts) >= 3 and parts[1] == "document":
        return parts[0]
    return None


def export_filename(*, product: str, revision: int, stamp: int | None = None) -> str:
    """Default download name for a document export."""
    if stamp is not None:
        return f"{product.lower()}-{stamp}{APE_FILE_EXTENSION}"
    return f"{product.lower()}-{revision}{APE_FILE_EXTENSION}"
