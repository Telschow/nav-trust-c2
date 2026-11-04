# Believed-vs-real clip (issue 184)

`run.sh` renders a 1080x1920 MP4 of about 24 s for social video feeds. It tells one story the console never
shows on one canvas: a drone's GPS freezes, it keeps reporting the old position, and two recorded
runs of the same fault are shown side by side, one with no action and one with a LAND approved 15 s
after the fault. Distances from launch: 5320 m and 450 m, the figures in ADR 0003.

```
tools/story/run.sh                                       # logs/story/story.mp4 (not committed)
STORY_STILLS="45 95 250 400 560" tools/story/run.sh      # those frames as JPEG, to check by eye
```

Needs Node 22+, Google Chrome (`STORY_CHROME` for another path) and python3. No simulator, no
project dependency: Remotion 4.0.499 is installed outside the repository, in `$STORY_TOOLS`
(default `$TMPDIR/nav-trust-story`), from `package.json` here, and renders with the installed Chrome.

- `build_story.py` reads `tests/replay/data/experiments/stuck-action-{none,land}.jsonl` and writes
  the tracks, the fault, approval and touchdown times and a sha256 of each recording. The scene
  code holds no result. `tests/test_story_data.py` checks the distances against ADR 0003.
- `src/Story.tsx` is the scene. Time is sped up (the on-screen clock says simulated time since the
  fault): 4x from the fault to touchdown, about 19x after it.
- The truth track is evaluation-only ground truth, drawn here to show the gap, never an input to the
  trust engine.

## Accuracy rules

- The clip says "SIMULATION (PX4 SITL), recorded runs replayed" and that the operator is scripted.
- One recorded run per action in one simulator; the end card says so. It is not a rate.
- "Furthest point from launch within 220 s" is how ADR 0003 measures it; do not shorten it to
  "it flew 5 km away" without that.
- No real place appears: the grid is metres from the launch point.
