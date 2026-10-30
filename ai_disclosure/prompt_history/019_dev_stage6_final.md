# Prompt 019 — Orchestrator → DEV: Stage 6, final hand-off (one pass, no further review rounds)

The candidate wants the work finished now. This is the last DEV pass. The orchestrator will run the final verification
and packaging. Keep the scope tight and make it look professional.

1. **README.md (final):**
   - Remove the "Status: Stage 5 of 6" banner and any wording about stages or the sprint.
   - It must cover: the problem; the solution overview and architecture; the quickstart for macOS/Linux and Windows
     (keep it); configuration (policy file, seed, scale); how to run; how to verify (tests plus the reports to open); a
     map of the repository layout and outputs; a results snapshot with the real numbers from the committed full build
     (volumes, mix, extraction accuracy, agreement with ground truth, STP %, exceptions by type, payment-ready safety,
     reproducibility); key assumptions and design decisions (short, linking to the ADRs); limitations and next steps;
     and a pointer to `ai_disclosure/`.
   - Keep it readable: around 200–300 lines at most, with detail living in `docs/`.
2. **New docs:**
   - `docs/testing_and_verification.md`: the testing approach, what each test group proves, the mutation and blind-run
     evidence, and "how we know it works".
   - `docs/walkthrough.md`: a 10–15 minute script for presenting the solution live (what to show, in what order, and
     which commands to run).
3. **`ai_disclosure/AI_USAGE.md`:**
   - An honest disclosure. The work was produced with Claude (Anthropic): a main session orchestrated two agents, a
     developer that built everything and an independent senior reviewer that gated each stage against the assignment.
   - Say where AI accelerated the work and where it was relied on heavily (effectively all code and docs).
   - Point to the prompt history in `ai_disclosure/prompt_history/` and the review evidence in
     `ai_disclosure/sprint_reviews/`. The orchestrator will add these folders, so just reference them.
   - Include a clearly marked section, "What I personally reviewed, changed and validated", that contains only a
     placeholder and a checklist for the candidate to fill in. Do not invent their statement.
4. **`docs/requirements_traceability.md`:** finalise it with an evidence link (file, test or report) for every
   requirement. Main docs should read on their own for a reviewer: sprint finding IDs (S1-R1-…) may stay as
   provenance notes but must not be needed to understand anything.
5. **Hygiene:**
   - No `__pycache__`, scratch files, TODOs or stage-progress wording in tracked files. The `.gitignore` must be
     correct.
   - `pyproject.toml` metadata should be neutral (no personal e-mail).
   - The LICENSE stays MIT.
   - Make sure `python -m pytest` passes from a fresh clone.
6. **Commit:** `stage-6: final README, walkthrough, testing doc, AI-usage disclosure` with the trailers.
7. Budget: the usage limit is tight, so be efficient. Reply in 10 lines or fewer.
