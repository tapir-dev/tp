# The model entry carries a third provenance vocabulary

A resolved model entry is inspected through `tp models`, a query verb, and
every cell of it carries an **origin**: a token naming which position in the
composition wrote the winning value, plus a citation where that position is a
patch. `origin` is a third provenance vocabulary beside the config `layer` and
the scope-ladder `rung`, and it is deliberately not either of them.

## Why a third vocabulary, when a previous decision fixed two

The query-verb convention fixed `layer` and `rung` and named the reason they
are not unified: a config layer composes by **deep merge**, a scope-ladder rung
composes by **shadowing**, and collapsing the tokens would assert a composition
that does not exist. That same discriminator is what admits a third term rather
than what forbids it. A model entry resolves **per cell**, last write winning,
over a stack that is *open*: the per-model patches are an ordered list of
arbitrary length, and a user override is a patch in that same stack rather than
a mechanism beside it.

Openness is the part neither existing vocabulary can absorb. `layer` is five
tokens and `rung` is six, and both are closed ladders, so a token alone answers
"which one won". Here it cannot: two patches can both match a model id, and
saying `origin: "patch"` without saying *which* patch leaves the support
question exactly where it was. So an origin is a token **and**, for the patch
case, a citation — the config key that declared it, with its layer, file and
span. The citation reuses the backlink shape the asset record already uses; the
two provenance senses touch by citation, not by merger.

## Why the origin domain is the union of two stacks

A model entry is a pair — metadata and a quirk row — and the two halves compose
from different stacks. The quirk row runs dialect defaults, then the surface
base row, then patches. The metadata runs the built-in catalog, then the
network-refreshed cache, then patches. The union is five tokens: `dialect`,
`surface`, `catalog`, `patch`, `cache`.

The three-tier vocabulary already in use — built-in catalog, cache, user
overrides — is a coarser view of the model *source*, the machinery, and it
cannot express this. It collapses `dialect` and `surface` into one token, which
loses the distinction the support question turns on: whether a quirk cell reads
the way it does because a dialect default says so or because a surface base row
overrode it. Those are two compiled artifacts, not one.

Some tokens are impossible in one half. The cache may write metadata and may
never write a quirk cell; `dialect` and `surface` never appear under metadata;
`catalog` never appears under a quirk. Emitting the two halves as separately
named sections makes that authority split readable on the wire — a reader sees
that no quirk cell carries `origin: "cache"` — instead of trusting an invariant
documented elsewhere.

## Why the verb, and not the settings browser

The asset surface refused a settings-browser view on the grounds that one
product cannot put two composition rules behind one navigation gesture. That
argument does **not** transfer here, and reaching for it would be borrowing
reasoning that does not hold: per-cell last-write is close kin to deep merge,
not to shadowing.

The browser is refused anyway, on this ADR's own grounds. The registry is a
second snapshot with its own clock. The browser shows config keys, and every
value it shows carries a layer, a file and a span; a model entry has none of
the three, and it can be replaced under the browser by a refresh that owes
nothing to a config reload. A view that had to explain both of those to be
honest is a second product inside the first.

## Consequences

- **The verb reaches no network.** It passes the query-verb predicate: it
  re-derives the entry from the built-in catalog, the on-disk cache and config
  on the invocation that asked, exactly as the asset verb re-derives its ladder.
  A refresh is the scheduler's, behind its persisted throttle; a user-facing
  refresh verb would cross that throttle and is not in v1.
- **The generation counter does not travel.** The verb runs in a fresh process,
  so a published generation would be the same number every time and would only
  invite a consumer to match on it.
- **Staleness travels where it lives, not as a flat pair.** The catalog's cut
  date is already a metadata cell, so it arrives as a cell with its own origin
  and costs no new field. The cache's age belongs to the tier for one surface
  rather than to the entry, and it carries two facts, not one: when the surface
  last refreshed, and whether it supports listing at all. A surface with no
  listing endpoint is never going to refresh, and that is a different fact from
  a refresh that has not happened lately.
- **Every cell is emitted, always.** A cell whose origin is `dialect` is the
  answer "nobody touched this" made observable; omitting it would leave a
  reader inferring the entry has fewer cells than it has. This is the same
  argument the asset record uses for emitting vacuous rungs.
- **Two names now mean adjacent things.** `origin` sits beside `layer` and
  `rung` on the wire, and the glossary carries all three with their composition
  rules, because the cost of a third token is a reader who assumes it is one of
  the first two.
