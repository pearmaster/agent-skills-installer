# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1]

### Fixed

- When `skills/` (or `.claude/skills/`) yields any skills, the other preferred
  root is no longer also searched. Previously both were scanned and merged
  even when one already had results.

## [0.3.0]

### Added

- Skills are now discovered across several repo layouts instead of only `skills/`.
  Tried in order: `skills/` and `.claude/skills/` (searched recursively, so
  `skills/<category>/<name>/` works), then a root `SKILL.md` for single-skill
  repos, then a repo-wide search covering root-level collections and
  `<plugin>/skills/<name>/` plugin layouts.
- `metadata.git-sha` is recorded alongside `metadata.git-repo`, so `install`
  can report whether a skill is already installed, upgradable, or would replace
  a skill of the same name from a different repo, and `update` can skip skills
  that are already up to date.
- The destination prompt suggests project-local directories (`.claude/skills/`,
  `.github/skills/`, `.agents/skills/`, `.opencode/skills/`) when run inside a
  git repo.
- The skill picker shows names and descriptions in aligned columns sized to the
  terminal.

### Changed

- Skills are installed under their frontmatter `name` rather than their source
  directory name, which is also the key `update` matches on. Previously the two
  could disagree, so a skill could be updated into the wrong directory or
  reported as missing from its own repo.
- Repos are cloned in full rather than shallow, so the commit that last touched
  each skill can be determined.
- A `SKILL.md` with no `name` in its frontmatter is now skipped with a warning
  instead of falling back to its directory name.

### Fixed

- `--version` reported `0.1.0` regardless of the released version. The version is
  now single-sourced from `agent_skills_installer.__version__`.
- Skill names are validated before use as directory names, so a name such as
  `../../.ssh` from an untrusted repo can no longer write outside the
  destination directory.

## [0.2.1]

- Error handling improvements.

## [0.2.0]

- Initial published release.
