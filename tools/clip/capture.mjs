// Records the vertical "a person approves" clip from the real console in the replay demo
// (issue 164). Real UI only: this drives the built console in headless Chromium, adds captions
// as an overlay and writes a WebM, an .srt, a poster frame and a manifest. tools/clip/run.sh
// starts the backend, installs Playwright outside the repo and encodes the MP4.
//
// Environment: CLIP_TOOLS (where Playwright is installed), CLIP_OUT (output directory),
// CLIP_PYTHON (python with the project installed), CLIP_BACKEND (default http://127.0.0.1:8000).
import { spawn, execSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const require = createRequire(join(process.env.CLIP_TOOLS, "/"));
const { chromium } = require("playwright");
const playwrightVersion = require("playwright/package.json").version;

const OUT = process.env.CLIP_OUT;
const BACKEND = process.env.CLIP_BACKEND ?? "http://127.0.0.1:8000";
const PYTHON = process.env.CLIP_PYTHON ?? "python";
const SCENARIO = "stuck"; // uav2's position freezes (ADR 0003)
const SPEED = "8"; // replay speed: recorded seconds per demo second (the default demo uses 5)
const OPERATOR = "Duty operator"; // a placeholder name; the audit row shows it
const SIZE = { width: 1080, height: 1920 };
mkdirSync(OUT, { recursive: true });

const captions = []; // {from, to, text} in ms since the video started
let t0 = 0;
const now = () => Date.now() - t0;
let open = null;
function caption(page, text) {
  const at = now();
  if (open) open.to = at;
  open = text ? { from: at, to: at, text } : null;
  if (open) captions.push(open);
  return page.evaluate((t) => window.__setCaption(t), text ?? "");
}

const browser = await chromium.launch({ channel: process.env.CLIP_CHANNEL ?? "chrome" });
const context = await browser.newContext({
  viewport: SIZE,
  recordVideo: { dir: OUT, size: SIZE },
});
await context.addInitScript((name) => {
  try {
    localStorage.setItem("nav-trust-operator", name);
    localStorage.setItem("nav-trust-sound", "off");
  } catch {}
  window.addEventListener("DOMContentLoaded", () => {
    const top = document.createElement("div");
    top.textContent = "SIMULATION (PX4 SITL), replayed";
    top.style.cssText =
      "position:fixed;top:0;left:0;right:0;z-index:99999;padding:14px 20px;background:#161616;" +
      "color:#f4f4f4;font:600 36px/1.2 system-ui,sans-serif;letter-spacing:.02em;text-align:center;" +
      "border-bottom:2px solid #78a9ff";
    const bar = document.createElement("div");
    bar.style.cssText =
      "position:fixed;left:0;right:0;bottom:0;z-index:99999;padding:0 32px;background:#161616;" +
      "color:#f4f4f4;font:600 48px/1.25 system-ui,sans-serif;text-align:center;height:220px;box-sizing:border-box;display:flex;align-items:center;justify-content:center;" +
      "border-top:2px solid #78a9ff";
    // reserve room for both bars so they cover nothing of the console
    const room = document.createElement("style");
    room.textContent = "#root{position:fixed;top:76px;bottom:220px;left:0;right:0;overflow:auto}";
    document.head.append(room);
    document.body.append(top, bar);
    window.__setCaption = (t) => {
      bar.textContent = t;
      bar.style.visibility = t ? "visible" : "hidden";
    };
    window.__setCaption("");
  });
}, OPERATOR);

const page = await context.newPage();
t0 = Date.now();
await page.goto(BACKEND);
await page.waitForSelector("text=REPLAY DEMO", { timeout: 15000 });
const beat = (name) => page.screenshot({ path: join(OUT, `beat-${name}.jpg`), type: "jpeg", quality: 80 });
await caption(page, "Three simulated drones. Every one is trusted.");
await page.waitForTimeout(2500);

// start the replay now, so the clip begins before uav2 goes wrong
const feed = spawn(
  PYTHON,
  ["-m", "sim.demo_feed", "--backend", BACKEND, "--speed", SPEED, "--scenario", SCENARIO],
  { stdio: "ignore" },
);
const card = page.locator('article[aria-label^="Recommendation:"]').first();
await card.waitFor({ timeout: 60000 }); // uav2 goes RED and a decision is raised
await beat("1-flagged");
await caption(page, "uav2's position froze. The system flags it RED and says why.");
await page.waitForTimeout(3500);
await card.scrollIntoViewIfNeeded();
await beat("2-recommendation");
await caption(page, "It recommends landing uav2. It cannot act on its own.");
await page.waitForTimeout(3500);

await caption(page, "Nothing moves until a person approves.");
await card.getByRole("button", { name: /Approve/ }).click();
const hold = page.getByRole("button", { name: /Hold to confirm landing/ });
await hold.waitFor();
await beat("3-confirm");
await page.waitForTimeout(2500);
const box = await hold.boundingBox();
await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
await page.mouse.down();
await page.waitForTimeout(2000); // the button asks for a deliberate hold
await page.mouse.up();
await page.getByText(/Approved and recorded|Approved, but not executed/).first().waitFor({ timeout: 15000 });
await caption(page, `Approved by ${OPERATOR}. The decision and the name go to the audit log.`);
await page.getByText(`by ${OPERATOR}`).first().scrollIntoViewIfNeeded();
await page.waitForTimeout(1500);
await page.screenshot({ path: join(OUT, "poster.jpg"), type: "jpeg", quality: 90 });
await page.waitForTimeout(4500);
await caption(page, "");

const video = page.video();
await context.close();
await browser.close();
feed.kill();
const webm = await video.path();
renameSync(webm, join(OUT, "clip.webm"));

const stamp = (ms) => {
  const p = (n, w = 2) => String(n).padStart(w, "0");
  return `${p(Math.floor(ms / 3600000))}:${p(Math.floor(ms / 60000) % 60)}:${p(Math.floor(ms / 1000) % 60)},${p(ms % 1000, 3)}`;
};
const srt = captions
  .filter((c) => c.to > c.from)
  .map((c, i) => `${i + 1}\n${stamp(c.from)} --> ${stamp(c.to)}\n${c.text}\n`)
  .join("\n");
writeFileSync(join(OUT, "clip.srt"), srt);

const git = (a) => execSync(`git ${a}`, { encoding: "utf8" }).trim();
writeFileSync(
  join(OUT, "manifest.json"),
  JSON.stringify(
    {
      commit: git("rev-parse HEAD"),
      scenario: SCENARIO,
      replay_speed: Number(SPEED),
      source: "sim.demo_feed replay of recorded trust data with synthetic positions; not a flight",
      viewport: SIZE,
      playwright: playwrightVersion,
      captions: captions.length,
      beats_s: { flagged: captions[1].from / 1000, approved: captions[4].from / 1000, end: captions[captions.length - 1].to / 1000 },
      operator_name_shown: OPERATOR,
    },
    null,
    2,
  ) + "\n",
);
console.log(`wrote ${OUT}/clip.webm, clip.srt, poster.jpg, manifest.json`);
