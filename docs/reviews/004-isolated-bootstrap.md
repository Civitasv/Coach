# Review 004 — Local venv startup

**Reviewer:** author self-review; no independent reviewer available at implementation time.

## Findings

- The former Windows launcher invoked `py -3 -m pip install` into whatever interpreter the launcher selected, potentially polluting system Python and reinstalling every launch.
- Shared bootstrap now starts via stdlib host Python only, with installation and execution both routed to `.venv`.
- Requirements hash, Python version and package presence probe prevent needless reinstalls while repairing obvious missing packages.
- Failure paths retain nonzero exit status and do not mark installation complete.

## Limitations

- An initial download from a pip index is still required; this is not a prebundled offline binary.
- Underlying transitive package version drift remains possible because `requirements.txt` is range-constrained rather than fully locked.
- Concurrent first-run launches are not coordinated.
- Windows double-click visual UX is not tested locally; CI is authoritative for Python tests, not human desktop QA.
- crapper, dryer, mutator and independent reviewer were unavailable / not run.

## Evidence

- Expected red: bootstrap module absent, tests fail.
- Local green: 8 bootstrap tests passing on Python 3.13. See CI job logs on PR for Windows and Linux Python 3.11.