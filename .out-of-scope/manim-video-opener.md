# Manim opener for the overview video

This project does not build an illustrated opener (Manim or otherwise) for the overview video.

## Why this is out of scope

The request assumes an existing Manim hook prototype and a video pipeline. Neither is in the
repository: there is no Manim script, no render step, and no media manifest to update. Building
them means a new rendering toolchain, two aspect-ratio exports and a regenerated overview video
that CI cannot check without the simulator. The project's claims rest on the recorded replay and
its measured figures, and the explainer page already covers the plain-language introduction
(`docs/media/explainer.html`, with the brief in `docs/media/explainer-brief.md`).

If a Manim prototype and pipeline are added to the repository, delete this file and open a new
issue.

## Prior requests

- #189: "Make the Manim opener (16:9 and 4:5) and prepend it to the overview video"
