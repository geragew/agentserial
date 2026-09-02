# Contributing

Changes to checking behavior must first update `SPEC.md`, state the property and
assumptions being changed, and add a semantic regression test. Avoid terminology
that implies stronger guarantees than the implementation provides.

Run locally:

```console
python -m pip install -e ".[dev]"
python -m ruff check agentserial tests scripts
python -m ruff format --check agentserial tests scripts
pytest
python scripts/export_schemas.py --check
python scripts/release_smoke.py
npm ci
npm run test:sdk
npm run typecheck:sdk
npm run test:ui
npm run test:integration
```

Tests must not require a network connection, model API, credential, or external
service after dependencies are installed. Examples must contain fictional data
only. Keep public behavior deterministic and preserve causal reachability when
changing order projection or counterexample reduction.
