(() => {
  const canvas = document.getElementById("board");
  const ctx = canvas.getContext("2d", { alpha: false });
  const overlay = document.getElementById("overlay");
  const octx = overlay.getContext("2d");
  const statusEl = document.getElementById("status");
  const zoomLabel = document.getElementById("zoom-label");
  const btnPan = document.getElementById("btn-pan");
  const btnPen = document.getElementById("btn-pen");
  const btnEraseStroke = document.getElementById("btn-erase-stroke");
  const btnErasePartial = document.getElementById("btn-erase-partial");
  const dockStyle = document.getElementById("dock-style");
  const dockEraser = document.getElementById("dock-eraser");
  const dockExport = document.getElementById("dock-export");
  const inkWidthInput = document.getElementById("ink-width");
  const inkWidthLabel = document.getElementById("ink-width-label");
  const eraserSizeInput = document.getElementById("eraser-size");
  const eraserSizeLabel = document.getElementById("eraser-size-label");
  const fileImageInput = document.getElementById("file-image");
  const btnRecord = document.getElementById("btn-record");

  let pair = null;
  let ws = null;
  let documentState = null;
  let currentStrokeId = null;
  let lastStrokeId = null;
  let pointBuffer = [];
  let flushTimer = null;
  const author = `web-${Math.random().toString(36).slice(2, 8)}`;

  const view = { x: 0, y: 0, scale: 1 };
  const MIN_SCALE = 0.1;
  const MAX_SCALE = 8;
  const ZOOM_STEP = 1.15;

  /** @type {"pen"|"erase-stroke"|"erase-partial"} */
  let tool = "pen";
  let toolBeforeEraserTip = "pen";
  let eraserTipActive = false;

  /** @type {"pen"|"fountain"|"chalk"} */
  let inkKind = "pen";
  let inkTip = "round";
  let inkColor = "#000000";
  let inkWidth = 2.5;
  let pageBackground = "#fafaf7";
  let styleDockOpen = false;
  let eraserDockOpen = false;
  let exportDockOpen = false;
  const imageElCache = new Map();
  let mediaRecorder = null;
  let recordChunks = [];
  let recording = false;
  let selectedImageId = null;
  let imageGesture = null;
  let imagePress = null;
  const MIN_IMAGE_SIZE = 24;
  const IMAGE_HANDLES = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];
  const IMAGE_CORNER_HANDLES = new Set(["nw", "ne", "se", "sw"]);
  const LONG_PRESS_MS = 550;
  const LONG_PRESS_MOVE_PX = 10;

  let panMode = false;
  let spaceHeld = false;
  let isPanning = false;
  let panLast = null;
  let dpr = 1;
  const MAX_DPR = 1.5;
  let eraserCursor = null;
  let redrawPending = false;
  let overlayPending = false;
  let provisionalDraw = null;
  let lastZoomText = "";
  let livePoints = null; // open-stroke preview without realloc each move

  let eraserRadiusWorld = 14;
  const ERASER_STEP_RATIO = 0.45;
  const ERASER_MAX_SEG_STAMPS = 24;
  const ERASER_ADOPT_RATIO = 3.5;
  function eraserStep() {
    return eraserRadiusWorld * ERASER_STEP_RATIO;
  }
  function eraserAdoptRadius() {
    return eraserRadiusWorld * ERASER_ADOPT_RATIO;
  }
  const MIN_POINT_DIST = 1.25;
  const SPATIAL_CELL = 48;
  /** high | medium — stamped into perf samples for A/B cuts */
  let OPT_TIER = "medium";
  let USE_SPATIAL = true;
  let USE_DECIMATE = true;
  const erasedStrokeIds = new Set();
  const pendingSyncOps = [];

  /**
   * @type {null | {
   *   originals: Map<string, any>,
   *   alive: Map<string, Uint8Array>,
   *   runs: Map<string, any[]>,
   *   touched: Set<string>,
   *   lastX: number,
   *   lastY: number
   * }}
   */
  let partialSession = null;

  const inkLayer = document.createElement("canvas");
  const inkCtx = inkLayer.getContext("2d");
  const gridLayer = document.createElement("canvas");
  const gridCtx = gridLayer.getContext("2d");
  let inkDirty = true;
  let inkViewKey = "";
  let inkBake = { x: 0, y: 0, scale: 1 };
  let gridDirty = true;
  let gridViewKey = "";
  let gridBake = { x: 0, y: 0, scale: 1 };
  let docRevision = 0;
  let spatialIndex = null;
  let spatialRev = -1;

  const pointers = new Map();
  let pinch = null;

  const perfHud = document.getElementById("perf-hud");
  const btnPerf = document.getElementById("btn-perf");
  const btnPerfExport = document.getElementById("btn-perf-export");
  const PERF_WINDOW = 120;
  const PERF_HISTORY = 180; // ~3 min at 1 Hz
  const PERF_TICK_MS = 1000;
  const PERF_POST_EVERY = 5; // seconds between server posts
  const PERF_LS_KEY = "apeSketch.perf.history.v1";

  const Perf = {
    // Continuous collection is always on; HUD is optional.
    hud: new URLSearchParams(location.search).has("perf"),
    monitor: true,
    fps: 0,
    _fpsFrames: 0,
    _fpsLast: performance.now(),
    _fpsRaf: 0,
    _tickTimer: 0,
    _postClock: 0,
    room: null,
    history: [],
    serverSummary: null,
    samples: {
      redraw_ms: [],
      stamp_ms: [],
      commit_ms: [],
      emit_ms: [],
      frame_ms: [],
    },
    counters: {
      stamps: 0,
      commits: 0,
      emits: 0,
      redraws: 0,
    },
    lastGesture: null,
    mark(name, ms) {
      const arr = this.samples[name];
      if (!arr) return;
      arr.push(ms);
      if (arr.length > PERF_WINDOW) arr.splice(0, arr.length - PERF_WINDOW);
    },
    stats(name) {
      const arr = this.samples[name];
      if (!arr || !arr.length) return { n: 0, avg: 0, p95: 0, last: 0 };
      const sorted = arr.slice().sort((a, b) => a - b);
      const sum = sorted.reduce((a, b) => a + b, 0);
      const idx = Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95));
      return {
        n: sorted.length,
        avg: sum / sorted.length,
        p95: sorted[idx],
        last: arr[arr.length - 1],
      };
    },
    scene() {
      const page = documentState && documentState.pages && documentState.pages.p0;
      if (!page) return { strokes: 0, points: 0 };
      let points = 0;
      for (const sid of page.stroke_order || []) {
        const s = page.strokes[sid];
        if (s && s.points) points += s.points.length;
      }
      return { strokes: (page.stroke_order || []).length, points };
    },
    snapshot() {
      const scene = this.scene();
      return {
        t: new Date().toISOString(),
        source: "board",
        opt_tier: OPT_TIER,
        room: this.room,
        fps: this.fps,
        scene,
        pending_sync_ops: pendingSyncOps.length,
        partial_active: Boolean(partialSession),
        tool,
        scale: view.scale,
        counters: { ...this.counters },
        timings: {
          redraw_ms: this.stats("redraw_ms"),
          stamp_ms: this.stats("stamp_ms"),
          commit_ms: this.stats("commit_ms"),
          emit_ms: this.stats("emit_ms"),
          frame_ms: this.stats("frame_ms"),
        },
        last_gesture: this.lastGesture,
      };
    },
    loadHistory() {
      try {
        const raw = localStorage.getItem(PERF_LS_KEY);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) this.history = parsed.slice(-PERF_HISTORY);
      } catch (_) {}
    },
    saveHistory() {
      try {
        localStorage.setItem(PERF_LS_KEY, JSON.stringify(this.history.slice(-PERF_HISTORY)));
      } catch (_) {}
    },
    trend(key) {
      const vals = this.history
        .map((row) => {
          const block = row.timings && row.timings[key];
          return block ? block.avg : null;
        })
        .filter((v) => typeof v === "number");
      if (vals.length < 2) return "n/a";
      const a = vals[vals.length - 1];
      const b = vals[Math.max(0, vals.length - 31)];
      const d = a - b;
      const sign = d > 0.01 ? "+" : d < -0.01 ? "" : "±";
      return `${sign}${d.toFixed(2)} vs ~30s`;
    },
    renderHud() {
      if (!this.hud) return;
      const s = this.snapshot();
      const fmt = (st) =>
        st.n ? `${st.avg.toFixed(2)} / p95 ${st.p95.toFixed(2)} (n=${st.n})` : "—";
      const sum = this.serverSummary;
      perfHud.textContent = [
        "apeSketch perf · continuous",
        `fps           ${s.fps.toFixed(0)}`,
        `strokes/pts   ${s.scene.strokes} / ${s.scene.points}`,
        `redraw_ms     ${fmt(s.timings.redraw_ms)}  ${this.trend("redraw_ms")}`,
        `stamp_ms      ${fmt(s.timings.stamp_ms)}  ${this.trend("stamp_ms")}`,
        `commit_ms     ${fmt(s.timings.commit_ms)}  ${this.trend("commit_ms")}`,
        `emit_ms       ${fmt(s.timings.emit_ms)}`,
        `frame_ms      ${fmt(s.timings.frame_ms)}`,
        `history       ${this.history.length} samples (1 Hz)`,
        `sync_queue    ${s.pending_sync_ops}`,
        `stamps/commits ${s.counters.stamps} / ${s.counters.commits}`,
        s.last_gesture
          ? `last_partial  stamps=${s.last_gesture.stamps} commit=${s.last_gesture.commit_ms.toFixed(2)}ms ops=${s.last_gesture.ops}`
          : "last_partial  —",
        sum
          ? `server day    n=${sum.sample_count} redraw≈${(sum.redraw_ms_avg || 0).toFixed(2)} stamp≈${(sum.stamp_ms_avg || 0).toFixed(2)}`
          : "server day    —",
      ].join("\n");
    },
    setHud(on) {
      this.hud = on;
      perfHud.classList.toggle("on", on);
      btnPerf.classList.toggle("active", on);
      btnPerfExport.hidden = !on;
      if (on) {
        this.startFpsLoop();
        this.renderHud();
      } else {
        this.stopFpsLoop();
      }
    },
    startFpsLoop() {
      if (this._fpsRaf) return;
      const tick = (now) => {
        this._fpsFrames += 1;
        if (now - this._fpsLast >= 500) {
          this.fps = (this._fpsFrames * 1000) / (now - this._fpsLast);
          this._fpsFrames = 0;
          this._fpsLast = now;
        }
        // Only keep the rAF heartbeat while the HUD is open; otherwise sample
        // fps from redraw cadence to avoid a permanent second animation loop.
        if (this.hud) this._fpsRaf = requestAnimationFrame(tick);
        else this._fpsRaf = 0;
      };
      this._fpsRaf = requestAnimationFrame(tick);
    },
    stopFpsLoop() {
      if (this._fpsRaf) cancelAnimationFrame(this._fpsRaf);
      this._fpsRaf = 0;
    },
    async refreshServerSummary() {
      try {
        const res = await fetch("/api/perf/summary");
        if (!res.ok) return;
        this.serverSummary = await res.json();
      } catch (_) {}
    },
    async postSample(sample) {
      try {
        await fetch("/api/perf", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(sample),
        });
      } catch (_) {}
    },
    tick() {
      if (!this.monitor) return;
      const sample = this.snapshot();
      this.history.push(sample);
      if (this.history.length > PERF_HISTORY) {
        this.history.splice(0, this.history.length - PERF_HISTORY);
      }
      this.saveHistory();
      this._postClock += 1;
      if (this._postClock >= PERF_POST_EVERY) {
        this._postClock = 0;
        this.postSample(sample);
        this.refreshServerSummary();
      }
      if (this.hud) this.renderHud();
    },
    start() {
      this.loadHistory();
      if (this._tickTimer) clearInterval(this._tickTimer);
      this._tickTimer = setInterval(() => this.tick(), PERF_TICK_MS);
      this.refreshServerSummary();
      this.setHud(this.hud);
    },
  };

  function clampScale(s) {
    return Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));
  }

  function setTool(next) {
    tool = next;
    btnPen.classList.toggle("active", tool === "pen");
    btnEraseStroke.classList.toggle("active", tool === "erase-stroke");
    btnErasePartial.classList.toggle("active", tool === "erase-partial");
    updateCursor();
    scheduleOverlay();
  }

  function setStyleDockOpen(open) {
    styleDockOpen = !!open;
    if (!dockStyle) return;
    dockStyle.classList.toggle("open", styleDockOpen);
    if (styleDockOpen) {
      dockStyle.removeAttribute("hidden");
      setEraserDockOpen(false);
      setExportDockOpen(false);
    } else {
      dockStyle.setAttribute("hidden", "");
    }
  }

  function toggleStyleDock() {
    setStyleDockOpen(!styleDockOpen);
  }

  function setEraserDockOpen(open) {
    eraserDockOpen = !!open;
    if (!dockEraser) return;
    dockEraser.classList.toggle("open", eraserDockOpen);
    if (eraserDockOpen) {
      dockEraser.removeAttribute("hidden");
      setStyleDockOpen(false);
      setExportDockOpen(false);
    } else {
      dockEraser.setAttribute("hidden", "");
    }
  }

  function toggleEraserDock() {
    setEraserDockOpen(!eraserDockOpen);
  }

  function setExportDockOpen(open) {
    exportDockOpen = !!open;
    if (!dockExport) return;
    dockExport.classList.toggle("open", exportDockOpen);
    if (exportDockOpen) {
      dockExport.removeAttribute("hidden");
      setStyleDockOpen(false);
      setEraserDockOpen(false);
    } else {
      dockExport.setAttribute("hidden", "");
    }
  }

  function toggleExportDock() {
    setExportDockOpen(!exportDockOpen);
  }

  function syncInkKindButtons() {
    for (const btn of document.querySelectorAll(".pen-kind")) {
      btn.classList.toggle("active", btn.getAttribute("data-kind") === inkKind);
    }
  }

  function syncTipButtons() {
    for (const btn of document.querySelectorAll(".tip-shape")) {
      btn.classList.toggle("active", btn.getAttribute("data-tip") === inkTip);
    }
  }

  function syncColorButtons() {
    for (const btn of document.querySelectorAll("#color-swatches .swatch")) {
      btn.classList.toggle("active", btn.getAttribute("data-color") === inkColor);
    }
  }

  function syncBgButtons() {
    const bg = normalizeHex(pageBackground);
    for (const btn of document.querySelectorAll(".bg-swatch")) {
      btn.classList.toggle("active", normalizeHex(btn.getAttribute("data-bg")) === bg);
    }
  }

  function syncSizeControls() {
    if (inkWidthInput) inkWidthInput.value = String(inkWidth);
    if (inkWidthLabel) inkWidthLabel.textContent = String(inkWidth);
    if (eraserSizeInput) eraserSizeInput.value = String(eraserRadiusWorld);
    if (eraserSizeLabel) eraserSizeLabel.textContent = String(eraserRadiusWorld);
  }

  function normalizeHex(color) {
    const raw = String(color || "").trim().toLowerCase();
    if (/^#[0-9a-f]{6}$/.test(raw)) return raw;
    if (/^[0-9a-f]{6}$/.test(raw)) return `#${raw}`;
    return raw;
  }

  function applyChromeTheme(color) {
    const hex = normalizeHex(color) || "#fafaf7";
    document.documentElement.style.setProperty("--paper", hex);
    document.body.classList.toggle("theme-dark", isDarkBackground(hex));
  }

  function applyPageBackground(color) {
    const hex = normalizeHex(color) || "#fafaf7";
    pageBackground = hex;
    const page =
      documentState &&
      documentState.pages &&
      documentState.pages[documentState.active_page_id || "p0"];
    if (page) page.background = hex;
    syncBgButtons();
    applyChromeTheme(hex);
    invalidateGrid();
    invalidateInk();
  }

  function setInkKind(kind) {
    inkKind = kind;
    if (tool !== "pen") setTool("pen");
    syncInkKindButtons();
  }

  function setInkTip(tip) {
    inkTip = tip === "square" || tip === "chisel" ? tip : "round";
    if (tool !== "pen") setTool("pen");
    syncTipButtons();
  }

  function setInkWidth(width) {
    const next = Math.min(24, Math.max(1, Number(width) || 2.5));
    inkWidth = Math.round(next * 2) / 2;
    syncSizeControls();
  }

  function setEraserRadius(radius) {
    const next = Math.min(48, Math.max(4, Math.round(Number(radius) || 14)));
    eraserRadiusWorld = next;
    syncSizeControls();
    scheduleOverlay();
  }

  function setInkColor(color) {
    inkColor = color;
    if (tool !== "pen") setTool("pen");
    syncColorButtons();
  }

  function setBackground(color) {
    const hex = normalizeHex(color) || "#fafaf7";
    sendOp({ op: "set_background", color: hex, page_id: "p0" });
  }

  function updateCursor() {
    const erasing = tool === "erase-stroke" || tool === "erase-partial";
    canvas.classList.toggle("panning", panMode || spaceHeld || isPanning);
    canvas.classList.toggle("dragging", isPanning);
    canvas.classList.toggle("erasing", erasing && !panMode && !spaceHeld && !isPanning);
  }

  function isStylusEraser(ev) {
    if (ev.pointerType !== "pen") return false;
    if (ev.button === 5) return true;
    if (ev.buttons & 32) return true;
    return false;
  }

  function scheduleRedraw(provisional) {
    if (provisional !== undefined) provisionalDraw = provisional;
    if (redrawPending) return;
    redrawPending = true;
    const scheduledAt = performance.now();
    requestAnimationFrame(() => {
      redrawPending = false;
      const frameStart = performance.now();
      Perf.mark("frame_ms", frameStart - scheduledAt);
      redraw(provisionalDraw);
      provisionalDraw = null;
      drawOverlay();
      if (Perf.hud) Perf.renderHud();
    });
  }

  function scheduleOverlay() {
    if (overlayPending || redrawPending) return;
    overlayPending = true;
    requestAnimationFrame(() => {
      overlayPending = false;
      if (redrawPending) return;
      drawOverlay();
    });
  }

  function resize() {
    dpr = Math.min(MAX_DPR, window.devicePixelRatio || 1);
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const bw = Math.floor(w * dpr);
    const bh = Math.floor(h * dpr);
    canvas.width = bw;
    canvas.height = bh;
    overlay.width = bw;
    overlay.height = bh;
    invalidateInk();
    invalidateGrid();
    scheduleRedraw();
  }

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function screenToWorld(sx, sy) {
    return {
      x: (sx - view.x) / view.scale,
      y: (sy - view.y) / view.scale,
    };
  }

  function pointerScreen(ev) {
    const rect = canvas.getBoundingClientRect();
    return {
      sx: ev.clientX - rect.left,
      sy: ev.clientY - rect.top,
    };
  }

  function pointerWorld(ev) {
    const { sx, sy } = pointerScreen(ev);
    const w = screenToWorld(sx, sy);
    return {
      x: w.x,
      y: w.y,
      t: ev.timeStamp || performance.now(),
      pressure: ev.pressure > 0 ? ev.pressure : 0.5,
      sx,
      sy,
    };
  }

  function applyViewTransform() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.translate(view.x, view.y);
    ctx.scale(view.scale, view.scale);
  }

  function viewportCenterWorld() {
    return screenToWorld(canvas.clientWidth / 2, canvas.clientHeight / 2);
  }

  function fitImageSize(naturalW, naturalH, maxSide) {
    const cap = maxSide || 640;
    const scale = Math.min(1, cap / Math.max(naturalW, naturalH, 1));
    return {
      width: Math.max(1, naturalW * scale),
      height: Math.max(1, naturalH * scale),
    };
  }

  function ensureImageAsset(assetId) {
    if (!assetId) return null;
    let img = imageElCache.get(assetId);
    if (img) return img;
    img = new Image();
    img.decoding = "async";
    img.onload = () => scheduleRedraw();
    img.onerror = () => setStatus(`asset missing ${assetId}`);
    img.src = `/api/asset/${encodeURIComponent(assetId)}`;
    imageElCache.set(assetId, img);
    return img;
  }

  function drawPageImages(page) {
    if (!page || !page.image_order || !page.images) return;
    for (const iid of page.image_order) {
      const image = page.images[iid];
      if (!image) continue;
      const el = ensureImageAsset(image.asset_id);
      if (!el || !el.complete || !el.naturalWidth) continue;
      ctx.drawImage(el, image.x, image.y, image.width, image.height);
    }
  }

  function getPage() {
    return documentState && documentState.pages
      ? documentState.pages[documentState.active_page_id || "p0"]
      : null;
  }

  function getImage(imageId) {
    const page = getPage();
    return page && page.images ? page.images[imageId] : null;
  }

  function setSelectedImage(imageId) {
    selectedImageId = imageId || null;
    scheduleOverlay();
  }

  function imageHandlePoints(image) {
    const x = image.x;
    const y = image.y;
    const w = image.width;
    const h = image.height;
    return {
      nw: { x, y },
      n: { x: x + w / 2, y },
      ne: { x: x + w, y },
      e: { x: x + w, y: y + h / 2 },
      se: { x: x + w, y: y + h },
      s: { x: x + w / 2, y: y + h },
      sw: { x, y: y + h },
      w: { x, y: y + h / 2 },
    };
  }

  function handleHitRadius() {
    return Math.max(10 / view.scale, 8);
  }

  function hitImageHandle(image, x, y) {
    const r = handleHitRadius();
    const points = imageHandlePoints(image);
    for (const id of IMAGE_HANDLES) {
      const p = points[id];
      if (Math.abs(x - p.x) <= r && Math.abs(y - p.y) <= r) return id;
    }
    return null;
  }

  function pointInImage(image, x, y) {
    return (
      x >= image.x &&
      x <= image.x + image.width &&
      y >= image.y &&
      y <= image.y + image.height
    );
  }

  function hitTopImageAt(x, y) {
    const page = getPage();
    if (!page || !page.image_order) return null;
    for (let i = page.image_order.length - 1; i >= 0; i--) {
      const iid = page.image_order[i];
      const image = page.images && page.images[iid];
      if (image && pointInImage(image, x, y)) return iid;
    }
    return null;
  }

  function clampImageBox(box) {
    let { x, y, width, height } = box;
    if (width < MIN_IMAGE_SIZE) width = MIN_IMAGE_SIZE;
    if (height < MIN_IMAGE_SIZE) height = MIN_IMAGE_SIZE;
    return { x, y, width, height };
  }

  function resizeFromHandle(orig, handle, dx, dy, keepAspect) {
    const aspect = orig.width / Math.max(orig.height, 1e-6);
    const isCorner = IMAGE_CORNER_HANDLES.has(handle);
    if (keepAspect && isCorner) {
      let x = orig.x;
      let y = orig.y;
      let w = orig.width;
      let h = orig.height;
      // Project drag onto the diagonal that preserves aspect.
      if (handle === "se") {
        const candW = Math.max(MIN_IMAGE_SIZE, orig.width + dx);
        const candH = Math.max(MIN_IMAGE_SIZE, orig.height + dy);
        if (candW / aspect >= candH) {
          w = candW;
          h = candW / aspect;
        } else {
          h = candH;
          w = candH * aspect;
        }
      } else if (handle === "nw") {
        const candW = Math.max(MIN_IMAGE_SIZE, orig.width - dx);
        const candH = Math.max(MIN_IMAGE_SIZE, orig.height - dy);
        if (candW / aspect >= candH) {
          w = candW;
          h = candW / aspect;
        } else {
          h = candH;
          w = candH * aspect;
        }
        x = orig.x + orig.width - w;
        y = orig.y + orig.height - h;
      } else if (handle === "ne") {
        const candW = Math.max(MIN_IMAGE_SIZE, orig.width + dx);
        const candH = Math.max(MIN_IMAGE_SIZE, orig.height - dy);
        if (candW / aspect >= candH) {
          w = candW;
          h = candW / aspect;
        } else {
          h = candH;
          w = candH * aspect;
        }
        y = orig.y + orig.height - h;
      } else if (handle === "sw") {
        const candW = Math.max(MIN_IMAGE_SIZE, orig.width - dx);
        const candH = Math.max(MIN_IMAGE_SIZE, orig.height + dy);
        if (candW / aspect >= candH) {
          w = candW;
          h = candW / aspect;
        } else {
          h = candH;
          w = candH * aspect;
        }
        x = orig.x + orig.width - w;
      }
      return clampImageBox({ x, y, width: w, height: h });
    }

    let x = orig.x;
    let y = orig.y;
    let w = orig.width;
    let h = orig.height;
    if (handle.indexOf("w") !== -1) {
      x += dx;
      w -= dx;
    }
    if (handle.indexOf("e") !== -1) w += dx;
    if (handle.indexOf("n") !== -1) {
      y += dy;
      h -= dy;
    }
    if (handle.indexOf("s") !== -1) h += dy;

    if (w < MIN_IMAGE_SIZE) {
      if (handle.indexOf("w") !== -1) x = orig.x + orig.width - MIN_IMAGE_SIZE;
      w = MIN_IMAGE_SIZE;
    }
    if (h < MIN_IMAGE_SIZE) {
      if (handle.indexOf("n") !== -1) y = orig.y + orig.height - MIN_IMAGE_SIZE;
      h = MIN_IMAGE_SIZE;
    }
    return clampImageBox({ x, y, width: w, height: h });
  }

  function imageLockIconRect(image) {
    const size = Math.max(22 / view.scale, 16);
    const pad = Math.max(8 / view.scale, 6);
    return {
      x: image.x + image.width - size - pad,
      y: image.y + pad,
      size,
    };
  }

  function hitImageLockIcon(image, x, y) {
    const r = imageLockIconRect(image);
    return x >= r.x && x <= r.x + r.size && y >= r.y && y <= r.y + r.size;
  }

  function drawLockIcon(image) {
    const r = imageLockIconRect(image);
    const s = r.size;
    const locked = !!image.locked;
    octx.save();
    octx.fillStyle = locked ? "rgba(47, 93, 80, 0.95)" : "rgba(252, 251, 247, 0.95)";
    octx.strokeStyle = "rgba(47, 93, 80, 0.95)";
    octx.lineWidth = 1.4 / view.scale;
    const rad = Math.max(3 / view.scale, 2);
    octx.beginPath();
    octx.moveTo(r.x + rad, r.y);
    octx.arcTo(r.x + s, r.y, r.x + s, r.y + s, rad);
    octx.arcTo(r.x + s, r.y + s, r.x, r.y + s, rad);
    octx.arcTo(r.x, r.y + s, r.x, r.y, rad);
    octx.arcTo(r.x, r.y, r.x + s, r.y, rad);
    octx.closePath();
    octx.fill();
    octx.stroke();

    const cx = r.x + s / 2;
    const cy = r.y + s / 2;
    const bodyW = s * 0.38;
    const bodyH = s * 0.28;
    const bodyY = cy - bodyH * 0.1;
    octx.fillStyle = locked ? "rgba(252, 251, 247, 0.95)" : "rgba(47, 93, 80, 0.95)";
    octx.strokeStyle = octx.fillStyle;
    octx.lineWidth = Math.max(1.6 / view.scale, 1.1);
    octx.beginPath();
    octx.rect(cx - bodyW / 2, bodyY, bodyW, bodyH);
    octx.fill();
    octx.beginPath();
    octx.arc(cx, bodyY, bodyW * 0.42, Math.PI, 0, false);
    if (!locked) {
      // Open shackle: leave a gap on the right.
      octx.moveTo(cx + bodyW * 0.42, bodyY);
      octx.lineTo(cx + bodyW * 0.42, bodyY - bodyH * 0.15);
    }
    octx.stroke();
    octx.restore();
  }

  function clearImagePress() {
    if (imagePress && imagePress.timer) clearTimeout(imagePress.timer);
    imagePress = null;
  }

  function toggleImageLock(imageId) {
    const image = getImage(imageId);
    if (!image) return;
    sendOp({
      op: "set_image_lock",
      image_id: imageId,
      locked: !image.locked,
      page_id: "p0",
    });
    setStatus(image.locked ? "image unlocked" : "image locked");
  }

  function beginStrokeAt(p) {
    currentStrokeId = `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    lastStrokeId = currentStrokeId;
    sendOp({
      op: "begin_stroke",
      stroke_id: currentStrokeId,
      author,
      page_id: "p0",
      style: {
        color: inkColor,
        width: inkKind === "chalk" ? inkWidth * 1.35 : inkKind === "fountain" ? inkWidth * 1.1 : inkWidth,
        kind: inkKind,
        tip: inkTip,
      },
    });
    const first = [p.x, p.y, p.t, p.pressure];
    pointBuffer.push(first);
    livePoints = [first];
    scheduleRedraw({ strokeId: currentStrokeId, points: livePoints });
    if (flushTimer) clearInterval(flushTimer);
    flushTimer = setInterval(flushPoints, 32);
  }

  function applyImageBoxLocal(imageId, box) {
    const image = getImage(imageId);
    if (!image || image.locked) return;
    image.x = box.x;
    image.y = box.y;
    image.width = box.width;
    image.height = box.height;
  }

  function commitImageTransform(imageId) {
    const image = getImage(imageId);
    if (!image || image.locked) return;
    sendOp({
      op: "transform_image",
      image_id: imageId,
      x: image.x,
      y: image.y,
      width: image.width,
      height: image.height,
      page_id: "p0",
    });
  }

  function cursorForImageHandle(handle) {
    if (handle === "n" || handle === "s") return "ns-resize";
    if (handle === "e" || handle === "w") return "ew-resize";
    if (handle === "ne" || handle === "sw") return "nesw-resize";
    if (handle === "nw" || handle === "se") return "nwse-resize";
    return "move";
  }

  function updateImageHoverCursor(x, y) {
    if (tool !== "pen" || panMode || spaceHeld) return;
    const selected = selectedImageId ? getImage(selectedImageId) : null;
    if (selected) {
      if (hitImageLockIcon(selected, x, y)) {
        canvas.style.cursor = "pointer";
        return;
      }
      if (!selected.locked) {
        const handle = hitImageHandle(selected, x, y);
        if (handle) {
          canvas.style.cursor = cursorForImageHandle(handle);
          return;
        }
        if (pointInImage(selected, x, y)) {
          canvas.style.cursor = "move";
          return;
        }
      } else if (pointInImage(selected, x, y)) {
        canvas.style.cursor = "default";
        return;
      }
    }
    if (hitTopImageAt(x, y)) {
      canvas.style.cursor = "pointer";
      return;
    }
    canvas.style.cursor = "";
  }

  function bytesToBase64(bytes) {
    const chunk = 0x8000;
    let binary = "";
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  function sniffImageMime(bytes) {
    if (!bytes || bytes.length < 12) return "";
    if (bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) {
      return "image/png";
    }
    if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
      return "image/jpeg";
    }
    if (bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46) {
      return "image/gif";
    }
    if (
      bytes[0] === 0x52 &&
      bytes[1] === 0x49 &&
      bytes[2] === 0x46 &&
      bytes[3] === 0x46 &&
      bytes[8] === 0x57 &&
      bytes[9] === 0x45 &&
      bytes[10] === 0x42 &&
      bytes[11] === 0x50
    ) {
      return "image/webp";
    }
    return "";
  }

  function normalizeImageBlob(blob, preferredMime) {
    const mime =
      (preferredMime && preferredMime.startsWith("image/") && preferredMime) ||
      (blob && blob.type && blob.type.startsWith("image/") && blob.type) ||
      "image/png";
    if (blob && blob.type === mime) return blob;
    return new Blob([blob], { type: mime });
  }

  async function uploadAssetBlob(blob, preferredMime) {
    const normalized = normalizeImageBlob(blob, preferredMime);
    const buf = await normalized.arrayBuffer();
    const bytes = new Uint8Array(buf);
    const sniffed = sniffImageMime(bytes);
    const mime = sniffed || normalized.type || "image/png";
    if (!bytes.length) throw new Error("empty image");
    const data_base64 = bytesToBase64(bytes);
    const res = await fetch("/api/asset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mime, data_base64 }),
    });
    let payload = null;
    try {
      payload = await res.json();
    } catch (_) {
      throw new Error(
        res.ok
          ? "invalid asset response"
          : `upload failed (${res.status}) — restart apeSketch host`
      );
    }
    if (!res.ok) throw new Error((payload && payload.error) || `upload failed (${res.status})`);
    return payload;
  }

  function loadImageElement(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("failed to decode image"));
      img.src = url;
    });
  }

  async function placeImageFromBlob(blob, preferredMime) {
    const normalized = normalizeImageBlob(blob, preferredMime);
    const uploaded = await uploadAssetBlob(normalized, preferredMime);
    ensureImageAsset(uploaded.asset_id);
    const objectUrl = URL.createObjectURL(normalized);
    let natural;
    try {
      const decoded = await loadImageElement(objectUrl);
      natural = fitImageSize(decoded.naturalWidth, decoded.naturalHeight, 720);
    } finally {
      URL.revokeObjectURL(objectUrl);
    }
    const center = viewportCenterWorld();
    const imageId = `img-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    sendOp({
      op: "add_image",
      image_id: imageId,
      asset_id: uploaded.asset_id,
      x: center.x - natural.width / 2,
      y: center.y - natural.height / 2,
      width: natural.width,
      height: natural.height,
      author,
      page_id: "p0",
    });
    setSelectedImage(imageId);
    setStatus(`image added · ${uploaded.mime}`);
  }

  async function importImageBlobs(entries) {
    const list = (entries || [])
      .map((entry) => {
        if (!entry) return null;
        if (entry instanceof Blob) return { blob: entry, mime: entry.type || "" };
        if (entry.blob instanceof Blob) {
          return { blob: entry.blob, mime: entry.mime || entry.blob.type || "" };
        }
        return null;
      })
      .filter(Boolean);
    if (!list.length) {
      setStatus("no image on clipboard");
      return;
    }
    for (const item of list) {
      try {
        await placeImageFromBlob(item.blob, item.mime);
      } catch (err) {
        setStatus(String(err.message || err));
      }
    }
  }

  async function importImageFiles(fileList) {
    const files = [...(fileList || [])].filter(
      (f) => f && (!f.type || f.type.startsWith("image/"))
    );
    if (!files.length) {
      setStatus("no image files");
      return;
    }
    await importImageBlobs(files.map((f) => ({ blob: f, mime: f.type || "" })));
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportViewportPng() {
    canvas.toBlob((blob) => {
      if (!blob) {
        setStatus("png export failed");
        return;
      }
      downloadBlob(blob, `apesketch-${Date.now()}.png`);
      setStatus("exported PNG");
    }, "image/png");
  }

  async function exportFromApi(path, filename) {
    const res = await fetch(path);
    if (!res.ok) {
      const body = await res.text();
      throw new Error(body || `export failed (${res.status})`);
    }
    const blob = await res.blob();
    downloadBlob(blob, filename);
  }

  function syncRecordButton() {
    if (!btnRecord) return;
    btnRecord.textContent = recording ? "Stop" : "Start";
    btnRecord.classList.toggle("recording", recording);
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
  }

  function startRecording() {
    if (!canvas.captureStream) {
      setStatus("recording not supported here");
      return;
    }
    recordChunks = [];
    const stream = canvas.captureStream(30);
    let mime = "video/webm;codecs=vp9";
    if (typeof MediaRecorder === "undefined") {
      setStatus("MediaRecorder unavailable");
      return;
    }
    if (!MediaRecorder.isTypeSupported(mime)) mime = "video/webm";
    if (!MediaRecorder.isTypeSupported(mime)) {
      setStatus("no MediaRecorder mime support");
      return;
    }
    mediaRecorder = new MediaRecorder(stream, { mimeType: mime });
    mediaRecorder.ondataavailable = (ev) => {
      if (ev.data && ev.data.size) recordChunks.push(ev.data);
    };
    mediaRecorder.onstop = () => {
      recording = false;
      syncRecordButton();
      const blob = new Blob(recordChunks, { type: mime });
      recordChunks = [];
      if (blob.size) {
        downloadBlob(blob, `apesketch-${Date.now()}.webm`);
        setStatus("recording saved");
      } else {
        setStatus("empty recording");
      }
      mediaRecorder = null;
    };
    mediaRecorder.start(500);
    recording = true;
    syncRecordButton();
    setStatus("recording…");
  }

  function toggleRecording() {
    if (recording) stopRecording();
    else startRecording();
  }

  function niceGridStep(worldPxTarget) {
    const exp = Math.floor(Math.log10(Math.max(worldPxTarget, 1e-6)));
    const base = Math.pow(10, exp);
    const candidates = [base, 2 * base, 5 * base, 10 * base];
    let best = candidates[0];
    let bestDist = Infinity;
    for (const c of candidates) {
      const d = Math.abs(c - worldPxTarget);
      if (d < bestDist) {
        best = c;
        bestDist = d;
      }
    }
    return best;
  }

  function isDarkBackground(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ""));
    if (!m) return false;
    const n = parseInt(m[1], 16);
    const r = (n >> 16) & 255;
    const g = (n >> 8) & 255;
    const b = n & 255;
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 110;
  }

  function drawGrid(screenW, screenH) {
    const minor = niceGridStep(40 / view.scale);
    const major = minor * 5;
    const left = screenToWorld(0, 0).x;
    const top = screenToWorld(0, 0).y;
    const right = screenToWorld(screenW, screenH).x;
    const bottom = screenToWorld(screenW, screenH).y;
    const startX = Math.floor(left / minor) * minor;
    const startY = Math.floor(top / minor) * minor;
    const dark = isDarkBackground(pageBackground);
    const minorStroke = dark ? "rgba(230, 230, 220, 0.07)" : "rgba(80, 70, 55, 0.08)";
    const majorStroke = dark ? "rgba(230, 230, 220, 0.14)" : "rgba(80, 70, 55, 0.18)";
    const axisStroke = dark ? "rgba(180, 210, 190, 0.28)" : "rgba(47, 93, 80, 0.35)";

    ctx.save();
    applyViewTransform();
    ctx.lineWidth = 1 / view.scale;
    for (let x = startX; x <= right; x += minor) {
      const isMajor = Math.abs(x / major - Math.round(x / major)) < 1e-9;
      ctx.strokeStyle = isMajor ? majorStroke : minorStroke;
      ctx.beginPath();
      ctx.moveTo(x, top);
      ctx.lineTo(x, bottom);
      ctx.stroke();
    }
    for (let y = startY; y <= bottom; y += minor) {
      const isMajor = Math.abs(y / major - Math.round(y / major)) < 1e-9;
      ctx.strokeStyle = isMajor ? majorStroke : minorStroke;
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(right, y);
      ctx.stroke();
    }
    ctx.strokeStyle = axisStroke;
    ctx.beginPath();
    ctx.moveTo(0, top);
    ctx.lineTo(0, bottom);
    ctx.moveTo(left, 0);
    ctx.lineTo(right, 0);
    ctx.stroke();
    ctx.restore();
  }

  function strokeStyleOf(stroke) {
    return {
      color: (stroke.style && stroke.style.color) || "#111111",
      width: (stroke.style && stroke.style.width) || 2,
      kind: (stroke.style && stroke.style.kind) || "pen",
      tip: (stroke.style && stroke.style.tip) || "round",
    };
  }

  function xyOf(p) {
    return Array.isArray(p) ? { x: p[0], y: p[1] } : { x: p.x, y: p.y };
  }

  function pressureOf(p) {
    if (Array.isArray(p)) return p.length > 3 ? p[3] : 0.5;
    return typeof p.pressure === "number" ? p.pressure : 0.5;
  }

  function applyTipCaps(target, tip) {
    if (tip === "square") {
      target.lineCap = "square";
      target.lineJoin = "miter";
    } else if (tip === "chisel") {
      target.lineCap = "butt";
      target.lineJoin = "bevel";
    } else {
      target.lineCap = "round";
      target.lineJoin = "round";
    }
  }

  function drawStrokePoints(points, style, opts) {
    if (!points.length) return;
    const target = (opts && opts.ctx) || ctx;
    const fast = opts && opts.fast;
    const kind = fast ? "pen" : style.kind || "pen";
    const tip = style.tip || "round";
    if (kind === "fountain") {
      applyTipCaps(target, tip);
      target.strokeStyle = style.color;
      for (let i = 1; i < points.length; i++) {
        const a = xyOf(points[i - 1]);
        const b = xyOf(points[i]);
        const pressure = pressureOf(points[i]);
        target.beginPath();
        target.lineWidth = style.width * (0.45 + pressure * 1.8);
        target.globalAlpha = 0.92;
        target.moveTo(a.x, a.y);
        target.lineTo(b.x, b.y);
        target.stroke();
      }
      target.globalAlpha = 1;
      return;
    }
    if (kind === "chalk") {
      applyTipCaps(target, tip);
      target.strokeStyle = style.color;
      const passes = [
        { ox: 0, oy: 0, w: style.width * 1.7, a: 0.38 },
        { ox: 0.8, oy: -0.6, w: style.width * 1.1, a: 0.28 },
        { ox: -0.7, oy: 0.5, w: style.width * 0.9, a: 0.22 },
      ];
      for (const pass of passes) {
        target.beginPath();
        target.globalAlpha = pass.a;
        target.lineWidth = pass.w;
        for (let i = 0; i < points.length; i++) {
          const { x, y } = xyOf(points[i]);
          const jx = x + pass.ox + ((i % 3) - 1) * 0.35;
          const jy = y + pass.oy + (((i + 1) % 3) - 1) * 0.35;
          if (i === 0) target.moveTo(jx, jy);
          else target.lineTo(jx, jy);
        }
        target.stroke();
      }
      target.globalAlpha = 1;
      return;
    }
    if (tip === "chisel") {
      target.strokeStyle = style.color;
      target.globalAlpha = 1;
      applyTipCaps(target, "chisel");
      for (let i = 1; i < points.length; i++) {
        const a = xyOf(points[i - 1]);
        const b = xyOf(points[i]);
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const len = Math.hypot(dx, dy) || 1;
        const nx = (-dy / len) * style.width * 0.55;
        const ny = (dx / len) * style.width * 0.55;
        target.beginPath();
        target.lineWidth = style.width * 0.35;
        target.moveTo(a.x - nx, a.y - ny);
        target.lineTo(a.x + nx, a.y + ny);
        target.lineTo(b.x + nx, b.y + ny);
        target.lineTo(b.x - nx, b.y - ny);
        target.closePath();
        target.fillStyle = style.color;
        target.fill();
      }
      return;
    }
    target.beginPath();
    applyTipCaps(target, tip);
    target.strokeStyle = style.color;
    target.lineWidth = style.width;
    target.globalAlpha = 1;
    for (let i = 0; i < points.length; i++) {
      const { x, y } = xyOf(points[i]);
      if (i === 0) target.moveTo(x, y);
      else target.lineTo(x, y);
    }
    target.stroke();
  }

  function drawStroke(stroke, provisionalPoints, opts) {
    drawStrokePoints(provisionalPoints || stroke.points || [], strokeStyleOf(stroke), opts);
  }

  function runsFromAlive(points, alive) {
    const runs = [];
    let run = [];
    for (let i = 0; i < points.length; i++) {
      if (alive[i]) run.push(points[i]);
      else if (run.length) {
        if (run.length >= 2) runs.push(run);
        run = [];
      }
    }
    if (run.length >= 2) runs.push(run);
    return runs;
  }

  function cachedPartialRuns(sid, orig, alive) {
    let runs = partialSession.runs.get(sid);
    if (runs) return runs;
    runs = runsFromAlive(orig.points, alive);
    partialSession.runs.set(sid, runs);
    return runs;
  }

  function drawOverlay() {
    const screenW = overlay.clientWidth;
    const screenH = overlay.clientHeight;
    octx.setTransform(dpr, 0, 0, dpr, 0, 0);
    octx.clearRect(0, 0, screenW, screenH);
    const selected = selectedImageId ? getImage(selectedImageId) : null;
    if (!selected && !eraserCursor) return;
    octx.save();
    octx.translate(view.x, view.y);
    octx.scale(view.scale, view.scale);

    if (selected) {
      const hs = Math.max(7 / view.scale, 5);
      octx.strokeStyle = selected.locked
        ? "rgba(138, 59, 43, 0.9)"
        : "rgba(47, 93, 80, 0.95)";
      octx.fillStyle = "rgba(252, 251, 247, 0.95)";
      octx.lineWidth = 1.5 / view.scale;
      octx.setLineDash(selected.locked ? [6 / view.scale, 4 / view.scale] : []);
      octx.strokeRect(selected.x, selected.y, selected.width, selected.height);
      octx.setLineDash([]);
      if (!selected.locked) {
        const points = imageHandlePoints(selected);
        for (const id of IMAGE_HANDLES) {
          const p = points[id];
          octx.fillRect(p.x - hs / 2, p.y - hs / 2, hs, hs);
          octx.strokeStyle = "rgba(47, 93, 80, 0.95)";
          octx.strokeRect(p.x - hs / 2, p.y - hs / 2, hs, hs);
        }
      }
      drawLockIcon(selected);
    }

    if (eraserCursor) {
      octx.beginPath();
      octx.arc(eraserCursor.x, eraserCursor.y, eraserRadiusWorld, 0, Math.PI * 2);
      octx.strokeStyle = "rgba(160, 40, 40, 0.7)";
      octx.fillStyle = "rgba(160, 40, 40, 0.08)";
      octx.lineWidth = 1.5 / view.scale;
      octx.fill();
      octx.stroke();
    }
    octx.restore();
  }

  function updateZoomLabel() {
    const text = `${Math.round(view.scale * 100)}%`;
    if (text === lastZoomText) return;
    lastZoomText = text;
    zoomLabel.textContent = text;
  }

  function invalidateInk() {
    inkDirty = true;
  }

  function invalidateGrid() {
    gridDirty = true;
  }

  function invalidateSpatial() {
    spatialIndex = null;
    spatialRev = -1;
  }

  function bumpDoc(opName, strokeId) {
    docRevision += 1;
    invalidateSpatial();
    if (opName === "set_background" || opName === "clear_page") invalidateGrid();
    // Open stroke is painted live (excluded from ink bake); avoid thrashing the cache.
    if (opName === "append_points" && strokeId && strokeId === currentStrokeId) return;
    if (opName === "begin_stroke") return;
    invalidateInk();
  }

  function viewCacheKey() {
    // Includes pan — only for debugging / overlay; caches use viewStableKey.
    return [
      view.x.toFixed(2),
      view.y.toFixed(2),
      view.scale.toFixed(4),
      canvas.width,
      canvas.height,
      dpr,
      pageBackground,
    ].join("|");
  }

  function viewStableKey() {
    // Pan-independent. Translation is applied as a blit offset.
    return [
      view.scale.toFixed(4),
      canvas.width,
      canvas.height,
      dpr,
      pageBackground,
    ].join("|");
  }

  function sessionSkipKey() {
    if (!partialSession) return "";
    return [...partialSession.originals.keys()].sort().join(",");
  }

  function applyWorldTransform(target) {
    target.setTransform(dpr, 0, 0, dpr, 0, 0);
    target.translate(view.x, view.y);
    target.scale(view.scale, view.scale);
  }

  function rebuildGridLayer(screenW, screenH) {
    if (gridLayer.width !== canvas.width || gridLayer.height !== canvas.height) {
      gridLayer.width = canvas.width;
      gridLayer.height = canvas.height;
    }
    gridCtx.setTransform(1, 0, 0, 1, 0, 0);
    gridCtx.clearRect(0, 0, gridLayer.width, gridLayer.height);
    // drawGrid uses ctx + applyViewTransform — temporarily draw via ink-style
    const prevApply = applyViewTransform;
    // Inline grid onto gridCtx
    const minor = niceGridStep(40 / view.scale);
    const major = minor * 5;
    const left = screenToWorld(0, 0).x;
    const top = screenToWorld(0, 0).y;
    const right = screenToWorld(screenW, screenH).x;
    const bottom = screenToWorld(screenW, screenH).y;
    const startX = Math.floor(left / minor) * minor;
    const startY = Math.floor(top / minor) * minor;
    const dark = isDarkBackground(pageBackground);
    const minorStroke = dark ? "rgba(230, 230, 220, 0.07)" : "rgba(80, 70, 55, 0.08)";
    const majorStroke = dark ? "rgba(230, 230, 220, 0.14)" : "rgba(80, 70, 55, 0.18)";
    const axisStroke = dark ? "rgba(180, 210, 190, 0.28)" : "rgba(47, 93, 80, 0.35)";
    applyWorldTransform(gridCtx);
    gridCtx.lineWidth = 1 / view.scale;
    for (let x = startX; x <= right; x += minor) {
      const isMajor = Math.abs(x / major - Math.round(x / major)) < 1e-9;
      gridCtx.strokeStyle = isMajor ? majorStroke : minorStroke;
      gridCtx.beginPath();
      gridCtx.moveTo(x, top);
      gridCtx.lineTo(x, bottom);
      gridCtx.stroke();
    }
    for (let y = startY; y <= bottom; y += minor) {
      const isMajor = Math.abs(y / major - Math.round(y / major)) < 1e-9;
      gridCtx.strokeStyle = isMajor ? majorStroke : minorStroke;
      gridCtx.beginPath();
      gridCtx.moveTo(left, y);
      gridCtx.lineTo(right, y);
      gridCtx.stroke();
    }
    gridCtx.strokeStyle = axisStroke;
    gridCtx.beginPath();
    gridCtx.moveTo(0, top);
    gridCtx.lineTo(0, bottom);
    gridCtx.moveTo(left, 0);
    gridCtx.lineTo(right, 0);
    gridCtx.stroke();
    void prevApply;
    gridDirty = false;
    gridViewKey = viewStableKey();
    gridBake = { x: view.x, y: view.y, scale: view.scale };
  }

  function rebuildInkLayer(page, skipIds) {
    if (inkLayer.width !== canvas.width || inkLayer.height !== canvas.height) {
      inkLayer.width = canvas.width;
      inkLayer.height = canvas.height;
    }
    inkCtx.setTransform(1, 0, 0, 1, 0, 0);
    inkCtx.clearRect(0, 0, inkLayer.width, inkLayer.height);
    if (!page) {
      inkDirty = false;
      return;
    }
    applyWorldTransform(inkCtx);
    for (const sid of page.stroke_order || []) {
      if (skipIds && skipIds.has(sid)) continue;
      const stroke = page.strokes[sid];
      if (!stroke) continue;
      drawStrokePoints(stroke.points || [], strokeStyleOf(stroke), { ctx: inkCtx });
    }
    inkDirty = false;
    inkBake = { x: view.x, y: view.y, scale: view.scale };
  }

  function ensureSpatial(page) {
    if (spatialIndex && spatialRev === docRevision) return spatialIndex;
    const index = new Map();
    if (page) {
      for (const sid of page.stroke_order || []) {
        const stroke = page.strokes[sid];
        if (!stroke || !stroke.points || stroke.points.length < 2) continue;
        const bb = strokeBBox(stroke, 0);
        const x0 = Math.floor(bb.minX / SPATIAL_CELL);
        const x1 = Math.floor(bb.maxX / SPATIAL_CELL);
        const y0 = Math.floor(bb.minY / SPATIAL_CELL);
        const y1 = Math.floor(bb.maxY / SPATIAL_CELL);
        for (let cx = x0; cx <= x1; cx++) {
          for (let cy = y0; cy <= y1; cy++) {
            const key = cx + ":" + cy;
            let bucket = index.get(key);
            if (!bucket) {
              bucket = [];
              index.set(key, bucket);
            }
            bucket.push(sid);
          }
        }
      }
    }
    spatialIndex = index;
    spatialRev = docRevision;
    return index;
  }

  function querySpatialIds(page, cx, cy, r) {
    const index = ensureSpatial(page);
    const ids = new Set();
    const x0 = Math.floor((cx - r) / SPATIAL_CELL);
    const x1 = Math.floor((cx + r) / SPATIAL_CELL);
    const y0 = Math.floor((cy - r) / SPATIAL_CELL);
    const y1 = Math.floor((cy + r) / SPATIAL_CELL);
    for (let gx = x0; gx <= x1; gx++) {
      for (let gy = y0; gy <= y1; gy++) {
        const bucket = index.get(gx + ":" + gy);
        if (!bucket) continue;
        for (const sid of bucket) ids.add(sid);
      }
    }
    return ids;
  }

  function decimatePoints(points) {
    if (!points || points.length <= 2) return points;
    const min2 = MIN_POINT_DIST * MIN_POINT_DIST;
    const out = [points[0]];
    let last = points[0];
    for (let i = 1; i < points.length - 1; i++) {
      const p = points[i];
      const dx = p[0] - last[0];
      const dy = p[1] - last[1];
      if (dx * dx + dy * dy >= min2) {
        out.push(p);
        last = p;
      }
    }
    out.push(points[points.length - 1]);
    return out.length >= 2 ? out : points;
  }

  function redraw(provisional) {
    const t0 = performance.now();
    const screenW = canvas.clientWidth;
    const screenH = canvas.clientHeight;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, screenW, screenH);
    const page =
      documentState && documentState.pages
        ? documentState.pages[documentState.active_page_id || "p0"]
        : null;
    pageBackground = (page && page.background) || pageBackground || "#fafaf7";
    ctx.fillStyle = pageBackground;
    ctx.fillRect(0, 0, screenW, screenH);

    const stable = viewStableKey();
    // Keep the grid visible while erasing — cached blit is cheap.
    if (gridDirty || gridViewKey !== stable) rebuildGridLayer(screenW, screenH);
    {
      const gdx = (view.x - gridBake.x) * dpr;
      const gdy = (view.y - gridBake.y) * dpr;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.drawImage(gridLayer, gdx, gdy);
    }

    applyViewTransform();
    drawPageImages(page);

    const bakeSkip = new Set();
    if (partialSession) {
      for (const sid of partialSession.originals.keys()) bakeSkip.add(sid);
    }
    if (currentStrokeId) bakeSkip.add(currentStrokeId);
    if (provisional && provisional.strokeId) bakeSkip.add(provisional.strokeId);
    const wantKey = stable + "#" + [...bakeSkip].sort().join(",");
    if (inkDirty || inkViewKey !== wantKey) {
      rebuildInkLayer(page, bakeSkip.size ? bakeSkip : null);
      inkViewKey = wantKey;
    }

    const idx = (view.x - inkBake.x) * dpr;
    const idy = (view.y - inkBake.y) * dpr;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(inkLayer, idx, idy);

    applyViewTransform();
    if (partialSession) {
      for (const [sid, orig] of partialSession.originals) {
        const alive = partialSession.alive.get(sid);
        const runs = cachedPartialRuns(sid, orig, alive);
        const style = strokeStyleOf(orig);
        for (const run of runs) drawStrokePoints(run, style, { fast: true });
      }
    }
    if (page && provisional && provisional.strokeId) {
      const stroke = page.strokes[provisional.strokeId];
      if (stroke) drawStroke(stroke, provisional.points, { fast: true });
    } else if (page && currentStrokeId) {
      const stroke = page.strokes[currentStrokeId];
      if (stroke) {
        const pts = livePoints || stroke.points;
        drawStroke(stroke, pts, { fast: true });
      }
    }

    updateZoomLabel();
    Perf.counters.redraws += 1;
    Perf.mark("redraw_ms", performance.now() - t0);
    if (!Perf.hud) {
      // Lightweight fps estimate from redraw cadence when HUD loop is off.
      Perf._fpsFrames = (Perf._fpsFrames || 0) + 1;
      const now = performance.now();
      if (!Perf._fpsLast) Perf._fpsLast = now;
      if (now - Perf._fpsLast >= 500) {
        Perf.fps = (Perf._fpsFrames * 1000) / (now - Perf._fpsLast);
        Perf._fpsFrames = 0;
        Perf._fpsLast = now;
      }
    }
  }

  function zoomAt(sx, sy, factor) {
    const before = screenToWorld(sx, sy);
    view.scale = clampScale(view.scale * factor);
    view.x = sx - before.x * view.scale;
    view.y = sy - before.y * view.scale;
    invalidateInk();
    invalidateGrid();
    scheduleRedraw();
  }

  function zoomByButton(factor) {
    zoomAt(canvas.clientWidth / 2, canvas.clientHeight / 2, factor);
  }

  function resetView() {
    view.x = 0;
    view.y = 0;
    view.scale = 1;
    invalidateInk();
    invalidateGrid();
    scheduleRedraw();
  }

  function wantsPan(ev) {
    if (isPanning) return true;
    if (panMode) return true;
    if (spaceHeld) return true;
    if (ev.buttons === 4 || ev.button === 1) return true;
    if (ev.pointerType === "touch") return true;
    return false;
  }

  function dist2(ax, ay, bx, by) {
    const dx = ax - bx;
    const dy = ay - by;
    return dx * dx + dy * dy;
  }

  function distPointSeg2(px, py, ax, ay, bx, by) {
    const abx = bx - ax;
    const aby = by - ay;
    const len2 = abx * abx + aby * aby;
    if (len2 < 1e-9) return dist2(px, py, ax, ay);
    let t = ((px - ax) * abx + (py - ay) * aby) / len2;
    t = Math.max(0, Math.min(1, t));
    return dist2(px, py, ax + t * abx, ay + t * aby);
  }

  function bboxOfPoints(pts, pad) {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (let i = 0; i < pts.length; i++) {
      const x = pts[i][0];
      const y = pts[i][1];
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
    if (!Number.isFinite(minX)) {
      return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
    }
    return {
      minX: minX - pad,
      minY: minY - pad,
      maxX: maxX + pad,
      maxY: maxY + pad,
    };
  }

  function bboxHitsCircle(bb, cx, cy, r) {
    const qx = Math.max(bb.minX, Math.min(cx, bb.maxX));
    const qy = Math.max(bb.minY, Math.min(cy, bb.maxY));
    return dist2(cx, cy, qx, qy) <= r * r;
  }

  function strokeBBox(stroke, pad) {
    if (stroke._bbox && stroke._bboxPad === pad) return stroke._bbox;
    const pts = stroke.points || [];
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      const x = Array.isArray(p) ? p[0] : p.x;
      const y = Array.isArray(p) ? p[1] : p.y;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
    const bb = Number.isFinite(minX)
      ? { minX: minX - pad, minY: minY - pad, maxX: maxX + pad, maxY: maxY + pad }
      : { minX: 0, minY: 0, maxX: 0, maxY: 0 };
    stroke._bbox = bb;
    stroke._bboxPad = pad;
    return bb;
  }

  function strokeHitsPoint(stroke, x, y, radius) {
    const pts = stroke.points || [];
    if (!pts.length) return false;
    if (!bboxHitsCircle(strokeBBox(stroke, radius), x, y, radius)) return false;
    const r2 = radius * radius;
    for (let i = 0; i < pts.length; i++) {
      const a = xyOf(pts[i]);
      if (dist2(x, y, a.x, a.y) <= r2) return true;
      if (i > 0) {
        const b = xyOf(pts[i - 1]);
        if (distPointSeg2(x, y, b.x, b.y, a.x, a.y) <= r2) return true;
      }
    }
    return false;
  }

  function pointAsList(p) {
    if (Array.isArray(p)) return [p[0], p[1], p[2] ?? 0, p[3] ?? 0.5];
    return [p.x, p.y, p.t ?? 0, p.pressure ?? 0.5];
  }

  function applyLocalOp(op, { paint = true } = {}) {
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
        style: op.style || { color: "#111111", width: 2, kind: "pen" },
        author: op.author || "",
        open: true,
      };
      page.stroke_order.push(op.stroke_id);
    } else if (op.op === "append_points") {
      const stroke = page.strokes[op.stroke_id];
      if (stroke) {
        stroke.points.push(...op.points);
        stroke._bbox = null;
      }
    } else if (op.op === "end_stroke") {
      const stroke = page.strokes[op.stroke_id];
      if (stroke) stroke.open = false;
    } else if (op.op === "erase_stroke") {
      delete page.strokes[op.stroke_id];
      page.stroke_order = page.stroke_order.filter((id) => id !== op.stroke_id);
    } else if (op.op === "clear_page") {
      page.strokes = {};
      page.stroke_order = [];
      page.images = {};
      page.image_order = [];
      setSelectedImage(null);
    } else if (op.op === "set_background") {
      applyPageBackground(op.color);
    } else if (op.op === "add_image") {
      if (!page.images) page.images = {};
      if (!page.image_order) page.image_order = [];
      page.images[op.image_id] = {
        image_id: op.image_id,
        asset_id: op.asset_id,
        x: op.x,
        y: op.y,
        width: op.width,
        height: op.height,
        author: op.author || "",
        layer: op.layer || "images",
        locked: false,
      };
      page.image_order.push(op.image_id);
      ensureImageAsset(op.asset_id);
    } else if (op.op === "erase_image") {
      if (page.images) delete page.images[op.image_id];
      if (page.image_order) {
        page.image_order = page.image_order.filter((id) => id !== op.image_id);
      }
      if (selectedImageId === op.image_id) setSelectedImage(null);
    } else if (op.op === "transform_image") {
      if (!page.images) page.images = {};
      const image = page.images[op.image_id];
      if (image && !image.locked) {
        image.x = op.x;
        image.y = op.y;
        image.width = op.width;
        image.height = op.height;
      }
    } else if (op.op === "set_image_lock") {
      if (!page.images) page.images = {};
      const image = page.images[op.image_id];
      if (image) image.locked = !!op.locked;
    } else if (op.op === "add_stroke") {
      page.strokes[op.stroke_id] = {
        stroke_id: op.stroke_id,
        points: op.points.slice(),
        style: op.style || { color: "#111111", width: 2, kind: "pen" },
        author: op.author || "",
        layer: op.layer || "default",
        open: false,
      };
      page.stroke_order.push(op.stroke_id);
    } else if (op.op === "replace_stroke_points") {
      if (!op.points || op.points.length === 0) {
        delete page.strokes[op.stroke_id];
        page.stroke_order = page.stroke_order.filter((id) => id !== op.stroke_id);
      } else {
        const stroke = page.strokes[op.stroke_id];
        if (stroke) {
          stroke.points = op.points.slice();
          stroke.open = false;
          stroke._bbox = null;
        }
      }
    }
    if (paint) scheduleRedraw();
    bumpDoc(op.op, op.stroke_id);
  }

  function emitOp(op) {
    emitOps([op]);
  }

  function emitOps(ops) {
    if (!ops.length) return;
    const t0 = performance.now();
    if (ws && ws.readyState === WebSocket.OPEN) {
      if (ops.length === 1) {
        ws.send(JSON.stringify({ type: "op", op: ops[0] }));
      } else {
        ws.send(JSON.stringify({ type: "ops", ops }));
      }
    } else {
      for (const op of ops) {
        fetch("/api/op", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(op),
        }).catch(() => {});
      }
    }
    Perf.counters.emits += 1;
    Perf.mark("emit_ms", performance.now() - t0);
  }

  function sendOp(op, { paint = true } = {}) {
    applyLocalOp(op, { paint });
    emitOps([op]);
  }

  function sendOps(ops, { paint = true } = {}) {
    for (const op of ops) applyLocalOp(op, { paint: false });
    if (paint) scheduleRedraw();
    emitOps(ops);
  }

  function queueSyncOp(op) {
    pendingSyncOps.push(op);
    applyLocalOp(op, { paint: false });
  }

  function flushSyncOps() {
    if (!pendingSyncOps.length) return;
    const batch = pendingSyncOps.splice(0, pendingSyncOps.length);
    emitOps(batch);
    scheduleRedraw();
  }

  async function loadPair() {
    const res = await fetch("/api/pair");
    pair = await res.json();
    Perf.room = pair.room || null;
    setStatus(`room ${pair.room}`);
    return pair;
  }

  function connectWs() {
    if (!pair || !pair.ws) return;
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
        const page =
          documentState &&
          documentState.pages &&
          documentState.pages[documentState.active_page_id || "p0"];
        if (page && page.background) {
          applyPageBackground(page.background);
        }
        if (page && page.images) {
          for (const iid of page.image_order || Object.keys(page.images)) {
            const image = page.images[iid];
            if (image && image.asset_id) ensureImageAsset(image.asset_id);
          }
        }
        scheduleRedraw();
        return;
      }
      if (msg.type === "op" && msg.op) {
        applyLocalOp(msg.op);
        if (
          msg.op.op === "end_stroke" ||
          msg.op.op === "begin_stroke" ||
          msg.op.op === "add_stroke"
        ) {
          lastStrokeId = msg.op.stroke_id;
        }
        return;
      }
      if (msg.type === "ops" && Array.isArray(msg.ops)) {
        for (const op of msg.ops) {
          applyLocalOp(op, { paint: false });
          if (op.op === "end_stroke" || op.op === "begin_stroke" || op.op === "add_stroke") {
            lastStrokeId = op.stroke_id;
          }
        }
        scheduleRedraw();
      }
    };
  }

  function flushPoints() {
    if (!currentStrokeId || pointBuffer.length === 0) return;
    let points = pointBuffer.splice(0, pointBuffer.length);
    if (USE_DECIMATE) points = decimatePoints(points);
    if (!points.length) return;
    sendOp({
      op: "append_points",
      stroke_id: currentStrokeId,
      page_id: "p0",
      points,
    });
  }

  function endStrokeIfAny() {
    if (!currentStrokeId) return;
    flushPoints();
    if (flushTimer) clearInterval(flushTimer);
    flushTimer = null;
    sendOp({ op: "end_stroke", stroke_id: currentStrokeId, page_id: "p0" });
    currentStrokeId = null;
    livePoints = null;
  }

  function eraseWholeAt(x, y) {
    const page = documentState && documentState.pages.p0;
    if (!page) return false;
    let hit = false;
    const images = page.image_order || [];
    for (let i = images.length - 1; i >= 0; i--) {
      const iid = images[i];
      const image = page.images && page.images[iid];
      if (!image) continue;
      if (
        x >= image.x &&
        x <= image.x + image.width &&
        y >= image.y &&
        y <= image.y + image.height
      ) {
        queueSyncOp({ op: "erase_image", image_id: iid, page_id: "p0" });
        return true;
      }
    }
    const candidates = USE_SPATIAL
      ? querySpatialIds(page, x, y, eraserRadiusWorld)
      : null;
    for (let i = page.stroke_order.length - 1; i >= 0; i--) {
      const sid = page.stroke_order[i];
      if (candidates && !candidates.has(sid)) continue;
      if (erasedStrokeIds.has(sid)) continue;
      const stroke = page.strokes[sid];
      if (!stroke) continue;
      if (strokeHitsPoint(stroke, x, y, eraserRadiusWorld)) {
        erasedStrokeIds.add(sid);
        queueSyncOp({ op: "erase_stroke", stroke_id: sid, page_id: "p0" });
        if (lastStrokeId === sid) lastStrokeId = null;
        hit = true;
        break;
      }
    }
    return hit;
  }

  function adoptStrokeIntoSession(sid, stroke) {
    if (!partialSession || partialSession.originals.has(sid)) return false;
    if (!stroke || !stroke.points || stroke.points.length < 2) return false;
    const points = stroke.points.map(pointAsList);
    partialSession.originals.set(sid, {
      points,
      style: stroke.style || { color: "#111111", width: 2, kind: "pen" },
      author: stroke.author || "",
      layer: stroke.layer || "default",
      bbox: bboxOfPoints(points, eraserRadiusWorld),
    });
    partialSession.alive.set(sid, new Uint8Array(points.length).fill(1));
    invalidateInk();
    return true;
  }

  function adoptNearby(cx, cy) {
    if (!partialSession) return false;
    const page = documentState && documentState.pages.p0;
    if (!page) return false;
    const margin = eraserAdoptRadius();
    const candidates = USE_SPATIAL
      ? querySpatialIds(page, cx, cy, margin)
      : null;
    let added = false;
    for (const sid of page.stroke_order) {
      if (candidates && !candidates.has(sid)) continue;
      if (partialSession.originals.has(sid)) continue;
      const stroke = page.strokes[sid];
      if (!stroke) continue;
      if (!bboxHitsCircle(strokeBBox(stroke, margin), cx, cy, margin)) continue;
      if (adoptStrokeIntoSession(sid, stroke)) added = true;
    }
    return added;
  }

  function beginPartialSession(cx, cy) {
    Perf.counters.stamps = 0;
    partialSession = {
      originals: new Map(),
      alive: new Map(),
      runs: new Map(),
      touched: new Set(),
      lastX: NaN,
      lastY: NaN,
    };
    adoptNearby(cx, cy);
  }

  function stampPartial(cx, cy) {
    if (!partialSession) return false;
    const t0 = performance.now();
    const r = eraserRadiusWorld;
    const r2 = r * r;
    let changed = false;
    for (const [sid, orig] of partialSession.originals) {
      if (!bboxHitsCircle(orig.bbox, cx, cy, r)) continue;
      const flags = partialSession.alive.get(sid);
      const pts = orig.points;
      let strokeChanged = false;
      for (let i = 0; i < pts.length; i++) {
        if (!flags[i]) continue;
        const x = pts[i][0];
        const y = pts[i][1];
        if (dist2(cx, cy, x, y) <= r2) {
          flags[i] = 0;
          strokeChanged = true;
          continue;
        }
        if (i > 0) {
          const px = pts[i - 1][0];
          const py = pts[i - 1][1];
          if (distPointSeg2(cx, cy, px, py, x, y) <= r2) {
            flags[i] = 0;
            if (flags[i - 1]) flags[i - 1] = 0;
            strokeChanged = true;
          }
        }
      }
      if (strokeChanged) {
        changed = true;
        partialSession.touched.add(sid);
        partialSession.runs.delete(sid);
      }
    }
    Perf.counters.stamps += 1;
    Perf.mark("stamp_ms", performance.now() - t0);
    return changed;
  }

  function maybeStampPartial(x, y, force) {
    if (!partialSession) return;
    if (adoptNearby(x, y)) {
      // new strokes entered the live set; ink cache rebuilds on next redraw
    }
    const lastX = partialSession.lastX;
    const lastY = partialSession.lastY;
    let changed = false;

    if (!force && Number.isFinite(lastX)) {
      const travel = Math.hypot(x - lastX, y - lastY);
      if (travel < eraserStep()) {
        scheduleOverlay();
        return;
      }
      const steps = Math.min(ERASER_MAX_SEG_STAMPS, Math.max(1, Math.ceil(travel / eraserStep())));
      for (let i = 1; i <= steps; i++) {
        const t = i / steps;
        if (stampPartial(lastX + (x - lastX) * t, lastY + (y - lastY) * t)) changed = true;
      }
    } else if (stampPartial(x, y)) {
      changed = true;
    }

    partialSession.lastX = x;
    partialSession.lastY = y;
    if (changed) scheduleRedraw();
    else scheduleOverlay();
  }

  function commitPartialSession() {
    if (!partialSession) return;
    const t0 = performance.now();
    const { originals, alive, touched } = partialSession;
    const stamps = Perf.counters.stamps;
    partialSession = null;
    const outOps = [];

    for (const sid of touched) {
      const orig = originals.get(sid);
      if (!orig) continue;
      const flags = alive.get(sid);
      let runs = runsFromAlive(orig.points, flags);
      if (USE_DECIMATE) {
        runs = runs.map((run) => decimatePoints(run));
      }

      if (runs.length === 0) {
        outOps.push({ op: "erase_stroke", stroke_id: sid, page_id: "p0" });
        if (lastStrokeId === sid) lastStrokeId = null;
        continue;
      }

      outOps.push({
        op: "replace_stroke_points",
        stroke_id: sid,
        page_id: "p0",
        points: runs[0],
      });

      for (let r = 1; r < runs.length; r++) {
        const newId = `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
        outOps.push({
          op: "add_stroke",
          stroke_id: newId,
          page_id: "p0",
          author: orig.author || author,
          layer: orig.layer || "default",
          style: orig.style,
          points: runs[r],
        });
        lastStrokeId = newId;
      }
    }

    sendOps(outOps, { paint: true });
    const commitMs = performance.now() - t0;
    Perf.counters.commits += 1;
    Perf.mark("commit_ms", commitMs);
    Perf.lastGesture = {
      stamps,
      commit_ms: commitMs,
      ops: outOps.length,
      scene: Perf.scene(),
    };
    Perf.counters.stamps = 0;
  }

  function onDown(ev) {
    pointers.set(ev.pointerId, pointerScreen(ev));

    if (isStylusEraser(ev)) {
      eraserTipActive = true;
      toolBeforeEraserTip = tool === "pen" ? tool : toolBeforeEraserTip;
      setTool("erase-stroke");
    }

    if (pointers.size === 2) {
      endStrokeIfAny();
      if (partialSession) commitPartialSession();
      const pts = [...pointers.values()];
      const dx = pts[1].sx - pts[0].sx;
      const dy = pts[1].sy - pts[0].sy;
      pinch = {
        dist: Math.hypot(dx, dy) || 1,
        scale: view.scale,
        midX: (pts[0].sx + pts[1].sx) / 2,
        midY: (pts[0].sy + pts[1].sy) / 2,
        viewX: view.x,
        viewY: view.y,
      };
      isPanning = false;
      return;
    }

    if (wantsPan(ev)) {
      endStrokeIfAny();
      if (partialSession) commitPartialSession();
      isPanning = true;
      panLast = pointerScreen(ev);
      updateCursor();
      try {
        canvas.setPointerCapture(ev.pointerId);
      } catch (_) {}
      ev.preventDefault();
      return;
    }

    if (ev.pointerType === "touch") return;

    try {
      canvas.setPointerCapture(ev.pointerId);
    } catch (_) {}

    const p = pointerWorld(ev);
    eraserCursor =
      tool === "erase-stroke" || tool === "erase-partial" ? { x: p.x, y: p.y } : null;

    if (tool === "erase-stroke") {
      erasedStrokeIds.clear();
      if (eraseWholeAt(p.x, p.y)) scheduleRedraw();
      else scheduleOverlay();
      ev.preventDefault();
      return;
    }
    if (tool === "erase-partial") {
      beginPartialSession(p.x, p.y);
      maybeStampPartial(p.x, p.y, true);
      ev.preventDefault();
      return;
    }

    // Pen tool: long-press to select; move/resize when selected (unless locked).
    if (tool === "pen") {
      const selected = selectedImageId ? getImage(selectedImageId) : null;
      if (selected) {
        if (hitImageLockIcon(selected, p.x, p.y)) {
          toggleImageLock(selectedImageId);
          ev.preventDefault();
          return;
        }
        if (!selected.locked) {
          const handle = hitImageHandle(selected, p.x, p.y);
          if (handle) {
            imageGesture = {
              mode: "resize",
              imageId: selectedImageId,
              handle,
              keepAspect: IMAGE_CORNER_HANDLES.has(handle),
              startX: p.x,
              startY: p.y,
              orig: {
                x: selected.x,
                y: selected.y,
                width: selected.width,
                height: selected.height,
              },
            };
            ev.preventDefault();
            return;
          }
          if (pointInImage(selected, p.x, p.y)) {
            imageGesture = {
              mode: "move",
              imageId: selectedImageId,
              startX: p.x,
              startY: p.y,
              orig: {
                x: selected.x,
                y: selected.y,
                width: selected.width,
                height: selected.height,
              },
            };
            ev.preventDefault();
            return;
          }
        } else if (pointInImage(selected, p.x, p.y)) {
          // Locked: keep selection, ignore drag (still allow lock toggle above).
          ev.preventDefault();
          return;
        }
      }

      const hitId = hitTopImageAt(p.x, p.y);
      if (hitId) {
        const screen = pointerScreen(ev);
        clearImagePress();
        imagePress = {
          imageId: hitId,
          startX: p.x,
          startY: p.y,
          sx: screen.sx,
          sy: screen.sy,
          pointerId: ev.pointerId,
          t: p.t,
          pressure: p.pressure,
          armed: false,
        };
        imagePress.timer = setTimeout(() => {
          if (!imagePress || imagePress.pointerId !== ev.pointerId) return;
          imagePress.armed = true;
          setSelectedImage(imagePress.imageId);
          setStatus("image selected");
          scheduleOverlay();
        }, LONG_PRESS_MS);
        ev.preventDefault();
        return;
      }
      if (selectedImageId) setSelectedImage(null);
    }

    beginStrokeAt(p);
    ev.preventDefault();
  }

  function onMove(ev) {
    if (pointers.has(ev.pointerId)) {
      pointers.set(ev.pointerId, pointerScreen(ev));
    }

    if (pointers.size === 2 && pinch) {
      const pts = [...pointers.values()];
      const dx = pts[1].sx - pts[0].sx;
      const dy = pts[1].sy - pts[0].sy;
      const dist = Math.hypot(dx, dy) || 1;
      const midX = (pts[0].sx + pts[1].sx) / 2;
      const midY = (pts[0].sy + pts[1].sy) / 2;
      const nextScale = clampScale(pinch.scale * (dist / pinch.dist));
      const world = {
        x: (pinch.midX - pinch.viewX) / pinch.scale,
        y: (pinch.midY - pinch.viewY) / pinch.scale,
      };
      view.scale = nextScale;
      view.x = midX - world.x * view.scale;
      view.y = midY - world.y * view.scale;
      view.x += midX - pinch.midX;
      view.y += midY - pinch.midY;
      pinch.midX = midX;
      pinch.midY = midY;
      pinch.viewX = view.x;
      pinch.viewY = view.y;
      pinch.scale = view.scale;
      pinch.dist = dist;
      invalidateInk();
      invalidateGrid();
      scheduleRedraw();
      ev.preventDefault();
      return;
    }

    if (isPanning && panLast) {
      const now = pointerScreen(ev);
      view.x += now.sx - panLast.sx;
      view.y += now.sy - panLast.sy;
      panLast = now;
      // Pan only: blit cached layers with offset — no full rebuild mid-drag.
      scheduleRedraw();
      ev.preventDefault();
      return;
    }

    const p = pointerWorld(ev);

    if (imagePress && imagePress.pointerId === ev.pointerId) {
      const screen = pointerScreen(ev);
      const moved = Math.hypot(screen.sx - imagePress.sx, screen.sy - imagePress.sy);
      if (moved > LONG_PRESS_MOVE_PX) {
        const start = {
          x: imagePress.startX,
          y: imagePress.startY,
          t: imagePress.t,
          pressure: imagePress.pressure,
        };
        clearImagePress();
        beginStrokeAt(start);
        // Continue with current point as first move sample below.
      } else {
        ev.preventDefault();
        return;
      }
    }

    if (imageGesture) {
      const dx = p.x - imageGesture.startX;
      const dy = p.y - imageGesture.startY;
      const orig = imageGesture.orig;
      let box;
      if (imageGesture.mode === "resize") {
        box = resizeFromHandle(
          orig,
          imageGesture.handle,
          dx,
          dy,
          !!imageGesture.keepAspect
        );
      } else {
        box = {
          x: orig.x + dx,
          y: orig.y + dy,
          width: orig.width,
          height: orig.height,
        };
      }
      applyImageBoxLocal(imageGesture.imageId, box);
      scheduleRedraw();
      scheduleOverlay();
      ev.preventDefault();
      return;
    }

    if (tool === "pen" && ev.buttons === 0) {
      updateImageHoverCursor(p.x, p.y);
    }

    if (tool === "erase-stroke" || tool === "erase-partial") {
      eraserCursor = { x: p.x, y: p.y };
      if (ev.buttons > 0) {
        if (tool === "erase-stroke") {
          if (eraseWholeAt(p.x, p.y)) scheduleRedraw();
          else scheduleOverlay();
        } else {
          maybeStampPartial(p.x, p.y, false);
        }
      } else {
        scheduleOverlay();
      }
      ev.preventDefault();
      return;
    }

    if (!currentStrokeId) return;
    const sample = [p.x, p.y, p.t, p.pressure];
    pointBuffer.push(sample);
    if (!livePoints) {
      const page = documentState && documentState.pages.p0;
      const stroke = page && page.strokes[currentStrokeId];
      livePoints = stroke && stroke.points ? stroke.points.slice() : [];
    }
    livePoints.push(sample);
    scheduleRedraw({
      strokeId: currentStrokeId,
      points: livePoints,
    });
    ev.preventDefault();
  }

  function onUp(ev) {
    pointers.delete(ev.pointerId);
    if (pointers.size < 2) pinch = null;

    if (imageGesture) {
      const imageId = imageGesture.imageId;
      imageGesture = null;
      commitImageTransform(imageId);
      scheduleOverlay();
      updateCursor();
      ev.preventDefault();
      return;
    }

    if (imagePress && imagePress.pointerId === ev.pointerId) {
      const wasArmed = imagePress.armed;
      clearImagePress();
      if (wasArmed) setStatus("image selected");
      ev.preventDefault();
      return;
    }

    if (eraserTipActive && !isStylusEraser(ev) && (ev.buttons & 32) === 0) {
      eraserTipActive = false;
      setTool(toolBeforeEraserTip || "pen");
    }

    if (isPanning && pointers.size === 0) {
      isPanning = false;
      panLast = null;
      updateCursor();
      invalidateInk();
      invalidateGrid();
      scheduleRedraw();
      ev.preventDefault();
      return;
    }

    if (tool === "erase-partial" && partialSession) {
      commitPartialSession();
      eraserCursor = null;
      scheduleRedraw();
      ev.preventDefault();
      return;
    }

    if (tool === "erase-stroke") {
      flushSyncOps();
      erasedStrokeIds.clear();
      eraserCursor = null;
      scheduleOverlay();
      scheduleRedraw();
      ev.preventDefault();
      return;
    }

    if (!currentStrokeId) return;
    endStrokeIfAny();
    ev.preventDefault();
  }

  canvas.addEventListener(
    "wheel",
    (ev) => {
      ev.preventDefault();
      const { sx, sy } = pointerScreen(ev);
      zoomAt(sx, sy, ev.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP);
    },
    { passive: false }
  );

  window.addEventListener("keydown", (ev) => {
    if (ev.code === "Space" && !ev.repeat) {
      spaceHeld = true;
      updateCursor();
      ev.preventDefault();
    }
    if (ev.key === "Escape") {
      if (imageGesture) imageGesture = null;
      if (selectedImageId) {
        setSelectedImage(null);
        ev.preventDefault();
      }
    }
    if (
      (ev.key === "Delete" || ev.key === "Backspace") &&
      selectedImageId &&
      !ev.ctrlKey &&
      !ev.metaKey
    ) {
      const imageId = selectedImageId;
      sendOp({ op: "erase_image", image_id: imageId, page_id: "p0" });
      setSelectedImage(null);
      ev.preventDefault();
    }
    if (ev.key === "e" && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
      setTool(tool === "erase-stroke" ? "erase-partial" : "erase-stroke");
    }
    if (ev.key === "b" && !ev.ctrlKey && !ev.metaKey && !ev.altKey) setTool("pen");
    if (ev.key === "p" && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
      Perf.setHud(!Perf.hud);
    }
    if ((ev.key === "+" || ev.key === "=") && (ev.ctrlKey || ev.metaKey)) {
      zoomByButton(ZOOM_STEP);
      ev.preventDefault();
    }
    if (ev.key === "-" && (ev.ctrlKey || ev.metaKey)) {
      zoomByButton(1 / ZOOM_STEP);
      ev.preventDefault();
    }
    if (ev.key === "0" && (ev.ctrlKey || ev.metaKey)) {
      resetView();
      ev.preventDefault();
    }
  });

  window.addEventListener("keyup", (ev) => {
    if (ev.code === "Space") {
      spaceHeld = false;
      updateCursor();
    }
  });

  document.getElementById("btn-clear").onclick = () => {
    if (partialSession) partialSession = null;
    pendingSyncOps.length = 0;
    sendOp({ op: "clear_page", page_id: "p0" });
    lastStrokeId = null;
  };

  document.getElementById("btn-undo").onclick = () => {
    if (!lastStrokeId) return;
    sendOp({ op: "erase_stroke", stroke_id: lastStrokeId, page_id: "p0" });
    lastStrokeId = null;
  };

  document.getElementById("btn-pair").onclick = () => {
    location.href = "/pair";
  };

  document.getElementById("btn-image").onclick = () => {
    if (fileImageInput) fileImageInput.click();
  };
  if (fileImageInput) {
    fileImageInput.onchange = () => {
      importImageFiles(fileImageInput.files);
      fileImageInput.value = "";
    };
  }

  document.getElementById("btn-export").onclick = () => toggleExportDock();
  document.getElementById("btn-export-png").onclick = () => exportViewportPng();
  document.getElementById("btn-export-svg").onclick = () => {
    exportFromApi("/api/export/svg", `apesketch-${Date.now()}.svg`)
      .then(() => setStatus("exported SVG"))
      .catch((err) => setStatus(String(err.message || err)));
  };
  document.getElementById("btn-export-json").onclick = () => {
    exportFromApi("/api/export/json", `apesketch-${Date.now()}.json`)
      .then(() => setStatus("exported JSON"))
      .catch((err) => setStatus(String(err.message || err)));
  };
  if (btnRecord) btnRecord.onclick = () => toggleRecording();

  window.addEventListener("paste", (ev) => {
    const clip = ev.clipboardData;
    if (!clip) return;
    const images = [];
    if (clip.items) {
      for (const item of clip.items) {
        if (!item || !item.type || !item.type.startsWith("image/")) continue;
        const file = item.getAsFile();
        if (!file) continue;
        // Clipboard File objects often have an empty .type on Windows.
        images.push({
          blob: file,
          mime: item.type || file.type || "image/png",
        });
      }
    }
    if (!images.length && clip.files && clip.files.length) {
      for (const file of clip.files) {
        if (file && (!file.type || file.type.startsWith("image/"))) {
          images.push({ blob: file, mime: file.type || "image/png" });
        }
      }
    }
    if (!images.length) return;
    ev.preventDefault();
    importImageBlobs(images);
  });

  window.addEventListener("dragover", (ev) => {
    if (ev.dataTransfer && [...ev.dataTransfer.types].includes("Files")) {
      ev.preventDefault();
    }
  });
  window.addEventListener("drop", (ev) => {
    if (!ev.dataTransfer || !ev.dataTransfer.files || !ev.dataTransfer.files.length) return;
    const files = [...ev.dataTransfer.files].filter(
      (f) => f && (!f.type || f.type.startsWith("image/"))
    );
    if (!files.length) return;
    ev.preventDefault();
    importImageBlobs(files.map((f) => ({ blob: f, mime: f.type || "" })));
  });

  btnPerf.onclick = () => Perf.setHud(!Perf.hud);
  btnPerfExport.onclick = () => {
    const blob = new Blob(
      [
        JSON.stringify(
          {
            exported_at: new Date().toISOString(),
            live: Perf.snapshot(),
            history: Perf.history,
            server_summary: Perf.serverSummary,
          },
          null,
          2
        ),
      ],
      { type: "application/json" }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `apesketch-perf-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  document.getElementById("btn-zoom-in").onclick = () => zoomByButton(ZOOM_STEP);
  document.getElementById("btn-zoom-out").onclick = () => zoomByButton(1 / ZOOM_STEP);
  document.getElementById("btn-zoom-reset").onclick = () => resetView();

  btnPen.onclick = () => setTool("pen");
  btnPen.ondblclick = (ev) => {
    ev.preventDefault();
    setTool("pen");
    toggleStyleDock();
  };
  btnEraseStroke.onclick = () => setTool("erase-stroke");
  btnEraseStroke.ondblclick = (ev) => {
    ev.preventDefault();
    setTool("erase-stroke");
    toggleEraserDock();
  };
  btnErasePartial.onclick = () => setTool("erase-partial");
  btnErasePartial.ondblclick = (ev) => {
    ev.preventDefault();
    setTool("erase-partial");
    toggleEraserDock();
  };

  for (const btn of document.querySelectorAll(".pen-kind")) {
    btn.onclick = () => setInkKind(btn.getAttribute("data-kind") || "pen");
  }
  for (const btn of document.querySelectorAll(".tip-shape")) {
    btn.onclick = () => setInkTip(btn.getAttribute("data-tip") || "round");
  }
  for (const btn of document.querySelectorAll("#color-swatches .swatch")) {
    btn.onclick = () => setInkColor(btn.getAttribute("data-color") || "#000000");
  }
  for (const btn of document.querySelectorAll(".bg-swatch")) {
    btn.onclick = () => setBackground(btn.getAttribute("data-bg") || "#fafaf7");
  }
  if (inkWidthInput) {
    inkWidthInput.oninput = () => setInkWidth(inkWidthInput.value);
  }
  if (eraserSizeInput) {
    eraserSizeInput.oninput = () => setEraserRadius(eraserSizeInput.value);
  }

  btnPan.onclick = () => {
    panMode = !panMode;
    btnPan.classList.toggle("active", panMode);
    updateCursor();
  };

  window.addEventListener("resize", resize);
  canvas.addEventListener("pointerdown", onDown);
  canvas.addEventListener("pointermove", onMove);
  canvas.addEventListener("pointerup", onUp);
  canvas.addEventListener("pointercancel", onUp);
  canvas.addEventListener("contextmenu", (ev) => ev.preventDefault());

  resize();
  updateZoomLabel();
  setTool("pen");
  setStyleDockOpen(false);
  setEraserDockOpen(false);
  setExportDockOpen(false);
  syncRecordButton();
  syncInkKindButtons();
  syncTipButtons();
  syncColorButtons();
  syncBgButtons();
  syncSizeControls();
  applyChromeTheme(pageBackground);
  Perf.start();
  loadPair()
    .then(connectWs)
    .catch((err) => setStatus(String(err)));

  /**
   * Automated erase benchmark for Playwright / console.
   * Builds a dense scene, runs partial-erase stamps, returns timing stats.
   */
  window.__apeSketchBench = {
    getTier: () => OPT_TIER,
    setTier(tier) {
      OPT_TIER = tier === "medium" ? "medium" : "high";
      USE_SPATIAL = OPT_TIER === "medium";
      USE_DECIMATE = OPT_TIER === "medium";
      return { OPT_TIER, USE_SPATIAL, USE_DECIMATE };
    },
    snapshot: () => Perf.snapshot(),
    async runEraseBench({ strokes = 80, pointsPer = 24, stamps = 120 } = {}) {
      sendOp({ op: "clear_page", page_id: "p0" }, { paint: false });
      const seedOps = [];
      for (let s = 0; s < strokes; s++) {
        const sid = `bench-${s}`;
        const pts = [];
        const baseX = (s % 10) * 110;
        const baseY = Math.floor(s / 10) * 80;
        for (let i = 0; i < pointsPer; i++) {
          pts.push([baseX + i * 4, baseY + Math.sin(i / 3) * 18, i * 8, 0.5]);
        }
        seedOps.push({
          op: "add_stroke",
          stroke_id: sid,
          page_id: "p0",
          author: "bench",
          style: { color: "#111111", width: 2.5, kind: "pen" },
          points: pts,
        });
      }
      sendOps(seedOps, { paint: true });
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

      const scene = Perf.scene();
      beginPartialSession(40, 40);
      const stampSamples = [];
      const redrawSamples = [];
      for (let i = 0; i < stamps; i++) {
        const x = 40 + (i % 40) * 12;
        const y = 40 + Math.floor(i / 40) * 20;
        adoptNearby(x, y);
        const t0 = performance.now();
        stampPartial(x, y);
        stampSamples.push(performance.now() - t0);
        const t1 = performance.now();
        redraw(null);
        redrawSamples.push(performance.now() - t1);
      }
      const tCommit = performance.now();
      commitPartialSession();
      const commitMs = performance.now() - tCommit;
      const avg = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0);
      const result = {
        tier: OPT_TIER,
        spatial: USE_SPATIAL,
        decimate: USE_DECIMATE,
        scene,
        stamps,
        stamp_avg_ms: avg(stampSamples),
        stamp_max_ms: Math.max(...stampSamples, 0),
        redraw_avg_ms: avg(redrawSamples),
        redraw_max_ms: Math.max(...redrawSamples, 0),
        commit_ms: commitMs,
        session_strokes: null,
      };
      await fetch("/api/perf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          t: new Date().toISOString(),
          source: "bench",
          opt_tier: OPT_TIER,
          fps: 0,
          scene,
          timings: {
            stamp_ms: { n: stampSamples.length, avg: result.stamp_avg_ms, p95: result.stamp_max_ms, last: stampSamples.at(-1) || 0 },
            redraw_ms: { n: redrawSamples.length, avg: result.redraw_avg_ms, p95: result.redraw_max_ms, last: redrawSamples.at(-1) || 0 },
            commit_ms: { n: 1, avg: commitMs, p95: commitMs, last: commitMs },
          },
          last_gesture: Perf.lastGesture,
        }),
      }).catch(() => {});
      return result;
    },
  };
})();
