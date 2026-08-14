# CPA Channels, Cached Quotas, And Admin Console

```yaml
status: completed
current_milestone: M11
last_completed_milestone: M11
next_action: 推送 codex/release-0.3.0，创建 Pull Request，并等待 CI 全部通过
last_updated: 2026-08-14
branch: codex/release-0.3.0
head: null
changed_files:
  - .env.example
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - Dockerfile
  - README.md
  - config.json.example
  - docker-compose.yml.example
  - docs/plans/cpa-admin-quota.md
  - scripts/package-source.sh
  - scripts/package-uv.sh
  - scripts/check-version.py
  - scripts/render-release-notes.sh
  - scripts/start.bat
  - scripts/start.sh
  - backend/pyproject.toml
  - backend/uv.lock
  - backend/app/analytics.py
  - backend/app/auth.py
  - backend/app/bootstrap.py
  - backend/app/config.py
  - backend/app/cpa_quota.py
  - backend/app/db.py
  - backend/app/main.py
  - backend/app/logging_config.py
  - backend/app/quota_sync.py
  - backend/app/scheduler.py
  - backend/app/schemas.py
  - backend/app/secrets.py
  - backend/app/usage_sync.py
  - backend/app/version.py
  - backend/tests/conftest.py
  - backend/tests/test_analytics.py
  - backend/tests/test_api_config.py
  - backend/tests/test_api_cpa.py
  - backend/tests/test_api_quota.py
  - backend/tests/test_auth.py
  - backend/tests/test_cpa_quota.py
  - backend/tests/test_cpa_sync.py
  - backend/tests/test_db.py
  - backend/tests/test_quota_snapshots.py
  - backend/tests/test_scheduler.py
  - backend/tests/test_secrets.py
  - backend/tests/test_usage_sync.py
  - backend/tests/test_logging.py
  - frontend/package.json
  - frontend/pnpm-lock.yaml
  - frontend/src/App.tsx
  - frontend/src/components/quota/QuotaCards.tsx
  - frontend/src/components/usage/UsageTable.tsx
  - frontend/src/contexts/AdminAuthContext.tsx
  - frontend/src/contexts/QuotaContext.tsx
  - frontend/src/layouts/AdminLayout.tsx
  - frontend/src/layouts/AppLayout.tsx
  - frontend/src/lib/api.ts
  - frontend/src/lib/quota-cache.ts
  - frontend/src/lib/quota-sort.ts
  - frontend/src/lib/quota-stats.ts
  - frontend/src/pages/AccountDetailPage.tsx
  - frontend/src/pages/AccountsPage.tsx
  - frontend/src/pages/AdminLoginPage.tsx
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/pages/OverviewPage.tsx
  - frontend/src/pages/SettingsPage.tsx
focused_tests:
  - "M8 review baseline: 25 passed, 1 Starlette/httpx deprecation warning"
  - "baseline backend: 21 passed, 1 pre-existing time-window failure"
  - "M1 security/database: 13 passed"
  - "M2 authentication/authorization: 15 passed"
  - "M3 snapshots/scheduler/public zero-network APIs: 5 passed"
  - "M4 CPA parser/CRUD/encryption/scheduler: 18 passed"
  - "M5 backend full suite after cross-stack integration: 56 passed"
  - "M6 CPA plaintext-key migration regression: 8 passed"
  - "M7 security/database/HMAC remediation: 37 passed"
  - "M7 leases/scheduler/selective triggers: 21 passed"
  - "M7 public DTO/config contract: 15 passed"
  - "M7 resume public/config regression: 12 passed"
  - "M8 review fixes and logging bundle: 41 passed, 1 Starlette/httpx deprecation warning"
  - "M8 final logging/auth/scheduler hardening: 17 passed, 1 Starlette/httpx deprecation warning"
  - "M9 dependency/runtime regression: 14 passed, no warnings"
  - "M10 passive CPA, migration, API, and usage regression: 43 passed, no warnings"
  - "M11 review-fix baseline: 51 passed, no warnings"
  - "M11 database, secrets, and usage synchronization regression: 26 passed, no warnings"
  - "M11 CPA parsing and collection regression: 33 passed, no warnings"
  - "M11 administrator API regression: 8 passed, no warnings"
  - "M11 snapshots and safe logging regression: 15 passed, no warnings"
full_verification:
  - "baseline frontend build: passed"
  - "M5 strict TypeScript/Vite build: passed"
  - "M5 Playwright smoke: public navigation, admin login, CPA create, settings, usage, 390px layout passed"
  - "M6 backend full suite: 57 passed, 1 Starlette/httpx deprecation warning"
  - "M6 strict TypeScript/Vite build: passed"
  - "M7 strict TypeScript/Vite build after DTO/cache/settings changes: passed"
  - "M7 release notes rendered and UV/source package contents verified"
  - "M7 final backend suite: 69 passed, 1 Starlette/httpx deprecation warning"
  - "M7 final strict TypeScript/Vite build after cache write-back: passed"
  - "M7 Docker build: passed, sha256:b9c5f58b26f9a934df4133ecedd5612dea41a8023693a3db3a7a5ff1c6224700"
  - "M7 Playwright: settings dirty/save/failure-draft states and 390x844 layout passed"
  - "M7 final diff, secret, public-ID, SQLite, archive, browser-artifact, and generated-file scans: passed"
  - "M6 Docker build: passed, sha256:c31bc87837b404e9392b9eb096d38e65b50c2223800b44cc50ba7abc3380ebc9"
  - "M6 diff, secret, account-sample, SQLite, Playwright-artifact, and generated-file scans: passed"
  - "M8 final backend suite: 83 passed, 1 Starlette/httpx deprecation warning"
  - "M8 final strict TypeScript/Vite build: passed"
  - "M8 Playwright: CPA Pro 20x/windows rendering and edit-after-disable regression passed"
  - "M8 final Docker build: passed, sha256:6b4dce44379fb67d1b61c18245b87574f98c113e148b13ae880beeba61568e5a"
  - "M8 Uvicorn runtime smoke: health request passed with no access log or raw client IP"
  - "M8 final diff, logging-contract, secret, account-sample, SQLite, archive, browser-artifact, and generated-file scans: passed"
  - "M9 final backend suite: 83 passed, no warnings"
  - "M9 final strict TypeScript/Vite build: passed"
  - "M9 pip-audit 2.9.0: no known vulnerabilities"
  - "M9 pnpm audit, including production-only audit: no known vulnerabilities"
  - "M9 Docker build: passed, sha256:ae037ed01f24d4e1e6ed862deb1368022f085215be353d82c8e65fbef1c78c60"
  - "M9 Trivy 0.73.0 fixable MEDIUM/HIGH/CRITICAL gate: zero findings"
  - "M9 Trivy informational scan: 83 Debian findings without fixed versions (60 MEDIUM, 19 HIGH, 4 CRITICAL); application packages and uv binaries have zero findings"
  - "M9 runtime smoke: health passed, no access log/raw client IP, no startup dependency synchronization, Node, node_modules, or development packages"
  - "M9 workflow YAML, shell syntax, diff formatting, release packages, secret, SQLite, archive, browser-artifact, and generated-file scans: passed"
  - "M10 final backend suite: 94 passed, no warnings"
  - "M10 final strict TypeScript/Vite build: passed"
  - "M10 Docker build: passed, sha256:17943ef9a718138acc5100829af96fe00a06fa17ba6005491e2c920b140519ec"
  - "M10 Playwright public quota: CPA URL hidden and reset countdown derived dynamically from reset_at"
  - "M10 Playwright administrator account detail: usage tab performed local GET only and did not POST usage/sync on mount"
  - "M10 version/tag check, workflow YAML, shell syntax, diff formatting, UV/source packages, blank Secret, repository artifact, and secret scans: passed"
  - "M10 GitNexus compare review: 334 changed symbols and 113 affected flows; cumulative risk CRITICAL because the implementation spans authentication, persistence, schedulers, APIs, and frontend contracts"
  - "M11 final backend suite: 112 passed, no warnings"
  - "M11 strict TypeScript/Vite production build: passed"
  - "M11 Python compileall and git diff formatting checks: passed"
  - "M11 Docker build: passed, sha256:cd73508a629512fd2354b83ab49668b85ade13586a4661f18ab1a4908809b9ee"
  - "M11 container health smoke: passed with no Uvicorn access log or raw client IP"
  - "M11 UV/source packages: generated, extracted, version/blank-Secret/SPA contents verified, and forbidden-path scan passed"
  - "M11 final changed-file, package-content, credential-pattern, account-sample, SQLite, archive, browser-artifact, bytecode, and generated-file scans: passed"
  - "M11 staged GitNexus review: 658 changed symbols and 135 affected flows across 63 candidate files; cumulative risk CRITICAL because the complete 0.3.0 delivery spans authentication, encrypted migrations, schedulers, APIs, and frontend contracts"
blockers: []
```

This document is the source of truth for the implementation and handoff. It must
never contain administrator tokens, Fernet keys, cookies, real account identifiers,
or captured private upstream responses.

## Resume Protocol

1. Read `AGENTS.md` and this document completely.
2. Run `git status --short` and `git rev-parse HEAD`.
3. Compare the worktree with `changed_files` and the latest Handoff Log. Preserve
   unrelated user changes, including the existing untracked `AGENTS.md`.
4. Re-run the last focused test before continuing `next_action`.
5. Keep at most one milestone `in_progress`.
6. Before stopping, update the YAML status and append a Handoff Log entry with
   behavior completed, files changed, exact verification, blockers, and the next
   executable command.

## Decisions

- Anonymous users can only view `/` overview and `/quota` account quotas.
- Management, CPA channels, usage logs, and settings are in `/admin/login`,
  `/admin/accounts`, `/admin/usage`, and `/admin/settings`.
- One high-entropy `QUOTAHUB_ADMIN_TOKEN` is required; it must have at least 32
  characters and is never stored in SQLite. Missing or invalid configuration
  prevents startup.
- Login creates an opaque browser-session cookie (`HttpOnly`, `SameSite=Strict`),
  stores only its hash, and enforces a server-side 24-hour hard expiry. State-
  changing requests require a CSRF cookie and matching `X-CSRF-Token` header.
- Login failures are limited to five attempts per source IP in fifteen minutes.
- `QUOTAHUB_COOKIE_SECURE` controls the Secure cookie flag. CORS is same-origin,
  not permissive credentialed CORS.
- `QUOTAHUB_ENCRYPTION_KEY` must be a valid `Fernet.generate_key()` key. Missing,
  invalid, or unusable keys prevent startup.
- CPA management keys, OpenCode auth cookies, and Ollama session cookies use
  versioned `fernet:v1:` ciphertext. Existing plaintext values are migrated in one
  verified transaction; failure rolls the migration back.
- CPA, OpenCode, and Ollama quota pages read SQLite snapshots only. Browser refresh
  never calls an upstream quota endpoint.
- OpenCode and Ollama use service-level collection intervals. CPA uses per-channel
  intervals. Defaults are 1,800 seconds; the server minimum is 300 seconds.
- Only the newest snapshot is retained. Failed attempts retain the last successful
  value and mark it stale. Disabled sources stop collection, disappear publicly,
  and retain snapshots until deletion.
- No manual upstream refresh API exists. Create, credential change, and re-enable
  enqueue one immediate background collection.
- CPA quota collection is passive-first. Each due channel discovers accounts once,
  then requests the Manager Server header-snapshot endpoint once and uses only
  high-confidence `(auth file name, auth_index)` matches. It never assigns a
  channel-wide `items[0]` result to an account.
- Missing, stale, unsupported, or unusable passive data may fall back to the fixed
  `wham/usage` request, but each account is allowed at most one active attempt in
  twelve hours, including failed attempts. This safety interval is not exposed as
  a user setting or manual refresh action.

## Security And Persistence

- Public APIs are `/api/public/*` and `/api/health`; administrator APIs are under
  `/api/admin/*`. FastAPI dependencies enforce authorization; React guards only
  redirect unauthenticated pages.
- Session records store token hash, created/expiry/last-used timestamps. Expired
  sessions are cleaned during authentication and startup.
- Existing secret columns store ciphertext after migration. Legacy `config.json`
  values are encrypted before database insertion; operators remove the legacy file
  after successful import.
- Snapshot tables store normalized windows, success/stale flags, sanitized errors,
  timestamps, and public IDs. CPA rows are keyed by channel and a Fernet-derived
  account HMAC; raw file names and auth indexes never leave collection memory.
- CPA rows also record the quota source (`response_header` or `active_api`), the
  upstream observation time, and the most recent active-attempt time. These fields
  contain no upstream identity material.
- Database initialization and migrations are idempotent for existing SQLite files.

## Collection

- One scheduler and a global single-flight lock own all quota collection. Sources
  execute serially with fixed pacing, and a disabled source is checked before each
  account request.
- Next due time is based on the completed attempt. Failures wait the full interval.
- CPA protocol:
  1. `GET {base_url}/v0/management/auth-files` with the management Bearer token.
  2. Keep Codex entries; skip entries disabled/unavailable in CLIProxyAPI.
  3. Request
     `GET {base_url}/v0/management/monitoring/header-snapshots?days=30&limit=1000`
     once and match the latest item per account using both auth-file name and
     `auth_index`. A 404/405 means passive monitoring is unsupported, not channel
     authentication failure.
  4. Parse `response_metadata.quota`, anchoring relative reset seconds to the
     snapshot timestamp. Prefer its plan type, then fall back to auth-file ID-token
     metadata.
  5. Only when passive data is absent, stale, or invalid and the per-account
     twelve-hour guard is due, `POST {base_url}/v0/management/api-call` with fixed
     GET target `https://chatgpt.com/backend-api/wham/usage`, fixed headers, and the
     selected `auth_index`.
  6. Parse management `status_code` and JSON-string `body`.
- Parse primary/secondary windows, used percentage, reset time, reset-after seconds,
  and duration. 401/403 is authentication failure, never zero quota.
- Plans map `free -> Free`, `plus -> Plus`, `prolite/pro-lite/pro_lite/5x -> Pro 5x`,
  `pro/20x -> Pro 20x`; unknown values display `未知套餐`.
- Account display uses email, then account, then ChatGPT account ID. Email becomes
  `a***@example.com`; other identifiers retain safe edge characters. Raw identifiers
  exist only during one collection and are never persisted or returned.
- Per-account failures are isolated. Channel authentication failures stop the
  channel and preserve old snapshots.

## API Contracts

Public:

- `GET /api/public/quota`: grouped OpenCode, Ollama, and CPA snapshots.
- `GET /api/public/overview`: overview computed from snapshots.
- `GET /api/public/analytics/opencode/daily` and `/models`: local aggregates.
- Public payloads include display names, masked CPA accounts, plans, windows,
  stale/error state, and timestamps, but no internal IDs, credentials, or mutation
  controls. Old quota paths remain snapshot-only deprecated aliases for one release.

Administrator:

- `/api/admin/auth/{login,session,logout}`.
- `/api/admin/accounts/opencode/*`: CRUD, tests, cached quota, usage, sync/backfill.
- `/api/admin/accounts/ollama/*`: CRUD and cached quota.
- `/api/admin/cpa/channels/*`: multi-channel CRUD. Create requires a key; an empty
  update key preserves ciphertext. Responses never expose key, mask, or configured
  flag.
- `/api/admin/config` and `/api/admin/usage/*` are protected.
- Unauthenticated legacy management routes are removed.

## Frontend

- Public layout shows overview, quota, and a management icon.
- Admin layout shows account management, usage, settings, return-to-public, logout.
- Accounts has OpenCode, Ollama, and CPA tabs. All three list types have direct
  enabled switches; CPA accounts are grouped by channel.
- CPA cards show masked account, Free/Plus/Pro plan, quota windows, stale/error
  state, and last successful update.
- Public polling reloads cached APIs every 60 seconds and never triggers collection.

## Milestones

- **M0 Documentation/baseline:** create this file, record HEAD/worktree, run
  unchanged backend tests and frontend build.
- **M1 Security/migration:** environment validation, Fernet helpers, plaintext
  migration, session persistence, focused database/encryption tests.
- **M2 Admin boundary:** login/logout/CSRF/rate limit, protected routers, public/admin
  contract and authorization matrix.
- **M3 Snapshots:** OpenCode/Ollama snapshot tables, scheduler, cached public APIs,
  settings migration, zero-network public request tests.
- **M4 CPA backend:** channel CRUD, encrypted keys, discovery, usage parser, masking,
  plan mapping, failure isolation, and per-channel scheduling.
- **M5 Frontend:** public/admin layouts, login, protected routes, tabs, switches,
  settings, grouped CPA quota cards.
- **M6 Delivery:** README/Docker updates, full tests, frontend build, Docker build,
  diff/security scan, and final handoff.
- **M7 Review remediation and 0.3.0 delivery:** harden deployment secrets and
  release artifacts, migrate deterministic CPA fingerprints to keyed HMAC,
  invalidate sessions on administrator-token rotation, persist login throttling,
  add SQLite scheduler leases and task-failure isolation, narrow immediate quota
  triggers, replace settings autosave, migrate public caches/IDs, and deliver the
  corrected `ghcr.io/haoyang7/quotahub` 0.3.0 release inputs.
- **M8 Review fixes and operational logging:** propagate scheduler lease loss
  through multi-request collectors, correct CPA plan parsing and console bootstrap,
  make login throttling atomic, fix administrator quota/forms, centralize versioning,
  and add secret-safe application and scheduler event logs.
- **M9 Dependency and container security remediation:** patch React Router,
  PostCSS, and NanoID advisories, add Starlette's supported `httpx2` test backend,
  move build/CI to a supported Node LTS, replace the vulnerable Bookworm runtime
  base, and require clean application and final-image vulnerability scans.
- **M10 Passive CPA snapshots and final review remediation:** prefer CPA-Manager-
  Plus response-header snapshots with strict account matching, retain a fixed
  twelve-hour active fallback, add source/observation/throttle migrations, and fix
  the remaining usage lease, legacy disabled import, public CPA URL, dynamic reset
  countdown, account-detail auto-fetch, and release-version validation findings.

Only one milestone may be `in_progress`; each milestone is complete only after its
focused tests pass and this document is updated.

## Verification

- Test fresh/legacy/repeated migrations, wrong keys, cascade deletion, disabled
  snapshots, and absence of plaintext secrets.
- Test missing environment values, login throttling, session expiry/logout, cookie
  flags, CSRF, and anonymous `401/403` management responses.
- Test multi-channel discovery, plans, windows, masking, auth short-circuit,
  account isolation, stale snapshots, and scheduler single-flight behavior.
- Patch network clients to fail if invoked by public quota/overview requests.
- Run `cd backend && uv run python -m pytest -q`.
- Run `cd frontend && corepack pnpm@10.33.0 build`.
- Run `docker build .` when runtime inputs change.
- Scan final diff/database for secrets, local state, generated files, and unexpected
  lockfile changes.

## Handoff Log

### 2026-08-11 - M0 started

- Created the implementation and handoff document.
- No application code has been changed yet.
- Preserved the existing untracked `AGENTS.md`.
- Next command: run baseline backend tests and frontend build, then record HEAD and
  results in the YAML status block.

### 2026-08-11 - M0 completed

- Baseline HEAD: `fd0dd87e15df9b56d28c6d188ce7b302509fc80c`.
- Baseline frontend TypeScript/Vite build passed.
- Baseline backend result: 21 passed, 1 failed. The existing
  `test_list_all_usage_records_and_daily_stats` fixture uses the fixed date
  `2026-07-09`, which is outside its rolling 30-day query window on 2026-08-11.
  This pre-existing time-sensitive test must use a current UTC-derived date before
  final verification.
- M1 is now in progress.
- Next command: add the Fernet dependency and implement environment/secret helpers
  with focused migration tests.

### 2026-08-11 - M1 completed

- Added strict administrator-token and Fernet-key validation.
- Added randomized versioned Fernet encryption for OpenCode and Ollama credentials,
  including idempotent verified migration of legacy plaintext rows.
- Added hashed administrator session persistence and expiry cleanup.
- Updated the time-window database test to derive its fixture date from current UTC.
- Focused result: 13 passed.
- Next command: implement authentication endpoints and protect all management APIs,
  then run the authorization matrix.

### 2026-08-11 - M2 completed

- Added token login, opaque hashed sessions, browser-session cookies, CSRF checks,
  logout, expiry handling, and login throttling.
- Moved account, configuration, and all-usage management APIs under `/api/admin`;
  anonymous legacy management paths are no longer available.
- Removed permissive credentialed CORS.
- Focused result: 15 passed.
- Next command: add provider snapshot persistence and convert all public quota and
  overview routes to zero-network database reads.

### 2026-08-11 - M3 completed

- Added latest-snapshot persistence for OpenCode and Ollama, including stable
  public IDs, failure preservation, stale state, disabled-account filtering, and
  cascade deletion through account foreign keys.
- Added one serial quota scheduler with provider intervals, account pacing,
  immediate wakeups after account/config changes, and no overlapping collection.
- Converted public quota, overview, and compatibility quota routes to SQLite-only
  reads. Added public daily analytics aliases.
- Added service-level quota collection settings with a 1,800-second default and
  300-second server minimum, including legacy refresh-setting migration.
- Focused result: 5 passed. Full backend result at this point: 34 passed.
- Next command: add CPA channel/snapshot tables and the sanitized CLIProxyAPI
  collector/parser, then add authenticated CRUD and scheduler tests.

### 2026-08-11 - M4 completed

- Added multi-channel CPA persistence with encrypted management keys, per-channel
  intervals, enable/disable state, sync state, cascade deletion, and retained
  latest account snapshots.
- Added fixed CLIProxyAPI discovery and proxy-call clients, flexible sanitized
  quota parsing, plan mapping, account masking, disabled-account filtering,
  per-account failure isolation, and channel-authentication short circuiting.
- Raw account identifiers and auth indexes are collection-memory only; SQLite
  stores masked display names, random public IDs, and an internal one-way matching
  fingerprint that is never exposed by an API.
- Added authenticated/CSRF-protected CPA CRUD. Management API responses do not
  expose the key, a key mask, or a configured flag.
- Focused result: 18 passed.
- Next command: split public/admin React routing and add the CPA management tab,
  switches, grouped quota cards, and cached-only public polling.

### 2026-08-11 - M5 completed

- Public UI now contains only overview and quota pages plus a management icon.
  Public polling reads `/api/public/quota` every 60 seconds.
- Added administrator session context, login page, guarded admin layout, logout,
  account/usage/settings routes, and automatic CSRF headers on admin writes.
- Added direct enable switches for OpenCode, Ollama, and CPA; added CPA channel
  create/edit/delete forms and grouped masked account summaries.
- Added public CPA cards with plan, windows, stale/error state, and last-success
  time. Settings now control backend collection intervals rather than browser
  upstream refreshes.
- Strict TypeScript/Vite build passed. Playwright smoke covered anonymous pages,
  login, CPA creation without key disclosure, settings, usage, and a 390x844
  mobile viewport. Temporary browser artifacts and database were removed.
- Full backend result at this point: 56 passed.
- Next command: update deployment/upgrade documentation and examples, run Docker
  build plus final tests/security scans, then mark the plan complete.

### 2026-08-11 - M6 completed

- Completed deployment, environment-variable, backup, upgrade, HTTPS-cookie, and
  CPA `allow-remote` documentation in README and examples.
- Added a CPA legacy-plaintext management-key migration regression covering two
  consecutive bootstrap runs, ciphertext persistence, and successful decryption.
- Full backend verification passed: 57 tests. The only warning is the existing
  Starlette TestClient/httpx deprecation notice.
- Strict TypeScript/Vite production build passed.
- Docker build passed with image
  `sha256:c31bc87837b404e9392b9eb096d38e65b50c2223800b44cc50ba7abc3380ebc9`.
- Final diff formatting and whole-source scans found no Fernet-shaped keys, real
  CPA account samples, SQLite files, `.playwright-cli` directories, or tracked
  generated artifacts. Sanitized account fixtures use only `example.com`.
- The user's existing untracked `AGENTS.md` remains unmodified and untracked. No
  files were staged or committed.
- Known issue: the upstream Starlette/httpx deprecation warning remains; it does
  not affect the passing suite.
- Next command for review: `git status --short`.

### 2026-08-11 - README scope adjustment

- Restored the original introduction, acknowledgements, deployment comparison,
  Release/UV/source instructions, and technology-stack wording.
- Kept only the documentation required by the implemented behavior: mandatory
  administrator/encryption variables, HTTPS cookies, administrator entry point,
  CPA multi-channel configuration, low-frequency cached collection, migration
  safety, and the current public/admin API paths.
- README now differs from the baseline by 62 insertions and 16 deletions instead
  of a broad rewrite. No application code changed in this adjustment.
- Documentation diff formatting passed. No tests were rerun for this docs-only
  adjustment; the preceding M6 verification remains current.
- The user's untracked `AGENTS.md` remains untouched. No files were staged or
  committed.
- Next command for review: `git diff -- README.md`.

### 2026-08-11 - README final direction

- At the user's request, restored the newer task-oriented README because its
  administrator, encryption, CPA, collection, and upgrade guidance is more direct.
- Added [QuotaHub](https://github.com/lvmiao233/QuotaHub) to acknowledgements as
  the upstream project, while retaining the LinuxDo and opencode-cc credits.
- This entry supersedes the preceding README scope adjustment as the final chosen
  documentation direction. No application code changed.
- README diff formatting passed. Tests were not rerun for this docs-only change;
  the completed M6 verification remains current.
- No files were staged or committed, and the user's untracked `AGENTS.md` remains
  untouched.
- Next command for review: `git diff -- README.md`.

### 2026-08-11 - M7 started after review

- Reopened the completed plan after a full scheme and code review found release,
  scheduler, low-frequency collection, upgrade-cache, and security-hardening gaps.
- Locked the remediation decisions: SQLite leases for quota and usage schedulers,
  HMAC CPA fingerprints with legacy SHA compatibility, immediate session
  invalidation after administrator-token rotation, explicit settings save, version
  0.3.0, blank Secret examples, and `ghcr.io/haoyang7/quotahub` release images.
- Review verification before implementation: backend 57 passed with one existing
  Starlette/httpx deprecation warning; strict TypeScript/Vite build passed.
- Context7 documentation lookup was attempted as required but its configured
  monthly quota was exhausted; repository lockfiles and tests remain authoritative.
- No files were staged or committed. The existing untracked `AGENTS.md` remains
  untouched.
- Next command: implement focused security/database migrations and tests.

### 2026-08-11 - M7 security and migration checkpoint

- Added idempotent `security_state`, `admin_login_attempts`, and
  `scheduler_leases` tables and stable quota-snapshot backfill for legacy OpenCode
  and Ollama accounts.
- Administrator token fingerprints now use a Fernet-derived, domain-separated
  HMAC. First upgrade or token rotation transactionally revokes all administrator
  sessions; unchanged-token restarts preserve them.
- Login throttling now shares SQLite across clients and stores only a
  domain-separated source-IP HMAC. Successful login clears persisted failures.
- CPA account matching now uses `hmac:v1:` fingerprints and atomically upgrades
  legacy SHA-256 snapshot keys while preserving public IDs and quota data.
- Focused verification: 37 passed; only the existing Starlette/httpx deprecation
  warning remains.
- Next command: implement SQLite lease acquisition/renewal/release and scheduler
  fault/TOCTOU tests.

### 2026-08-11 - M7 scheduler and low-frequency checkpoint

- Added atomic SQLite lease acquisition, 30-second heartbeat renewal, 120-second
  expiry takeover, owner-checked release, and a per-process owner regenerated
  after fork. Quota collection and automatic usage synchronization use separate
  lease names plus existing in-process locks.
- Scheduler loops now isolate top-level and per-job failures and stop starting new
  requests after lease loss. Automatic usage synchronization checks each account's
  `last_sync_at + interval` instead of resynchronizing on task restart.
- OpenCode, Ollama, CPA, and usage collection reread source configuration after
  network responses. Deleted, disabled, or credential-changed sources discard old
  results and remain due.
- Account/channel routes now force immediate collection only for enabled creates,
  credential/URL/workspace changes, and re-enable transitions. Display/name
  changes retain the last-attempt timestamp; CPA interval changes only re-evaluate
  normal due time.
- Configuration writes are normalized and compared before persistence. Only real
  usage settings changes restart the usage task, and only real quota settings
  changes wake quota collection.
- Focused verification: 21 passed; only the existing Starlette/httpx deprecation
  warning remains.
- Next command: replace settings autosave and migrate public DTO/cache keys to
  `public_id`-only contracts.

### 2026-08-11 - M7 frontend and public-contract checkpoint

- Split public quota types from administrator quota responses. Public OpenCode and
  Ollama accounts require stable `public_id`; Overview now returns `public_id`
  rather than nullable internal account IDs.
- Removed public-card workspace fields, internal-ID React keys, and public-page
  navigation to administrator account details.
- Upgraded localStorage to the `quotahub:v2:cache:` namespace. First access removes
  legacy cache keys, and quota cache reads/writes rebuild data through an explicit
  field whitelist so internal IDs cannot survive in anonymous state.
- Replaced settings autosave with one explicit save action. It validates all
  numeric bounds, disables controls while saving, submits only changed quota or
  usage sections, and retains drafts after failures.
- Focused backend public/config contract verification: 15 passed. Strict
  TypeScript/Vite production build passed.
- Next command: align release workflows, package contents, examples, image owner,
  and all version declarations to 0.3.0.

### 2026-08-11 - M7 release-input checkpoint

- Aligned backend package, FastAPI, frontend package, CPA user agent, and lockfile
  project metadata to 0.3.0.
- Set README, Compose, workflow, and rendered release notes to
  `ghcr.io/haoyang7/quotahub`. The workflow now passes its resolved image address
  into the release-notes script instead of relying on a second hardcoded owner.
- Left both required Secret values blank in `.env.example`. Docker, UV, Windows,
  and source release instructions all include administrator token, Fernet key,
  and HTTPS-cookie configuration.
- Added README and `.env.example` to the UV package and `.env.example` to the
  source package. Both archives contain `frontend/dist`; packaging now excludes
  Python bytecode caches and `.DS_Store` files.
- Rendered 0.3.0 release notes successfully and generated/inspected both archives
  in temporary directories. README now distinguishes Git clone builds from
  Release archives and documents single-instance 0.3.0 migration before scale-out.
- Next command: run the complete backend suite and strict frontend build, followed
  by Docker build, browser smoke, and final secret/artifact scans.

### 2026-08-11 21:28 CST - M7 completed

- Completed the 0.3.0 review remediation across security migrations, keyed CPA
  fingerprints, persistent login throttling, cross-process scheduler leases,
  stale-result rejection, low-frequency due checks, public DTO/cache isolation,
  explicit settings saves, release inputs, packages, and deployment guidance.
- Final backend verification passed: 69 tests. The only warning is the existing
  Starlette TestClient/httpx deprecation notice.
- Final strict TypeScript/Vite build passed. Docker build passed with image
  `sha256:b9c5f58b26f9a934df4133ecedd5612dea41a8023693a3db3a7a5ff1c6224700`.
- Playwright verified that a settings change enables save, successful save disables
  it, a simulated 500 response retains the draft and retry action, and the
  390x844 layout has no horizontal overflow or overlapping controls.
- Rendered release notes use only `ghcr.io/haoyang7/quotahub:0.3.0`; UV and source
  archives contain the required README, blank-secret example, and compiled SPA.
- Final scans passed for diff formatting, secret-shaped values, non-example account
  samples, public internal IDs, SQLite files, release archives, browser state,
  bytecode, and tracked generated output. Verification processes and temporary
  directories were stopped and removed.
- No files were staged or committed. The existing untracked `AGENTS.md` remains
  unmodified and must be excluded from any later commit.
- Known issue: the upstream Starlette/httpx deprecation warning remains and does
  not affect the passing suite.
- Next command: `git status --short`.

### 2026-08-11 - M8 started after second review

- Reopened the implementation after review confirmed seven remaining defects:
  lease loss was not propagated within CPA account and usage-page loops, CPA plan
  parsing preferred the OAuth account kind, login throttling was non-atomic, the
  console entry point read an uninitialized database, administrator CPA cards did
  not render quota windows, edit forms could restore stale enabled flags, and the
  CPA user agent still reported `QuotaHub/0.3`.
- Logging audit confirmed that scheduler lease failures, collection cycles,
  per-account outcomes, authentication short circuits, discarded stale results,
  and loop recovery were silent. Uvicorn access logs do not cover these events.
- Locked the M8 log contract: CPA-style single-line text on stdout, UTC timestamps,
  fixed event names and allowlisted key/value fields, `INFO` default with
  `QUOTAHUB_LOG_LEVEL`, full keyed HMAC for login sources, and no raw credentials,
  account identifiers, upstream bodies, or free-form exception messages.
- Review baseline passed: 25 focused scheduler, authentication, CPA parser, and
  CPA collection tests; only the existing Starlette/httpx deprecation warning
  remains. The untracked `AGENTS.md` is unchanged.
- Next command: implement the centralized safe logger and focused logging tests.

### 2026-08-12 00:18 CST - M8 completed

- Completed lease-loss propagation through CPA account requests and usage pages,
  corrected CPA plan precedence, made login throttling atomic, bootstrapped the
  console entry point before reading settings, rendered administrator CPA quota
  windows, narrowed edit payloads, and centralized the 0.3.0 version.
- Added secret-safe UTC application logs for administrator actions, scheduler
  leases, actual collection cycles, per-account results, authentication short
  circuits, discarded stale results, and loop recovery. Both event names and
  fields are allowlisted; exception messages and unsupported values are never
  echoed by validation errors.
- Disabled `uvicorn.access` to prevent raw client IP logging. A real local Uvicorn
  health request produced no access-log line while startup, scheduler lifecycle,
  and shutdown logs remained available.
- Final focused verification passed: 17 logging, authentication, and scheduler
  tests. Final backend verification passed: 83 tests. The only warning is the
  existing Starlette TestClient/httpx deprecation notice.
- Strict TypeScript/Vite build passed. Docker build passed with image
  `sha256:6b4dce44379fb67d1b61c18245b87574f98c113e148b13ae880beeba61568e5a`.
  The earlier M8 Playwright run verified CPA Pro 20x/window rendering and that
  saving an already-open edit form cannot restore a concurrently disabled channel.
- Final checks passed for diff formatting, log call/event/field consistency,
  blank required Secret examples, Fernet-shaped values, non-example account data,
  SQLite/archive/browser artifacts, and tracked generated output. Temporary
  runtime data and Python bytecode caches were removed.
- No files were staged or committed. The user's existing untracked `AGENTS.md`
  remains unchanged and must be excluded from any later commit.
- Known issue: the upstream Starlette/httpx deprecation warning remains and does
  not affect the passing suite.
- Next command: `git status --short`.

### 2026-08-12 - M9 started after dependency audit

- Reopened the plan after live `pip-audit`, `pnpm audit`, and Trivy scans.
- Python application dependencies had no known vulnerability. The frontend lock
  contained one production React Router advisory plus four build-only PostCSS and
  NanoID advisories. The final Bookworm image contained 52 fixable medium-or-higher
  findings, including four critical and fourteen high findings.
- Confirmed the application uses regular browser routing rather than the affected
  experimental React Router RSC APIs, and confirmed Node/PostCSS/NanoID do not enter
  the final runtime image. Patches are still required to keep the supply chain clean.
- Selected minimal remediations: React Router 7.18.2, PostCSS 8.5.26, Node 24 LTS,
  UV Python 3.13 Trixie slim, and the Starlette-supported `httpx2` test backend.
  Live Trivy comparison reported zero fixable medium-or-higher findings for both
  the Trixie slim and Alpine UV alternatives; Trixie preserves glibc compatibility.
- Context7 lookup was attempted but its monthly quota remains exhausted. Version
  selection uses live registries, security advisories, lockfiles, and scanner data.
- No files were staged or committed. The untracked `AGENTS.md` remains untouched.
- Next command: update manifests and regenerate both lockfiles.

### 2026-08-12 20:56 CST - M9 completed

- Patched React Router to 7.18.2, PostCSS to 8.5.26, and the locked NanoID
  transitive dependency to 3.3.18. Added the Starlette-supported `httpx2` 2.10.0
  development backend; the complete backend suite now emits no deprecation
  warnings.
- Moved frontend builds and workflows to Node 24 and the runtime image from
  Bookworm to UV Python 3.13 Trixie slim. CI and Release now run pinned
  `pip-audit` and pnpm audits, then scan the actual final candidate image with
  Trivy before publication.
- Corrected the Trivy Action reference to `aquasecurity/trivy-action@v0.36.0`.
  Release builds one local candidate, scans it, and explicitly pushes only the
  version, `latest`, and source-tag aliases to `ghcr.io/haoyang7/quotahub`.
- Runtime smoke testing found that plain `uv run` after `uv sync --no-dev` could
  synchronize the default development group again at application startup. Docker,
  Unix, and Windows launchers now execute the already-synchronized virtual
  environment's Uvicorn directly, preventing startup downloads and development
  dependencies from entering a production installation.
- Final backend verification passed: 83 tests with no warnings. Strict
  TypeScript/Vite production build passed. `pip-audit 2.9.0`, full pnpm audit, and
  production-only pnpm audit reported no known dependency vulnerabilities.
- Final Docker build passed with image
  `sha256:ae037ed01f24d4e1e6ed862deb1368022f085215be353d82c8e65fbef1c78c60`.
  Trivy 0.73.0 reported zero fixable medium, high, or critical findings for Debian,
  Python packages, and the UV binaries. A separate informational scan found 83
  Debian findings without available fixed versions: 60 medium, 19 high, and four
  critical. No application-package or UV-binary findings were present.
- A fresh container returned `{"status":"ok"}` from `/api/health`, emitted no
  access-log line or raw client IP, performed no dependency download or install,
  and contained no Node, npm, pnpm, `node_modules`, `pytest`, or `httpx2` runtime
  artifacts. The temporary container was stopped and removed.
- Workflow YAML parsing, shell syntax, diff formatting, UV/source archive contents,
  blank Secret examples, Trivy secret scanning, credential-pattern scanning, and
  SQLite/archive/browser/bytecode/generated-artifact scans passed. Temporary
  release archives and Python bytecode caches were removed.
- Context7 documentation lookup was retried as required but its monthly quota is
  still exhausted; current CLI output, lockfiles, registry/audit results, scanner
  data, and executable runtime verification were used as the fallback evidence.
- No files were staged or committed. The user's existing untracked `AGENTS.md`
  remains unmodified and must be excluded from any later commit.
- Next command: `git status --short`.

### 2026-08-12 - Production-style functional acceptance

- Ran an isolated production-image acceptance environment against a sanitized
  local CLIProxyAPI-compatible mock. No real OpenCode, Ollama, CPA account, or
  credential was used.
- Administrator API checks passed for anonymous rejection, login cookies, CSRF,
  settings updates, OpenCode/Ollama CRUD and masking, two CPA channel creation,
  URL normalization, empty-key preservation, enable/disable behavior, and public
  DTO isolation.
- The two CPA channels each discovered four accounts. Free, Plus, Pro 5x, and
  Pro 20x mapping, masked identifiers, five-hour and weekly windows, reset times,
  serial pacing, and disabled-channel public hiding all rendered correctly.
- Browser acceptance passed for anonymous overview/quota pages, administrator
  redirects and login, three-provider enable switches, CPA cached windows,
  explicit settings dirty/save/persistence behavior, two usage records and the
  account filter, OpenCode cached quota details, logout, and protected-route
  redirection.
- Public refresh was confirmed snapshot-only: the mock request baseline remained
  exactly 75 requests before and after clicking refresh. At 390x844 the document
  had `scrollWidth == clientWidth == 390`, with no horizontal overflow.
- Runtime log scanning found no raw email, `auth_index`, Bearer value, Cookie or
  Set-Cookie value, raw loopback/container IP, traceback, or unexpected ERROR.
  Scheduler cycles and logout were observable. Warnings were limited to expected
  OpenCode synchronization failures caused by the intentionally fake credential.
- Final verification repeated successfully: backend `83 passed in 1.71s`; strict
  TypeScript/Vite production build passed. The isolated browser, containers,
  Docker network, temporary scripts/data, and `.playwright-cli` output were
  removed. No business code was changed during this acceptance pass.
- Limit: real upstream OpenCode and Ollama login/quota compatibility remains
  unverified because acceptance deliberately did not use real credentials.
- Next command: `git status --short`.

### 2026-08-13 - M10 started after passive-snapshot review

- Reopened the completed plan after comparing CPA-Manager-Plus monitoring storage
  with QuotaHub's active-only CPA collector. The current collector discovers every
  account and calls ChatGPT `wham/usage` on every channel interval; this is more
  frequent and riskier than necessary when Manager Server already has response-
  header quota observations.
- Locked the hybrid contract: one account-discovery request and one header-snapshot
  request per due channel, latest high-confidence file-name plus auth-index match,
  no global `items[0]` shortcut, and an unconfigurable twelve-hour per-account
  active fallback that throttles both successes and failures.
- Header snapshot 404/405 is a supported capability downgrade. Other passive
  failures preserve discovery and do not cause rapid active retries. Relative reset
  values are anchored to the upstream observation timestamp.
- Added the remaining review findings to M10: administrator usage actions must
  share the usage lease, account details must not fetch upstream on mount, legacy
  disabled flags must survive import, public CPA payloads must omit channel URLs,
  reset countdowns must advance from `reset_at`, and release tags must match all
  three application version declarations.
- GitNexus impact analysis found LOW risk for the primary symbols. CPA collection
  affects `collect_due_quotas`, `quota_sync_loop`, and lifespan; usage backfill has
  one direct administrator route consumer. No HIGH or CRITICAL impact was found.
- No business source was changed before this checkpoint. Existing uncommitted work
  and the user's untracked `AGENTS.md` remain untouched.
- Next command: add focused migration and passive CPA parser/collector tests, then
  implement the database and collection changes.

### 2026-08-14 - M10 completed

- Implemented passive-first CPA quota collection. Each due channel performs one
  account discovery and one 30-day header-snapshot request, selects only the newest
  strict auth-file-name plus `auth_index` match, and never assigns a channel's
  first item to an unrelated account.
- Added parsing for header quota windows, `window_minutes`, millisecond reset
  timestamps, observation-anchored relative resets, passive capability downgrade,
  source/observation persistence, and a fixed per-account twelve-hour active
  fallback throttle covering success, failure, and interrupted requests.
- Completed the remaining review remediations: administrator usage sync/backfill
  share the SQLite lease, account-detail mount reads local usage only, legacy
  disabled states survive import, public CPA responses omit channel URLs, quota
  countdowns derive from `reset_at`, and release tags are checked against all
  application version declarations.
- Updated README to describe the passive header-snapshot endpoint, strict account
  matching, and twelve-hour active fallback. No credentials, upstream captures,
  raw account identities, file names, or `auth_index` values were added.
- Focused regression passed: 43 tests. Final backend verification passed: 94 tests
  with no warnings. Strict TypeScript/Vite production build passed.
- Docker build passed with image
  `sha256:17943ef9a718138acc5100829af96fe00a06fa17ba6005491e2c920b140519ec`.
  Version/tag validation passed for `v0.3.0` and rejected a mismatched tag.
- Playwright verified that the public CPA URL is hidden, reset countdowns advance
  from `reset_at`, and opening the administrator usage tab issues only the local
  usage GET; it does not POST `usage/sync` until the explicit action is selected.
  The two console errors observed before login were the expected anonymous 401
  session probes.
- Generated both 0.3.0 release archives in a temporary directory and verified the
  README, blank-secret example, VERSION, and compiled SPA contents. Workflow YAML,
  shell syntax, diff formatting, repository artifact, and secret scans passed.
- Refreshed GitNexus and ran compare review against `master`: 334 changed symbols
  across 42 tracked files affect 113 flows and produce a cumulative CRITICAL risk
  classification because the full uncommitted delivery spans authentication,
  encrypted migrations, database integrity, schedulers, APIs, and public/admin UI.
  The complete test, browser, package, Docker, audit, and security evidence above
  is therefore required before any release.
- Closed the browser and Uvicorn processes, removed the local M10 image, and moved
  the temporary smoke database, seed script, packages, and browser artifacts to
  `~/.Trash/quotahub-m10-cleanup-20260814` so they remain recoverable.
- No files were staged or committed. The user's existing untracked `AGENTS.md`,
  `.claude/`, and `CLAUDE.md` remain untouched and must be excluded from any later
  commit unless the user explicitly requests otherwise.
- Next command: `git status --short && git diff --check`.

### 2026-08-14 - M11 started after second design and code review

- Reopened delivery after review found three release blockers: CPA identity was
  derived only from path-stable `auth_index`, collection validation and database
  writes were not atomic across configuration updates, and Fernet migration left
  recoverable plaintext bytes in SQLite pages.
- Additional fixes in scope are controlled API/database errors, OpenCode workspace
  invalidation after Cookie changes, an explicit passive-snapshot freshness window
  with future-clock tolerance, deterministic plan priority, and active-response
  plan propagation.
- GitNexus reports HIGH impact for `sync_usage_incremental`, `_ensure_workspace`,
  and `ensure_bootstrapped`; affected paths include automatic usage collection,
  administrator sync/backfill, lifespan startup, login, and configuration status.
  CPA collection is MEDIUM and the remaining primary symbols are LOW.
- Baseline regression passed: 51 tests covering CPA parsing/collection, secrets,
  quota API, usage synchronization, and logging. No source files were changed
  before this checkpoint; the user's untracked `AGENTS.md`, `.claude/`, and
  `CLAUDE.md` remain excluded.
- Next command: implement idempotent `collection_revision` columns and guarded
  SQLite writes, then run the focused database and synchronization tests.

### 2026-08-14 - M11 completed

- Added idempotent `collection_revision` migrations for OpenCode, Ollama, and CPA.
  Collection-related credential, workspace, URL, key, and enabled-state changes
  increment the revision; display-only changes do not force an upstream request.
- Protected usage pages, workspace caching, OpenCode/Ollama snapshots, CPA
  discovery, account snapshots, and channel completion with `BEGIN IMMEDIATE`
  conditional writes. Results are discarded when the source was deleted,
  disabled, revised, or its scheduler lease was lost while a request was running.
- Upgraded CPA account identity to a domain-separated HMAC over `auth_index` plus
  the stable account subject. Legacy SHA/HMAC identities migrate without losing
  the prior `public_id`, while replacing the account behind one `auth_index`
  creates a new public identity and cannot inherit quota or fallback throttling.
- Corrected deterministic plan precedence and propagated plans and windows from
  active usage responses. Passive monitoring remains the preferred source, with
  a six-hour freshness window, five-minute future-clock tolerance, and the fixed
  twelve-hour active fallback when no acceptable passive observation exists.
- Hardened plaintext credential migration with SQLite secure deletion, WAL
  truncation, and vacuuming after verified encrypted rewrites. Regression tests
  confirmed that database, WAL, and journal files do not retain plaintext.
- Replaced free-form CPA, database, and API exception persistence/serialization
  with fixed safe error codes. Cookie/workspace changes now invalidate cached
  OpenCode workspace resolution before the next scheduled collection.
- Focused verification passed in four groups: 26 database/secrets/usage tests,
  33 CPA parser/collector tests, eight administrator API tests, and 15 snapshot/
  logging tests. Final backend verification passed with 112 tests and no warnings;
  the strict TypeScript/Vite production build also passed.
- Docker build and container health smoke passed with image
  `sha256:cd73508a629512fd2354b83ab49668b85ade13586a4661f18ab1a4908809b9ee`.
  The health request emitted no Uvicorn access log or raw client IP. The temporary
  `quotahub:m11-review` image was removed after verification.
- Generated and extracted both 0.3.0 UV/source archives. README, blank required
  Secret values, VERSION, and compiled SPA contents were verified; forbidden path,
  credential-pattern, account-sample, SQLite, archive, browser-artifact, bytecode,
  and generated-file scans passed. Temporary packages and Python caches were moved
  recoverably to `/Users/yanghao/.Trash/quotahub-m11-final-20260814-0937`.
- GitNexus was refreshed to 1,700 symbols, 5,857 relationships, and 146 flows.
  The final staged review reported 658 changed symbols and 135 affected flows
  across 63 candidate files with cumulative `CRITICAL` risk because the full 0.3.0 delivery
  crosses authentication, encrypted migration, persistence, schedulers, API
  contracts, and both public and administrator UIs. High-risk collection paths are
  covered by revision/lease boundary tests and the complete regression suite.
- No files were staged or committed. The user's existing untracked `AGENTS.md`,
  `CLAUDE.md`, and `.claude/` remain untouched and must be excluded from a future
  commit unless the user explicitly requests otherwise.
- Next command: `git status --short && git diff --check`.

### 2026-08-14 - 0.3.0 release candidate prepared

- Created local candidate branch `codex/release-0.3.0` from
  `fd0dd87e15df9b56d28c6d188ce7b302509fc80c`.
- Consolidated the completed M1-M11 implementation, tests, release workflows,
  documentation, and packaging changes into the candidate commit. The commit
  author is `yanghao <haoyoung7@gmail.com>`.
- Kept the user's local `AGENTS.md`, `CLAUDE.md`, and `.claude/` files outside the
  candidate commit. No database, credential, release archive, browser artifact,
  Python cache, or generated local state is included.
- Final staged GitNexus review covered all 63 candidate files and reported 658
  changed symbols, 135 affected flows, and cumulative `CRITICAL` scope risk. This
  is the expected full-release classification and is backed by the M11 focused,
  complete, browser, package, container, migration, and security verification.
- The exact candidate SHA is intentionally obtained from `git rev-parse HEAD`
  after checkout; embedding a commit's own SHA in its tracked contents is not
  self-consistent.
- Next command: `git push -u origin codex/release-0.3.0`, then create a Pull
  Request to `master` and wait for the `test`, `frontend`, and `container` jobs.
