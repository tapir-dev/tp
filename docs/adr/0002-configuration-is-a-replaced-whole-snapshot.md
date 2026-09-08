# Configuration is a replaced-whole snapshot, never a diff

Every runtime surface in `tp` — the tool registry, the theme, the keybinding
table, the provider set — is a pure function of one immutable configuration
snapshot. A config change builds a new snapshot and swaps it in whole; nothing
observes a change event and patches itself in place.

## Why

The obvious design is the opposite one: watch the config file, work out what
changed, and apply that delta to the affected subsystem. It looks cheaper, and
it is the shape most reload implementations take.

It fails on the case `tp` cannot afford to get wrong. The product's premise is a
long-lived process the user reconfigures while it runs, so a reload is not a
rare event — it is the normal way the product is operated. Under diffing,
correctness is a property of every subsystem's `apply_change` path, and a state
reachable only by a particular *sequence* of edits is a state nobody tested. The
common bug is not a crash; it is a running instance whose behaviour no longer
matches its own config file, which is unfalsifiable from the user's chair.

Three separate decisions arrived at this shape independently before it was named:
the tool registry is a host-owned draft rebuilt from scratch on every change
rather than a registry with `register`/`unregister`; a failed live reload is
rejected atomically with the previous configuration left in force; and terminal
capability is a snapshot replaced whole rather than a set of fields mutated as
probes answer. Three instances of one idea is the point at which it should be a
stated invariant rather than a coincidence of taste.

## Considered options

- **Diff and apply.** Rejected above: it distributes reload correctness across
  every subsystem and makes the failure mode silent.
- **Rebuild the whole process — reload by restart.** Rejected: it discards the
  live session, which is the one thing a coding agent must not lose, and the
  brief requires reload without restart.
- **Snapshot for some subsystems, diff for the expensive ones.** Rejected as the
  worst of both: the user would have to know which surfaces reload honestly and
  which reload approximately, and the boundary would move with every
  optimisation.

## Consequences

Rebuild cost is paid on every reload, including for surfaces that did not
change. This is accepted: reload is user-initiated and human-paced, so the
budget is a keystroke, not a frame. If a surface ever becomes genuinely
expensive to rebuild, the answer is to make its construction cheaper, not to
reintroduce diffing.

Subsystems may not hold long-lived references into the snapshot's interior, or
they will observe a stale sub-tree after a swap. They take the snapshot, or a
value derived from it, and re-derive after a swap.

Because a snapshot is constructed whole, it can be validated whole before it is
installed. That is what makes an invalid reload a no-op rather than a partial
application, and it is why the error path needed no separate rollback machinery.
