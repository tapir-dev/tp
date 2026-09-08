# An overlay may contribute a binding context without owning input

The context chain gains a fourth, innermost position: an **advisory context**,
contributed by an overlay that never enters the ownership stack. `completion` is
the only one in v1. The `Owning` / `Transient` pair is unchanged, and so are
suspend, resume, and the fixed teardown order.

## The bind

The completion overlay is the editor's most frequent gesture and it shipped on
`tab`, `alt+l`, `alt+n`, `alt+p`, `ctrl+g`, marked provisional. That was not a
taste failure. The five ids sat in `editor`, layer 1, and a binding may not
depend on prior state — `editor.yank_pop` is the sole exception — so all five
were permanently live and could not reuse `enter`, `up`/`down` or `esc`, which
`editor.submit`, motion and the `app.cancel` floor already held.

Neither shape available at the time fixed it:

- The overlay as **`Owning`** pushes onto the ownership stack and **suspends**
  the surface beneath. The editor stops receiving keys, so the user can no longer
  type to narrow the candidate list — which is half the gesture.
- The overlay declaring **the editor as its focused component** puts `editor`
  back at layer 1, innermost, reclaiming exactly the keys it was meant to free.

A thirteenth binding context therefore looked useless, and the enum was left
closed at twelve.

## What was actually wrong

The two shapes above are the only ones available because "is on the ownership
stack" and "contributes a binding context" were **one thing**. The chain's layer
2 was defined as *the top non-suspended, non-hidden ownership-stack entry*, so
the only way to reach the keymap was to take ownership, and the only way to take
ownership was to suspend whoever had it.

Those are two independent properties. An overlay that owns no input can still
have a namespace of its own, and the completion overlay is the case that needs
exactly that: it advises, it does not own.

Cutting the coupling makes a thirteenth context work after all. `completion`
sits innermost and is in the chain only while the overlay is **shown**, so it
takes `enter`, `tab`, the arrows and `esc` while shown and gives all of them back
when hidden. Printable keys match nothing in it, fall through to `editor`, match
nothing there either, and become text insertion — which is not a binding and has
no entry in the namespace. That existing non-binding fall-through is what makes
the whole thing work; no new mechanism was needed for it.

## Rejected: a third overlay kind

The alternative was a third declaration beside `Owning` and `Transient` — an
overlay that pushes onto the stack without suspending the entry beneath.

It reaches the same behaviour and costs more. The ownership stack stops being a
LIFO of exclusive owners, and *"the top non-suspended, non-hidden entry owns
input"* stops having one answer: with a non-suspending entry on top, both it and
the entry beneath are receiving keys. Every rule written against the stack —
suspend and resume, the six-step teardown order, the marker rule that resolves
against the top of the stack — would need re-reading against a stack whose top is
no longer the owner.

The advisory context touches none of that. `Transient` already meant "owns no
input", which was always the correct classification for this overlay; the defect
was that it also meant "invisible to the keymap".

## Chain membership is not a state-dependent binding

Making the chain depend on whether an overlay is shown is the same kind of thing
the driver already does when it puts `transcript` in the chain in fullscreen and
leaves it out in scrollback. What is banned is a **binding** whose validity
depends on the immediately preceding action. These are different axes, and the
ban is untouched.

## Consequences

- The binding-context enum is **thirteen**, still closed at compile time.
- The five ids split across two contexts. `editor.completion_open` stays in
  `editor` — an opening action lives in the narrowest context guaranteed live
  before its target exists — and `accept`, `next`, `prev`, `cancel` move to
  `completion`. The total stays 103.
- `tab` resolves to two ids, one per context: opening with the overlay hidden,
  accepting with it shown. The no-two-ids-share-a-key assertion is per context,
  so this is not a collision.
- **The shadowing assertion had to be restated.** Its positional form banned a
  layer-2 context from reusing a layer-1 key beneath it, which an advisory
  context does on purpose. The property it was approximating is that **no id may
  be shadowed in every chain it appears in** — sometimes-shadowing is fine and
  already relied upon, as with the seven layer-2 `close` ids over `app.cancel` on
  `esc`. The restated form is enforced against an explicit table of assemblable
  chains, and it closes a hole: the positional form never compared layer 2
  against layer 3 at all, so those seven ids passed by omission rather than by
  rule. It carries one extra clause, because reachable *somewhere* is not enough
  for the floor: an `app` id must additionally win in the base surface chain.
- A chain holds **at most one** advisory context. Two would need an ordering
  between them and nothing asks for a second.
