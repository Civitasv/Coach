# Architecture — Coach

## Product intent

Windows-first, local-first **read-only** gameplay coach. PySide6 shell presents a live captured viewport and a persistent two-way chat within a match. Users explicitly click Start, Pause, End.

## Data flow

```text
User-selected rectangle → Observer (mss capture, single latest frame)
    → local RapidOCR / strict local IconMatcher / calibrated ROIs
    → bounded OCR event queue → desktop_ui.py on Qt main thread
    → GameSession / FactLedger / Match (trusted + expiring state)
    → left preview overlay and compact facts
    → advice.py deterministic hints / missing-fact question card
    → optional consented text provider requests → right conversation timeline
Manual screenshot confirmation → optional image provider analysis
```

## Dependency map

- `coach.py`: entrypoint only.
- `desktop_ui.py`: PySide6 coordinator; single writer to GameSession, API permission prompts and per-game model-epoch guards.
- `qt_widgets.py`: presentational preview and chat; must not initiate game capture/cloud calls.
- `observer.py`: local worker; captures one frame into one slot, deduplicates for OCR, capped event queue, no model API.
- `local_ocr.py`/`icon_matcher.py`: local OCR and abstaining icon matcher.
- `observation.py`/`session.py`/`engine.py`: source, confidence, expiry and match state (no Qt).
- `advice.py`: safe text prompts/offline hints. `providers.py`: explicit cloud/model boundary.

## Invariants

1. Render only confirmed facts; expired evidence is "未知"; uncalibrated icon slots cannot be guessed from generic OCR words.
2. `idle → active → ended` is explicit. `run_id` gates OCR/model work and separate `model_epoch` rejects old responses following provider change or pause.
3. Cloud text and cloud image transmission require separate user permission. The automatic observer has no outbound network calls.
4. Screenshot frames are not persisted by default, and a single-slot buffer prevents preview backlog. Per-match summaries are stored locally without API secrets or screenshots.
5. UI updates happen only on the Qt GUI thread; worker threads write into queues / single-frame buffer.
6. Never read game memory, intercept packets, automate gameplay or bypass client protections.
7. GUI smoke tests in Qt offscreen do not prove performance or game-specific OCR fidelity on Windows.

## Planned follow-up

Sanitized Windows gameplay fixtures for calibration and recognition accuracy; hero icon training; session-scoped enemy lineup and pool correctness; accessibility keyboard shortcuts and HiDPI manual QA.