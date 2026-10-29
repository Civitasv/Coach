# Spec 002 — Structured game-state observation (draft)

**Status:** In progress — ROI / evidence / local icon template slice implemented; real-client data and full enemy tracking pending  
**Goal:** Convert local OCR + icon recognition into verifiable, actionable game state without fabricating absent data.

## Problem

Generic OCR detects text but cannot reliably classify icon-only heroes, equipment, card levels, or opponents. The coaching engine needs trustworthy, timely inventory and tactical state to advise beyond general tips.

## Acceptance criteria

- **AC-001:** Configurable, resolution-independent ROIs for health, energy, round, shop, pool, enemy board and weapon; calibration is saved locally and is opt-in.
- **AC-002:** Every recognized fact has `value`, `confidence`, `source`, `observed_at`, `expires_at`; conflicting/unreadable facts remain unknown pending user clarification.
- **AC-003:** Icon-only assets use a calibrated local matcher/classifier; an unknown class never becomes a forced hero identity.
- **AC-004:** Public-pool exact counts are updated only from a verified panel or explicit human correction; other sightings are labeled estimates.
- **AC-005:** Opponent snapshots include observation freshness; updates can trigger a revised recommendation without requiring per-frame cloud calls.
- **AC-006:** Benchmarks record OCR precision, false-positive rate, latency distribution, and question burden from sanitized gameplay captures.

## Verification

Sanitized golden-image fixtures, negative/unknown icon samples, TTL and conflicting-fact tests, per-frame-to-event simulation, Windows client benchmark. Dataset collection and client-version labeling are prerequisites before claiming real accuracy.

## Non-goals

Reading hidden game state, automated gameplay actions, defeating anti-cheat, or claiming exact remaining inventory from observed opponents alone.

## Implementation mapping (first slice)

| AC | Implemented artifact | Outstanding evidence |
| --- | --- | --- |
| AC-001 | `Calibration`/`ROI`, Tk screen-region picker, opt-in `config/calibration.json` | Real display/resolution calibration walkthrough |
| AC-002 | `Observation` / `FactLedger`, conflict handling, session fact projection | Capture-driven error audit |
| AC-003 | `IconMatcher`, user-confirmed local PNG templates, unknown abstention | Real UI icon dataset and precision |
| AC-004 | Existing `Match.apply` panel guard retained; icon observations cannot write exact public pool | Manual correction UI for individual pool cards |
| AC-005 | Time-bounded icon fragments and dynamic AI-text fingerprint; `Match.opponents` full lineup remains vision-confirmed | Full opponent identity tracking across views |
| AC-006 | Offline benchmark script and test manifest format, with explicit `pending_dataset` | Sanitized game capture measurements on Windows |

The first implementation slice is **not** proof that the full Spec 002 or practical real-time lineup recognition is complete.