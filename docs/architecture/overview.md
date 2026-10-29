# Architecture — Coach

## Goal

Read-only local-first gameplay coaching, with predictable latency and bounded cloud cost. The user clicks **Start** at the beginning of each match and **End** when it finishes. AI can suggest actions but does not interact with the game.

## Data flow

```text
Selected screen ROI
  → local capture / image-change gate (coach.py)
  → local OCR (local_ocr.py)
  → evidence-aware per-game facts + TTL (session.py)
  → deterministic alerts / missing-field questions (advice.py)
  → optional throttled text LLM (providers.py)
  → non-modal Tk display (coach.py)

Manual opt-in image LLM → confirmed screenshot analysis
                          → cautious pool/opponent snapshots (engine.py)
```

## Boundaries

- `coach.py`: UI, pacing, lifecycle ownership, background worker orchestration, request authorization, event queue. Tk widgets must be mutated only on UI thread.
- `local_ocr.py`: implementation detail behind OCR line/region interfaces. Recognition errors are normal and must be represented explicitly.
- `session.py`: per-game lifecycle and fresh/expired facts; must remain usable without cloud credentials.
- `engine.py`: shared pool/opponent snapshots; only high-confidence confirmed scans mutate exact counts.
- `advice.py`: deterministic guidance and model prompt construction; may not fabricate board state.
- `providers.py`: isolated external-service requests. Must not initiate cloud calls without UI authorization.

## Invariants / non-goals

1. Screenshots and API credentials are not stored by default. Match summaries are local, so their privacy implications should be documented.
2. `idle → active → ended` is explicit; all in-flight work carries a generation/run ID and may be discarded.
3. OCR field extraction is conservative. Facts carry provenance and TTL; stale facts may be shown only with freshness labels.
4. High-frequency observation and slow LLM decisions must remain separate to control latency and cost.
5. An OCR-only path cannot reliably identify icon-only cards, heroes, weapons, or positioning. Future ROI calibration and visual classifiers require a separate spec and evidence.
6. No memory reading, network interception, input automation, or gameplay bypass.

## Evolution seams

- Calibrated HUD/ROI segmentation (test on real, sanitized sample screenshots).
- Hero/equipment icon classification with confidence and unknown class.
- Explicit user-corrected enemy board and remaining-pool model.
- Decision policy with deterministic legality checks and uncertainty-aware questions.
- Per-match metrics for OCR success, inference latency, model calls, and stale-data incidents.

Every change affecting fact contracts, network privacy, session epochs, or decision behavior requires a spec and regression tests.

## Spec 002 structured observation slice

- `observation.py` is the pure ROI/FactLedger boundary: normalized ROIs, schema validation, atomic local config, TTL facts and conflict invalidation. No game/network/Tk APIs.
- `local_ocr.py` restores OCR boxes to original game-crop coordinates after image downscaling. `scoped_lines` assigns those boxes to calibrated regions. If a HUD ROI has not been calibrated, current conservative full-crop label matching remains as fallback.
- `icon_matcher.py` performs single-icon crop matching only against human-confirmed local templates. Strong score and runner-up margin required; ambiguous output is unknown. Output is a time-limited fragment, not a reconstructed lineup.
- `coach.py` captures a calibration snapshot when the per-game read-only observer starts, then posts OCR+matched-icon results to the Tk event queue. UI thread alone mutates session state; pause/end invalidates late events as before.
- Benchmark harness consumes privately held, sanitized labeled game captures. The absence of captures is never recorded as real-world passing evidence.