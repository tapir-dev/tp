# Terminal keyboard protocols and their emulator reality

Research note for [issue #7](https://github.com/tapir-dev/tp/issues/7). Survey date: **2026-09-07**.

Terminal input is where a TUI silently breaks. This note establishes the actual
wire encodings, the negotiation handshakes, and which emulators really implement
them — with literal escape bytes rather than generalities.

**Every escape sequence below carries a verification marker.** An unverified
sequence is worse than a gap, so derived-but-not-literally-published sequences
are marked as such rather than presented as quotations.

| Marker | Meaning |
| --- | --- |
| `[D]` | Verified — the byte sequence or claim appears literally in primary documentation |
| `[S]` | Verified — read out of the terminal's own source code or changelog |
| `[E]` | Verified empirically — reproduced against a running binary during this survey |
| `[X]` | Derived — follows arithmetically from a documented rule, but is not printed in any source |
| `[I]` | Inferred from an open issue (an open "please support X" ticket is evidence of non-support) |
| `[?]` | Could not confirm — treat as unknown, not as absence |

---

## 1. Executive summary

1. **There are three encoding schemes, not two.** Legacy (no enhancement), xterm's
   `modifyOtherKeys` — which has *two* wire formats selected by `formatOtherKeys` —
   and the Kitty keyboard protocol. "CSI-u" is ambiguous terminology: it names both
   the 2013 fixterms proposal *and* one of `modifyOtherKeys`' output formats *and*
   the family of kitty sequences. This note keeps them separate.

2. **The Kitty protocol has effectively won, and 2026 was the year it did.** Windows
   Terminal (v1.25, Feb 2026), VS Code / xterm.js (1.109, Jan 2026) and Konsole
   (26.08, Aug 2026) all shipped it within eight months of each other. **Any
   compatibility table older than about twelve months is now wrong on those three.**

3. **VTE (GNOME Terminal, and every VTE-based terminal) is the last major holdout**
   and supports *neither* protocol. Its `modifyOtherKeys` request issue has been open
   since **2007**. This is the emulator that fundamentally cannot distinguish
   `Ctrl+Enter` or `Shift+Enter` from plain `Enter`, and — unlike every other
   terminal in this survey — it offers **no user-side workaround** at all.

4. **The tmux "full server restart" folklore is wrong, and in a useful way.** The
   real requirement is a **client reattach**, which is much cheaper to ask of a
   user. This was established from tmux source and confirmed empirically (§7.3).

5. **tmux collapses a kitty-protocol terminal down to `modifyOtherKeys`-class
   fidelity.** tmux does not implement the Kitty protocol and does not pass it
   through; `CSI ? u` inside a tmux pane returns *silence*, not a negative answer.
   Key release, repeat, alternate-key and associated-text reporting are all lost.

6. **Defaults matter more than capability.** WezTerm is the only surveyed terminal
   that ships Kitty protocol support switched **off** by default.

---

## 2. The three schemes at a glance

| | Legacy | xterm `modifyOtherKeys` | Kitty keyboard protocol |
| --- | --- | --- | --- |
| Origin | VT100 lineage | xterm (Thomas Dickey) | kitty 0.20.0, 2021-04-19 `[D]` |
| Enable | n/a | `\x1b[>4;2m` `[D]` | `\x1b[>1u` (push) `[D]` |
| Query | n/a | `\x1b[?4m` `[D]` | `\x1b[?u` `[D]` |
| Reply | n/a | `\x1b[>4;2m` `[S]` | `\x1b[?<flags>u` `[S]` |
| Disable | n/a | `\x1b[>4m` (reset) / `\x1b[>4n` (off) `[D]` | `\x1b[<u` (pop) `[D]` |
| State model | flat resource | flat resource | **stack**, separate per screen `[D]` |
| Modifier field | `1 + bitmask` `[D]` | `1 + bitmask` `[D]` | `1 + bitmask` `[D]` |
| Modifiers covered | — | shift, alt, ctrl, meta | + super, hyper, meta, caps/num lock `[D]` |
| Key release events | no | **no** | **yes**, flag `0b10` `[D]` |
| Repeat events | no | no | yes `[D]` |
| Machine-queryable | no | yes (XTQMODKEYS) | yes, and stack-safe `[D]` |

The Kitty spec's own critique of `modifyOtherKeys` is worth recording verbatim,
because it is the design rationale for preferring the newer protocol: no release
events; doesn't fix the Escape ambiguity; doesn't fix identical-byte keypresses;
*"There is no robust way to query it or manage its state from a program running in
the terminal"*; no shifted keys; no alternate layouts; no modifiers beyond the
basic four; no lock keys; *"Is completely unspecified."*
([kitty spec](https://sw.kovidgoyal.net/kitty/keyboard-protocol/)) `[D]`

---

## 3. THE TABLE: `Ctrl+Enter`, `Shift+Enter`, `Alt+Enter` under each scheme

`Enter`'s key code is **13** (`0x0D`) in every scheme — not 10. Verified twice
independently: kitty's functional key table gives `ENTER  13 u` `[D]`, and
Dickey's generated xterm key table gives `0xff0d | XK_Return | 65293` with all
sequences using `13` `[D]`.

### 3.1 Legacy — no enhancement active

| Key | Bytes | ESC form | Status |
| --- | --- | --- | --- |
| `Enter` | `\x0d` | `CR` | `[D]` |
| `Ctrl+Enter` | `\x0d` | `CR` | `[D]` |
| `Shift+Enter` | `\x0d` | `CR` | `[D]` |
| `Ctrl+Shift+Enter` | `\x0d` | `CR` | `[D]` |
| `Alt+Enter` | `\x1b\x0d` | `ESC CR` | `[X]` |
| `Ctrl+Alt+Enter` | `\x1b\x0d` | `ESC CR` | `[X]` |

Source for the `CR` rows: kitty's "C0 controls" table, which tabulates legacy-mode
output for all eight modifier combinations of `Enter` and gives
`"0xd", "0xd", "0x1b 0xd", "0xd", "0xd", "0x1b 0xd", "0x1b 0xd"` `[D]`.

**The `Alt+Enter` caveat.** `\x1b\x0d` is marked derived because no source fetched
tabulates it directly for `Return`. It follows from xterm's documented generic rule
(`Alt-x` produces `ESC x` when `metaSendsEscape` is set) applied to `Return`, whose
`XLookupString` byte is `\r`. Dickey's own generated table shows plain `\r` in the
`-a--` row because the generator does not model `metaSendsEscape`. In practice
every modern non-xterm emulator ships ESC-prefix as the default, so `\x1b\x0d` is
the effectively-universal legacy `Alt+Enter` — but note that xterm's *own* default
is `metaSendsEscape: False` with `eightBitInput: true`, which would instead give
the high-bit form `0x8D` (or `0xC2 0x8D` in a UTF-8 locale) `[D]`.

**This row is the whole problem.** Under legacy encoding, `Ctrl+Enter`,
`Shift+Enter` and plain `Enter` are byte-identical. No amount of application-side
cleverness recovers the distinction; the information was destroyed in the emulator.

### 3.2 `modifyOtherKeys` — xterm format (`formatOtherKeys = 0`, the default)

Enable with `\x1b[>4;2m`. Wire form is `CSI 27 ; <modifier> ; <keycode> ~` — the
literal `27` is "function key 27", which is why xterm's manual describes it as
"parameters for function-key 27" `[D]`.

| Key | Bytes | ESC form | Status |
| --- | --- | --- | --- |
| `Enter` | `\x0d` | `CR` | `[D]` |
| `Shift+Enter` | `\x1b[27;2;13~` | `ESC [ 2 7 ; 2 ; 1 3 ~` | `[D]` |
| `Alt+Enter` | `\x1b[27;3;13~` | `ESC [ 2 7 ; 3 ; 1 3 ~` | `[D]` |
| `Shift+Alt+Enter` | `\x1b[27;4;13~` | `ESC [ 2 7 ; 4 ; 1 3 ~` | `[D]` |
| `Ctrl+Enter` | `\x1b[27;5;13~` | `ESC [ 2 7 ; 5 ; 1 3 ~` | `[D]` |
| `Ctrl+Shift+Enter` | `\x1b[27;6;13~` | `ESC [ 2 7 ; 6 ; 1 3 ~` | `[D]` |
| `Ctrl+Alt+Enter` | `\x1b[27;7;13~` | `ESC [ 2 7 ; 7 ; 1 3 ~` | `[D]` |
| `Ctrl+Shift+Alt+Enter` | `\x1b[27;8;13~` | `ESC [ 2 7 ; 8 ; 1 3 ~` | `[D]` |

All eight rows are quoted directly from Dickey's generated reference table,
[modified-keys-us-pc105.html](https://invisible-island.net/xterm/modified-keys-us-pc105.html),
under "Other modifiable keycodes".

> **Correction to a widely-repeated claim.** xterm's manual says `modifyOtherKeys`
> *"does not apply to special keys, i.e. cursor-, keypad-, function- or control-keys
> which are labeled on your keyboard"*, which reads as though `Return` is excluded.
> **It is not.** xterm's `input.c` explicitly special-cases `XK_Return` *into* the
> encoded set at **both** mode 1 and mode 2 `[S]`:
>
> ```c
> case 1:
>     case XK_Return:
>     case XK_Tab:
>         result = (modify_parm != 0);   /* Return IS encoded in mode 1 */
> ```
>
> and in `allowedCharModifiers()`, where modes 0/1 normally strip Ctrl/Shift,
> `XK_Tab` and `XK_Return` fall into an explicitly empty branch so that **no
> modifiers are stripped**. The generated table agrees, showing `-*******` for
> `XK_Return` at both mode 1 and mode 2. So `Ctrl+Enter` works at
> `modifyOtherKeys=1`, and you do not need mode 2 for it.
>
> Contrast the neighbours: `Escape` is encoded for alt only at mode 1 and fully at
> mode 2; `BackSpace` is **never** encoded at mode 1.

### 3.3 `modifyOtherKeys` — CSI-u format (`formatOtherKeys = 1`) and fixterms

Select the format with `\x1b[>4;1f` `[D]`. Wire form is
`CSI <codepoint> ; <modifier> u` — the same data, reordered. xterm's own docs note
the drawback: *"applications may confuse it with `CSI u` (restore-cursor)"* `[D]`.

This is also exactly the [fixterms](http://www.leonerd.org.uk/hacks/fixterms/)
encoding (Paul Evans, 2013), and what tmux emits under
`extended-keys-format csi-u`.

| Key | Bytes | ESC form | Status |
| --- | --- | --- | --- |
| `Enter` | `\x0d` | `CR` | `[D]` |
| `Shift+Enter` | `\x1b[13;2u` | `ESC [ 1 3 ; 2 u` | `[D]` |
| `Alt+Enter` | `\x1b[13;3u` | `ESC [ 1 3 ; 3 u` | `[X]` |
| `Ctrl+Enter` | `\x1b[13;5u` | `ESC [ 1 3 ; 5 u` | `[D]` |
| `Ctrl+Shift+Enter` | `\x1b[13;6u` | `ESC [ 1 3 ; 6 u` | `[X]` |

fixterms prints `Shift-Enter = CSI 13;2 u` and `Ctrl-Enter = CSI 13;5 u`
verbatim `[D]`. The `Alt` rows follow from `1 + alt(2) = 3` but are not tabulated
anywhere, hence `[X]`.

tmux's man page independently corroborates the pairing of the two formats, using
`C-S-a` as its worked example: `^[[27;6;65~` under `xterm` format versus
`^[[65;6u` under `csi-u` `[D]`.

### 3.4 Kitty keyboard protocol

Behaviour depends on which flags are active — this is the subtlety that catches
implementers out.

**Under flag `0b1` (disambiguate) alone** — plain `Enter` is **still** `\x0d`:

| Key | Bytes | ESC form | Status |
| --- | --- | --- | --- |
| `Enter` | `\x0d` | `CR` | `[D]` |
| `Shift+Enter` | `\x1b[13;2u` | `ESC [ 1 3 ; 2 u` | `[X]` |
| `Alt+Enter` | `\x1b[13;3u` | `ESC [ 1 3 ; 3 u` | `[X]` |
| `Ctrl+Enter` | `\x1b[13;5u` | `ESC [ 1 3 ; 5 u` | `[X]` |
| `Ctrl+Shift+Enter` | `\x1b[13;6u` | `ESC [ 1 3 ; 6 u` | `[X]` |

The spec is explicit that plain `Enter` is exempt: *"The only exceptions are the
`Enter`, `Tab` and `Backspace` keys which still generate the same bytes as in
legacy mode — this is to allow the user to type and execute commands in the shell
such as `reset` after a program that sets this mode crashes without clearing
it."* `[D]`

**Under flag `0b1000` (report all keys as escape codes)** — `Enter` becomes a CSI u
sequence too:

| Key | Bytes | ESC form | Status |
| --- | --- | --- | --- |
| `Enter` | `\x1b[13u` | `ESC [ 1 3 u` | `[X]` |
| `Shift+Enter` | `\x1b[13;2u` | `ESC [ 1 3 ; 2 u` | `[X]` |
| `Alt+Enter` | `\x1b[13;3u` | `ESC [ 1 3 ; 3 u` | `[X]` |
| `Ctrl+Enter` | `\x1b[13;5u` | `ESC [ 1 3 ; 5 u` | `[X]` |
| `Ctrl+Shift+Enter` | `\x1b[13;6u` | `ESC [ 1 3 ; 6 u` | `[X]` |

> **Honesty note on `[X]` in this section.** `\x1b[13;5u` for `Ctrl+Enter` is
> universally quoted in blog posts as "the kitty sequence for Ctrl+Enter", and it
> **is** correct — but it is **not literally printed anywhere in the kitty spec**.
> The spec contains no worked `Enter`+modifier CSI-u example at all. It is derived
> from three separately-verified facts: `ENTER = 13 u` from the functional key
> table `[D]`, the modifier field rule `1 + 0b100 = 5` `[D]`, and the disambiguate
> rule that modified `Enter` leaves legacy encoding `[D]`. It was additionally
> checked against the branch structure of `kitty/key_encoding.c` `[S]`, where
> `legacy_mode` is false once `disambiguate` is set, both `\r` shortcuts are
> skipped for non-zero modifiers, and execution reaches `S(13, 'u')`.
>
> The fixterms spec *does* print `Ctrl-Enter = CSI 13;5 u` literally `[D]`, and
> kitty is a superset of fixterms for this case — which is the strongest
> independent corroboration available.

**Release and repeat events** (require flag `0b10`):

| Event | Bytes | ESC form | Status |
| --- | --- | --- | --- |
| `Ctrl+Enter` release | `\x1b[13;5:3u` | `ESC [ 1 3 ; 5 : 3 u` | `[X]` |
| `Ctrl+Enter` repeat | `\x1b[13;5:2u` | `ESC [ 1 3 ; 5 : 2 u` | `[X]` |
| `Shift+Enter` release | `\x1b[13;2:3u` | `ESC [ 1 3 ; 2 : 3 u` | `[X]` |
| plain `Enter` release (needs `0b10` + `0b1000`) | `\x1b[13;1:3u` | `ESC [ 1 3 ; 1 : 3 u` | `[X]` |

The mandatory `;1` on the unmodified form is spec-verbatim: *"If no modifiers are
present, the modifiers field must have the value `1` and the event type sub-field
the type of event."* `[D]`

### 3.5 The one-glance comparison

| Scheme | `Enter` | `Ctrl+Enter` | `Shift+Enter` | `Alt+Enter` |
| --- | --- | --- | --- | --- |
| Legacy | `\x0d` | `\x0d` | `\x0d` | `\x1b\x0d` |
| `modifyOtherKeys` (xterm fmt) | `\x0d` | `\x1b[27;5;13~` | `\x1b[27;2;13~` | `\x1b[27;3;13~` |
| `modifyOtherKeys` (CSI-u fmt) / fixterms | `\x0d` | `\x1b[13;5u` | `\x1b[13;2u` | `\x1b[13;3u` |
| Kitty, flag `0b1` | `\x0d` | `\x1b[13;5u` | `\x1b[13;2u` | `\x1b[13;3u` |
| Kitty, flag `0b1000` | `\x1b[13u` | `\x1b[13;5u` | `\x1b[13;2u` | `\x1b[13;3u` |

Note the first column: **only kitty flag `0b1000` changes plain `Enter`**. Every
other scheme leaves `\x0d` alone, deliberately, so that `reset` still works at a
shell prompt after a crashed TUI.

---

## 4. The modifier field

All three schemes use **`1 + bitmask`**. The `+1` exists because a missing CSI
parameter conventionally defaults to `1`.

Kitty's bitmask `[D]`, confirmed against `kitty/key_encoding.c` `[S]`:

| Modifier | Bit | Value |
| --- | --- | --- |
| `shift` | `0b1` | 1 |
| `alt` | `0b10` | 2 |
| `ctrl` | `0b100` | 4 |
| `super` | `0b1000` | 8 |
| `hyper` | `0b10000` | 16 |
| `meta` | `0b100000` | 32 |
| `caps_lock` | `0b1000000` | **64** |
| `num_lock` | `0b10000000` | **128** |

> **Correction worth flagging:** several secondary write-ups (and the rendered HTML
> of the spec as processed by some readers) list `num_lock = 64, caps_lock = 128`.
> The reStructuredText source of the spec and `key_encoding.c` **both** give
> `CAPS_LOCK = 64, NUM_LOCK = 128`. Trust the source.

xterm's equivalent table stops at `meta = 8`, producing modifier codes 2 through
16 `[D]`. fixterms stops at `ctrl = 4`. Values 1-8 are therefore **identical
across all three schemes**, which is why a single decoder handles all of them.

Resulting field values:

| Modifiers | bitmask | field |
| --- | --- | --- |
| none | 0 | 1 |
| shift | 1 | **2** |
| alt | 2 | **3** |
| shift+alt | 3 | 4 |
| ctrl | 4 | **5** |
| ctrl+shift | 5 | 6 |
| ctrl+alt | 6 | 7 |
| ctrl+alt+shift | 7 | 8 |
| super | 8 | 9 |

---

## 5. Kitty protocol: flags, negotiation, detection

### 5.1 The five progressive-enhancement flags `[D]`

| Bit | Name | Effect |
| --- | --- | --- |
| `0b1` (1) | Disambiguate escape codes | `Esc`, `alt+key`, `ctrl+key`, `ctrl+alt+key`, `shift+alt+key` reported as `CSI u` instead of legacy. **`ctrl+c` no longer generates `SIGINT`.** `Enter`/`Tab`/`Backspace` exempt when unmodified. Lock modifiers not reported for text-producing keys. |
| `0b10` (2) | Report event types | Enables key **repeat** and **release** events. |
| `0b100` (4) | Report alternate keys | Adds shifted / base-layout key codes as sub-fields, to aid shortcut matching. Only affects events already being sent as escape codes. |
| `0b1000` (8) | Report all keys as escape codes | Text-producing keys stop sending text; modifier keypresses become reportable; `Enter`/`Tab`/`Backspace` included. **Implies disambiguation.** |
| `0b10000` (16) | Report associated text | Embeds the generated text as codepoints in the escape code. **Explicitly undefined if used without flag 8.** |

Trap when cross-reading kitty's C source: the struct field named `report_text` is
flag **8** (report all keys), while flag 16 is `embed_text` `[S]`.

### 5.2 Negotiation sequences `[D]`

| Purpose | Spec form | Literal bytes |
| --- | --- | --- |
| Query current flags | `CSI ? u` | `\x1b[?u` |
| Terminal's reply | `CSI ? flags u` | e.g. `\x1b[?5u` |
| Push flags | `CSI > flags u` | `\x1b[>1u` |
| Push, flags default 0 | `CSI > u` | `\x1b[>u` |
| Pop N entries | `CSI < number u` | `\x1b[<1u` |
| Pop, default 1 | `CSI < u` | `\x1b[<u` |
| Set flags | `CSI = flags ; mode u` | `\x1b[=1;1u` |

`mode` defaults to 1. **1** = set all bits to the given value; **2** = OR the set
bits in, leave others; **3** = AND-NOT the set bits out, leave others `[D]`,
confirmed in `screen.c` `[S]`.

**Lifecycle**, from the spec's own Quickstart `[D]`: send `\x1b[>1u` at startup or
on entering the alternate screen; send `\x1b[<u` on exit or before leaving it.

### 5.3 The detection handshake that does not hang

This is the load-bearing detail. Quoting the spec `[D]`:

> An application can query the terminal for support of this protocol by sending the
> escape code querying for the current progressive enhancement status followed by
> request for the primary device attributes. If an answer for the device attributes
> is received without getting back an answer for the progressive enhancement the
> terminal does not support this protocol.

Combined byte string: **`\x1b[?u\x1b[c`** — i.e. `ESC [ ? u` then `ESC [ c`.

Marked `[X]` for the concatenation: both halves and the decision logic are
spec-verbatim, but the joined literal is not printed. kitty's own
`kittens/query_terminal` uses exactly this pattern, terminating on a CSI reply
ending in `c` `[S]`.

Because DA1 is answered by essentially every terminal ever made, this bounds the
wait: you get *some* reply, and the presence or absence of the `CSI ? … u` reply
before it is your answer. **Never wait on `\x1b[?u` alone** — a non-supporting
terminal simply says nothing, and you would hang for your full timeout.

**Detecting partial implementations.** The spec strongly encourages terminals to
implement all five flags, and notes applications can detect partial support by
*"first setting the desired progressive enhancements and then querying for the
current progressive enhancement"* `[D]` — i.e. send `\x1b[=15;1u`, then `\x1b[?u`,
and compare what comes back against what you asked for.

### 5.4 State model

- **Separate stacks for main and alternate screens** `[D]`. This is deliberate:
  an editor can change the mode in the alt screen without knowing or disturbing
  the main screen's mode.
- **If a pop empties the stack, all flags reset** `[D]`.
- If a push overflows, the oldest entry is evicted `[D]`.
- **Reset (RIS/DECSTR) behaviour is unspecified.** kitty's implementation zeroes
  both stacks on both soft and hard reset `[S]`, but Ghostty's RIS documentation
  does not list kitty flags among what it resets `[D]`. **Do not rely on RIS to
  restore keyboard state** — pop explicitly.

---

## 6. Legacy control sequences reference

Set/reset via **XTMODKEYS**, `CSI > Pp ; Pv m`, where `Pp` selects the resource `[D]`:

| `Pp` | Resource |
| --- | --- |
| 0 | `modifyKeyboard` |
| 1 | `modifyCursorKeys` |
| 2 | `modifyFunctionKeys` |
| 3 | `modifyKeypadKeys` |
| **4** | **`modifyOtherKeys`** |
| 6 | `modifyModifierKeys` |
| 7 | `modifySpecialKeys` |

| Purpose | ESC form | Bytes | Status |
| --- | --- | --- | --- |
| Enable mode 2 | `ESC [ > 4 ; 2 m` | `\x1b[>4;2m` | `[D]` |
| Enable mode 1 | `ESC [ > 4 ; 1 m` | `\x1b[>4;1m` | `[D]` |
| Reset to initial value | `ESC [ > 4 m` | `\x1b[>4m` | `[D]` |
| Reset **all** `modify*` resources | `ESC [ > m` | `\x1b[>m` | `[D]` |
| Disable (resource `-1`) | `ESC [ > 4 n` | `\x1b[>4n` | `[D]` |
| Query (XTQMODKEYS) | `ESC [ ? 4 m` | `\x1b[?4m` | `[D]` |
| Query reply | `ESC [ > 4 ; 2 m` | `\x1b[>4;2m` | `[S]` |
| Select CSI-u output format | `ESC [ > 4 ; 1 f` | `\x1b[>4;1f` | `[D]` |
| Query format (XTQFMTKEYS) | `ESC [ ? 4 g` | `\x1b[?4g` | `[D]` |
| Factor out shift modifier | `ESC [ > 4 : 1 m` | `\x1b[>4:1m` | `[D]` |

**The query reply format is worth the `[S]`.** ctlseqs describes the reply loosely
as `CSI > Pp m`, but xterm's `charproc.c` `report_mod_fkeys()` sets
`a_nparam = 2`, so the actual reply is **`CSI > Pp ; Pv m`** — two parameters,
replayable verbatim to restore state.

`modifyOtherKeys` values `[D]`: **0** disabled; **1** enabled except keys with
well-known behaviour (but see §3.2 — `Return` and `Tab` *are* included); **2** all
modifiers apply to all ordinary keys; **3** unmodified keys are sent as escape
sequences too.

---

## 7. tmux

### 7.1 What tmux does and does not speak

**tmux does not implement the Kitty keyboard protocol, and does not pass it
through.** `input.c`'s complete CSI dispatch table contains exactly one `u`
entry — `{ 'u', "", INPUT_CSI_RCP }`, plain restore-cursor-position. There is no
handler for `>`, `<`, `?` or `=` intermediates on `u` `[S]`. A repo-wide grep for
`kitty` in `input.c`, `tty-keys.c`, `input-keys.c`, `options-table.c`, `tmux.1`
and `CHANGES` returns **zero hits** `[S]`.

Confirmed empirically inside a tmux 3.7c pane `[E]`:

```
DA (CSI c)                      -> b'\x1b[?1;2;4c'
kitty query (CSI ? u)           -> b''                <-- silence, times out
kitty push (CSI > 1 u) + query  -> b''
XTVERSION (CSI > q)             -> b'\x1bP>|tmux 3.7c\x1b\\'
DECRQM 2026 (CSI ? 2026 $ p)    -> b'\x1b[?2026;2$y'
```

Issue trail: [#3335](https://github.com/tmux/tmux/issues/3335) closed 2022-10-04
(maintainer: *"I don't mind supporting this but I don't intend to work on it"*);
PRs [#4912](https://github.com/tmux/tmux/pull/4912) and
[#5405](https://github.com/tmux/tmux/pull/5405) both **closed unmerged**; the
open [3.8 and 3.9 roadmap #5406](https://github.com/tmux/tmux/issues/5406) lists it
struck through as *"Seems to be abandoned again."* `[I]`

What tmux *does* speak: xterm `modifyOtherKeys` on both sides, and **both** wire
formats on input (`tty-keys.c`: *"Handle extended key input. This has two forms:
`\033[27;m;k~` and `\033[k;mu`"*) `[S]`.

**Practical consequence: running under tmux collapses a Kitty-protocol terminal to
`modifyOtherKeys`-class fidelity.** Key release, repeat, alternate keys,
associated text and report-all-keys are all unavailable. Modified `Enter` does
survive, because that is within `modifyOtherKeys`' reach.

### 7.2 The options

| Option | Values | Default | Since |
| --- | --- | --- | --- |
| `extended-keys` | `off` / `on` / `always` | **`off`** `[S][E]` | 3.2; `always` in 3.2a; semantics rewritten in 3.5 `[S]` |
| `extended-keys-format` | `csi-u` / `xterm` | **`xterm`** `[S][E]` | 3.5 `[S]` |
| `allow-passthrough` | `off` / `on` / `all` | **`off`** `[S][E]` | 3.3; `all` in 3.4 `[S]` |
| `escape-time` | ms | **10** (was 500 at 3.4 and earlier) `[S][E]` | 1.2 `[S]` |

Note both defaults that bite: `extended-keys` is **off**, and neither default is
stated in the current man page — both were read out of `options-table.c` and
confirmed against a running server.

Minimum working config:

```tmux
set -s extended-keys always
set -as terminal-features 'xterm*:extkeys'
```

The feature flag is spelled **`extkeys`**, lowercase, no hyphen `[D]`. Use `set -as`
(append) — a plain `set -s` replaces array entry 0. tmux auto-grants `extkeys` to
terminals it identifies via DA2/XTVERSION as `mintty`, `tmux`, `iTerm2`, `foot`,
`WezTerm`, `ghostty` or `XTerm` — notably **not** `rxvt-unicode` `[S]`.

### 7.3 What "requires a full server restart" actually means

**It means a client reattach.** The folklore overstates it, and the truth is
cheaper to ask of a user.

There are two independent gates, and only one is live at runtime.

**Outer gate (tmux to the real terminal): not live.** `extended-keys` is read on
the output side in exactly one place, `tty.c:553`:

```c
if (options_get_number(global_options, "extended-keys"))
        tty_puts(tty, tty_term_string(tty->term, TTYC_ENEKS));
```

where `Eneks` is `\E[>4;2m` `[S]`. `tty_update_features()` is reached only from
the DA/DA2/XTVERSION reply handlers and a 5-second startup timer — and the DA
request is only re-sent while the corresponding `TTY_HAVEDA*` flag is still clear.
So once the terminal has answered once, it never runs again for that client. The
chain that gets there is `server_client_open()` to `tty_open()` to
`tty_start_tty()`, i.e. **client attach**. There is no option-change hook anywhere
that re-runs terminal setup `[S]`.

Reproduced against tmux 3.7c with a pty harness watching the raw master fd `[E]`:

```
PHASE1 attach with extended-keys=off:                \033[>4;2m present: False
PHASE2 after `set -s extended-keys on` (attached):   \033[>4;2m present: False
PHASE3 after `refresh-client` / `refresh-client -S`: \033[>4;2m present: False
PHASE4 detach + reattach (option still on):          \033[>4;2m present: True
```

**Inner gate (application to tmux): live, but only on the next request.** `input.c`
reads the option at the instant a `CSI > 4 ; Ps m` arrives, so an app that
re-requests after the option changed gets the new behaviour immediately `[S][E]`.

**Therefore:**

- `tmux detach` + `tmux attach` **is sufficient** `[E]`.
- `tmux kill-server` works because it forces every client to reattach — which is
  why it became the folklore fix.
- **`source-file` / config reload alone is not enough** `[E]`. This is the trap:
  the option visibly changes, `tmux show -gv extended-keys` reports the new value,
  and keys are still silently dropped.
- **The man page documents none of this.** The `extended-keys` entry carries no
  reattach note, unlike the neighbouring `focus-events` entry which explicitly says
  *"Attached clients should be detached and attached again after changing this
  option."* `[?]` — the omission appears to be an oversight.

### 7.4 Detecting the failure rather than silently losing keys

| Technique | Verdict | Status |
| --- | --- | --- |
| `$TMUX` env var | Set in every pane; cheap, but says nothing about key handling. Absent if the client runs outside a pane. | `[E]` |
| `CSI > q` reply `DCS > \| tmux <ver> ST` | **Strongest single detector.** In-band, works even if `$TMUX` was scrubbed, and yields the version. | `[E]` |
| `tmux show -gv extended-keys` | Works from inside a pane. Returns the **policy**, not the outcome. | `[E]` |
| `tmux display -p '#{client_termfeatures}'` | Best "is the outer terminal capable" probe; must contain `extkeys`. Empty if no client attached. | `[E]` |
| `tmux display -p '#{pane_key_mode}'` | **The definitive outcome check.** Values `VT10x`, `Ext 1`, `Ext 2`. | `[E]` |
| kitty `CSI ? u` + timeout | Returns **silence** inside tmux, by construction. Never wait on it for a positive answer. | `[E]` |

**Recommended detection order** (composed from the verified primitives, `[X]` as a
sequence):

1. `CSI > q` — if the reply is `DCS > | tmux …`, you are inside tmux and know the version.
2. `tmux show -gv extended-keys` — if `off`, extended keys will be dropped. Stop and tell the user.
3. `tmux display -p '#{client_termfeatures}'` — must contain `extkeys`, else the outer terminal was never enabled.
4. Send `\x1b[>4;2m`, then read `tmux display -p '#{pane_key_mode}'` — must be `Ext 1` or `Ext 2`.
5. If step 4 still reads `VT10x` after the option reads `on`, **the user needs to reattach** — say so explicitly.

**The DCS passthrough is not a workaround for the handshake.** You can tunnel raw
escapes out with `ESC P t m u x ; <payload> ESC \`, doubling every `ESC` in the
payload `[D]`, and this was confirmed to work `[E]` — the outer tty received
`\x1b[?u` from a pane that wrote `\033Ptmux;\033\033[?u\033\\`. **But the
terminal's reply arrives on the client's tty, where tmux's own `tty-keys.c`
consumes it — it is not routed back to your pane** `[X]`. Corroborating reports:
[#4386](https://github.com/tmux/tmux/issues/4386) and
[#5530](https://github.com/tmux/tmux/issues/5530). Also note `allow-passthrough`
defaults to `off` since 3.3 `[D]`.

---

## 8. THE TABLE: emulator compatibility

Surveyed 2026-09-07. **This table has a shelf life of months, not years.**

| Emulator | Kitty KBP | Flags | Since | `modifyOtherKeys` | Key release | Modified `Enter`? | Option / default |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **kitty** | Yes (reference) | all 5 | 0.20.0, 2021-04-19 `[D][S]` | **No** — parsed, logs an error `[S]` | Yes | **Yes** | none; always available |
| **Ghostty** | Yes | all 5 `[S]` | 1.0.0 or earlier (issue closed 2023-08-17) `[S]` | **Yes**, mode 2 `[S]` | Yes | **Yes** | none found `[?]`; always available |
| **WezTerm** | Yes, **opt-in** | all `[D]` | 20220624-141144 `[D][S]` | Yes, since 20221119-145034 `[D]` | Yes (KKP; win32 mode on Windows) | **Only if enabled** | `enable_kitty_keyboard` — **default `false`** |
| **Alacritty** | Yes | all 5 `[S]` | 0.13.0, 2023-12-27 `[S]` | **No** — declined `[S]` | Yes | **Yes** | none; always available |
| **foot** | Yes | all 5 | 1.10.2 initial, 1.10.3 complete `[S]` | **Yes** (=2), since 1.10.0 `[S]` | Yes | **Yes** | none; always available |
| **iTerm2** | Yes | all 5 `[S]` | commit 2024-08-08; visible in 3.5.12 `[S]` | `[?]` | Yes | **Yes** | legacy CSI-u toggle deprecated by vendor `[D]` |
| **Windows Terminal** | **Yes (new)** | incl. event types `[S]` | PR #19817 merged 2026-02-17, **v1.25** `[S]` | `[?]` | Yes (KKP + win32-input-mode) | **Yes** | `compatibility.kittyKeyboardMode` — default `true` `[S]`, **undocumented** |
| **VS Code / xterm.js** | **Yes (new)** | all 5 `[S]` | xterm.js PR #5600 merged 2026-01-10; **VS Code 1.109** `[D][S]` | No evidence `[?]` | Yes | **Yes** | `terminal.integrated.enableKittyKeyboardProtocol` — default `true` `[D]` |
| **Konsole** | **Yes (new)** | all 5 `[S]` | commit 2026-05-04, stable **26.08.0** `[S]` | **No** — bug 435975 open since 2021 `[I]` | Yes | **Yes** | `KittyKeyboardEnabled` — default `true` `[S]`, **undocumented** |
| **GNOME Terminal / VTE** | **NO** | — | — (issue #2601 open since 2022-10-21) `[I]` | **NO** — #1441 open since **2007** `[I][S]` | No `[I]` | **NO** | none exists |
| **xterm** | No `[D]` | — | — | **Yes — the origin** `[D]` | No | **Yes**, at mode 1 or 2 `[S]` | `modifyOtherKeys`, `formatOtherKeys` |
| **tmux** (pass-through) | **No** `[S][E]` | — | — | Yes (equivalent) `[D]` | **No** | Yes, via `modifyOtherKeys` | `extended-keys` — **default `off`** |

### 8.1 The emulators that fundamentally cannot distinguish modified `Enter`

The brief asks for this list explicitly. As of 2026-09-07 it has become
**short**, which is the headline finding:

**GNOME Terminal, and every other VTE-based terminal** (Tilix, Terminator,
Guake, Xfce Terminal, GNOME Console).

- Supports neither the Kitty protocol nor `modifyOtherKeys`. A shallow clone of
  `GNOME/vte` master (version 0.85.0) yields **zero** matches across `src/` for
  `modify_other`, `modifyOtherKeys`, `XTMODKEYS` or `kitty` `[S]`.
- `Ctrl+Enter` and `Shift+Enter` both emit bare `\x0d`, indistinguishable from
  plain `Enter`.
- Only `Alt+Enter` is distinguishable, as `\x1b\x0d`, via the generic
  meta-sends-escape path in `src/keymap.cc` `[S]`.
- **There is no user-side workaround.** VTE exposes no key-to-escape-sequence
  binding mechanism, and GNOME Terminal's keyboard settings bind *terminal*
  actions (copy/paste/tabs), not the bytes sent to the child. The only remedies
  are using `Ctrl+J` as a newline substitute, or switching terminals.
- Open issues: [vte#1441](https://gitlab.gnome.org/GNOME/vte/-/issues/1441)
  (`modifyOtherKeys`, opened **2007-09-14**),
  [vte#2607](https://gitlab.gnome.org/GNOME/vte/-/issues/2607),
  [vte#2601](https://gitlab.gnome.org/GNOME/vte/-/issues/2601) (Kitty protocol),
  [vte#2764](https://gitlab.gnome.org/GNOME/vte/-/issues/2764) (win32-input-mode).

**Conditionally in this category:**

- **WezTerm with default config** — capable, but ships `enable_kitty_keyboard = false`.
  One config line fixes it, so the honest message to the user is a fix instruction,
  not a degradation notice.
- **Any terminal under tmux with `extended-keys off`** (the default) — capable
  outside, deaf inside.
- **Pre-2026 Windows Terminal, VS Code and Konsole** — a large installed base that
  will take time to roll over.

### 8.2 Notes that change decisions

- **kitty and Alacritty refuse `modifyOtherKeys` on principle.** kitty logs
  *"The application is trying to use xterm's modifyOtherKeys. This is superseded by
  the kitty keyboard protocol"* and ignores it `[S]`. Alacritty declined it as
  maintenance burden ([#3101](https://github.com/alacritty/alacritty/issues/3101),
  closed 2023-12-13) `[S]`. Meanwhile **foot and Ghostty implement both.** So the
  correct strategy is genuinely "try Kitty first, fall back to `modifyOtherKeys`" —
  neither alone covers the field.
- **Config option names are frequently undocumented.**
  `compatibility.kittyKeyboardMode` (Windows Terminal) and `KittyKeyboardEnabled`
  (Konsole) exist only in source; neither appears in user-facing docs. Do not
  expect users to find them unaided.
- **xterm.js support is new and still settling.** Open bugs at survey time include
  [#5882](https://github.com/xtermjs/xterm.js/issues/5882),
  [#5819](https://github.com/xtermjs/xterm.js/issues/5819),
  [#6112](https://github.com/xtermjs/xterm.js/issues/6112) (IME commits dropped) —
  the last is directly relevant given the IME cursor-placement requirement.
- **Konsole's KKP rollout has fresh regressions**: KDE bugs
  [524571](https://bugs.kde.org/show_bug.cgi?id=524571) and
  [524772](https://bugs.kde.org/show_bug.cgi?id=524772), both confirmed Aug 2026
  (KKP steals Konsole's own `Shift+PageUp` bindings).
- **VS Code's own release notes name this exact use case**: *"A big benefit you
  will see immediately is shift+enter should work in some agentic CLIs without the
  need to run something like `/terminalSetup`."* `[D]`

### 8.3 Manual per-terminal workarounds

Where the protocol is unavailable but the terminal can bind keys to literal bytes,
users can synthesise the sequence themselves. Offering these in documentation is
the honest degradation path:

| Terminal | Mechanism |
| --- | --- |
| kitty | `map ctrl+enter send_text all \x1b[13;5u` |
| Ghostty | `keybind = ctrl+enter=csi:13;5u` (also `text:` / `esc:`) `[S]` |
| Alacritty | `{ key = "Enter", mods = "Shift", chars = "\u001b[13;2u" }` |
| WezTerm | prefer `enable_kitty_keyboard = true`; else a `SendString` binding |
| iTerm2 | Profiles, Keys, Key Mappings, "Send Escape Sequence" / "Send Hex Code" `[D]` |
| **VTE / GNOME Terminal** | **none exists** |

---

## 9. Key release events: where they are actually available

| Source | Available? | Notes |
| --- | --- | --- |
| Kitty protocol, flag `0b10` | **Yes** | `press=1`, `repeat=2`, `release=3` as a sub-field of the modifier field `[D]` |
| win32-input-mode (`\x1b[?9001h`) | **Yes** | `Kd` field is the key-down flag; also distinguishes left/right modifiers `[D]` |
| `modifyOtherKeys` | **No** | Structurally absent; kitty's spec lists this first among its deficiencies `[D]` |
| xterm | **No** | — |
| tmux | **No** | Not passed through; tmux has no representation for them `[S]` |

Practically, key release is available in **kitty, Ghostty, WezTerm, Alacritty,
foot, iTerm2, Windows Terminal, VS Code/xterm.js and Konsole** — and **never under
tmux**, and never in VTE.

**Two exclusions to design around** `[D]`:

- `Enter`, `Tab` and `Backspace` produce **no release events** under flag `0b10`
  alone. You must also set flag `0b1000`. The spec's rationale is that a user must
  still be able to type `reset` after a crashed program leaves the mode set.
  foot implemented this exclusion explicitly in 1.20.0 ("Enter, Tab and Backspace
  no longer report release events") `[S]`.
- Reading `kitty/key_encoding.c` `[S]`, that exclusion applies only to *unmodified*
  (or lock-modifier-only) `Enter`/`Tab`/`Backspace`; with a real modifier held,
  `Enter` does produce a release event under flag `0b10` alone `[X]`.

Consequence for a component-level opt-in: **release events must be treated as a
capability that can vanish**, not a fact. The same binary, same terminal, gains
and loses them by being run inside tmux.

---

## 10. Escape timeout: disambiguating a lone `Escape`

### 10.1 Documented defaults

| Tool | Default | Source |
| --- | --- | --- |
| tmux `escape-time` (3.5+) | **10 ms** | `options-table.c` `.default_num = 10` `[S][E]` |
| tmux `escape-time` (3.4 and earlier) | 500 ms | 3.4 man page + `options-table.c` `[S]` |
| neovim `ttimeoutlen` | **50 ms** | `runtime/doc/options.txt` `[D]` |
| vim `ttimeoutlen` | -1 (falls back to `timeoutlen`, 1000 ms); **`defaults.vim` sets 100** | `runtime/doc/options.txt` `[D]` |
| GNU readline `keyseq-timeout` | **500 ms** | readline manual `[D]` |
| ncurses `ESCDELAY` | **1000 ms**, capped at 30000 | `ncurses(3x)` `[D]` |
| crossterm | **no timer** — read-ahead based | `parse.rs` `[S]` |
| termwiz | **no timer** — read-ahead based | `input.rs` `[S]` |

### 10.2 The read-ahead alternative

Both Rust terminal libraries dispense with wall-clock timing entirely. crossterm's
`parse_event` `[S]`:

```rust
b'\x1B' => {
    if buffer.len() == 1 {
        if input_available { Ok(None) }          // possible Esc sequence
        else { Ok(Some(Event::Key(KeyCode::Esc.into()))) }
    }
```

Disambiguation is purely *"were more bytes already readable in this `read()`"*.
termwiz uses the same strategy via an `EscapeMaybeAlt` state plus a `maybe_more`
flag `[S]`. **Locally this is sufficient and has zero latency cost** — which is the
strongest argument for making the timeout a fallback rather than the primary
mechanism.

### 10.3 Practical ranges

| Context | Range | Basis |
| --- | --- | --- |
| Local TTY | **10-50 ms** | tmux 3.5+ = 10; neovim = 50 |
| Conservative default | **100 ms** | vim `defaults.vim` |
| Historical / safe-over-anything | **500-1000 ms** | readline = 500; ncurses = 1000 |
| SSH / high latency | **raise it**; ncurses caps at 30 s | see below |

ncurses' manual is the only primary source found that addresses latency directly,
and it is worth quoting `[D]`:

> The most common instance where you may wish to change this value is to work with
> a remote host over a slow communication channel. If the host running a curses
> application does not receive the characters of an escape sequence in a timely
> manner, the library can interpret them as multiple key stroke events. Conversely,
> a fast typist on a low-latency connection who happens to input an ESC followed by
> characters that match an escape sequence […] may experience confusing application
> behavior.

**The modern answer is dynamic, not static.** tmux 3.6/3.7 floors the timeout at
500 ms *while a terminal query response or a partial bracketed paste is
outstanding*, rather than raising the static default `[S]`:

```c
delay = options_get_number(global_options, "escape-time");
if (delay == 0) delay = 1;
if ((tty->flags & TTY_BRACKETPASTE) && tty_keys_partial_paste_end(buf, len)) {
        if (delay < 500) delay = 500;    /* partial paste end */
}
if (tty->flags & (TTY_WAITFG|TTY_WAITBG) || ... || !TAILQ_EMPTY(&c->input_requests)) {
        if (delay < 500) delay = 500;    /* active query */
}
```

This is directly relevant to timing our own detection probes: **inside tmux, the
effective escape timeout jumps to at least 500 ms while a query is in flight**, so
a detection handshake budget must exceed that.

### 10.4 The real fix

Both specs say the same thing: with disambiguation active, timing stops mattering.

- fixterms `[D]`: if the terminal sends CSI as the single byte `0x9b`, *"it is no
  longer required to use timing information."*
- Kitty flag `0b1` reports `Esc` as `\x1b[27u`, making a lone `Escape`
  unambiguous by construction `[D]`.

So the escape timeout should be understood as **legacy-path-only machinery**. Under
the Kitty protocol it is dead code.

---

## 11. Implications for `tp`

Derived from the findings; recorded here so the brief's "Terminal input reality"
section has something concrete to point at.

1. **Negotiate in this order:** Kitty protocol, then `modifyOtherKeys`, then
   legacy. No single scheme covers the field (§8.2), and the two most modern
   terminals actively refuse the older one.
2. **Use `\x1b[?u\x1b[c` for detection, never `\x1b[?u` alone** (§5.3). Budget the
   timeout above 500 ms if `$TMUX` is set (§10.3).
3. **Push and pop kitty flags; do not set-and-restore.** The stack exists precisely
   for this, RIS behaviour is unspecified across terminals (§5.4), and popping to
   empty resets cleanly.
4. **Request flag `0b1` at minimum.** Flag `0b1000` only where uniform `Enter`
   reporting is genuinely wanted — it changes plain `Enter` and disables `SIGINT`
   on `ctrl+c`, which is a large behavioural change.
5. **Treat key release as revocable capability, not a fact** (§9). Per-component
   opt-in must degrade when the same binary runs under tmux.
6. **Under tmux, run the five-step detection ladder (§7.4) and say the reattach
   sentence.** Tell the user `tmux detach` + `tmux attach` — not "restart the
   server", which is both harsher than necessary and, if they only reload the
   config, will not work.
7. **Ship §8 as the compatibility table the brief asks for**, and diff it against
   upstream at least twice a year. Three major terminals changed category in the
   eight months before this survey.
8. **For VTE, degrade honestly and immediately.** Detect it, state plainly that
   `Ctrl+Enter` and `Shift+Enter` are unavailable and that no workaround exists,
   and offer a bindable alternative. Silently dropping the key is the failure mode
   the brief calls out.
9. **The escape timeout is a legacy-path tunable** (§10.4). Under the Kitty
   protocol it should be bypassed entirely, not merely shortened.

---

## 12. Gaps and unverified items

Recorded deliberately — flagged gaps beat confident-sounding guesses.

| Item | Status |
| --- | --- |
| iTerm2 `modifyOtherKeys` support | `[?]` Not mentioned anywhere in iTerm2's docs; an `iTermTermkeyKeyMapper.m` exists for the CSI-u path, but nothing establishes XTMODKEYS handling |
| Windows Terminal `modifyOtherKeys` support | `[?]` No evidence found either way |
| xterm.js `modifyOtherKeys` support | `[?]` No evidence found |
| Exact iTerm2 3.5.x release that first shipped KKP | `[?]` iTerm2 keeps no in-repo 3.5.x release notes; first changelog mention is 3.5.12 (2025-04-03) |
| Ghostty config toggle for KKP | `[?]` None found in the config reference; appears to be always-on |
| Whether tmux passthrough replies are misrouted | `[X]` Reasoned from source; supported by issue titles #4386 and #5530; **not reproduced first-hand** |
| Legacy `Alt+Enter` = `\x1b\x0d` | `[X]` Generic `Alt-x` to `ESC x` rule applied to `Return`; not tabulated in any fetched source |
| Kitty `Ctrl+Enter` = `\x1b[13;5u` | `[X]` Derived from three verified rules and checked against `key_encoding.c`; corroborated by fixterms printing the identical sequence `[D]` |
| Any tmux doc stating the reattach requirement | `[?]` **No such sentence exists** in the man page or CHANGES — the §7.3 mechanism is source- and experiment-derived |
| ctlseqs "shift-Tab at mode 2" prose vs the generated table | `[?]` Reading of `input.c` suggests the `XK_ISO_Left_Tab` path explains the discrepancy, but this is inference |
| VTE version at which anything might change | `[?]` All four relevant issues open at survey date |

---

## 13. Primary sources

**Specifications**

- Kitty keyboard protocol — https://sw.kovidgoyal.net/kitty/keyboard-protocol/ and the RST source at https://raw.githubusercontent.com/kovidgoyal/kitty/master/docs/keyboard-protocol.rst
- xterm control sequences (ctlseqs) — https://invisible-island.net/xterm/ctlseqs/ctlseqs.html
- xterm manual — https://invisible-island.net/xterm/manpage/xterm.html
- xterm modified-keys reference and generated key table — https://invisible-island.net/xterm/modified-keys.html and https://invisible-island.net/xterm/modified-keys-us-pc105.html
- fixterms — http://www.leonerd.org.uk/hacks/fixterms/
- win32-input-mode — https://github.com/microsoft/terminal/blob/main/doc/specs/%234999%20-%20Improved%20keyboard%20handling%20in%20Conpty.md
- iTerm2 CSI u — https://iterm2.com/documentation-csiu.html

**Terminal source and changelogs**

- kitty `key_encoding.c`, `keys.c`, `screen.c` — https://github.com/kovidgoyal/kitty
- Ghostty `src/terminal/kitty/key.zig`, `src/input/key_encode.zig` — https://github.com/ghostty-org/ghostty
- WezTerm — https://wezterm.org/config/lua/config/enable_kitty_keyboard.html and https://wezterm.org/config/key-encoding.html
- Alacritty CHANGELOG — https://github.com/alacritty/alacritty/blob/master/CHANGELOG.md
- foot CHANGELOG — https://codeberg.org/dnkl/foot
- Windows Terminal PR #19817 — https://github.com/microsoft/terminal/pull/19817
- xterm.js PR #5600 — https://github.com/xtermjs/xterm.js/pull/5600
- VS Code 1.109 release notes — https://code.visualstudio.com/updates/v1_109
- Konsole KKP commit — https://invent.kde.org/utilities/konsole/-/commit/1983d2b4735d6b61b74cf85854acc1cb4d2445d5
- VTE — https://gitlab.gnome.org/GNOME/vte
- xterm `input.c`, `charproc.c` — https://github.com/ThomasDickey/xterm-snapshots

**tmux**

- Man page source — https://raw.githubusercontent.com/tmux/tmux/master/tmux.1
- CHANGES — https://raw.githubusercontent.com/tmux/tmux/master/CHANGES
- `tty.c`, `tty-keys.c`, `tty-features.c`, `input.c`, `input-keys.c`, `options-table.c`
- Wiki FAQ — https://github.com/tmux/tmux/wiki
- Kitty protocol issue trail — [#3335](https://github.com/tmux/tmux/issues/3335), [#4912](https://github.com/tmux/tmux/pull/4912), [#5405](https://github.com/tmux/tmux/pull/5405), [#5406](https://github.com/tmux/tmux/issues/5406)

**Timeout defaults**

- neovim / vim `options.txt` — https://github.com/neovim/neovim and https://github.com/vim/vim
- ncurses manual — https://invisible-island.net/ncurses/man/ncurses.3x.html
- GNU readline manual — https://tiswww.cwru.edu/php/chet/readline/readline.html
- crossterm `parse.rs` — https://github.com/crossterm-rs/crossterm
- termwiz `input.rs` — https://github.com/wezterm/wezterm
