# Sanitized game capture benchmark

Put **user-consented, sanitized** screenshots under `fixtures/private/` (gitignored), and a local `fixtures/manifest.json` containing:

```json
{"samples": [{"image": "private/game1.png", "expected": {"health": "18", "energy": "12"}}]}
```

Optional `calibration` is a path to a saved local calibration JSON relative to the manifest.
Use `python scripts/benchmark_observation.py fixtures/manifest.json --output fixtures/private/report.json`.

The script measures HUD precision/false positives/false negatives, approximate OCR+state latency p50/p95, and the fraction of screenshots that require at least one missing-fact question. Do not confuse this with icon classification quality. Collect screenshots from distinct matches and client versions, document hardware, and include negative cases. Never commit account names, chats, screenshots or private manifest. Without labeled images results are explicitly **pending**.