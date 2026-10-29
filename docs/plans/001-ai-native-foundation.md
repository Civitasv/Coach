# Plan 001 — AI-native repository workflow

**Spec:** `docs/specs/001-ai-native-foundation.md`  
**Status:** Implemented; CI verification reported in PR.

## Plan

1. Inspect Orven AGENTS, Spec, CI and PR template alongside Coach baseline.
2. Define project-specific invariants, context entrypoints and evidence rubric.
3. Add Spec/Plan/Review docs with clear AC links; provide issue/PR templates.
4. Add a dependency-free validator and regression tests.
5. Run compilation, tests and validator; upgrade CI to Linux/Windows matrix.
6. Create PR, wait for actual checks on the PR head SHA, perform independent/fresh-context review where possible, then squash merge if clean.

## Risks and mitigations

- **Workflow overhead:** small bug fixes can cite existing specs and use PR plan rather than a new plan file.
- **False CI confidence:** mocks do not prove real-game recognition; UI metrics require manual evidence.
- **Windows CI dependency installation:** use Python 3.11 and existing supported dependencies; if Windows package installation fails, diagnose rather than skipping that job.
- **Over-automation:** no automatic external agent execution or broad bot write permissions.

## Rollback

Revert the workflow/documentation PR. Runtime behavior is not intentionally altered.