# ADR 0001 — Local-first observation and explicit cloud consent

**Status:** Accepted for current architecture  
**Context:** A high-frequency real-time helper must limit latency, cloud spending and data disclosure.

## Decision

Keep screenshot capture, OCR and basic state updates local. Expose separately authorized, rate-limited LLM text and image paths. Per-match state has explicit Start/End lifecycle and timestamped observations; unknown information is surfaced as questions rather than invented answers.

## Consequences

Local models can run slowly on some PCs. OCR alone cannot parse icon-only state, so future classifier/ROI work is required. Cloud assistance improves inference only where consent and cost permit. Tests must cover negative consent and in-flight-result invalidation.

## Revisit when

Real Windows gameplay measurements show the OCR path cannot achieve useful latency or confidence, or UI automation would be considered (requires an entirely separate policy decision).