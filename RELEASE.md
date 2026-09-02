# Release process

AgentSerial publishes one source version to PyPI, npm, and GitHub Releases. A
GitHub release is the only production publication trigger; manual workflow runs
build and validate artifacts but never publish them.

## One-time registry setup

1. Create the PyPI project `agentserial` and configure a Trusted Publisher for
   repository `geragew/agentserial`, workflow `publish.yml`, environment `pypi`.
2. Create the npm package `@geragew/agentserial` and configure trusted publishing
   for repository `geragew/agentserial`, workflow `publish.yml`, environment
   `npm`.
3. In GitHub, protect the `pypi` and `npm` environments with required reviewer
   approval. Do not add long-lived registry tokens.

Registry names are not reserved by this repository configuration. The owner must
complete the first publication while the names remain available.

## Release checklist

1. Update the version in `pyproject.toml` and `sdk/javascript/package.json`.
2. Update release notes, compatibility statements, and migration guidance.
3. Run `python scripts/release_metadata.py` and the commands in `CONTRIBUTING.md`.
4. Commit the release, tag the exact commit as `v<version>`, and push the tag.
5. Create a GitHub release from that tag.
6. Approve the protected `pypi` and `npm` deployment environments.
7. Verify clean registry installs and the GitHub artifact attestations.

The workflow rejects mismatched Python, JavaScript, and tag versions. It validates
the packages on Linux, Windows, and macOS before building once on GitHub-hosted
infrastructure. Published assets include SHA-256 hashes, source commit, schema
compatibility, runtime support, an SPDX software bill of materials, and build
provenance.

The Python build backend is pinned in `pyproject.toml`. Backend upgrades are
intentional changes and require package metadata validation plus a clean-install
test; they must not be introduced implicitly during a release.

## Verification

```console
python -m pip install --isolated agentserial==<version>
npm install @geragew/agentserial@<version>
gh attestation verify agentserial-<version>-py3-none-any.whl --repo geragew/agentserial
```

Compare downloaded artifact hashes with `release-manifest.json`. A provenance
attestation proves where an artifact was built; it does not prove the code is
correct or safe.

## Failure and rollback

Registry releases are immutable and must never be overwritten. If publication is
partial, keep the successful artifact, repair the workflow, and publish the same
version only to the missing registry. If released behavior is defective, mark the
affected version as yanked or deprecated with a reason, publish a corrected patch
version, and document compatibility impact. Never reuse a released version.

The synchronized release process currently accepts canonical stable versions in
`major.minor.patch` form. Add prerelease support only with cross-registry tests
that prove Python and npm normalize the chosen version identically.
