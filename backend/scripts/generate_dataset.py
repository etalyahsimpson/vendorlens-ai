#!/usr/bin/env python3
"""Regenerate the deterministic synthetic datasets.

Writes:
    data/generated/suppliers_labeled.csv  (training/evaluation pipeline only)
    data/sample_suppliers.csv             (bundled UI sample, no labels)

Run from the repository root:  python backend/scripts/generate_dataset.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from vendorlens.config import repo_root
from vendorlens.data.generator import SEED, generate_all, generate_labeled_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output-root", type=Path, default=None)
    args = parser.parse_args()

    root = args.output_root or repo_root()
    paths = generate_all(root, seed=args.seed)
    records = generate_labeled_dataset(args.seed)
    entities = {r.canonical_entity_id for r in records}

    print(f"Seed:                  {args.seed}")
    print(f"Records generated:     {len(records)}")
    print(f"Canonical entities:    {len(entities)}")
    print(f"Labeled dataset:       {paths['labeled']}")
    print(f"UI sample (no labels): {paths['sample']}")


if __name__ == "__main__":
    main()
