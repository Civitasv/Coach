## Change / why

<!-- Describe one cohesive behavior change and user impact. -->

## Spec and plan

- Spec: `docs/specs/NNN-...md` (or link existing spec for a small fix)
- Plan: `docs/plans/NNN-...md` (or describe a small fix plan here)
- Acceptance criteria → evidence: `AC-001` → [test/log/sanitized screenshot]

## Verification (on this head SHA)

- [ ] `python scripts/verify_ai_workflow.py`
- [ ] `python -m compileall -q coach.py engine.py local_ocr.py session.py advice.py providers.py scripts tests`
- [ ] `python -m unittest discover -s tests -v`
- [ ] GitHub Actions Ubuntu and Windows checks Green (paste run links)
- [ ] Real Windows game verification when relevant (or explain *not run*)

## Review and risks

- Reviewer/context (independent, fresh-context, or **author self-review**):
- Blocking findings + resolution:
- Consent / screenshot / OCR uncertainty / concurrency / API cost impact:
- Rollback or fallback:
- Known unverified behavior:

## Merge gate

- [ ] Checks passed on current PR head SHA
- [ ] No unresolved blocking review threads
- [ ] Acceptance criteria satisfied; no fabricated evidence
- [ ] Ready for squash merge