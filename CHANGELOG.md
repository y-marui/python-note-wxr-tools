# Changelog

## [Unreleased]

### Added
### Changed

- Bumped `gitleaks` to v8.30.1 and `pre-commit-hooks` to v6.0.0; wired the `check-markdown-heading-language` pre-commit hook.
- Aligned CI with `python-closed-template`: `build` job now runs `uv build` instead of an import smoke test, and `astral-sh/setup-uv` steps enable dependency caching.
- `AI_CONTEXT.md`'s Tech Stack table now references `docs/dev-charter/topics/python/PYTHON_DEV_ENV.md` / `PYTHON_CLI.md` instead of restating the general policy (y-marui/dev-charter#131).

### Fixed
