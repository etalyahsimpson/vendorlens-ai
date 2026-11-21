"""Deterministic synthetic supplier-register generator.

Produces a reproducible, fully synthetic benchmark dataset of supplier
records with known canonical-entity labels, plus a small unlabeled sample
CSV used by the application's "Explore Sample Data" flow.

Provenance (documented in docs/ML_METHODOLOGY.md):
    * Every record is fictional. Company names, addresses, postal codes and
      ``.example`` websites are generated from fixed word pools.
    * Generation is driven by a single documented seed (default 42) so the
      labeled dataset and sample CSV are byte-for-byte reproducible.
    * Ground-truth ``canonical_entity_id`` labels exist ONLY in the labeled
      pipeline output; they are never exposed to the model as features and
      are not part of the sample CSV or any API response.

The generator deliberately includes hard negatives: distinct companies that
share name tokens, cities and postal prefixes to make duplicate detection
non-trivial (e.g. "Northstar Industrial Supplies LLC" vs
"Northstar Office Services LLC" in the same city).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SEED = 42
N_CANONICAL_ENTITIES = 240  # within the required 200-300 range
HARD_NEGATIVE_GROUPS = 40  # canonical entities created as lookalike siblings
NAMESAKE_GROUPS = 12  # same name, different city/state/website -> NOT matches
SAMPLE_ENTITIES = 18  # entities included in the bundled sample CSV

SCHEMA_COLUMNS = [
    "supplier_id",
    "supplier_name",
    "street_address",
    "city",
    "state",
    "postal_code",
    "country",
    "website",
]
LABELED_COLUMNS = SCHEMA_COLUMNS + ["canonical_entity_id"]

_PREFIXES = [
    "Northstar", "Silverline", "Blue Ridge", "Ironwood", "Crestway",
    "Harborview", "Meridian", "Redstone", "Lakeshore", "Summit",
    "Pinnacle", "Clearwater", "Blackwell", "Fairmount", "Keystone",
    "Cardinal", "Stonebridge", "Ravenwood", "Westgate", "Ashford",
    "Copperfield", "Dunmore", "Eastport", "Foxglove", "Granite",
    "Hollowbrook", "Kingsley", "Larkspur", "Milstead", "Norwood",
    "Oakmont", "Pemberly", "Quarryhill", "Riverbend", "Sagebrook",
    "Thornbury", "Unionville", "Vineyard", "Wexford", "Yorkfield",
]
_CORES = [
    "Industrial", "Packaging", "Logistics", "Electronics", "Chemical",
    "Steel", "Medical", "Textile", "Precision", "Automotive", "Aerospace",
    "Polymer", "Machine", "Tool", "Plastic", "Rubber", "Wire", "Cable",
    "Bearing", "Valve", "Fastener", "Coating", "Metal", "Paper", "Glass",
]
# Distinguishing cores used ONLY for hard-negative sibling companies so the
# pair (same prefix, same city, different core) is a genuine "not the same
# entity" case.
_SIBLING_CORES = [
    "Office", "Janitorial", "Staffing", "Landscaping", "Catering",
    "Print", "Legal", "Design", "Security", "Real Estate",
]
_TYPES = [
    "Supplies", "Solutions", "Distribution", "Components", "Systems",
    "Materials", "Services", "Trading", "Industries", "Products",
    "Works", "Technologies",
]
_LEGAL_SUFFIXES = ["LLC", "Inc.", "Ltd.", "Corp.", "Co.", "LLP", "PLC", "GmbH", ""]

_STREET_NAMES = [
    "Market", "Chestnut", "Walnut", "Spruce", "Pine", "Elm", "Maple",
    "Oak", "Washington", "Franklin", "Liberty", "Commerce", "Industrial",
    "Foundry", "Railroad", "Canal", "Wharf", "Forge", "Cameron", "Harbor",
]
_STREET_TYPES = ["St", "Ave", "Blvd", "Rd", "Dr", "Way", "Pkwy", "Ln"]

# (city, state, postal prefix) - real US cities with plausible prefixes;
# street numbers and postal suffixes remain fictional.
_CITIES = [
    ("Philadelphia", "PA", "191"), ("Pittsburgh", "PA", "152"),
    ("New York", "NY", "100"), ("Brooklyn", "NY", "112"),
    ("Chicago", "IL", "606"), ("Houston", "TX", "770"),
    ("Phoenix", "AZ", "850"), ("Denver", "CO", "802"),
    ("Seattle", "WA", "981"), ("Portland", "OR", "972"),
    ("Detroit", "MI", "482"), ("Minneapolis", "MN", "554"),
    ("St. Louis", "MO", "631"), ("Atlanta", "GA", "303"),
    ("Charlotte", "NC", "282"), ("Boston", "MA", "021"),
    ("Newark", "NJ", "071"), ("Cleveland", "OH", "441"),
    ("Columbus", "OH", "432"), ("Indianapolis", "IN", "462"),
    ("Milwaukee", "WI", "532"), ("Nashville", "TN", "372"),
    ("Memphis", "TN", "381"), ("Kansas City", "MO", "641"),
    ("Baltimore", "MD", "212"), ("Richmond", "VA", "232"),
    ("Hartford", "CT", "061"), ("Providence", "RI", "029"),
    ("Buffalo", "NY", "142"), ("Rochester", "NY", "146"),
]


@dataclass
class _Record:
    supplier_name: str
    street_address: str | None
    city: str
    state: str
    postal_code: str
    country: str = "USA"
    website: str | None = None
    canonical_entity_id: str = ""
    supplier_id: str = field(default="")


def _misspell(rng: np.random.Generator, word: str) -> str:
    """Apply a single plausible typo to a word."""
    if len(word) < 4:
        return word
    strategy = rng.integers(0, 3)
    i = int(rng.integers(1, len(word) - 1))
    if strategy == 0:  # transpose adjacent characters
        return word[: i - 1] + word[i] + word[i - 1] + word[i + 1:]
    if strategy == 1:  # drop a vowel
        for j, ch in enumerate(word):
            if ch.lower() in "aeiou" and j != 0:
                return word[:j] + word[j + 1:]
        return word
    return word[:i] + word[i] * 2 + word[i + 1:]  # duplicate a letter


def _alias_name(rng: np.random.Generator, base_name: str, base_suffix: str) -> str:
    """Create one altered variant of a canonical supplier name."""
    words = base_name.split()
    n_transforms = 1 + int(rng.integers(0, 2))
    for _ in range(n_transforms):
        choice = rng.integers(0, 6)
        if choice == 0 and words:  # misspell one word
            idx = int(rng.integers(0, len(words)))
            words[idx] = _misspell(rng, words[idx])
        elif choice == 1 and len(words) > 2:  # drop a middle word
            idx = int(rng.integers(1, len(words) - 1))
            words.pop(idx)
        elif choice == 2:  # uppercase variant
            words = [w.upper() for w in words]
        elif choice == 3:  # lowercase variant
            words = [w.lower() for w in words]
        elif choice == 4 and words:  # spacing / punctuation join
            joiner = str(rng.choice([" ", "  ", "-", "/"]))
            words = [joiner.join(words[:1])] + words[1:]
        # choice == 5: no change (keeps some aliases close to the base name)
    name = " ".join(w for w in words if w)
    suffix = base_suffix if rng.random() < 0.6 else str(rng.choice(_LEGAL_SUFFIXES))
    return f"{name} {suffix}".strip()


def _make_address(rng: np.random.Generator) -> str:
    number = int(rng.integers(100, 9999))
    street = str(rng.choice(_STREET_NAMES))
    stype = str(rng.choice(_STREET_TYPES))
    if rng.random() < 0.3:
        unit = int(rng.integers(1, 40))
        floor = int(rng.integers(1, 12))
        return f"{number} {street} {stype}, Ste {unit * 10 + floor}"
    return f"{number} {street} {stype}"


def _make_website(slug: str) -> str:
    return f"{slug}.example"


def generate_labeled_dataset_with_meta(
    seed: int = SEED,
) -> tuple[list[_Record], dict]:
    """Generate the full labeled synthetic register plus entity metadata.

    Metadata is used only for deterministic sample selection and analysis -
    never as model features:

    * ``sibling_pairs``: (entity_id, entity_id) hard-negative lookalike pairs.
    * ``namesake_pairs``: (entity_id, entity_id) identical-name pairs that
      are different companies in different regions.
    """
    rng = np.random.default_rng(seed)

    # 1. Canonical entity names from prefix x core x type combinations.
    combos = [(p, c, t) for p in _PREFIXES for c in _CORES for t in _TYPES]
    picked = [combos[i] for i in rng.choice(len(combos), size=N_CANONICAL_ENTITIES, replace=False)]

    entities: list[dict] = []
    used_names: set[str] = set()
    for idx, (prefix, core, type_) in enumerate(picked):
        city, state, postal_prefix = _CITIES[int(rng.integers(0, len(_CITIES)))]
        suffix = str(rng.choice(_LEGAL_SUFFIXES))
        name = f"{prefix} {core} {type_}"
        if name in used_names:  # pragma: no cover - guarded by sampling space
            continue
        used_names.add(name)
        slug = (prefix + core).lower().replace(" ", "")
        entities.append(
            {
                "entity_index": idx,
                "name": name,
                "suffix": suffix,
                "city": city,
                "state": state,
                "postal_prefix": postal_prefix,
                "address": _make_address(rng),
                "website": _make_website(slug),
                "hard_negative": False,
            }
        )

    # 2. Hard-negative sibling entities: same prefix and city as an existing
    # entity, different core word, different website - a different company.
    sibling_pairs: list[tuple[str, str]] = []
    sibling_count = 0
    attempts = 0
    while sibling_count < HARD_NEGATIVE_GROUPS and attempts < HARD_NEGATIVE_GROUPS * 10:
        attempts += 1
        base = entities[int(rng.integers(0, len(entities)))]
        sibling_core = str(rng.choice(_SIBLING_CORES))
        sibling_type = str(rng.choice(_TYPES))
        name = f"{base['name'].split()[0]} {sibling_core} {sibling_type}"
        if name in used_names:
            continue
        used_names.add(name)
        prefix_word = base["name"].split()[0]
        entities.append(
            {
                "entity_index": len(entities),
                "name": name,
                "suffix": str(rng.choice(_LEGAL_SUFFIXES)),
                "city": base["city"],
                "state": base["state"],
                "postal_prefix": base["postal_prefix"],
                "address": _make_address(rng),
                "website": _make_website((prefix_word + sibling_core).lower().replace(" ", "")),
                "hard_negative": True,
                "base_entity_index": base["entity_index"],
            }
        )
        sibling_pairs.append(
            (f"ENT-{base['entity_index'] + 1:04d}", f"ENT-{len(entities):04d}")
        )
        sibling_count += 1

    # 3. Records: each canonical entity contributes its base record plus
    #    1-3 altered aliases (2-4 records per entity in total).
    records: list[_Record] = []
    for ent in entities:
        ent_id = f"ENT-{ent['entity_index'] + 1:04d}"
        n_aliases = int(rng.integers(1, 4))  # 1..3 -> 2..4 records per entity
        base_postal = f"{ent['postal_prefix']}{int(rng.integers(10, 99))}"
        # Base record.
        records.append(
            _Record(
                supplier_name=f"{ent['name']} {ent['suffix']}".strip(),
                street_address=ent["address"],
                city=ent["city"],
                state=ent["state"],
                postal_code=base_postal,
                website=ent["website"],
                canonical_entity_id=ent_id,
            )
        )
        for _ in range(n_aliases):
            # Aliases usually keep the base postal code and often keep the
            # base street address; ~10% have no address on file.
            postal = base_postal if rng.random() < 0.6 else f"{ent['postal_prefix']}{int(rng.integers(10, 99))}"
            r = rng.random()
            if r < 0.10:
                address = None
            elif r < 0.55:
                address = ent["address"]
            else:
                address = _make_address(rng)
            website = ent["website"]
            r = rng.random()
            if r < 0.15:  # legacy/secondary domain variant
                website = _make_website(ent["website"].split(".")[0] + "-group")
            elif r < 0.27:  # missing website
                website = None
            records.append(
                _Record(
                    supplier_name=_alias_name(rng, ent["name"], ent["suffix"]),
                    street_address=address,
                    city=ent["city"] if rng.random() < 0.97 else str(rng.choice([c[0] for c in _CITIES])),
                    state=ent["state"],
                    postal_code=postal,
                    website=website,
                    canonical_entity_id=ent_id,
                )
            )

    # 4. Namesake companies: identical name, different region and website.
    #    These are genuinely different businesses that share a name. Like all
    #    canonical entities they contribute 2-4 records.
    namesake_pairs: list[tuple[str, str]] = []
    namesake_source = [e for e in entities if not e["hard_negative"]]
    for k in range(NAMESAKE_GROUPS):
        base = namesake_source[int(rng.integers(0, len(namesake_source)))]
        other_city = _CITIES[int(rng.integers(0, len(_CITIES)))]
        while other_city[0] == base["city"]:  # ensure a different region
            other_city = _CITIES[int(rng.integers(0, len(_CITIES)))]
        ent_id = f"ENT-{len(entities) + k + 1:04d}"
        full_name = f"{base['name']} {str(rng.choice(_LEGAL_SUFFIXES))}".strip()
        slug = ("".join(base["name"].split()[:2])).lower()
        base_postal = f"{other_city[2]}{int(rng.integers(10, 99))}"
        records.append(
            _Record(
                supplier_name=full_name,
                street_address=_make_address(rng),
                city=other_city[0],
                state=other_city[1],
                postal_code=base_postal,
                website=_make_website(slug + "grp"),
                canonical_entity_id=ent_id,
            )
        )
        records.append(
            _Record(
                supplier_name=_alias_name(rng, full_name, str(rng.choice(_LEGAL_SUFFIXES))),
                street_address=_make_address(rng),
                city=other_city[0],
                state=other_city[1],
                postal_code=base_postal,
                website=_make_website(slug + "grp"),
                canonical_entity_id=ent_id,
            )
        )
        namesake_pairs.append(
            (f"ENT-{base['entity_index'] + 1:04d}", ent_id)
        )

    # 5. Shuffle deterministically and assign stable supplier IDs.
    order = rng.permutation(len(records))
    records = [records[i] for i in order]
    for i, rec in enumerate(records):
        rec.supplier_id = f"SUP-{i + 1:04d}"
    meta = {
        "sibling_pairs": sorted(sibling_pairs),
        "namesake_pairs": sorted(namesake_pairs),
    }
    return records, meta


def generate_labeled_dataset(seed: int = SEED) -> list[_Record]:
    """Convenience wrapper returning only the labeled records."""
    return generate_labeled_dataset_with_meta(seed)[0]


def records_to_rows(records: list[_Record], include_labels: bool) -> list[dict]:
    columns = LABELED_COLUMNS if include_labels else SCHEMA_COLUMNS
    return [{col: getattr(r, col) for col in columns} for r in records]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0].keys()) if rows else SCHEMA_COLUMNS
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_sample_rows(seed: int = SEED, n_entities: int = SAMPLE_ENTITIES) -> list[dict]:
    """Deterministically select entities for the bundled sample CSV.

    The sample deliberately mixes:

    * ordinary duplicate clusters (aliases of the same company),
    * several hard-negative lookalike sibling pairs (both sides), and
    * namesake companies (same name, different region),

    so the demo surfaces all recommendation bands. Labels are removed - the
    sample is exactly what an analyst would upload.
    """
    records, meta = generate_labeled_dataset_with_meta(seed)
    entity_ids = sorted({r.canonical_entity_id for r in records})
    rng = np.random.default_rng(seed + 1)
    chosen: set[str] = set(
        rng.choice(entity_ids, size=n_entities, replace=False).tolist()
    )

    # Include both sides of the first sibling (lookalike) pairs.
    for pair in meta["sibling_pairs"][:4]:
        chosen.update(pair)
    # Include the source company and its namesake for the first pairs.
    for pair in meta["namesake_pairs"][:2]:
        chosen.update(pair)

    sample = [r for r in records if r.canonical_entity_id in chosen]
    return records_to_rows(sample, include_labels=False)


def generate_all(output_root: Path, seed: int = SEED) -> dict[str, Path]:
    """Generate the labeled dataset and the UI sample CSV under output_root."""
    labeled = records_to_rows(generate_labeled_dataset(seed), include_labels=True)
    sample = build_sample_rows(seed)

    labeled_path = output_root / "data" / "generated" / "suppliers_labeled.csv"
    sample_path = output_root / "data" / "sample_suppliers.csv"
    write_csv(labeled_path, labeled)
    write_csv(sample_path, sample)
    return {"labeled": labeled_path, "sample": sample_path}
