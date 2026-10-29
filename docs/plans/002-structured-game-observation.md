# Plan 002 — Structured game observation

**Scope:** first functional Spec 002 slice. References `docs/specs/002-structured-game-observation.md`.

## Deliverables

1. Pure `observation.py`: normalized user-calibrated named ROIs, atomic local opt-in persistence, location-scoped OCR, confidence/source/freshness ledger; unknown and conflicting facts cannot become authoritative.
2. `icon_matcher.py`: strict local Pillow template matching for user-calibrated single-icon slots only, with an unknown result when score/margin/contrast are inadequate. Never model unlabeled enemy icons as complete formations.
3. `session.py` / `coach.py` / `local_ocr.py`: apply ROI and icon observations in the existing single-worker pipeline, preserve Start/End invalidation and cloud consent, show manual nonmodal clarification when necessary. Template storage remains in gitignored `config/`.
4. `scripts/benchmark_observation.py`: user-consented benchmark manifest with precision, false positives/negatives, latency percentiles and question frequency. No real client benchmark should be fabricated.
5. Repo-level `.agents/skills/ub-mode` adapter + optional pinned personal installer; Coach CI and PR rules override any suggestion of unconditional direct main push.

## Validation / hazards

- Behavior tests: ROI scales/invalid bounds, atomic persistence, off-region text, lower-confidence, conflicting OCR facts, expiring snapshots, unknown/ambiguous icon, late game isolation, benchmark false positives.
- GitHub Actions on Windows and Linux; Python compile + workflow validator; GUI headless smoke test if available.
- Risk: icon template matching can be sensitive to art/animation, UI cropping, scaled fonts and OCR coordinate transforms. Do not claim client accuracy without real labeled screenshots.
- Risk: screenshot/Png templates can contain personal information. Save only after explicit user action; the entire `config/` tree is ignored and no frame is sent to cloud by this change.
- Privacy: leave model authorizations as-is; deterministic observation stays local. No persistence of raw frames by default.
- Rollback: revert PR; delete local `config/calibration.json` and templates to remove calibration.

## Follow-up gates (real client)

- Capture multiple sanitized game versions and monitor resolutions after opt-in; measure precision/FPR/latency with the benchmark script.
- Add region-specific shop card/gear detectors; validate a robust enemy identity and full-board tracker, replacing single-icon fragments only with evidence.