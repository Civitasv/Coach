# Review 002 — Spec 002 first implementation slice

**Context:** author-review; independent reviewer not available in this run.

## Evidence log

1. Read Coach AGENTS, architecture, Spec 002, code, tests, and upstream `ub-mode/SKILL.md`; reviewed GitHub repo state.
2. Wrote `tests/test_observation.py` before implementing `observation.py` and `icon_matcher.py`. Confirmed expected import failure. Added passing core tests.
3. Added session-level scoped observation and changing enemy/shop icon fragments, and per-sample benchmark tests. Existing tests continue passing.
4. Added Tk calibration/opt-in template capture, README, plan and CI compile targets. Verified via local Python unit tests and automated CI on PR head where available.
5. Reduced false claims: exact public stock stays behind verified panel/user correction; icon is partial evidence; no game-specific accuracy claims; absent benchmark data returns `pending_dataset`.

## Review risks and deferrals

- Real Windows gameplay screenshot benchmark **not run**: no consented labeled captures or game client in this environment. This blocks claiming real OCR accuracy/precision, not pure-model behavior.
- `crapper`, `dryer`, `mutator` not installed or run; do not claim CRAP, duplication or mutation targets met.
- Template matcher is heuristic and not a trained classifier; moving/animated icons require further validation.
- No independent code-review subagent available; author self-review only.
- Scope does **not** include full automated opponent lineup recognition, exact probability model or UI-controlled card/gear classifiers. Subsequent PRs must complete those pieces.