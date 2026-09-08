# Keybindings: key vocabulary, resolution, and the default set

Non-goals:

- Modal editing. A binding context is never a mode; normal mode is unexpressible.
- Multi-chord sequences. One binding is one chord; `C-x C-s` has no spelling.
- Platform-conditional chains. v1 ships one table for all three platforms.
- Bindings that depend on the previous action. `editor.yank_pop` is the sole exception.

## 1. The key vocabulary

The action namespace is closed at 103 ids across 13 binding contexts. The *key*
side needs the same treatment: a closed enum known at compile time.

A **key** is `modifier* key_name`, joined by `+`.

**Modifiers**, in canonical order — `ctrl`, `alt`, `shift`, `super`. The parser
accepts any order; the serializer emits this one, so `shift+ctrl+a` and
`ctrl+shift+a` are one key rather than two.

**Key names** are `snake_case` and closed:

| Family | Names |
|---|---|
| Text | `enter`, `tab`, `space`, `backspace`, `delete`, `esc` |
| Navigation | `up`, `down`, `left`, `right`, `home`, `end`, `page_up`, `page_down`, `insert` |
| Function | `f1` … `f12` |
| Character | the **unshifted** printable character, named where it is not a letter or digit: `comma`, `period`, `slash`, `backslash`, `semicolon`, `quote`, `grave`, `minus`, `equal`, `bracket_left`, `bracket_right` |

Characters are named unshifted and `shift` is always explicit, so `alt+<` is
written `alt+shift+comma`. Without this, `alt+<` and `alt+shift+comma` are two
spellings of one key and the closed enum leaks.

`super` is in the grammar because the brief puts it there. **No default binding
uses it**: it has no legacy encoding at all, and VTE does not read the modifier
bit, so `super+x` is byte-identical to `x`.

## 2. Resolution

Two orthogonal mechanisms, already fixed upstream:

- The **context chain** decides which action id a key resolves to — advisory
  context, then focused component, then owner, then `app`, first match
  innermost-wins.
- The **binding chain** decides which key fires an action, filtered by reachability.

An **advisory context** is contributed by an overlay that owns no input. It sits
innermost, and it is in the chain only while its overlay is **shown** — so it
shadows the focused component while shown and vanishes otherwise. This is the
same kind of state the driver already resolves when it puts `transcript` in the
chain in fullscreen and leaves it out in scrollback; it is not a binding that
depends on the previous action, which stays banned.

`completion` is the only advisory context in v1, and **a chain holds at most
one**: two would need an ordering between them, and nothing asks for a second.

Because an advisory context binds no bare printable, typing still falls through
it to the component beneath and on into text insertion — which is not a binding
and never appears in the namespace. That fall-through is what lets the candidate
list keep narrowing while the overlay holds `enter`, `tab`, the arrows and `esc`.

**Every reachable key in a binding chain is live.** The chain is still a
preference order — its first reachable key is what help text displays, and it is
what the orphan test reports — but a second key is a genuine second binding, not
a dormant understudy. This matters twice in the default set: `select_toggle`
carries `alt+i` beside `ctrl+space` because an input-method grab is not
observable and a fallback keyed on reachability would never fire; and the presets
can lead with their idiomatic key while keeping the default one live.

An **orphaned** action is one whose chain has no reachable key. It is the only
condition that speaks to the user. An **empty** chain is deliberate disablement
and is silent.

## 3. Invariants the default set must satisfy

All four are build assertions, not review items.

1. **No two ids in one context share a key.** Within a context, first-match has
   nothing to disambiguate.
2. **No id may be shadowed in every chain it appears in.** Keys resolve
   innermost-first, so an id whose key is claimed by a context inner to it is
   unreachable *in that chain*; it is a defect only when no assemblable chain is
   left in which it wins. This is what removed `sessions.switch` and
   `session_tree.confirm` — `select_list` sits beneath both in *every* chain, so
   `enter` never arrived. It is also what permits the sanctioned shadowing:
   seven layer-2 `close` ids over `app.cancel` on `esc`, `single_line_input`
   over `settings.filter_focus` on `ctrl+f` once the filter is focused, and
   `completion` over `editor.submit` on `enter` while the overlay is shown.
   Those inner contexts are in the chain only sometimes.

   The assertion is enforced against an explicit table of **assemblable
   chains**, which the earlier positional form approximated. The positional form
   also never compared layer 2 against layer 3, so the seven `esc` ids passed by
   omission rather than by rule.

   **Floor clause:** reachable *somewhere* is not enough for `app`. The floor
   exists to be live while the user is typing, so an `app` id must additionally
   win in the base surface chain, evaluated with no advisory context present.
3. **A context whose chain can contain a text-entry component may not bind a bare
   printable character.** A bare `y` in `transcript` would resolve to `copy` and
   never reach text insertion. The set is **derived from the chain table**, not
   listed by hand: `transcript`, `search`, `settings`, `branch_summary`,
   `completion`, `dialog` and `app`. Bare letters are available only in
   `session_tree`, `sessions` and `picker`, whose layer 1 is `select_list` alone.
4. **`ctrl+shift+<letter>` may not appear.** Under legacy encoding it is
   byte-identical to `ctrl+<letter>`, so it does not degrade — it fires a
   different action's binding. This is stronger than the reachability filter,
   which cannot see the collision.

## 4. Legacy reachability, as it bears on the defaults

Survey extends `docs/research/terminal-keyboard-protocols.md` to the non-Enter
key classes; VTE with defaults is the worst case.

**Reachable, no fallback needed** — `ctrl+<letter>` (excluding `i`, `m`, `j`,
`h`, `[`, which alias `tab`/`enter`/LF/`backspace`/`esc`); `alt+<letter>` and
`alt+shift+<letter>`; bare arrows, `home`, `end`, `page_up`, `page_down`,
`delete`; `ctrl`/`shift`/`alt` + arrow; `ctrl+home`, `ctrl+end`; `shift+tab`;
`backspace`, `ctrl+backspace`, `alt+backspace`; `f1`–`f9`, `f12` with or without
`ctrl`/`shift`/`alt`; `ctrl+space`.

The surprise is that VTE implements xterm's `modifyCursorKeys`/`modifyFunctionKeys`
scheme in full — its gap is confined to *text* keys, which is exactly the
`modifyOtherKeys` domain it refuses. Modified arrows were assumed lost and are not.

**Unusable, and why** — `ctrl+shift+<letter>`, `ctrl+tab`, `ctrl+shift+tab`,
`ctrl+1`/`ctrl+9`/`ctrl+0`/`ctrl+;`, `shift+space`, `shift+backspace` and
`super+*` are indistinguishable by construction. The `insert` family, `shift+f10`,
`f11`, `ctrl+page_up`/`ctrl+page_down`, `alt+<digit>`, `alt+space` and `alt+tab`
encode correctly but are intercepted by VTE, GNOME Terminal or the window manager
before delivery.

**The alternate-screen lever** — VTE steals `ctrl+shift+arrow`, `shift+page_up`/
`shift+page_down` and `shift+home`/`shift+end` **only on the normal screen**. In
the alternate screen they arrive intact. `transcript` is fullscreen-only, i.e.
alternate-screen-only, which is why `scroll_top`/`scroll_bottom` can take
`shift+home`/`shift+end` and stay clear of the editor's `home`/`end`.

`Backspace`: read `kbs` from terminfo rather than hardcoding `0x7f` or `0x08` —
which of the two is "plain" is not fixed, and `ctrl+backspace` is the other one.

## 5. Platform conditionality

`app.suspend` is bound on every platform and **reports rather than acting** on
Windows, so its chain does not vary. With `super` banned and the Enter family
handled by the reachability ladder, **no chain varies across `windows | wsl |
unix`** — v1 ships one table.

The three-arm mechanism is still specified, because WSL is a **runtime**
distinction: it is Linux at compile time, so `cfg!` cannot express it and a
derived default would document only the platform that built the binary. Defaults
therefore ship as an **embedded asset** selected at run time, not as a `Default`
impl; the doc-comment carrying each key's *effect* still comes from the Rust type.
The generator emits all three arms. Today they are identical, and that identity is
itself the decision: a user moving between WSL and Windows meets one keymap.

## 6. Presets

Shipped as **example assets the user copies**, not as a `preset = "emacs"` config
key. Keybindings are a two-layer config axis, global and project; a preset key
would smuggle in a third merge layer.

```
tp keymap export emacs > ~/.config/tp/keybindings.toml
```

`assets/keymaps/emacs.toml` covers `editor` and `single_line_input`. Every `C-x`
and `C-c` prefixed command is unexpressible — one chord per binding, no sequences.

`assets/keymaps/vim.toml` is Vim-**flavoured**. It touches `editor` only to free
`ctrl+e`/`ctrl+y`/`ctrl+f`/`ctrl+b` for the transcript; `hjkl` in the editor would
replace typing with motion, and without a normal mode there is nothing to switch
out of. `gg`/`G`/`y` in the transcript are unavailable under invariant 3.

## 7. The completion overlay

The overlay owns no input: it stays `Transient`, never enters the ownership
stack, and never suspends the editor. What it declares at open is an **advisory
context**, `completion`, and that is the whole of the change to the ownership
model — suspend, resume and the fixed teardown order are untouched.

The five ids split across two contexts, because an opening action lives in the
narrowest context guaranteed live *before* its target exists:

```toml
[editor]
completion_open = ["tab"]

[completion]
accept = ["tab", "enter"]
next   = ["down", "ctrl+n"]
prev   = ["up", "ctrl+p"]
cancel = ["esc"]
```

`tab` therefore resolves to two ids: `editor.completion_open` with the overlay
hidden, `completion.accept` with it shown. Invariant 1 is per context, so this is
not a collision. `ctrl+n`/`ctrl+p` shadow `editor.cursor_down`/`cursor_up` on
purpose — "move down" is one intention either way. That is already what the
Emacs preset would ask for, so its `completion` block overrides `cancel` alone,
taking `ctrl+g` for keyboard-quit; the advisory context is innermost and present
only while shown, so `ctrl+g` stays `editor.select_clear` everywhere else, which
the old preset could not manage and worked around with `alt+g`.

`editor.completion_open` covers the two cases a trigger character does not:
invoking with no trigger in the buffer, and re-opening after `cancel` with the
trigger still there. Typing `@` or `/` is text insertion, so it opens the overlay
without passing through the namespace at all.

**Shown, not open.** The advisory context is in the chain only while the overlay
is shown, and an overlay whose candidate list is empty is not shown — the
existing rule that a hidden overlay contributes no context does the work, with no
gate of its own. With no candidates, `enter` submits.

Implicit dismissal — the cursor leaving the trigger region, an edit emptying the
list, `submit`, or focus leaving the editor — is component behaviour, not a
binding. It gets no ids, deliberately.
