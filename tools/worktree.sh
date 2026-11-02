#!/usr/bin/env bash
# Makes a ready git worktree for a task (issue 175).
#
#   tools/worktree.sh <name> [base]      base defaults to origin/main
#   cd "$(tools/worktree.sh <name>)"     stdout is the absolute path alone; messages go to stderr
#
# The worktree is a new branch <name> in a folder next to the main checkout, wt-<name> (a slash in
# the name becomes a dash). If the branch already exists it is used and the base is ignored. It
# links the main checkout's console/node_modules so the console builds and tests run, and prints
# how to run the Python checks there with the main checkout's virtual environment. Safe to run
# twice, and from the main checkout or from any worktree.
set -euo pipefail

say() { echo "$@" >&2; }

name="${1:-}"
[ -n "${name}" ] || { say "usage: tools/worktree.sh <name> [base]"; exit 2; }
base="${2:-origin/main}"

git rev-parse --git-common-dir >/dev/null 2>&1 || { say "Not inside a git repository."; exit 2; }
common="$(git rev-parse --path-format=absolute --git-common-dir)"
main_root="$(dirname "${common}")"
dir="$(dirname "${main_root}")/wt-${name//\//-}"
listing="$(git -C "${main_root}" worktree list --porcelain)"

if grep -Fxq "worktree ${dir}" <<<"${listing}"; then
    say "The worktree already exists: ${dir}"
else
    git -C "${main_root}" fetch -q origin 2>/dev/null || true # no remote, or offline: use what is there
    if git -C "${main_root}" show-ref -q --verify "refs/heads/${name}"; then
        if grep -Fxq "branch refs/heads/${name}" <<<"${listing}"; then
            say "Branch ${name} is already checked out in another worktree (git worktree list)."
            exit 1
        fi
        git -C "${main_root}" worktree add -q "${dir}" "${name}"
        say "Created ${dir} on the existing branch ${name} (the base is ignored)"
    else
        if ! git -C "${main_root}" rev-parse --verify -q "${base}^{commit}" >/dev/null; then
            say "The base '${base}' does not exist. Pass one, for example: tools/worktree.sh ${name} main"
            exit 1
        fi
        git -C "${main_root}" worktree add -q -b "${name}" "${dir}" "${base}"
        say "Created ${dir} on a new branch ${name} from ${base}"
    fi
fi

if [ -d "${main_root}/console/node_modules" ] && [ -d "${dir}/console" ] \
    && [ ! -e "${dir}/console/node_modules" ]; then
    ln -s "${main_root}/console/node_modules" "${dir}/console/node_modules"
fi

say ""
say "  cd $(printf '%q' "${dir}")"
say "  PATH=$(printf '%q' "${main_root}/.venv/bin"):\$PATH make check   # the main checkout's Python environment"
echo "${dir}"
