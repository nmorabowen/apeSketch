/**
 * Playwright erase bench: high tier, then medium tier, same workload.
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

  const high = await page.evaluate(async () => {
    window.__apeSketchBench.setTier("high");
    return window.__apeSketchBench.runEraseBench({ strokes: 80, pointsPer: 24, stamps: 160 });
  });

  const medium = await page.evaluate(async () => {
    window.__apeSketchBench.setTier("medium");
    return window.__apeSketchBench.runEraseBench({ strokes: 80, pointsPer: 24, stamps: 160 });
  });

  const out = {
    t: new Date().toISOString(),
    url: URL,
    high,
    medium,
    deltas: {
      stamp_avg_ms: high.stamp_avg_ms - medium.stamp_avg_ms,
      redraw_avg_ms: high.redraw_avg_ms - medium.redraw_avg_ms,
      commit_ms: high.commit_ms - medium.commit_ms,
      stamp_pct: high.stamp_avg_ms
        ? ((high.stamp_avg_ms - medium.stamp_avg_ms) / high.stamp_avg_ms) * 100
        : 0,
      redraw_pct: high.redraw_avg_ms
        ? ((high.redraw_avg_ms - medium.redraw_avg_ms) / high.redraw_avg_ms) * 100
        : 0,
    },
  };

  const outPath = path.join(__dirname, "..", ".apeSketch", "perf", "_bench_high_medium.json");
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 2));
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
