# A capability override lives on two surfaces

Every terminal capability override exists twice: as a config key on the
`terminal` axis, which is canonical, and as a **mirrored env entry** in the
environment registry. The resolution order is `--set`, then the mirrored env
entry, then the config file, then the key's own resolution ladder.

## Why two surfaces rather than one

The brief lists hyperlinks, image protocol, truecolor, hardware cursor and
escape timeout under *Environment variables*, each with an `auto` default. The
ticket that decided terminal input then wrote `escape_timeout = "auto"`, which
is TOML. Both readings are in the contract and neither is wrong, because the two
surfaces answer different questions.

An env var is the right shape for the moment the value is needed: a user who has
just discovered their multiplexer eats `key_release` wants to prove it in one
command, on one run, without editing a file and without leaving the setting
behind. A config key is the right shape for the answer they keep. Forcing one
surface loses one of those.

The config key is canonical because the alternative removes the keys from
`tp config get` and `tp config schema` — the two verbs that exist precisely so
an agent can query a setting without a network. The capability overrides are the
settings most likely to be the subject of a support question, so they are the
last ones that should be invisible to the query surface.

## Why this is not the generic env mapping that was already rejected

The config schema decision rejected a blanket `TP_<KEY>` mapping on three
grounds: it doubles the config surface, it turns provenance into a translation
table, and it contradicts the small declared env set already chosen. A mirrored
entry survives all three because it is **enumerated, not derived**. Each mirror
is a row written by hand in the same closed registry, carrying the same derived
name, type, default, effect and example as any other row, and the lint that
forbids raw env reads outside the registry is unchanged. The registry stays
closed; it simply has rows in it that happen to target an existing key.

The distinction is worth the name it is given. "Every capability override also
has an env var" is a rule; "every config key also has an env var" is the
mapping that was rejected. Only the enumeration keeps them apart.

## Why the mirror outranks the file

An env var is scoped to one invocation and a config file is not. A setting the
user typed for this run should not lose to a setting they typed last month, and
the reverse ordering makes the diagnostic gesture — run once with the override,
see whether the symptom moves — silently useless. `--set` stays above both: it
is the explicit, per-invocation escape hatch, and it records provenance as
`cli`.

Provenance is what makes the ladder honest: a value that arrived from a mirrored
entry records `override`, never `measured`. A field whose `auto` resolved to a
guess must not report itself as having been asked.

## Consequences

- **The mirror set is enumerated in the registry, not generated.** Adding a
  capability override is two edits, and the second one is deliberate. A key that
  nobody mirrors is a key nobody can set for one run — which is the correct
  outcome for a setting that is not a capability claim.
- **Only capability overrides earn a mirror.** The admission test is the one the
  `auto`-overrides ticket states: a key qualifies only if the capability
  snapshot has a field of that name carrying provenance. A preference about what
  `tp` chooses to emit is not a capability override however terminal-flavoured
  it sounds, so `click_interval`, `handshake_budget` and the `layout` keys get
  no mirror.
- **`escape_timeout` is the edge case, and it is mirrored anyway.** It is not a
  snapshot field — its ladder *reads* the snapshot rather than setting it — but
  the brief names it in the same breath as the other four, and it is diagnosed
  the same way: over SSH, on one run. The exception is recorded here rather than
  left for a reader to trip over.
- **Two surfaces mean two places a value can be wrong.** The settings browser
  must show provenance for these keys or the ladder is unreadable from inside
  the product; that is already guaranteed, since every value in the snapshot
  carries its layer, file and span.

## Note on numbering

ADR numbers collide across the unmerged wayfinder branches: `0001` through
`0004` are each claimed by more than one branch. This file takes `0005` on the
same assumption every other branch has made — that numbers are reconciled when
the branches land, not before.

## Amendment: the admission test was never about capabilities

The consequence above titled *"Only capability overrides earn a mirror"* is
**superseded**. It was true of the set of keys in front of the ticket that wrote
it and false as a general rule, and the error is visible in this document's own
reasoning: the argument for two surfaces — an env var is the right shape for the
moment a value is needed, a config key is the right shape for the answer you
keep — never mentions capabilities anywhere. It is an argument about the
lifetime of a setting, and it generalises.

The evidence that it was already false: the asset-resolution ticket declared
three environment variables before this ADR existed, and one of them,
`TP_SESSION_DIR`, sets the session directory. The moment the sessions axis
declares a `directory` key, that variable *is* a mirrored entry under this ADR's
own definition — a row that targets an existing config key rather than naming a
variable of its own. Nothing was added to make that true; it was true and
unnoticed.

**The amended test.** An environment row is a **mirror** when a config key for
the same setting can exist, and **standalone** when one cannot. The distinction
is not about the subject matter of the setting but about whether config has been
loaded yet at the moment the value is read:

- `TP_CONFIG_DIR` is **standalone and must remain so**. It locates the config,
  so it is read before any key exists. A key for it would be a key that names
  the file it is read from.
- `TP_SESSION_DIR` is a **mirror**, targeting `sessions.directory`.
- The capability overrides are **mirrors**, exactly as enumerated above. The
  capability admission test still decides which *terminal* keys exist at all; it
  simply never decided which keys are mirrored.

The enumeration is untouched, and with it the three grounds on which the generic
`TP_<KEY>` mapping was rejected: each mirror is still one hand-written row in a
closed registry, provenance is still a fact rather than a translation, and the
lint against raw environment reads is unchanged. What changes is only the
sentence that says which keys may earn a row.

**Deliberately not settled: `TP_ASSET_DIR`.** The third variable overlays
built-in assets per file. Whether the amended test reaches it depends on when an
asset root is resolved relative to the config load, which belongs to the ticket
that owns asset resolution and is closed. Applying the new test to it in passing
would create exactly the orphan this amendment's ticket exists to close, so it
is recorded as an open question on the map rather than answered here. Until it
is answered, `TP_ASSET_DIR` stays standalone by default, which is what it is
today.
