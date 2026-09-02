# Contributing

Changes to checking behavior must first update `SPEC.md`, state the property and
assumptions being changed, and add a semantic regression test. Avoid terminology
that implies stronger guarantees than the implementation provides.

Run locally:

```console
python -m pip install -e ".[dev]"
pytest
python scripts/export_schemas.py --check
python scripts/release_smoke.py
```

Tests must not require a network connection, model API, credential, or external
service. Examples must contain fictional data only.
