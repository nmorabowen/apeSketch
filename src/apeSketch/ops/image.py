"""Image ops: placed raster objects backed by the asset store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from apeSketch.errors import DocumentError
from apeSketch.ops._base import register, require_id, require_str


@register
@dataclass(frozen=True, slots=True)
class AddImage:
    kind: ClassVar[str] = "add_image"

    image_id: str
    asset_id: str
    x: float
    y: float
    width: float
    height: float
    author: str = ""
    layer: str = "images"
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_id", require_id("image_id", self.image_id))
        object.__setattr__(self, "asset_id", require_id("asset_id", self.asset_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        object.__setattr__(self, "layer", self.layer.strip() or "images")
        if self.width <= 0 or self.height <= 0:
            raise DocumentError("image width/height must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.kind,
            "image_id": self.image_id,
            "asset_id": self.asset_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "author": self.author,
            "layer": self.layer,
            "page_id": self.page_id,
        }

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> AddImage:
        image_id = data.get("image_id")
        asset_id = data.get("asset_id")
        if not isinstance(image_id, str) or not isinstance(asset_id, str):
            raise DocumentError("image_id/asset_id must be strings")
        x = data.get("x", 0.0)
        y = data.get("y", 0.0)
        width = data.get("width")
        height = data.get("height")
        author = data.get("author", "")
        layer = data.get("layer", "images")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise DocumentError("image x/y must be numbers")
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            raise DocumentError("image width/height must be numbers")
        if not isinstance(author, str) or not isinstance(layer, str):
            raise DocumentError("author/layer must be strings")
        return cls(
            image_id=image_id,
            asset_id=asset_id,
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
            author=author,
            layer=layer,
            page_id=page_id,
        )


@register
@dataclass(frozen=True, slots=True)
class EraseImage:
    kind: ClassVar[str] = "erase_image"

    image_id: str
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_id", require_id("image_id", self.image_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))

    def to_dict(self) -> dict[str, Any]:
        return {"op": self.kind, "image_id": self.image_id, "page_id": self.page_id}

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> EraseImage:
        return cls(image_id=require_str(data, "image_id"), page_id=page_id)


@register
@dataclass(frozen=True, slots=True)
class TransformImage:
    kind: ClassVar[str] = "transform_image"

    image_id: str
    x: float
    y: float
    width: float
    height: float
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_id", require_id("image_id", self.image_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        if self.width <= 0 or self.height <= 0:
            raise DocumentError("image width/height must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.kind,
            "image_id": self.image_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "page_id": self.page_id,
        }

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> TransformImage:
        image_id = require_str(data, "image_id")
        x = data.get("x")
        y = data.get("y")
        width = data.get("width")
        height = data.get("height")
        if (
            not isinstance(x, (int, float))
            or not isinstance(y, (int, float))
            or not isinstance(width, (int, float))
            or not isinstance(height, (int, float))
        ):
            raise DocumentError("transform_image needs numeric x/y/width/height")
        return cls(
            image_id=image_id,
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
            page_id=page_id,
        )


@register
@dataclass(frozen=True, slots=True)
class SetImageLock:
    kind: ClassVar[str] = "set_image_lock"

    image_id: str
    locked: bool
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_id", require_id("image_id", self.image_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.kind,
            "image_id": self.image_id,
            "locked": self.locked,
            "page_id": self.page_id,
        }

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> SetImageLock:
        image_id = require_str(data, "image_id")
        locked = data.get("locked")
        if not isinstance(locked, bool):
            raise DocumentError("locked must be a bool")
        return cls(image_id=image_id, locked=locked, page_id=page_id)
