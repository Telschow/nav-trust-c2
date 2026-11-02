# Vertical clip and README GIF (issue 164)

`run.sh` records a 1080x1920 clip of the replay demo: one vehicle goes GREEN, then RED with a
reason, the recommendation appears, the operator holds the button to approve, and the audit row
with the operator's name shows. It uses the real console (built from `console/`) and the replay
feeder (`sim.demo_feed`), no simulator, no mock frames. It is a replay of recorded trust data with
synthetic positions, and the clip says so on screen: "SIMULATION (PX4 SITL), replayed".

```
source .venv/bin/activate
brew install ffmpeg                # once, for the MP4 and the GIF
tools/clip/run.sh                  # about 1 minute; outputs in logs/clip (not committed)
```

Outputs: `clip.mp4` (burned-in captions), `clip.webm`, `clip.srt` (the same captions), `poster.jpg`,
`loop.gif` (at most 10 s and 5 MB, for the README), `manifest.json` (the commit, the scenario, the
replay speed, the Playwright version) and one frame per beat (`beat-*.jpg`) to check by eye.

Playwright is not a project dependency. `run.sh` installs a pinned version (1.63.0) into
`$CLIP_TOOLS` (default `$TMPDIR/nav-trust-clip`), uses the installed Google Chrome
(`CLIP_CHANNEL=chromium` after `playwright install chromium` uses Playwright's own browser) and
fetches only Playwright's small recording ffmpeg. Behind a proxy that Node's downloader does not
use, fetch `https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1011/ffmpeg-mac-arm64.zip`
with `curl` and unpack it to `~/Library/Caches/ms-playwright/ffmpeg-1011/` with an empty
`INSTALLATION_COMPLETE` file.

## Accuracy rules for the clip

- Real UI only. Never call the replay a flight. Do not imply that the usability question is
  answered ([findings](../../docs/usability/findings-2026-10.md)).
- The only numbers on screen come from the console itself, which shows what the replay feeds it.
- Captions are 48 px on 1080 px, which is 16 px at 360 px width. Check `beat-*.jpg` after any
  change to the captions or the layout.

## Maintainer checklist (settings; agents do not change these)

- [ ] Repository homepage field: `https://telschow.github.io/nav-trust-c2/` (empty on 2026-11-01).
- [ ] Social preview image (1280x640): a crop of `poster.jpg` or of `docs/screenshots/console-1080p.jpg`,
      uploaded under Settings, General.
- [ ] Look at `logs/clip/clip.mp4` once for pace and wording before it is committed.
