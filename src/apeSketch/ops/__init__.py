"""Typed ink operations. The ops log is the document writer.

Ops are grouped by domain (stroke, image, text, page). Each op class
declares its own wire format (``kind``, ``to_dict``, ``from_payload``)
and registers itself, so adding an op means adding one class in one
domain module plus a Document handler — no central dispatch to edit.
"""

from __future__ import annotations

from typing import Any

from apeSketch.errors import DocumentError
from apeSketch.ops._base import REGISTRY
from apeSketch.ops.image import AddImage, EraseImage, SetImageLock, TransformImage
from apeSketch.ops.page import ClearPage, SetBackground
from apeSketch.ops.stroke import (
    AddStroke,
    AppendPoints,
    BeginStroke,
    EndStroke,
    EraseStroke,
    MoveStrokes,
    ReplaceStrokePoints,
    SetStrokeStyle,
)
from apeSketch.ops.text import (
    AddText,
    EraseText,
    SetTextContent,
    SetTextLock,
    SetTextStyle,
    TransformText,
)

SCHEMA_ID = "apeSketch.document.v0"
UNITS = "css_px"

Op = (
    BeginStroke
    | AppendPoints
    | EndStroke
    | EraseStroke
    | ClearPage
    | SetBackground
    | AddStroke
    | ReplaceStrokePoints
    | AddImage
    | EraseImage
    | TransformImage
    | SetImageLock
    | AddText
    | SetTextContent
    | SetTextStyle
    | TransformText
    | EraseText
    | SetTextLock
    | MoveStrokes
    | SetStrokeStyle
)

__all__ = [
    "SCHEMA_ID",
    "UNITS",
    "AddImage",
    "AddStroke",
    "AddText",
    "AppendPoints",
    "BeginStroke",
    "ClearPage",
    "EndStroke",
    "EraseImage",
    "EraseStroke",
    "EraseText",
    "MoveStrokes",
    "Op",
    "ReplaceStrokePoints",
    "SetBackground",
    "SetImageLock",
    "SetStrokeStyle",
    "SetTextContent",
    "SetTextLock",
    "SetTextStyle",
    "TransformImage",
    "TransformText",
    "op_from_dict",
    "op_to_dict",
]


def op_to_dict(op: Op) -> dict[str, Any]:
    kind = getattr(op, "kind", None)
    if not isinstance(kind, str) or REGISTRY.get(kind) is not type(op):
        raise DocumentError(f"unknown op type {type(op)!r}")
    return op.to_dict()


def op_from_dict(data: dict[str, Any]) -> Op:
    kind = data.get("op")
    if not isinstance(kind, str):
        raise DocumentError("op field must be a string")
    page_id = data.get("page_id", "p0")
    if not isinstance(page_id, str):
        raise DocumentError("page_id must be a string")
    cls = REGISTRY.get(kind)
    if cls is None:
        raise DocumentError(f"unknown op {kind!r}")
    op: Op = cls.from_payload(data, page_id)
    return op
