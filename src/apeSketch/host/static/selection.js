/** Geometry helpers for apeSketch selection (tap, marquee, lasso). */
(function (global) {
  "use strict";

  function refKey(kind, id) {
    return `${kind}:${id}`;
  }

  function parseRef(key) {
    const i = key.indexOf(":");
    if (i <= 0) return { kind: "", id: key };
    return { kind: key.slice(0, i), id: key.slice(i + 1) };
  }

  function normalizeRect(x0, y0, x1, y1) {
    const minX = Math.min(x0, x1);
    const minY = Math.min(y0, y1);
    const maxX = Math.max(x0, x1);
    const maxY = Math.max(y0, y1);
    return { minX, minY, maxX, maxY, x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }

  function rectsIntersect(a, b) {
    return !(a.maxX < b.minX || a.minX > b.maxX || a.maxY < b.minY || a.minY > b.maxY);
  }

  function pointInRect(x, y, rect) {
    return x >= rect.minX && x <= rect.maxX && y >= rect.minY && y <= rect.maxY;
  }

  /** Ray-casting point-in-polygon (closed loop). */
  function pointInPolygon(x, y, poly) {
    if (!poly || poly.length < 3) return false;
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const xi = poly[i].x;
      const yi = poly[i].y;
      const xj = poly[j].x;
      const yj = poly[j].y;
      const intersect =
        yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi;
      if (intersect) inside = !inside;
    }
    return inside;
  }

  /** Pick when bbox center falls inside the polygon. */
  function bboxCenterInPolygon(bb, poly) {
    const cx = (bb.minX + bb.maxX) / 2;
    const cy = (bb.minY + bb.maxY) / 2;
    return pointInPolygon(cx, cy, poly);
  }

  function unionBounds(items) {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const bb of items) {
      if (!bb) continue;
      minX = Math.min(minX, bb.minX);
      minY = Math.min(minY, bb.minY);
      maxX = Math.max(maxX, bb.maxX);
      maxY = Math.max(maxY, bb.maxY);
    }
    if (!Number.isFinite(minX)) return null;
    return normalizeRect(minX, minY, maxX, maxY);
  }

  global.ApeSketchSelection = {
    refKey,
    parseRef,
    normalizeRect,
    rectsIntersect,
    pointInRect,
    pointInPolygon,
    bboxCenterInPolygon,
    unionBounds,
  };
})(typeof window !== "undefined" ? window : globalThis);
