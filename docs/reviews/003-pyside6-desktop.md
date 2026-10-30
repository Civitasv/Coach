# Review 003 — UI migration

Scope: replace Tk window, keep the existing read-only observation/model boundaries.

- [x] Shell layout and user pathways implemented (preview + chat + controls + calibration).
- [x] Capture writes latest frame into a single slot; OCR event queue bounded.
- [x] No automatic image upload; text consent and manual screenshot consent separate.
- [x] Start/End generation guards maintained, including late model answers.
- [x] Missing facts use a question card, not a modal dialog during gameplay.
- [ ] Windows actual game visual alignment and OCR latency: **pending real client**.
- [ ] Independent reviewer: **not available; author review only**.
- [ ] crapper/dryer/mutator: **not run** (unavailable in this environment).

This log records a code-based self-review only, not evidence of gameplay accuracy.