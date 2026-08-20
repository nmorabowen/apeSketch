"""Asset store and image ops."""

from __future__ import annotations

import base64

import pytest

from apeSketch.assets import AssetStore
from apeSketch.document import Document
from apeSketch.export import page_to_svg
from apeSketch.ops import AddImage, EraseImage, SetBackground


def test_asset_store_roundtrip(tmp_path) -> None:
    store = AssetStore(tmp_path)
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    item = store.put_bytes(png, "image/png")
    got = store.get(item.asset_id)
    assert got is not None
    assert got.data == png
    assert got.mime == "image/png"
    assert store.data_uri(item.asset_id).startswith("data:image/png;base64,")


def test_asset_store_sniffs_png_when_mime_blank(tmp_path) -> None:
    store = AssetStore(tmp_path)
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    item = store.put_bytes(png, "application/octet-stream")
    assert item.mime == "image/png"


def test_add_and_erase_image_in_document() -> None:
    doc = Document()
    doc.apply(
        AddImage(
            image_id="img1",
            asset_id="a-test",
            x=10,
            y=20,
            width=100,
            height=50,
            author="t",
        )
    )
    page = doc.page()
    assert "img1" in page.images
    assert page.image_order == ["img1"]
    assert page.images["img1"].asset_id == "a-test"

    svg = page_to_svg(page)
    assert 'data-image-id="img1"' in svg
    assert "a-test" in svg

    doc.apply(EraseImage(image_id="img1"))
    assert page.images == {}
    assert page.image_order == []


def test_clear_page_clears_images() -> None:
    from apeSketch.ops import ClearPage

    doc = Document()
    doc.apply(SetBackground(color="#1c211c"))
    doc.apply(
        AddImage(
            image_id="img1",
            asset_id="a-test",
            x=0,
            y=0,
            width=10,
            height=10,
        )
    )
    doc.apply(ClearPage())
    assert doc.page().images == {}
    assert doc.page().image_order == []
    assert doc.page().background == "#1c211c"


def test_transform_image() -> None:
    from apeSketch.ops import TransformImage

    doc = Document()
    doc.apply(
        AddImage(
            image_id="img1",
            asset_id="a-test",
            x=0,
            y=0,
            width=100,
            height=50,
        )
    )
    doc.apply(
        TransformImage(image_id="img1", x=20, y=30, width=80, height=40)
    )
    image = doc.page().images["img1"]
    assert image.x == 20
    assert image.y == 30
    assert image.width == 80
    assert image.height == 40


def test_image_lock_blocks_transform() -> None:
    from apeSketch.errors import DocumentError
    from apeSketch.ops import SetImageLock, TransformImage

    doc = Document()
    doc.apply(
        AddImage(
            image_id="img1",
            asset_id="a-test",
            x=0,
            y=0,
            width=100,
            height=50,
        )
    )
    doc.apply(SetImageLock(image_id="img1", locked=True))
    assert doc.page().images["img1"].locked is True
    with pytest.raises(DocumentError):
        doc.apply(TransformImage(image_id="img1", x=1, y=1, width=10, height=10))
    doc.apply(SetImageLock(image_id="img1", locked=False))
    doc.apply(TransformImage(image_id="img1", x=1, y=1, width=10, height=10))
    assert doc.page().images["img1"].x == 1
