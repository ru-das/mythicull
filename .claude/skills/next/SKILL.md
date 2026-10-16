---
name: next
description: Do the next unchecked task in docs/PLAN.md, test it, tick it off, update docs/PROGRESS.md and commit.
argument-hint: "[task-id]"
disable-model-invocation: true
---

Complete exactly one MythiCull task.

1. Read `docs/PROGRESS.md`, then `docs/PLAN.md`. If a task id was passed ($ARGUMENTS), do that task. Otherwise pick the first unchecked task.
2. Read only the parts of `docs/SPEC.md` that the task needs.
3. If the task looks larger than one focused session, split it into smaller checkboxes in `docs/PLAN.md`, then do only the first one.
4. Implement it, following the hard rules and conventions in `CLAUDE.md`. Write or update tests alongside the code.
5. Run `pytest -q` until it passes. Then run the task's "Done when" check. If that check needs real photos or a manual look in the browser or Lightroom, stop and tell me exactly what to run and what to look for.
6. Tick the box in `docs/PLAN.md`. In `docs/PROGRESS.md`, set "Next task", "Last completed", record any tuned values, decisions, new dependencies and known issues.
7. Commit with a message like `M2.1: recursive scan with RAW+JPEG pairing`. Do not use phrases like "Co-authored by..." in the commit message.
8. Report in at most 5 lines: what was done, how it was tested, anything I need to check, and the next task. Do not start the next task.
