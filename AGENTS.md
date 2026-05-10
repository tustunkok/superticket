# AGENTS.md — superticket

## Project Basics
- **Language:** Python 3.12+ (enforced by `pyproject.toml` and `.python-version`).
- **Entrypoint:** `main.py` (currently a scaffold).
- **Package manager:** `uv` (PEP 621). Every Python command must be run with `uv run`.

## Tooling — Current State
- **Test runner**: `pytest` (with `pytest-asyncio` and `pytest-cov`)
- **Linter / Formatter**: `ruff`
- **No typechecker or CI is configured yet.**
- Do not assume `mypy`, etc. are available unless they appear in `pyproject.toml` dependencies.

## Testing Policy
- For every testable atomic functionality written, the agent must write a corresponding test. No exceptions. Tests should be written immediately after the feature implementation, not deferred.
- Use `pytest` and `pytest-asyncio` for async tests. Aim for high coverage on business logic, especially state machine transitions and service layer operations.

## Specifications
- `SPECS.md` contains the high-level system specification (ticketing + AI triage). It is not executable configuration.

## Architecture
- `DESIGN.md` is a living document capturing the current architecture and design decisions. It must be kept updated as the project evolves and should be read as the primary source of architectural context at any point in time.

## Commit Policy
- After each significant change, ask the user whether or not to commit the changes before proceeding.
- When committing, always include **all** changes: added, modified, and removed files. Use `git add -A` to ensure nothing is left out.

## Versioning
- Use semantic versioning with stage suffixes:
  - Alpha: `x.x.x-alpha.x`
  - Beta: `x.x.x-beta.x`
  - Release: `x.x.x`

## Verified Commands
- Run the scaffold: `uv run python main.py`
- (Any other command requires adding dependencies to `pyproject.toml` first.)
