"""CLI entry point – Typer application with install (default) and update commands."""

from __future__ import annotations

import typer

from agent_skills_installer import __version__

app = typer.Typer(
    name="agent-skills-installer",
    help="Copy agent skills from git repos into local directories for coding agents.",
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"agent-skills-installer {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Agent Skills Installer – copy skills from git repos to local directories."""
    # If no subcommand was given, default to install
    if ctx.invoked_subcommand is None:
        _install_command()


@app.command("install")
def _install_command(
    destination: str | None = typer.Option(
        None,
        "--destination",
        "-d",
        help="Destination directory for skills (skip interactive prompt).",
    ),
    source: str | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Source git repo URL (skip interactive prompt).",
    ),
    skill: str | None = typer.Option(
        None,
        "--skill",
        "-k",
        help="Skill name to install (skip selection and confirmation).",
    ),
) -> None:
    """Install new skills from a git repo (default command)."""
    from agent_skills_installer.install import run_install

    try:
        run_install(destination=destination, source=source, skill_name=skill)
    except KeyboardInterrupt:
        typer.echo("\nAborted.")
        raise typer.Exit(0)


@app.command("update")
def _update_command(
    destination: str | None = typer.Option(
        None,
        "--destination",
        "-d",
        help="Destination directory to scan for installed skills (skip interactive prompt).",
    ),
    skill: str | None = typer.Option(
        None,
        "--skill",
        "-k",
        help="Skill name to update (skip confirmation).",
    ),
) -> None:
    """Update previously installed skills from their source repos."""
    from agent_skills_installer.update import run_update

    try:
        run_update(destination=destination, skill_name=skill)
    except KeyboardInterrupt:
        typer.echo("\nAborted.")
        raise typer.Exit(0)
