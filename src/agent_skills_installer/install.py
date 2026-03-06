"""Install command – orchestrates the interactive skill installation flow."""

from __future__ import annotations

from pathlib import Path

import typer

from agent_skills_installer import config as cfg
from agent_skills_installer import tui
from agent_skills_installer.git_ops import GitError, cloned_repo
from agent_skills_installer.skills import SkillInfo, copy_skill, discover_skills


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
    typer.echo(f"\n⏳ Cloning {repo_url} …")
    try:
        with cloned_repo(repo_url) as repo_path:
            skills = discover_skills(repo_path)

            if not skills:
                typer.echo(
                    "❌ No skills found in this repo (looked in skills/ subdirectory).",
                    err=True,
                )
                raise typer.Exit(1)

            typer.echo(f"Found {len(skills)} skill(s).\n")

            # 5. Select skills
            skill_dicts = [
                {
                    "name": s.name,
                    "description": s.description,
                    "source_path": s.source_path,
                }
                for s in skills
            ]

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

            # 6. Confirmation (skip when skill was specified on CLI)
            if not skill_name:
                summary = _build_summary(dest, repo_url, selected)
                if not tui.prompt_confirm_actions(summary):
                    typer.echo("Aborted.")
                    raise typer.Exit(0)

            # 7. Copy skills
            typer.echo()
            for item in selected:
                src = item["source_path"]
                result = copy_skill(src, dest, repo_url)
                typer.echo(f"  ✅ Installed {item['name']} → {result}")

    except GitError as exc:
        typer.echo(f"❌ {exc}", err=True)
        raise typer.Exit(1) from exc

    # 8. Update config
    cfg.set_last_destination(conf, str(dest))
    cfg.add_recent_repo(conf, repo_url)
    cfg.save_config(conf)

    typer.echo(f"\n🎉 Done! {len(selected)} skill(s) installed to {dest}")


# ── Helpers ──────────────────────────────────────────────────────────


def _build_summary(dest, repo_url, selected) -> str:
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
    lines.append("└─────────────────────────────────────────────")
    lines.append("")
    return "\n".join(lines)
