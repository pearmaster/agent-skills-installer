"""Interactive TUI prompts built on questionary."""

from __future__ import annotations

from pathlib import Path

import questionary
from questionary import Choice

# ── Styling ──────────────────────────────────────────────────────────

STYLE = questionary.Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "fg:white bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("answer", "fg:green bold"),
    ]
)

# ── Predefined destination directories ───────────────────────────────

DEFAULT_DESTINATIONS = [
    "~/.agents/skills/",
    "~/.cursor/skills/",
    "~/.claude/skills/",
    "~/.opencode/skills/",
    "~/.copilot/skills/",
]

OTHER_SENTINEL = "✏️  Other (enter path manually)"
NEW_REPO_SENTINEL = "✏️  Enter a new repo URL"


# ── Public prompt functions ──────────────────────────────────────────


def prompt_destination(last_used: str | None = None) -> Path:
    """Ask the user to choose a destination directory.

    Returns an absolute :class:`Path`.
    """
    choices: list[Choice | str] = []

    # Last-used destination first (if available and not already in default list)
    if last_used and last_used not in DEFAULT_DESTINATIONS:
        choices.append(Choice(title=f"{last_used}  (last used)", value=last_used))

    for dest in DEFAULT_DESTINATIONS:
        choices.append(Choice(title=dest, value=dest))

    choices.append(Choice(title=OTHER_SENTINEL, value=OTHER_SENTINEL))

    answer = questionary.select(
        "Select destination directory:",
        choices=choices,
        style=STYLE,
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    if answer == OTHER_SENTINEL:
        answer = questionary.text(
            "Enter destination directory path:",
            style=STYLE,
        ).ask()
        if not answer:
            raise KeyboardInterrupt

    dest_path = Path(answer).expanduser().resolve()

    if not dest_path.exists():
        create = questionary.confirm(
            f"Directory {dest_path} does not exist. Create it?",
            default=True,
            style=STYLE,
        ).ask()
        if create is None or not create:
            raise KeyboardInterrupt
        dest_path.mkdir(parents=True, exist_ok=True)

    return dest_path


def prompt_repo(recent_repos: list[str] | None = None) -> str:
    """Ask the user to pick a git repo URL from recent history or enter a new one."""
    choices: list[Choice | str] = []

    for url in recent_repos or []:
        choices.append(Choice(title=url, value=url))

    choices.append(Choice(title=NEW_REPO_SENTINEL, value=NEW_REPO_SENTINEL))

    answer = questionary.select(
        "Select source git repo:",
        choices=choices,
        style=STYLE,
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    if answer == NEW_REPO_SENTINEL:
        answer = questionary.text(
            "Enter git repo URL:",
            style=STYLE,
            validate=lambda val: (True if val.strip() else "Please enter a valid URL"),
        ).ask()
        if not answer:
            raise KeyboardInterrupt
        answer = answer.strip()

    return answer


def prompt_select_skills(skills: list[dict]) -> list[dict]:
    """Display a checkbox list of skills and let the user pick one or more.

    Each item in *skills* must have ``name`` and ``description`` keys.
    Returns the selected subset (same dicts).
    """
    choices = [
        Choice(
            title=_format_skill_label(s["name"], s["description"]),
            value=s["name"],  # use name as the tracking value
        )
        for s in skills
    ]

    selected_names: list[str] | None = None
    while True:
        selected_names = questionary.checkbox(
            "Select skills to install (space to toggle, enter to confirm):",
            choices=choices,
            style=STYLE,
        ).ask()

        if selected_names is None:
            raise KeyboardInterrupt

        if len(selected_names) == 0:
            questionary.print("⚠  Please select at least one skill.", style="fg:yellow")
            continue
        break

    return [s for s in skills if s["name"] in selected_names]


def prompt_confirm_actions(summary: str) -> bool:
    """Show a summary and ask the user to confirm."""
    questionary.print(summary, style="bold")
    answer = questionary.confirm(
        "Proceed?",
        default=True,
        style=STYLE,
    ).ask()
    if answer is None:
        raise KeyboardInterrupt
    return answer


# ── Helpers ──────────────────────────────────────────────────────────


def _format_skill_label(name: str, description: str, max_desc: int = 256) -> str:
    """Format a skill name + description for display in a list."""
    if not description:
        return name
    desc = description[:max_desc]
    if len(description) > max_desc:
        desc += "…"
    return f"{name} — {desc}"
