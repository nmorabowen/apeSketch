# Adding an op

The op vocabulary grows one class at a time; nothing central is
edited (ADR 0011). Checklist:

1. **Pick the domain module** in `src/apeSketch/ops/`: `stroke.py`,
   `image.py`, `text.py`, or `page.py`. A genuinely new domain (e.g.
   shapes) gets a new module there.
2. **Write the op class**: frozen slotted dataclass with
   - `kind: ClassVar[str] = "<snake_case_wire_name>"`
   - `@register` decorator (from `ops._base`)
   - `__post_init__` validation (use `require_id`, raise
     `DocumentError`)
   - `to_dict(self)` returning the wire payload (include `"op":
     self.kind` and `page_id`)
   - `@classmethod from_payload(cls, data, page_id)` parsing the wire
     dict (use `require_str`, `points_from_raw`, `blocks_tuple`).
3. **Export it** from `ops/__init__.py`: import, add to the `Op`
   union and `__all__`.
4. **Handle it in `document.py`**: add a method named exactly
   `_<kind>` — the naming convention is the dispatch. Don't name an
   op kind after an existing private Document attribute/method
   (`ops`, `pages`, `ensure_page`, ...).
5. **Tests**:
   - add a sample instance to `SAMPLES` in `tests/test_ops.py`
     (the registry-coverage test fails until you do);
   - add behavior tests for the Document handler in the matching
     `tests/test_*.py`.
6. **Client**: handle the kind in `board.js` `applyLocalOp` (and emit
   it where the tool commits). Update `AProjects/memory/glossary.md`
   if the op introduces a new concept.
7. **Exports**: if the op changes what a page *looks like*, update
   `apeSketch/export.py` (SVG) too.

Run: `ruff check src tests` and `pytest` (see
`guides/python-env.md` for the venv).
