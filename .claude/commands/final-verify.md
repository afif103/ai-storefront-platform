# /final-verify

Full post-implementation validation across backend, frontend, and docs.

## Instructions

Do not modify any files. Run checks and report only.

1. Run backend checks:
   - `cd backend && ruff check .`
   - `cd backend && black --check .`
   - `cd backend && pytest` (if database is available; note if skipped)

2. Run frontend checks:
   - `cd frontend && npm run lint`
   - `cd frontend && npm run build`

3. Verify latest commit:
   - `git log -1 --oneline`
   - Confirm commit message follows conventional commits format

4. Verify working tree is clean:
   - `git status --short`
   - Working tree should be clean except for intentionally ignored files (e.g., `infra/ecs/_rendered/`)
   - Flag any unexpected uncommitted changes

5. Verify docs match shipped state:
   - Spot-check `docs/05-backlog/backlog-v1.md` — do task statuses match what was actually committed?
   - Spot-check `docs/05-backlog/milestones.md` — does the progress table reflect current state?
   - Flag any mismatches

6. Report pass/fail for each check:
   - Backend lint (ruff): PASS/FAIL/SKIPPED
   - Backend black: PASS/FAIL/SKIPPED
   - Backend tests: PASS/FAIL/SKIPPED
   - Frontend lint: PASS/FAIL
   - Frontend build: PASS/FAIL
   - Commit format: PASS/FAIL
   - Working tree clean: PASS/FAIL
   - Docs consistency: PASS/FAIL

7. Do not modify any files.
