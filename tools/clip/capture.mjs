// Records the vertical LinkedIn cut of the replay demo (issue 164), following the portfolio visual
// strategy: the question in large text over moving real footage for the first 3 s, one idea per
// beat, a spotlight on what to look at, one number with its denominator (read from the generated
// results files, never typed), the evidence label with the commit on every frame, and an end card
// that says what the project does not show. Real UI only: it drives the built console in Chrome.
// tools/clip/run.sh starts the backend, installs Playwright outside the repo and encodes the MP4.
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
const URL_SHORT = "telschow.github.io/nav-trust-c2";
mkdirSync(OUT, { recursive: true });

const sh = (cmd) => execSync(cmd, { encoding: "utf8" }).trim();
const sha = sh("git rev-parse --short HEAD") + (sh("git status --porcelain --untracked-files=no") ? "+dirty" : "");

// The one number: how fast a frozen position was flagged, over which runs. From the committed
// results files, the same figures the README states and tests/test_readme_numbers.py checks.
const frozen = JSON.parse(
  execSync(
    `${PYTHON} -c "import json; r=[x for f in ('eval/results.json','eval/heldout/results.json') ` +
      `for n,s in json.load(open(f))['scenarios'].items() if n.startswith('stuck_position') ` +
      `for x in s['runs'] if x['detected']]; t=[x['ttd_s'] for x in r]; ` +
      `print(json.dumps({'min': round(min(t),1), 'max': round(max(t),1), 'runs': len(t)}))"`,
    { encoding: "utf8" },
  ),
);
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

const cues = []; // {name, from, to, text}: ms since the video started, for the .srt
let t0 = Date.now();
const now = () => Date.now() - t0;
let open = null;
function cue(name, text) {
  const at = now();
  if (open) open.to = at;
  open = text ? { name, from: at, to: at, text } : null;
  if (open) cues.push(open);
}
const beatAt = (name) => cues.find((c) => c.name === name).from / 1000;

const browser = await chromium.launch({ channel: process.env.CLIP_CHANNEL ?? "chrome" });
let feed = null;
let video = null;
try {
  const context = await browser.newContext({ viewport: SIZE, recordVideo: { dir: OUT, size: SIZE } });
  await context.addInitScript(
    ([name, zoom, evidence]) => {
      try {
        localStorage.setItem("nav-trust-operator", name);
        localStorage.setItem("nav-trust-sound", "off");
      } catch {}
      window.addEventListener("DOMContentLoaded", () => {
        const css = document.createElement("style");
        css.textContent = `
          body{background:#0e1216}
          #root{position:fixed;top:0;bottom:330px;left:0;right:0;overflow:auto;zoom:${zoom}}
          .clip{font-family:"IBM Plex Sans",system-ui,sans-serif;color:#f4f4f4;position:fixed;z-index:99999}
          #clip-bar{left:0;right:0;bottom:0;height:330px;box-sizing:border-box;padding:26px 40px 18px;background:#161616;
            border-top:3px solid #6aa9e9;display:flex;flex-direction:column;justify-content:space-between}
          #clip-text{font-weight:600;font-size:56px;line-height:1.18;text-align:center;flex:1;display:flex;
            flex-direction:column;align-items:center;justify-content:center;gap:14px}
          #clip-evidence{font-weight:600;font-size:30px;letter-spacing:.03em;color:#c6c6c6;text-align:left}
          .pill{display:inline-flex;align-items:center;gap:16px;font-weight:600;font-size:48px;padding:6px 22px;
            border:3px solid currentColor;letter-spacing:.04em}
          .pill i{display:inline-block;width:30px;height:30px;background:currentColor}
          .pill.ok{color:#52c28a}.pill.ok i{border-radius:50%}
          .pill.bad{color:#f06262}
          #clip-spot{left:0;top:0;width:0;height:0;border:5px solid #6aa9e9;box-shadow:0 0 0 4000px rgba(14,18,22,.80);
            transition:all .25s ease-out;opacity:0;pointer-events:none}
          #clip-title{inset:0;background:rgba(14,18,22,.80);display:flex;flex-direction:column;align-items:center;
            justify-content:center;text-align:center;gap:44px;padding:0 70px;opacity:0;transition:opacity .25s ease-out;
            pointer-events:none}
          #clip-title h1{font-weight:600;font-size:92px;line-height:1.08;margin:0}
          #clip-title p{font-weight:400;font-size:52px;line-height:1.25;margin:0;color:#e0e0e0}
          #clip-title .mono{font-family:"IBM Plex Mono",monospace;font-weight:400;font-size:42px;white-space:nowrap}
          #clip-title .stat{font-family:"IBM Plex Mono",monospace;font-weight:400;font-size:132px;line-height:1;color:#f06262}`;
        document.head.append(css);
        const mk = (id, tag = "div") => Object.assign(document.createElement(tag), { id, className: "clip" });
        const spot = mk("clip-spot");
        const title = mk("clip-title");
        const bar = mk("clip-bar");
        const text = Object.assign(document.createElement("div"), { id: "clip-text" });
        const ev = Object.assign(document.createElement("div"), { id: "clip-evidence", textContent: evidence });
        bar.append(text, ev);
        document.body.append(spot, title, bar);
        window.__clip = {
          text: (html) => {
            text.innerHTML = html;
            bar.style.height = html ? "330px" : "96px";
          },
          spot: (r) => {
            if (!r) { spot.style.opacity = 0; return; }
            const pad = 10;
            Object.assign(spot.style, {
              opacity: 1, left: r.x - pad + "px", top: r.y - pad + "px",
              width: r.width + 2 * pad + "px", height: r.height + 2 * pad + "px",
            });
          },
          title: (html) => { title.innerHTML = html ?? ""; title.style.opacity = html ? 1 : 0; },
        };
        window.__clip.text("");
      });
    },
    [OPERATOR, ZOOM, `SIMULATION (PX4 SITL), replayed  |  ${sha}`],
  );

  t0 = Date.now();
  const page = await context.newPage();
  video = page.video();
  // a frame to check by eye, taken once the 250 ms transitions have finished
  const beat = async (name) => {
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(OUT, `beat-${name}.jpg`), type: "jpeg", quality: 80 });
  };
  const say = (name, html, plain) => { cue(name, plain); return page.evaluate((h) => window.__clip.text(h), html); };
  const spot = async (loc) => {
    if (!loc) return page.evaluate(() => window.__clip.spot(null));
    await loc.scrollIntoViewIfNeeded();
    // measure only once the element has stopped moving (smooth scrolling, layout after an update)
    let box = await loc.boundingBox();
    for (let i = 0; i < 20; i++) {
      await page.waitForTimeout(120);
      const next = await loc.boundingBox();
      const still = Math.abs(next.y - box.y) < 1 && Math.abs(next.height - box.height) < 1;
      box = next;
      if (still) break;
    }
    await page.evaluate((b) => window.__clip.spot(b), box);
  };
  const title = (html) => page.evaluate((h) => window.__clip.title(h), html);
  const ok = '<span class="pill ok"><i></i>TRUSTED</span>';
  const bad = '<span class="pill bad"><i></i>DO NOT TRUST</span>';

  await page.goto(BACKEND);
  await page.waitForSelector("text=REPLAY DEMO", { timeout: 15000 });
  // start the replay now: the footage moves behind the opening question
  feed = spawn(
    PYTHON,
    ["-m", "sim.demo_feed", "--backend", BACKEND, "--speed", SPEED, "--scenario", SCENARIO],
    { stdio: "ignore" },
  );
  await page.getByText("3 trusted").first().waitFor({ timeout: 30000 });

  // 1. hook: the question, large, over real moving footage (3.5 s)
  cue("hook", "Which drone's position can you trust? Three simulated drones. One person decides.");
  await title("<h1>Which drone's position can you trust?</h1><p>Three simulated drones. One person decides.</p>");
  await page.waitForTimeout(2200);
  await page.screenshot({ path: join(OUT, "poster.jpg"), type: "jpeg", quality: 90 });
  await page.waitForTimeout(1300);
  await title(null);

  // 2. all three trusted (what the console itself says: "3 trusted")
  await spot(page.locator('section[aria-label="Map"]'));
  await say("trusted", `${ok}<span>All three report<br>a trusted position.</span>`, "TRUSTED. All three report a trusted position.");
  await beat("1-trusted");

  // 3. uav2 goes RED: the system says so and says why
  const card = page.locator('article[aria-label^="Recommendation:"]').first();
  await card.waitFor({ timeout: 60000 });
  await spot(page.locator('button[aria-label^="uav2,"]'));
  await say("flagged", `${bad}<span>uav2's position froze.<br>The system says why.</span>`, "DO NOT TRUST. uav2's position froze. The system says why.");
  await beat("2-flagged");
  await page.waitForTimeout(3600);

  // 4. one number, with its denominator, held for a second
  await spot(null);
  await title(
    `<p>Frozen position flagged in</p><div class="stat">${frozen.min.toFixed(1)} to ${frozen.max.toFixed(1)} s</div>` +
      `<p>${frozen.runs} simulation runs</p>`,
  );
  cue("number", `Frozen position flagged in ${frozen.min.toFixed(1)} to ${frozen.max.toFixed(1)} s, ${frozen.runs} simulation runs.`);
  await beat("3-number");
  await page.waitForTimeout(3200);
  await title(null);

  // 5. the recommendation
  await spot(card);
  await say("recommended", "<span>It recommends landing uav2.<br>It cannot act alone.</span>", "It recommends landing uav2. It cannot act alone.");
  await beat("4-recommendation");
  await page.waitForTimeout(3600);

  // 6. the approval: the required overlay line, and a deliberate press-and-hold
  await say("approval", "<span>Nothing moves until<br>a person approves.</span>", "Nothing moves until a person approves.");
  await card.getByRole("button", { name: /Approve/ }).click();
  const hold = page.getByRole("button", { name: /Hold to confirm landing/ });
  await hold.waitFor();
  await spot(page.getByRole("dialog"));
  await beat("5-confirm");
  await page.waitForTimeout(2500);
  const box = await hold.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(HOLD_MS);
  await page.mouse.up();
  await page.getByText(/Approved and recorded|Approved, but not executed/).first().waitFor({ timeout: 15000 });

  // 7. recorded with the operator's name
  await spot(null);
  await say("recorded", `<span>Approved by ${OPERATOR}.<br>Recorded in the audit log.</span>`, `Approved by ${OPERATOR}. Recorded in the audit log.`);
  const decided = page.getByText(`by ${OPERATOR}`).first();
  await decided.scrollIntoViewIfNeeded();
  await spot(decided.locator("xpath=ancestor::li[1]"));
  await beat("6-recorded");
  await page.waitForTimeout(3600);
  await spot(null);

  // 8. end card: the line again, what this does not show, where to look
  cue("end", `Nothing moves until a person approves. What this does not show: real hardware or radio interference, and a usability result. Simulation only. Not flight-tested. ${URL_SHORT}`);
  await title(
    "<h1>Nothing moves until a person approves.</h1>" +
      "<p><b>What this does not show</b><br>Real hardware or radio interference.<br>A usability result: not re-tested.</p>" +
      `<p class="mono">${URL_SHORT}</p><p>Simulation only. Not flight-tested.</p>`,
  );
  await page.evaluate(() => window.__clip.text(""));
  await beat("7-end");
  await page.waitForTimeout(5000);
  cue("done", "");
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
  cues
    .filter((c) => c.to > c.from)
    .map((c, i) => `${i + 1}\n${stamp(c.from)} --> ${stamp(c.to)}\n${c.text}\n`)
    .join("\n"),
);

const alt = (what) => `Simulation (PX4 SITL), replayed. ${what}`;
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
      numbers: {
        frozen_position_flagged_s: {
          ...frozen,
          from: ["eval/results.json", "eval/heldout/results.json"],
          note: "time from the start of the fault to the first report that is not GREEN, over runs where it was flagged",
        },
      },
      viewport: SIZE,
      console_zoom: Number(ZOOM),
      playwright: playwrightVersion,
      beats_s: {
        hook: beatAt("hook"),
        trusted: beatAt("trusted"),
        flagged: beatAt("flagged"),
        recorded: beatAt("recorded"),
        end: beatAt("end"),
      },
      operator_name_shown: OPERATOR,
      shown_on_screen: "the decided row and the activity line 'approved by <name>'; the audit database itself is not shown",
      alt_text: {
        "clip.mp4": alt(
          `A person supervises three drones. One drone's position freezes and is flagged as not trusted within ${frozen.min.toFixed(1)} to ${frozen.max.toFixed(1)} seconds in ${frozen.runs} runs. The console recommends landing it, the person holds a button to approve, and the approval is recorded with their name. Nothing moves until a person approves. It does not show real hardware or a usability result.`,
        ),
        "loop.gif": alt("uav2 flagged as not trusted, a landing recommended, the person approves by holding a button."),
        "poster.jpg": alt("The question 'Which drone's position can you trust?' over the console with three simulated drones."),
      },
    },
    null,
    2,
  ) + "\n",
);
console.log(`wrote ${OUT}/clip.webm, clip.srt, poster.jpg, manifest.json`);
