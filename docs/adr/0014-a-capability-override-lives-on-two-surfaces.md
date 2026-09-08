# An environment row is a mirror or standalone

> Titled "A capability override lives on two surfaces" until the second
> amendment below, which is where the title stopped describing the document. The
> filename keeps the original slug: closed tickets link to this file by path.


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

## Second amendment: the test has two clauses, and the first one says *consumed*

The amended test above is **necessary but not sufficient**, and its single clause
is mis-worded. Both defects surface on the same row — `TP_ASSET_DIR`, the
variable the first amendment deliberately left open.

**The first clause says *read*; it must say *consumed*.** The environment is one
closed registry built from a derive, and the natural shape of that is a single
construction at process start: every row is *read* at the same moment, before
config, which run literally would make every row standalone and take
`TP_SESSION_DIR` and the capability overrides down with it. What differs between
rows is when the value is **needed**. The diagnostics ticket had already written
this out by hand for `TP_LOG_LEVEL` — the level is wanted at two moments and only
the second one has a key — and under the corrected wording that row classifies
itself.

Corrected, the clause is unchanged in every verdict it has already delivered:
`TP_CONFIG_DIR` standalone, because the config root is needed before config is
located; `TP_SESSION_DIR` and the capability overrides mirrors, because nothing
wants them until the snapshot exists.

**The second clause: no writer, no key.** An environment row is also standalone
when **no writer of the setting can author a config file**. This is a different
impossibility from timing, and the two divide the work cleanly: the first is
about *when* the value is needed, the second about *who* writes it. They never
shadow each other — whoever sets `TP_CONFIG_DIR` can write a config file
perfectly well, they simply cannot be found in one.

### `TP_ASSET_DIR` is standalone, on the second clause

The timing clause does not reach this row in either direction, and that is a fact
about the row rather than a gap in the test. Resolving an asset is necessarily
post-config, because rung 5 of the scope ladder *is* config — so the ladder as a
whole never resolves early, and "does the asset root resolve before or after the
config load" has no answer to give.

The asset root has exactly two writers: a packager patching a built-in file for
immutable-store packaging, and someone developing `tp` itself, pointing the
variable at the repository's asset tree to recover the authoring loop a built-in
cannot have. Neither writes the user's config file. A packager's derivation
cannot write into somebody else's `$XDG_CONFIG_HOME`, and the developer keeps the
value in the shell environment, where it belongs to the checkout rather than to
the machine.

The concrete proof that no key is missing is **domination**. Everything an
`assets.root` key could express is already expressible by the rung 5 pattern
lists, which *outrank* rung 2 — and rung 2 also loses to rung 3, the user's own
global asset directory. A key written by the user and deliberately beaten by two
locations that same user controls is not a key. Worse, under "the mirror outranks
the file", a packager's `TP_ASSET_DIR` would silently beat a user's
`assets.root`, in the one rung whose entire purpose is to lose to the user.

Rung 2 is distinct by its **writer**, not by its content. The environment is not
a second surface for it; it is the only surface it has.

### Consequences

- The *"Deliberately not settled: `TP_ASSET_DIR`"* paragraph above is
  **discharged**. The row stays standalone, which is what it already was, but now
  on a stated ground rather than by default.
- **There is no `assets` axis and no `assets.root` key.** This is a negative
  declaration, not an omission: the axis was considered and refused, because it
  would carry one key, that key is dominated at birth, and no existing axis is a
  host for it.
- **Passing the timing clause is not enough.** A setting wanted only after the
  snapshot exists is a mirror *unless* nobody who sets it can write a config
  file. Classifying a new row means running both clauses, in that order.
