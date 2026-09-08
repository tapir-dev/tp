# The theme role taxonomy is a rooted forest

The taxonomy is fifty-six theme roles. Seven of them are **root roles** — `text`,
`background`, `accent`, `muted`, `success`, `warning`, `error` — which a theme
file must spell. Every one of the other forty-nine names **exactly one** parent
role, so the roles form a forest rooted in those seven, and a role's fallback
chain is the walk from it to its root rather than a list it carries.

## Why seven required roles instead of all fifty-six

A theme is an asset, and an asset shadows whole file by whole file: a user's
`gruvbox` replaces the built-in rather than deep-merging with it. Reading the
brief's *required `colors` table covering every semantic role* literally under
that composition means a user who wants to change the accent colour must first
write fifty-five other keys, because there is nothing left to merge with. The
requirement and the composition cannot both hold at full strength, and the
composition is the one another decision already fixed.

Seven is the smallest set that every other role can be phrased in terms of. They
are required rather than defaulted because a theme with no `error` colour is not
a theme with a sensible fallback; it is a theme whose author did not consider
errors.

`background` is required and may still be `""`. Required means the key is
present, not that it is coloured, and the empty string already means *terminal
default* — so a transparent theme is a choice the author writes down rather than
an omission that happens to work.

## Why one parent rather than an ordered list

The schema generator inlines every subschema, which is why a chain is spelled by
**name, as a string** and never by nesting a role inside a role — a nested
spelling would recurse forever and hang the build rather than fail it. That much
was already decided. What is decided here is the arity.

A list lets two roles reach the same destination by different routes, and
nothing detects that they disagree. A single parent makes the chain a property of
the forest rather than of each role, which collapses the invariants to two, both
checkable at build time: no cycles, and every walk terminates in a root. The
generated reference page then prints the chain instead of asserting one, which
is the difference the doc-comment rule was buying in the first place.

The cost is that a role cannot express "prefer A, else B, else C" for unrelated
A and B. No role in the taxonomy wanted to; the deepest walk is three hops
(`markdown_link` → `link` → `accent` → root).

## Consequences

- **Adding a role after v1 is backwards compatible; adding a root is not.** A
  non-root role is optional and inherits, so an existing theme file stays valid
  and picks the new role up through its parent. The seven roots are therefore
  the stability contract of the theme file format, and the only part of it that
  a later version cannot extend quietly.
- **A missing role is a component that cannot be written.** A `Style` is a theme
  role plus attributes, so the taxonomy is the styling API rather than a lookup
  table beside it. Fifty-six is what the surfaces in the brief actually consume,
  not a target.
- **Every role carries a mandatory doc-comment, with no per-role example.** The
  build already fails on a key without a doc-comment; fifty-six one-line TOML
  examples would be noise, so the worked example is per page.
- **No word-level intra-line diff role exists.** Diff carries added, removed,
  context, a header and two backgrounds; highlighting the changed run *within* a
  line was considered and left out of v1. It is recorded as a negative
  declaration on the axis page so the next reader sees a refusal rather than an
  oversight.
- **One theme file describes one appearance.** Light and dark are two assets,
  not two blocks inside one, because a variant block reintroduces partial
  merging under a composition that has none.
