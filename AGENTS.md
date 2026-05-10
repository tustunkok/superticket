# AGENTS.md — superticket

## Project Basics
- **Language:** Python 3.12+ (enforced by `pyproject.toml` and `.python-version`).
- **Entrypoint:** `main.py` (currently a scaffold).
- **Package manager:** `uv` (PEP 621). Every Python command must be run with `uv run`.

## Tooling — Current State
- **No test runner, linter, formatter, typechecker, or CI is configured yet.**
- Do not assume `pytest`, `ruff`, `mypy`, etc. are available unless they appear in `pyproject.toml` dependencies.

## Specifications
- `SPECS.md` contains the high-level system specification (ticketing + AI triage). It is not executable configuration.

## Architecture
- `DESIGN.md` is a living document capturing the current architecture and design decisions. It must be kept updated as the project evolves and should be read as the primary source of architectural context at any point in time.

## Commit Policy
- After each significant change, ask the user whether or not to commit the changes before proceeding.

## Versioning
- Use semantic versioning with stage suffixes:
  - Alpha: `x.x.x-alpha.x`
  - Beta: `x.x.x-beta.x`
  - Release: `x.x.x`

## Verified Commands
- Run the scaffold: `uv run python main.py`
- (Any other command requires adding dependencies to `pyproject.toml` first.)
