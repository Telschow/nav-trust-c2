// Records the vertical "a person approves" clip from the real console in the replay demo
// (issue 164). Real UI only: this drives the built console in headless Chrome, adds captions as an
// overlay and writes a WebM, an .srt, a poster frame and a manifest. tools/clip/run.sh starts the
// backend, installs Playwright outside the repo and encodes the MP4 and the GIF.
//
// Environment: CLIP_TOOLS (where Playwright is installed), CLIP_OUT (output directory),
// CLIP_PYTHON (python with the project installed), CLIP_BACKEND (default http://127.0.0.1:8000),
// CLIP_CHANNEL (browser channel, default "chrome"), CLIP_ZOOM (console zoom, default 1.5).
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
const ZOOM = process.env.CLIP_ZOOM ?? "1.5"; // a desktop UI at 1080 px: zoomed, its text survives 360 px; 2 breaks its header
const SCENARIO = "stuck"; // uav2's position freezes (ADR 0003)
const SPEED = "8"; // replay speed: recorded seconds per demo second (the default demo uses 5)
const OPERATOR = "Duty operator"; // a placeholder name; the decided row and the activity log show it
const SIZE = { width: 1080, height: 1920 };
const HOLD_MS = 2000; // the landing button asks for a 1.5 s hold (HOLD_TO_CONFIRM_MS in the console)
// colours from console/DESIGN.md (IBM/Carbon): layer, text, accent
const BAR = "background:#161616;color:#f4f4f4;border-color:#78a9ff";
mkdirSync(OUT, { recursive: true });

const captions = []; // {name, from, to, text}: ms since the video started
let t0 = Date.now(); // set again just before the page exists: that is when the video starts
const now = () => Date.now() - t0;
let current = null;
function caption(page, text, name = "") {
  const at = now();
  if (current) current.to = at;
  current = text ? { name, from: at, to: at, text } : null;
  if (current) captions.push(current);
  return page.evaluate((t) => window.__setCaption(t), text ?? "");
}
const beatAt = (name) => captions.find((c) => c.name === name).from / 1000;

const sh = (cmd) => execSync(cmd, { encoding: "utf8" }).trim();
// which recordings the replay feeds the trust engine, and a hash of each
const recordings = JSON.parse(
  execSync(
    `${PYTHON} -c "import hashlib, json; from sim.demo_feed import ROOT, scenario_plan; ` +
      `print(json.dumps({v: {'path': str(s.recording.relative_to(ROOT)), ` +
      `'sha256': hashlib.sha256(s.recording.read_bytes()).hexdigest()} ` +
      `for v, s in scenario_plan('${SCENARIO}').items()}))"`,
    { encoding: "utf8" },
  ),
);

const browser = await chromium.launch({ channel: process.env.CLIP_CHANNEL ?? "chrome" });
let feed = null;
let video = null;
try {
  const context = await browser.newContext({ viewport: SIZE, recordVideo: { dir: OUT, size: SIZE } });
  await context.addInitScript(
    ([name, zoom, bar]) => {
      try {
        localStorage.setItem("nav-trust-operator", name);
        localStorage.setItem("nav-trust-sound", "off");
      } catch {}
      window.addEventListener("DOMContentLoaded", () => {
        const top = document.createElement("div");
        top.textContent = "SIMULATION (PX4 SITL), replayed";
        top.style.cssText =
          `position:fixed;top:0;left:0;right:0;z-index:99999;padding:14px 20px;${bar};` +
          "font:600 36px/1.2 system-ui,sans-serif;letter-spacing:.02em;text-align:center;border-bottom:2px solid";
        const cap = document.createElement("div");
        cap.style.cssText =
          `position:fixed;left:0;right:0;bottom:0;z-index:99999;height:220px;box-sizing:border-box;padding:0 32px;${bar};` +
          "font:600 48px/1.25 system-ui,sans-serif;text-align:center;border-top:2px solid;" +
          "display:flex;align-items:center;justify-content:center";
        // reserve room for both bars so they cover nothing of the console
        const room = document.createElement("style");
        room.textContent = `#root{position:fixed;top:76px;bottom:220px;left:0;right:0;overflow:auto;zoom:${zoom}}`;
        document.head.append(room);
        document.body.append(top, cap);
        window.__setCaption = (t) => {
          cap.textContent = t;
          cap.style.visibility = t ? "visible" : "hidden";
        };
        window.__setCaption("");
      });
    },
    [OPERATOR, ZOOM, BAR],
  );

  t0 = Date.now();
  const page = await context.newPage();
  video = page.video();
  const beat = (name) => page.screenshot({ path: join(OUT, `beat-${name}.jpg`), type: "jpeg", quality: 80 });
  await page.goto(BACKEND);
  await page.waitForSelector("text=REPLAY DEMO", { timeout: 15000 });

  // start the replay, so the clip begins before uav2 goes wrong
  feed = spawn(
    PYTHON,
    ["-m", "sim.demo_feed", "--backend", BACKEND, "--speed", SPEED, "--scenario", SCENARIO],
    { stdio: "ignore" },
  );
  await page.getByText("3 trusted").first().waitFor({ timeout: 30000 }); // what the console itself says
  await caption(page, "Three simulated drones, all trusted.", "trusted");
  await beat("0-trusted");
  const card = page.locator('article[aria-label^="Recommendation:"]').first();
  await card.waitFor({ timeout: 60000 }); // uav2 goes RED and a decision is raised
  await beat("1-flagged");
  await caption(page, "uav2's position froze. The system flags it RED and says why.", "flagged");
  await page.waitForTimeout(3500);
  await card.scrollIntoViewIfNeeded();
  await beat("2-recommendation");
  await caption(page, "It recommends landing uav2. It cannot act on its own.", "recommended");
  await page.waitForTimeout(3500);

  await caption(page, "Nothing moves until a person approves.", "approval");
  await card.getByRole("button", { name: /Approve/ }).click();
  const hold = page.getByRole("button", { name: /Hold to confirm landing/ });
  await hold.waitFor();
  await beat("3-confirm");
  await page.waitForTimeout(2500);
  const box = await hold.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(HOLD_MS);
  await page.mouse.up();
  await page.getByText(/Approved and recorded|Approved, but not executed/).first().waitFor({ timeout: 15000 });
  await caption(page, `Approved by ${OPERATOR}. The decision and the name are recorded in the audit log.`, "recorded");
  await page.getByText(`by ${OPERATOR}`).first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "poster.jpg"), type: "jpeg", quality: 90 });
  await page.waitForTimeout(4500);
  await caption(page, "");
  await context.close(); // the video is written when the context closes
} finally {
  feed?.kill();
  await browser.close();
}
renameSync(await video.path(), join(OUT, "clip.webm"));

const stamp = (ms) => {
  const p = (n, w = 2) => String(n).padStart(w, "0");
  return `${p(Math.floor(ms / 3600000))}:${p(Math.floor(ms / 60000) % 60)}:${p(Math.floor(ms / 1000) % 60)},${p(ms % 1000, 3)}`;
};
writeFileSync(
  join(OUT, "clip.srt"),
  captions
    .filter((c) => c.to > c.from)
    .map((c, i) => `${i + 1}\n${stamp(c.from)} --> ${stamp(c.to)}\n${c.text}\n`)
    .join("\n"),
);

writeFileSync(
  join(OUT, "manifest.json"),
  JSON.stringify(
    {
      commit: sh("git rev-parse HEAD"),
      working_tree_dirty: sh("git status --porcelain --untracked-files=no").length > 0,
      scenario: SCENARIO,
      replay_speed: Number(SPEED),
      source: "sim.demo_feed: recorded trust data with synthetic positions; no simulator was running",
      recordings,
      viewport: SIZE,
      console_zoom: Number(ZOOM),
      playwright: playwrightVersion,
      beats_s: {
        trusted: beatAt("trusted"),
        flagged: beatAt("flagged"),
        approval: beatAt("approval"),
        recorded: beatAt("recorded"),
      },
      operator_name_shown: OPERATOR,
      shown_on_screen: "the decided row and the activity line 'approved by <name>'; the audit database itself is not shown",
      alt_text: {
        "clip.mp4": "A person supervising simulated drones: uav2 is flagged as not trusted, the console recommends landing it, the person holds a button to approve, and the approval is recorded with their name. Captions say nothing moves until a person approves.",
        "loop.gif": "The same sequence in 10 seconds: uav2 flagged, a landing recommended, the person approves by holding a button.",
        "poster.jpg": "The console after the approval: uav2 not trusted, the decision shown as approved by the operator, and the activity log line recording it.",
      },
    },
    null,
    2,
  ) + "\n",
);
console.log(`wrote ${OUT}/clip.webm, clip.srt, poster.jpg, manifest.json`);
