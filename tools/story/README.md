# Believed-vs-real clip (issue 184)

`run.sh` renders a 1080x1920 MP4 of 22 s for social video feeds. It opens with an analogy for
readers who do not know the field: a map app loses GPS in a tunnel, its dot freezes and you keep
moving, with no warning. The analogy uses the same two symbols as the drone view (amber ring: what
the app shows; cyan dot: where you really are), so nothing new has to be decoded. Then the same thing for a drone: two recorded runs of one fault are shown side by side,
one with no action and one with a LAND approved 15 s after the fault. Distances from launch: 5320 m
and 450 m, the figures in ADR 0003.

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
- `src/Story.tsx` is the scene. The first 5 s are the analogy (`MapAnalogy`, drawn, no data); the rest
  are the two recorded runs. Time is sped up (the on-screen clock says simulated time since the
  fault): about 5x from the fault to touchdown, about 25x after it.
- The truth track is evaluation-only ground truth, drawn here to show the gap, never an input to the
  trust engine.

## Accuracy rules

- The tunnel scene is tagged "Analogy, not data" and the footer says it is not footage or data. It must not
  suggest the drone sees anything: the system compares the drone's sensors with each other, which
  is how the README describes the consistency detector.
- Wording stays plain: "GPS", "the system", no detector or engine names on screen.

- The clip says "SIMULATION (PX4 SITL), recorded runs replayed" and that the operator is scripted.
- One recorded run per action in one simulator; the end card says so. It is not a rate.
- "Furthest point from launch within 220 s" is how ADR 0003 measures it; do not shorten it to
  "it flew 5 km away" without that.
- No real place appears: the grid is metres from the launch point.
