/**
 * Playwright draw bench: coalesced capture + live-stroke paint under a dense scene.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.APESKETCH_PORT || "9972";
const URL = `http://127.0.0.1:${PORT}/?perf=1`;

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on("pageerror", (err) => console.error("pageerror", err));
  await page.goto(URL, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForFunction(() => window.__apeSketchBench, null, { timeout: 15000 });

  const checks = await page.evaluate(() => window.__apeSketchBench.runDecimateCheck());

  const high = await page.evaluate(async () => {
    window.__apeSketchBench.setTier("high");
    return window.__apeSketchBench.runDrawBench({
      sceneStrokes: 80,
      pointsPer: 24,
      strokes: 8,
      pointsPerStroke: 180,
      coalescedPerMove: 6,
    });
  });

  const medium = await page.evaluate(async () => {
    window.__apeSketchBench.setTier("medium");
    return window.__apeSketchBench.runDrawBench({
      sceneStrokes: 80,
      pointsPer: 24,
      strokes: 8,
      pointsPerStroke: 180,
      coalescedPerMove: 6,
    });
  });

  const out = {
    t: new Date().toISOString(),
    url: URL,
    checks,
    high,
    medium,
    deltas: {
      live_stroke_avg_ms: high.live_stroke_avg_ms - medium.live_stroke_avg_ms,
      input_to_glass_avg_ms: high.input_to_glass_avg_ms - medium.input_to_glass_avg_ms,
    },
    gates: {
      live_stroke_p95_ms: { target: 4, high: high.live_stroke_p95_ms, medium: medium.live_stroke_p95_ms },
      input_to_glass_p95_ms: {
        target: 25,
        high: high.input_to_glass_p95_ms,
        medium: medium.input_to_glass_p95_ms,
      },
      coalesced_per_frame: { target: 1, high: high.coalesced_per_frame, medium: medium.coalesced_per_frame },
    },
  };

  const outPath = path.join(__dirname, "..", ".apeSketch", "perf", "_bench_draw.json");
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 2));
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
