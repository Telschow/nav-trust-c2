#!/usr/bin/env bash
# Renders the 1080x1920 "believed vs real" clip (issue 184) from two recorded runs. No simulator.
#
#   tools/story/run.sh            # outputs in logs/story (not committed)
#   STORY_STILLS="60 150 300 420 600" tools/story/run.sh   # also writes those frames as JPEG
#
# Needs Node 22+, Google Chrome and python3. Remotion is installed OUTSIDE the repository, in
# $STORY_TOOLS (default $TMPDIR/nav-trust-story), at the versions pinned in tools/story/package.json,
# so the project gains no dependency. It renders with the installed Chrome, so nothing else is
# downloaded.
set -euo pipefail
cd "$(dirname "$0")/../.."

export STORY_TOOLS="${STORY_TOOLS:-${TMPDIR:-/tmp}/nav-trust-story}"
OUT="${STORY_OUT:-logs/story}"
CHROME="${STORY_CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
[ -x "${CHROME}" ] || { echo "Chrome not found at ${CHROME}; set STORY_CHROME" >&2; exit 1; }

mkdir -p "${STORY_TOOLS}" "${OUT}"
rm -rf "${STORY_TOOLS}/src" && mkdir -p "${STORY_TOOLS}/src"
cp tools/story/package.json tools/story/tsconfig.json "${STORY_TOOLS}/"
cp tools/story/src/*.ts tools/story/src/*.tsx "${STORY_TOOLS}/src/"
python3 tools/story/build_story.py "${STORY_TOOLS}/src/story.json"

[ -d "${STORY_TOOLS}/node_modules/remotion" ] || (cd "${STORY_TOOLS}" && npm install --no-audit --no-fund)
(cd "${STORY_TOOLS}" && node_modules/.bin/tsc -p .)

remotion=("${STORY_TOOLS}/node_modules/.bin/remotion")
cd "${STORY_TOOLS}"
for f in ${STORY_STILLS:-}; do
    "${remotion[@]}" still src/index.ts Story "${OLDPWD}/${OUT}/frame-${f}.jpg" --frame="${f}" \
        --browser-executable="${CHROME}" --log=error
done
if [ -z "${STORY_STILLS:-}" ]; then
    "${remotion[@]}" render src/index.ts Story "${OLDPWD}/${OUT}/story.mp4" --codec=h264 --crf=18 \
        --browser-executable="${CHROME}" --log=error
    echo "wrote ${OUT}/story.mp4"
fi
