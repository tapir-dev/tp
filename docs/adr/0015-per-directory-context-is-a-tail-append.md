# Per-directory context is a tail append, not system prompt

A context file found at the user level or the project root is assembled into the
system prompt once, at session start. A **per-directory** context file — one
that becomes relevant only when work reaches its subtree — is never added to the
system prompt. It enters the conversation as an appended entry at the moment a
file tool resolves a path underneath it.

## The two brief lines that do not close together

The brief asks for "hierarchical context files: global, project root, and
optionally per-directory files that **load when work touches that subtree**".

The brief also states, as a hard invariant: "the provider context may only grow
at the tail across a lane's requests. Any insertion before the previous tail
invalidates the provider's KV cache and multiplies cost."

The system prompt sits before the tail. If a per-directory context file is
system-prompt text and it loads mid-session, that load is an insertion before
the previous tail — the exact operation the hard invariant forbids, and the one
the ticket that owns retry and cache enforcement exists to make impossible. The
two lines cannot both be honoured while context files are one kind of thing.

## What was considered

**Resolve the whole set once, at start-up, from the working directory.** Honest,
and it is what at least one shipped implementation of the surrounding convention
does. It costs the capability outright: in a monorepo the context that matters
is the one belonging to the package the agent has not opened yet, and at
start-up nobody knows which that is.

**Put it in the system prompt and accept the cache cost.** This was rejected not
on price but on contradiction. The invariant is stated in the brief as hard, and
a design that violates it in one place turns it into a guideline everywhere
else.

**Split the two.** Levels that are knowable at start-up are prompt; the level
that is not is a message. Nothing is inserted before the tail, so the invariant
holds by construction rather than by care.

## Consequences

- **Hierarchical context is no longer one mechanism.** The accumulation order
  governs the prompt-level files only. A per-directory file is not "later in the
  merge"; it is a different position in the request entirely, and the reference
  page has to say so or the ordering reads as arbitrary.
- **A loaded per-directory file is visible in the transcript.** This is a real
  gain and not merely a consolation: the question "why does the agent believe
  this?" has an answer a user can point at. A block of invisible system prompt
  has no such answer.
- **Loading is sticky, and it has to be.** Unloading a context file whose
  subtree the agent has left would mean removing an entry that is already behind
  the tail — the same violation by the back door. Once appended, it stays for
  the session.
- **The trigger is a resolved path, not a mentioned one.** A file tool
  (`read`, `write`, `edit`) resolving a path under the directory is what loads
  it. A path that merely appears in a tool argument does not, because a
  mentioned path may never be read, and triggering on mention makes the prompt a
  function of what the model *wrote* rather than of what happened. The shell
  tool is excluded, consistent with its exclusion from the path-keyed mutation
  queue: it declares no path.
- **Unbounded accumulation is governed by the budget, not by a second limit.**
  An agent walking a large monorepo accumulates context files with nothing
  reclaiming them. The prompt budget already rejects; a per-file or per-session
  cap here would be a second mechanism interacting with the first, which is the
  shape this map has refused before.

## Note on numbering

ADR numbers collide across the unmerged wayfinder branches. This file takes
`0015` against the highest number on `main` at the time of writing, on the
standing assumption that numbers are reconciled when branches land.
