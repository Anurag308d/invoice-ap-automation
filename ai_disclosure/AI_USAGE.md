# AI usage

The submission guidelines allow LLM tools and require a prompt history. This file covers that requirement.

## Tools used

Claude (Anthropic), through Claude Code. It drafted the code, tests and documentation from my prompts. A second AI
session reviewed each stage against the assignment before the next stage began.

## Where AI helped

- **Accelerated:** turning the assignment into an exact data allocation and rule catalogue, writing the generator,
  extraction and decision engine, and writing tests and documentation.
- **Relied on heavily:** implementation of the code and documents.
- **Checked:** the generated design, data and results against the assignment, with the test suite, the validation
  suite and the reproducibility check.

## Prompt history

All prompts are in [`prompt_history/`](prompt_history/). `INDEX.md` lists them in order. `ASSIGNMENT.md` is the
assignment text given to the tools.

## What I personally reviewed, changed and validated

I, Anurag Kumar, directed the work instead of typing the code myself. Specifically:

- I read the problem statement, the submission guidelines and the FAQ, and gave them to the AI as the source of truth.
- I chose the working method. One AI agent built the solution in stages, and a second, independent agent reviewed each
  stage against the assignment. A stage moved forward only after its review passed.
- I made sure the work was saved continuously and resumed after interruptions. When the AI hit usage limits, I
  restarted the work so nothing was lost.
- I asked for the final repository to contain only what the assignment requires. That meant removing internal review
  notes and process clutter, while keeping this prompt history as the guidelines require.
- The prompts listed in `prompt_history/INDEX.md` are mine or were sent on my instruction.

The correctness evidence (544 automated tests, the validation suite, the evaluation against ground truth and the
reproducibility check) was produced and run by the AI tools. The results are in `data/full/reports/`.
