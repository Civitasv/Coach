# Plan 004 — Isolated bootstrap

1. Add a stdlib-only `scripts/bootstrap.py` with a single owner for environment creation, version verification, requirements fingerprints, local package probes, and launching. Do not touch application UI code.
2. Route `run.bat` and `run.sh` through it. Accept optional `COACH_PYTHON` override (host interpreter only). Require Python 3.11+. Only `.venv` receives `pip install`.
3. Use a small in-venv stamp keyed to requirements SHA-256 and Python major/minor, written only after successful installation and a package presence probe. On invalid venv, fail with recovery guidance instead of executing global pip.
4. Replace CI's global dependency install with the same `--prepare` bootstrap; run all subsequent commands using platform-specific `.venv` Python paths.
5. Add mock-based regression tests and document user startup, limitations and recovery path.

## Risks and rollback

- First run needs internet and an installed Python with `venv`/`ensurepip`; surface clear failures.
- Existing `.venv` may become invalid when its underlying interpreter is removed. Do not destroy it automatically; direct the user to remove and rerun.
- No concurrent-bootstrap locking in this slice: do not double-launch during first setup. A future installer can use robust locking if observed necessary.
- Roll back by reverting this PR, which restores old scripts; user `.venv` is local and ignored by git.

## Validation record

Initial TDD run: failed with missing bootstrap module (expected). Follow-up local run: 8 bootstrap tests passed. CI Windows/Linux pending PR run. No full Windows game-client launch performed locally.