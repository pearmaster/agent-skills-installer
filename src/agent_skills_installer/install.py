"""Install command – orchestrates the interactive skill installation flow."""

from __future__ import annotations

from pathlib import Path

import typer

from agent_skills_installer import config as cfg
from agent_skills_installer import tui
from agent_skills_installer.git_ops import GitError, cloned_repo
from agent_skills_installer.skills import (
    SkillInfo,
    copy_skill,
    describe_install_status,
    discover_skills,
    resolve_dependencies,
)

_STATUS_PREFIXES = {
    "REPLACES": "Replaces existing skill with the same name.",
    "UPGRADE": "UPGRADE",
    "INSTALLED": "INSTALLED",
}

# Shown next to auto-installed dependencies in the summary, since the user
# never picked them and may not have seen their status in the skill list.
_DEPENDENCY_STATUS_NOTES = {
    "REPLACES": "replaces an existing skill from another repo",
    "UPGRADE": "upgrades the installed copy",
    "INSTALLED": "already installed, will be refreshed",
}


def _resolve_destination(raw: str) -> Path:
    """Expand and resolve a CLI-provided destination, creating it if needed."""
    dest = Path(raw).expanduser().resolve()
    if not dest.exists():
        dest.mkdir(parents=True, exist_ok=True)
        typer.echo(f"Created directory {dest}")
    return dest


def run_install(
    *,
    destination: str | None = None,
    source: str | None = None,
    skill_name: str | None = None,
) -> None:
    """Run the install flow.

    When *destination*, *source*, or *skill_name* are provided the
    corresponding interactive prompts are skipped.
    """
    # 1. Load config
    conf = cfg.load_config()

    # 2. Choose destination
    if destination:
        dest = _resolve_destination(destination)
    else:
        last_dest = cfg.get_last_destination(conf)
        dest = tui.prompt_destination(last_dest or None)

    # 3. Choose source repo
    if source:
        repo_url = source.strip()
    else:
        recent = cfg.get_recent_repos(conf)
        repo_url = tui.prompt_repo(recent or None)

    # 4. Clone & discover
    typer.echo(f"\n⏳ Fetching {repo_url} …")
    try:
        with cloned_repo(repo_url) as repo_path:
            skills = discover_skills(repo_path)

            if not skills:
                typer.echo(
                    "❌ No skills found in this repo (looked in skills/, .claude/skills/, "
                    "a root SKILL.md, then the rest of the repo).",
                    err=True,
                )
                raise typer.Exit(1)

            typer.echo(f"Found {len(skills)} skill(s).\n")

            # 5. Select skills
            skill_dicts = []
            for s in skills:
                status = describe_install_status(s, dest, repo_url)
                description = s.description
                if status is not None:
                    description = f"{_STATUS_PREFIXES[status]} {description}".strip()
                skill_dicts.append(
                    {
                        "name": s.name,
                        "description": description,
                        "source_path": s.source_path,
                        "status": status,
                    }
                )

            if skill_name:
                # Filter to the requested skill – no interactive prompt
                selected = [s for s in skill_dicts if s["name"] == skill_name]
                if not selected:
                    available = ", ".join(s["name"] for s in skill_dicts)
                    typer.echo(
                        f"❌ Skill '{skill_name}' not found. Available: {available}",
                        err=True,
                    )
                    raise typer.Exit(1)
            else:
                selected = tui.prompt_select_skills(skill_dicts)

            # 6. Pull in skills that the selected ones depend on
            required_by = resolve_dependencies([s["name"] for s in selected], skills)
            dependencies = [
                {**s, "required_by": required_by[s["name"]]}
                for s in skill_dicts
                if s["name"] in required_by
            ]

            # 7. Confirmation (skip when skill was specified on CLI)
            if not skill_name:
                summary = _build_summary(dest, repo_url, selected, dependencies)
                if not tui.prompt_confirm_actions(summary):
                    typer.echo("Aborted.")
                    raise typer.Exit(0)
            elif dependencies:
                typer.echo("Also installing dependencies:")
                for item in dependencies:
                    typer.echo(f"  • {_describe_dependency(item)}")

            # 8. Copy skills
            selected = selected + dependencies
            typer.echo()
            for item in selected:
                src = item["source_path"]
                result = copy_skill(src, dest, repo_url, dest_name=item["name"])
                typer.echo(f"  ✅ Installed {item['name']} → {result}")

    except GitError as exc:
        typer.echo(f"❌ {exc}", err=True)
        raise typer.Exit(1) from exc

    # 9. Update config
    cfg.set_last_destination(conf, str(dest))
    cfg.add_recent_repo(conf, repo_url)
    cfg.save_config(conf)

    typer.echo(f"\n🎉 Done! {len(selected)} skill(s) installed to {dest}")


# ── Helpers ──────────────────────────────────────────────────────────


def _describe_dependency(item: dict) -> str:
    """One-line description of an auto-installed dependency and why it's included."""
    text = f"{item['name']}  ← required by {', '.join(item['required_by'])}"
    note = _DEPENDENCY_STATUS_NOTES.get(item.get("status"))
    if note:
        text += f"  ({note})"
    return text


def _build_summary(dest, repo_url, selected, dependencies=()) -> str:
    lines = [
        "",
        "┌─────────────────────────────────────────────",
        "│  Install Summary",
        "├─────────────────────────────────────────────",
        f"│  Destination : {dest}",
        f"│  Source repo : {repo_url}",
        "│  Skills:",
    ]
    for item in selected:
        lines.append(f"│    • {item['name']}")
    if dependencies:
        lines.append("│")
        lines.append("│  Dependencies (installed automatically):")
        for item in dependencies:
            lines.append(f"│    • {_describe_dependency(item)}")
    lines.append("└─────────────────────────────────────────────")
    lines.append("")
    return "\n".join(lines)
