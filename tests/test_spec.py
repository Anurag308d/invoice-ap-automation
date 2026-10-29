"""The machine-readable data dictionary is complete, internally consistent and leak-free."""
from __future__ import annotations

import json

import pytest

from invoice_ap.common import enums
from invoice_ap.common.paths import DOCS_DIR, SPEC_JSON
from invoice_ap.spec import BY_NAME, CORE_ENTITIES, LAYERS, ORIGINS, TABLES, TYPES
from invoice_ap.spec.model import WRITERS
from invoice_ap.spec.render import to_dict, to_json, to_markdown

FIELDS = [(t, f) for t in TABLES for f in t.fields]
# Which layers a table may reference by FK. Engine output never points into evaluation-only layers.
MAY_REFERENCE = {
    "master": {"master"},
    "inbox": {"master", "inbox"},
    "source": {"master", "inbox", "source"},
    "ground_truth": {"master", "inbox", "source", "ground_truth"},
    "processed": {"master", "inbox", "processed"},
}


def test_every_core_entity_has_exactly_one_table():
    for entity in CORE_ENTITIES:
        assert [t.name for t in TABLES if t.entity == entity].__len__() == 1, entity
    assert {t.entity for t in TABLES if t.entity} == set(CORE_ENTITIES)


def test_table_metadata_is_valid():
    assert len(BY_NAME) == len(TABLES)
    for t in TABLES:
        names = [f.name for f in t.fields]
        assert len(names) == len(set(names)), t.name
        assert t.layer in LAYERS and t.writer in WRITERS, t.name
        assert t.primary_key and set(t.primary_key) <= set(names), t.name
        for group in t.unique_together:
            assert set(group) <= set(names), (t.name, group)
        if t.layer == "processed":
            assert t.writer == "engine", t.name
        else:
            assert t.writer in ("generator", "oracle"), t.name


@pytest.mark.parametrize("table,field", FIELDS, ids=[f"{t.name}.{f.name}" for t, f in FIELDS])
def test_every_field_is_fully_specified(table, field):
    assert field.type in TYPES and field.origin in ORIGINS
    assert field.description
    if field.type in ("enum", "code") or (field.type == "list" and field.allowed):
        assert field.allowed or field.fk, "enumerated fields need allowed values or an FK"
    if field.type == "id":
        assert field.pattern, "ID fields need a pattern"
    if field.origin == "derived":
        assert field.derivation or field.rule, "derived fields need a formula or rule"
    if field.required_when:
        assert not field.required, "conditionally required fields are optional in the base sense"
    if field.type in ("money", "qty", "pct"):
        assert field.unit


def test_foreign_keys_resolve_to_a_unique_column_in_an_allowed_layer():
    for t, f in FIELDS:
        if not f.fk:
            continue
        target_table, _, target_col = f.fk.partition(".")
        assert target_table in BY_NAME, f.fk
        target = BY_NAME[target_table]
        col = target.column(target_col)
        assert col.unique or target.primary_key == (target_col,), f"{t.name}.{f.name} -> {f.fk}"
        assert target.layer in MAY_REFERENCE[t.layer], f"{t.name}.{f.name} -> {f.fk} crosses layers"


def test_foreign_key_graph_is_acyclic():
    edges = {t.name: {f.fk.split(".")[0] for f in t.fields if f.fk} - {t.name} for t in TABLES}
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        assert state.get(node) != 1, f"FK cycle through {node}"
        if state.get(node) == 2:
            return
        state[node] = 1
        for nxt in sorted(edges[node]):
            visit(nxt)
        state[node] = 2

    for name in sorted(edges):
        visit(name)


def test_inbox_and_master_carry_no_label_columns():
    forbidden = ("scenario", "expected", "intended", "label", "ground", "issue", "anomaly", "defect")
    for t in TABLES:
        if t.layer in ("master", "inbox"):
            for f in t.fields:
                assert not any(w in f.name for w in forbidden), f"{t.name}.{f.name}"


def test_ground_truth_vocabulary_matches_enums():
    gt = BY_NAME["ground_truth"]
    assert gt.column("scenario_code").allowed == enums.SCENARIO_CODES
    assert gt.column("scenario_category").allowed == enums.SCENARIO_CATEGORIES
    assert gt.column("expected_issue_types").allowed == enums.EXCEPTION_TYPES


def test_json_spec_and_markdown_are_up_to_date():
    assert SPEC_JSON.read_text(encoding="utf-8") == to_json(), "run: python -m invoice_ap docs"
    assert json.loads(SPEC_JSON.read_text(encoding="utf-8")) == to_dict()
    assert (DOCS_DIR / "data_dictionary.md").read_text(encoding="utf-8") == to_markdown(), \
        "run: python -m invoice_ap docs"
