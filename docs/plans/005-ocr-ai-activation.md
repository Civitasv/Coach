# Plan 005 — Recover OCR and decision feedback

1. Inspect camera/OCR and provider/decision pipelines; reproduce silent states via behavior tests.
2. Move OCR construction into a retriable observer loop; never block latest-frame delivery on OCR initialization or failure. Display distinct OCR progress, errors, and empty-read hints.
3. Extend existing conservative scoped HUD fact handling to accept one calibrated high-confidence numeric value only; do not loosen non-ROI parsing.
4. Expose one-click manual advice on the main view and avoid suppressing an explicitly approved initial AI request when OCR is empty. Preserve separate text/image authorization.
5. Bound and sanitize provider failure detail; show unstructured text as unverified, without mutating pool/opponent facts.
6. Run GitHub CI on both OSes, review privacy and epoch boundaries, squash only if green.

## Evidence and limits

Behavior mocks are not proof of client OCR accuracy. DeepSeek API requires an actual user key, which cannot be tested via CI. Preserve no screenshot upload by default. Rollback via PR revert.
