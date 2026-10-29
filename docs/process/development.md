# Development process (AI-native SDLC)

## Durable artifacts, not chat history

The repository is the source of truth. Each substantial feature uses a shared numeric ID across `docs/specs/NNN-*.md` and `docs/plans/NNN-*.md`. Evidence and design decisions go into the PR (or `docs/reviews/` when long-lived). Never treat an agent's chat summary as verification evidence.

## Steps

1. **Explore:** inspect `AGENTS.md`, architecture, relevant spec, minimal source, tests and recent PRs. Record unknowns instead of inventing game data.
2. **Specify:** define user outcomes, explicit non-goals and stable AC IDs. If dealing with OCR/vision, specify datasets, expected false positives and how errors trigger questions.
3. **Plan:** document affected modules, concurrency/consent risks, test matrix, rollback path, and any screenshot fixtures required.
4. **Implement:** write a failing regression test for bug fixes where practical, then make the smallest change to pass. Do not add cloud calls to local loops as a shortcut.
5. **Validate locally:** run the commands below; log tests as pass/fail/not-run with reasons.
6. **Review:** use a different agent/context if possible. Independently check privacy, stale session handling, incorrect pool counts, missing information, and user-visible failures. Resolve blocking defects before merging.
7. **PR:** use the template with AC→test evidence. Observe GitHub Actions statuses on the actual PR head SHA; review unresolved threads.
8. **Merge:** squash only after CI passes and no blocking issues remain. If auto merge is enabled later, enforce exactly the same gates and a narrow trusted-actor policy.

## Validation commands

```bash
python -m pip install -r requirements.txt
python scripts/verify_ai_workflow.py
python -m compileall -q coach.py engine.py local_ocr.py session.py advice.py providers.py scripts tests
python -m unittest discover -s tests -v
```

CI runs these on Ubuntu and Windows (Python 3.11). Real Windows gameplay QA and OCR accuracy against real client screenshots are **manual evidence requirements**; passing mocks is not evidence of actual recognition accuracy.

## Evidence rubric

| Evidence | Acceptable | Unacceptable |
| --- | --- | --- |
| Unit behavior | Test command + outcome + tested branch SHA | “Looks correct” |
| Game UI | Sanitized screenshots/video + client version + conditions | Fabricated success rates |
| Latency | Measured sample distribution on specified hardware | Interval setting presented as observed FPS |
| Cost | Recorded model call count and token/billing source | Estimating per-frame cost from OCR loop |
| Security/privacy | Test cloud consent and negative paths | Claiming no upload because default checkbox is off |

## Change sizes

- **Small bug fix:** existing spec link, regression test, PR plan/review sections.
- **Material feature / cross-boundary:** new spec + plan + focused PR review and tests.
- **Schema or consent change:** ADR (`docs/decisions/`) when tradeoffs have long-term impact.

Follow `AGENTS.md` for all hard requirements.