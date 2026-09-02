# Continuous integration and security scanning

GitHub Actions runs from a clean checkout on Python 3.12. The `test` job starts
PostgreSQL 16 with a health check, installs exactly `requirements.txt`, compiles
the application, upgrades a clean schema, downgrades and re-upgrades the latest
revision, checks Alembic drift, and runs the complete pytest suite. AI is disabled
and Elastic is unset so external providers cannot make CI nondeterministic.

The repository currently has no configured Ruff, Black, mypy, or Pyright policy.
CI therefore does not silently invent style/type gates: `compileall` and pytest
are the deliberate configured equivalents. Add a pinned tool and its configuration
in a dedicated change before making it a required check.

The dependency-audit job runs pinned `pip-audit` against the requirements file.
The secret-scan job runs Gitleaks with the repository default rules. Test fixtures
are allowlisted only because they contain explicitly marked non-secret tokens and
password hashes; real credentials must never be added there. Dependabot opens
monthly pip update PRs.

All jobs grant `contents: read`, use no repository secrets, run on untrusted PR
code without write permissions, have timeouts, and cancel superseded runs. Action
checkout/setup-python references are immutable commit SHAs. Gitleaks is pinned to
the maintained major action line because its release commit is managed upstream;
renovate/dependabot should surface action upgrades for review.
The secret-scan checkout fetches full history so pull-request parent revisions
are available and the scanner cannot silently degrade to a zero-byte scan.

Local equivalents:

```bash
python -m pip install -r requirements.txt
python -m compileall -q api api_client app backend config db tests
POSTGRES_PORT=5432 python -m alembic upgrade head
POSTGRES_PORT=5432 python -m alembic downgrade -1
POSTGRES_PORT=5432 python -m alembic upgrade head
POSTGRES_PORT=5432 python -m alembic check
pytest -q
pip-audit -r requirements.txt
gitleaks detect --no-banner --redact
```

No CI secrets are required. If a future provider integration needs credentials,
keep them in environment-scoped secrets unavailable to pull requests from forks.
For failures, inspect the first failing job, reproduce its local equivalent, and
update the relevant dependency/configuration in a separate reviewed commit.
