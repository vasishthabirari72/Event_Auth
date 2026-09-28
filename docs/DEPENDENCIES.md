# Dependency review — M1/M2

This file flags additions replacing the old Flutter dependency list. Direct installed
package metadata and upstream model licences were checked on 2026-09-24. Exact package
versions are in uv.lock and frontend/package-lock.json. Review transitive notices before
distribution; this is not a claim that all third-party redistribution obligations are complete.

| Dependency | Licence / use |
|---|---|
| FastAPI, SQLAlchemy, Alembic | MIT; local HTTP and PostgreSQL persistence |
| Uvicorn | BSD-3-Clause; local server |
| psycopg and psycopg-binary | LGPL-3.0-only; PostgreSQL driver; retain notices and applicable LGPL rights when distributing |
| OpenCV Python | Apache-2.0 package; bundled third-party notices also apply; camera and local ONNX execution |
| NumPy | BSD-3-Clause plus bundled 0BSD/MIT/Zlib/CC0 notices; numerical arrays |
| React, React DOM, Vite, React plugin | MIT; all assets served locally |
| TypeScript | Apache-2.0; build-time type checking |
| ESLint, typescript-eslint, Prettier, Vitest, React types, globals | MIT; development only |
| pytest, pytest-cov, Ruff, mypy | MIT; development only |
| HTTPX | BSD-3-Clause; in-process HTTP tests only |
| uv / Hatchling | MIT or Apache-2.0 / MIT respectively; environment/build tooling |

Dependencies do not require an internet service during application operation. Do not use
OpenCV sample downloads, remote fonts, CDN scripts or automatic model downloads at runtime.
Model-specific licences and hashes are separate: see MODEL_EVALUATION.md and assets/models.

## M2 additions — 2026-09-25
- cryptography 50.0.1: Apache-2.0 OR BSD-3-Clause; local authenticated encryption
  using Fernet. [Upstream licence declaration](https://github.com/pyca/cryptography/blob/main/pyproject.toml).
- openpyxl 3.1.5: MIT; local .xlsx imports. [Publisher metadata](https://pypi.org/project/openpyxl/).
- defusedxml 0.7.1: PSFL; protects XML parsing used by Excel imports.
- New transitive packages: cffi 2.1.1 (MIT-0), pycparser 3.0 (BSD-3-Clause),
  et-xmlfile 2.0.0 (MIT). Installed metadata checked; exact resolution is in uv.lock.
  These packages make no application-runtime network requests.
- No new frontend dependency. Browser smoke checks use the installed Chrome and Node's
  built-in DevTools/WebSocket support with a disposable fake-data profile.

## M3 addition — 2026-09-27
ReportLab 5.0.1 generates PDFs and QR vectors entirely locally. BSD licence:
https://docs.reportlab.com/developerfaqs/ . No separate QR dependency is required.
Its locked dependencies include Pillow (MIT-CMU) and charset-normalizer (MIT).
No runtime downloads, remote fonts or external PDF services. No new frontend package.
PDF raster validation uses an already-installed `pdftoppm` executable in development;
it is not required to generate PDFs in the running app.

## M5 operator tools — 2026-09-28
No new Python/frontend dependencies. Existing cryptography supplies Scrypt and AES-GCM;
PostgreSQL 17's container supplies pg_dump/pg_restore. HTTPS uses existing Uvicorn/ssl.
Optional setup-time mkcert is BSD-3-Clause ([upstream licence](https://github.com/FiloSottile/mkcert/blob/master/LICENSE));
Ubuntu libnss3-tools provides certutil for local trust setup. Neither was installed or
run in this increment. mkcert is for controlled local development/pilot provisioning;
certificate trust must be explicitly established on intended devices. No runtime internet.
