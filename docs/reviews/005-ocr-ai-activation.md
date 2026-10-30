# Review 005 — OCR/AI activation

- Root causes verified from code: API key configuration alone does not activate advice; auto advice was suppressed on empty OCR. OCR initialization used to happen before any frame was saved and any exception stopped the observer.
- Changes: capture survives OCR errors; status/errors are explicit; manual advice on main screen; empty OCR no longer blocks an authorized AI request; calibrated pure-number OCR is conservative; provider errors include bounded details.
- Verification pending: GitHub Actions Windows/Linux tests and real-world screenshot/paid DeepSeek usage (not run).
- Privacy: no new automatic screenshot upload path; model text and vision still require independent opt-in; remote errors redact keys.
- Residual risk: unknown game HUD layouts; icons require templates; no real-client dataset. Author self-review only, no independent reviewer/complexity tooling recorded.
