"""Interactive TUI prompts built on questionary."""

from __future__ import annotations

from pathlib import Path

import questionary
from questionary import Choice
from rich.console import Console
from rich.text import Text

# ── Styling ──────────────────────────────────────────────────────────

_BASE_STYLE_RULES = [
    ("qmark", "fg:cyan bold"),
    ("question", "fg:white bold"),
    ("pointer", "fg:cyan bold"),
    ("highlighted", "fg:cyan bold"),
    ("selected", "fg:green"),
    ("answer", "fg:green bold"),
]

STYLE = questionary.Style(_BASE_STYLE_RULES)

# Separate style for the skills checkbox list: overriding "text" here (used by
# questionary for the "Description: ..." line shown below the list) would
# otherwise recolor unrelated prompts (e.g. the plain destination/repo lists)
# that also render through the "text" class.
SKILL_LIST_STYLE = questionary.Style(
    [
        *_BASE_STYLE_RULES,
        ("skill-name", "fg:white bold"),
        ("skill-desc", "fg:#888888"),
        ("text", "fg:yellow"),
    ]
)

# Reserve room for the pointer/checkbox indicator prefix questionary draws
# before each row (e.g. "❯ ● ").
_ROW_PREFIX_WIDTH = 4
_MAX_NAME_COLUMN = 30
_MIN_DESC_COLUMN = 20

# ── Predefined destination directories ───────────────────────────────

DEFAULT_DESTINATIONS = [
    "~/.agents/skills/",
    "~/.cursor/skills/",
    "~/.claude/skills/",
    "~/.opencode/skills/",
    "~/.copilot/skills/",
]

# Suggested when the current directory is a git repo (i.e. has a .git/), so
# project-local skills can be installed alongside the repo's own config.
PROJECT_DESTINATIONS = [
    ".github/skills/",
    ".claude/skills/",
    ".agents/skills/",
    ".opencode/skills/"
]

OTHER_SENTINEL = "✏️  Other (enter path manually)"
NEW_REPO_SENTINEL = "✏️  Enter a new repo URL"


# ── Public prompt functions ──────────────────────────────────────────


def prompt_destination(last_used: str | None = None) -> Path:
    """Ask the user to choose a destination directory.

    Returns an absolute :class:`Path`.
    """
    cwd = Path.cwd()
    project_destinations = []
    if (cwd / ".git").exists():
        project_destinations = [str(cwd / rel) for rel in PROJECT_DESTINATIONS]

    choices: list[Choice | str] = []

    # Last-used destination first (if available and not already suggested below)
    if last_used and last_used not in DEFAULT_DESTINATIONS and last_used not in project_destinations:
        choices.append(Choice(title=f"{last_used}  (last used)", value=last_used))

    for dest in project_destinations:
        choices.append(Choice(title=dest, value=dest))

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
    term_width = Console().size.width
    name_column = min(
        max((len(s["name"]) for s in skills), default=0), _MAX_NAME_COLUMN
    )

    choices = [
        _build_skill_choice(
            s["name"], s.get("description", ""), name_column, term_width
        )
        for s in skills
    ]

    selected_names: list[str] | None = None
    while True:
        selected_names = questionary.checkbox(
            "Select skills to install (space to toggle, enter to confirm):",
            choices=choices,
            style=SKILL_LIST_STYLE,
            show_description=True,
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


def _build_skill_choice(
    name: str, description: str, name_column: int, term_width: int
) -> Choice:
    """Build a :class:`Choice` with a bold name column and a dimmed, truncated description."""
    title: list[tuple[str, str]] = [("class:skill-name", name.ljust(name_column))]

    description = (description or "").strip()
    if description:
        one_line = " ".join(description.split())
        desc_column = max(
            term_width - _ROW_PREFIX_WIDTH - name_column - 3, _MIN_DESC_COLUMN
        )
        desc_text = Text(one_line)
        desc_text.truncate(desc_column, overflow="ellipsis")
        title.append(("class:skill-desc", f"   {desc_text.plain}"))

    return Choice(title=title, value=name, description=description or None)
