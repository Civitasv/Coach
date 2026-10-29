# Spec 002 — Structured game-state observation (draft)

**Status:** Draft / not implemented  
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