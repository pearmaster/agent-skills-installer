"""Skill discovery, frontmatter parsing, and file-copy operations."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

from agent_skills_installer.git_ops import last_commit_sha_for_path


@dataclass
class SkillInfo:
    """Metadata about a single skill discovered in a repo."""

    name: str
    description: str
    source_path: Path
    metadata: dict = field(default_factory=dict)


# ── Discovery ────────────────────────────────────────────────────────

#: Conventional skill roots, checked first and scanned recursively.
PREFERRED_ROOTS = ("skills", ".claude/skills")

#: Directory names never entered while scanning. Hidden directories (``.git``,
#: ``.venv``, …) are skipped separately, so they aren't listed here.
EXCLUDED_DIRS = frozenset(
    {
        "node_modules",
        "__pycache__",
        "venv",
        "dist",
        "build",
        "target",
        "vendor",
        "site-packages",
        "test",
        "tests",
        "fixtures",
        "__fixtures__",
        "templates",
    }
)

#: How many directory levels below a scan root to search for ``SKILL.md``.
MAX_SCAN_DEPTH = 4


def discover_skills(repo_path: Path) -> list[SkillInfo]:
    """Return every skill found in *repo_path*.

    Layouts are tried in order, and the first one that yields anything wins:

    1. ``skills/`` and ``.claude/skills/``, scanned recursively — so both
       ``skills/<name>/`` and ``skills/<category>/<name>/`` work.
    2. A ``SKILL.md`` at the repo root — the repo is itself one skill.
    3. A repo-wide scan, catching root-level collections (``<name>/SKILL.md``)
       and plugin layouts (``<plugin>/skills/<name>/SKILL.md``).

    A directory counts as a skill when it contains a ``SKILL.md`` whose
    frontmatter carries a ``name`` usable as a directory name. A directory
    that yields a skill is never descended into, so reference or template
    ``SKILL.md`` files bundled *inside* a skill aren't mistaken for skills.
    """
    candidates: list[Path] = []

    for rel in PREFERRED_ROOTS:
        root = repo_path / rel
        if root.is_dir():
            candidates.extend(_walk_for_skill_dirs(root))

    if not candidates and (repo_path / "SKILL.md").is_file():
        candidates.append(repo_path)

    if not candidates:
        candidates.extend(_walk_for_skill_dirs(repo_path))

    return _build_skill_infos(candidates)


def _walk_for_skill_dirs(root: Path, max_depth: int = MAX_SCAN_DEPTH) -> list[Path]:
    """Breadth-first search under *root* for directories containing ``SKILL.md``.

    Excluded and hidden directories are never entered, and a directory that
    contains a ``SKILL.md`` is recorded without descending into it.
    """
    found: list[Path] = []
    frontier = [root]

    for _ in range(max_depth + 1):
        if not frontier:
            break
        next_frontier: list[Path] = []
        for directory in frontier:
            if (directory / "SKILL.md").is_file():
                found.append(directory)
                continue
            try:
                children = sorted(p for p in directory.iterdir() if p.is_dir())
            except OSError:
                continue
            next_frontier.extend(
                child
                for child in children
                if child.name not in EXCLUDED_DIRS and not child.name.startswith(".")
            )
        frontier = next_frontier

    return found


def _build_skill_infos(skill_dirs: list[Path]) -> list[SkillInfo]:
    """Parse each candidate directory into a :class:`SkillInfo`, skipping invalid ones."""
    results: list[SkillInfo] = []
    seen_paths: set[Path] = set()
    seen_names: dict[str, Path] = {}

    for directory in skill_dirs:
        resolved = directory.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)

        try:
            fm = parse_skill_frontmatter(directory / "SKILL.md")
        except Exception as exc:
            _warn(f"Skipping '{directory.name}': failed to parse SKILL.md frontmatter ({exc})")
            continue

        name = str(fm.get("name") or "").strip()
        if not name:
            _warn(f"Skipping '{directory.name}': SKILL.md frontmatter has no 'name'.")
            continue
        if not is_safe_dir_name(name):
            _warn(f"Skipping '{directory.name}': name {name!r} is not a usable directory name.")
            continue
        if name in seen_names:
            _warn(f"Skipping duplicate skill '{name}' at {directory} (already found at {seen_names[name]}).")
            continue
        seen_names[name] = directory

        metadata = fm.get("metadata")
        results.append(
            SkillInfo(
                name=name,
                description=str(fm.get("description") or "").strip(),
                source_path=directory,
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        )

    return sorted(results, key=lambda s: s.name)


def is_safe_dir_name(name: str) -> bool:
    """Return whether *name* is usable as a single directory component.

    Skill names come from a remote repo, so a name like ``../../.ssh`` must
    never reach a filesystem path.
    """
    if name in ("", ".", ".."):
        return False
    if "/" in name or "\\" in name or "\x00" in name:
        return False
    return Path(name).name == name


def _warn(message: str) -> None:
    print(f"⚠️  {message}", file=sys.stderr)


# ── Frontmatter helpers ──────────────────────────────────────────────


def parse_skill_frontmatter(skill_md_path: Path) -> dict:
    """Parse ``SKILL.md`` and return its frontmatter as a dict."""
    post = frontmatter.load(str(skill_md_path))
    return dict(post.metadata)


def add_git_metadata(skill_md_path: Path, repo_url: str, sha: str | None = None) -> None:
    """Add or update ``metadata.git-repo``/``metadata.git-sha`` in *skill_md_path*'s frontmatter."""
    post = frontmatter.load(str(skill_md_path))
    meta = post.metadata.get("metadata", {})
    if not isinstance(meta, dict):
        meta = {}
    meta["git-repo"] = repo_url
    if sha:
        meta["git-sha"] = sha
    post.metadata["metadata"] = meta
    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))
        f.write("\n")


# ── Copy ─────────────────────────────────────────────────────────────


def copy_skill(
    src_skill_dir: Path,
    dest_dir: Path,
    repo_url: str,
    dest_name: str | None = None,
) -> Path:
    """Copy a skill directory into *dest_dir* and inject ``metadata.git-repo``.

    *dest_name* is the directory name to install under, defaulting to the
    source directory's name. Callers should pass the skill's frontmatter
    ``name`` so skills are installed under the same key they're looked up by.

    Returns the path to the newly created skill directory.
    """
    name = dest_name or src_skill_dir.name
    if not is_safe_dir_name(name):
        raise ValueError(f"Refusing to install skill under unsafe directory name: {name!r}")

    dest_skill_dir = dest_dir / name
    if dest_skill_dir.exists():
        shutil.rmtree(dest_skill_dir)
    shutil.copytree(src_skill_dir, dest_skill_dir)

    skill_md = dest_skill_dir / "SKILL.md"
    if skill_md.exists():
        sha = last_commit_sha_for_path(src_skill_dir)
        add_git_metadata(skill_md, repo_url, sha)

    return dest_skill_dir


def describe_install_status(skill: SkillInfo, dest_dir: Path, repo_url: str) -> str | None:
    """Compare *skill* against an already-installed copy at *dest_dir*, if any.

    Returns ``"REPLACES"`` if a skill with the same name is installed from a
    different repo, ``"UPGRADE"`` if it's from the same repo but a different
    commit, ``"INSTALLED"`` if it's already up to date, or ``None`` if the
    skill isn't installed at *dest_dir* yet.
    """
    dest_skill_md = dest_dir / skill.name / "SKILL.md"
    if not dest_skill_md.exists():
        return None

    try:
        fm = parse_skill_frontmatter(dest_skill_md)
    except Exception:
        return None

    installed_meta = fm.get("metadata") or {}
    if installed_meta.get("git-repo") != repo_url:
        return "REPLACES"

    installed_sha = installed_meta.get("git-sha")
    remote_sha = last_commit_sha_for_path(skill.source_path)
    if installed_sha != remote_sha:
        return "UPGRADE"

    return "INSTALLED"


def find_local_skills_with_git(dest_dir: Path) -> list[tuple[Path, str, str]]:
    """Scan *dest_dir* for installed skills that have ``metadata.git-repo``.

    Returns a list of ``(skill_dir, repo_url, name)`` tuples, where *name* is
    the skill's frontmatter name — the key remote skills are matched on — and
    falls back to the directory name for skills installed by hand.
    """
    results: list[tuple[Path, str, str]] = []
    if not dest_dir.is_dir():
        return results

    for child in sorted(dest_dir.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            fm = parse_skill_frontmatter(skill_md)
            git_url = (fm.get("metadata") or {}).get("git-repo", "")
            if git_url:
                name = str(fm.get("name") or "").strip() or child.name
                results.append((child, git_url, name))
        except Exception:
            continue
    return results
