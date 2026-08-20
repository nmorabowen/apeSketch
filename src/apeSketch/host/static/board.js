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
  const btnRule = document.getElementById("btn-rule");
  const btnText = document.getElementById("btn-text");
  const textEditor = document.getElementById("text-editor");
  const dockStyle = document.getElementById("dock-style");
  const dockEraser = document.getElementById("dock-eraser");
  const dockRule = document.getElementById("dock-rule");
  const dockText = document.getElementById("dock-text");
  const dockExport = document.getElementById("dock-export");
  const dockSessions = document.getElementById("dock-sessions");
  const sessionTitleInput = document.getElementById("session-title");
  const sessionListEl = document.getElementById("session-list");
  const inkWidthInput = document.getElementById("ink-width");
  const inkWidthLabel = document.getElementById("ink-width-label");
  const eraserSizeInput = document.getElementById("eraser-size");
  const eraserSizeLabel = document.getElementById("eraser-size-label");
  const textSizeInput = document.getElementById("text-size");
  const textSizeLabel = document.getElementById("text-size-label");
  const btnTextBold = document.getElementById("btn-text-bold");
  const btnTextItalic = document.getElementById("btn-text-italic");
  const btnTextBullet = document.getElementById("btn-text-bullet");
  const btnTextNumber = document.getElementById("btn-text-number");
  const btnTextIndent = document.getElementById("btn-text-indent");
  const btnTextOutdent = document.getElementById("btn-text-outdent");
  const fileImageInput = document.getElementById("file-image");
  const fileOpenInput = document.getElementById("file-open");
  const btnRecord = document.getElementById("btn-record");

  let pair = null;
  let ws = null;
  let documentState = null;
  let currentStrokeId = null;
  let lastStrokeId = null;
  let pointBuffer = [];
  let flushTimer = null;
  const author = `web-${Math.random().toString(36).slice(2, 8)}`;
  let activeSessionId = null;
  let activeSessionTitle = "Untitled";
  let sessionCatalog = [];
  let sessionsDockOpen = false;

  const view = { x: 0, y: 0, scale: 1 };
  const MIN_SCALE = 0.1;
  const MAX_SCALE = 8;
  const ZOOM_STEP = 1.15;

  /** @type {"pen"|"erase-stroke"|"erase-partial"|"text"|"rule"} */
  let tool = "pen";
  let toolBeforeEraserTip = "pen";
  let eraserTipActive = false;

  const DEFAULT_RULER_LENGTH = 420;
  const RULE_SNAP_SCREEN_PX = 16;
  const RULER_BODY_SCREEN_PX = 52;

  /**
   * Per-client drawing rule (ADR 0009). Not synced; not in Document.
   * @type {null | {
   *   kind: "ruler"|"guide",
   *   snapEnabled: boolean,
   *   locked?: boolean,
   *   cx?: number, cy?: number, angle?: number, length?: number,
   *   x1?: number, y1?: number, x2?: number, y2?: number
   * }}
   */
  let rule = null;

  /** @type {null | {
   *   mode: string,
   *   startX: number, startY: number,
   *   orig: object,
   *   pointerId: number
   * }} */
  let ruleGesture = null;

  let ruleDockOpen = false;
  let inkLockedToRule = false;

  /** @type {"pen"|"fountain"|"chalk"} */
  let inkKind = "pen";
  let inkTip = "round";
  let inkColor = "#000000";
  let inkWidth = 2.5;
  let pageBackground = "#f4f0e6";
  let styleDockOpen = false;
  let eraserDockOpen = false;
  let textDockOpen = false;
  let exportDockOpen = false;
  const imageElCache = new Map();
  let mediaRecorder = null;
  let recordChunks = [];
  let recording = false;
  let selectedImageId = null;
  let imageGesture = null;
  let imagePress = null;
  let selectedTextId = null;
  let textGesture = null;
  let textPress = null;
  let editingTextId = null;
  let editingTextBaseline = "";
  /** @type {{ textId: string, selectAll: boolean } | null} */
  let pendingTextEdit = null;
  /** @type {{ startX: number, startY: number, curX: number, curY: number, pointerId: number } | null} */
  let textCreateDrag = null;
  let ignoreTextEditorBlur = false;
  const MIN_IMAGE_SIZE = 24;
  const MIN_TEXT_SIZE = 40;
  const DEFAULT_TEXT_WIDTH = 240;
  const DEFAULT_TEXT_HEIGHT = 72;
  const DEFAULT_TEXT_FONT = 28;
  const TEXT_CREATE_DRAG_MIN = 12;
  let textFontSize = DEFAULT_TEXT_FONT;
  let textBold = false;
  let textItalic = false;
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
    if (editingTextId) commitTextEditor();
    if (textCreateDrag) {
      textCreateDrag = null;
      scheduleOverlay();
    }
    if (next !== "rule") ruleGesture = null;
    tool = next;
    btnPen.classList.toggle("active", tool === "pen");
    btnEraseStroke.classList.toggle("active", tool === "erase-stroke");
    btnErasePartial.classList.toggle("active", tool === "erase-partial");
    if (btnRule) btnRule.classList.toggle("active", tool === "rule");
    if (btnText) btnText.classList.toggle("active", tool === "text");
    if (tool === "text") setTextDockOpen(true);
    else setTextDockOpen(false);
    if (tool === "rule") {
      ensureRule();
      setSelectedImage(null);
      setSelectedText(null);
    } else {
      setRuleDockOpen(false);
    }
    updateCursor();
    scheduleOverlay();
  }

  function cloneRuleState(src) {
    return { ...src };
  }

  function ensureRule() {
    if (rule) return rule;
    const c = viewportCenterWorld();
    rule = {
      kind: "ruler",
      cx: c.x,
      cy: c.y,
      angle: 0,
      length: DEFAULT_RULER_LENGTH,
      snapEnabled: true,
      locked: false,
    };
    scheduleOverlay();
    return rule;
  }

  function rulerEndpoints(r) {
    const half = r.length / 2;
    const cos = Math.cos(r.angle);
    const sin = Math.sin(r.angle);
    return {
      a: { x: r.cx - half * cos, y: r.cy - half * sin },
      b: { x: r.cx + half * cos, y: r.cy + half * sin },
    };
  }

  function ruleBandWorld() {
    return RULER_BODY_SCREEN_PX / view.scale;
  }

  function snapToleranceWorld() {
    return RULE_SNAP_SCREEN_PX / view.scale;
  }

  function rulerGeometry(r) {
    const { a, b } = rulerEndpoints(r);
    const ux = Math.cos(r.angle);
    const uy = Math.sin(r.angle);
    return {
      a,
      b,
      ux,
      uy,
      nx: -uy,
      ny: ux,
      body: RULER_BODY_SCREEN_PX / view.scale,
      length: Math.max(40, r.length),
    };
  }

  function worldToRulerLocal(x, y, g) {
    const dx = x - g.a.x;
    const dy = y - g.a.y;
    return { along: dx * g.ux + dy * g.uy, across: dx * g.nx + dy * g.ny };
  }

  function rulerCloseLocal(g) {
    return {
      along: g.length - 16 / view.scale,
      across: g.body * 0.5,
      r: 10 / view.scale,
    };
  }

  function rulerLockLocal(g) {
    const size = 22 / view.scale;
    return {
      along: g.length - 42 / view.scale,
      across: (g.body - size) * 0.5,
      size,
    };
  }

  function toggleRuleLock() {
    if (!rule) return;
    rule.locked = !rule.locked;
    ruleGesture = null;
    scheduleOverlay();
    setStatus(rule.locked ? "ruler locked" : "ruler unlocked");
  }

  function pointOnRulerInk(x, y) {
    if (!rule) return false;
    if (rule.kind === "ruler") {
      const g = rulerGeometry(rule);
      const loc = worldToRulerLocal(x, y, g);
      const pad = snapToleranceWorld();
      return (
        loc.along >= -pad &&
        loc.along <= g.length + pad &&
        loc.across >= -pad &&
        loc.across <= g.body + pad
      );
    }
    const tol = snapToleranceWorld();
    return distPointSeg2(x, y, rule.x1, rule.y1, rule.x2, rule.y2) <= tol * tol;
  }

  function hideRule() {
    const wasRuleTool = tool === "rule";
    rule = null;
    ruleGesture = null;
    inkLockedToRule = false;
    setRuleDockOpen(false);
    scheduleOverlay();
    setStatus("ruler off");
    if (wasRuleTool) setTool("pen");
  }

  function toggleRule() {
    if (rule) {
      hideRule();
      return;
    }
    setTool("rule");
    ensureRule();
  }

  function projectOntoSegment(px, py, ax, ay, bx, by) {
    const abx = bx - ax;
    const aby = by - ay;
    const len2 = abx * abx + aby * aby;
    if (len2 < 1e-9) {
      const d2 = dist2(px, py, ax, ay);
      return { x: ax, y: ay, dist2: d2 };
    }
    let t = ((px - ax) * abx + (py - ay) * aby) / len2;
    t = Math.max(0, Math.min(1, t));
    const x = ax + t * abx;
    const y = ay + t * aby;
    return { x, y, dist2: dist2(px, py, x, y) };
  }

  function projectOntoLine(px, py, ax, ay, bx, by) {
    const abx = bx - ax;
    const aby = by - ay;
    const len2 = abx * abx + aby * aby;
    if (len2 < 1e-9) {
      return { x: ax, y: ay, dist2: dist2(px, py, ax, ay) };
    }
    const t = ((px - ax) * abx + (py - ay) * aby) / len2;
    const x = ax + t * abx;
    const y = ay + t * aby;
    return { x, y, dist2: dist2(px, py, x, y) };
  }

  function constrainInkPoint(p) {
    if (!rule || !rule.snapEnabled) return p;
    if (tool !== "pen" && !currentStrokeId) return p;
    const glued = inkLockedToRule && currentStrokeId;
    if (!glued && !pointOnRulerInk(p.x, p.y)) return p;
    let proj;
    if (rule.kind === "ruler") {
      const { a, b } = rulerEndpoints(rule);
      proj = projectOntoSegment(p.x, p.y, a.x, a.y, b.x, b.y);
    } else {
      proj = projectOntoLine(p.x, p.y, rule.x1, rule.y1, rule.x2, rule.y2);
    }
    inkLockedToRule = true;
    return { ...p, x: proj.x, y: proj.y };
  }

  function syncRuleFromEndpoints(a, b) {
    rule.cx = (a.x + b.x) / 2;
    rule.cy = (a.y + b.y) / 2;
    rule.angle = Math.atan2(b.y - a.y, b.x - a.x);
    rule.length = Math.max(40, Math.hypot(b.x - a.x, b.y - a.y));
  }

  function setRuleKind(kind) {
    ensureRule();
    if (kind === "guide" && rule.kind === "ruler") {
      const { a, b } = rulerEndpoints(rule);
      rule = {
        kind: "guide",
        x1: a.x,
        y1: a.y,
        x2: b.x,
        y2: b.y,
        snapEnabled: rule.snapEnabled,
        locked: !!rule.locked,
      };
    } else if (kind === "ruler" && rule.kind === "guide") {
      const cx = (rule.x1 + rule.x2) / 2;
      const cy = (rule.y1 + rule.y2) / 2;
      const angle = Math.atan2(rule.y2 - rule.y1, rule.x2 - rule.x1);
      const length = Math.max(40, Math.hypot(rule.x2 - rule.x1, rule.y2 - rule.y1));
      rule = {
        kind: "ruler",
        cx,
        cy,
        angle,
        length,
        snapEnabled: rule.snapEnabled,
        locked: !!rule.locked,
      };
    }
    syncRuleDockControls();
    scheduleOverlay();
  }

  function setRuleSnapEnabled(on) {
    ensureRule();
    rule.snapEnabled = !!on;
    syncRuleDockControls();
    setStatus(rule.snapEnabled ? "rule snap on" : "rule snap off");
    scheduleOverlay();
  }

  function syncRuleDockControls() {
    if (!dockRule) return;
    const kind = rule ? rule.kind : "ruler";
    const snapOn = rule ? rule.snapEnabled : true;
    for (const btn of dockRule.querySelectorAll("[data-rule-kind]")) {
      btn.classList.toggle("active", btn.getAttribute("data-rule-kind") === kind);
    }
    const snapBtn = document.getElementById("btn-rule-snap");
    if (snapBtn) snapBtn.classList.toggle("active", snapOn);
  }

  function setRuleDockOpen(open) {
    ruleDockOpen = !!open;
    if (!dockRule) return;
    dockRule.classList.toggle("open", ruleDockOpen);
    if (ruleDockOpen) {
      dockRule.removeAttribute("hidden");
      setStyleDockOpen(false);
      setEraserDockOpen(false);
      setTextDockOpen(false);
      setExportDockOpen(false);
      setSessionsDockOpen(false);
      syncRuleDockControls();
    } else {
      dockRule.setAttribute("hidden", "");
    }
  }

  function toggleRuleDock() {
    setRuleDockOpen(!ruleDockOpen);
  }

  function hitRuleLock(x, y) {
    if (!rule) return false;
    if (rule.kind === "ruler") {
      const g = rulerGeometry(rule);
      const loc = worldToRulerLocal(x, y, g);
      const lock = rulerLockLocal(g);
      return (
        loc.along >= lock.along &&
        loc.along <= lock.along + lock.size &&
        loc.across >= lock.across &&
        loc.across <= lock.across + lock.size
      );
    }
    const mx = (rule.x1 + rule.x2) / 2;
    const my = (rule.y1 + rule.y2) / 2;
    const size = 22 / view.scale;
    return x >= mx - size && x <= mx && y >= my - size / 2 && y <= my + size / 2;
  }

  function hitRuleClose(x, y) {
    if (!rule) return false;
    if (rule.kind === "ruler") {
      const g = rulerGeometry(rule);
      const loc = worldToRulerLocal(x, y, g);
      const c = rulerCloseLocal(g);
      return (loc.along - c.along) ** 2 + (loc.across - c.across) ** 2 <= c.r * c.r;
    }
    const mx = (rule.x1 + rule.x2) / 2;
    const my = (rule.y1 + rule.y2) / 2;
    const r = 12 / view.scale;
    return dist2(x, y, mx, my) <= r * r;
  }

  function hitRuleTarget(x, y) {
    if (!rule) return null;
    if (hitRuleClose(x, y)) return { mode: "close" };
    const hr = handleHitRadius();
    const hr2 = hr * hr;
    if (rule.kind === "ruler") {
      const g = rulerGeometry(rule);
      if (dist2(x, y, g.a.x, g.a.y) <= hr2) return { mode: "end-a" };
      if (dist2(x, y, g.b.x, g.b.y) <= hr2) return { mode: "end-b" };
      const loc = worldToRulerLocal(x, y, g);
      const pad = 6 / view.scale;
      if (loc.along >= -pad && loc.along <= g.length + pad && loc.across >= -pad && loc.across <= g.body + pad) {
        return { mode: "move" };
      }
      return null;
    }
    if (dist2(x, y, rule.x1, rule.y1) <= hr2) return { mode: "guide-a" };
    if (dist2(x, y, rule.x2, rule.y2) <= hr2) return { mode: "guide-b" };
    const band = 14 / view.scale;
    if (distPointSeg2(x, y, rule.x1, rule.y1, rule.x2, rule.y2) <= band * band) {
      return { mode: "move-guide" };
    }
    return null;
  }

  function moveRuleToPoint(x, y) {
    if (!rule) return;
    if (rule.kind === "ruler") {
      rule.cx = x;
      rule.cy = y;
    } else {
      const cx = (rule.x1 + rule.x2) / 2;
      const cy = (rule.y1 + rule.y2) / 2;
      const dx = x - cx;
      const dy = y - cy;
      rule.x1 += dx;
      rule.y1 += dy;
      rule.x2 += dx;
      rule.y2 += dy;
    }
  }

  function applyRuleGesture(p) {
    if (!ruleGesture || !rule || rule.locked) return;
    const dx = p.x - ruleGesture.startX;
    const dy = p.y - ruleGesture.startY;
    const orig = ruleGesture.orig;
    if (rule.kind === "ruler") {
      if (ruleGesture.mode === "move") {
        rule.cx = orig.cx + dx;
        rule.cy = orig.cy + dy;
      } else {
        const ends = rulerEndpoints(orig);
        const fixed = ruleGesture.mode === "end-a" ? ends.b : ends.a;
        const moved = ruleGesture.mode === "end-a"
          ? { x: ends.a.x + dx, y: ends.a.y + dy }
          : { x: ends.b.x + dx, y: ends.b.y + dy };
        const a = ruleGesture.mode === "end-a" ? moved : fixed;
        const b = ruleGesture.mode === "end-b" ? moved : fixed;
        syncRuleFromEndpoints(a, b);
      }
    } else if (ruleGesture.mode === "move-guide") {
      rule.x1 = orig.x1 + dx;
      rule.y1 = orig.y1 + dy;
      rule.x2 = orig.x2 + dx;
      rule.y2 = orig.y2 + dy;
    } else if (ruleGesture.mode === "guide-a") {
      rule.x1 = orig.x1 + dx;
      rule.y1 = orig.y1 + dy;
    } else if (ruleGesture.mode === "guide-b") {
      rule.x2 = orig.x2 + dx;
      rule.y2 = orig.y2 + dy;
    }
  }

  function drawRuleOverlay() {
    if (!rule) return;
    const lw = 1 / view.scale;
    const handleR = Math.max(7 / view.scale, 5);

    if (rule.kind === "ruler") {
      const g = rulerGeometry(rule);
      octx.save();
      octx.translate(g.a.x, g.a.y);
      octx.rotate(rule.angle);
      const rad = Math.min(6 / view.scale, g.body * 0.18);
      octx.beginPath();
      octx.moveTo(rad, 0);
      octx.lineTo(g.length - rad, 0);
      octx.arcTo(g.length, 0, g.length, rad, rad);
      octx.lineTo(g.length, g.body - rad);
      octx.arcTo(g.length, g.body, g.length - rad, g.body, rad);
      octx.lineTo(rad, g.body);
      octx.arcTo(0, g.body, 0, g.body - rad, rad);
      octx.lineTo(0, rad);
      octx.arcTo(0, 0, rad, 0, rad);
      octx.closePath();
      octx.fillStyle = "rgba(236, 214, 160, 0.92)";
      octx.fill();
      octx.strokeStyle = "rgba(92, 64, 40, 0.88)";
      octx.lineWidth = 1.4 * lw;
      octx.stroke();

      octx.beginPath();
      octx.moveTo(0, 0);
      octx.lineTo(g.length, 0);
      octx.strokeStyle = "rgba(47, 32, 18, 0.95)";
      octx.lineWidth = 2.2 * lw;
      octx.stroke();

      const minor = 8 / view.scale;
      const majorEvery = 5;
      let i = 0;
      octx.strokeStyle = "rgba(70, 48, 28, 0.85)";
      octx.fillStyle = "rgba(70, 48, 28, 0.9)";
      octx.font = `${Math.max(9 / view.scale, 7)}px "Segoe UI", system-ui, sans-serif`;
      octx.textAlign = "center";
      octx.textBaseline = "top";
      for (let t = 0; t <= g.length - 28 / view.scale; t += minor) {
        const major = i % majorEvery === 0;
        const h = (major ? g.body * 0.42 : g.body * 0.22);
        octx.beginPath();
        octx.moveTo(t, 0);
        octx.lineTo(t, h);
        octx.lineWidth = (major ? 1.4 : 1) * lw;
        octx.stroke();
        if (major && i > 0) {
          octx.fillText(String(i / majorEvery), t, h + 2 / view.scale);
        }
        i += 1;
      }

      const lock = rulerLockLocal(g);
      drawPadlockAt(lock.along, lock.across, lock.size, !!rule.locked);

      const c = rulerCloseLocal(g);
      octx.beginPath();
      octx.arc(c.along, c.across, c.r, 0, Math.PI * 2);
      octx.fillStyle = "rgba(252, 248, 236, 0.96)";
      octx.fill();
      octx.strokeStyle = "rgba(92, 64, 40, 0.9)";
      octx.lineWidth = 1.3 * lw;
      octx.stroke();
      const arm = c.r * 0.45;
      octx.beginPath();
      octx.moveTo(c.along - arm, c.across - arm);
      octx.lineTo(c.along + arm, c.across + arm);
      octx.moveTo(c.along + arm, c.across - arm);
      octx.lineTo(c.along - arm, c.across + arm);
      octx.stroke();
      octx.restore();

      if (!rule.locked) {
        for (const pt of [g.a, g.b]) {
          octx.beginPath();
          octx.arc(pt.x, pt.y, handleR, 0, Math.PI * 2);
          octx.fillStyle = "rgba(252, 248, 236, 0.96)";
          octx.fill();
          octx.strokeStyle = "rgba(92, 64, 40, 0.9)";
          octx.lineWidth = 1.4 * lw;
          octx.stroke();
        }
      }
    } else {
      const dx = rule.x2 - rule.x1;
      const dy = rule.y2 - rule.y1;
      const len = Math.hypot(dx, dy) || 1;
      const ux = dx / len;
      const uy = dy / len;
      const extend = 2400;
      octx.setLineDash([8 / view.scale, 6 / view.scale]);
      octx.strokeStyle = "rgba(92, 64, 40, 0.75)";
      octx.lineWidth = 1.25 * lw;
      octx.beginPath();
      octx.moveTo(rule.x1 - ux * extend, rule.y1 - uy * extend);
      octx.lineTo(rule.x2 + ux * extend, rule.y2 + uy * extend);
      octx.stroke();
      octx.setLineDash([]);
      octx.beginPath();
      octx.moveTo(rule.x1, rule.y1);
      octx.lineTo(rule.x2, rule.y2);
      octx.lineWidth = 2.5 * lw;
      octx.stroke();
      for (const pt of [{ x: rule.x1, y: rule.y1 }, { x: rule.x2, y: rule.y2 }]) {
        octx.beginPath();
        octx.arc(pt.x, pt.y, handleR, 0, Math.PI * 2);
        octx.fillStyle = "rgba(252, 248, 236, 0.96)";
        octx.fill();
        octx.strokeStyle = "rgba(92, 64, 40, 0.9)";
        octx.stroke();
      }
      const mx = (rule.x1 + rule.x2) / 2;
      const my = (rule.y1 + rule.y2) / 2;
      const cr = 10 / view.scale;
      const lockSize = 22 / view.scale;
      drawPadlockAt(mx - lockSize - 4 / view.scale, my - lockSize / 2, lockSize, !!rule.locked);
      octx.beginPath();
      octx.arc(mx, my, cr, 0, Math.PI * 2);
      octx.fillStyle = "rgba(252, 248, 236, 0.96)";
      octx.fill();
      octx.stroke();
      const arm = cr * 0.45;
      octx.beginPath();
      octx.moveTo(mx - arm, my - arm);
      octx.lineTo(mx + arm, my + arm);
      octx.moveTo(mx + arm, my - arm);
      octx.lineTo(mx - arm, my + arm);
      octx.stroke();
    }

    if (!rule.snapEnabled) {
      octx.save();
      octx.font = `${Math.max(10 / view.scale, 8)}px "Segoe UI", system-ui, sans-serif`;
      octx.fillStyle = "rgba(138, 59, 43, 0.9)";
      octx.textAlign = "center";
      if (rule.kind === "ruler") {
        octx.fillText("snap off", rule.cx, rule.cy);
      } else {
        octx.fillText("snap off", (rule.x1 + rule.x2) / 2, (rule.y1 + rule.y2) / 2 - 18 / view.scale);
      }
      octx.restore();
    }
  }

  function drawPadlockAt(x, y, s, locked) {
    octx.fillStyle = locked ? "rgba(47, 93, 80, 0.95)" : "rgba(252, 248, 236, 0.96)";
    octx.strokeStyle = "rgba(47, 93, 80, 0.95)";
    octx.lineWidth = 1.4 / view.scale;
    const rad = Math.max(3 / view.scale, 2);
    octx.beginPath();
    octx.moveTo(x + rad, y);
    octx.arcTo(x + s, y, x + s, y + s, rad);
    octx.arcTo(x + s, y + s, x, y + s, rad);
    octx.arcTo(x, y + s, x, y, rad);
    octx.arcTo(x, y, x + s, y, rad);
    octx.closePath();
    octx.fill();
    octx.stroke();
    const cx = x + s / 2;
    const cy = y + s / 2;
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
      octx.moveTo(cx + bodyW * 0.42, bodyY);
      octx.lineTo(cx + bodyW * 0.42, bodyY - bodyH * 0.15);
    }
    octx.stroke();
  }

  function setStyleDockOpen(open) {
    styleDockOpen = !!open;
    if (!dockStyle) return;
    dockStyle.classList.toggle("open", styleDockOpen);
    if (styleDockOpen) {
      dockStyle.removeAttribute("hidden");
      setEraserDockOpen(false);
      setRuleDockOpen(false);
      setTextDockOpen(false);
      setExportDockOpen(false);
      setSessionsDockOpen(false);
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
      setRuleDockOpen(false);
      setTextDockOpen(false);
      setExportDockOpen(false);
      setSessionsDockOpen(false);
    } else {
      dockEraser.setAttribute("hidden", "");
    }
  }

  function toggleEraserDock() {
    setEraserDockOpen(!eraserDockOpen);
  }

  function setTextDockOpen(open) {
    textDockOpen = !!open;
    if (!dockText) return;
    dockText.classList.toggle("open", textDockOpen);
    if (textDockOpen) {
      dockText.removeAttribute("hidden");
      setStyleDockOpen(false);
      setEraserDockOpen(false);
      setRuleDockOpen(false);
      setExportDockOpen(false);
      setSessionsDockOpen(false);
      syncTextStyleControls();
    } else {
      dockText.setAttribute("hidden", "");
    }
  }

  function toggleTextDock() {
    setTextDockOpen(!textDockOpen);
  }

  function setExportDockOpen(open) {
    exportDockOpen = !!open;
    if (!dockExport) return;
    dockExport.classList.toggle("open", exportDockOpen);
    if (exportDockOpen) {
      dockExport.removeAttribute("hidden");
      setStyleDockOpen(false);
      setEraserDockOpen(false);
      setRuleDockOpen(false);
      setTextDockOpen(false);
      setSessionsDockOpen(false);
    } else {
      dockExport.setAttribute("hidden", "");
    }
  }

  function toggleExportDock() {
    setExportDockOpen(!exportDockOpen);
  }

  function setSessionsDockOpen(open) {
    sessionsDockOpen = !!open;
    if (!dockSessions) return;
    dockSessions.classList.toggle("open", sessionsDockOpen);
    if (sessionsDockOpen) {
      dockSessions.removeAttribute("hidden");
      setStyleDockOpen(false);
      setEraserDockOpen(false);
      setRuleDockOpen(false);
      setTextDockOpen(false);
      setExportDockOpen(false);
      refreshSessions().catch(() => {});
    } else {
      dockSessions.setAttribute("hidden", "");
    }
  }

  function toggleSessionsDock() {
    setSessionsDockOpen(!sessionsDockOpen);
  }

  function formatSessionWhen(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function applySessionInfo(info) {
    if (!info) return;
    if (typeof info.active_id === "string" || info.active_id === null) {
      activeSessionId = info.active_id || null;
    }
    if (typeof info.title === "string") {
      activeSessionTitle = info.title || "Untitled";
    }
    if (Array.isArray(info.sessions)) {
      sessionCatalog = info.sessions;
    }
    if (sessionTitleInput && document.activeElement !== sessionTitleInput) {
      sessionTitleInput.value = activeSessionTitle;
    }
    renderSessionList();
  }

  function renderSessionList() {
    if (!sessionListEl) return;
    sessionListEl.innerHTML = "";
    if (!sessionCatalog.length) {
      const empty = document.createElement("div");
      empty.className = "label";
      empty.textContent = "No saved sessions yet";
      sessionListEl.appendChild(empty);
      return;
    }
    for (const item of sessionCatalog) {
      const row = document.createElement("div");
      row.className = "session-item" + (item.id === activeSessionId ? " active" : "");
      row.setAttribute("role", "listitem");

      const openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.style.cssText =
        "flex:1;min-width:0;border:0;background:transparent;color:inherit;text-align:left;cursor:pointer;padding:0;font:inherit;";
      openBtn.title = "Open session";
      const meta = document.createElement("span");
      meta.className = "meta";
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = item.title || "Untitled";
      const when = document.createElement("span");
      when.className = "when";
      when.textContent = formatSessionWhen(item.updated_at);
      meta.appendChild(name);
      meta.appendChild(when);
      openBtn.appendChild(meta);
      openBtn.onclick = () => {
        loadSession(item.id).catch((err) => setStatus(String(err.message || err)));
      };

      const del = document.createElement("button");
      del.type = "button";
      del.className = "del";
      del.title = "Delete";
      del.textContent = "×";
      del.disabled = item.id === activeSessionId;
      del.onclick = (ev) => {
        ev.stopPropagation();
        deleteSession(item.id).catch((err) => setStatus(String(err.message || err)));
      };

      row.appendChild(openBtn);
      row.appendChild(del);
      sessionListEl.appendChild(row);
    }
  }

  async function refreshSessions() {
    const res = await fetch("/api/sessions");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `sessions failed (${res.status})`);
    applySessionInfo(data);
    return data;
  }

  async function postSession(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      data = null;
    }
    if (!res.ok) {
      throw new Error((data && data.error) || `request failed (${res.status})`);
    }
    applySessionInfo(data);
    if (data && data.snapshot) applySnapshotMessage(data.snapshot);
    return data;
  }

  async function saveSessionNow() {
    const title = sessionTitleInput ? sessionTitleInput.value.trim() : activeSessionTitle;
    const data = await postSession("/api/sessions/save", { title: title || "Untitled" });
    setStatus(`saved · ${data.session && data.session.title ? data.session.title : "session"}`);
  }

  async function newSession() {
    const title = sessionTitleInput ? sessionTitleInput.value.trim() : "";
    await postSession("/api/sessions/new", title ? { title } : {});
    setStatus("new session");
  }

  async function loadSession(id) {
    if (!id || id === activeSessionId) return;
    await postSession("/api/sessions/load", { id });
    setStatus(`opened · ${activeSessionTitle}`);
  }

  async function openDocumentFile(file) {
    if (!file) return;
    let parsed;
    try {
      parsed = JSON.parse(await file.text());
    } catch (_) {
      throw new Error("invalid JSON file");
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("document JSON must be an object");
    }
    await postSession("/api/sessions/open", {
      document: parsed,
      filename: file.name,
    });
    setStatus(`opened · ${activeSessionTitle}`);
  }

  function openDocumentFilePicker() {
    if (fileOpenInput) fileOpenInput.click();
  }

  async function deleteSession(id) {
    if (!id || id === activeSessionId) return;
    await postSession("/api/sessions/delete", { id });
    setStatus("session deleted");
  }

  async function renameActiveSession() {
    if (!activeSessionId || !sessionTitleInput) return;
    const title = sessionTitleInput.value.trim() || "Untitled";
    await postSession("/api/sessions/rename", { id: activeSessionId, title });
  }

  function applySnapshotMessage(msg) {
    if (!msg || !msg.document) return;
    documentState = msg.document;
    if (msg.session) {
      activeSessionId = msg.session.id || null;
      activeSessionTitle = msg.session.title || "Untitled";
      if (sessionTitleInput && document.activeElement !== sessionTitleInput) {
        sessionTitleInput.value = activeSessionTitle;
      }
    }
    setSelectedImage(null);
    setSelectedText(null);
    if (textEditor && !textEditor.hidden) {
      textEditor.hidden = true;
      textEditor.setAttribute("hidden", "");
      textEditor.innerHTML = "";
    }
    editingTextId = null;
    editingTextBaseline = "";
    currentStrokeId = null;
    livePoints = null;
    pointBuffer = [];
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
    const hex = normalizeHex(color) || "#f4f0e6";
    document.documentElement.style.setProperty("--paper", hex);
    document.body.classList.toggle("theme-dark", isDarkBackground(hex));
  }

  function applyPageBackground(color) {
    const hex = normalizeHex(color) || "#f4f0e6";
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
    const hex = normalizeHex(color) || "#f4f0e6";
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

  function pointerWorldRaw(ev) {
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

  function pointerWorld(ev) {
    return constrainInkPoint(pointerWorldRaw(ev));
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

  function textFontCss(fontSize, bold, italic) {
    const style = italic ? "italic" : "normal";
    const weight = bold ? "700" : "400";
    return `${style} ${weight} ${fontSize}px "Segoe UI", system-ui, sans-serif`;
  }

  function ensureTextBlocks(text) {
    if (!text) return [{ kind: "p", indent: 0, runs: [{ text: "" }] }];
    if (Array.isArray(text.blocks) && text.blocks.length) return text.blocks;
    const lines = String(text.content || "").split("\n");
    return lines.map((line) => ({
      kind: "p",
      indent: 0,
      runs: [{ text: line }],
    }));
  }

  function flattenBlocksPlain(blocks) {
    return (blocks || []).map((b) => (b.runs || []).map((r) => r.text || "").join("")).join("\n");
  }

  function resolveRunStyle(run, text) {
    return {
      text: run.text || "",
      font_size: run.font_size != null ? run.font_size : text.font_size || DEFAULT_TEXT_FONT,
      bold: run.bold != null ? !!run.bold : !!text.bold,
      italic: run.italic != null ? !!run.italic : !!text.italic,
      color: run.color != null ? run.color : text.color || "#111111",
    };
  }

  function measureRunsWidth(targetCtx, runs, text) {
    let w = 0;
    for (const run of runs) {
      const style = resolveRunStyle(run, text);
      targetCtx.font = textFontCss(style.font_size, style.bold, style.italic);
      w += targetCtx.measureText(style.text).width;
    }
    return w;
  }

  /** Wrap a block's runs into visual lines of {runs, height}. */
  function wrapBlockRuns(targetCtx, block, text, maxWidth) {
    const lines = [];
    let lineRuns = [];
    let lineWidth = 0;
    let lineHeight = text.font_size || DEFAULT_TEXT_FONT;

    function pushLine() {
      if (!lineRuns.length) {
        lines.push({
          runs: [{ text: "", font_size: lineHeight, bold: false, italic: false, color: text.color }],
          height: lineHeight * 1.25,
        });
      } else {
        lines.push({ runs: lineRuns, height: lineHeight * 1.25 });
      }
      lineRuns = [];
      lineWidth = 0;
      lineHeight = text.font_size || DEFAULT_TEXT_FONT;
    }

    const allRuns = block.runs && block.runs.length ? block.runs : [{ text: "" }];
    for (const raw of allRuns) {
      const style = resolveRunStyle(raw, text);
      const parts = style.text.split(/(\s+)/);
      for (const part of parts) {
        if (!part) continue;
        targetCtx.font = textFontCss(style.font_size, style.bold, style.italic);
        const partW = targetCtx.measureText(part).width;
        if (lineRuns.length && lineWidth + partW > maxWidth && !/^\s+$/.test(part)) {
          pushLine();
        }
        lineRuns.push({
          text: part,
          font_size: style.font_size,
          bold: style.bold,
          italic: style.italic,
          color: style.color,
        });
        lineWidth += partW;
        lineHeight = Math.max(lineHeight, style.font_size);
      }
    }
    pushLine();
    return lines;
  }

  function drawPageTexts(page) {
    if (!page || !page.text_order || !page.texts) return;
    ctx.save();
    for (const tid of page.text_order) {
      if (tid === editingTextId) continue;
      const text = page.texts[tid];
      if (!text) continue;
      ctx.save();
      ctx.beginPath();
      ctx.rect(text.x, text.y, text.width, text.height);
      ctx.clip();

      const blocks = ensureTextBlocks(text);
      let y = text.y + 4;
      const olCounters = {};
      for (const block of blocks) {
        const indentPx = 18 * (block.indent || 0);
        let marker = "";
        if (block.kind === "ul") marker = "•";
        else if (block.kind === "ol") {
          olCounters[block.indent || 0] = (olCounters[block.indent || 0] || 0) + 1;
          for (const k of Object.keys(olCounters)) {
            if (Number(k) > (block.indent || 0)) delete olCounters[k];
          }
          marker = `${olCounters[block.indent || 0]}.`;
        }
        const markerW = marker ? 18 : 0;
        const maxW = Math.max(8, text.width - 8 - indentPx - markerW);
        const lines = wrapBlockRuns(ctx, block, text, maxW);
        for (const line of lines) {
          if (y > text.y + text.height) break;
          let x = text.x + 4 + indentPx;
          if (marker) {
            const fs = text.font_size || DEFAULT_TEXT_FONT;
            ctx.font = textFontCss(fs * 0.9, false, false);
            ctx.fillStyle = text.color || "#111111";
            ctx.textBaseline = "top";
            ctx.fillText(marker, x, y);
            x += markerW;
            marker = ""; // only first line of block
          }
          for (const run of line.runs) {
            ctx.font = textFontCss(run.font_size, run.bold, run.italic);
            ctx.fillStyle = run.color;
            ctx.textBaseline = "top";
            ctx.fillText(run.text, x, y);
            x += ctx.measureText(run.text).width;
          }
          y += line.height;
        }
        y += 2;
      }
      ctx.restore();
    }
    ctx.restore();
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function runToHtml(run, text) {
    const style = resolveRunStyle(run, text);
    let inner = escapeHtml(style.text).replace(/\n/g, "<br>");
    const needsSpan =
      run.font_size != null ||
      run.color != null ||
      (run.bold != null && run.bold !== !!text.bold) ||
      (run.italic != null && run.italic !== !!text.italic);
    if (needsSpan || run.font_size != null) {
      const css = [
        run.font_size != null ? `font-size:${run.font_size}px` : "",
        run.color != null ? `color:${run.color}` : "",
      ]
        .filter(Boolean)
        .join(";");
      const attrs = run.font_size != null ? ` data-fs="${run.font_size}"` : "";
      inner = `<span${attrs}${css ? ` style="${css}"` : ""}>${inner}</span>`;
    }
    if (style.bold) inner = `<b>${inner}</b>`;
    if (style.italic) inner = `<i>${inner}</i>`;
    return inner;
  }

  function blocksToHtml(blocks, text) {
    const parts = [];
    let i = 0;
    while (i < blocks.length) {
      const block = blocks[i];
      if (block.kind === "ul" || block.kind === "ol") {
        const kind = block.kind;
        const indent = block.indent || 0;
        const tag = kind === "ul" ? "ul" : "ol";
        const items = [];
        while (
          i < blocks.length &&
          blocks[i].kind === kind &&
          (blocks[i].indent || 0) === indent
        ) {
          const html = (blocks[i].runs || [])
            .map((r) => runToHtml(r, text))
            .join("");
          items.push(
            `<li style="margin-left:${indent * 18}px">${html || "<br>"}</li>`
          );
          i++;
        }
        parts.push(`<${tag}>${items.join("")}</${tag}>`);
        continue;
      }
      const html = (block.runs || []).map((r) => runToHtml(r, text)).join("");
      const pad = block.indent ? ` style="margin-left:${block.indent * 18}px"` : "";
      parts.push(`<p${pad}>${html || "<br>"}</p>`);
      i++;
    }
    return parts.join("") || "<p><br></p>";
  }

  function parseInlineRuns(node, inherited) {
    const runs = [];
    function walk(n, style) {
      if (n.nodeType === Node.TEXT_NODE) {
        const t = n.textContent || "";
        if (!t) return;
        runs.push({
          text: t,
          font_size: style.font_size,
          bold: style.bold,
          italic: style.italic,
          color: style.color,
        });
        return;
      }
      if (n.nodeType !== Node.ELEMENT_NODE) return;
      const tag = n.tagName.toLowerCase();
      if (tag === "br") {
        runs.push({ text: "\n", ...style });
        return;
      }
      const next = { ...style };
      if (tag === "b" || tag === "strong") next.bold = true;
      if (tag === "i" || tag === "em") next.italic = true;
      if (n.hasAttribute && n.hasAttribute("data-fs")) {
        const fs = Number(n.getAttribute("data-fs"));
        if (fs > 0) next.font_size = fs;
      }
      if (n.style && n.style.fontSize) {
        const fs = parseFloat(n.style.fontSize);
        if (fs > 0) next.font_size = fs;
      }
      if (n.style && n.style.fontWeight) {
        const w = n.style.fontWeight;
        if (w === "bold" || Number(w) >= 600) next.bold = true;
        if (w === "normal" || Number(w) < 600) next.bold = false;
      }
      if (n.style && n.style.fontStyle === "italic") next.italic = true;
      if (n.style && n.style.fontStyle === "normal") next.italic = false;
      for (const child of n.childNodes) walk(child, next);
    }
    walk(node, inherited);
    if (!runs.length) runs.push({ text: "" });
    // Merge adjacent identical styles
    const merged = [];
    for (const run of runs) {
      const prev = merged[merged.length - 1];
      if (
        prev &&
        prev.font_size === run.font_size &&
        prev.bold === run.bold &&
        prev.italic === run.italic &&
        prev.color === run.color &&
        !prev.text.includes("\n") &&
        !run.text.includes("\n")
      ) {
        prev.text += run.text;
      } else {
        merged.push({ ...run });
      }
    }
    return merged;
  }

  function htmlToBlocks(root, defaults) {
    const blocks = [];
    const base = {
      font_size: null,
      bold: null,
      italic: null,
      color: null,
    };

    function pushParagraph(el, indent) {
      const runs = parseInlineRuns(el, base);
      // Split on hard newlines into multiple p blocks
      let current = [];
      const flush = () => {
        blocks.push({
          kind: "p",
          indent: Math.min(6, Math.max(0, indent || 0)),
          runs: current.length ? current : [{ text: "" }],
        });
        current = [];
      };
      for (const run of runs) {
        const parts = String(run.text).split("\n");
        for (let i = 0; i < parts.length; i++) {
          if (i > 0) flush();
          if (parts[i] || i === 0) {
            current.push({
              text: parts[i],
              font_size: run.font_size,
              bold: run.bold,
              italic: run.italic,
              color: run.color,
            });
          }
        }
      }
      flush();
    }

    function listIndent(el) {
      const ml = el.style && el.style.marginLeft ? parseFloat(el.style.marginLeft) : 0;
      if (ml > 0) return Math.min(6, Math.round(ml / 18));
      return 0;
    }

    const children = [...root.childNodes];
    if (!children.length) {
      return [{ kind: "p", indent: 0, runs: [{ text: "" }] }];
    }
    for (const child of children) {
      if (child.nodeType === Node.TEXT_NODE) {
        const t = (child.textContent || "").trim();
        if (t) pushParagraph(child, 0);
        continue;
      }
      if (child.nodeType !== Node.ELEMENT_NODE) continue;
      const tag = child.tagName.toLowerCase();
      if (tag === "ul" || tag === "ol") {
        const kind = tag === "ul" ? "ul" : "ol";
        for (const li of child.querySelectorAll(":scope > li")) {
          const runs = parseInlineRuns(li, base);
          blocks.push({
            kind,
            indent: listIndent(li),
            runs: runs.length ? runs : [{ text: "" }],
          });
        }
      } else if (tag === "p" || tag === "div") {
        pushParagraph(child, listIndent(child));
      } else {
        pushParagraph(child, 0);
      }
    }
    return blocks.length ? blocks : [{ kind: "p", indent: 0, runs: [{ text: "" }] }];
  }

  function editorHasSelection() {
    if (!textEditor || textEditor.hidden) return false;
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return false;
    if (sel.isCollapsed) return false;
    return textEditor.contains(sel.anchorNode);
  }

  function applyFontSizeToSelection(size) {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return false;
    if (!textEditor || !textEditor.contains(sel.anchorNode)) return false;
    const range = sel.getRangeAt(0);
    const span = document.createElement("span");
    span.setAttribute("data-fs", String(size));
    span.style.fontSize = `${size}px`;
    try {
      range.surroundContents(span);
    } catch (_) {
      const frag = range.extractContents();
      if (frag.querySelectorAll) {
        frag.querySelectorAll("[data-fs]").forEach((el) => {
          const parent = el.parentNode;
          if (!parent) return;
          while (el.firstChild) parent.insertBefore(el.firstChild, el);
          el.remove();
        });
      }
      span.appendChild(frag);
      range.insertNode(span);
    }
    sel.removeAllRanges();
    const next = document.createRange();
    next.selectNodeContents(span);
    sel.addRange(next);
    return true;
  }

  function syncTextStyleControls() {
    // Don't fight the user while they drag the size slider.
    if (textSizeInput && document.activeElement !== textSizeInput) {
      textSizeInput.value = String(textFontSize);
    }
    if (textSizeLabel) textSizeLabel.textContent = String(Math.round(textFontSize));
    if (btnTextBold) btnTextBold.classList.toggle("active", textBold);
    if (btnTextItalic) btnTextItalic.classList.toggle("active", textItalic);
  }

  function applyTextStyleToEditor() {
    if (!textEditor || textEditor.hidden) return;
    const text = editingTextId ? getText(editingTextId) : null;
    const size = (text && text.font_size) || textFontSize;
    textEditor.style.fontSize = `${Math.max(12, size * view.scale)}px`;
    textEditor.style.fontWeight = (text ? text.bold : textBold) ? "700" : "400";
    textEditor.style.fontStyle = (text ? text.italic : textItalic) ? "italic" : "normal";
    if (text) textEditor.style.color = text.color || "#111111";
  }

  function styledTextTargetId() {
    if (editingTextId) return editingTextId;
    if (selectedTextId) return selectedTextId;
    return null;
  }

  function commitTextFontSize(size) {
    const next = Math.max(12, Math.min(96, Number(size) || DEFAULT_TEXT_FONT));
    textFontSize = next;
    if (textSizeLabel) textSizeLabel.textContent = String(Math.round(next));

    if (editingTextId && textEditor && !textEditor.hidden && editorHasSelection()) {
      applyFontSizeToSelection(next);
      return;
    }

    const textId = styledTextTargetId();
    if (textId) {
      const text = getText(textId);
      if (!text || text.locked) {
        setStatus("text locked");
        return;
      }
      if (text.font_size === next) {
        applyTextStyleToEditor();
        return;
      }
      text.font_size = next;
      sendOp({
        op: "set_text_style",
        text_id: textId,
        page_id: "p0",
        font_size: next,
      });
      applyTextStyleToEditor();
      scheduleRedraw();
      return;
    }
    syncTextStyleControls();
  }

  function pushTextStyle(partial) {
    // While editing with a selection, apply to selection (DOM only until commit).
    if (editingTextId && textEditor && !textEditor.hidden) {
      if (partial.bold != null && editorHasSelection()) {
        document.execCommand("bold");
        return;
      }
      if (partial.italic != null && editorHasSelection()) {
        document.execCommand("italic");
        return;
      }
      if (partial.font_size != null) {
        commitTextFontSize(partial.font_size);
        return;
      }
      if ((partial.bold != null || partial.italic != null) && !editorHasSelection()) {
        document.execCommand(partial.bold != null ? "bold" : "italic");
        return;
      }
    }

    if (partial.font_size != null) {
      commitTextFontSize(partial.font_size);
      return;
    }

    const textId = styledTextTargetId();
    if (textId && !editingTextId) {
      const text = getText(textId);
      if (!text || text.locked) {
        setStatus("text locked");
        return;
      }
      if (partial.bold != null) text.bold = partial.bold;
      if (partial.italic != null) text.italic = partial.italic;
      if (partial.color != null) text.color = partial.color;
      sendOp({
        op: "set_text_style",
        text_id: textId,
        page_id: "p0",
        ...partial,
      });
      loadTextStyleFromObject(text);
      scheduleRedraw();
      return;
    }
    if (partial.bold != null) textBold = partial.bold;
    if (partial.italic != null) textItalic = partial.italic;
    syncTextStyleControls();
  }

  function loadTextStyleFromObject(text) {
    if (!text) return;
    textFontSize = text.font_size || DEFAULT_TEXT_FONT;
    textBold = !!text.bold;
    textItalic = !!text.italic;
    syncTextStyleControls();
  }

  function measureContentHeight(text) {
    const blocks = ensureTextBlocks(text);
    let y = 8;
    const probe = document.createElement("canvas").getContext("2d");
    for (const block of blocks) {
      const indentPx = 18 * (block.indent || 0);
      const markerW = block.kind === "ul" || block.kind === "ol" ? 18 : 0;
      const maxW = Math.max(8, text.width - 8 - indentPx - markerW);
      const lines = wrapBlockRuns(probe, block, text, maxW);
      for (const line of lines) y += line.height;
      y += 2;
    }
    return Math.max(MIN_TEXT_SIZE, y);
  }

  function getText(textId) {
    const page = getPage();
    return page && page.texts ? page.texts[textId] : null;
  }

  function setSelectedText(textId) {
    if (selectedImageId) setSelectedImage(null);
    selectedTextId = textId || null;
    if (selectedTextId) loadTextStyleFromObject(getText(selectedTextId));
    scheduleOverlay();
  }

  function setSelectedImage(imageId) {
    if (imageId) {
      if (editingTextId) commitTextEditor();
      selectedTextId = null;
    }
    selectedImageId = imageId || null;
    scheduleOverlay();
  }

  function hitTopTextAt(x, y) {
    const page = getPage();
    if (!page || !page.text_order) return null;
    for (let i = page.text_order.length - 1; i >= 0; i--) {
      const tid = page.text_order[i];
      const text = page.texts && page.texts[tid];
      if (text && pointInImage(text, x, y)) return tid;
    }
    return null;
  }

  function placeTextAt(worldX, worldY, width, height) {
    const textId = `t-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    const fontSize = textFontSize || DEFAULT_TEXT_FONT;
    const blocks = [{ kind: "p", indent: 0, runs: [{ text: "" }] }];
    const w = Math.max(MIN_TEXT_SIZE, width != null ? width : DEFAULT_TEXT_WIDTH);
    const h = Math.max(
      MIN_TEXT_SIZE,
      height != null ? height : Math.max(fontSize * 2.2, DEFAULT_TEXT_HEIGHT)
    );
    sendOp({
      op: "add_text",
      text_id: textId,
      content: "",
      x: worldX,
      y: worldY,
      width: w,
      height: h,
      font_size: fontSize,
      color: inkColor || "#111111",
      bold: textBold,
      italic: textItalic,
      blocks,
      author,
      page_id: "p0",
    });
    setSelectedText(textId);
    return textId;
  }

  function normalizeCreateRect(x0, y0, x1, y1) {
    const x = Math.min(x0, x1);
    const y = Math.min(y0, y1);
    const width = Math.abs(x1 - x0);
    const height = Math.abs(y1 - y0);
    return { x, y, width, height };
  }

  function finishTextCreateDrag() {
    if (!textCreateDrag) return null;
    const drag = textCreateDrag;
    textCreateDrag = null;
    const rect = normalizeCreateRect(drag.startX, drag.startY, drag.curX, drag.curY);
    const dragged =
      rect.width >= TEXT_CREATE_DRAG_MIN || rect.height >= TEXT_CREATE_DRAG_MIN;
    let textId;
    if (dragged) {
      textId = placeTextAt(
        rect.x,
        rect.y,
        Math.max(MIN_TEXT_SIZE, rect.width),
        Math.max(MIN_TEXT_SIZE, rect.height)
      );
    } else {
      textId = placeTextAt(drag.startX, drag.startY);
    }
    scheduleOverlay();
    return textId;
  }

  function worldToScreen(x, y) {
    return { sx: x * view.scale + view.x, sy: y * view.scale + view.y };
  }

  function isTypingInTextEditor() {
    return Boolean(
      editingTextId &&
        textEditor &&
        !textEditor.hidden &&
        (document.activeElement === textEditor || textEditor.contains(document.activeElement))
    );
  }

  function isTypingTarget(el) {
    if (!el || el === document.body || el === document.documentElement || el === canvas) {
      return false;
    }
    if (el === textEditor || (textEditor && textEditor.contains(el))) {
      return isTypingInTextEditor();
    }
    const tag = el.tagName;
    if (tag === "TEXTAREA") return true;
    if (tag === "INPUT") {
      const type = String(el.type || "text").toLowerCase();
      return type === "text" || type === "search" || type === "password" || type === "number";
    }
    return false;
  }

  function shortcutKey(ev) {
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return "";
    const code = ev.code || "";
    if (code.indexOf("Key") === 0) return code.slice(3).toLowerCase();
    return String(ev.key || "").toLowerCase();
  }

  function openTextEditor(textId, selectAll) {
    const text = getText(textId);
    if (!text || !textEditor) return;
    if (text.locked) {
      setStatus("text locked");
      return;
    }
    if (editingTextId && editingTextId !== textId) {
      commitTextEditor();
    }
    editingTextId = textId;
    const blocks = ensureTextBlocks(text);
    editingTextBaseline = JSON.stringify(blocks);
    loadTextStyleFromObject(text);
    const topLeft = worldToScreen(text.x, text.y);
    textEditor.removeAttribute("hidden");
    textEditor.hidden = false;
    textEditor.innerHTML = blocksToHtml(blocks, text);
    textEditor.style.left = `${Math.max(8, topLeft.sx)}px`;
    textEditor.style.top = `${Math.max(8, topLeft.sy)}px`;
    textEditor.style.width = `${Math.max(80, text.width * view.scale)}px`;
    textEditor.style.height = `${Math.max(40, text.height * view.scale)}px`;
    textEditor.style.fontSize = `${Math.max(12, (text.font_size || DEFAULT_TEXT_FONT) * view.scale)}px`;
    textEditor.style.fontWeight = text.bold ? "700" : "400";
    textEditor.style.fontStyle = text.italic ? "italic" : "normal";
    textEditor.style.color = text.color || "#111111";
    textEditor.style.pointerEvents = "auto";
    setTextDockOpen(true);
    ignoreTextEditorBlur = true;
    scheduleRedraw();
    requestAnimationFrame(() => {
      textEditor.focus({ preventScroll: true });
      if (selectAll) {
        const range = document.createRange();
        range.selectNodeContents(textEditor);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      }
      ignoreTextEditorBlur = false;
    });
  }

  function commitTextEditor() {
    if (!editingTextId || !textEditor) return;
    const textId = editingTextId;
    const text = getText(textId);
    const blocks = htmlToBlocks(textEditor, text || {});
    const content = flattenBlocksPlain(blocks);
    const baseline = editingTextBaseline;
    editingTextId = null;
    editingTextBaseline = "";
    textEditor.hidden = true;
    textEditor.setAttribute("hidden", "");
    textEditor.innerHTML = "";
    if (!text) {
      scheduleRedraw();
      return;
    }
    text.blocks = blocks;
    text.content = content;
    const needed = measureContentHeight(text);
    if (needed > text.height) {
      text.height = needed;
      sendOp({
        op: "transform_text",
        text_id: textId,
        x: text.x,
        y: text.y,
        width: text.width,
        height: text.height,
        page_id: "p0",
      });
    }
    const serialized = JSON.stringify(blocks);
    if (serialized !== baseline) {
      sendOp({
        op: "set_text_content",
        text_id: textId,
        content,
        blocks,
        page_id: "p0",
      });
    } else {
      scheduleRedraw();
    }
  }

  function applyTextBoxLocal(textId, box) {
    const text = getText(textId);
    if (!text || text.locked) return;
    text.x = box.x;
    text.y = box.y;
    text.width = box.width;
    text.height = box.height;
  }

  function commitTextTransform(textId) {
    const text = getText(textId);
    if (!text || text.locked) return;
    sendOp({
      op: "transform_text",
      text_id: textId,
      x: text.x,
      y: text.y,
      width: text.width,
      height: text.height,
      page_id: "p0",
    });
  }

  function toggleTextLock(textId) {
    const text = getText(textId);
    if (!text) return;
    sendOp({
      op: "set_text_lock",
      text_id: textId,
      locked: !text.locked,
      page_id: "p0",
    });
    setStatus(text.locked ? "text unlocked" : "text locked");
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

  function clearTextPress() {
    if (textPress && textPress.timer) clearTimeout(textPress.timer);
    textPress = null;
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
    const selectedImage = selectedImageId ? getImage(selectedImageId) : null;
    const selectedText = selectedTextId ? getText(selectedTextId) : null;
    const selected = selectedImage || selectedText;
    if (!selected && !eraserCursor && !textCreateDrag && !rule) return;
    octx.save();
    octx.translate(view.x, view.y);
    octx.scale(view.scale, view.scale);

    if (textCreateDrag) {
      const rect = normalizeCreateRect(
        textCreateDrag.startX,
        textCreateDrag.startY,
        textCreateDrag.curX,
        textCreateDrag.curY
      );
      octx.strokeStyle = "rgba(47, 93, 80, 0.85)";
      octx.fillStyle = "rgba(47, 93, 80, 0.08)";
      octx.lineWidth = 1.5 / view.scale;
      octx.setLineDash([6 / view.scale, 4 / view.scale]);
      octx.fillRect(rect.x, rect.y, rect.width, rect.height);
      octx.strokeRect(rect.x, rect.y, rect.width, rect.height);
      octx.setLineDash([]);
    }

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
          const pt = points[id];
          octx.fillRect(pt.x - hs / 2, pt.y - hs / 2, hs, hs);
          octx.strokeStyle = "rgba(47, 93, 80, 0.95)";
          octx.strokeRect(pt.x - hs / 2, pt.y - hs / 2, hs, hs);
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

    if (rule) drawRuleOverlay();

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
    pageBackground = (page && page.background) || pageBackground || "#f4f0e6";
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
    drawPageTexts(page);

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
      page.texts = {};
      page.text_order = [];
      setSelectedImage(null);
      setSelectedText(null);
      if (editingTextId) {
        editingTextId = null;
        if (textEditor) textEditor.hidden = true;
      }
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
    } else if (op.op === "add_text") {
      if (!page.texts) page.texts = {};
      if (!page.text_order) page.text_order = [];
      if (!page.texts[op.text_id]) {
        const blocks =
          Array.isArray(op.blocks) && op.blocks.length
            ? op.blocks
            : [{ kind: "p", indent: 0, runs: [{ text: op.content || "" }] }];
        page.texts[op.text_id] = {
          text_id: op.text_id,
          content: op.content || flattenBlocksPlain(blocks),
          x: op.x,
          y: op.y,
          width: op.width,
          height: op.height,
          font_size: op.font_size || DEFAULT_TEXT_FONT,
          color: op.color || "#111111",
          bold: !!op.bold,
          italic: !!op.italic,
          author: op.author || "",
          layer: op.layer || "text",
          locked: false,
          blocks,
        };
        page.text_order.push(op.text_id);
      }
    } else if (op.op === "set_text_content") {
      const text = page.texts && page.texts[op.text_id];
      if (text && !text.locked) {
        text.content = op.content || "";
        if (Array.isArray(op.blocks)) text.blocks = op.blocks;
        else text.blocks = [{ kind: "p", indent: 0, runs: [{ text: text.content }] }];
      }
    } else if (op.op === "set_text_style") {
      const text = page.texts && page.texts[op.text_id];
      if (text && !text.locked) {
        if (op.font_size != null) text.font_size = op.font_size;
        if (op.color != null) text.color = op.color;
        if (op.bold != null) text.bold = !!op.bold;
        if (op.italic != null) text.italic = !!op.italic;
        if (editingTextId === op.text_id || selectedTextId === op.text_id) {
          if (document.activeElement !== textSizeInput) {
            loadTextStyleFromObject(text);
          }
          applyTextStyleToEditor();
        }
      }
    } else if (op.op === "transform_text") {
      const text = page.texts && page.texts[op.text_id];
      if (text && !text.locked) {
        text.x = op.x;
        text.y = op.y;
        text.width = op.width;
        text.height = op.height;
        if (op.font_size) text.font_size = op.font_size;
      }
    } else if (op.op === "erase_text") {
      if (page.texts) delete page.texts[op.text_id];
      if (page.text_order) {
        page.text_order = page.text_order.filter((id) => id !== op.text_id);
      }
      if (selectedTextId === op.text_id) setSelectedText(null);
      if (editingTextId === op.text_id) {
        editingTextId = null;
        if (textEditor) textEditor.hidden = true;
      }
    } else if (op.op === "set_text_lock") {
      const text = page.texts && page.texts[op.text_id];
      if (text) text.locked = !!op.locked;
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
        applySnapshotMessage(msg);
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
    inkLockedToRule = false;
  }

  function eraseWholeAt(x, y) {
    const page = documentState && documentState.pages.p0;
    if (!page) return false;
    let hit = false;
    const texts = page.text_order || [];
    for (let i = texts.length - 1; i >= 0; i--) {
      const tid = texts[i];
      const text = page.texts && page.texts[tid];
      if (!text) continue;
      if (pointInImage(text, x, y)) {
        queueSyncOp({ op: "erase_text", text_id: tid, page_id: "p0" });
        return true;
      }
    }
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

    if (typeof canvas.focus === "function") {
      try {
        canvas.focus({ preventScroll: true });
      } catch (_) {
        canvas.focus();
      }
    }

    const raw = pointerWorldRaw(ev);
    const p = constrainInkPoint(raw);
    eraserCursor =
      tool === "erase-stroke" || tool === "erase-partial" ? { x: p.x, y: p.y } : null;

    if (rule) {
      if (hitRuleLock(raw.x, raw.y)) {
        toggleRuleLock();
        ev.preventDefault();
        return;
      }
      if (hitRuleClose(raw.x, raw.y)) {
        hideRule();
        ev.preventDefault();
        return;
      }
      if (tool === "rule" && !rule.locked) {
        const hit = hitRuleTarget(raw.x, raw.y);
        if (hit && hit.mode !== "close") {
          try {
            canvas.setPointerCapture(ev.pointerId);
          } catch (_) {}
          ruleGesture = {
            mode: hit.mode,
            startX: raw.x,
            startY: raw.y,
            orig: cloneRuleState(rule),
            pointerId: ev.pointerId,
          };
          setStatus("adjust ruler");
          ev.preventDefault();
          return;
        }
      }
    }

    if (tool === "rule") {
      ev.preventDefault();
      return;
    }

    // Text tool: drag to size a new box, or click existing to edit.
    if (tool === "text") {
      const hitText = hitTopTextAt(p.x, p.y);
      if (hitText) {
        setSelectedText(hitText);
        pendingTextEdit = { textId: hitText, selectAll: false };
        ev.preventDefault();
        return;
      }
      try {
        canvas.setPointerCapture(ev.pointerId);
      } catch (_) {}
      textCreateDrag = {
        startX: p.x,
        startY: p.y,
        curX: p.x,
        curY: p.y,
        pointerId: ev.pointerId,
      };
      scheduleOverlay();
      setStatus("drag to size text box");
      ev.preventDefault();
      return;
    }

    try {
      canvas.setPointerCapture(ev.pointerId);
    } catch (_) {}

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

    // Text tool handled above.
    if (tool === "pen") {
      const selectedImg = selectedImageId ? getImage(selectedImageId) : null;
      const selectedTxt = selectedTextId ? getText(selectedTextId) : null;

      if (selectedTxt) {
        if (hitImageLockIcon(selectedTxt, p.x, p.y)) {
          toggleTextLock(selectedTextId);
          ev.preventDefault();
          return;
        }
        if (!selectedTxt.locked) {
          const handle = hitImageHandle(selectedTxt, p.x, p.y);
          if (handle) {
            textGesture = {
              mode: "resize",
              textId: selectedTextId,
              handle,
              keepAspect: false,
              startX: p.x,
              startY: p.y,
              orig: {
                x: selectedTxt.x,
                y: selectedTxt.y,
                width: selectedTxt.width,
                height: selectedTxt.height,
              },
            };
            ev.preventDefault();
            return;
          }
          if (pointInImage(selectedTxt, p.x, p.y)) {
            if (ev.detail >= 2) {
              try {
                canvas.releasePointerCapture(ev.pointerId);
              } catch (_) {}
              pendingTextEdit = { textId: selectedTextId, selectAll: false };
              ev.preventDefault();
              return;
            }
            textGesture = {
              mode: "move",
              textId: selectedTextId,
              startX: p.x,
              startY: p.y,
              orig: {
                x: selectedTxt.x,
                y: selectedTxt.y,
                width: selectedTxt.width,
                height: selectedTxt.height,
              },
            };
            ev.preventDefault();
            return;
          }
        } else if (pointInImage(selectedTxt, p.x, p.y)) {
          ev.preventDefault();
          return;
        }
      }

      if (selectedImg) {
        if (hitImageLockIcon(selectedImg, p.x, p.y)) {
          toggleImageLock(selectedImageId);
          ev.preventDefault();
          return;
        }
        if (!selectedImg.locked) {
          const handle = hitImageHandle(selectedImg, p.x, p.y);
          if (handle) {
            imageGesture = {
              mode: "resize",
              imageId: selectedImageId,
              handle,
              keepAspect: IMAGE_CORNER_HANDLES.has(handle),
              startX: p.x,
              startY: p.y,
              orig: {
                x: selectedImg.x,
                y: selectedImg.y,
                width: selectedImg.width,
                height: selectedImg.height,
              },
            };
            ev.preventDefault();
            return;
          }
          if (pointInImage(selectedImg, p.x, p.y)) {
            imageGesture = {
              mode: "move",
              imageId: selectedImageId,
              startX: p.x,
              startY: p.y,
              orig: {
                x: selectedImg.x,
                y: selectedImg.y,
                width: selectedImg.width,
                height: selectedImg.height,
              },
            };
            ev.preventDefault();
            return;
          }
        } else if (pointInImage(selectedImg, p.x, p.y)) {
          ev.preventDefault();
          return;
        }
      }

      const hitTextId = hitTopTextAt(p.x, p.y);
      if (hitTextId) {
        const screen = pointerScreen(ev);
        clearImagePress();
        textPress = {
          textId: hitTextId,
          startX: p.x,
          startY: p.y,
          sx: screen.sx,
          sy: screen.sy,
          pointerId: ev.pointerId,
          t: p.t,
          pressure: p.pressure,
          armed: false,
        };
        textPress.timer = setTimeout(() => {
          if (!textPress || textPress.pointerId !== ev.pointerId) return;
          textPress.armed = true;
          setSelectedText(textPress.textId);
          setStatus("text selected");
          scheduleOverlay();
        }, LONG_PRESS_MS);
        ev.preventDefault();
        return;
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
      if (selectedTextId) setSelectedText(null);
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

    const raw = pointerWorldRaw(ev);
    const p = constrainInkPoint(raw);

    if (ruleGesture && ruleGesture.pointerId === ev.pointerId) {
      applyRuleGesture(raw);
      scheduleOverlay();
      ev.preventDefault();
      return;
    }

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

    if (textPress && textPress.pointerId === ev.pointerId) {
      const screen = pointerScreen(ev);
      const moved = Math.hypot(screen.sx - textPress.sx, screen.sy - textPress.sy);
      if (moved > LONG_PRESS_MOVE_PX) {
        const start = {
          x: textPress.startX,
          y: textPress.startY,
          t: textPress.t,
          pressure: textPress.pressure,
        };
        clearTextPress();
        beginStrokeAt(start);
      } else {
        ev.preventDefault();
        return;
      }
    }

    if (textCreateDrag && textCreateDrag.pointerId === ev.pointerId) {
      textCreateDrag.curX = p.x;
      textCreateDrag.curY = p.y;
      scheduleOverlay();
      ev.preventDefault();
      return;
    }

    if (textGesture) {
      const dx = p.x - textGesture.startX;
      const dy = p.y - textGesture.startY;
      const orig = textGesture.orig;
      let box;
      if (textGesture.mode === "resize") {
        // Box is a window: geometry only — never scale font with the frame.
        box = resizeFromHandle(orig, textGesture.handle, dx, dy, false);
      } else {
        box = {
          x: orig.x + dx,
          y: orig.y + dy,
          width: orig.width,
          height: orig.height,
        };
      }
      applyTextBoxLocal(textGesture.textId, box);
      scheduleRedraw();
      scheduleOverlay();
      ev.preventDefault();
      return;
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

    if (textCreateDrag && textCreateDrag.pointerId === ev.pointerId) {
      try {
        canvas.releasePointerCapture(ev.pointerId);
      } catch (_) {}
      const textId = finishTextCreateDrag();
      if (textId) {
        pendingTextEdit = { textId, selectAll: true };
        requestAnimationFrame(() => {
          openTextEditor(textId, true);
          pendingTextEdit = null;
        });
      }
      ev.preventDefault();
      return;
    }

    if (pendingTextEdit) {
      const pending = pendingTextEdit;
      pendingTextEdit = null;
      try {
        canvas.releasePointerCapture(ev.pointerId);
      } catch (_) {}
      requestAnimationFrame(() => {
        openTextEditor(pending.textId, pending.selectAll);
      });
      ev.preventDefault();
      return;
    }

    if (imageGesture) {
      const imageId = imageGesture.imageId;
      imageGesture = null;
      commitImageTransform(imageId);
      scheduleOverlay();
      updateCursor();
      ev.preventDefault();
      return;
    }

    if (textGesture) {
      const textId = textGesture.textId;
      textGesture = null;
      commitTextTransform(textId);
      scheduleOverlay();
      updateCursor();
      ev.preventDefault();
      return;
    }

    if (ruleGesture && ruleGesture.pointerId === ev.pointerId) {
      ruleGesture = null;
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

    if (textPress && textPress.pointerId === ev.pointerId) {
      const wasArmed = textPress.armed;
      clearTextPress();
      if (wasArmed) setStatus("text selected");
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
    if (isTypingTarget(ev.target) || isTypingTarget(document.activeElement)) {
      if (ev.key === "Escape" && editingTextId) {
        commitTextEditor();
        ev.preventDefault();
      }
      return;
    }
    const key = shortcutKey(ev);
    if (ev.code === "Space" && !ev.repeat) {
      spaceHeld = true;
      updateCursor();
      ev.preventDefault();
    }
    if (ev.key === "Escape") {
      if (editingTextId) {
        commitTextEditor();
        ev.preventDefault();
        return;
      }
      if (textCreateDrag) {
        textCreateDrag = null;
        scheduleOverlay();
        setStatus("text create cancelled");
        ev.preventDefault();
        return;
      }
      if (imageGesture) imageGesture = null;
      if (textGesture) textGesture = null;
      if (ruleGesture) ruleGesture = null;
      if (rule) {
        hideRule();
        ev.preventDefault();
        return;
      }
      if (selectedImageId) {
        setSelectedImage(null);
        ev.preventDefault();
      }
      if (selectedTextId) {
        setSelectedText(null);
        ev.preventDefault();
      }
    }
    if (
      (ev.key === "Delete" || ev.key === "Backspace") &&
      !ev.ctrlKey &&
      !ev.metaKey
    ) {
      if (selectedTextId) {
        const textId = selectedTextId;
        sendOp({ op: "erase_text", text_id: textId, page_id: "p0" });
        setSelectedText(null);
        ev.preventDefault();
        return;
      }
      if (selectedImageId) {
        const imageId = selectedImageId;
        sendOp({ op: "erase_image", image_id: imageId, page_id: "p0" });
        setSelectedImage(null);
        ev.preventDefault();
      }
    }
    if (key === "e") {
      setTool(tool === "erase-stroke" ? "erase-partial" : "erase-stroke");
      ev.preventDefault();
    }
    if (key === "b") {
      setTool("pen");
      ev.preventDefault();
    }
    if (key === "r") {
      toggleRule();
      ev.preventDefault();
    }
    if (key === "t") {
      setTool("text");
      ev.preventDefault();
    }
    if (key === "p") {
      Perf.setHud(!Perf.hud);
      ev.preventDefault();
    }
    if ((ev.key === "+" || ev.key === "=") && (ev.ctrlKey || ev.metaKey)) {
      zoomByButton(ZOOM_STEP);
      ev.preventDefault();
    }
    if (ev.key === "-" && (ev.ctrlKey || ev.metaKey)) {
      zoomByButton(1 / ZOOM_STEP);
      ev.preventDefault();
    }
    if (ev.key === "o" && (ev.ctrlKey || ev.metaKey)) {
      openDocumentFilePicker();
      ev.preventDefault();
    }
    if (ev.key === "0" && (ev.ctrlKey || ev.metaKey)) {
      resetView();
      ev.preventDefault();
    }
  });

  window.addEventListener("keyup", (ev) => {
    if (
      textEditor &&
      (document.activeElement === textEditor ||
        (ev.target && (ev.target.tagName === "TEXTAREA" || ev.target.tagName === "INPUT")))
    ) {
      return;
    }
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
  if (fileOpenInput) {
    fileOpenInput.onchange = () => {
      const file = fileOpenInput.files && fileOpenInput.files[0];
      fileOpenInput.value = "";
      if (!file) return;
      openDocumentFile(file).catch((err) => setStatus(String(err.message || err)));
    };
  }

  document.getElementById("btn-export").onclick = () => toggleExportDock();
  const btnSessions = document.getElementById("btn-sessions");
  if (btnSessions) btnSessions.onclick = () => toggleSessionsDock();
  const btnSessionSave = document.getElementById("btn-session-save");
  const btnSessionNew = document.getElementById("btn-session-new");
  const btnSessionOpen = document.getElementById("btn-session-open");
  if (btnSessionSave) {
    btnSessionSave.onclick = () => {
      saveSessionNow().catch((err) => setStatus(String(err.message || err)));
    };
  }
  if (btnSessionNew) {
    btnSessionNew.onclick = () => {
      newSession().catch((err) => setStatus(String(err.message || err)));
    };
  }
  if (btnSessionOpen) {
    btnSessionOpen.onclick = () => openDocumentFilePicker();
  }
  if (sessionTitleInput) {
    sessionTitleInput.addEventListener("change", () => {
      renameActiveSession().catch((err) => setStatus(String(err.message || err)));
    });
    sessionTitleInput.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        sessionTitleInput.blur();
        ev.preventDefault();
      }
      ev.stopPropagation();
    });
  }
  document.getElementById("btn-export-png").onclick = () => exportViewportPng();
  document.getElementById("btn-export-svg").onclick = () => {
    exportFromApi("/api/export/svg", `apesketch-${Date.now()}.svg`)
      .then(() => setStatus("exported SVG"))
      .catch((err) => setStatus(String(err.message || err)));
  };
  document.getElementById("btn-export-json").onclick = () => {
    exportFromApi("/api/export/json", `apesketch-${Date.now()}.ape.json`)
      .then(() => setStatus("exported JSON"))
      .catch((err) => setStatus(String(err.message || err)));
  };
  if (btnRecord) btnRecord.onclick = () => toggleRecording();

  if (textEditor) {
    textEditor.addEventListener("pointerdown", (ev) => {
      ev.stopPropagation();
    });
    textEditor.addEventListener("mousedown", (ev) => {
      ev.stopPropagation();
    });
    textEditor.addEventListener("blur", () => {
      if (ignoreTextEditorBlur) return;
      setTimeout(() => {
        if (ignoreTextEditorBlur) return;
        if (document.activeElement === textEditor || textEditor.contains(document.activeElement)) {
          return;
        }
        // Don't commit if focus moved to text dock controls.
        const active = document.activeElement;
        if (active && dockText && dockText.contains(active)) {
          ignoreTextEditorBlur = true;
          textEditor.focus({ preventScroll: true });
          ignoreTextEditorBlur = false;
          return;
        }
        commitTextEditor();
      }, 0);
    });
    textEditor.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") {
        commitTextEditor();
        ev.preventDefault();
      }
      if (ev.key === "Tab") {
        ev.preventDefault();
        document.execCommand(ev.shiftKey ? "outdent" : "indent");
      }
      if ((ev.ctrlKey || ev.metaKey) && (ev.key === "b" || ev.key === "B")) {
        document.execCommand("bold");
        ev.preventDefault();
      }
      if ((ev.ctrlKey || ev.metaKey) && (ev.key === "i" || ev.key === "I")) {
        document.execCommand("italic");
        ev.preventDefault();
      }
      ev.stopPropagation();
    });
    textEditor.addEventListener("keyup", (ev) => ev.stopPropagation());
    textEditor.addEventListener("keypress", (ev) => ev.stopPropagation());
  }

  window.addEventListener("paste", (ev) => {
    if (isTypingInTextEditor()) return;
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
  if (btnText) {
    btnText.onclick = () => setTool("text");
    btnText.ondblclick = (ev) => {
      ev.preventDefault();
      setTool("text");
      toggleTextDock();
    };
  }
  if (textSizeInput) {
    textSizeInput.oninput = () => {
      const next = Math.max(12, Math.min(96, Number(textSizeInput.value) || DEFAULT_TEXT_FONT));
      // Preview only while dragging — no network ops / DOM rewrites per tick.
      textFontSize = next;
      if (textSizeLabel) textSizeLabel.textContent = String(Math.round(next));
      if (editingTextId && textEditor && !textEditor.hidden && !editorHasSelection()) {
        textEditor.style.fontSize = `${Math.max(12, next * view.scale)}px`;
      }
    };
    textSizeInput.onchange = () => {
      const next = Math.max(12, Math.min(96, Number(textSizeInput.value) || DEFAULT_TEXT_FONT));
      commitTextFontSize(next);
    };
  }
  if (btnTextBold) {
    btnTextBold.onclick = () => {
      if (editingTextId) {
        document.execCommand("bold");
        textEditor && textEditor.focus();
        return;
      }
      const id = styledTextTargetId();
      const text = id ? getText(id) : null;
      pushTextStyle({ bold: text ? !text.bold : !textBold });
      syncTextStyleControls();
    };
  }
  if (btnTextItalic) {
    btnTextItalic.onclick = () => {
      if (editingTextId) {
        document.execCommand("italic");
        textEditor && textEditor.focus();
        return;
      }
      const id = styledTextTargetId();
      const text = id ? getText(id) : null;
      pushTextStyle({ italic: text ? !text.italic : !textItalic });
      syncTextStyleControls();
    };
  }
  if (btnTextBullet) {
    btnTextBullet.onclick = () => {
      if (!editingTextId) setStatus("edit text to use lists");
      else {
        document.execCommand("insertUnorderedList");
        textEditor.focus();
      }
    };
  }
  if (btnTextNumber) {
    btnTextNumber.onclick = () => {
      if (!editingTextId) setStatus("edit text to use lists");
      else {
        document.execCommand("insertOrderedList");
        textEditor.focus();
      }
    };
  }
  if (btnTextIndent) {
    btnTextIndent.onclick = () => {
      if (!editingTextId) return;
      document.execCommand("indent");
      textEditor.focus();
    };
  }
  if (btnTextOutdent) {
    btnTextOutdent.onclick = () => {
      if (!editingTextId) return;
      document.execCommand("outdent");
      textEditor.focus();
    };
  }
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

  if (btnRule) {
    btnRule.onclick = () => toggleRule();
    btnRule.ondblclick = (ev) => {
      ev.preventDefault();
      setTool("rule");
      ensureRule();
      toggleRuleDock();
    };
  }
  for (const btn of document.querySelectorAll("[data-rule-kind]")) {
    btn.onclick = () => setRuleKind(btn.getAttribute("data-rule-kind") || "ruler");
  }
  const btnRuleSnap = document.getElementById("btn-rule-snap");
  if (btnRuleSnap) {
    btnRuleSnap.onclick = () => {
      ensureRule();
      setRuleSnapEnabled(!rule.snapEnabled);
    };
  }
  const btnRuleHide = document.getElementById("btn-rule-hide");
  if (btnRuleHide) {
    btnRuleHide.onclick = () => hideRule();
  }

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
    btn.onclick = () => setBackground(btn.getAttribute("data-bg") || "#f4f0e6");
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
  syncTextStyleControls();
  applyChromeTheme(pageBackground);
  Perf.start();
  loadPair()
    .then(connectWs)
    .then(() => refreshSessions().catch(() => {}))
    .catch((err) => setStatus(String(err)));

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

  window.__apeSketchRules = {
    getRule: () => (rule ? cloneRuleState(rule) : null),
    setRule: (state) => {
      rule = state ? cloneRuleState(state) : null;
      scheduleOverlay();
    },
    constrainPoint: (x, y) => {
      const p = constrainInkPoint({ x, y, t: 0, pressure: 0.5, sx: 0, sy: 0 });
      return { x: p.x, y: p.y };
    },
    projectSegment: projectOntoSegment,
    projectLine: projectOntoLine,
  };
})();
