"""Deterministic synthetic data generator tests."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from vendorlens.data.generator import (
    LABELED_COLUMNS,
    SCHEMA_COLUMNS,
    SEED,
    build_sample_rows,
    generate_all,
    generate_labeled_dataset,
    generate_labeled_dataset_with_meta,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_generator_is_deterministic():
    a = generate_labeled_dataset(SEED)
    b = generate_labeled_dataset(SEED)
    assert [(r.supplier_id, r.supplier_name) for r in a] == [
        (r.supplier_id, r.supplier_name) for r in b
    ]


def test_entity_and_record_counts_in_required_range():
    records = generate_labeled_dataset(SEED)
    entities = {r.canonical_entity_id for r in records}
    # Spec: 200-300 canonical entities, 2-4 records per entity.
    assert 200 <= len(entities) <= 300
    by_entity: dict[str, int] = {}
    for r in records:
        by_entity[r.canonical_entity_id] = by_entity.get(r.canonical_entity_id, 0) + 1
    assert all(2 <= n <= 4 for n in by_entity.values()), (
        "every canonical entity must contribute 2-4 records"
    )


def test_hard_negative_sibling_pairs_exist():
    _records, meta = generate_labeled_dataset_with_meta(SEED)
    assert len(meta["sibling_pairs"]) >= 20, "expected hard-negative lookalikes"
    assert len(meta["namesake_pairs"]) >= 5, "expected same-name different-region pairs"


def test_required_fields_nonempty_and_fictional():
    records = generate_labeled_dataset(SEED)
    for r in records:
        assert r.supplier_id and r.supplier_name and r.city and r.state and r.postal_code
        assert r.website is None or r.website.endswith(".example"), (
            "all synthetic websites must use the reserved .example TLD"
        )


def test_sample_csv_matches_input_schema_without_labels():
    rows = build_sample_rows(SEED)
    assert rows, "sample must not be empty"
    assert list(rows[0].keys()) == SCHEMA_COLUMNS
    assert "canonical_entity_id" not in rows[0], (
        "ground-truth labels must never leak into the sample CSV"
    )


def test_generate_all_writes_reproducible_csv(tmp_path):
    paths = generate_all(tmp_path, seed=SEED)
    first = paths["labeled"].read_bytes()
    generate_all(tmp_path, seed=SEED)
    assert first == paths["labeled"].read_bytes(), "regeneration must be byte-identical"

    with open(paths["labeled"], newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == LABELED_COLUMNS


def test_committed_dataset_matches_generator():
    """The committed labeled CSV must equal a fresh deterministic regeneration."""
    committed = REPO_ROOT / "data" / "generated" / "suppliers_labeled.csv"
    if not committed.exists():  # before first generation
        return
    rows = generate_labeled_dataset(SEED)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=LABELED_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({c: getattr(r, c) for c in LABELED_COLUMNS})
    assert buf.getvalue() == committed.read_text(encoding="utf-8")
