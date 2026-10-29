---
name: ub-mode
description: Apply the upstream Uncle Bob engineering workflow during Coach code changes.
---

# Coach `ub-mode` adapter

Upstream source: https://github.com/unclebob/ub-mode/blob/57a8bdd28e45ed41900ace0bafa2ff76dd9ed70f/SKILL.md

The upstream text is not redistributed here because the repository did not advertise a license when this adapter was added. To install the exact upstream skill in your personal agent environment, follow that repository's README and copy its `SKILL.md` into your agent skills directory.

For Coach contributions, apply this equivalent local project convention:

1. **First make it work**: establish the data shape, write a failing behavior test, add the smallest implementation, keep single-writer state and idempotent operations.
2. **Then make it right**: verify behavior, fix causes rather than symptoms, remove duplication, review complexity, add mutation/coverage evidence where the tools are available.
3. **Practice**: record changes and evidence, perform scoped cleanup safely, make small commits, and follow Coach's PR/CI/merge gates.

If `crapper`, `dryer`, or `mutator` are not installed, mark their checks `not run` with reasons. Do not fabricate their results. The upstream instruction to push directly to the main line does **not** override Coach's protected PR/CI merge protocol.