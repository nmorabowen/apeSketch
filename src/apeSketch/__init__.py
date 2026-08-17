"""apeSketch: hand-ink bridge for ape* workflows.

The Python Document is the source of truth. Clients emit Ops.
See AProjects/ for ADRs and the prototype plan.
"""

from apeSketch.document import Document
from apeSketch.errors import DocumentError
from apeSketch.ops import SCHEMA_ID, UNITS
from apeSketch.session import SketchSession

__all__ = [
    "SCHEMA_ID",
    "UNITS",
    "Document",
    "DocumentError",
    "SketchSession",
]

__version__ = "0.1.0"
