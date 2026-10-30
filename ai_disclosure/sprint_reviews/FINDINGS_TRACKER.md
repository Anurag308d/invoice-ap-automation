# Findings tracker

Created by the orchestrator on REV's behalf, because the subagent harness blocked REV from creating this file.
REV owns the content. If REV cannot write here, REV includes the cumulative table at the end of each review and the
orchestrator copies it in. Conventions: ACCEPTANCE_CHECKLIST.md §F.

Open after stage-4-review-1: BLOCKER 0 · MAJOR 0 · MINOR 0 · NIT 2 (S1-R1-09, S4-R1-01). Stages 1-3 PASS-WITH-NITS; Stage 4 PASS-WITH-NITS at `ad005fb`.

| ID | Stage | Severity | Requirement | Summary | Status (open/fixed/verified/accepted-deviation) | Notes |
|---|---|---|---|---|---|---|
| S1-R1-01 | 1 | MAJOR | A-10, A-50, A-55; R30, R34a | Inbox manifest gives the engine the true vendor (sender_vendor_id required for every channel incl. SCAN; vendor code inside invoice_id). No data case can expose a shortcut, and there is no disagreement rule or enforcement test | verified | Verified in stage-1-review-2 at 66b1f07: manifest has no invoice_id; sender_vendor_id only for PORTAL/EDI; ID-01 engine-assigned ID; VEN-04 routed; static-ban probes fail the suite. ID-blind sandbox carried to Stage 3 |
| S1-R1-02 | 1 | MINOR | A-67, A-10; R30, R35c | Master year-end `*_as_of` snapshot columns (vendor, PO, PO line, GRN) are engine-readable and hold future information | verified | Verified at 66b1f07: snapshot_* columns marked reporting_only; static-ban probe fails the suite. Time-travel sandbox carried to Stage 4 |
| S1-R1-03 | 1 | MINOR | A-36, AMB-05; R24 | C-CAPTURE-DEGRADED labelled CLEAN but expected HOLD; is_anomaly false while expected_blocked true | verified | Verified at 66b1f07: CAPTURE_REVIEW 10/1; CLEAN 1,350/135; is_anomaly = intended issues non-empty; invariant test |
| S1-R1-04 | 1 | MINOR | A-63, AMB-03; R35c | as_of_date 2026-12-31 is after the submission date, so the data would hold completed events in the future | verified | Verified at 66b1f07: as-of 2026-10-22; no stale 2026-12-31 / 24 Dec / 2027 refs. Completed-event test carried to Stage 2 |
| S1-R1-05 | 1 | MINOR | A-26; R15 | N:M claimed in both directions, but no placement makes one GRN line serve two invoice lines | verified | Verified at 66b1f07: A12 10 POs / 20 invoices (starter 1/2); identities exact; REV checker S12 capacity OK. Data check carried to Stage 4 |
| S1-R1-06 | 1 | MINOR | A-33; R20 | 16 of 336 fields have no validation rule beyond type (11 date/decimal ordering rules); 3 confidence fields have no unit | verified | Verified at 66b1f07: REV checker reports every field has all checked attributes; completeness test |
| S1-R1-07 | 1 | MINOR | A-25; R14 | schema_render.py `[:48]` truncates state-machine labels mid-word (schema.md lines 285, 332, 363) | verified | Verified at 66b1f07: no slicing in the renderer; the only regex hit is full text (schema.md:297) |
| S1-R1-08 | 1 | MINOR | A-82 | Traceability matrix has 0 REV-added A-items | verified | Verified at 66b1f07: 22 A-ids cited, covering checklist §C.2 |
| S1-R1-09 | 1 | NIT | A-79, A-81 | Commits use the candidate's personal Gmail as author e-mail | open | Stage-6 hand-off decision for the candidate; no DEV action now |
| S2-R1-01 | 2 | NIT | A-33, A-51; R20, R31 | Spec-required list fields (ground_truth edge_case_ids, intended/expected issue types, …) are legitimately empty; manifest file_sha256 and file_bytes are pending until Stage 3 | verified | Verified in stage-3-review-1 at 0a2ca58: lists are required=False ('empty = none'); manifest fields filled; REV checker reports PROBLEMS: none |
| S2-R1-02 | 2 | NIT | A-61 | Every date falls on a business day (100%) | verified | Verified at 0a2ca58: README Known limitations lines 60-61 |
| S4-R1-01 | 4 | NIT | A-09, A-76; R4 | reports/evaluation.md prints raw Python dicts and has no KPI definitions (they are only in evaluation_plan E10 / ADR-041) | open | Fix in the Stage-5 commit: definitions, tables, overdue snapshot caveat with age buckets; acceptance = no `{'` text and every KPI defined |
