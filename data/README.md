# Data Directory

## `sample_suppliers.csv` — bundled UI sample (78 records)

A deterministic subset of the synthetic supplier register, shaped exactly like
a user upload (no labels). It deliberately contains:

- ordinary duplicate clusters (aliases of the same company with suffix, case,
  typo and domain variations),
- hard-negative lookalike companies (shared name prefix/city, different
  business and website),
- namesake companies (identical name, different region),
- missing optional fields.

Opening it via **Explore Sample Data** exercises the full pipeline: FAISS
candidate retrieval → pair features → trained classifier → recommendation
bands → review workflow.

## `generated/suppliers_labeled.csv` — labeled benchmark (850 records, 292 entities)

The full generated register **including the `canonical_entity_id` ground-truth
labels**. Used only by the training/evaluation pipeline; never exposed through
the API, never included in the sample, never a model feature.

## Provenance

Both files are produced by `backend/vendorlens/data/generator.py` with seed
**42** and are byte-for-byte reproducible:

```bash
make generate   # regenerates both files identically
```

All records are fictional. Company names, street numbers, postal suffixes and
`.example` websites are synthesized; city/state pairs reference real US
locations for realism. See `docs/ML_METHODOLOGY.md` for the full methodology
and the external-validity limitations of benchmark metrics.
