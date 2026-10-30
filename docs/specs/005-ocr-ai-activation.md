# Spec 005 — OCR diagnostics and AI activation recovery

**Status:** In progress — implementation submitted for CI, real-client validation pending.

## Goal

A player who has chosen the game screen and entered a model key must be able to tell whether screenshot capture, local OCR, AI authorization or API inference is failing, and get a visible response without depending on successful OCR.

## Acceptance criteria

- **AC-001:** Local screen capture continues when the OCR model fails to initialize/recognize; OCR errors and initialization progress are displayed distinctly from no-text observations.
- **AC-002:** A user-calibrated HUD ROI accepts exactly one high-confidence bare numeric value for health/energy/round; an uncalibrated or ambiguous digit cannot become a confirmed fact.
- **AC-003:** The primary UI exposes a manual text-only AI recommendation action usable with zero recognized OCR lines, guarded by cloud-text consent and per-match model limits.
- **AC-004:** Opted-in automatic advice may run once on initial empty OCR and is change-gated; it must not continuously call the model when nothing changes.
- **AC-005:** Model HTTP errors expose the status and a bounded provider error message without disclosing the user's secret; non-JSON text results remain labelled as unstructured, not verified state.
- **AC-006:** Windows and Ubuntu CI cover the failure/empty-value path. Real Windows OCR recognition and DeepSeek account credentials are manually tested before accuracy/cost claims.

## Verification

Synthetic screenshot OCR mocks for error recovery and scoped numeric-only readings; Qt offscreen UI tests for button, auto gate and visible failure; HTTP-error mock; Python 3.11 Windows and Ubuntu CI. Real client tests require user-provided sanitized frames and an explicit API test (not available here).

## Non-goals

Guaranteeing recognition of all hero icons, assuming model request success from API key presence, bypassing consent, guessing card inventories, or automating gameplay.
