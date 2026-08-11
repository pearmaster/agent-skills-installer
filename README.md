# agent-skills-installer

A CLI tool to copy [Agent Skills](https://agentskills.io/) from git repos into local directories for coding agents.

## Install

```bash
uv tool install agent-skills-installer
```

Or run directly without installing:

```bash
uvx agent-skills-installer
```

> **Note:** `uv` must be installed. See https://docs.astral.sh/uv/getting-started/installation/ for installation instructions.

## Usage

### Install skills (default command)

```bash
# Interactive — prompts for destination, repo, and skill selection
agent-skills-installer

# Fully non-interactive
agent-skills-installer install \
  --destination ~/.claude/skills/ \
  --source https://github.com/anthropics/skills \
  --skill skill-creator
```

**Options:**

| Flag | Short | Description |
|------|-------|-------------|
| `--destination` | `-d` | Destination directory (skip prompt) |
| `--source` | `-s` | Source git repo URL (skip prompt) |
| `--skill` | `-k` | Skill name to install (skip selection & confirmation) |

### Update skills

```bash
# Interactive — prompts for destination, confirms before updating
agent-skills-installer update

# Non-interactive
agent-skills-installer update -d ~/.claude/skills/ -k skill-creator
```

**Options:**

| Flag | Short | Description |
|------|-------|-------------|
| `--destination` | `-d` | Directory to scan for installed skills (skip prompt) |
| `--skill` | `-k` | Skill name to update (skip confirmation) |

## How it works

1. Skills are discovered in the source repo, trying these layouts in order and using the first that matches:
   - `skills/` or `.claude/skills/` (searched recursively, so `skills/<category>/<name>/` works)
   - a `SKILL.md` at the repo root — the repo is itself a single skill
   - a repo-wide search, covering root-level collections (`<name>/SKILL.md`) and plugin layouts (`<plugin>/skills/<name>/SKILL.md`)
2. Each skill directory (containing a `SKILL.md` with a `name` in its frontmatter) is copied to the destination, named after that `name`
3. `metadata.git-repo` and `metadata.git-sha` entries are added to the SKILL.md frontmatter to track the source repo and the commit the skill was copied at
4. The `update` command uses that metadata to refresh skills from their original repos

Configuration (last destination, recent repos) is saved to `~/.agent-skills-installer/config.toml`.

## License

MIT
