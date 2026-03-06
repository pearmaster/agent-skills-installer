"""Skill discovery, frontmatter parsing, and file-copy operations."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter


@dataclass
class SkillInfo:
    """Metadata about a single skill discovered in a repo."""

    name: str
    description: str
    source_path: Path
    metadata: dict = field(default_factory=dict)


# ── Discovery ────────────────────────────────────────────────────────


def discover_skills(repo_path: Path) -> list[SkillInfo]:
    """Return all skills found under ``<repo_path>/skills/``.

    A skill is any immediate subdirectory of ``skills/`` that contains a
    ``SKILL.md`` file with valid YAML frontmatter.
    """
    skills_dir = repo_path / "skills"
    if not skills_dir.is_dir():
        return []

    results: list[SkillInfo] = []
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            fm = parse_skill_frontmatter(skill_md)
            results.append(
                SkillInfo(
                    name=fm.get("name", child.name),
                    description=fm.get("description", ""),
                    source_path=child,
                    metadata=fm.get("metadata", {}),
                )
            )
        except Exception:
            # Skip skills with unparseable frontmatter
            continue
    return results


# ── Frontmatter helpers ──────────────────────────────────────────────


def parse_skill_frontmatter(skill_md_path: Path) -> dict:
    """Parse ``SKILL.md`` and return its frontmatter as a dict."""
    post = frontmatter.load(str(skill_md_path))
    return dict(post.metadata)


def add_git_metadata(skill_md_path: Path, repo_url: str) -> None:
    """Add or update ``metadata.git-repo`` in the YAML frontmatter of *skill_md_path*."""
    post = frontmatter.load(str(skill_md_path))
    meta = post.metadata.get("metadata", {})
    if not isinstance(meta, dict):
        meta = {}
    meta["git-repo"] = repo_url
    post.metadata["metadata"] = meta
    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))
        f.write("\n")


# ── Copy ─────────────────────────────────────────────────────────────


def copy_skill(src_skill_dir: Path, dest_dir: Path, repo_url: str) -> Path:
    """Copy a skill directory into *dest_dir* and inject ``metadata.git-repo``.

    Returns the path to the newly created skill directory.
    """
    dest_skill_dir = dest_dir / src_skill_dir.name
    if dest_skill_dir.exists():
        shutil.rmtree(dest_skill_dir)
    shutil.copytree(src_skill_dir, dest_skill_dir)

    skill_md = dest_skill_dir / "SKILL.md"
    if skill_md.exists():
        add_git_metadata(skill_md, repo_url)

    return dest_skill_dir


def find_local_skills_with_git(dest_dir: Path) -> list[tuple[Path, str]]:
    """Scan *dest_dir* for installed skills that have ``metadata.git-repo``.

    Returns a list of ``(skill_dir, repo_url)`` tuples.
    """
    results: list[tuple[Path, str]] = []
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
                results.append((child, git_url))
        except Exception:
            continue
    return results
