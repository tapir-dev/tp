# Trust is decided before the configuration snapshot exists

Project trust decides whether the project configuration layer joins the merged
snapshot at all. It therefore cannot itself be a function of that snapshot, and
`tp` resolves it in a phase that runs before the snapshot is built: the global
config layer loads, trust is decided for each project-local input root, and only
then does the project layer join and the snapshot get merged. The trust keys are
read from the **global layer only**.

## Why this is an exception to ADR-0002, and why it has to be

ADR-0002 states that every runtime surface is a pure function of one immutable
configuration snapshot. Trust is the one input that cannot be, and the reason is
circularity rather than convenience: the value that decides whether a file is
read cannot be read from that file.

The failure this prevents is not subtle. If `trust.default` were an ordinary key
resolved from the merged snapshot, a project's own `.tp/config.toml` could carry
`trust.default = "always"` — and a cloned repository would grant itself the trust
that gates whether it is read. The gate would admit exactly the inputs it exists
to hold back, and it would do so silently, because a merged value carries the
provenance of the layer it came from and nothing forbids that layer being the
project.

Making the keys global-layer-only is what closes it. A `trust.default` in a
project layer is not merged and not honoured; it is dropped with a warning, so a
user who wrote it learns that it did nothing rather than believing it worked.

This is the same shape as the model registry, which was made a *second* snapshot
rather than folded into the first: two values with two clocks, because folding
them would let one synthesise the other. Here there is no second snapshot, only a
phase that runs first, but the reason for refusing the fold is the same one.

## Considered options

- **A `trust` field on the merged snapshot, with the project layer forbidden
  from setting it.** Rejected: the prohibition would be a rule enforced by
  review rather than by structure, on the one key where a missed enforcement is
  a silent trust grant. The phase ordering makes it unrepresentable instead.
- **Trust as a pre-snapshot value with no config key at all**, resolved only from
  the CLI and the store. Rejected: the brief names `default_project_trust` as a
  global setting, and a user with `always` set once should not retype it every
  run.
- **Deciding trust once per run against the session cwd.** Rejected in favour of
  gating each discovered input root, which is what the config decision already
  chose when it fixed that the gate applies to the directory *found* rather than
  to cwd. One decision per run is the reading that lets a grant on a narrow
  subdirectory admit a config file from an ancestor nobody trusted.

## Consequences

- **The bootstrap window is real and bounded.** Between process start and the
  global layer loading, no trust value exists. Nothing project-local may be read
  in that window, which is a stronger statement than it sounds: it means asset
  discovery cannot run before config, and the scope ladder's project rung is
  therefore always evaluated after the global layer.

- **Reload re-evaluates trust, and cannot patch it.** A live reload rebuilds the
  whole snapshot, so a grant or revocation changes which layers compose and lands
  atomically. There is no path that adds project-local inputs to a running
  snapshot in place, which is what keeps a revocation honest.

- **The one-shot surface has no trust prompt and no reload.** Configuration is
  read once there, so trust is decided once, from configuration and the CLI
  alone. Nothing waits for a human.

- **A per-run override is a property of the invocation, not of the snapshot.** It
  therefore survives a reload, where a config-derived value would not. This is
  deliberate: a flag the user passed for this run should not be silently dropped
  by an unrelated edit to a config file.

## Note on numbering

ADR numbers collide across the unmerged wayfinder branches; `0009` is claimed by
two of them. This file takes `0010` on the same assumption every other branch has
made — that numbers are reconciled when the branches land, not before.
