# AI usage disclosure

## Summary

This repository was produced with **Claude (Anthropic)**, used through Claude Code. AI wrote
effectively all of the code, tests and documentation. The candidate directed the work, set the
constraints, and is responsible for the submission.

## How the work was organised

A main Claude session acted as **orchestrator**. It never wrote project code itself. It ran two
agents and relayed messages between them:

- a **developer agent** (DEV), which designed and built everything: the specification and policy,
  the synthetic data generator and oracle, document rendering, the extraction and decision engine,
  the evaluation, the validation suite, exports, the dashboard and the documentation;
- an **independent senior reviewer agent** (REV), which did not write project code. It extracted an
  acceptance checklist from the assignment and gated every stage against it. For each stage it
  checked out the commit in a fresh clone, rebuilt the data, recomputed labels and metrics with its
  own standard-library scripts, and issued findings and rulings that the developer had to address
  before the next stage.

The work ran in six stages:
1. specification;
2. generator;
3. intake and extraction;
4. decision engine and evaluation;
5. outputs and committed data;
6. hand-off.

Each stage ended in a commit and a review. Findings were tracked to closure. Review IDs such as
S1-R1-01 appear in the docs as provenance notes.

## Where AI accelerated the work, and where it was relied on

- **Relied on heavily, effectively 100%:** all Python code, all tests, the data dictionary, the
  policy file, the ADRs and the other documentation, the generated data and reports, and the
  commit messages.
- **Accelerated:** turning the assignment into an exact allocation and rule catalogue;
  independent recomputation during review; boundary and mutation tests; byte-level reproducibility
  checks.
- **Independent checking within the AI workflow:** the reviewer used separate scripts that did not
  import project code. Its rulings changed the design several times, for example: the vendor
  identity from documents only, the time-travel safety, the capture-review category, the size budget
  and the backlog presentation.

AI review does not replace human review. The candidate's own review is recorded below.

## Evidence

- **Prompt history:** [`prompt_history/`](prompt_history/). It holds the candidate's original
  request, the briefs to both agents, and every stage prompt and relay message.
- **Review evidence:** [`sprint_reviews/`](sprint_reviews/). It holds the acceptance checklist, every
  stage review with findings and rulings, the findings tracker, and the developer's stage reports.
- **Commit history:** one commit per stage and fix round. Commits carry a `Co-Authored-By: Claude`
  trailer.

## What I personally reviewed, changed and validated

> **[CANDIDATE TO COMPLETE]** This section must be written by the candidate, in their own words. It
> was intentionally left blank by the AI.

Checklist to complete before submission (tick what you did and add notes):

- [ ] Read the README, the architecture and the business rules, and agree with the design decisions
- [ ] Ran `python -m pytest` on my own machine (OS and Python version: ______)
- [ ] Ran `python -m invoice_ap build-all` and opened `data/full/reports/dashboard.html`
- [ ] Spot-checked invoices with `python -m invoice_ap explain <invoice_id>` (which ones: ______)
- [ ] Reviewed `reports/evaluation.md` and `reports/validation_summary.md` and understand the numbers
- [ ] Reviewed the assumptions and limitations, and can defend or change them
- [ ] Changes I made myself (files and why): ______
- [ ] Rehearsed the walkthrough in `docs/walkthrough.md`
- [ ] Chose the author e-mail for the commit history and confirmed the MIT licence
