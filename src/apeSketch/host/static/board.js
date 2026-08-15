(() => {
  const canvas = document.getElementById("board");
  const ctx = canvas.getContext("2d");
  const statusEl = document.getElementById("status");

  let pair = null;
  let ws = null;
  let documentState = null;
  let currentStrokeId = null;
  let lastStrokeId = null;
  let pointBuffer = [];
  let flushTimer = null;
  const author = `web-${Math.random().toString(36).slice(2, 8)}`;

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    redraw();
  }

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function strokeStyle(stroke) {
    return {
      color: (stroke.style && stroke.style.color) || "#111111",
      width: (stroke.style && stroke.style.width) || 2,
    };
  }

  function drawStroke(stroke, provisionalPoints) {
    const points = provisionalPoints || stroke.points || [];
    if (!points.length) return;
    const style = strokeStyle(stroke);
    ctx.beginPath();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = style.color;
    ctx.lineWidth = style.width;
    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      const x = Array.isArray(p) ? p[0] : p.x;
      const y = Array.isArray(p) ? p[1] : p.y;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  function redraw() {
    ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
    if (!documentState || !documentState.pages) return;
    const pageId = documentState.active_page_id || "p0";
    const page = documentState.pages[pageId];
    if (!page) return;
    const order = page.stroke_order || [];
    for (const sid of order) {
      const stroke = page.strokes[sid];
      if (stroke) drawStroke(stroke);
    }
  }

  function applyLocalOp(op) {
    if (!documentState) {
      documentState = {
        active_page_id: "p0",
        pages: { p0: { page_id: "p0", stroke_order: [], strokes: {} } },
      };
    }
    const pageId = op.page_id || "p0";
    if (!documentState.pages[pageId]) {
      documentState.pages[pageId] = { page_id: pageId, stroke_order: [], strokes: {} };
    }
    const page = documentState.pages[pageId];
    if (op.op === "begin_stroke") {
      page.strokes[op.stroke_id] = {
        stroke_id: op.stroke_id,
        points: [],
        style: op.style || { color: "#111111", width: 2 },
        author: op.author || "",
        open: true,
      };
      page.stroke_order.push(op.stroke_id);
    } else if (op.op === "append_points") {
      const stroke = page.strokes[op.stroke_id];
      if (stroke) stroke.points.push(...op.points);
    } else if (op.op === "end_stroke") {
      const stroke = page.strokes[op.stroke_id];
      if (stroke) stroke.open = false;
    } else if (op.op === "erase_stroke") {
      delete page.strokes[op.stroke_id];
      page.stroke_order = page.stroke_order.filter((id) => id !== op.stroke_id);
    } else if (op.op === "clear_page") {
      page.strokes = {};
      page.stroke_order = [];
    }
    redraw();
  }

  async function loadPair() {
    const res = await fetch("/api/pair");
    pair = await res.json();
    setStatus(`room ${pair.room}`);
    return pair;
  }

  function connectWs() {
    if (!pair || !pair.ws) return;
    // Prefer same-host WS using advertised path; rewrite host for localhost browsing.
    let wsUrl = pair.ws;
    if (location.hostname === "127.0.0.1" || location.hostname === "localhost") {
      const u = new URL(pair.ws);
      u.hostname = location.hostname;
      wsUrl = u.toString();
    }
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "hello", author, role: "capture" }));
      setStatus(`room ${pair.room} · live`);
    };
    ws.onclose = () => setStatus(`room ${pair.room} · disconnected`);
    ws.onerror = () => setStatus(`room ${pair.room} · ws error`);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "snapshot") {
        documentState = msg.document;
        redraw();
        return;
      }
      if (msg.type === "op" && msg.op) {
        applyLocalOp(msg.op);
        if (msg.op.op === "end_stroke") lastStrokeId = msg.op.stroke_id;
        if (msg.op.op === "begin_stroke") lastStrokeId = msg.op.stroke_id;
      }
    };
  }

  function sendOp(op) {
    applyLocalOp(op);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "op", op }));
      return;
    }
    fetch("/api/op", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(op),
    }).catch(() => {});
  }

  function flushPoints() {
    if (!currentStrokeId || pointBuffer.length === 0) return;
    const points = pointBuffer.splice(0, pointBuffer.length);
    sendOp({
      op: "append_points",
      stroke_id: currentStrokeId,
      page_id: "p0",
      points,
    });
  }

  function pointerPos(ev) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: ev.clientX - rect.left,
      y: ev.clientY - rect.top,
      t: ev.timeStamp || performance.now(),
      pressure: ev.pressure > 0 ? ev.pressure : 0.5,
    };
  }

  function onDown(ev) {
    if (ev.pointerType === "touch" && ev.isPrimary === false) return;
    canvas.setPointerCapture(ev.pointerId);
    const p = pointerPos(ev);
    currentStrokeId = `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    lastStrokeId = currentStrokeId;
    sendOp({
      op: "begin_stroke",
      stroke_id: currentStrokeId,
      author,
      page_id: "p0",
      style: { color: "#111111", width: 2.5 },
    });
    pointBuffer.push([p.x, p.y, p.t, p.pressure]);
    flushTimer = setInterval(flushPoints, 32);
    ev.preventDefault();
  }

  function onMove(ev) {
    if (!currentStrokeId) return;
    const p = pointerPos(ev);
    pointBuffer.push([p.x, p.y, p.t, p.pressure]);
    // Local preview of buffered points
    const page = documentState && documentState.pages.p0;
    const stroke = page && page.strokes[currentStrokeId];
    if (stroke) {
      redraw();
      drawStroke(stroke, stroke.points.concat(pointBuffer));
    }
    ev.preventDefault();
  }

  function onUp(ev) {
    if (!currentStrokeId) return;
    flushPoints();
    if (flushTimer) clearInterval(flushTimer);
    flushTimer = null;
    sendOp({ op: "end_stroke", stroke_id: currentStrokeId, page_id: "p0" });
    currentStrokeId = null;
    ev.preventDefault();
  }

  document.getElementById("btn-clear").onclick = () => {
    sendOp({ op: "clear_page", page_id: "p0" });
    lastStrokeId = null;
  };

  document.getElementById("btn-undo").onclick = () => {
    if (!lastStrokeId) return;
    sendOp({ op: "erase_stroke", stroke_id: lastStrokeId, page_id: "p0" });
    lastStrokeId = null;
  };

  document.getElementById("btn-pair").onclick = () => {
    window.open("/pair", "_blank");
  };

  window.addEventListener("resize", resize);
  canvas.addEventListener("pointerdown", onDown);
  canvas.addEventListener("pointermove", onMove);
  canvas.addEventListener("pointerup", onUp);
  canvas.addEventListener("pointercancel", onUp);

  resize();
  loadPair()
    .then(connectWs)
    .catch((err) => setStatus(String(err)));
})();
