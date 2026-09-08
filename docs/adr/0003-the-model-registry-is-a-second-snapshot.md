# The model registry is a second snapshot, with its own clock

The resolved set of model entries is an immutable value published by swap, on
the same discipline as the configuration snapshot — replaced whole, never
diffed — but it is *not* part of that snapshot and does not share its version.
Configuration contributes the registry's inputs: the declared surfaces, the
user's patches, and the refresh policy. The registry is what those inputs
compose into once the built-in catalog and the network-refreshed cache are
merged in.

## Why

The configuration invariant says every runtime surface is a pure function of
the merged configuration snapshot. Read literally, that puts the model registry
inside the snapshot, and the model registry is the one surface that has a
second input the user did not type: a network refresh that arrives on its own
schedule.

Folding the two together breaks in both directions. A refresh completing would
have to build a new *configuration* snapshot, which means a background network
response synthesises a config reload — and under the reject-atomically rule, a
config file that is invalid at that moment would silently discard a successful
refresh. In the other direction, a user editing an unrelated key rebuilds the
registry, and the honest implementations of that either re-read the cache from
disk on every keystroke-paced reload or quietly carry the old registry forward,
which is the in-place mutation the invariant exists to forbid.

Two values with two clocks keeps both rules true without weakening either. The
configuration invariant stays literal. The registry gets the same guarantee —
whole replacement, no long-lived references into its interior — and a version
of its own.

That version is also what the brief asks for when it requires generation
counters so a stale in-flight refresh cannot clobber newer state. A refresh
computes against the registry generation it started from; if the published
generation has moved on, its result is dropped. The counter is not a new
mechanism invented for the refresh, it is the snapshot's version doing the job
snapshot versions do.

This is worth stating because the durability decision *rejected* a generation
counter, and a reader who remembers that will expect consistency. The objection
there was specific: a durable counter beside a state machine is a second source
of truth on disk that can drift from the first. This counter is in memory, it
is derived from the publish itself rather than maintained alongside it, and
nothing reads it after the process exits.

## Considered options

- **Registry inside the configuration snapshot.** Rejected above: it makes a
  network response trigger a config reload, and couples the freshness of the
  model catalog to the validity of an unrelated file.
- **Registry as mutable shared state behind a lock.** Rejected: it is exactly
  the in-place mutation the configuration invariant forbids, and it reintroduces
  the class of bug that invariant was written to kill — a running instance whose
  behaviour no longer matches any state the user can point at.
- **No cache at all; built-in catalog only, refreshed by release.** Rejected:
  it makes every new model wait for a binary release, which the brief's
  three-tier requirement rules out. It is, however, exactly what the product
  degrades to when the network is unavailable, and that is not an error state.

## Consequences

A model change and a config reload are independent events, so the two can
interleave. Anything deriving from both — the model picker, the status line —
re-derives from whichever swapped, and holds a reference into neither.

The registry's inputs live in configuration but its content does not, so
`tp config get` reports what the user wrote, not what the merge produced.
Inspecting the resolved entry is a separate affordance, and it has to exist, or
the user has no way to see which tier won a cell.

Deleting the on-disk cache is always safe. It costs freshness, never
correctness, because the built-in catalog is a complete tier on its own rather
than a base the cache is required to complete.
