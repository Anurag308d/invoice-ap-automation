# Prompt history

Every prompt sent to an AI tool for this project, in order. `INDEX.md` lists each prompt with its time, sender and
recipient, and the exact message text. Longer instructions were written to a brief file first, and the message told the
agent to read it; those briefs are the numbered `NNN_*.md` files here.

- `000_user_prompt.md` and the "Candidate → Claude" rows in `INDEX.md`: the candidate's own prompts to Claude.
- `ASSIGNMENT.md`: the problem statement, submission guidelines and FAQ, given to both agents as their source of truth.
- `SPRINT_PLAN.md`: the staged build-and-review process the agents followed.
- All other files: prompts from the orchestrating Claude session to the developer agent (DEV) and the reviewer agent (REV).

AI responses are optional under the guidelines. The reviewer's verdicts and the developer's stage reports are included
anyway, in `../sprint_reviews/`, as evidence of how each stage was checked.
