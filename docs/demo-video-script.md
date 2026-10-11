# Demo video script (about 3 minutes)

Screen recording at 1920 x 1080 with a voice-over. Record from `make demo` so every view can be
reproduced. Keep the `REPLAY DEMO` label in the frame the whole time: it says what you are
looking at.

| Time | On screen | Say |
|---|---|---|
| 0:00 | Console, three vehicles trusted | "Three simulated survey drones. Each row says whether its navigation can be trusted, how far its position can be off, and how close it is to being flagged. This is a replay of recorded simulator data." |
| 0:20 | Point at "within 3 m, 99% of reports" | "The 3 m bound was measured against the simulator's ground truth. It held in 99% of reports in the data I tuned on and in an independent set." |
| 0:35 | Alert appears: uav2 turns red, red band across the top | "uav2's GPS position has frozen. The vehicle thinks it is in the same place while it flies away. Nothing is sent to it until I approve." |
| 0:55 | Decision card, "If you approve" list | "The card says why, what approving will do, and how long I have." |
| 1:15 | Approve, confirmation dialog, then the sector moves on the map | "I approve. The sector goes to uav1. In a live run the vehicle would land." |
| 1:40 | Switch to `eval/fleet/results.md` | "In three-vehicle simulator runs with one vehicle lost, the re-task brought the area covered from 87% to 100%. Three runs each, a scripted operator, simulation only." |
| 2:10 | `docs/how-this-was-built.md` | "Claude Code wrote the code and tests. I made every decision. The mistakes list is public." |
| 2:40 | README | "Simulation only, public sources, no weapons or targeting. Repository link below." |

Do not claim: field performance, real receivers, a usability result beyond the findings note.
