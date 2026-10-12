# Demo video: script and how to record it

About 3 minutes, 1080p, with your voice. Record from `make demo`, so every view can be
reproduced, and keep the `REPLAY DEMO` label in frame the whole time: it says what you are
looking at.

## Script

| Time | On screen | Say |
|---|---|---|
| 0:00 | Console, three vehicles trusted | "Three simulated survey drones. Each row says whether its navigation can be trusted, how far its position can be off, and how close it is to being flagged. This is a replay of recorded simulator data." |
| 0:20 | Point at "within 3 m, 99% of reports" | "The 3 m bound was measured against the simulator's ground truth. It held in 99% of reports in the data I tuned on and in an independent set." |
| 0:35 | Alert: uav2 turns red, red band across the top | "uav2's GPS position has frozen. The vehicle thinks it is in the same place while it flies away. Nothing is sent to it until I approve." |
| 0:55 | Decision card, "If you approve" list | "The card says why, what approving will do, and how long I have." |
| 1:15 | Approve, confirmation dialog, then the sector moves on the map | "I approve. The sector goes to uav1. In a live run the vehicle would land." |
| 1:40 | Open `eval/fleet/results.md` on GitHub | "In three-vehicle simulator runs with one vehicle lost, the hand-over brought the area covered from 87% to 100%. Three runs each, a scripted operator, simulation only." |
| 2:10 | `docs/how-this-was-built.md` | "Claude Code wrote the code and tests. I made every decision. The mistakes list is public." |
| 2:40 | README | "Simulation only, public sources, no weapons or targeting. The repository link is below." |

Do not claim: field performance, real receivers, or a usability result for the redesigned console.

## How to record (macOS)

**Prepare**
1. Quit chat and mail apps, switch on Do Not Disturb, hide the Dock and the bookmarks bar, and
   close other browser tabs. Nothing personal should be visible.
2. Run `make demo-run DEMO_DB=logs/video-take1.sqlite` (build the console first with
   `make console`, or use `make demo`). Open http://127.0.0.1:8000 in a fresh Chrome window.
   About 15 seconds after the feed starts, uav2 turns red.
3. Set the window to a 16:9 shape. If your screen is not 1920 x 1080, that is fine: the console
   was checked at 1440 x 900 as well. Zoom the browser so the three panels and the red band are
   all visible.
4. Rehearse once. To restart the scenario, press Ctrl-C and run the command again with a new
   database name (`video-take2.sqlite`).

**Record**
1. Press Cmd+Shift+5, choose "Record Selected Portion" and drag over the browser window. Under
   Options, turn on "Show Mouse Clicks" and choose the microphone if you want to speak live.
2. Start the recording, then start the demo feed (or reload the page right after the backend
   starts) and follow the table. Keep the pointer slow and deliberate; point at what you mention.
3. Stop with the menu bar button. The file lands on your Desktop.

**Voice-over (easier than speaking live)**
Record the screen with no sound first. Then open the clip in QuickTime Player or iMovie and record
the voice while it plays (iMovie: Voiceover button), reading the "Say" column. Trim the start and
end.

**Export and publish**
1. Export at 1080p, as MP4, under about 3 minutes.
2. Upload it to YouTube (unlisted or public) or Vimeo; do not commit it to the repository.
3. Send me the link and I will put it in the README and the release notes.
