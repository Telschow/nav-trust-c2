#!/usr/bin/env bash
# Records the vertical "a person approves" clip from the replay demo (issue 164). No simulator.
#
#   source .venv/bin/activate && tools/clip/run.sh        # outputs in logs/clip (not committed)
#
# Needs: the project installed in the active Python, Node 22+, and ffmpeg for the MP4 and the GIF
# (`brew install ffmpeg`), and Google Chrome (set CLIP_CHANNEL=chromium after
# `playwright install chromium` to use Playwright's own browser instead). Playwright is installed
# OUTSIDE the repository, in $CLIP_TOOLS, at a pinned version, so the project gains no dependency;
# it downloads only its small recording ffmpeg (about 1 MB).
set -euo pipefail
cd "$(dirname "$0")/../.."

PLAYWRIGHT_VERSION=1.63.0
PORT="${PORT:-8000}"
export CLIP_TOOLS="${CLIP_TOOLS:-${TMPDIR:-/tmp}/nav-trust-clip}"
export CLIP_OUT="${CLIP_OUT:-logs/clip}"
export CLIP_PYTHON="${CLIP_PYTHON:-python}"
export CLIP_BACKEND="${CLIP_BACKEND:-http://127.0.0.1:${PORT}}"

if curl -s -o /dev/null --max-time 2 "${CLIP_BACKEND}/state"; then
    echo "Something already answers at ${CLIP_BACKEND}: stop it first (the clip must show a fresh demo)." >&2
    exit 1
fi

if [ ! -d "${CLIP_TOOLS}/node_modules/playwright" ]; then
    mkdir -p "${CLIP_TOOLS}"
    (cd "${CLIP_TOOLS}" && npm init -y >/dev/null && \
        npm install --no-save --no-audit --no-fund "playwright@${PLAYWRIGHT_VERSION}")
fi
"${CLIP_TOOLS}/node_modules/.bin/playwright" install ffmpeg
[ -f console/dist/index.html ] || (cd console && npm run build)

rm -rf "${CLIP_OUT:?}" && mkdir -p "${CLIP_OUT}"
workdir="$(mktemp -d)"
"${CLIP_PYTHON}" -m c2.server --db "${workdir}/audit.sqlite" --source "REPLAY DEMO" \
    --port "${PORT}" >"${CLIP_OUT}/server.log" 2>&1 &
server=$!
trap 'kill "${server}" 2>/dev/null || true; rm -rf "${workdir}"' EXIT
for _ in $(seq 1 20); do
    curl -s -o /dev/null --max-time 1 "${CLIP_BACKEND}/state" && break
    kill -0 "${server}" 2>/dev/null || { echo "the backend exited:" >&2; tail -n 20 "${CLIP_OUT}/server.log" >&2; exit 1; }
    sleep 0.5
done
curl -s -o /dev/null --max-time 2 "${CLIP_BACKEND}/state" || { echo "the backend did not come up (see ${CLIP_OUT}/server.log)" >&2; exit 1; }

node tools/clip/capture.mjs

if command -v ffmpeg >/dev/null; then
    ffmpeg -loglevel error -y -i "${CLIP_OUT}/clip.webm" -an -c:v libx264 -preset slow -crf 20 \
        -pix_fmt yuv420p -movflags +faststart "${CLIP_OUT}/clip.mp4"
    echo "wrote ${CLIP_OUT}/clip.mp4"

    # the README's first-screen GIF: from the flag to the approval being recorded, sped up to 9 s,
    # 360 px wide. Issue 164 sets under 10 s and 5 MB; both are measured below, not assumed.
    read -r start span speed < <("${CLIP_PYTHON}" -c "
import json, sys
b = json.load(open(sys.argv[1]))['beats_s']
start = max(0, b['flagged'] - 0.3)
span = b['recorded'] + 3.5 - start
print(round(start, 2), round(span, 2), round(span / 9.0, 3))" "${CLIP_OUT}/manifest.json")
    ffmpeg -loglevel error -y -ss "${start}" -t "${span}" -i "${CLIP_OUT}/clip.webm" \
        -vf "setpts=PTS/${speed},fps=10,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse" \
        "${CLIP_OUT}/loop.gif"
    bytes="$(wc -c <"${CLIP_OUT}/loop.gif")"
    seconds="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "${CLIP_OUT}/loop.gif")"
    echo "wrote ${CLIP_OUT}/loop.gif (${bytes} bytes, ${seconds} s)"
    [ "${bytes}" -lt 5000000 ] || { echo "loop.gif is over 5 MB" >&2; exit 1; }
    "${CLIP_PYTHON}" -c "import sys; sys.exit(0 if float(sys.argv[1]) < 10 else 1)" "${seconds}" \
        || { echo "loop.gif is not under 10 s" >&2; exit 1; }
else
    echo "ffmpeg not found: ${CLIP_OUT}/clip.webm is not encoded to MP4 or GIF (brew install ffmpeg)" >&2
fi
