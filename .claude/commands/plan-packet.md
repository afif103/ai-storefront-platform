# /plan-packet

Produce a structured packet plan for ChatGPT review before any coding.

## Instructions

Investigate first. Produce a plan only. Do not modify any files. Do not start implementation. Wait for ChatGPT approval before coding.

1. Accept a packet name argument (e.g., `M10B.5`).

2. Read current state from:
   - `docs/05-backlog/backlog-v1.md` — what's shipped, what's deferred, what's next
   - `docs/05-backlog/milestones.md` — milestone status and acceptance criteria
   - Relevant backend/frontend source files as needed to understand current implementation

3. Produce a plan with these sections:
   - **Packet name** — full name and number
   - **Exact scope** — what will be built, smallest safe scope
   - **Why now** — why this packet should come before later work
   - **Likely files** — files to create or modify
   - **API/model changes** — new endpoints, schema changes, migrations (if any)
   - **Acceptance criteria** — what must be true when done
   - **Non-goals** — what is explicitly out of scope
   - **Risks** — anything that could go wrong or needs attention
   - **Commit breakdown** — ordered list of commits with conventional commit messages

4. Do not modify any files.
5. Do not create any code.
6. Do not commit anything.
7. Wait for user/ChatGPT to approve the plan before proceeding.
