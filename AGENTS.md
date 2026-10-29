# Coach Agent Collaboration Contract

Coach is a **local-first, read-only, real-time gameplay adviser** for 王者万象棋. The current runtime is a Python/Tkinter desktop app; local OCR feeds a per-game state machine, and optional LLM providers offer advice. Humans remain responsible for game actions.

## Start here (fresh context, every task)

1. Read this file and `docs/architecture/overview.md`.
2. Read the relevant `docs/specs/*.md`, then `docs/process/development.md`, and inspect only the source/tests required.
3. Check the latest state of the target branch and any open PR; never rely on stale conversation assumptions.
4. Produce a concise change plan with affected boundaries and acceptance criteria before coding. A small bug fix may use the PR plan section instead of a separate plan file.

## Engineering skill

Read `.agents/skills/ub-mode/SKILL.md` for `ub-mode` engineering practices on nontrivial code changes. It provides a locally maintained adapter to the upstream skill. Follow the repository PR/CI gates for merges and never treat unavailable crapper/dryer/mutator tooling as passing.

## AI-native change protocol

**Explore → Specify → Plan → Implement → Validate → Review → PR → Merge.**

- **Explore:** identify observable problem, constraints, competing changes, and affected modules. Do not guess game rules or unreadable UI state.
- **Specify:** material features require a versioned `docs/specs/NNN-slug.md` with user-visible acceptance criteria (`AC-001`, etc.), non-goals, and verification strategy. Bug fixes may reference an existing spec and add a regression test.
- **Plan:** write `docs/plans/NNN-slug.md` for cross-module changes; list risks, migration/fallback, test evidence, and any approvals needed.
- **Implement:** prefer small cohesive modules and narrow diffs; tests are part of the implementation. Update docs when an interface or invariant changes.
- **Validate:** run the exact checks in `docs/process/development.md`. CI on GitHub Actions is the source of truth for remote checks. Never claim green from intent alone.
- **Review:** perform a fresh-context review after implementation (prefer a separate agent/reviewer where available). Review against the spec, not just style. Record high-severity defects and resolution; if independent review was unavailable, say so explicitly.
- **PR:** attach spec, plan, test results, risk/privacy analysis, screenshots only if sanitized, and known limitations in the PR template.
- **Merge:** only when all applicable CI checks have passed, the PR is mergeable, no blocking review/thread remains, and criteria are satisfied. Prefer squash merge. **Do not bypass failing checks or claim that CI green alone proves game accuracy.** Automated merging may be enabled only under these conditions with explicit repository policy; it is not enabled by this file.

## Architectural invariants

1. **Observation is not truth:** a low-confidence OCR line or model guess cannot overwrite a confirmed match fact. Store provenance and freshness/TTL, separate *observed*, *inferred*, *user-confirmed*, and *unknown*.
2. **Per-game isolation:** each Start initializes fresh state; End stops observation and invalidates in-flight results. A late callback must not contaminate a new match.
3. **Local-first/consent:** screenshot capture is local by default. Cloud **text** and cloud **image** transmission require separate opt-in. Do not persist secrets or raw screenshots by default.
4. **No hidden access/actions:** never read game memory, inspect packets, automate input, evade anti-cheat, or imply that AI operates the game.
5. **Cost and latency budgets:** a fast deterministic observation loop must not trigger an LLM request for every frame. Respect throttles, user authorization, and per-match request caps.
6. **Match data:** exact public-pool counts only come from clearly readable confirmed panels (or explicit user corrections), not deduction from opponents. Opponent information expires.
7. **UI thread safety:** worker threads cannot directly update Tk widgets; use event queues and run/session IDs.
8. **User questions:** ask only for information that materially affects action; prompts must be non-modal and suppress duplicates.

## Ownership and test map

| Boundary | Files | Minimum tests |
| --- | --- | --- |
| Capture and UI lifecycle | `coach.py` | thread/session invalidation and GUI smoke where possible |
| OCR adapter | `local_ocr.py` | OCR normalization and uncertainty tests; screenshots only when sanitized |
| Fact/session model | `session.py`, `engine.py` | fact TTL, snapshots, Start/End, absent/contradictory data |
| Decision logic | `advice.py` | deterministic advice/risk boundary and missing-information tests |
| External APIs | `providers.py` | mocked payload, explicit consent path, no unintended uploads |
| Workflow | `scripts/verify_ai_workflow.py` | repository checks + script regression tests |

## Definition of done

- Relevant Spec ACs and PR acceptance checklist satisfied; no invented verification.
- Applicable unit/regression tests pass, `python -m compileall` passes, workflow validator passes.
- Windows and Linux CI passes for changes shipped on either platform; Windows GUI behavior still needs human QA when tests cannot exercise real screens.
- No raw game screenshot or API key unintentionally committed/logged. Documentation and any limitations updated.
- Distinguish **unit-test verified**, **CI verified**, and **real-client verified**. Screenshots/OCR accuracy and latency claims require real game evidence.
- Use Conventional Commit messages (`feat:`, `fix:`, `test:`, `docs:`, `ci:`).

For the full lifecycle, see `docs/process/development.md`. For technical boundaries, see `docs/architecture/overview.md`.