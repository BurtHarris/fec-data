# Developer Notes

This file collects developer-facing guidance for working in this repository and for using Matt's skills package alongside the ETL workflow.

See also: [docs/matt-pocock-skills.md](docs/matt-pocock-skills.md)

## How to Use Matt's Skills Package

*** Experimental in this repo ***

### Suggested Dev Cycle

1. Align on the task with `/grill-me` or `/grill-with-docs` when the plan, wording, or docs need pressure-testing.
2. Turn the task into a testable implementation plan with the smallest matching skill.
3. Use `/tdd` for new behavior, `/diagnose` for bugs, and `/improve-codebase-architecture` when the design feels too coupled or brittle.
4. Use `/zoom-out` when you need wider codebase context before changing a subsystem.
5. Keep changes in the repo's documented ETL paths unless the skill explicitly requires a different location.

### Skill Invocation Cheat Sheet

- `/grill-me` - interrogate a plan until the major decisions are explicit.
- `/grill-with-docs` - same as above, but update docs and decision records inline.
- `/tdd` - red-green-refactor for new or changed behavior.
- `/diagnose` - disciplined bug and regression investigation.
- `/improve-codebase-architecture` - find refactoring opportunities and reduce design drift.
- `/zoom-out` - get system-level context before a larger change.
- `/to-prd` - convert a conversation into a PRD.
- `/to-issues` - break a plan or PRD into issue-sized work.
- `/triage` - move issues through the workflow state machine.

## Repository Notes

- Project-level conventions and lessons learned belong in `PROJECT_MEMORY.md`.
- Durable agent or workflow instructions belong in `AGENTS.md` or `.github/copilot-instructions.md`.
- Human-facing developer documentation belongs under `docs/`.
