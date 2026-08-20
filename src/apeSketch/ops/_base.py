"""Op registry and shared parsing helpers.

Every op class declares its wire name as ``kind`` and registers itself
with :func:`register`. ``op_from_dict`` dispatches through the registry,
so adding an op never touches a central if/elif chain.
"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, TypeVar

from apeSketch.errors import DocumentError
from apeSketch.types import InkPoint


class OpProtocol(Protocol):
    """Shape every op class must satisfy."""

    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> Any: ...


_T = TypeVar("_T", bound=type)

REGISTRY: dict[str, Any] = {}


def register(cls: _T) -> _T:
    """Register an op class under its ``kind`` wire name."""
    kind = getattr(cls, "kind", None)
    if not isinstance(kind, str) or not kind:
        raise TypeError(f"{cls.__name__} must define a non-empty ClassVar 'kind'")
    if kind in REGISTRY:
        raise TypeError(f"duplicate op kind {kind!r}")
    REGISTRY[kind] = cls
    return cls


def require_id(name: str, value: str) -> str:
    stripped = value.strip()
    if stripped == "":
        raise DocumentError(f"{name} must be a non-empty string")
    return stripped


def require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise DocumentError(f"{key} must be a string")
    return value


def points_from_raw(raw: object) -> tuple[InkPoint, ...]:
    if not isinstance(raw, list):
        raise DocumentError("points must be a list")
    points: list[InkPoint] = []
    for item in raw:
        if not isinstance(item, (list, tuple)):
            raise DocumentError("each point must be a list of numbers")
        try:
            points.append(InkPoint.from_list([float(v) for v in item]))
        except (TypeError, ValueError) as exc:
            raise DocumentError(f"invalid point: {exc}") from exc
    return tuple(points)


def blocks_tuple(data: dict[str, Any]) -> tuple[dict[str, Any], ...] | None:
    raw = data.get("blocks")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise DocumentError("blocks must be a list")
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise DocumentError("each block must be an object")
        out.append({str(k): v for k, v in item.items()})
    return tuple(out)
