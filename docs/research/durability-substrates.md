# Embedded transactional stores for the durability substrate

Research note for [tapir-dev/tp#6](https://github.com/tapir-dev/tp/issues/6).
Status: **survey only — no recommendation**. Picking one is a separate ticket.

Date of survey: 2026-09-07. Version numbers and maintenance signals age fast;
re-check before the decision ticket acts on them.

## What the substrate has to do

Requirements extracted from the durability chapter of the product brief, restated
as testable properties. These are the columns every candidate is scored against.

| # | Requirement | Why it constrains the choice |
|---|---|---|
| R1 | **Multi-key atomic commit.** A settlement record and the next operation state must land in one transaction, all-or-nothing. | Rules out any store whose unit of atomicity is a single key or a single append. |
| R2 | **Atomic cross-scope delete + insert.** The whole streaming-frame list must be deleted in the same transaction that inserts the final message, on *every* terminal path (success, error, cancel, crash-resume). | Needs a transaction that spans a range delete and a point insert. |
| R3 | **Ordered keys with prefix enumeration and prefix delete.** Terminal cleanup deletes exactly the address prefixes an operation owns, reached through named prefix constructors. | Needs lexicographic byte ordering and a range/prefix scan; a native range-delete is a bonus. |
| R4 | **Two separable durable scopes.** Permanent append-only history vs. a wholesale-droppable ephemeral sidecar, separated so a transaction cannot accidentally mix them. | Needs multiple named tables/partitions/trees, ideally openable under distinct Rust types. |
| R5 | **No fsync on the token path.** Streaming frames are written continuously during generation and must never await disk I/O; only the settlement commit needs to be durable. | Needs a *tunable* durability level per commit, or a store cheap enough that a frame write never blocks. |
| R6 | **Identical restart point after clean close and after `SIGKILL`.** | Needs a crash-safety story the project itself documents and tests, not one inferred from architecture. |
| R7 | **Bounded recovery cost.** Restore reads a small fixed control projection; cost must not scale with session size. | Needs cheap point reads on open — no full-log replay, no unbounded startup scan. |
| R8 | **Coexistence with a separate append-only JSONL history.** The session transcript stays JSONL on disk (own brief requirement); the store backs the control plane beside it. | The store must not force a second synchronous flush per turn, and must tolerate being one of two writers to the same session directory. |

Two distribution constraints from outside the durability chapter, which the
decision ticket will weigh even though the survey question does not ask for them:

- **Single static binary.** A C dependency is not disqualifying, but it costs
  cross-compilation and musl friction that a pure-Rust crate does not.
- **`rusqlite` is already a sanctioned dependency** in the brief's dependency
  policy, named as the escape hatch for session search once scanning stops
  scaling. If SQLite arrives anyway, a second embedded store is a second
  storage engine to operate, and that is an argument the decision ticket owns.

## How to read the verdicts

Every claim below is marked **[V]** verified against the primary source cited
inline, or **[I]** inferred — a reasonable reading of the documented design that
the project does not state in those words. Inferences are load-bearing exactly
where the projects are silent, which is itself a finding.

---

## Comparison matrix

Scored against R1–R8 above. "Yes" means the project documents it; see the
per-store sections for the citation and for what had to be inferred.

| | redb | fjall | sled | heed / LMDB | rusqlite / SQLite |
|---|---|---|---|---|---|
| Latest release | 4.2.0 (2026-08-17) | 3.1.10 (2026-08-30) | **0.34.7 (2021-09-12)** stable; 1.0.0-alpha.124 (2024-10-11) | heed 0.22.1 (2026-04-07) | 0.40.2 (2026-08-08) |
| Licence (SPDX) | MIT OR Apache-2.0 | MIT OR Apache-2.0 | MIT OR Apache-2.0 | heed MIT; `lmdb-master-sys` Apache-2.0; **LMDB C = OpenLDAP Public License 2.8** | rusqlite MIT; SQLite public domain |
| Engine | Copy-on-write B+tree, no WAL | LSM-tree, memtable + journal WAL | Log-structured (0.34.x); rewrite in flight | Copy-on-write B+tree, mmap, no WAL | B-tree + rollback journal or WAL |
| R1 multi-key atomic commit | Yes, `WriteTransaction` | Yes, `SingleWriterWriteTx` / `OptimisticWriteTx` | Yes, `Tree::transaction` | Yes, `RwTxn` | Yes, `Transaction` |
| R2 atomic delete-range + insert | Yes, in one txn (scan-based delete) | Yes, in one txn (scan-based delete) | Yes, in one txn (scan-based delete) | Yes, `delete_range` (cursor loop) or native `clear`/`mdb_drop` | Yes, single `DELETE ... WHERE k >= ? AND k < ?` |
| R3 native prefix delete | **No** — `retain_in(range, pred)` | **No** — `prefix()` + `remove()` | **No** — `scan_prefix` + `remove` | Partial — `delete_range` is a cursor loop; **whole-DBI `clear()` is native `mdb_drop`** | **Yes** — one indexed range `DELETE` |
| R3 prefix scan API | `range(RangeBounds)`, no `prefix()` helper | `prefix()`, `range()`, `DoubleEndedIterator` | `scan_prefix()`, `range()` | `prefix_iter()`, `rev_prefix_iter()`, `range()` | index range scan; `LIKE 'p%'` only under strict collation preconditions |
| R4 separate scopes | Multiple tables, typed `TableDefinition` | Multiple keyspaces (own LSM tree each) | Multiple `Tree`s | Multiple named DBIs, typed by codec | Multiple tables |
| Isolation | Serializable (MVCC), stated in design doc | Serializable in tx modes; plain MVCC snapshot otherwise | "Fully serializable (ACID)" | Serializable snapshot (MVCC readers, single writer) | Serializable; **snapshot isolation in WAL mode** |
| Writers | Single, `begin_write` blocks | Single-writer *or* optimistic multi-writer with manual retry | Single logical writer, auto-retry on conflict | Single writer, enforced by LMDB | Single writer (`SQLITE_BUSY` otherwise) |
| R5 defer fsync | Yes — `Durability::None` | **Yes, by default** — `PersistMode::Buffer` | Yes — background flusher, `flush_every_ms: 500` | Yes — `MDB_NOSYNC` / `NOMETASYNC` / `MAPASYNC` (each with a stated corruption or loss risk) | Yes — WAL + `synchronous=NORMAL` |
| R6 documented crash story | XXH3-128 Merkle checksums, 1PC+C / 2PC | Journal + `persist()` on drop | `flush()` only guarantee; ≤500ms at risk by default | COW pages, "no special recovery procedure" | Most explicit of the five: dedicated crash-simulation harnesses |
| Multi-process | Not by default (`experimental-multiprocess`, unstable) | **Never** — `LOCK` file, `Error::Locked` | Not supported | **Yes** (LMDB); heed caps at one `Env` per process | Yes, same host; WAL needs shared memory |
| Background threads | None | Yes, worker pool (≤4 default) | Yes, one flusher thread | None | None (checkpoint runs on the committing thread) |
| Async API | No | No (ships a `spawn_blocking` example) | `flush_async()` only | No | No; `Connection` is `Send` but **not `Sync`** |
| Pure Rust | Yes | Yes | Yes | **No** — vendors LMDB C, compiled via `cc` | **No** — `bundled` compiles 269,649 lines of C |
| Transitive deps | **0** | ~42 | 13 | ~30 (default features) | `libsqlite3-sys` + C build |
| Maintainer concentration | cberner, 1569 of ~1600 commits | marvin-j97, 1933 commits | single author, rewrite unreleased | Meilisearch team | gwenn / thomcc |

---

## redb

Sources: [repo](https://github.com/cberner/redb), [design doc](https://github.com/cberner/redb/blob/master/docs/design.md),
[CHANGELOG](https://github.com/cberner/redb/blob/master/CHANGELOG.md), [docs.rs](https://docs.rs/redb/latest/redb/),
[crates.io](https://crates.io/crates/redb).

**Maturity.** [V] 4.2.0 released 2026-08-17; roughly monthly cadence with one
~4-month gap (Apr–Aug 2026). The README's self-declaration is **"Stable and
maintained"** with a committed file-format stability promise — no "beta"
language anywhere, which distinguishes it sharply from sled. [V] Only 5 open
issues. [V] Licence `MIT OR Apache-2.0`. [V] Bus-factor one: cberner holds 1569
of roughly 1600 commits.

**Transactions.** [V] `WriteTransaction` / `ReadTransaction`. Writers are
serialized by blocking, not by conflict-abort — `begin_write` doc: *"Only a
single write may be in progress at a time. If a write is in progress, this
function will block until it completes."* [V] The design doc states the
isolation level outright: *"redb uses MVCC to provide isolation, and provides a
single isolation level: serializable, in which all writes are applied
sequentially."* That is the clearest isolation claim of any candidate here.
[V] One `WriteTransaction` can `open_table()` several tables and commit them
together — R1 and R4 are satisfied with typed `TableDefinition` handles, which
maps unusually directly onto the brief's "separate durable scopes at the type
level". [V] `abort()` is explicit and `Drop` auto-aborts, except when the thread
is panicking, where pages are conservatively leaked rather than risk corrupting
committed data.

**Keys and prefixes.** [V] `Key` requires a `compare` giving a total order;
byte and string keys sort lexicographically. [V] `Table::range(impl RangeBounds)`
returns a double-ended iterator. [V] There is **no `prefix()` helper** — a prefix
scan is a hand-built `Range` over the key encoding. [V] No native prefix delete;
the built-ins are `retain(predicate)` and `retain_in(range, predicate)`, i.e.
scan-and-delete inside the transaction, O(range) with copy-on-write page churn
per removal.

**Crash safety and fsync.** [V] COW B+trees with no separate WAL; the tree is
the log, via double-buffered commit slots. [V] Commit strategies are 1PC+C
(write data and checksums, flip the primary bit, one fsync) and 2PC (write a new
tree copy, fsync, flip, fsync again). [V] All pages carry **XXH3-128** checksums
in a Merkle arrangement, so a partially-committed transaction is detected and
rolled back after a crash. [V] **Correction worth carrying into the decision
ticket:** the `Durability` enum today has exactly **two** variants, `None` and
`Immediate` — the `Eventual` variant that older material refers to no longer
exists. [I] Fuzzing appears to exist (a `fuzz/` directory is in the repo) but no
published crash-test statement was found; the crash story rests on the checksum
design rather than on a documented power-loss test suite.

**Shape.** [V] Single file. [V] No background threads — page reclamation is
synchronous with commit and epoch tracking. [V] Multi-process is **not** supported
by default; the `experimental-multiprocess` feature uses byte-range file locks
and is marked *"May change incompatibly, or be removed, in any release"*
(open issue [#678](https://github.com/cberner/redb/issues/678) tracks this).

**Coexistence (R5/R8).** [V] `Durability::None` commits without fsync, and a
later `Durability::Immediate` commit flushes everything pending — a clean fit
for "frames cheap, settlement durable". [V] No async API. [I] Must be driven from
a blocking thread under tokio; redb's own docs do not address this.

**Footprint.** [V] **Zero mandatory transitive dependencies** — `cargo tree` on
redb 4.2.0 resolves to redb alone. [V] Pure Rust, README's first line. [V]
`no_std` support exists behind feature gates.

---

## fjall

Sources: [repo](https://github.com/fjall-rs/fjall), [CHANGELOG](https://github.com/fjall-rs/fjall/blob/main/CHANGELOG.md),
[docs.rs](https://docs.rs/fjall/latest/fjall/), [crates.io](https://crates.io/crates/fjall).

**Maturity.** [V] 3.1.10 released 2026-08-30, roughly biweekly cadence. [V] No
explicit production-ready or beta self-declaration; instead the README commits
to a stable disk format — *"Future breaking changes will result in a major
version bump and a migration path"*. [V] **Recent churn is a real risk signal:**
3.0.0 renamed `keyspace→database` and `partition→keyspace`, a breaking vocabulary
swap that makes older documentation and any code written against it actively
misleading. [V] 29 open issues. [V] `MIT OR Apache-2.0`. [V] Bus-factor one:
marvin-j97, 1933 commits.

**Transactions.** [V] Two opt-in transactional modes. `SingleWriterTxDatabase`
serializes writers — README: *"This is trivially serializable because it
literally serializes write transactions."* `OptimisticTxDatabase` allows multiple
writers with OCC, and **the caller must retry manually**: `OptimisticWriteTx::commit()`
returns `Result<Result<(), Conflict>>`. [V] Both span multiple keyspaces
atomically, satisfying R1/R2/R4. [V] Important caveat: outside a transaction the
backing store is only *"a MVCC key-value store, allowing repeatable snapshot
reads"*, and the README warns this *"can not do read-modify-write operations
without the chance of lost updates"* — the brief's fence-late-writes rule (a
commit-time re-verification, i.e. exactly a read-modify-write) therefore
*requires* the transactional wrapper, not the plain API. [I] Repo example folders
are named `tx-ssi-*`, hinting at serializable snapshot isolation internally, but
the README only says "serializable"; treat SSI as inferred vocabulary.

**Keys and prefixes.** [V] Raw byte keys; README states ordering explicitly and
gives the encoding advice the brief's key layout will need: *"keys are stored in
lexicographic order. If you are storing integer keys (e.g. timeseries data), you
should use the big endian form to have predictable ordering."* [V] `prefix()` and
`range()` exist and are `DoubleEndedIterator`. [V] No native prefix delete —
scan plus per-key `remove()`, which in an LSM tree also writes one tombstone per
key and pays write amplification through later compaction. That is the worst
cost profile of the five for R3, since the brief deletes a frame list on every
single terminal path.

**Crash safety and fsync.** [V] `PersistMode` has three variants, read from
`src/journal/writer.rs`: `Buffer` (OS buffers only, not durable across power
loss), `SyncData` (fdatasync), `SyncAll` (fsync). [V] **The default defers fsync
already** — `Database::batch()` sets `PersistMode::Buffer` unless
`manual_journal_persist` is set, and the README says so: *"By default, any
operation will flush to OS buffers, but not to disk. This matches RocksDB's
default durability."* [V] `Database::persist(mode)` forces a sync, and Drop tries
to persist the journal synchronously. This is the most convenient R5 story of
the five — but it inverts the safe default: a settlement commit is **not** durable
unless you remember to call `persist`. [I] No crash-test or power-loss report was
found in primary sources; absence, not a negative finding.

**Shape.** [V] Directory of many files: `journals/<n>`, and per keyspace
`partitions/<name>/{segments,manifest,levels}` plus an optional `blobs/` vlog.
[V] Runs a worker thread pool for flush and compaction, `min(available_parallelism(), 4)`
by default. [V] Defaults from source: 32 MiB shared block cache, 512 MiB max
journaling size, 64 MiB per-keyspace memtable, and an open-fd budget of 900 on
Linux / 400 Windows / **150 on macOS**. [V] Multi-process is hard-blocked always
(not feature-gated): a `LOCK` file, 3 retries 100 ms apart, then `Error::Locked`.

**Coexistence (R5/R8).** [V] Deferred fsync is the default, so the token path is
free by construction. [V] No async API, but the repo ships its own `examples/tokio/`
that wraps every call in `tokio::task::spawn_blocking` — the project's own
documented pattern.

**Footprint.** [V] ~42 transitive dependencies (`cargo tree` on 3.1.10). [V]
README claims *"100% safe & stable Rust"*. [I] No C toolchain needed — no `cc`
or `-sys` build step appears in the tree.

---

## sled

Sources: [repo](https://github.com/spacejam/sled), [README](https://github.com/spacejam/sled/blob/main/README.md),
[docs.rs 0.34.7](https://docs.rs/sled/0.34.7/sled/), [crates.io](https://crates.io/crates/sled).

**Maturity — this is the finding that matters.** [V] What `cargo add sled`
actually resolves to is **0.34.7, published 2021-09-12** — five years old. [V]
The 1.0 line exists only as prereleases: `1.0.0-alpha.124`, last published
**2024-10-11**, nothing on crates.io since. [V] The repo is not dead — commits
continue (latest 2026-04-04), and a 2025-05-07 commit "Project Bloodstone -
sled 1.0" starts a from-scratch storage-engine rewrite introducing `heap.rs`,
`object_cache.rs`, `leaf.rs` and others that do not exist in 0.34.7's
architecture. [V] 172 open issues. [V] `MIT OR Apache-2.0` per Cargo.toml
(GitHub's detector reports Apache-2.0 only — a detection artifact; the Cargo.toml
SPDX field is authoritative).

[V] The maintainer's own words in the README are the primary source that settles
this: *"quite young, should be considered unstable for the time being"*; *"if
reliability is your primary constraint, use SQLite. sled is beta"*; *"if storage
price performance is your primary constraint, use RocksDB. sled uses too much
space sometimes"*; and the on-disk format *"is going to change in ways that
require manual migrations before the 1.0.0 release."*

[I] Synthesis: "actively maintained" is true of the git repo and false of any
installable release. A dependency pin gets a five-year-old artifact that its own
author routes reliability-sensitive users away from — against a brief whose
central demand is durability.

**Transactions.** [V] `Tree::transaction` is documented as *"Fully serializable
(ACID) multi-`Tree` transactions"*, and tuple syntax spans trees:
`(&a, &b).transaction(|(tx_a, tx_b)| ...)` — R1/R2/R4 are covered on paper.
[V] `ConflictableTransactionError` has only `Abort(T)` and `Storage(Error)`;
write-write conflicts are retried internally rather than surfaced. [V] The
consequence is a hard constraint on the brief's intent-effect-settlement pattern:
*"Transactions are optimistic — do not interact with external state or perform IO
from within a transaction closure unless it is idempotent"*, because the closure
may re-run.

**Keys and prefixes.** [V] `AsRef<[u8]>` keys, byte-lexicographic. [V]
`scan_prefix(prefix)` and `range(RangeBounds)` exist, both reversible. [I] No
native prefix delete — no `remove_prefix`/`clear_prefix` appears in the API
surface; it is scan plus per-key `Tree::remove`.

**Crash safety and fsync.** [V] Source-verified default in `src/config.rs`:
`flush_every_ms: Some(500)`, driven by a dedicated `Flusher` OS thread in
`src/flusher.rs`. [V] The only documented durability guarantee is `flush()`:
*"Synchronously flushes all dirty IO buffers and calls fsync. If this succeeds,
it is guaranteed that all previous writes will be recovered if the system
crashes"* — plus the warning that *"Flushing can take quite a lot of time"*.
[V] `Tree::insert` promises nothing about fsync. [I] On `SIGKILL` without a
flush, up to ~500 ms of writes are at risk; the project does not state this,
it follows from the default interval. Against R6 — clean close and `SIGKILL`
must give an identical restart point — that gap must be closed by explicit
`flush()` calls at settlement, which the API supports.

**Shape.** [V] `Config` exposes `cache_capacity`, `use_compression` (zstd),
`temporary` (deletes on drop, uses `/dev/shm` on Linux when no path is set), and
a `mode` of "small" vs "fast". [V] README concedes space usage: *"sled uses too
much space sometimes"*. [I] No multi-process support documented.

**Coexistence (R5/R8).** [V] `flush()` and `pub async fn flush_async()` both
exist — the only candidate here offering any async surface at all. [I] Regular
`insert()` does not block on fsync, so the token path is free; this follows from
the Flusher architecture rather than from an explicit project statement.

**Footprint.** [V] 13 transitive dependencies on 0.34.7 (`cargo tree`). [V] Pure
Rust, no C dependency, no `build.rs` invoking a compiler.

---

## heed / LMDB

Sources: [heed repo](https://github.com/meilisearch/heed), [docs.rs](https://docs.rs/heed/latest/heed/),
[LMDB mirror](https://github.com/LMDB/lmdb), [lmdb.h](https://github.com/LMDB/lmdb/blob/mdb.master/libraries/liblmdb/lmdb.h),
[LMDB LICENSE](https://github.com/LMDB/lmdb/blob/mdb.master/libraries/liblmdb/LICENSE), [lmdb.tech/doc](http://www.lmdb.tech/doc/).

**Maturity.** [V] heed 0.22.1 released 2026-04-07, with a run of
`0.22.1-nested-rtxns-*` prereleases through 2026-02-24 — incremental feature work
stabilised deliberately. [V] Maintained under `meilisearch/heed` and used in
Meilisearch's own engine; 51 open issues, pushed 2026-06-04. [V] LMDB itself has
no semver releases; it is the `mdb.master` branch of an explicitly **read-only
mirror** — the repo description says *"Issues and pull requests here are ignored.
Use OpenLDAP ITS for issues"*, and the header copyright reads "Copyright
2011-2021 Howard Chu, Symas Corp." That is stability by stasis, which cuts both
ways: no churn, but also no responsive upstream on GitHub.

**Licence — the one genuine legal wrinkle in this survey.** [V] heed is MIT;
`lmdb-master-sys`'s Rust code is Apache-2.0; the **vendored LMDB C source is the
OpenLDAP Public License, Version 2.8**. [V] Read in full, it is a short BSD-style
permissive licence: source redistributions retain notices, binary redistributions
reproduce the copyright/notice/disclaimer in accompanying documentation, and
redistributions include a verbatim copy of the licence. [I] It is **not**
copyleft and does not require disclosing the linking application's source, so
static linking into `tp` is fine — provided the OpenLDAP notice and verbatim
licence text ship with the binary's notices. This is a conclusion drawn from
reading the licence, not guidance the LMDB project issues; the decision ticket
should treat it as a checkbox, not a blocker.

**Transactions.** [V] `RoTxn` and `RwTxn`. [V] Nested transactions are real:
`RwTxn::nested()` — *"Transactions may be nested to any level"* — plus
`nested_read_txn()` that reads uncommitted changes within the parent write
transaction. No other candidate here offers that. [V] LMDB's header states the
model: *"The database structure is multi-versioned so readers run with no locks;
writers cannot block readers, and readers don't block writers... Writes are fully
serialized; only one write transaction may be active at a time."* Readers get a
serializable snapshot. [I] A transaction is scoped to the `Env`, not to one
database, so multiple named DBIs commit atomically together — R1/R2/R4 hold;
heed simply does not scope transactions per-DBI at the type level.

**Constraints the others do not have.** [V] `map_size` is a fixed upper bound set
at open time via `EnvOpenOptions::map_size`; exceeding it returns `MDB_MAP_FULL`,
and a second process writing past another's mapsize triggers `MDB_MAP_RESIZED`.
LMDB does not grow the map automatically. [V] Default max readers is 126. [V]
Default max **key size is 511 bytes** — overridable via heed's `longer-keys`
feature (`-DMDB_MAXKEYSIZE=0`, giving ~1982 bytes on Linux/amd64). For the
brief's prefix-addressed keys this is a design constraint to check early, not an
afterthought.

**Keys and prefixes.** [V] `BytesEncode`/`BytesDecode` codecs, with
`Database<KC, DC, C = DefaultComparator>` generic over a pluggable `Comparator` —
the strongest typed-key story here, and a natural home for the brief's named
prefix constructors. [V] `prefix_iter`, `rev_prefix_iter`, `range`, `iter`, plus
`delete_range` and `clear`. [V] **`delete_range` is a cursor scan-and-delete
loop** — read directly from source, it opens `range_mut` and calls
`iter.del_current()` per entry. [V] But `clear()` calls `ffi::mdb_drop(txn, dbi, 0)`
natively, and the docs recommend it: *"Prefer using this method instead of a call
to delete_range with a full range."* [I] That is a real architectural option for
the brief's ephemeral sidecar: if the frame list gets its own DBI per operation,
terminal cleanup becomes a native single-call drop rather than an O(n) scan.

**Crash safety and fsync.** [V] COW B+tree, no WAL: *"Data pages use a
copy-on-write strategy so no active data pages are ever overwritten, which also
provides resistance to corruption and eliminates the need of any special recovery
procedures after a system crash."* [V] The flags, quoted from `lmdb.h`, each name
what they cost:

- `MDB_NOMETASYNC` — *"preserves the ACI... but not D... a system crash may undo
  the last committed transaction."*
- `MDB_NOSYNC` — *"a system crash can corrupt the database or lose the last
  transactions... if the filesystem preserves write order and MDB_WRITEMAP is not
  used, transactions exhibit ACI and only lose D."*
- `MDB_WRITEMAP` — *"the mapped memory may become corrupted if application code
  experiences a bug... Incompatible with nested transactions."*
- `MDB_MAPASYNC` — *"a system crash can then corrupt the database or lose the
  last transactions."*

[I] The zero-flag default fsyncs data and metadata per commit; no single sentence
states this baseline, but it follows necessarily from every flag being described
as an opt-out from it. **Not found:** no published per-commit fsync cost figure
exists in LMDB's own docs — they describe behaviour, not latency.

**Shape.** [V] A directory (or single file with `MDB_NOSUBDIR`) holding a data
file and a lock file. [V] The whole database is mmapped; *"all data fetches
return data directly from the mapped memory, so no malloc's or memcpy's occur"* —
which serves R7's bounded-recovery requirement well, since opening and reading a
small control projection touches only the pages it needs. [V] LMDB supports
concurrent multi-process access, but **heed caps it at one `Env` per path per
process** via a static registry returning `Error::EnvAlreadyOpened`. [I] No
background threads.

**Coexistence (R5/R8).** [V] No async API; `commit()` is a plain blocking call.
[I] To keep the token path free you must either set the no-sync flags and drive
`Env::force_sync` yourself, or push `commit()` onto a blocking pool. Unlike redb
(`Durability::None` per transaction) or SQLite (`synchronous` per connection),
LMDB's durability knobs are **environment-wide flags**, so "cheap for frames,
durable for settlement" is not expressible per-commit without running two
environments or calling `force_sync` manually at settlement.

**Footprint.** [V] **Not pure Rust.** `lmdb-master-sys/build.rs` compiles the
vendored `mdb.c` and `midl.c` through `cc::Build` into `liblmdb.a`. [V] ~30
transitive deps with default features (serde/bincode/json), reducible with
`default-features = false`. [I] Cross-compiling — to musl or anything non-native —
needs a working C cross-toolchain at build time. The output is a normal static
binary, so single-binary distribution is achievable; the cost is at build time,
not distribution time. A search of heed's issue tracker for "musl" returned
nothing, so there is no known blocker and also no explicit confirmation.

---

## rusqlite / SQLite

Sources: [rusqlite repo](https://github.com/rusqlite/rusqlite), [docs.rs](https://docs.rs/rusqlite/latest/rusqlite/),
[isolation](https://www.sqlite.org/isolation.html), [WAL](https://www.sqlite.org/wal.html),
[pragma](https://www.sqlite.org/pragma.html), [atomic commit](https://www.sqlite.org/atomiccommit.html),
[testing](https://www.sqlite.org/testing.html), [optoverview](https://www.sqlite.org/optoverview.html),
[WITHOUT ROWID](https://www.sqlite.org/withoutrowid.html), [copyright](https://www.sqlite.org/copyright.html).

**Maturity.** [V] rusqlite 0.40.2 released 2026-08-08; steady 1–3 month cadence
through 2025–2026. [V] rusqlite and `libsqlite3-sys` are both MIT. [V] SQLite is
public domain — *"All of the code and documentation in SQLite has been dedicated
to the public domain by the authors"* — with an optional paid Warranty of Title
for jurisdictions that do not recognise public-domain dedication. [V] `bundled`
currently vendors SQLite **3.53.4** (read from the amalgamation's own
`SQLITE_VERSION` define; the README says 3.53.2 and is stale by a patch).

**Transactions.** [V] `Transaction` and `Savepoint`, with
`TransactionBehavior::{Deferred, Immediate, Exclusive}` mapping to the
corresponding `BEGIN` forms. [V] `DropBehavior` defaults to `Rollback`.
[V] `Transaction::new` takes `&mut Connection` specifically so transactions
cannot nest on one connection — `Savepoint` is the nesting mechanism. [V]
Isolation, stated plainly: *"all transactions in SQLite show 'serializable'
isolation"* and *"SQLite implements serializable transactions by actually
serializing the writes. There can only be a single writer at a time."* [V] In WAL
mode specifically the reader semantics differ: *"In WAL mode, SQLite exhibits
'snapshot isolation'"*, and a reader upgrading against a stale snapshot fails with
`SQLITE_BUSY_SNAPSHOT`. [V] `BEGIN IMMEDIATE` removes mid-transaction surprise:
*"If the BEGIN IMMEDIATE operation succeeds, then no subsequent operations in
that transaction will ever fail with an SQLITE_BUSY error"* — relevant, because
the brief's settlement transaction must not fail partway. [V] Multi-table
atomicity is guaranteed, and even holds across `ATTACH`ed files via a
super-journal.

**Keys and prefixes — the strongest R3 story here.** [V] The clean form is an
indexed range scan, `WHERE k >= :p AND k < :p_upper`. [V] SQLite lowers
`LIKE 'prefix%'` into exactly that: for pattern `x%` it computes the smallest
string `y > x` of the same length and adds `column >= x AND column < y` — e.g.
`'hello%'` becomes `col >= 'hello' AND col < 'hellp'` — and drops the LIKE test
entirely when the pattern is a single trailing wildcard. [V] But the LIKE
optimization's preconditions are strict and easy to get wrong: no leading
wildcard, no overloaded LIKE function, and the collation must match — with
`case_sensitive_like` OFF (the default) the column must be **NOCASE**, which is
wrong for byte-shaped keys; with it ON the column must be **BINARY**. GLOB is
always case-sensitive/BINARY and sidesteps the pragma. [I] For a KV shape,
writing the explicit range predicate avoids the whole trap.
[V] `DELETE FROM t WHERE k >= ? AND k < ?` is a **single atomic statement** —
the only native, one-call prefix delete among the five, exactly what the brief's
terminal cleanup wants. [V] `WITHOUT ROWID` gives a pure KV table keyed directly
by the primary key, using one B-tree instead of two; sqlite.org's own
`wordcount` example reports "nearly twice as fast" using "about half the amount
of disk space". The page warns against it for large blobs. [I] `BLOB PRIMARY KEY`
on a `WITHOUT ROWID` table is the natural key shape; blobs compare byte-for-byte
intrinsically. [I] Note the tension: the incremental-blob API keys off `rowid`,
so a `WITHOUT ROWID` table cannot use it.

**Crash safety and fsync — the most precisely documented of the five.** [V] In
rollback-journal mode a commit costs roughly **three fsyncs** (two to the journal,
one to the database). [V] In WAL mode with `synchronous=FULL` it is one WAL fsync
per commit ([I] the count for WAL is inferred from the append-only design; no
first-party sentence states it). [V] The decisive quote for R5 is from
`pragma_synchronous`: in WAL mode at `NORMAL`, *"A transaction committed in WAL
mode with synchronous=NORMAL might roll back following a power loss or system
crash"* — no corruption, atomicity/consistency/isolation intact, only durability
of the most recent commits lost, and **application crash (process death, OS
alive) remains fully durable**. That last clause maps almost exactly onto the
brief's `SIGKILL` requirement (R6): `SIGKILL` is an application crash, not a
power loss. The docs conclude *"synchronous=NORMAL is normally all one needs in
WAL mode"*. [V] `wal_autocheckpoint` defaults to 1000 pages, and *"the checkpoint
will be run automatically by the same thread that does the COMMIT that pushes the
WAL over its size limit"* — so checkpoint latency lands on a foreground commit
unless auto-checkpointing is disabled and driven manually.

[V] **Testing is where SQLite is simply in a different category.** sqlite.org
documents 100% branch coverage and 100% MC/DC coverage for the core plus Unix
VFS; roughly 590x more test code than library code; TH3 with 50,362 test cases
(millions of instances in full-coverage runs); SQL Logic Test cross-checking 7.2M
queries against Postgres, MySQL, SQL Server and Oracle; ~500M `dbsqlfuzz` cases
per day. Crucially for R6, it runs **purpose-built crash simulation**: child
processes killed mid-write with VFS-level write reordering and corruption
injection, plus an in-memory VFS that snapshots after N I/O operations, injects
random damage, and verifies via `integrity_check` that every transaction either
fully completed or fully rolled back. No other candidate here publishes anything
comparable — for a brief that says clean shutdown is a controlled crash and to
assert it with a test, that asymmetry is the single largest differentiator in
the survey.

**Shape.** [V] Three files in WAL mode: the database, `-wal`, and `-shm`. [V]
WAL's shared-memory index means **all processes must be on the same host** —
*"WAL does not work over a network filesystem"*. [I] For a coding agent whose
working directory may sit on NFS or a network share, that is a real constraint
worth flagging to the decision ticket. [V] No background threads. [V]
`Connection` is `Send` but **not `Sync`** — verified by source inspection: there
is an `unsafe impl Send for Connection` and no `Sync` impl. Connection-per-thread,
or `Arc<Mutex<_>>`, or a pool.

**Coexistence (R5/R8).** [V] WAL + `synchronous=NORMAL` gives exactly the shape
the brief asks for: no fsync per commit on the hot path, fsync deferred to
checkpoint, durability against process death preserved. [V] Sync API only. [I]
Needs `spawn_blocking` under tokio — standard practice, not documented by
rusqlite.

**Footprint.** [V] The vendored amalgamation is **269,649 lines / 9.5 MB of C**,
compiled via the `cc` crate — a real build-time cost and a C compiler
requirement. [V] `bundled` compiles with FTS5, JSON1, RTree, dbstat and STAT4
enabled unconditionally, so **FTS5 full-text search and the JSON1 functions are
available for free at the SQL level** — which speaks directly to the brief's
session-search projection needing more than scanning. [V] Not using `bundled`
means dynamic linkage against a system SQLite ≥3.45.3, which defeats
single-static-binary distribution. [V] `libsqlite3-sys` declares `links = "sqlite3"`;
[I] per Cargo's `links` semantics only one version of it can exist in a
dependency graph, so two dependencies wanting incompatible `libsqlite3-sys`
versions is an unresolvable build failure — a known practical hazard when mixing
SQLite-linking crates. [V] The README also documents the `modern_sqlite` /
`buildtime_bindgen` version-sync trap: *"Failing to do this will cause a runtime
error."*

---

## Cross-cutting observations for the decision ticket

These are the axes on which the candidates actually separate. No recommendation
is implied by the ordering.

1. **Native prefix delete is nearly absent.** Only SQLite expresses the brief's
   terminal cleanup as one atomic statement. redb, fjall, sled and heed's
   `delete_range` all perform scan-and-delete inside the transaction. [I] For
   fjall this is worst, since an LSM writes a tombstone per key and pays again at
   compaction; for heed there is an escape hatch — give the ephemeral scope its
   own DBI and use the native `clear()`/`mdb_drop`.

2. **Deferred fsync is universally available, but the granularity differs, and
   that is the real distinction.** redb picks durability **per transaction**
   (`Durability::None` vs `Immediate`) — the finest granularity, and the closest
   match to "frames cheap, settlement durable" as a single-store design. SQLite
   picks it **per connection** (`synchronous` pragma). LMDB picks it **per
   environment** (flags), so mixed durability needs two environments or manual
   `force_sync`. fjall defers **by default**, which is convenient but inverts the
   safe default. sled defers via a 500 ms background flusher.

3. **`SIGKILL` and power loss are different failures, and the brief only demands
   the first.** R6 asks that clean close and `SIGKILL` leave an identical restart
   point — that is application-crash durability, not power-loss durability. [V]
   SQLite's WAL+`NORMAL` mode is documented as exactly this: durable against
   process death, may lose recent commits on power loss. [I] If the brief's bar
   really is `SIGKILL` rather than power loss, the cheapest durability tier of
   several candidates is already sufficient, and paying for an fsync per
   settlement is a choice rather than a requirement. Worth resolving explicitly
   before the decision, because it changes the ranking.

4. **Two stores or one.** The brief's dependency policy already names `rusqlite`
   as the escape hatch when session search outgrows scanning, and `bundled`
   enables FTS5 for free. [I] Choosing a non-SQLite substrate therefore risks
   shipping *both* engines later; choosing SQLite risks nothing extra. This is a
   product-level argument, not a technical one, and it belongs in the decision.

5. **Pure Rust vs C is a build-time cost, not a distribution-time one.** [V]
   redb (0 deps), fjall (~42) and sled (13) are pure Rust and cross-compile
   trivially. [V] heed and rusqlite both compile vendored C via `cc`; [I] both
   still produce a static binary, but both need a C cross-toolchain for musl or
   any non-native target.

6. **Bus factor is a shared weakness, differently shaped.** [V] redb and fjall are
   each effectively one person. sled is one person mid-rewrite with no release in
   two years. heed has an institutional maintainer (Meilisearch) atop a C library
   whose GitHub presence is a read-only mirror. rusqlite is community-maintained
   over a public-domain library with an exceptional test corpus. Longevity risk
   and code-quality risk are not the same axis and should be scored separately.

7. **Multi-process access is a latent product question.** [V] fjall forbids it
   outright; redb needs an unstable feature; sled does not support it; LMDB
   supports it natively (though heed limits one `Env` per process); SQLite
   supports it on the same host but not over a network filesystem. [I] If two
   `tp` instances may ever open the same session directory — plausible for a
   terminal agent — this constraint promotes itself from footnote to requirement.

## Open questions this survey could not close

- No first-party fsync latency figures exist for LMDB, sled, redb or fjall.
  redb publishes its own comparative benchmark table (redb, lmdb, rocksdb, fjall,
  sqlite) in its README, but it is the author's own harness on one machine, and
  measures throughput rather than fsync cost. The ticket's "what an fsync costs
  in practice" is therefore answered structurally (how many, and when) rather
  than numerically. Measuring it on target hardware is a separate task.
- Only SQLite publishes a crash-testing methodology. For redb the crash story
  rests on checksum design; fjall and sled publish nothing found.
- redb's page-cache configuration knobs were not fully enumerated; the `Builder`
  API needs a closer look before sizing decisions.
