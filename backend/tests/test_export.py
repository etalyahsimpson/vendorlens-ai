"""Export sanitization unit tests (spreadsheet formula injection)."""

from __future__ import annotations

from vendorlens.services.export import EXPORT_COLUMNS, neutralize_formula


def test_neutralizes_all_documented_prefixes():
    for payload in ("=cmd", "+123", "-sum", "@SUM(A1)", "\ttab", "\rcr"):
        assert neutralize_formula(payload).startswith("'"), payload


def test_leaves_normal_values_untouched():
    assert neutralize_formula("Northstar Industrial Supplies LLC") == "Northstar Industrial Supplies LLC"
    assert neutralize_formula("0.93") == "0.93"
    assert neutralize_formula("") == ""
    assert neutralize_formula(None) == ""
    # Supplier IDs like SUP-0107 must not be altered.
    assert neutralize_formula("SUP-0107") == "SUP-0107"


def test_export_schema_documented():
    assert EXPORT_COLUMNS[0] == "pair_id"
    for column in (
        "left_supplier_id",
        "right_supplier_name",
        "model_score",
        "recommendation_band",
        "review_decision",
        "reviewed_at",
    ):
        assert column in EXPORT_COLUMNS
