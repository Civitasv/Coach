# Plan 003 — Qt UI migration

1. Introduce a pure Python observer with one-frame coalescing and bounded events; retain `session.py`, `observation.py`, `icon_matcher.py`, `providers.py` behavior.
2. Build PySide6 view widgets: live preview and transparent HUD, compact fact cards, structured shop slots, scrollable chat timeline, non-modal answer widget.
3. Build a thin main window to compose views and UI-thread-only state updates, with source consent, run/epoch guards and local save.
4. Replace `coach.py` with the entry point; update Windows launcher, requirements and CI smoke tests; revise agent docs and README.
5. Run behavior tests and UI offscreen smoke, then Windows/Linux CI. Do not merge on failing checks. Record real-game visual/performance evaluation as pending.

## Risk & rollback

PySide6 increases download size and first-start install time; Qt platform plugins can fail on certain Windows environments. Tightly bound `PySide6>=6.8,<7` until compatibility tests pass. Revert the UI PR to restore the Tk shell; the domain logic remains unchanged.

## Verification evidence

`tests/test_observer_ui_contract.py`; Python compileall; GitHub CI. Actual game UI screenshots/real-world latency and ROI recognition are not covered by synthetic tests.