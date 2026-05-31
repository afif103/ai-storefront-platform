# /review-ready

Run all relevant checks before committing. Report results for approval.

## Instructions

Do not commit. Wait for user/ChatGPT approval before committing.

1. Run backend checks (if backend files changed):
   - `cd backend && ruff check .`
   - `cd backend && black --check .`
   - `cd backend && pytest` (if database is available)

2. Run frontend checks (if frontend files changed):
   - `cd frontend && npm run lint`
   - `cd frontend && npm run build`

3. If only docs/workflow files changed, explicitly state that app lint/build/tests were skipped because no app source was modified.

4. Show:
   - `git status --short`
   - `git diff --stat`
   - Exact list of files changed

5. Propose a conventional commit message based on the changes.

6. Do not run `git add` or `git commit`.
7. Do not push.
8. Wait for user/ChatGPT to approve the commit.
