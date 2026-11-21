"""CSV input validation: the trust boundary for uploaded supplier files.

Rules (documented in docs/SECURITY_AND_LIMITATIONS.md and
docs/DATA_DICTIONARY.md):

* CSV files only; rejected extensions and non-UTF-8 encodings fail with
  explicit messages (never a Python traceback).
* Hard limits: 5 MB upload size, 2000 rows per analysis.
* Required columns ``supplier_id`` (unique, nonempty) and ``supplier_name``
  (nonempty); optional address/city/state/postal/country/website columns.
* Control characters are stripped before storage/display; optional missing
  values are recorded as missing, never as a match or mismatch signal.
* Uploaded content is treated as data only - never executed, never rendered
  as HTML by the frontend, never interpreted as formulas.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from vendorlens.config import MAX_ROWS, MAX_UPLOAD_BYTES
from vendorlens.ml.candidates import CandidateRecord
from vendorlens.ml.normalization import (
    clean_display_value,
    normalize_address,
    normalize_city,
    normalize_name,
    normalize_postal,
    normalize_state,
    normalize_website,
)

REQUIRED_COLUMNS = ["supplier_id", "supplier_name"]
OPTIONAL_COLUMNS = [
    "street_address",
    "city",
    "state",
    "postal_code",
    "country",
    "website",
]


class CSVValidationError(Exception):
    """Structured, user-facing validation failure."""

    def __init__(self, code: str, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []


@dataclass
class ValidatedRecord(CandidateRecord):
    """A parsed supplier row with original + normalized fields."""

    original_supplier_name: str = ""
    normalized_name_v: str | None = None

    @property
    def normalized_fields(self) -> dict[str, str | None]:
        return {
            "normalized_name": self.normalized_name_v,
            "normalized_city": normalize_city(self.city),
            "normalized_state": normalize_state(self.state),
            "normalized_postal": normalize_postal(self.postal_code),
            "normalized_website": normalize_website(self.website),
            "normalized_address": normalize_address(self.street_address),
        }


@dataclass
class ValidatedCSV:
    records: list[ValidatedRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_csv_bytes(filename: str, content: bytes) -> ValidatedCSV:
    """Validate and parse an uploaded CSV into typed records."""
    name = (filename or "").strip().lower()
    if not name.endswith(".csv"):
        raise CSVValidationError(
            "unsupported_file_type",
            "Only .csv files are accepted.",
            [f"Received file name: {filename or '(none)'}"],
        )
    if not content:
        raise CSVValidationError("empty_file", "The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise CSVValidationError(
            "file_too_large",
            "The uploaded file exceeds the 5 MB limit.",
            [f"Size: {len(content)} bytes (limit {MAX_UPLOAD_BYTES})."],
        )

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVValidationError(
            "invalid_encoding",
            "The file must be UTF-8 encoded CSV.",
            [f"Decoding failed near byte {exc.start}."],
        ) from exc

    try:
        reader = csv.DictReader(io.StringIO(text))
        fieldnames = reader.fieldnames or []
    except csv.Error as exc:  # pragma: no cover - DictReader is lazy
        raise CSVValidationError("malformed_csv", "The CSV could not be parsed.", [str(exc)]) from exc

    headers = [h.strip().lower() for h in fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise CSVValidationError(
            "missing_required_columns",
            "Required columns are missing from the CSV header.",
            [f"Missing: {', '.join(missing)}", f"Found: {', '.join(headers) or '(none)'}"],
        )

    warnings: list[str] = []
    unknown = [h for h in headers if h not in REQUIRED_COLUMNS + OPTIONAL_COLUMNS]
    if unknown:
        warnings.append(
            "Ignored columns not in the schema: " + ", ".join(sorted(set(unknown)))
        )

    records: list[ValidatedRecord] = []
    seen_ids: dict[str, int] = {}
    duplicates: list[str] = []

    for line_no, row in enumerate(reader, start=2):
        if row is None:
            continue
        raw = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k is not None}
        supplier_id = clean_display_value(raw.get("supplier_id", ""))
        supplier_name = clean_display_value(raw.get("supplier_name", ""))
        if supplier_id is None or supplier_name is None:
            raise CSVValidationError(
                "missing_required_value",
                "supplier_id and supplier_name must be nonempty on every row.",
                [f"Row {line_no}: missing required value(s)."],
            )
        if supplier_id in seen_ids:
            duplicates.append(supplier_id)
        else:
            seen_ids[supplier_id] = line_no
        records.append(
            ValidatedRecord(
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                original_supplier_name=supplier_name,
                street_address=clean_display_value(raw.get("street_address")),
                city=clean_display_value(raw.get("city")),
                state=clean_display_value(raw.get("state")),
                postal_code=clean_display_value(raw.get("postal_code")),
                country=clean_display_value(raw.get("country")),
                website=clean_display_value(raw.get("website")),
                normalized_name_v=normalize_name(supplier_name),
            )
        )

    if not records:
        raise CSVValidationError(
            "no_data_rows", "The CSV contains a header but no data rows."
        )
    if duplicates:
        raise CSVValidationError(
            "duplicate_supplier_ids",
            "supplier_id values must be unique within the uploaded file.",
            [f"Duplicate IDs: {', '.join(duplicates[:10])}"],
        )
    if len(records) > MAX_ROWS:
        raise CSVValidationError(
            "too_many_rows",
            f"Analyses are limited to {MAX_ROWS} supplier rows.",
            [f"Rows in file: {len(records)} (limit {MAX_ROWS})."],
        )

    return ValidatedCSV(records=records, warnings=warnings)


def load_sample_records(path) -> ValidatedCSV:
    """Load the bundled sample CSV through the same validation path."""
    return validate_csv_bytes(path.name, path.read_bytes())
