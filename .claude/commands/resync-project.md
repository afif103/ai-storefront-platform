# /resync-project

Generate a project state snapshot for ChatGPT handoff or review.

## Instructions

Do not modify any files. Inspect and report only.

1. Run and show:
   - `git branch --show-current`
   - `git status --short`
   - `git log --oneline -10`

2. Read and summarize active/open milestones from:
   - `docs/05-backlog/backlog-v1.md` — summarize each milestone's current status (what's done, what's in progress, what's deferred)
   - `docs/05-backlog/milestones.md` — summarize the progress table

3. List any uncommitted changes or untracked files (exclude `.gitignore`-ignored paths).

4. Report in a structured format with these sections:
   - Branch
   - Git status
   - Latest commit
   - Recent commits
   - Backlog/milestone summary (all active milestones, not just one)
   - Open questions or blockers (if any)

5. Do not modify any files. This command is read-only.
