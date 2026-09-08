# Keybindings: key vocabulary, resolution, and the default set

Non-goals:

- Modal editing. A binding context is never a mode; normal mode is unexpressible.
- Multi-chord sequences. One binding is one chord; `C-x C-s` has no spelling.
- Platform-conditional chains. v1 ships one table for all three platforms.
- Bindings that depend on the previous action. `editor.yank_pop` is the sole exception.

## 1. The key vocabulary

The action namespace is closed at 103 ids across 12 binding contexts. The *key*
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

- The **context chain** decides which action id a key resolves to — focused
  component, then owner, then `app`, first match innermost-wins.
- The **binding chain** decides which key fires an action, filtered by reachability.

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
2. **A layer-2 context may not reuse a key held by a layer-1 context that can
   appear beneath it in the same chain.** The inner one wins and the outer id is
   unreachable by construction. This is what removed `sessions.switch` and
   `session_tree.confirm`, both shadowed by `select_list.accept` on `enter`.
3. **A context whose chain can contain a text-entry component may not bind a bare
   printable character.** `transcript` sits over a focused `editor`; `search`,
   `settings` and `branch_summary` can hold a focused `single_line_input`. A bare
   `y` in `transcript` would resolve to `copy` and never reach text insertion.
   Bare letters are available only in `session_tree`, `sessions` and `picker`,
   whose layer 1 is `select_list` alone.
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
