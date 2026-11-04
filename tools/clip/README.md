# Vertical clip and README GIF (issue 164)

**Maintainer checklist for the settings: the last section of this file.**

`run.sh` records a 1080x1920 vertical cut of the replay demo (about 38 s): the question in large text over moving footage from the first frame; all three
drones TRUSTED; uav2 DO NOT TRUST with its reason; the one number, with its denominator, read from
the committed results files (frozen position flagged in 3.0 to 4.5 s, 7 simulation runs); the
recommendation; the press-and-hold approval ("Nothing moves until a person approves."); the decided
row with the operator's name; and an end card with what the project does not show and the Pages
URL. A spotlight marks what to look at in each beat, and the evidence label with the commit is on
every frame. It uses the real console (built from `console/`) and the replay
feeder (`sim.demo_feed`), no simulator, no mock frames. It is a replay of recorded trust data with
synthetic positions, and the clip says so on screen: "SIMULATION (PX4 SITL), replayed".

```
source .venv/bin/activate
brew install ffmpeg                # once, for the MP4 and the GIF
tools/clip/run.sh                  # about 1 minute; outputs in logs/clip (not committed)
```

Outputs: `clip.mp4` (burned-in captions), `clip.webm`, `clip.srt` (the same captions), `poster.jpg`,
`loop.gif` (under 10 s and 5 MB, both measured by the script, for the README), `manifest.json` and
one frame per beat (`beat-*.jpg`) to check by eye. The manifest records the commit and whether the
working tree was dirty, the scenario and replay speed, **which recordings the replay used with a
sha256 of each**, the Playwright version, and the alt text for each asset (use it where the asset is
embedded). The audit database itself is not on screen: the clip shows the decided row and the
activity line "approved by <name>", which the audit row produces.

Playwright is not a project dependency. `run.sh` installs a pinned version (1.63.0) into
`$CLIP_TOOLS` (default `$TMPDIR/nav-trust-clip`), uses the installed Google Chrome
(`CLIP_CHANNEL=chromium` after `playwright install chromium` uses Playwright's own browser) and
fetches only Playwright's small recording ffmpeg. Behind a proxy that Node's downloader does not
use, fetch `https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1011/ffmpeg-mac-arm64.zip`
with `curl` and unpack it to `~/Library/Caches/ms-playwright/ffmpeg-1011/` with an empty
`INSTALLATION_COMPLETE` file.

## Accuracy rules for the clip

- Real UI only. Never call the replay a flight, and the clip says it is a replay. Do not imply that
  the usability question is answered ([findings](../../docs/usability/findings-2026-10.md)).
- The only numbers on screen come from the console itself, which shows what the replay feeds it.
- Captions are 48 px on 1080 px, which is 16 px at 360 px width. The console is zoomed 1.5x (2x
  breaks its header), so its own text is about 8 px at 360 px: the captions carry the message.
  Check `beat-*.jpg` after any change to the captions or the layout (`sips -Z 640 poster.jpg` on
  macOS shows the 360 px version).

## Maintainer checklist (settings; agents do not change these)

- [ ] **Repository homepage:** on the repository page, About (the gear), Website:
      `https://telschow.github.io/nav-trust-c2/`.
- [ ] **Social preview:** Settings, General, Social preview, upload `docs/media/social-preview.png`
      (1280x640, a crop of the real console).
- [ ] **Posting the clip:** upload `docs/media/vertical/clip.mp4` with `clip.srt` as captions
      (burned-in captions are already in the video), `poster.jpg` as the thumbnail and the alt text
      from `manifest.json` (`alt_text`). Keep "Simulation only" in the post text.
