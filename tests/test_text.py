"""Text object ops — plain and rich blocks."""

from __future__ import annotations

import pytest

from apeSketch.document import Document
from apeSketch.errors import DocumentError
from apeSketch.ops import (
    AddText,
    EraseText,
    SetTextContent,
    SetTextLock,
    SetTextStyle,
    TransformText,
)
from apeSketch.types import TextBlock, TextObject, TextRun, flatten_blocks


def test_add_edit_transform_erase_text() -> None:
    doc = Document()
    doc.apply(
        AddText(
            text_id="t1",
            content="Hello",
            x=10,
            y=20,
            width=200,
            height=40,
            font_size=24,
            color="#001199",
        )
    )
    page = doc.page()
    assert page.text_order == ["t1"]
    assert page.texts["t1"].content == "Hello"
    assert page.texts["t1"].blocks[0].runs[0].text == "Hello"

    doc.apply(SetTextContent(text_id="t1", content="Hello\nworld"))
    assert page.texts["t1"].content == "Hello\nworld"

    doc.apply(TransformText(text_id="t1", x=5, y=6, width=180, height=60, font_size=30))
    text = page.texts["t1"]
    assert text.x == 5 and text.font_size == 30

    svg = Document._page_to_svg(page)
    assert 'data-text-id="t1"' in svg
    assert "Hello" in svg

    doc.apply(EraseText(text_id="t1"))
    assert page.texts == {}


def test_text_style_bold_italic() -> None:
    doc = Document()
    doc.apply(
        AddText(
            text_id="t1",
            content="Styled",
            x=0,
            y=0,
            width=120,
            height=40,
            bold=True,
            italic=True,
            font_size=32,
        )
    )
    text = doc.page().texts["t1"]
    assert text.bold and text.italic and text.font_size == 32

    doc.apply(SetTextStyle(text_id="t1", bold=False, font_size=18, color="#c62828"))
    text = doc.page().texts["t1"]
    assert text.bold is False and text.italic is True
    assert text.font_size == 18 and text.color == "#c62828"


def test_rich_blocks_roundtrip() -> None:
    blocks = (
        {
            "kind": "ul",
            "indent": 0,
            "runs": [{"text": "Alpha", "bold": True, "font_size": 20}],
        },
        {
            "kind": "ol",
            "indent": 1,
            "runs": [{"text": "Beta", "italic": True}],
        },
        {
            "kind": "p",
            "indent": 0,
            "runs": [
                {"text": "Hi "},
                {"text": "there", "font_size": 36, "bold": True},
            ],
        },
    )
    doc = Document()
    doc.apply(
        AddText(
            text_id="t1",
            content="",
            x=0,
            y=0,
            width=240,
            height=120,
            blocks=blocks,
        )
    )
    text = doc.page().texts["t1"]
    assert len(text.blocks) == 3
    assert text.blocks[0].kind == "ul"
    assert text.blocks[0].runs[0].bold is True
    assert text.blocks[0].runs[0].font_size == 20
    assert text.blocks[1].kind == "ol" and text.blocks[1].indent == 1
    assert text.blocks[2].runs[1].font_size == 36
    assert "Alpha" in text.content and "Beta" in text.content

    svg = Document._page_to_svg(doc.page())
    assert "•" in svg or "Alpha" in svg
    assert "1." in svg or "Beta" in svg
    assert 'font-size="36' in svg

    payload = doc.to_dict()
    restored = Document.from_dict(payload)
    rtext = restored.page().texts["t1"]
    assert len(rtext.blocks) == 3
    assert rtext.blocks[2].runs[1].bold is True


def test_set_text_content_with_blocks() -> None:
    doc = Document()
    doc.apply(AddText(text_id="t1", content="A", x=0, y=0, width=100, height=40))
    blocks = (
        {"kind": "p", "indent": 0, "runs": [{"text": "One"}]},
        {"kind": "ul", "indent": 0, "runs": [{"text": "Two"}]},
    )
    doc.apply(SetTextContent(text_id="t1", content="One\nTwo", blocks=blocks))
    text = doc.page().texts["t1"]
    assert text.blocks[1].kind == "ul"
    assert flatten_blocks(text.blocks) == "One\nTwo"


def test_legacy_plain_content_loads() -> None:
    obj = TextObject.from_dict(
        {
            "text_id": "legacy",
            "content": "line1\nline2",
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 50,
        }
    )
    assert len(obj.blocks) == 2
    assert obj.blocks[0].kind == "p"
    assert obj.blocks[1].runs[0].text == "line2"


def test_text_lock_blocks_edit() -> None:
    doc = Document()
    doc.apply(AddText(text_id="t1", content="A", x=0, y=0, width=100, height=40))
    doc.apply(SetTextLock(text_id="t1", locked=True))
    with pytest.raises(DocumentError):
        doc.apply(SetTextContent(text_id="t1", content="B"))
    with pytest.raises(DocumentError):
        doc.apply(TransformText(text_id="t1", x=1, y=1, width=10, height=10))
    with pytest.raises(DocumentError):
        doc.apply(SetTextStyle(text_id="t1", bold=True))


def test_transform_does_not_require_font_size() -> None:
    doc = Document()
    doc.apply(
        AddText(text_id="t1", content="A", x=0, y=0, width=100, height=40, font_size=28)
    )
    doc.apply(TransformText(text_id="t1", x=10, y=20, width=200, height=80))
    text = doc.page().texts["t1"]
    assert text.x == 10 and text.width == 200
    assert text.font_size == 28
