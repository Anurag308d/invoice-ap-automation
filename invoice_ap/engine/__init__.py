"""AP decision engine: intake, extraction, validation, duplicates, matching, routing,
approvals, payments, events and explain (implemented from Stage 3).

No-leakage boundary: the engine reads only data/<scale>/master and data/<scale>/inbox, and it
imports only invoice_ap.common, invoice_ap.spec and invoice_ap.engine. tests/test_boundary.py
enforces the import rule; tests/test_engine_sandbox.py enforces the file-access rule at runtime.
"""

from .pipeline import run_engine  # noqa: E402,F401
