# Truestill architecture excellence audit - 2026

> **Status:** Advisory research record, written 2026-08-02. No implementation is authorized by
> this document. Every recommendation below requires its own ruling, measured design pass and
> verification at the repository's normal gate level.

## 1. Executive conclusion

Truestill's fundamental architecture is already appropriate for the product:

- `truestill-core` owns domain behaviour, persistence, filesystem operations and recovery.
- `truestill-cli` and `truestill-app` are two adapters over the same core rather than separate
  implementations.
- SQLite provides a local, offline catalog without introducing a server.
- Filesystem mutation is dry-run-first, explicit, journalled where necessary and biased toward
  preserving the source.
- Dependencies are deliberately few and justified by capabilities missing from the standard
  library.

The path from strong to excellent is therefore **production hardening**, not a framework rewrite.
FastAPI, Pydantic, SQLAlchemy, React, Electron, PostgreSQL, Redis and a dependency-injection
framework do not solve a demonstrated architectural problem here. Adding them now would enlarge the
runtime, packaging and security surfaces while obscuring contracts the current code expresses
directly.

The most important architectural gap found in this review is **cross-process operation
coordination**. The app serializes jobs per drive inside one process, but a CLI process, a second app
process or a second CLI terminal can still operate on the same catalog or drive concurrently.

Recommended priority:

1. Cross-process operation coordination.
2. Explicit SQLite transaction, timeout, integrity, backup and recovery policy.
3. Clean resource lifecycle: no unclosed database or socket warnings.
4. Process isolation for untrusted native media decoding.
5. Release SBOMs, provenance attestations and installed-artifact verification.
6. Property-based testing of path, migration and recovery invariants.
7. Evidence-led decomposition of the largest orchestration modules.
8. Python 3.14 experiments only after compatibility and performance measurement.

## 2. Scope and evidence

This assessment compared the current repository against the official Python, SQLite, Python
Packaging, PyPI, GitHub Actions, SLSA and relevant library documentation available on 2026-08-02.
Primary sources were preferred over opinion posts because the questions involve transaction
semantics, concurrency, build provenance and platform behaviour.

Repository evidence inspected includes:

- `packages/truestill-core/src/truestill_core/`
- `packages/truestill-cli/src/truestill_cli/`
- `packages/truestill-app/src/truestill_app/`
- the three package test suites and `tests/e2e/`
- `pyproject.toml`, `uv.lock`, `Makefile` and `.github/workflows/`
- `PROJECT_STATUS.md`, `ENGINEERING_STANDARD.md`, `IMPLEMENTATION_STANDARDS.md`,
  `DECISIONS.md`, `BACKLOG.md` and `PERFORMANCE.md`

Verification at review time:

```text
ruff check:                 passed
ruff format --check:        299 files already formatted
mypy strict:                no issues in 83 source files
pytest:                     1,246 passed, 1 skipped
pytest warnings:            17 ResourceWarnings
browser E2E:                not run in this review
```

The warnings named unclosed SQLite connections and test-server sockets. They do not establish a
production leak by themselves, but they are useful evidence that ownership is not uniformly explicit
in every test and failure path.

## 3. What is already architecturally strong

### 3.1 Package and dependency boundaries

The three-package workspace is the correct scale. Core remains usable without Starlette or Uvicorn;
the CLI adds no runtime dependency; and the UI is an adapter rather than a parallel domain layer.
Tests enforce the app-to-core boundary.

The use of standard-library dataclasses, protocols, `pathlib`, `sqlite3`, hashing and concurrency is
well matched to a local desktop application. There is no remote, multi-tenant validation boundary
that would justify Pydantic models or a larger web framework.

### 3.2 Data-safety ordering

The organizer's write path follows a strong order:

```text
resolve and plan
-> preflight destination
-> write or relocate bytes
-> record the organized copy
-> journal a relocation or verify before deleting the source
```

The source hash remains the deduplication identity. A metadata-modified organized copy has its own
post-write hash for later verification. This avoids both major mistakes: verifying modified bytes
against the source and blessing a corrupted copy by recording a hash calculated from that same
corrupted copy as the expected source truth.

### 3.3 Failure honesty and recovery

Unreadable, skipped, duplicate, failed and unverifiable outcomes are modelled and presented rather
than being folded into success. Layout migration, reclaim and in-place organization have dedicated
journals and recovery semantics. Drive identity is UUID-based instead of relying on mutable mount
paths.

### 3.4 Localhost security

The local web application combines:

- a per-session random token;
- loopback-only binding;
- `Host` validation;
- `Origin` validation;
- no authentication cookie that a cross-site request can automatically carry.

That is a proportionate defence against localhost request forgery and DNS rebinding for this product.
Replacing Starlette with FastAPI would not strengthen it.

### 3.5 Performance discipline

The repository measures before optimizing. Metadata extraction is the dominant preview cost, not
SHA-256. Metadata and hash caches address repeated work. Perceptual comparison remains linear because
the measured scale has not justified an index. HEIF decode cost and immediate copy re-verification
have documented measurements and tradeoffs.

This is the correct optimization posture. No general performance rewrite is recommended.

## 4. Priority 1 - cross-process operation coordination

### 4.1 Current gap

`truestill_app.jobs.JobManager` provides one-operation-per-drive protection, but documents that its
lock is process-local and in-memory. It protects concurrent requests inside one running app only.

The following combinations remain possible:

- two `truestill-app` processes;
- `truestill-app` and `truestill` CLI;
- two CLI terminals;
- an older packaged process and a newly launched process.

SQLite serializes database writes, but it cannot make the complete filesystem operation atomic:

```text
inspect filesystem
-> calculate plan
-> copy or move files
-> update catalog
-> update operation journal
```

Two processes can derive plans from the same initial state and then interleave filesystem and catalog
changes. Existing collision checks and journals limit damage, but they are not a substitute for one
authoritative operation owner.

### 4.2 Recommended design

Introduce a core-level `OperationCoordinator` used by both front ends.

An operation should acquire, in deterministic order:

- the catalog lock;
- every participating marked drive, keyed by drive UUID;
- every participating unmarked destination, keyed by normalized/resolved path.

Required properties:

- acquisition is all-or-nothing;
- locks release automatically after process termination;
- a contention refusal identifies the resource and, where available, the operation holding it;
- lock ordering prevents deadlock for two-drive operations such as backup;
- preview locking is decided explicitly: a preview may need a shared/read lock because a concurrent
  apply can invalidate the plan while it is being calculated;
- unsupported or demonstrably unreliable filesystems fail visibly rather than pretending to lock;
- the app's in-memory guard remains as fast UI feedback, while the core lock is authoritative.

The design must decide where the rendezvous object lives without violating the current rule that the
drive marker is the only Truestill-named artifact written to a user's drive. Options include locking a
known byte/descriptor of an existing local control file or keeping lock rendezvous files in the local
application data directory keyed by drive UUID. A local-only rendezvous cannot coordinate two
different machines writing the same removable/network drive, so that limitation must be explicit.

### 4.3 Candidate library

[`filelock`](https://py-filelock.readthedocs.io/en/stable/index.html) is the strongest candidate found
for evaluation. Its current documentation describes native `LockFileEx` locking on Windows,
`fcntl.flock` on Unix/macOS and automatic release after process termination. Its
[`concepts`](https://py-filelock.readthedocs.io/en/stable/concepts.html) documentation also states
that native locks are local-machine locks and that shared/network filesystem behaviour must be
verified for the actual filesystem.

[`portalocker`](https://portalocker.readthedocs.io/) is a credible alternative, but its public
documentation emphasizes that Unix locks are advisory and that networked filesystems may require
additional flush/sync care.

No dependency should be selected on API appearance alone. The design pass must test the candidate on
the filesystems Truestill actually supports: NTFS, ext4/APFS as applicable, exFAT/FAT32 and the real
cloud/FUSE mounts used during soak.

## 5. Priority 2 - explicit SQLite operational policy

### 5.1 Current state

The catalog correctly enables foreign-key enforcement and uses `PRAGMA user_version` for ordered
schema migrations. It has explicit close/context-manager support. The review did not find a single
documented operational policy covering:

- transaction mode/autocommit;
- lock wait/busy timeout;
- journal mode;
- synchronous durability;
- integrity checks;
- catalog backup and user-facing recovery.

Python's SQLite API currently defaults to legacy transaction control, and the documentation says the
default will change in a future Python release. Therefore, implicit behaviour is a future migration
risk. Python 3.13 also emits `ResourceWarning` if a connection reaches destruction without an
explicit `close()`.

Source: [Python 3.13 `sqlite3` documentation](https://docs.python.org/3.13/library/sqlite3.html).

### 5.2 Recommended policy

Decide and test, rather than inherit, each of the following:

1. Set `autocommit` or `isolation_level` explicitly.
2. Set a measured busy timeout so a brief competing reader/writer does not become an arbitrary
   five-second failure.
3. Define the transaction boundary for every multi-row domain mutation.
4. Acquire an immediate/exclusive-enough transaction for schema migration before inspecting and
   changing the version.
5. Create a pre-migration catalog backup through SQLite's backup API.
6. Run `PRAGMA foreign_key_check` after migration.
7. Run `PRAGMA quick_check` after an unclean shutdown, before high-risk migration and as part of a
   user-invoked catalog diagnostic.
8. Provide a supported recovery command and clear message rather than requiring manual SQLite work.
9. Make every catalog and cache connection owner explicit and remove the current resource warnings.

### 5.3 WAL is a measurement, not a default recommendation

Write-ahead logging could improve read/write concurrency between the app and background operations,
but it changes durability and filesystem assumptions. It should not be enabled merely because it is
common advice.

Before adopting WAL, measure and failure-test:

- normal local catalog performance;
- app reads during a long writer transaction;
- power/process interruption;
- backup correctness with WAL and shared-memory side files;
- antivirus interaction on Windows;
- the guarantee that the catalog remains on a local filesystem.

The outcome may be WAL, rollback journal or no change. The architectural improvement is an explicit,
tested policy.

### 5.4 Do not add an ORM

SQLAlchemy, SQLModel or another ORM would not provide the operational guarantees above. The catalog's
queries, migrations and invariants are domain-specific and already visible. An ORM would add a large
dependency and a second transaction model without removing SQLite-specific responsibilities.

## 6. Priority 3 - resource lifecycle

The ordinary test suite completed with 17 `ResourceWarning`s, including unclosed SQLite connections
and sockets in test or failure paths. The configured exemption is deliberate because garbage
collection timing can make these warnings intermittent, but repeated warnings still conceal useful
ownership evidence.

Recommended approach:

- trace every warning to its allocation with `tracemalloc` enabled;
- distinguish production-object leaks from deliberately incomplete test doubles;
- close real connections/sockets at the owner boundary;
- give test doubles a deterministic `close()`/context-manager lifecycle;
- retain the narrow warning policy only for cases that genuinely cannot be deterministic;
- add a focused zero-resource-warning lane once the suite is clean, rather than immediately making
  the whole suite flaky.

This matters especially on Windows, where open files commonly block replacement and deletion, and in
a desktop process expected to remain open for hours.

## 7. Priority 4 - isolate native media decoding

ExifTool already runs out of process, limiting the main interpreter's exposure to malformed metadata.
Perceptual hashing, Pillow and `pillow-heif` native decoders still process untrusted media inside a
worker context that may share the main process depending on the selected pool.

A stronger boundary is a dedicated decode/hash worker process with:

- no catalog connection;
- no drive mutation capability;
- a minimal environment;
- per-file time and memory limits where the platform permits;
- structured request/result values;
- cancellation and forced termination;
- a named per-file `unreadable`/`decoder-crashed` outcome;
- worker recycling so one decoder leak does not grow for the whole library;
- tests using malformed and oversized fixtures.

Process isolation remains useful even if Python's future free-threaded runtime improves raw
parallelism: this boundary is primarily about containing native decoder crashes and memory faults.

## 8. Priority 5 - release provenance and SBOM

The source dependency process is stronger than the future binary-release process currently described.
Installers will bundle the Python runtime, ExifTool and native decoder libraries that a Python-only
advisory scan cannot fully see.

GitHub Actions supports cryptographically signed artifact attestations for binaries and associated
SBOM attestations. The attestation records the repository, commit, workflow and triggering event and
can be verified with GitHub's tooling.

Source: [GitHub artifact attestation documentation](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations).

PyPI implements PEP 740 digital attestations tied to Trusted Publishing and can carry SLSA
provenance.

Sources:

- [PyPI digital attestations](https://docs.pypi.org/attestations/)
- [SLSA provenance](https://slsa.dev/spec/v1.2/)

Recommended release flow:

```text
protected tag
-> clean locked build on the target OS
-> test the installed/frozen artifact, not only the source checkout
-> inventory Python and bundled native dependencies
-> generate an SBOM
-> calculate release hashes
-> generate build and SBOM attestations
-> publish through OIDC/Trusted Publishing
-> download and verify the published artifact
-> retain provenance with the release
```

The SBOM must name bundled native libraries such as libheif/libde265/x265 where present; exporting
Python distributions alone repeats the blind spot already documented in the repository.

## 9. Priority 6 - property-based invariant testing

The example-based suite is extensive. Property-based testing would add the most value at boundaries
where the input space is combinatorial and the rule is already expressible as an invariant.

Candidate properties:

- a generated source name can never escape its destination root;
- path sanitization is idempotent;
- a collision never overwrites unrelated content;
- organizing an already organized path does not stack date prefixes;
- layout rendering and migration routing agree for the same effective scheme;
- migration plus undo returns every completed move to its original relative path;
- cancellation at any item boundary leaves a resumable journal;
- source and copy hashes retain their distinct meanings across metadata baking;
- every resolution belongs to exactly one report tally bucket;
- a date resolver never consults filesystem mtime;
- lock acquisition order cannot deadlock for any pair of resources.

[`Hypothesis`](https://hypothesis.readthedocs.io/) is the natural Python candidate, but it should be a
development-only dependency and introduced for a small number of high-value invariants first. A
coverage-number exercise or mass conversion of existing tests is not recommended.

## 10. Priority 7 - decompose only at real change boundaries

The largest production units are expensive to review:

| Module | Approximate size at review |
|---|---:|
| `truestill_cli/cli.py` | 2,182 lines |
| `truestill_core/catalog.py` | 1,894 lines |
| `truestill_core/organizer.py` | 1,337 lines |
| `truestill_core/layout.py` | 966 lines |
| `truestill_app/service/organize.py` | 826 lines |
| `truestill_app/server.py` | 684 lines |

Size alone is not a defect. These modules contain cohesive orchestration and have strong tests.
Decomposition should happen when a concrete change exposes an ownership boundary, not as a repository
wide cleanup.

A plausible direction, not a prescribed tree:

```text
truestill_core/
├── organize/
│   ├── plan.py
│   ├── execute.py
│   └── recovery.py
├── catalog/
│   ├── schema.py
│   ├── custody.py
│   ├── migrations.py
│   └── dates.py
└── coordination/
    └── operation_lock.py
```

The rule for a split should be: a responsibility has its own invariant, changes for its own reasons,
and can expose a narrow typed interface. A target line count is not a sufficient reason.

### 10.1 Selective side-effect protocols

`Destination` is a useful existing seam. Similar narrow protocols may earn their place for:

- time/clock generation;
- ExifTool execution;
- process launching;
- operation coordination;
- catalog backup;
- filesystem capability probing.

Do not abstract `Path`, every SQLite query, every helper or every model. Explicit arguments and small
protocols are sufficient; a dependency-injection container is not needed.

## 11. Python 3.14 and free-threading ruling

Python 3.14 adds `concurrent.interpreters` and `InterpreterPoolExecutor`, enabling multi-core work in
isolated interpreters. The official documentation also lists current limitations: interpreter startup
is not fully optimized, memory sharing is limited, the programming model is unfamiliar and many
third-party extension modules are not yet compatible.

Sources:

- [What's new in Python 3.14](https://docs.python.org/3.14/whatsnew/3.14.html)
- [Python free-threading guidance](https://docs.python.org/3/howto/free-threading-python.html)

Current recommendation:

> ⚠ **CORRECTION, 2026-08-22: THE FIRST TWO ITEMS ARE SPENT, AND THEY READ AS STANDING ADVICE.**
> The floor is `>=3.14` and the experimental lane was added, run green on all three platforms, and
> then replaced outright - `DECISIONS.md` **D13**. The list is left as written because this is a
> record of an audit, and because its own condition is what was met: the lane went in when the
> wheels and packaging tools were ready, which is what the second item asked for. The remaining
> items are unaffected. ⚠ This audit is advisory and **no implementation was authorised**; that
> has not changed either.

- keep Python `>=3.13` as the shipping floor;
- add an experimental Python 3.14 CI lane only when the dependency wheels and packaging tools are
  ready;
- measure the real metadata/hash pipeline before changing executors;
- verify Pillow, `pillow-heif`, NumPy and imagehash under the selected runtime;
- do not adopt free-threaded Python merely because it is newer;
- retain process isolation where it provides a security or crash-containment boundary.

Truestill's dominant work includes filesystem I/O, ExifTool subprocesses and native image decoding.
Those paths do not automatically become faster by removing the GIL.

## 12. Library rulings

| Library or technology | Ruling | Reason |
|---|---|---|
| `filelock` | **Evaluate** | Directly addresses the cross-process coordination gap; must be proven on supported filesystems. |
| `portalocker` | **Alternative to evaluate** | Credible cross-platform locking API; same filesystem caveats apply. |
| Hypothesis | **Evaluate as dev-only** | High value for path, migration, cancellation and accounting invariants. |
| GitHub artifact attestations | **Adopt for releases** | Verifiable provenance for installers and other binaries. |
| SBOM generator | **Select during packaging design** | Must inventory bundled native libraries, not only Python distributions. |
| PyPI Trusted Publishing/PEP 740 | **Adopt when publishing** | Removes long-lived upload credentials and produces verifiable publication attestations. |
| SQLAlchemy/SQLModel | **Do not add** | Does not solve durability, locking, backup or recovery; obscures deliberate SQL. |
| APSW | **Do not add yet** | Stdlib SQLite meets current needs; no measured missing capability. |
| FastAPI/Pydantic | **Do not add** | No remote multi-tenant schema boundary; Starlette plus typed internal values is sufficient. |
| React/Vue/Svelte | **Do not add now** | Current UI does not justify an npm/build/runtime ecosystem. |
| Electron/Tauri | **Do not add for architecture alone** | Installer/distribution work should choose a shell only from product requirements and measurements. |
| Redis/message broker | **Do not add** | Wrong scale, adds a service and conflicts with local-first operation. |
| Dependency-injection framework | **Do not add** | Explicit construction and narrow protocols are enough. |
| Python 3.14 subinterpreters | **Experiment only** | Extension compatibility and measured benefit are not established. |
| Free-threaded CPython | **Do not ship yet** | Native dependency readiness and performance benefit are unproven. |

## 13. What “best architecture” means here

There is no universal best architecture independent of a product's constraints. For Truestill, an
excellent architecture is one that:

- keeps photos and catalog data local;
- preserves source data by default;
- makes destructive exceptions explicit and verifiable;
- survives cancellation, process death and removable-drive behaviour;
- provides one domain implementation to both front ends;
- remains installable for a non-developer;
- can explain every degraded outcome;
- minimizes dependencies that process untrusted files;
- measures performance before adding complexity;
- produces release artifacts whose origin and contents are verifiable.

The repository already satisfies much of that definition. Its next architectural gains come from
closing coordination, recovery, isolation and release-integrity gaps - not from replacing its core
technology choices.

## 14. Proposed staged research order

This document does not authorize implementation. If the recommendations are accepted, investigate
them independently in this order:

1. **Coordination research:** enumerate every CLI/app write operation and resource set; reproduce a
   two-process conflict; test candidate locks on supported filesystems.
2. **SQLite policy research:** measure lock contention and transaction duration; inject crashes;
   compare journal policies; design backup/recovery UX.
3. **Resource lifecycle pass:** trace every current warning and classify production versus test-only
   ownership.
4. **Decoder isolation research:** measure worker startup/memory cost and prove malformed-file crash,
   timeout and cancellation handling.
5. **Release security design:** select installer output, SBOM format, attestation mechanism and
   installed-artifact verification.
6. **Property-test pilot:** implement only two or three high-risk invariants and assess signal,
   runtime and maintainability before expanding.
7. **Python 3.14 experiment:** run the existing gates and real performance profile without changing
   the shipping floor.

Each stage should leave a dated measurement and a ruling. None should silently become a dependency or
architecture migration merely because the experiment succeeded.
