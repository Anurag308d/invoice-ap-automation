# AI usage

The submission guidelines allow LLM tools and require a prompt history. This file covers that requirement.

## Tools used

Claude (Anthropic), through Claude Code. It drafted the code, tests and documentation from my prompts. A second AI
session independently reviewed each stage against the assignment before the next stage began.

## Where AI helped

- **Accelerated:** turning the assignment into an exact data allocation and rule catalogue; writing the generator,
  extraction and decision engine; writing the tests and documentation.
- **Relied on heavily:** implementation of the code and documents.
- **Checked:** the design, data and results were checked against the assignment through the test suite, the
  validation suite, the evaluation against ground truth, and the reproducibility check.

## Prompt history

All prompts are in [`prompt_history/`](prompt_history/). `INDEX.md` lists them in order, and `ASSIGNMENT.md` is the
assignment text given to the tools.

## What I personally reviewed, changed and validated

I, Anurag Kumar, directed the work and validated the result myself:

- I read the problem statement, the submission guidelines and the FAQ, and gave them to the AI as the source of truth.
- I chose the working method. One AI agent built the solution in stages, and a second, independent agent reviewed
  each stage against the assignment. A stage moved forward only after its review passed.
- I kept the work saved continuously and restarted it after interruptions, so nothing was lost.
- I asked for the final repository to contain only what the assignment requires, without internal process notes.
- I ran the project on my own Windows machine. I installed the dependencies, ran the full automated test suite
  (`py -m pytest`, all tests passed) and opened the offline dashboard (`data/full/reports/dashboard.html`) to check
  the KPIs, exception queues and invoice decisions.
- The prompts listed in `prompt_history/INDEX.md` are mine or were sent on my instruction.

The verification evidence (automated tests, validation summary, evaluation against ground truth, reproducibility
report) is in `tests/` and `data/full/reports/`.
