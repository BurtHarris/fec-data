# Copilot CLI Workflow Tips for FEC ETL (Expanded)

This guide expands the five tips you received and translates them into a practical workflow for long-running ETL jobs in this repository.

## 1) Use `/tasks` + background execution for long ETL runs

When ETL runs take several minutes, the main chat view can feel stalled and may collapse output. Moving a run to the background keeps the session responsive and gives you explicit control over when to inspect results.

- **What `/tasks` does:** shows and manages background work (agent tasks and shell commands), including status and output retrieval.
- **Why it helps:** you avoid “is this hung?” ambiguity and can check progress/results on demand.

Typical pattern:
1. Start or move a long run to background (for example with `Ctrl+X` then `b` when available).
2. Continue working in chat.
3. Run `/tasks` to list status.
4. Pull logs/output explicitly when you are ready.

## 2) Use `!` for the heavy run, then ask Copilot to analyze artifacts

For benchmark loops, raw terminal output is often the fastest and clearest signal.

- **What `!` does:** executes a shell command directly from Copilot CLI.
- **Why it helps:** you see live, uncompressed command output immediately.

Recommended loop:
1. Run the ETL command with `!` (example: `!.\scripts\load-fec-duckdb.ps1 ...`).
2. Let it finish and write artifacts (`logs\`, timing CSVs, etc.).
3. Ask Copilot to compare the newest two timing files and summarize deltas.

This separates execution (terminal-native) from analysis (Copilot-native), which is usually faster than trying to have one turn do both during long jobs.

## 3) Use `/every` or `/after` for unattended benchmarking

When your workflow repeats the same checks, scheduling saves manual polling.

- **What `/after` does:** schedules a one-time prompt or skill after a delay (for example, 15 minutes later).
- **What `/every` does:** schedules a recurring prompt/skill at a fixed interval.

Examples:
- `/after 15m compare newest timing CSVs and summarize runtime deltas`
- `/every 30m check latest load log for failures and report row-count changes`

Use `/after` for one-off reminders tied to a run; use `/every` for recurring monitoring during longer benchmarking windows.

## 4) Use `/fleet` for parallelizable work

Some ETL tasks split naturally into independent tracks (A/B runs, log parsing, summary prep). Fleet mode is designed for that.

- **What `/fleet` does:** enables parallel subagent execution so multiple workstreams can run concurrently.
- **Why it helps:** reduces turnaround when tasks do not depend on one another.

Good fit:
- Run branch A vs branch B
- Parse separate logs in parallel
- Prepare comparison notes while another task is still running

If tasks are dependent (step 2 needs step 1 output), keep them sequential instead.

## 5) “Prompt upgrade”: define an output contract up front

“Prompt upgrade” means improving your prompt so Copilot knows exactly how to execute and report results, not just the end goal.

An **output contract** is a one-line constraint block that defines:
- execution style (sequential vs chained),
- observability (stage markers, full output),
- result format (what summary to produce at the end).

Example contract:

`Run one command at a time, print every stage marker, do not chain commands, and finish with a summary from the newest timing CSV.`

Why this matters: in your ETL sessions, most friction came from low visibility and mismatched output format. A strong output contract prevents retries by making operating expectations explicit at the start.

## Quick command reference (slash commands mentioned here)

- **`/tasks`** — view/manage background tasks and retrieve output
- **`/after`** — schedule a one-time future prompt/skill
- **`/every`** — schedule a recurring prompt/skill
- **`/fleet`** — enable parallel subagent execution for independent work
- **`!<command>`** — run a shell command directly in the terminal session

