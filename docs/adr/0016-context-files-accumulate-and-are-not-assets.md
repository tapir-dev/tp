# Context files accumulate, and are therefore not assets

The product has had exactly two composition rules: an **asset** composes by
shadowing — one whole file wins over another of the same name, resolved on the
scope ladder — and a **config layer** composes by deep merge. A context file
does neither. Every level that is present is included, in order, and none
removes another. That is a third rule, named **accumulation**, and its direct
consequence is that a context file is not an asset and does not sit on the scope
ladder at all.

## Why not shadowing

Forcing context files to be assets is the cheap answer: the ladder already
exists, it already carries the trust gate, and it already resolves collisions by
name. It fails on the first real case. A user keeps standing preferences in
their own context file; a repository ships one describing its conventions. Under
shadowing the project's file wins whole and the user's preferences vanish
silently in every repository that has one — which is the entire population of
repositories the feature is for.

## Why not deep merge

Deep merge needs a key path to merge along. These files are prose. There is
nothing to merge except concatenation, and calling concatenation a merge borrows
a word that already means something precise here and will be read as meaning it.

## What the surrounding ecosystem does, and where it disagrees with itself

Worth recording, because the disagreement is between a convention and its own
reference implementation and a future reader will find both.

The tool-neutral convention states in its own documentation that the nearest
file in the directory tree **takes precedence** and that the closest file
**wins** — replace semantics. The reference implementation of that same
convention documents the opposite: it concatenates from the root down and
describes "override" as nothing more than later position in the combined prompt.
A third widely-used implementation states outright that discovered files "are
concatenated into context rather than overriding each other."

So the convention says shadowing and the implementations do accumulation.
Accumulation is chosen on its merits above; the agreement with what tools
actually do is a check on that reasoning, not the reason.

## Consequences

- **Context files leave the scope ladder.** The ladder answers "which file
  wins", and here none does. What the ladder was also providing — the trust gate
  on the project rung — is unaffected, because the trust decision reaches
  context files by their own route: they are gated per input root like every
  other project-local input.
- **`context` is not an asset discovery axis.** The two axes named so far whose
  keys govern where things are searched for — `skills` and `commands` — sit
  downstream of the ladder, and their assets shadow. `context` looks like them
  and is not one. This has to be written down; otherwise a reader generalises
  from the pair and assumes the ladder applies to all three.
- **Order is fixed, not configurable.** The brief calls the merge order
  "documented and configurable". The order encodes a precedence — the more
  specific level has the last word — and making it configurable means the
  question "which instruction wins?" stops having an answer in the
  documentation and starts having one per user. This is the same defect that
  made the config loader refuse to accumulate N project layers. The line is
  overturned: documented, fixed.
- **Order is built-in, then user, then project root**, each appending, with
  per-directory files entering by a different route entirely (see the ADR on
  per-directory context being a tail append). Under an untrusted project the two
  project levels are absent, not empty: the project layer is not read at all.

## Note on numbering

ADR numbers collide across the unmerged wayfinder branches. This file takes
`0016` against the highest number on `main` at the time of writing, on the
standing assumption that numbers are reconciled when branches land.
