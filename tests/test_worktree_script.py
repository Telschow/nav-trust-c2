"""One command makes a ready worktree (issue 175).

Run against a throwaway repository: the worktree lands next to the main checkout (not inside
it), the console's installed packages are linked, a second run is harmless, and it works from
inside another worktree."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "worktree.sh"


def git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}  # fmt: skip
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, env=env
    ).stdout


def make_repo(tmp_path: Path) -> Path:
    main = tmp_path / "outer" / "main"
    main.mkdir(parents=True)
    git(main, "init", "-q", "-b", "main")
    (main / "console" / "node_modules" / "pkg").mkdir(parents=True)
    (main / "console" / "node_modules" / "pkg" / "index.js").write_text("x", encoding="utf-8")
    (main / "README.md").write_text("hi", encoding="utf-8")
    (main / "console" / "package.json").write_text("{}", encoding="utf-8")
    git(main, "add", "README.md", "console/package.json")
    git(main, "commit", "-q", "-m", "first")
    return main


def run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def test_it_makes_a_worktree_next_to_the_main_checkout_and_links_the_console_packages(
    tmp_path: Path,
) -> None:
    main = make_repo(tmp_path)
    done = run(main, "feature-x", "main")
    assert done.returncode == 0, done.stderr
    worktree = tmp_path / "outer" / "wt-feature-x"
    assert worktree.is_dir() and (worktree / "README.md").is_file()
    assert git(worktree, "branch", "--show-current").strip() == "feature-x"
    link = worktree / "console" / "node_modules"
    assert link.is_symlink() and (link / "pkg" / "index.js").is_file()
    assert done.stdout.strip() == str(worktree)  # the absolute path alone, for $(...)
    assert f"{main}/.venv/bin" in done.stderr  # how to run the checks with the main environment
    assert "make check" in done.stderr


def test_running_it_twice_says_it_exists_and_succeeds(tmp_path: Path) -> None:
    main = make_repo(tmp_path)
    assert run(main, "again", "main").returncode == 0
    second = run(main, "again", "main")
    assert second.returncode == 0 and "already exists" in second.stderr
    assert second.stdout.strip() == str(tmp_path / "outer" / "wt-again")


def test_it_works_from_inside_another_worktree(tmp_path: Path) -> None:
    main = make_repo(tmp_path)
    assert run(main, "first", "main").returncode == 0
    inside = tmp_path / "outer" / "wt-first"
    done = run(inside, "second", "main")
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "outer" / "wt-second").is_dir()  # beside the main checkout, not nested
    assert not (inside / "wt-second").exists()


def test_a_branch_name_with_a_slash_makes_a_plain_folder_name(tmp_path: Path) -> None:
    main = make_repo(tmp_path)
    assert run(main, "fix/174-x", "main").returncode == 0
    assert (tmp_path / "outer" / "wt-fix-174-x").is_dir()


def test_it_copes_with_a_path_that_has_spaces_and_regex_characters(tmp_path: Path) -> None:
    main = make_repo(tmp_path / "my outer+dir (1)")
    first = run(main, "a.b", "main")
    assert first.returncode == 0, first.stderr
    worktree = Path(first.stdout.strip())
    assert worktree.is_dir() and " " in str(worktree)
    assert (
        "already exists" in run(main, "a.b", "main").stderr
    )  # found again, not matched as a regex
    assert "\\ " in first.stderr  # the printed cd escapes the spaces for the shell


def test_an_existing_branch_is_used_and_the_base_is_said_to_be_ignored(tmp_path: Path) -> None:
    main = make_repo(tmp_path)
    git(main, "branch", "already")
    done = run(main, "already", "no-such-base")
    assert done.returncode == 0 and "base is ignored" in done.stderr


def test_a_branch_checked_out_elsewhere_gets_a_clear_message(tmp_path: Path) -> None:
    main = make_repo(tmp_path)  # main is checked out in the main checkout
    done = run(main, "main", "main")
    assert done.returncode == 1 and "already checked out" in done.stderr
    assert "fatal" not in done.stderr


def test_a_base_that_does_not_exist_is_named_with_an_example(tmp_path: Path) -> None:
    main = make_repo(tmp_path)
    done = run(main, "x", "nobase")
    assert done.returncode == 1 and "'nobase' does not exist" in done.stderr
    assert "tools/worktree.sh x main" in done.stderr
    assert not (tmp_path / "outer" / "wt-x").exists()


def test_outside_a_git_repository_it_says_so(tmp_path: Path) -> None:
    done = run(tmp_path, "x")
    assert done.returncode == 2 and "Not inside a git repository" in done.stderr
