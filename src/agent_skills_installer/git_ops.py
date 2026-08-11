"""Git operations – clone repos into temporary directories via subprocess."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


class GitError(Exception):
    """Raised when a git operation fails."""


def clone_repo(repo_url: str) -> Path:
    """Clone *repo_url* into a temporary directory and return its path.

    A full clone (not shallow) so that history is available to determine
    the last commit that touched a given skill's directory.

    Raises :class:`GitError` if git is not installed or the clone fails.
    """
    if shutil.which("git") is None:
        raise GitError("git is not installed or not on PATH. Please install git first.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="agent-skills-"))
    try:
        subprocess.run(
            ["git", "clone", repo_url, str(tmp_dir / "repo")],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise GitError(f"Failed to clone {repo_url}:\n{exc.stderr.strip()}") from exc

    return tmp_dir / "repo"


def last_commit_sha_for_path(path: Path) -> str | None:
    """Return the sha of the most recent commit that touched *path*.

    Returns ``None`` if git is unavailable, *path* isn't inside a git
    repo, or no commit touches it.
    """
    if shutil.which("git") is None:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "log", "-1", "--format=%H", "--", "."],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    return result.stdout.strip() or None


def cleanup_repo(path: Path) -> None:
    """Remove a previously cloned temporary repo directory."""
    # Walk up to the temp root (the parent we created)
    target = path.parent if path.name == "repo" else path
    shutil.rmtree(target, ignore_errors=True)


@contextmanager
def cloned_repo(repo_url: str) -> Generator[Path, None, None]:
    """Context manager that clones *repo_url* and cleans up on exit.

    Usage::

        with cloned_repo("https://github.com/org/repo") as repo_path:
            ...
    """
    path: Path | None = None
    try:
        path = clone_repo(repo_url)
        yield path
    finally:
        if path is not None:
            cleanup_repo(path)
