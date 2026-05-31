Here’s a clean, concise synthesis of the **key implementation steps** for using Matt Pocock’s AI engineering skills, drawn directly from your three open GitHub tabs (the repo root, the Quickstart, and the `grill-with-docs` SKILL.md).  
Citations reference the exact tabs you had open.

See also: [docs/developer-notes.md](docs/developer-notes.md)

---

## **1. Install the skills into your agent environment**  
From the repo’s Quickstart   [github.com](https://github.com/mattpocock/skills)  
- Run the installer:  
  `npx skills@latest add mattpocock/skills`  
- Select which skills to install and which coding agents should receive them.  
- **Ensure you include `/setup-matt-pocock-skills`** in the selection.

---

## **2. Run `/setup-matt-pocock-skills` once per repo**  
From both repo pages   [github.com](https://github.com/mattpocock/skills)  [github.com](https://github.com/mattpocock/skills/tree/179a14e721034706ffce7abae75b877c922b4ae8)  
This scaffolds all required per‑repository configuration:

- Choose your **issue tracker** (GitHub, Linear, or local files).  
- Define your **triage labels** (used by `/triage`).  
- Specify where **docs** (CONTEXT.md, ADRs) should be saved.  
- After this, all engineering skills—`to-issues`, `to-prd`, `triage`, `diagnose`, `tdd`, `improve-codebase-architecture`, `zoom-out`—will work correctly.

---

## **3. Use the core engineering skills in your workflow**  
From repo reference sections   [github.com](https://github.com/mattpocock/skills)  [github.com](https://github.com/mattpocock/skills/tree/179a14e721034706ffce7abae75b877c922b4ae8)  

### Alignment & shared language  
- **`/grill-me`** — interrogate your plan until all decisions are explicit.  
- **`/grill-with-docs`** — same as above, but also updates CONTEXT.md and ADRs inline.

### Architecture & code quality  
- **`/tdd`** — enforce red–green–refactor loops.  
- **`/diagnose`** — structured debugging loop.  
- **`/improve-codebase-architecture`** — find deepening opportunities and reduce entropy.  
- **`/zoom-out`** — get system-level context for any code section.

### Planning & issue creation  
- **`/to-prd`** — turn the current conversation into a PRD.  
- **`/to-issues`** — break a plan/PRD into vertical-slice GitHub issues.

### Triage  
- **`/triage`** — run issues through a state-machine triage workflow using your configured labels.

---

## **4. Understand how `grill-with-docs` behaves during implementation**  
From SKILL.md   [github.com](https://github.com/mattpocock/skills/blob/179a14e721034706ffce7abae75b877c922b4ae8/skills/engineering/grill-with-docs/SKILL.md)  

### What it does  
- Interviews you **one question at a time** until the design tree is fully resolved.  
- Recommends answers but waits for your confirmation.  
- Explores the codebase when needed.  
- Updates **CONTEXT.md** and **ADRs** *inline* as decisions solidify.

### Domain‑model integration  
- Detects glossary conflicts and forces precise terminology.  
- Sharpens vague language by proposing canonical terms.  
- Stress-tests domain relationships with concrete scenarios.  
- Cross-references code to surface contradictions.

### Documentation rules  
- Creates CONTEXT.md lazily (only when first needed).  
- Creates ADRs only when:  
  1. The decision is hard to reverse  
  2. It would be surprising without context  
  3. It reflects a real trade-off  
- Uses the formats defined in `CONTEXT-FORMAT.md` and `ADR-FORMAT.md`.

---

## **5. Maintain the workflow over time**  
From repo guidance   [github.com](https://github.com/mattpocock/skills)  [github.com](https://github.com/mattpocock/skills/tree/179a14e721034706ffce7abae75b877c922b4ae8)  
- Re-run **`/improve-codebase-architecture`** every few days to prevent “ball of mud” drift.  
- Use **shared language** (CONTEXT.md) to keep naming consistent and reduce verbosity.  
- Use **feedback loops** (tests, browser access, static types) to keep the agent grounded.  
- Use **`/zoom-out`** when navigating unfamiliar code or refactoring.

---

If you want, I can also produce a **minimal, repo-ready checklist** you can drop into your project root (e.g., `AI-WORKFLOW.md`) so you can run this whole system consistently.