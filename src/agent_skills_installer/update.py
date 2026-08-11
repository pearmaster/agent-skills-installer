"""Update command – refreshes locally installed skills from their source repos."""

from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path

import typer

from agent_skills_installer import config as cfg
from agent_skills_installer import tui
from agent_skills_installer.git_ops import GitError, cloned_repo, last_commit_sha_for_path
from agent_skills_installer.skills import (
    add_git_metadata,
    copy_skill,
    discover_skills,
    find_local_skills_with_git,
    parse_skill_frontmatter,
)


def run_update(
    *,
    destination: str | None = None,
    skill_name: str | None = None,
) -> None:
    """Run the update flow.

    When *destination* or *skill_name* are provided the corresponding
    interactive prompts / confirmations are skipped.
    """
    # 1. Load config
    conf = cfg.load_config()

    # 2. Choose destination
    if destination:
        dest = Path(destination).expanduser().resolve()
        if not dest.is_dir():
            typer.echo(f"❌ Directory does not exist: {dest}", err=True)
            raise typer.Exit(1)
    else:
        last_dest = cfg.get_last_destination(conf)
        dest = Path(tui.prompt_destination(last_dest or None))

    # 3. Scan for installed skills that track a git repo
    local_skills = find_local_skills_with_git(dest)

    if not local_skills:
        typer.echo("No skills with git metadata found in this directory.")
        raise typer.Exit(0)

    # If a specific skill was requested, narrow the list
    if skill_name:
        local_skills = [
            (d, u, n) for d, u, n in local_skills if skill_name in (n, d.name)
        ]
        if not local_skills:
            typer.echo(
                f"❌ Skill '{skill_name}' not found (or has no git metadata) in {dest}",
                err=True,
            )
            raise typer.Exit(1)

    # Group by repo URL, carrying each skill's frontmatter name alongside its directory
    by_repo: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for skill_dir, repo_url, name in local_skills:
        by_repo[repo_url].append((skill_dir, name))

    # 4. Build update plan (before touching any files)
    update_plan: list[dict] = []  # {"skill_dir": Path, "repo_url": str, "name": str}
    not_found: list[dict] = []
    up_to_date: list[dict] = []

    for repo_url, entries in by_repo.items():
        typer.echo(f"\n⏳ Checking {repo_url} …")
        try:
            with cloned_repo(repo_url) as repo_path:
                remote_skills = discover_skills(repo_path)
                remote_by_name = {s.name: s for s in remote_skills}

                for skill_dir, name in entries:
                    remote = remote_by_name.get(name)
                    if remote is None:
                        not_found.append({"name": name, "repo_url": repo_url})
                        continue

                    local_sha = _read_local_sha(skill_dir)
                    remote_sha = last_commit_sha_for_path(remote.source_path)
                    if local_sha is not None and local_sha == remote_sha:
                        up_to_date.append({"name": name, "repo_url": repo_url})
                        continue

                    update_plan.append(
                        {
                            "name": name,
                            "skill_dir": skill_dir,
                            "repo_url": repo_url,
                            "remote_source": remote.source_path,
                        }
                    )

        except GitError as exc:
            typer.echo(f"⚠️  Failed to clone {repo_url}: {exc}", err=True)
            for _skill_dir, name in entries:
                not_found.append({"name": name, "repo_url": repo_url})
            continue

    if not update_plan:
        if up_to_date:
            typer.echo("\n✅ All skills are already up to date.")
        else:
            typer.echo("\nNo matching remote skills found. Nothing to update.")
        raise typer.Exit(0)

    # 5. Show summary & confirm (skip when skill was specified on CLI)
    if not skill_name:
        summary = _build_update_summary(update_plan, not_found, up_to_date)
        if not tui.prompt_confirm_actions(summary):
            typer.echo("Aborted.")
            raise typer.Exit(0)

    # 6. Perform updates – re-clone each repo (they were cleaned up above)
    updated_count = 0
    repos_needed = {item["repo_url"] for item in update_plan}

    for repo_url in repos_needed:
        items = [i for i in update_plan if i["repo_url"] == repo_url]
        typer.echo(f"\n⏳ Fetching {repo_url} for update …")
        try:
            with cloned_repo(repo_url) as repo_path:
                remote_skills = discover_skills(repo_path)
                remote_by_name = {s.name: s for s in remote_skills}

                for item in items:
                    remote = remote_by_name.get(item["name"])
                    if remote is None:
                        typer.echo(f"  ⚠️  {item['name']} no longer in repo, skipping")
                        continue

                    # Replace the local skill directory
                    local_dir: Path = item["skill_dir"]
                    if local_dir.exists():
                        shutil.rmtree(local_dir)
                    copy_skill(
                        remote.source_path,
                        local_dir.parent,
                        repo_url,
                        dest_name=remote.name,
                    )
                    typer.echo(f"  ✅ Updated {item['name']}")
                    updated_count += 1

        except GitError as exc:
            typer.echo(f"  ❌ Failed to clone {repo_url}: {exc}", err=True)

    # 7. Save config
    cfg.set_last_destination(conf, str(dest))
    cfg.save_config(conf)

    typer.echo(f"\n🎉 Done! {updated_count} skill(s) updated.")
    if up_to_date:
        typer.echo(f"✅ {len(up_to_date)} skill(s) already up to date, skipped.")
    if not_found:
        typer.echo("⚠️  The following skills could not be found in their repos:")
        for item in not_found:
            typer.echo(f"    • {item['name']} ({item['repo_url']})")


# ── Helpers ──────────────────────────────────────────────────────────


def _read_local_sha(skill_dir: Path) -> str | None:
    """Read ``metadata.git-sha`` from an installed skill's SKILL.md, if present."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    try:
        fm = parse_skill_frontmatter(skill_md)
    except Exception:
        return None
    return (fm.get("metadata") or {}).get("git-sha")


def _build_update_summary(
    update_plan: list[dict], not_found: list[dict], up_to_date: list[dict] | None = None
) -> str:
    lines = [
        "",
        "┌─────────────────────────────────────────────",
        "│  Update Summary",
        "├─────────────────────────────────────────────",
        "│  Skills to update:",
    ]
    for item in update_plan:
        lines.append(f"│    • {item['name']}  ← {item['repo_url']}")

    if up_to_date:
        lines.append("│")
        lines.append("│  ✅ Already up to date (skipped):")
        for item in up_to_date:
            lines.append(f"│    • {item['name']}  ({item['repo_url']})")

    if not_found:
        lines.append("│")
        lines.append("│  ⚠️  Not found in remote repo:")
        for item in not_found:
            lines.append(f"│    • {item['name']}  ({item['repo_url']})")

    lines.append("└─────────────────────────────────────────────")
    lines.append("")
    return "\n".join(lines)
