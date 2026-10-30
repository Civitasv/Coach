# Spec 004 — Isolated, self-preparing desktop startup

**Status:** Implemented in PR; Windows installation and game-client smoke test pending.

## Goal

Double-clicking Coach's Windows launcher must be enough to prepare and reuse a project-owned Python virtual environment, without globally installing application dependencies. Provide an equivalent shell launcher for developer machines.

## Acceptance criteria

- **AC-001:** Windows `run.bat` and Unix `run.sh` find Python 3.11+, invoke one standard-library bootstrap and do not call global `pip install`.
- **AC-002:** First launch creates `.venv` under repository root, installs requirements into **that** environment and executes `coach.py` with the venv interpreter; the environment and credentials remain local and `.venv` is gitignored.
- **AC-003:** Repeated launches do not run pip when requirements, Python version, and required installed package names are unchanged; changed requirements or absent packages trigger repair.
- **AC-004:** Interrupted/failed installation never writes a success stamp. An invalid or incompatible existing venv must produce a visible error and never silently fall back to system Python.
- **AC-005:** GitHub Actions for Windows and Linux bootstraps the same `.venv` and executes code compilation, workflow checks, unit/Qt offscreen tests, and `pip check` with its Python.

## Verification

Use stdlib-only mocked bootstrap tests for first/repeated/failed/missing-package runs; perform a local smoke with an empty requirements file; observe Windows/Linux CI on the PR head. Actual user's Windows double-click remains an explicit manual QA checkpoint.

## Non-goals

Bundling a Python interpreter as a standalone executable, offline first-install, pinning every transitive dependency in a lockfile, signing Windows installers, or adding any network request beyond `pip install` from configured package indexes.