"""CSV validation tests: the untrusted-upload trust boundary."""

from __future__ import annotations

import pytest

from vendorlens.config import MAX_ROWS, MAX_UPLOAD_BYTES
from vendorlens.data.validation import CSVValidationError, validate_csv_bytes

VALID_CSV = """supplier_id,supplier_name,city,state,website
SUP-1,Northstar Industrial Supplies LLC,Philadelphia,PA,northstarindustrial.example
SUP-2,North Star Industrial Supply,Philadelphia,PA,northstarindustrial.example
"""


def _csv(rows: list[str], header: str = "supplier_id,supplier_name,city,state,website") -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode("utf-8")


def test_valid_csv_parses():
    result = validate_csv_bytes("suppliers.csv", VALID_CSV.encode("utf-8"))
    assert len(result.records) == 2
    rec = result.records[0]
    assert rec.supplier_id == "SUP-1"
    assert rec.supplier_name == "Northstar Industrial Supplies LLC"
    assert rec.normalized_fields["normalized_name"] == "northstar industrial supplies"
    assert rec.normalized_fields["normalized_website"] == "northstarindustrial.example"


def test_original_values_preserved_alongside_normalized():
    result = validate_csv_bytes("suppliers.csv", VALID_CSV.encode("utf-8"))
    rec = result.records[0]
    # Original display value untouched; normalized comparison value separate.
    assert rec.supplier_name == "Northstar Industrial Supplies LLC"
    assert rec.normalized_name_v == "northstar industrial supplies"


def test_rejects_non_csv_extension():
    with pytest.raises(CSVValidationError) as exc:
        validate_csv_bytes("suppliers.xlsx", VALID_CSV)
    assert exc.value.code == "unsupported_file_type"


def test_rejects_empty_file():
    with pytest.raises(CSVValidationError) as exc:
        validate_csv_bytes("suppliers.csv", b"")
    assert exc.value.code == "empty_file"


def test_rejects_invalid_encoding():
    with pytest.raises(CSVValidationError) as exc:
        validate_csv_bytes("suppliers.csv", b"\xff\xfe\x00suppliers")
    assert exc.value.code == "invalid_encoding"


def test_rejects_missing_required_headers():
    bad = b"supplier_id,city\nSUP-1,Philadelphia\n"
    with pytest.raises(CSVValidationError) as exc:
        validate_csv_bytes("suppliers.csv", bad)
    assert exc.value.code == "missing_required_columns"
    assert "supplier_name" in " ".join(exc.value.details)


def test_rejects_duplicate_supplier_ids():
    dup = _csv(
        [
            "SUP-1,Alpha Supply LLC,Philadelphia,PA,alpha.example",
            "SUP-1,Alpha Supply Inc.,Philadelphia,PA,alpha.example",
        ]
    )
    with pytest.raises(CSVValidationError) as exc:
        validate_csv_bytes("suppliers.csv", dup)
    assert exc.value.code == "duplicate_supplier_ids"


def test_rejects_missing_required_values():
    bad = _csv(["SUP-1,,Philadelphia,PA,alpha.example"])
    with pytest.raises(CSVValidationError) as exc:
        validate_csv_bytes("suppliers.csv", bad)
    assert exc.value.code == "missing_required_value"


def test_rejects_header_only_file():
    with pytest.raises(CSVValidationError) as exc:
        validate_csv_bytes("suppliers.csv", b"supplier_id,supplier_name\n")
    assert exc.value.code == "no_data_rows"


def test_rejects_row_limit_exceeded():
    rows = [f"SUP-{i},Company {i} LLC,City,ST,c{i}.example" for i in range(MAX_ROWS + 1)]
    with pytest.raises(CSVValidationError) as exc:
        validate_csv_bytes("suppliers.csv", _csv(rows))
    assert exc.value.code == "too_many_rows"
    assert str(MAX_ROWS + 1) in " ".join(exc.value.details)


def test_rejects_oversized_file():
    content = b"supplier_id,supplier_name\n" + b"SUP-1,Padded" + b" " * (MAX_UPLOAD_BYTES)
    with pytest.raises(CSVValidationError) as exc:
        validate_csv_bytes("suppliers.csv", content)
    assert exc.value.code == "file_too_large"


def test_control_characters_neutralized():
    evil = _csv(["SUP-1,Bad\x00Name\x1bCorp,Philadelphia,PA,bad.example"])
    result = validate_csv_bytes("suppliers.csv", evil)
    assert "\x00" not in result.records[0].supplier_name
    assert result.records[0].supplier_name == "BadNameCorp"


def test_unknown_columns_warn_but_do_not_fail():
    warn = _csv(
        ["SUP-1,Alpha Supply,Philadelphia,PA,alpha.example"],
        header="supplier_id,supplier_name,city,state,website,extra_note",
    )
    result = validate_csv_bytes("suppliers.csv", warn)
    assert result.records[0].supplier_id == "SUP-1"
    assert any("extra_note" in w for w in result.warnings)


def test_missing_optional_fields_are_none_not_signals():
    sparse = _csv(["SUP-1,Solo Supply"], header="supplier_id,supplier_name")
    result = validate_csv_bytes("suppliers.csv", sparse)
    rec = result.records[0]
    assert rec.city is None
    assert rec.website is None
    # Missing optional data must not become a match/mismatch value.
    assert rec.normalized_fields["normalized_city"] is None
    assert rec.normalized_fields["normalized_website"] is None
