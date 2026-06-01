# Copilot CLI Tips (Personalized)

These tips are grounded in your recent usage patterns in this repo.

## 1) Upgrade “continue/go” into “continue + guardrails”
In this repo you used **“continue” 6×** and **“go” 4×**; about **40%** of your prompts are ≤25 chars.

When you do want to just keep moving, add two quick lines to your prompt:
- **Scope** (what files/areas are allowed)
- **Definition of done** (how we know it’s finished)

Example:

```
Continue.
Scope: only touch `scripts/transform/*`.
DoD: script reruns clean + shows expected row counts.
```

## 2) Worktree hygiene in prompts
You’ve hit worktree context confusion (e.g., referencing “other worktree” / “earlier stage”). Start prompts with explicit context and ask Copilot to verify before editing:

- `CWD=… BRANCH=… WORKTREE=…`
- Confirm with: `git worktree list` and `git status`

This prevents edits landing in the wrong worktree/branch.

## 3) Make `/diff` + `/review` your pre-commit ritual
You asked “commit” multiple times in recent sessions.

Before staging/committing:
- Run **`/diff`** to sanity-check the full change set
- Then **`/review`** to catch logic/security issues while it’s still cheap to fix

## 4) Use timers + background task controls for ETL
For long-running ETL commands, use:
- **`/every`** for periodic health checks / progress updates
- **Ctrl+X → B** and **`/tasks`** to manage background commands

This is usually faster than repeatedly asking “what’s next?” during a long run.

## 5) Lean on your installed skills beyond `/tdd`
You have skills like: `diagnose`, `zoom-out`, `to-issues`, `triage`.

- When something breaks (e.g., a download/HTTP failure), invoke **`/diagnose`** immediately.
- When you’re planning or downscoping, use **`/zoom-out`** or **`/to-issues`** to keep scope crisp and slice work into grab-and-go tickets.
