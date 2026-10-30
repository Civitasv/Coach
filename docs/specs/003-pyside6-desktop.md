# Spec 003 — PySide6 split-view desktop UI

**Status:** Implementation candidate, pending real-client visual QA.

## Goal

Replace the monolithic Tkinter window with a modern, resizable desktop shell. Keep the existing local OCR, icon recognition, match state, and API provider logic intact while enabling uninterrupted game observation and ChatGPT-style two-way coaching.

## Acceptance criteria

- **AC-001:** App starts as a PySide6 desktop window with a draggable left live-preview / right coaching-chat split. The main screen has simple controls; configuration and ROI calibration are collapsed by default.
- **AC-002:** Selected game area appears on the left continuously while the local observer is active. HUD shows current health, energy, round, weapon, five trusted shop slots and enemy information without converting OCR guesses into facts.
- **AC-003:** The right pane preserves a per-match message timeline, supports proactive agent advice, free-form follow-ups, and a separate, non-modal answer control for missing facts.
- **AC-004:** Start, Pause/Resume and End preserve session boundaries. Closing an active match asks for confirmation. Out-of-epoch OCR or LLM results cannot contaminate a new match. Ending saves summary locally without screenshots or API keys.
- **AC-005:** Fast screen capture and local OCR do not block the UI or generate an unbounded frame queue. Automatic model calls are opt-in, change-triggered, throttled and capped.
- **AC-006:** Cloud text consent and image consent remain separate; the UI never sends screen pixels on automatic text requests. Cloud follow-ups require consent even when auto-coaching is disabled.
- **AC-007:** Existing ROI calibration and manually-confirmed icon template workflows stay available; test execution includes Python 3.11 on Windows and Linux, with Qt offscreen smoke tests.

## Non-goals

Pixel-perfect reproduction of ChatGPT, detecting unlabelled heroes without samples, automatic playing, direct memory or traffic access, undocumented gameplay rules, and claims of measured Windows screenshot latency without real-world data.

## Verification

- Unit tests for bounded observer queue, end/start isolation and consent.
- Qt offscreen UI tests for layout, buttons, per-match state and chat answer routing.
- GitHub Actions Windows and Linux checks plus a manual Windows gameplay visual pass (manual test pending).