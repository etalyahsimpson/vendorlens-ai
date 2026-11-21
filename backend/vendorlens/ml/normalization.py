"""Text normalization utilities shared by training and inference.

Normalization produces the comparison forms used by candidate retrieval and
pair-feature engineering. Original field values are always preserved for
display and export; these functions never mutate source data.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# Legal / corporate suffix tokens removed for name comparison. Removal is a
# feature transformation only - it is not evidence that two records are the
# same legal entity.
LEGAL_SUFFIXES = {
    "llc", "l.l.c", "inc", "incorporated", "ltd", "limited", "corp",
    "corporation", "co", "company", "plc", "gmbh", "ag", "sa", "sas",
    "lp", "llp", "lpa", "pllc", "and sons", "bros", "brothers",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_WS_RE = re.compile(r"\s+")

# Street-type abbreviations applied when normalizing addresses.
_STREET_ABBR = {
    "street": "st", "avenue": "ave", "boulevard": "blvd", "road": "rd",
    "drive": "dr", "lane": "ln", "parkway": "pkwy", "highway": "hwy",
    "suite": "ste", "floor": "fl", "building": "bldg", "north": "n",
    "south": "s", "east": "e", "west": "w",
}


def strip_control_chars(value: str) -> str:
    """Remove C0/C1 control characters from untrusted text before storage."""
    return _CONTROL_RE.sub("", value)


def clean_display_value(value: str | None) -> str | None:
    """Sanitize an untrusted string for display: strip control chars, trim."""
    if value is None:
        return None
    cleaned = strip_control_chars(value).strip()
    return cleaned if cleaned else None


def _basic_normalize(value: str | None) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def extract_legal_suffix(name: str) -> str | None:
    """Return the trailing legal suffix token of a supplier name, if any."""
    if not name:
        return None
    tokens = [t for t in re.split(r"[\s,]+", name.strip()) if t]
    if not tokens:
        return None
    last = tokens[-1].rstrip(".").lower()
    if last in LEGAL_SUFFIXES:
        return tokens[-1]
    tail = " ".join(t.lower() for t in tokens[-2:])
    if tail in LEGAL_SUFFIXES:
        return " ".join(tokens[-2:])
    return None


def normalize_name(name: str | None) -> str | None:
    """Normalize a supplier name for comparison.

    Lowercase, strip punctuation, collapse whitespace and remove legal-suffix
    tokens. The suffix itself is compared separately as an explicit feature.
    """
    if name is None:
        return None
    text = _basic_normalize(name) or ""
    tokens = text.split(" ")
    kept = [t for t in tokens if t not in LEGAL_SUFFIXES]
    normalized = " ".join(kept).strip()
    return normalized or None


def normalize_website(url: str | None) -> str | None:
    """Reduce a website value to a bare, comparable domain."""
    if url is None:
        return None
    text = strip_control_chars(url).strip().lower()
    if not text:
        return None
    text = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", text)
    text = text.split("/", 1)[0]
    text = text.split("?", 1)[0].split("#", 1)[0]
    for prefix in ("www.", "www2.", "m."):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    text = text.strip(".")
    if not text or "." not in text:
        return None
    return text


def normalize_address(address: str | None) -> str | None:
    """Normalize a street address: lowercase, punctuation, abbreviations."""
    if address is None:
        return None
    text = _basic_normalize(address)
    if not text:
        return None
    tokens = [_STREET_ABBR.get(t, t) for t in text.split(" ")]
    return " ".join(tokens) or None


def normalize_city(city: str | None) -> str | None:
    return _basic_normalize(city)


def normalize_state(state: str | None) -> str | None:
    if state is None:
        return None
    text = strip_control_chars(state).strip().upper()
    return text or None


def normalize_postal(postal: str | None) -> str | None:
    if postal is None:
        return None
    text = strip_control_chars(postal).strip().upper()
    text = re.sub(r"\s+", "", text)
    return text or None


def char_similarity(a: str | None, b: str | None) -> float:
    """SequenceMatcher ratio of two normalized strings; missing -> 0.0."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def token_jaccard(a: str | None, b: str | None) -> float:
    """Jaccard overlap of token sets; missing -> 0.0."""
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def token_containment(a: str | None, b: str | None) -> float:
    """|tokens(a) ∩ tokens(b)| / min(|a|, |b|); rewards shared vocabulary."""
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))
