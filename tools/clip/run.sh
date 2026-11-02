#!/usr/bin/env bash
# Records the vertical "a person approves" clip from the replay demo (issue 164). No simulator.
#
#   source .venv/bin/activate && tools/clip/run.sh        # outputs in logs/clip (not committed)
#
# Needs: the project installed in the active Python, Node 22+, and ffmpeg for the MP4
# (`brew install ffmpeg`), and Google Chrome (set CLIP_CHANNEL=chromium after
# `playwright install chromium` to use Playwright's own browser instead). Playwright is installed
# OUTSIDE the repository, in $CLIP_TOOLS, at a pinned version, so the project gains no dependency;
# it downloads only its small recording ffmpeg (about 1 MB).
set -euo pipefail
cd "$(dirname "$0")/../.."

PLAYWRIGHT_VERSION=1.63.0
export CLIP_TOOLS="${CLIP_TOOLS:-${TMPDIR:-/tmp}/nav-trust-clip}"
export CLIP_OUT="${CLIP_OUT:-logs/clip}"
export CLIP_PYTHON="${CLIP_PYTHON:-python}"
export CLIP_BACKEND="http://127.0.0.1:${PORT:-8000}"

if [ ! -d "${CLIP_TOOLS}/node_modules/playwright" ]; then
    mkdir -p "${CLIP_TOOLS}"
    (cd "${CLIP_TOOLS}" && npm init -y >/dev/null && \
        npm install --no-save --no-audit --no-fund "playwright@${PLAYWRIGHT_VERSION}")
fi
"${CLIP_TOOLS}/node_modules/.bin/playwright" install ffmpeg
[ -f console/dist/index.html ] || (cd console && npm run build)

rm -rf "${CLIP_OUT}" && mkdir -p "${CLIP_OUT}"
db="$(mktemp -d)/audit.sqlite"
"${CLIP_PYTHON}" -m c2.server --db "${db}" --source "REPLAY DEMO" --port "${PORT:-8000}" \
    >"${CLIP_OUT}/server.log" 2>&1 &
server=$!
trap 'kill "${server}" 2>/dev/null || true' EXIT
sleep 3

node tools/clip/capture.mjs

if command -v ffmpeg >/dev/null; then
    ffmpeg -loglevel error -y -i "${CLIP_OUT}/clip.webm" -an -c:v libx264 -preset slow -crf 20 \
        -pix_fmt yuv420p -movflags +faststart "${CLIP_OUT}/clip.mp4"
    echo "wrote ${CLIP_OUT}/clip.mp4"

    # the README's first-screen GIF: from the flag to the approval, 1.5x, 360 px wide, at most
    # 10 s and 5 MB (the limits issue 164 sets)
    start="$("${CLIP_PYTHON}" -c "import json,sys; print(max(0, json.load(open(sys.argv[1]))['beats_s']['flagged'] - 0.5))" "${CLIP_OUT}/manifest.json")"
    ffmpeg -loglevel error -y -ss "${start}" -t 15 -i "${CLIP_OUT}/clip.webm" \
        -vf "setpts=PTS/1.5,fps=10,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse" \
        "${CLIP_OUT}/loop.gif"
    bytes="$(wc -c <"${CLIP_OUT}/loop.gif")"
    echo "wrote ${CLIP_OUT}/loop.gif (${bytes} bytes, 10 s)"
    [ "${bytes}" -lt 5000000 ] || { echo "loop.gif is over 5 MB" >&2; exit 1; }
else
    echo "ffmpeg not found: ${CLIP_OUT}/clip.webm is not encoded to MP4 or GIF (brew install ffmpeg)" >&2
fi
