# Spec 001 — AI-native repository workflow

**Status:** Implemented (workflow foundation)  
**Owner:** Coach maintainers  
**Scope:** Repository process, documentation, and continuous integration; no game-runtime behavior change.

## Problem

Previously, Coach had a basic unit-test workflow but lacked durable agent instructions, feature acceptance criteria, review evidence, and cross-platform validation. An AI contributor could claim completion without reproducible checks or a plan.

## Acceptance criteria

- **AC-001:** Repository-root `AGENTS.md` describes startup reading order, collaboration flow, privacy invariants, and an evidence-backed definition of done.
- **AC-002:** Architecture, process, Spec, Plan and Review artifacts are discoverable and use consistent identifiers; CI validates the minimum artifact format.
- **AC-003:** A PR template links each relevant acceptance criterion to verification evidence, and records review independence, risks and unverified items.
- **AC-004:** GitHub Actions runs unit tests, compilation and the workflow validator on both Linux and Windows; it has minimal permissions.
- **AC-005:** Feature/bug issue forms capture reproduction, goals, acceptance criteria and privacy implications.
- **AC-006:** There is no unconditional GitHub bot auto-merge; the merge policy requires green CI, mergeability, and absence of blocking reviews.

## Verification

`python scripts/verify_ai_workflow.py`, `python -m unittest discover -s tests -v`, and successful GitHub Actions matrix runs on the PR head SHA. Review GitHub changed-files diff to confirm no app runtime modification.

## Non-goals

- Adding an autonomous agent orchestration service or CI-triggered LLM reviewer.
- Changing gameplay inference, OCR behavior, or API billing.
- Enforcing branch protection via an API that may require separate administrator configuration.
- Automated merge of all PRs regardless of actor or review status.