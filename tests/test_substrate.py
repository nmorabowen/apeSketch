"""Consolidated .ape.json substrate helpers."""

from __future__ import annotations

from apeSketch.ops import SCHEMA_ID
from apeSketch.substrate import (
    APE_FILE_EXTENSION,
    export_filename,
    is_ape_envelope,
    product_from_schema,
    title_from_filename,
    title_from_open_request,
)


def test_title_from_filename_handles_family_extensions():
    assert title_from_filename("bridge.ape.json") == "bridge"
    assert title_from_filename("notes.apesketch.json") == "notes"
    assert title_from_filename("legacy.json") == "legacy"
    assert title_from_filename("") is None


def test_title_from_open_request_prefers_explicit_title():
    assert title_from_open_request("Bridge", "other.ape.json") == "Bridge"
    assert title_from_open_request("  ", "notes.ape.json") == "notes"
    assert title_from_open_request(None, None) == "Untitled"


def test_envelope_helpers():
    payload = {"schema": SCHEMA_ID, "units": "css_px", "revision": 0, "ops": []}
    assert is_ape_envelope(payload) is True
    assert product_from_schema(SCHEMA_ID) == "apeSketch"
    assert product_from_schema("not-a-schema") is None


def test_export_filename():
    assert export_filename(product="apeSketch", revision=3) == "apesketch-3.ape.json"
    assert export_filename(product="apeSketch", revision=3, stamp=99) == "apesketch-99.ape.json"
    assert export_filename(product="apeSketch", revision=3).endswith(APE_FILE_EXTENSION)
