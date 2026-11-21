"""Normalization behaviour tests (spec: careful normalization, originals kept)."""

from __future__ import annotations

from vendorlens.ml.normalization import (
    char_similarity,
    extract_legal_suffix,
    normalize_address,
    normalize_city,
    normalize_name,
    normalize_postal,
    normalize_state,
    normalize_website,
    strip_control_chars,
    token_jaccard,
)


def test_legal_suffix_stripped_for_comparison():
    assert normalize_name("Northstar Industrial Supplies LLC") == "northstar industrial supplies"
    assert normalize_name("Northstar Industrial Supplies Inc.") == "northstar industrial supplies"
    assert normalize_name("Northstar Industrial Supplies") == "northstar industrial supplies"


def test_suffix_extraction():
    assert extract_legal_suffix("Acme Supply LLC") == "LLC"
    assert extract_legal_suffix("Acme Supply Inc.") == "Inc."
    assert extract_legal_suffix("Acme Supply") is None


def test_whitespace_punctuation_case_normalized():
    assert normalize_name("  BLUE--RIDGE   Packaging ") == "blue ridge packaging"
    assert normalize_name("Blue-Ridge Packaging") == "blue ridge packaging"


def test_website_domain_extraction():
    assert normalize_website("https://www.northstarindustrial.example/") == "northstarindustrial.example"
    assert normalize_website("HTTP://NorthStarIndustrial.Example/about") == "northstarindustrial.example"
    assert normalize_website("northstarindustrial.example") == "northstarindustrial.example"
    assert normalize_website("") is None
    assert normalize_website(None) is None
    assert normalize_website("not a url") is None


def test_address_abbreviation():
    assert (
        normalize_address("100 Market Street, Suite 210")
        == "100 market st ste 210"
    )


def test_state_and_postal_normalization():
    assert normalize_state(" pa ") == "PA"
    assert normalize_postal(" 19103 ") == "19103"
    assert normalize_postal(None) is None


def test_control_characters_stripped():
    assert strip_control_chars("bad\x00name\x1f[") == "badname["


def test_similarity_helpers():
    assert char_similarity("abc", "abc") == 1.0
    assert char_similarity(None, "abc") == 0.0
    assert token_jaccard("a b", "b a") == 1.0
    assert token_jaccard("a b", "c d") == 0.0
