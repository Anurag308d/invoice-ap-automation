"""State machines: complete diagram labels and transition checking."""
from __future__ import annotations

from invoice_ap.common.lifecycle import TERMINAL, TRANSITIONS, sequence_errors
from invoice_ap.common.paths import DOCS_DIR


def test_labels_are_short_whole_phrases_and_rendered_in_full():
    schema = (DOCS_DIR / "schema.md").read_text(encoding="utf-8")
    for entity, transitions in TRANSITIONS.items():
        for (src, dst), tr in transitions.items():
            assert tr.label and len(tr.label) <= 32, (entity, tr.label)
            assert not any(c in tr.label for c in ":;()"), (entity, tr.label)
            assert f"{src or '[*]'} --> {dst}: {tr.label}\n" in schema, (entity, tr.label)
            assert tr.detail


def test_every_entity_has_a_creation_transition_and_valid_terminals():
    for entity, transitions in TRANSITIONS.items():
        assert any(src is None for src, _ in transitions), entity
        states = {dst for _, dst in transitions}
        assert set(TERMINAL[entity]) <= states, entity


def test_sequence_check_accepts_documented_paths_and_rejects_others():
    assert sequence_errors("INVOICE", ["RECEIVED", "CAPTURED", "PENDING_APPROVAL", "APPROVED",
                                       "PAYMENT_READY", "PAID"]) == []
    assert sequence_errors("PURCHASE_ORDER", ["ISSUED", "PARTIALLY_RECEIVED", "RECEIVED"]) == []
    assert sequence_errors("INVOICE", ["RECEIVED", "PAYMENT_READY"])  # skips capture and approval
    assert sequence_errors("PAYMENT", ["PAID"])                        # must be scheduled first
