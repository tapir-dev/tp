# Copy to clipboard from a fullscreen TUI: OSC 52 vs native clipboard crates

Research note. Survey date: **2026-09-08**.

Scope: how "copy to clipboard" can work from inside a fullscreen Rust TUI when the
process may be running over SSH and/or inside tmux/screen/zellij. Two candidate
paths are examined — OSC 52 escape sequences, and a native clipboard crate.

**This note reports facts only. It does not choose an architecture.**

Every claim carries a marker:

| Marker | Meaning |
| --- | --- |
| **VERIFIED** | Traced to a primary source — official docs, the project's own source code, a manpage, or the XTerm control-sequence spec. Cited inline. |
| **VERIFIED (local)** | Reproduced on the survey machine against an installed binary or a vendored crate source. Command and output given. |
| **INFERRED** | Reasoned from primary sources but not stated by one. The reasoning is given so it can be checked. |
| **UNRESOLVED** | Could not be confirmed. Treat as unknown, not as absence. |

Survey machine: Arch Linux, `xterm 410`, `tmux 3.7_c-1`, `arboard 3.6.1` vendored
in the local cargo registry, `TERM=xterm-kitty`.

---

## Executive summary

1. **OSC 52 write is fire-and-forget.** There is no acknowledgement of any kind, in
   the spec or in any implementation surveyed. See Q5.
2. **A read probe does not detect write support.** Read is gated separately from
   write, and is the more restricted of the two. Multiple mainstream terminals
   write happily and answer no read query at all. See Q4.
3. **tmux's default `set-clipboard external` drops an inner program's OSC 52
   entirely.** This is the single most common non-obvious failure. GNU screen has no
   OSC 52 support at all, in any version. zellij accepts writes ungated but never
   forwards the original bytes. **No multiplexer relays OSC 52 verbatim — each one
   re-encodes or drops.** See Q3.
4. **On X11 and Wayland the clipboard content lives in the owning process.** A
   short-lived process that writes and exits loses the content unless a clipboard
   manager catches it. arboard exposes a blocking `.wait()` and a 100 ms
   clipboard-manager handoff on drop. See Q8.
5. **With no display server, native clipboard crates return `Err` fast — they do
   not panic and do not hang.** None of them has any SSH, OSC 52, or `clip.exe`
   fallback. See Q9.

---

# Part 1 — OSC 52 (write path)

## Baseline semantics

**VERIFIED** — XTerm Control Sequences, `OSC Ps ; Pt ST`, `Ps = 5 2`
(<https://invisible-island.net/xterm/ctlseqs/ctlseqs.html>):

> `Ps = 5 2` ⇒ Manipulate Selection Data. **These controls may be disabled using
> the `allowWindowOps` resource.** The parameter Pt is parsed as `Pc ; Pd`
>
> The first, Pc, may contain zero or more characters from the set
> `c , p , q , s , 0 , 1 , 2 , 3 , 4 , 5 , 6 , and 7`. […] **If the parameter is
> empty, xterm uses `s 0`**, to specify the configurable primary/clipboard
> selection and cut-buffer 0.
>
> The second parameter, Pd, gives the selection data. **Normally this is a string
> encoded in base64 (RFC-4648).** […]
>
> **If the second parameter is neither a base64 string nor `?`, then the selection
> is cleared.**

Both terminators are accepted — **VERIFIED**, same document: "XTerm accepts either
`BEL` or `ST` for terminating OSC sequences, and when returning information, uses
the same terminator used in a query."

Two consequences worth stating explicitly:

- An empty or malformed payload **clears** the clipboard rather than being ignored.
  This makes a "probe by writing garbage" strategy destructive.
- `Pc` selects the target selection. Terminals vary in which `Pc` values they honour
  (see contour and iTerm2 below).

---

## Q1 — Which terminals support OSC 52 write, and is it on by default

| Terminal | Write supported | Default | Config option (exact name, default) | Status |
| --- | --- | --- | --- | --- |
| xterm | Yes (`OPT_PASTE64`, compiled in by default) | **OFF** | `allowWindowOps` = `false`; `disallowedWindowOps` includes `SetSelection` | VERIFIED (local) |
| kitty | Yes | **ON** | `clipboard_control` = `write-clipboard write-primary read-clipboard-ask read-primary-ask` | VERIFIED |
| alacritty | Yes | **ON (copy only)** | `[terminal] osc52` = `"OnlyCopy"` | VERIFIED |
| wezterm | Yes | **ON, ungated** | none exists | VERIFIED |
| foot | Yes | **ON** | `[security] osc52` = `enabled` | VERIFIED |
| Ghostty | Yes | **ON** | `clipboard-write` = `allow` | VERIFIED |
| iTerm2 | Yes | **OFF** | `AllowClipboardAccess` = `@NO` | VERIFIED |
| Windows Terminal | Yes (≥ 1.22) | **ON** + focus required | `compatibility.allowOSC52` = `true` (per profile) | VERIFIED |
| GNOME Terminal / VTE | **No** — parsed, then discarded | n/a | none exists | VERIFIED |
| Konsole | Yes (≥ 24.12) | **ON, ungated** | none exists | VERIFIED |
| st | Yes | **OFF** | `allowwindowops = 0` (compile-time) | VERIFIED |
| contour | Yes | **ON, ungated** | none for write | VERIFIED |
| mintty | Yes | **OFF** | `AllowSetSelection` = `false` | VERIFIED |
| rxvt-unicode | **No** upstream; third-party perl ext only | off | `URxvt.perl-ext-common` | VERIFIED (absence) |
| PuTTY 0.85 | **No** | — | none | VERIFIED (absence) |
| Terminal.app (macOS) | **No** | — | — | INFERRED |

### xterm — off by default, and there are two gates

**VERIFIED (local)**, `man xterm` on xterm 410:

- `allowWindowOps (class AllowWindowOps)` — "Specifies whether extended window
  control sequences (as used in dtterm) should be allowed. […] For fine-tuning,
  see disallowedWindowOps. **The default is "false".**"
- `disallowedWindowOps (class DisallowedWindowOps)` — "Specify which features will
  be disabled **if allowWindowOps is false**. […] The default value is
  `GetChecksum,GetIconTitle,GetSelection,GetWinTitle,SetSelection,SetXprop`"
- `SetSelection` — "Set selection data."
- `GetSelection` — "Report selection data as a base64 string."

So out of the box `allowWindowOps` is false **and** `SetSelection` is on the
disallow list, therefore OSC 52 write is refused.

Source wiring — **VERIFIED**:

- `misc.c`, `ManipulateSelectionData()`: `if (AllowWindowOps(xw, ewSetSelection)) {`
- `ptyx.h`: `#define AllowWindowOps(w,name) (AllowXtermOps(w, allowWindowOps) || SpecialWindowOps(w,name))`,
  with `SpecialWindowOps(w,name) (!TScreenOf(w)->disallow_win_ops[name])`
- `main.h`: `#define DEF_ALLOW_WINDOW False`, and `#define DISALLOWED_PASTE64 ",SetSelection,GetSelection"`
- `configure.in`: `CF_ARG_DISABLE(paste64, ... [enable_paste64=yes])` — the feature is
  compiled in by default, only the runtime gate is closed.

To enable: set `XTerm*allowWindowOps: true`, or remove `SetSelection` from
`disallowedWindowOps`. tmux's own manpage documents exactly this recipe —
**VERIFIED (local)**, `man tmux`:

> Note that this feature needs to be enabled in xterm(1) by setting the resource:
> `disallowedWindowOps: 20,21,SetXprop`

It can also be toggled at runtime from the fontMenu (`allow-window-ops` entry) or
via the `allow-window-ops(on/off/toggle)` action. **VERIFIED (local)**, manpage.

### kitty — on

**VERIFIED** — <https://sw.kovidgoyal.net/kitty/conf/>:

> `clipboard_control write-clipboard write-primary read-clipboard-ask read-primary-ask`
>
> "The **default is to allow writing to the clipboard and primary selection** and to
> ask for permission when a program tries to read from the clipboard."

### alacritty — write on, read off

**VERIFIED** — `extra/man/alacritty.5.scd`, `[terminal]` table:

> `*osc52* = _"Disabled"_ | _"OnlyCopy"_ | _"OnlyPaste"_ | _"CopyPaste"_` … `Default: _"OnlyCopy"_`

CHANGELOG, `## 0.13.0`: "OSC 52 **paste** ability is now **disabled by default**;
use `terminal.osc52` to adjust it". CHANGELOG, `## 0.11.0`: "OSC 52 is now disabled
on unfocused windows" — still enforced, `alacritty/src/event.rs`:

```rust
TerminalEvent::ClipboardStore(..) => {
    if self.ctx.terminal.is_focused { self.ctx.clipboard.store(..) }
}
```

**Alacritty silently drops OSC 52 writes to an unfocused window.** VERIFIED.

Additional gotcha — **VERIFIED**, `alacritty_terminal/src/term/mod.rs`
`clipboard_store` base64-decodes then does `String::from_utf8(bytes)` and
**silently discards non-UTF-8 payloads**.

### foot — on

**VERIFIED** — `doc/foot.ini.5.scd`, `# SECTION: security`:

> `*osc52*` … "- *enabled*: all applications have full access to the host clipboard.
> **This is the default.**" / `Default: _enabled_`

`[main] selection-target` (default `primary`) governs *mouse* selection, not OSC 52.

foot also requires focus — `osc.c`, `osc_to_clipboard()`:
`LOG_WARN("OSC52: client tried to write to clipboard data while window was unfocused"); return;`

Per its CHANGELOG, an empty payload clears the clipboard, and an invalid base64
payload also clears it. VERIFIED.

### Ghostty — on

**VERIFIED** — `src/config/Config.zig`, mirrored at <https://ghostty.org/docs/config/reference>:

```zig
/// Whether to allow programs running in the terminal to read/write to the
/// system clipboard (OSC 52, for googling). The default is to allow clipboard
/// reading after prompting the user and allow writing unconditionally.
@"clipboard-read": ClipboardAccess = .ask,
@"clipboard-write": ClipboardAccess = .allow,
```

### wezterm — on, no opt-out

**VERIFIED** — <https://wezterm.org/escape-sequences.html>, OSC row 52: "**Requests
to query the clipboard are ignored. Allows setting or clearing the clipboard**".

`term/src/terminalstate/performer.rs` has no permission check:

```rust
OperatingSystemCommand::QuerySelection(_) => {}
OperatingSystemCommand::SetSelection(selection, selection_data) => {
    let selection = selection_to_selection(selection);
    match self.set_clipboard_contents(selection, Some(selection_data)) { .. }
}
```

No `osc52`/`clipboard` key exists in wezterm's config surface. VERIFIED (absence).

### iTerm2 — off by default

**VERIFIED** — `sources/Settings/iTermPreferences.m`:

```objc
NSString *const kPreferenceKeyAllowClipboardAccessFromTerminal = @"AllowClipboardAccess";
...
kPreferenceKeyAllowClipboardAccessFromTerminal: @NO,   // in +defaultValueMap
```

UI wording — <https://iterm2.com/documentation-preferences-general.html>, Selection
section: "**Applications in terminal may access clipboard** — If enabled, clipboard
access will be granted via escape code to programs running in iTerm2."

It is **app-global, not per-profile**, and `@NO` is unchanged across 3.4.23, 3.5.0,
3.5.11 and master. `Pc` is ignored ("Note: Pc is ignored now.", `VT100Terminal.m`).

### Windows Terminal — on since 1.22, plus a focus gate

**VERIFIED** — `src/cascadia/TerminalSettingsModel/MTSMSettings.h`:

```cpp
X(bool, AllowVtClipboardWrite, "compatibility.allowOSC52", true)
```

`doc/cascadia/profiles.schema.json`:

```json
"compatibility.allowOSC52": {
  "default": true,
  "description": "When set to true, VT applications will be allowed to set the contents of the local clipboard using OSC 52 (Manipulate Selection Data).",
  "type": "boolean"
}
```

It is **per-profile**. Enforcement — `src/cascadia/TerminalCore/TerminalApi.cpp`:

```cpp
void Terminal::CopyToClipboard(wil::zwstring_view content) {
    if (_clipboardOperationsAllowed && _focused) { _pfnCopyToClipboard(content); }
}
```

Conhost has the same focus guard (`src/host/outputStream.cpp`: "Only allow VT
clipboard writes when the console has focus"). Reads are parsed but never answered.
The setting is **not documented on learn.microsoft.com** — schema and source are the
only references. Before 1.22 writes were unconditional with no setting and no focus
check. VERIFIED.

### VTE / GNOME Terminal — not implemented

**VERIFIED** — `src/parser-osc.hh` defines `_VTE_OSC(XTERM_SET_XSELECTION, 52)`, but
`src/vteseq.cc` `Terminal::OSC()` places `case VTE_OSC_XTERM_SET_XSELECTION:` in the
group that falls through to `default: break;`. Identical in tags 0.70.0, 0.76.0,
0.82.4 and 0.84.1. No GSettings key exists in gnome-terminal's
`org.gnome.Terminal.gschema.xml`.

Tracking issue: <https://gitlab.gnome.org/GNOME/vte/-/issues/2495> "Add support for
OSC 52", **open since 2018-05-03**. MR !15 "osc52 preparations" is open and unmerged.

This is a large installed base with no OSC 52 at all.

### Konsole — on since 24.12, ungated

**VERIFIED** — `src/Vt102Emulation.h`: `Clipboard = 52,`; `src/Vt102Emulation.cpp`
`processSessionAttributeRequest()` calls `QApplication::clipboard()->setText(..)`
with **no permission check**. Added by commit `9f7a2b846` (2024-07-24, "Add support
for OSC-52 write-only clipboard access", BUG: 372116), first shipped in
`release/24.12`. `AllowEscapedLinks` (default `false`) gates OSC 8 hyperlinks, not
OSC 52.

Because the `?` query form is not special-cased, a read query would be treated as
data and **wipe the clipboard**. INFERRED from the code path; not reproduced.

### st, contour, mintty, PuTTY, urxvt

- **st** — **VERIFIED**, `config.def.h`: `int allowwindowops = 0;` with the comment
  "allow certain non-interactive (insecure) window operations such as: setting the
  clipboard text". `st.c`: `case 52: ... if (narg > 2 && allowwindowops) {`.
  Compile-time only. **Trap:** st's own `st.info` ships
  `Ms=\E]52;%p1%s;%p2%s\007,` regardless, so terminfo-based detection lies.
- **contour** — **VERIFIED**, `src/vtbackend/screen/Screen.cpp` `clipboard()` calls
  `terminal.copyToClipboard(..)` with no check. The only related setting is
  `bool allowClipboardRead = false;`, which covers reads and is not wired to any
  `contour.yml` key. Only `Pc` = `c` or empty is accepted; `p`/`s`/`0-7` return
  `ApplyResult::Invalid`.
- **mintty** — **VERIFIED**, `docs/mintty.1`: "**Allow control sequence to set
  selection** (`AllowSetSelection=false`) — If enabled, the terminal control
  sequence OSC 52 is allowed to set the clipboard selection for pasting…";
  `src/config.c`: `.allow_set_selection = false,`.
- **PuTTY 0.85** — **VERIFIED (absence)**, `terminal/terminal.c` `do_osc()` handles
  only OSC 0/1/2/21 and 4. No `no-remote-clipboard` option exists in the tree.
- **rxvt-unicode** — **VERIFIED (absence)**, `src/rxvt.h`'s OSC enum jumps
  `XTerm_font = 50`, `XTerm_emacs51 = 51`, with no 52; urxvt(7)'s documented `Ps`
  list omits 52. The Debian-shipped `clipboard-osc` extension is **OSC 777**, not 52.
  Third-party perl extensions using the documented `on_osc_seq` hook exist but have
  no canonical home. INFERRED that no upstream support is planned.
- **Terminal.app** — **INFERRED**. No Apple documentation either way. The best
  available signal is ncurses `terminfo.src`, which defines `Ms=` for only
  `xterm+tmux`, `xterm+tmux2`, `st-0.8`, `st-0.7` and `ghostty`; the
  `nsterm`/`Apple_Terminal` chain has none. This is absence of evidence in a
  third-party description, not an Apple statement.

### Runtime feature detection

Two mechanisms exist, both **VERIFIED**:

- **xterm** — `OSC 6 0` (XTQALLOWED) reports enabled feature categories including
  `allowWindowOps`; `OSC 6 1` (XTQDISALLOWED) reports disallowed sub-features. Per
  ctlseqs.
- **Windows Terminal and foot** — Primary DA includes `52` when clipboard write is
  enabled. WT `adaptDispatch.cpp`: `// 52 = Clipboard access` …
  `_ReturnCsiResponse(L"?61;4;6;7;14;21;22;23;24;28;32;42;52c");`. foot CHANGELOG:
  "DA (Device Attributes): include `52` in the reply, to indicate OSC-52 support
  (when at least *copy* has been enabled in `security.osc52`)."

**Do not trust terminfo `Ms`** — st is a live counterexample (advertises `Ms`,
defaults `allowwindowops = 0`).

---

## Q2 — Size limits

### xterm

There is **no dedicated "max selection size" resource**. The governing one is
`maxStringParse` — **VERIFIED (local)**, `man xterm` on xterm 410:

> Xterm reads these strings, accumulating them into a buffer until they are properly
> terminated. […] This resource sets a limit on the size of the buffer used for these
> strings. **The default is "600000"** based on the features which are configured for
> xterm. **Control strings which require larger buffer size are ignored.**

Units are **bytes of the raw control string** — the whole OSC body including the
`52;c;` prefix, not decoded bytes.

The default is build-dependent — **VERIFIED**, `main.h`:

```c
#ifndef DEF_STRINGS_MAX
#if OPT_REGIS_GRAPHICS || OPT_SIXEL_GRAPHICS
#define DEF_STRINGS_MAX		600000
#else
#define DEF_STRINGS_MAX		20000
#endif
#endif
```

So **600000 with ReGIS/Sixel compiled in, 20000 otherwise.**

**On exceed the whole sequence is dropped, not truncated** — **VERIFIED**,
`charproc.c`:

```c
} else if (sp->string_used >= screen->strings_max) {
    sp->string_skip = True;
    sp->string_used++;
    FreeAndNull(sp->string_area);
    sp->string_size = 0;
}
```

The buffer is freed and the remainder skipped, so `do_osc()` is never called.

A related but different resource: `limitResponse` ("Limits the buffer-size used when
xterm **replies** to various control sequences. The default is "1024"") applies to
the OSC 52 read *response*, not to writes. VERIFIED.

Also **VERIFIED**: xterm's base64 decoder (`button.c`, `AppendToSelectionBuffer`)
simply `return`s on any character outside `[A-Za-z0-9+/]` — invalid characters are
silently skipped rather than raising an error.

### Per-terminal limits and overflow behaviour

| Terminal | Documented limit | Actual limit | On exceed |
| --- | --- | --- | --- |
| xterm | `maxStringParse` 600000 (20000 w/o graphics) | same | **whole sequence dropped** |
| kitty | `clipboard_max_size 512` (**MB**) | 512 MB; parser chunks at 256 KiB | **truncates**, logs, ignores the rest |
| Ghostty | `clipboard-write-limit-bytes` 64 MiB — **explicitly not applied to OSC 52** | `MAX_ALLOCATING_BUF = 8 * 1024 * 1024` | **whole sequence dropped** (parser → `.invalid`) |
| alacritty | none | none | n/a; non-UTF-8 silently discarded |
| wezterm | none | none (`MAX_OSC = 64` bounds param *count*, not size) | n/a |
| foot | none | none (`osc_ensure_size()` reallocs; bound is `SIZE_MAX/2`) | n/a |
| Konsole | none | none | n/a |
| Windows Terminal | none | none found | n/a |
| iTerm2 | none | **1 MiB** OSC body | **silently truncated and dispatched** → partial write |
| contour | none | **51200 bytes** (`Sequence::MaxOscLength = 1024 * 50`) | **silently truncated** → corrupt clipboard |
| mintty | `MaxImageSize=4444444` (reused) | `TERM_CMD_BUF_MAX_SIZE = max(2222, cfg.max_image_size)` | **hard drop** |
| st | none | grows unbounded | n/a |

All **VERIFIED** from source. Notable quotes:

- **kitty** — <https://sw.kovidgoyal.net/kitty/conf/>: "`clipboard_max_size 512` — The
  maximum size (**in MB**) of data from programs running in kitty that will be stored
  for writing to the system clipboard. A value of zero means no size limit is
  applied." Truncation in `kitty/clipboard.py`:

  ```python
  if self.max_size > 0 and self.tempfile.tell() > self.max_size:
      log_error(f'Clipboard write request has more data than allowed by clipboard_max_size ({self.max_size} bytes), ignoring further data')
      self.max_size_exceeded = True
  ```

  Invalid base64 discards the whole request. Unpadded base64 is tolerated for OSC 52
  specifically: "the data is not padded to a multiple of four bytes. This is
  tolerated for the legacy OSC 52 protocol as it has no way to report errors to the
  client."

- **Ghostty** — `src/config/Config.zig` on `clipboard-write-limit-bytes`: "The maximum
  size in bytes of a single clipboard write by a program running in the terminal via
  the **Kitty clipboard protocol (OSC 5522)**. **This doesn't apply to OSC 52, which
  is limited by the maximum length of an escape sequence hardcoded into Ghostty for
  now.**" That bound is `src/terminal/osc.zig`:
  `pub const MAX_ALLOCATING_BUF = 8 * 1024 * 1024;`, and on overflow
  `error.WriteFailed => self.state = .invalid` discards the entire OSC.

- **iTerm2** — `sources/VT100/VT100XtermParser.m`:

  ```objc
  const NSUInteger maxLength = 1048576;
  if (data.length >= maxLength) { DLog(@"Truncate very long OSC"); nextState = kXtermParserFinishedState; }
  ```

  State goes to *Finished*, not *Failed*, so a truncated payload is dispatched.
  ~786 KB of decoded text (INFERRED arithmetic).

- **contour** — `src/vtbackend/vt/Sequence.hpp`:

  ```cpp
  // Make maximum size 50 kB since we need to support adding to the clipboard
  size_t constexpr static MaxOscLength = static_cast<size_t>(1024 * 50);
  ```

- **kitty's parser cap** — `kitty/vt-parser.c`: `#define BUF_SZ (1024u * 1024u)` and
  `#define MAX_ESCAPE_CODE_LENGTH (BUF_SZ / 4u)` = 256 KiB. Escape codes longer than
  that are normally dropped, **except OSC 52**, which is special-cased and
  re-dispatched in pieces (see Q6).

### pty and line-discipline limits

**No terminal documents a pty-level cap on OSC 52 writes, and none applies in the
write direction.**

The frequently cited 4096-byte limit is a *canonical-mode input* limit —
**VERIFIED**, termios(3), <https://man7.org/linux/man-pages/man3/termios.3.html>:

> In canonical mode: […] **The maximum line length is 4096 chars (including the
> terminating newline character); lines longer than 4096 chars are truncated.**

This affects the application→pty **input** direction, i.e. an OSC 52 **read
response** delivered while the tty is in canonical mode. It does not affect writes.
An application writing `OSC 52 ; c ; <b64> ST` to stdout uses the pty *output* path,
where a full buffer simply blocks the writer; there is no truncation. Base64's
alphabet contains no CR or NL, so `OPOST`/`ONLCR` output processing cannot corrupt
the payload. VERIFIED for termios; **INFERRED** for the direction analysis and
OPOST-safety, reasoned from the RFC-4648 alphabet cited by ctlseqs.

### Practical envelope

**INFERRED** from the table above: the binding constraints across the ecosystem are
contour's 50 KB OSC body (~38 KB decoded) and xterm-without-graphics' 20000 bytes.
Keeping the whole sequence under **~16 KB** stays inside every surveyed
implementation; under ~32 KB clears everything except a graphics-less xterm build.

---

## Q3 — Multiplexers

### tmux

**VERIFIED (local)** — `man tmux`, tmux 3.7c:

> `set-clipboard [on | external | off]`
>
> Attempt to set the terminal clipboard content using the xterm(1) escape sequence,
> **if there is an `Ms` entry in the terminfo(5) description** (see the "TERMINFO
> EXTENSIONS" section).
>
> If set to **on**, tmux will both accept the escape sequence to create a buffer and
> attempt to set the terminal clipboard. If set to **external**, tmux will attempt to
> set the terminal clipboard but **ignore attempts by applications to set tmux
> buffers**. If **off**, tmux will neither accept the clipboard escape sequence nor
> attempt to set the clipboard.

**The default is `external`** — **VERIFIED (local)** on a clean server with no
config loaded:

```console
$ tmux -L probeclean -f /dev/null new-session -d -s p
$ tmux -L probeclean show-options -g set-clipboard
set-clipboard external
```

Corroborated in source — **VERIFIED**, `options-table.c`:

```c
static const char *options_table_set_clipboard_list[] = { "off", "external", "on", NULL };
...
{ .name = "set-clipboard", ... .choices = options_table_set_clipboard_list, .default_num = 1 }
```

`.default_num = 1` indexes `"external"`.

**The default changed meaning in tmux 2.6, and the `CHANGES` file never says so
directly.** **VERIFIED** via `git log -L '/set-clipboard/,+12:options-table.c'`:
the option was introduced as `OPTIONS_TABLE_FLAG` with `.default_num = 1`, i.e.
boolean **on**. Commit `34420660545611af1b24060f55551ebe90d67a0c` (2017-06-03,
"Make set-clipboard a three-state option so tmux itself can ignore the sequencess.")
changed the type to `OPTIONS_TABLE_CHOICE` and left `.default_num = 1` untouched —
so `1` silently became the new middle value `external`. First release tag containing
it is **2.6**. The matching `CHANGES` entry, under "CHANGES FROM 2.5 TO 2.6,
05 October 2017":

> Make set-clipboard a three state option: on (tmux both sends to outside terminal
> and accepts from applications inside); **external (tmux sends outside but does not
> accept inside)**; and off.

So: **default `on` up to and including tmux 2.5; `external` from 2.6 (Oct 2017)
through master (next-3.8).** The parenthetical in `CHANGES` is the accurate
description; the manpage wording is looser and is what causes the common misreading.

**Consequence — the headline fact of this note.** Under the default, an inner
program's OSC 52 is **dropped entirely**: tmux neither creates a buffer nor forwards
to the outer terminal. **VERIFIED**, `input.c`, `input_osc_52_parse()` opens with:

```c
if (options_get_number(global_options, "set-clipboard") != 2)
    return (0);
```

`2` is the index of `"on"`, and `input_osc_52()` returns immediately when the parse
yields 0. Users must set `set -s set-clipboard on` for an application's OSC 52 to be
honoured.

The naming is actively misleading: `external` sounds like "forward to the external
terminal", but it means "tmux may set the outer clipboard *from its own copy-mode
selections*, while ignoring applications". tmux's own copy operations are gated by a
*different* comparison — **VERIFIED**, `window-copy.c` (`window_copy_copy_buffer`,
`window_copy_append_selection`): `options_get_number(global_options, "set-clipboard") != 0`,
which is true for both `external` and `on`.

**Mechanism.** With `set-clipboard on`, tmux consumes the application's OSC 52,
stores the decoded data as a **tmux paste buffer** (`paste_add`), and re-emits its
own OSC 52 to the outer terminal via `screen_write_setselection()`. It is a
store-and-re-emit, **not** a byte passthrough — the original bytes never reach the
outer terminal.

Empirically **VERIFIED** with nested tmux on 3.7c (inner tmux inside an outer tmux
acting as the "outer terminal"), inner app emitting `\033]52;c;<base64>\007`:

| inner `set-clipboard` | inner paste buffer created | forwarded outward |
| --- | --- | --- |
| `off` | no | no |
| **`external` (default)** | **no** | **no** |
| `on` | yes | yes |

Same harness but copying via tmux's own copy-mode instead:

| inner `set-clipboard` | inner paste buffer | forwarded outward |
| --- | --- | --- |
| `off` | yes | no |
| **`external` (default)** | yes | **yes** |
| `on` | yes | yes |

**The `Ms` gate.** Forwarding requires the outer terminal's terminfo to carry `Ms`,
unconditionally. **VERIFIED**, `tty.c`, `tty_set_selection()`:

```c
	if (~tty->flags & TTY_STARTED)
		return;
	if (!tty_term_has(tty->term, TTYC_MS))
		return;
```

`TTYC_MS` is the terminfo capability `Ms` (`tty-term.c`: `[TTYC_MS] = { TTYCODE_STRING, "Ms" }`).
No `Ms` means a silent return: no forward, no error, no user feedback.

**VERIFIED (local)** under `TERM=xterm-kitty`:

```console
$ infocmp -x | tr ',' '\n' | grep -E '^\s*Ms'
 Ms=\E]52;%p1%s;%p2%s\E\\
```

Three ways `Ms` gets set — all **VERIFIED**:

1. **From the terminfo database** for `TERM`. Modern ncurses ships `Ms` for
   `xterm-256color` and `tmux-256color`; older ncurses did not, which is the
   historical reason for the widespread
   `set -ga terminal-overrides ',xterm*:Ms=\E]52;%p1%s;%p2%s\7'` advice.
2. **From `terminal-features`**, which synthesizes the capability —
   `tty-features.c`: the `clipboard` feature is defined as
   `"Ms=\\E]52;%p1%s;%p2%s\\a"`. Built-in per-terminal defaults
   (`TTY_FEATURES_BASE_MODERN_XTERM = "256,RGB,bpaste,clipboard,mouse,strikethrough,title"`)
   apply it to mintty, tmux, iTerm2 and others. Named features arrived in tmux 3.2.
3. **From the Primary Device Attributes report**, new in tmux 3.6 — commit
   `d858ad11` (2025-06-24), "Detect support for OSC 52 using the device attributes
   report." `tty-keys.c`: `if (p[i] == 52) tty_parse_client_features(c, "clipboard", ",");`

**Three further silent gates on the forward path**, none documented, all
**VERIFIED** empirically on tmux 3.7c with `set-clipboard on`. The forward goes
through `screen_write_set_client_cb()` *without* `TTY_CTX_INVISIBLE_PANES`:

- **No attached client → no forward.** A detached session creates the paste buffer
  and sends nothing anywhere.
- **Background (non-current) window → no forward.** The paste buffer is created, the
  outer terminal receives nothing, and it is **not queued** — it is lost.
- **`PANE_REDRAW` pending → skipped.** `window_copy_copy_buffer` contains an explicit
  workaround for this (`/* Clear PANE_REDRAW so clipboard write not skipped. */`);
  **no such workaround exists on the OSC 52 path.**

**`allow-passthrough` is NOT involved in OSC 52.** **VERIFIED**, `input.c`: the
option is read only in `input_dcs_dispatch()`, gating the `tmux;` DCS prefix.
`input_osc_52()` never reads it.

**VERIFIED (local)**, `man tmux` — it is a **pane** option:

> `allow-passthrough [on | off | all]`
>
> Allow programs in the pane to bypass tmux using a terminal escape sequence
> (`\ePtmux;...\e\\`). If set to `on`, passthrough sequences will be allowed only if
> the pane is visible. If set to `all`, they will be allowed even if the pane is
> invisible.

Default `off` — `options-table.c` `.default_num = 0` against
`{"off", "on", "all"}`, and **VERIFIED (local)**:

```console
$ tmux -L pc2 -f /dev/null new-session -d -s p
$ tmux -L pc2 show-options -g -w -A | grep -i passthrough
allow-passthrough off
```

**Relationship (INFERRED from the two independent code paths):** OSC 52 does not
*need* `allow-passthrough`, but the DCS wrapper is the standard **workaround** for
tmux's gating. Wrapping the sequence as
`\033Ptmux;\033\033]52;c;<b64>\007\033\\` sends raw bytes onward via
`screen_write_rawstring`, bypassing `set-clipboard`, `Ms`, and (with `all`) even the
visibility check. The two mechanisms are mutually exclusive alternatives, not
layered. It requires doubling every `\e` in the payload.

Nesting note (**INFERRED**): with nested tmux sessions, each layer applies its own
`set-clipboard` gate, so every layer must be set to `on`.

**Size limit.** There is no OSC-52-specific limit, but there is a generic
escape-sequence input limit that applies to every OSC/DCS/APC — **VERIFIED**,
`tmux.h`: `#define INPUT_BUF_DEFAULT_SIZE 1048576`. `input.c`'s string collector
sets `INPUT_DISCARD` when the buffer would exceed it, and `input_exit_osc()` bails on
that flag, so **an oversized OSC 52 is silently discarded in full — not truncated**.
Base64 overhead puts the effective clipboard ceiling at **~786 KB**.

Configurable since tmux 3.6 (`CHANGES`: "Add input-buffer-size option (from Ken
Lau)") — `options-table.c` gives `input-buffer-size` `.default_num = INPUT_BUF_DEFAULT_SIZE`
with `.minimum` equal to the default, so it can be raised but **not lowered**.
**VERIFIED (local)**: `tmux show -g input-buffer-size` → `1048576`.

Two secondary limits, both **VERIFIED**: a **5-second terminator timeout**
(`input_start_ground_timer()`, `tv_sec = 5`) drops any OSC whose ST/BEL arrives too
late; and `input_reply_clipboard` refuses reply payloads at or above
`((size_t)INT_MAX * 3 / 4) - 1`.

**Other tmux OSC 52 facts.** All **VERIFIED**:

- The selection code `Pc` is parsed and filtered (`allow = "cpqs01234567"`,
  deduplicated) and passed outward as `%p1`, but tmux has only one buffer stack —
  empirically, `Pc` values `c`, `p`, `pc`, `XYZ` and empty all produced one identical
  paste buffer. Passing `Pc` through at all is new in 3.4.
- Unknown OSC numbers are **dropped**, not forwarded (`input.c`:
  `default: log_debug("%s: unknown '%u'", __func__, option); break;`).
- OSC 52 only started working in popups in **3.7**.

### GNU screen

**GNU screen has no OSC 52 support of any kind, in any version, up to and including
5.0.2. There is no option, no interception, no reply, and no implicit passthrough.**

Source-only finding — screen was not installed on the survey machine, so this is not
empirically tested.

**52 is not in the OSC dispatch.** **VERIFIED**, `src/ansi.c`, `StringEnd()`, branch
`screen-v5` at `e9206ef` (Release 5.0.2, 2026-07-11):

```c
	switch (win->w_StringType) {
	case OSC:		/* special xterm compatibility hack */
		...
		typ = atoi(win->w_string);
		...
		if (typ == 83) {	/* 83 = 'S' */
		...
		if (typ == 0 || typ == 1 || typ == 2 || typ == 11 || typ == 20 || typ == 39 || typ == 49) {
```

Recognised OSC numbers are **0, 1, 2, 11, 20, 39, 49, 83**. **52 is absent.**
Historically identical — the 2012 `next` branch (4.x lineage) has the same list minus
`11`. The only change in fourteen years is the added background-RGB code.

**Unrecognised OSC is dropped, not passed through.** **VERIFIED**, immediately after
that block:

```c
		if (typ != 0 && typ != 2)
			break;
```

For `typ == 52` every branch is skipped and `StringEnd()` returns 0. The bytes,
already consumed into `win->w_string`, are discarded. **There is no `default:`
fall-through relaying bytes to the outer terminal.** Even the recognised OSCs are not
byte-relayed — they are gated on `D_CXT` and rewritten from a fixed table in
`SetXtermOSC()`.

**No clipboard option or command exists.** **VERIFIED**:
`grep -rni "clipboard\|osc 52\|osc52" src/*.c src/*.h` returns **0 hits**, and
`grep -rni "clipboard" src/doc/` returns **0 hits**. `bufferfile`, `writebuf` and
`readbuf` are file-based (default `/tmp/screen-exchange`), not OSC 52. Screen emits
OSC in only two places in the whole tree, neither of which is 52, so **screen never
answers an OSC 52 query either**.

**The only escape hatch is DCS, and it is not OSC-52-aware.** **VERIFIED**,
`src/ansi.c`: `case DCS: LAY_DISPLAYS(&win->w_layer, AddStr(win->w_string)); break;`
and the manpage:

> `ESC P` (A) Device Control String — Outputs a string directly to the host terminal
> without interpretation.

Unlike tmux there is nothing to enable or disable. Correct usage takes a **single**
inner ESC (`ESC ESC` stores one ESC but stays in `STRESC`, so doubling is wrong):

```sh
printf '\033P\033]52;c;%s\007\033\\' "$(printf %s "$text" | base64 | tr -d '\n')"
```

**Two hard limits on this workaround**, both **VERIFIED**:

- **~569 bytes of clipboard payload.** `MAXSTR` is 768 (`src/screen.h`) and
  `w_string` is `char w_string[MAXSTR]`. Overflow does not truncate gracefully —
  `StringChar()` flips the parser to `LIT`, which means **the rest of the base64 is
  printed into the window as visible garbage**. (The ~569 figure is INFERRED
  arithmetic: 767 usable bytes minus the 8-byte `\033]52;c;` + `\a` framing, then
  base64's 3/4 ratio.)
- **Requires an attached, visible window** — `LAY_DISPLAYS` skips unless a canvas
  holds the layer.

**Release history: nothing was ever added.** **VERIFIED** —
`git log --all -i --grep="osc\|clipboard"` returns **0 commits**. `screen-v5` HEAD is
5.0.2; `master` is still 5.0.0. 5.0.1 was the CVE-2025-46802…46805 fixes.

### zellij

**zellij intercepts OSC 52 writes, decodes them, and routes them into its own
clipboard provider. It never forwards the inner sequence verbatim — it re-emits its
own. Reads are forwarded to the host but are default-deny.**

Source: `zellij-org/zellij` at `af38660` (2026-08-31), workspace version **0.46.0**.

**Interception.** **VERIFIED**, `zellij-server/src/panes/grid.rs`, the OSC 52 arm of
`Perform::osc_dispatch`:

```rust
b"52" => {
    if params.len() < 3 { return; }
    let clipboard = *params[1].get(0).unwrap_or(&b'c');
    match params[2] {
        b"?" => {
            self.pending_forwarded_queries.push(
                crate::host_query::HostQuery::ClipboardContent { selection: clipboard as char, .. });
        },
        base64 => {
            if let Ok(bytes) = BASE64_DECODER.decode(base64) {
                if let Ok(string) = String::from_utf8(bytes) {
                    self.pending_clipboard_update = Some(string);
                }
            };
        },
    }
},
```

Notes, all **VERIFIED** from this and the surrounding code:

- Short or malformed sequences (`params.len() < 3`) are silently dropped.
- Base64 padding is treated leniently (`DecodePaddingMode::Indifferent`).
- Non-UTF-8 payloads are dropped.
- **The selection char is parsed but unused on the write path** — it is read only in
  the `?` arm. An inner app cannot choose primary vs system; zellij's own
  `copy_clipboard` config decides.

zellij **advertises** OSC 52 support two ways — **VERIFIED**: XTGETTCAP answers `Ms`
with `\u{1b}]52;%p1%s;%p2%s\u{7}`, and Primary DA replies `\u{1b}[?62;4;52c` /
`\u{1b}[?62;52c`. The latter is exactly what tmux 3.6's DA sniffing keys on.

**Non-forwarding is asserted by an upstream unit test** — **VERIFIED**,
`zellij-server/src/panes/unit/grid_tests.rs`:

```rust
fn osc_52_write_is_not_forwarded() {
    vte_parser.advance(&mut grid, b"\x1b]52;c;aGVsbG8=\x07");
    assert!(grid.pending_forwarded_queries.is_empty(),
        "copying to the clipboard must not go through the forward path");
    assert_eq!(grid.pending_clipboard_update.as_deref(), Some("hello"));
}
```

**Whether it reaches the outer terminal depends entirely on `copy_command`.**
**VERIFIED**, `zellij-server/src/tab/clipboard.rs`:

```rust
pub(crate) enum ClipboardProvider { Command(CopyCommand), Osc52(Clipboard) }
```

with provider selection in `tab/mod.rs`:

```rust
let clipboard_provider = match copy_options.command {
    Some(command) => ClipboardProvider::Command(CopyCommand::new(command)),
    None => ClipboardProvider::Osc52(copy_options.clipboard),
};
```

- **`copy_command` unset (default)** — zellij emits *its own*
  `\u{1b}]52;{dest};{base64}\u{1b}\\` to every attached client, always terminated
  with `ST` and always with `dest` chosen by config (`c` or `p`), never by the app.
- **`copy_command` set** — the host terminal never sees an OSC 52 at all; the text is
  piped to the command's stdin. The command is split on spaces with **no shell and no
  quoting**, and the child is deliberately not killed (X11/Wayland helpers must stay
  alive to own the selection — see Q8).

**Config options and defaults.** **VERIFIED**, `zellij-utils/src/input/options.rs`
and `zellij-server/src/screen.rs`
(`copy_on_select.unwrap_or(true)`, `Clipboard::default() = System`):

| Option | Type | Default | Meaning |
| --- | --- | --- | --- |
| `copy_command` | string | **unset** | Command run on copy; text piped to stdin. When set, replaces OSC 52 entirely. |
| `copy_clipboard` | `system` \| `primary` | **`system`** | OSC 52 selection char: `system` → `c`, `primary` → `p` (→ `c` on macOS). Ignored when `copy_command` is set. |
| `copy_on_select` | bool | **`true`** | Copy on mouse release. |
| `dangerously_enable_paste_buffer_read` | bool | **`false`** | Allow inner programs to *read* the clipboard via `OSC 52 ; c ; ?`. |

The shipped `default.kdl` states the reasoning verbatim — **VERIFIED**:

> Whether to let programs running inside panes read the paste buffer (clipboard)
> with the OSC 52 escape sequence. When enabled, any program in any pane —
> including one running on a remote machine over SSH — can read the clipboard
> without the user being asked. Default: false

**Reads are default-deny and completely silent.** **VERIFIED**, `screen.rs`:

```rust
if let crate::host_query::HostQuery::ClipboardContent { .. } = query {
    if !self.paste_buffer_read_enabled {
        let _ = self.resume_pane_after_forward(pane_id, Vec::new());
        return STARTUP_SENTINEL_TOKEN;
    }
    return self.enqueue_clipboard_forward(pane_id, query);
}
```

When disabled the app gets **nothing** — not even the empty `OSC 52;c;` reply that a
host timeout would synthesize. Asserted upstream by the integration test
`a_clipboard_read_is_never_answered_when_the_option_is_off`. When enabled, clipboard
forwards get a 35-second timeout, versus 1 second for other host queries.

**No gate and no size limit on writes.** **VERIFIED** — there is no config flag,
permission check, or byte cap on the write branch. Any program in any pane, including
over SSH, can set the clipboard. At the parser level zellij builds `vte` with the
`std` feature, so OSC data is a `Vec<u8>` rather than the `no_std`
`ArrayVec<u8, 1024>`; **there is no 1024-byte OSC cap** in zellij's build.

**Version history.** **VERIFIED**, `CHANGELOG.md`: inner OSC 52 write support landed
in **0.31.2** (2022-08-17, "forward OSC52 clipboard copy events from terminals");
DA-based capability reporting was fixed in **0.44.1** (2026-04-07); OSC 52 *read*
forwarding and its default-deny gate arrived in **0.45.0** (2026-08-20). **INFERRED**:
reads were simply unsupported before 0.45.0.

### Multiplexer comparison

| | inner OSC 52 write | forwarded verbatim? | inner OSC 52 read | options |
| --- | --- | --- | --- | --- |
| **tmux** (default `external`) | **dropped entirely** | no | silent | `set-clipboard`, `get-clipboard` |
| **tmux** (`set-clipboard on`) | paste buffer + re-encoded outward via `Ms` | no (re-encoded) | answers from *tmux's own paste buffer* | as above |
| **GNU screen** | dropped entirely (unknown OSC) | no | never answers | none (DCS passthrough only) |
| **zellij** (defaults) | decoded → clipboard provider → re-encoded outward | no (test-enforced) | **silent** (default-deny) | `copy_command`, `copy_clipboard`, `copy_on_select`, `dangerously_enable_paste_buffer_read` |

**No multiplexer relays the original bytes. All three re-encode or drop.**

---

## Q4 — Is write gated separately from read?

**Yes, and read is consistently the more restricted of the two.** This is the
decisive answer for probe-based detection.

The read form — **VERIFIED**, ctlseqs: `OSC 52 ; Pc ; ? ST` asks the terminal to
report the selection; the terminal replies with an OSC 52 sequence carrying the
base64 data, terminated with the same terminator the query used.

Separate gating, per terminal:

| Terminal | Write default | Read default | Separately gated? |
| --- | --- | --- | --- |
| xterm | off (`SetSelection` disallowed) | off (`GetSelection` disallowed) | Yes — two distinct names in `disallowedWindowOps` |
| kitty | **allowed** | **ask** | Yes — `clipboard_control` tokens |
| Ghostty | **allow** | **ask** | Yes — `clipboard-write` vs `clipboard-read` |
| alacritty | **allowed** | **disabled** | Yes — `osc52 = OnlyCopy` |
| wezterm | **allowed** | **ignored entirely** | Yes, implicitly |
| Windows Terminal | **allowed** | parsed, never answered | Yes, implicitly |
| Konsole | **allowed** | not special-cased (would clear) | n/a |

All **VERIFIED** from the sources cited under Q1.

### xterm gates the two independently

**VERIFIED**, `ptyx.h`:

```c
#define SpecialWindowOps(w,name) (!TScreenOf(w)->disallow_win_ops[name])
#define AllowWindowOps(w,name)	(AllowXtermOps(w, allowWindowOps) || \
				 SpecialWindowOps(w,name))
```

`misc.c` uses `AllowWindowOps(xw, ewGetSelection)` on the `?` branch and
`AllowWindowOps(xw, ewSetSelection)` on the base64 branch, so read and write are
independently switchable. Both are denied by default and **both denials are entirely
silent** — the `if` simply does not execute.

The build-level switch removes both together — **VERIFIED**, xterm `INSTALL`:
"`--disable-paste64` … Do not compile-in code to support bracketed paste mode, along
with functions for setting/getting the selection data, termed "paste64"."

Note that `allowPasteControls` / `disallowedPasteControls` are unrelated to OSC 52;
they govern bracketed-paste sanitisation.

### tmux answers reads only under `set-clipboard on`, and then from its own buffer

The read branch sits *inside* `input_osc_52_parse`, **after** the
`set-clipboard != 2` gate, so `external` and `off` never reach it. **VERIFIED**,
`input.c`:

```c
	if (strcmp(end, "?") == 0) {
		input_osc_52_reply(ictx, *clip);
		return (0);
	}
```

A second option then applies. `get-clipboard` is **new in tmux 3.7**, with values
`off | buffer | request | both` and `.default_num = 1` → **`buffer`**. **VERIFIED
(local)**: `tmux show -g get-clipboard` → `get-clipboard buffer`. Manpage: "If `off`,
the request is ignored; if `buffer`, tmux responds with the newest paste buffer;
`request` causes tmux to request the clipboard from the most recently used client …
`both` is the same as `request` but also creates a paste buffer."

> **Discrepancy — flagged.** tmux's `CHANGES` entry for 3.7 says `get-clipboard`'s
> "default is off", but the source constant and the running binary both say
> `buffer`. **INFERRED** reading: "off" refers to the *new* request-from-the-outer-
> terminal behaviour, while `buffer` preserves the pre-3.7 behaviour. Trust the
> source constant.

Empirically **VERIFIED** on tmux 3.7c (raw-mode probe on `/dev/tty`, 2.5 s read
window, harness sanity-checked with `ESC [ c`):

| `set-clipboard` | `get-clipboard` | paste stack | reply |
| --- | --- | --- | --- |
| `off` | `buffer` | `SEEDDATA` | **0 bytes** |
| **`external` (default)** | `buffer` | `SEEDDATA` | **0 bytes** |
| `on` | `buffer` | `SEEDDATA` | `^[]52;c;U0VFRERBVEE=^[\` |
| `on` | `off` | `SEEDDATA` | **0 bytes** |
| `on` | `buffer` | *empty* | **0 bytes** |

Terminator mirroring is correct (ST→ST, BEL→BEL). Crucially, **what tmux returns is
tmux's own top paste buffer, not the outer terminal's real system clipboard** — under
the default `get-clipboard buffer` a read probe measures tmux, not the terminal.

The reply shape is also version-dependent — **VERIFIED**: tmux ≤ 3.6 always replied
with an *empty* selection field (`\033]52;;`), while 3.7+ echoes the requested code
(`\033]52;c;`) and returns nothing at all when the buffer stack is empty. A parser
must handle both.

### Concrete configurations where write works but a read probe returns nothing

All **VERIFIED** in the sources cited above.

| # | Named configuration | Write | `OSC 52;c;?` probe |
| --- | --- | --- | --- |
| 1 | **wezterm**, out of the box | works | queries ignored — silence |
| 2 | **alacritty**, out of the box (`osc52 = OnlyCopy`) | works | read disabled |
| 3 | **Windows Terminal ≥ 1.22**, out of the box | works | parsed, never answered |
| 4 | **kitty default** (`read-clipboard-ask`) | works immediately | **modal prompt**, defaulting to Deny |
| 5 | **kitty** `clipboard_control write-clipboard write-primary` | works | replies with **empty payload** — never matches a read-back |
| 6 | **kitty**, target not `c`/`s`/`p` (e.g. `OSC 52;q;?`) | discarded | silence |
| 7 | **Ghostty default** (`clipboard-read = ask`) | works immediately | **modal prompt**; if denied, empty payload |
| 8 | **Ghostty** `clipboard-read = deny` | works | absolute silence (`return;` before any I/O) |
| 9 | **xterm** with `GetSelection` disallowed but not `SetSelection` | works | absolute silence |
| 10 | **tmux** `set-clipboard on` + `get-clipboard off` | works | silence |
| 11 | **tmux** `set-clipboard on` + default `get-clipboard buffer`, empty buffer stack | works | silence |
| 12 | **zellij default** (`dangerously_enable_paste_buffer_read false`) | works | silence, test-enforced |
| 13 | **GNU screen**, any version | dropped | never answers |

**The converse also fails** — a positive probe does not prove write works: Ghostty
`clipboard-read = allow` + `clipboard-write = deny`; kitty
`clipboard_control read-clipboard`; xterm `disallowedWindowOps: SetSelection`.
VERIFIED in the same code paths.

**Conclusion: a read probe is not a valid detector of write support.** It produces
false negatives under the *default* configuration of tmux, zellij, xterm, wezterm,
alacritty and Windows Terminal, and it **pops an interactive modal** under the
*default* configuration of kitty and Ghostty — so it is not even a silent probe. It
is also not free of side effects: under Konsole a `?` query is not special-cased and
would be treated as a non-base64 payload, which per ctlseqs **clears the selection**.

---

## Q5 — Can you learn whether an OSC 52 write succeeded?

**No. There is no reply, no acknowledgement, and no status report. The write is
fire-and-forget.**

**VERIFIED by absence** — ctlseqs' OSC 52 entry defines a response only for the `?`
query form. Nothing in the specification defines a success, failure, or receipt
indication for the write form.

Confirmed in implementations — all **VERIFIED**:

- **xterm** — the `ewSetSelection` branch of `ManipulateSelectionData()` calls only
  `ClearSelectionBuffer` / `AppendToSelectionBuffer` / `CompleteSelection`. There is
  **no `unparseput*` call anywhere in it.** Zero bytes go back to the host, on
  success *and* on denial. The query branch is the only one that emits output.
- **kitty** — verbatim source comments in `kitty/clipboard.py`: "*OSC 52 has no way
  to report errors to the client so just discard the entire request*" and "*the data
  is not padded to a multiple of four bytes. This is tolerated for the legacy OSC 52
  protocol as it has no way to report errors to the client.*"
  `fulfill_legacy_write_request` returns without sending anything.
- **Ghostty** — verbatim source comments in `src/Surface.zig`: "*OSC 52 has no error
  responses, but the client is waiting on a reply*", and in `denyClipboardRequest`,
  "*A denied write simply doesn't happen*" (`.osc_52_write => {}`).
- **foot** — `osc.c` writes `"\033]52;"` only from `osc_from_clipboard()`, the query
  path.
- **tmux, zellij, screen** — no write-acknowledgement code exists.
  `input_osc_52()` returns `void` and writes nothing back; zellij's write arm only
  sets `pending_clipboard_update`; screen never reaches OSC 52 at all.

**The only real ACK mechanism in this space is a different escape code.** kitty's
**OSC 5522** clipboard protocol — also implemented by Ghostty — returns explicit
statuses `OK`, `DONE`, `EPERM`, `EFBIG`, `EINVAL`, `ENOSYS`. **VERIFIED**: kitty
`clipboard.py` `encode_response(status=..)`, `abort_write_request`,
`commit_write_request`; Ghostty `Surface.zig` `kittyClipboardStatus(..., .EPERM)`.
kitty's docs state the motivation verbatim
(<https://sw.kovidgoyal.net/kitty/clipboard/>): "Allow terminals to ask the user for
permission to access the clipboard **and report permission denied**".

Secondarily, xterm's `OSC 60`/`61`/`62` can report whether `SetSelection` is
currently blocked — but that is *capability discovery*, not acknowledgement of a
specific write, and it is xterm-only.

**Indirect verification (write a sentinel, then read back with `?`) does not work.**
Eleven independent things break it, all **VERIFIED** above:

1. **Read can be off while write works** — rows 1–3 and 8–13 of the Q4 table. You get
   silence and wrongly conclude the write failed. This is the *default* in tmux,
   zellij, wezterm, alacritty and Windows Terminal.
2. **Read can trigger an interactive prompt** — kitty and Ghostty by default. The
   probe steals user focus, and kitty's prompt defaults to Deny.
3. **A denied read returns an empty string, not an error** — indistinguishable from
   "clipboard genuinely empty" or "write failed".
4. **Silence is ambiguous with "no OSC 52 support at all."** No timeout is defined
   anywhere, so any detector must invent one. In xterm the `?` completes only after
   an asynchronous X-selection round trip whose latency xterm does not bound.
5. **The selection you read may not be the one you wrote.** kitty normalises `s` to
   clipboard and answers with `c`; xterm treats `s` as configurable and `0`–`7` as
   real cut-buffers; tmux collapses everything into one stack; kitty discards `q` and
   `0`–`7` entirely.
6. **The reply does not reliably echo the requested code.** xterm returns the whole
   `select_code` list; kitty returns only `c` or `p`; tmux ≤ 3.6 returns an empty
   field, tmux 3.7+ echoes it.
7. **Terminator mismatch.** xterm and tmux mirror the query's BEL/ST; Ghostty always
   emits `ST` regardless.
8. **It is destructive** — it requires overwriting the user's real clipboard with a
   sentinel. There is no non-destructive variant.
9. **Ordering is not guaranteed.** With Ghostty `clipboard-write = ask`, or through a
   multiplexer, the write may still be awaiting human confirmation while the read
   returns the old value. No barrier exists.
10. **Size limits are silent** — see Q2.
11. **Multiplexer chains measure the wrong layer.** Under tmux the `?` is answered by
    **tmux itself** from its own paste buffer, not by the outer terminal, so you
    measure tmux's capability rather than that of the terminal actually receiving the
    forwarded write. In zellij the read is a *different code path* from the write
    (test-enforced) with an independent default-deny gate, so neither says anything
    about the other.

**Failure is therefore silent in every one of these cases**, none of which is
distinguishable from success by the writing process:

- tmux with the default `set-clipboard external` — dropped.
- tmux with `set-clipboard on` but an outer `TERM` lacking `Ms` — not forwarded.
- tmux with `set-clipboard on` and `Ms` present, but the pane is in a **background
  window**, or **no client is attached**, or `PANE_REDRAW` is pending — buffer
  created, nothing forwarded, nothing queued.
- GNU screen, any version — dropped as an unknown OSC.
- zellij with `copy_command` set — the outer terminal never sees an OSC 52 at all.
- xterm with default `allowWindowOps: false` — refused.
- iTerm2 with default `AllowClipboardAccess = @NO` — refused.
- st and mintty at their compiled/config defaults — refused.
- VTE-based terminals (GNOME Terminal et al.) — parsed and discarded.
- Any window that is **unfocused** under alacritty, foot, or Windows Terminal.
- Payload over the terminal's cap — dropped (xterm, Ghostty, mintty) or, worse,
  **silently truncated** (iTerm2, contour, kitty), yielding a partial clipboard.
- Non-UTF-8 decoded payload under alacritty — discarded.

The only positive signals available are the two *capability* probes noted in Q1
(xterm's `OSC 6 0` / `OSC 6 1`, and the `52` marker in Primary DA under Windows
Terminal and foot). Both report configuration, not delivery, and neither is widely
implemented.

---

## Q6 — Chunking, bracketed paste, raw mode

### Chunking

**OSC 52 has no chunking mechanism. VERIFIED by absence** — ctlseqs defines exactly
`OSC 52 ; Pc ; Pd ST` with `Pd` a single base64 string. There is no continuation or
more-data parameter, and the word "chunk" does not appear in the OSC 52 entry. The
whole payload must arrive in one escape sequence.

**Client-side chunking does not work.** Sending N successive `OSC 52;c;…` sequences
produces N independent complete writes, each replacing the previous. VERIFIED across
kitty, foot, alacritty, Konsole, contour and xterm, all of which treat each
terminated OSC 52 as a finished write.

The contrast is explicit in kitty's own documentation — **VERIFIED**,
<https://sw.kovidgoyal.net/kitty/graphics-protocol/>:

> Since escape codes are of limited maximum length, the data will need to be chunked
> up for transfer. This is done using the `m` key. […] chunked up into chunks no
> larger than 4096 bytes.

and <https://sw.kovidgoyal.net/kitty/clipboard/>:

> There already exists an escape code to allow terminal programs to read/write plain
> text data from the system clipboard, **OSC 52**. kitty introduces a more advanced
> protocol […] The escape code is **OSC 5522**, an extension of OSC 52.

OSC 5522 does chunk, via repeated `type=wdata` packets terminated by an empty one.

**One terminal chunks internally and transparently: kitty.** **VERIFIED**,
`kitty/vt-parser.c` special-cases `is_osc_52(self)` to dispatch a partial OSC 52 and
call `continue_osc_52()`, which rewrites the buffer head as `52;;` and re-enters, so
a payload above 256 KiB is reassembled invisibly to the application.

### Bracketed paste

**No interaction with OSC 52 writes. VERIFIED.** Bracketed paste (`CSI ? 2004 h`)
governs how the terminal wraps *pasted input* it sends to the application
(`ESC[200~` … `ESC[201~`). OSC 52 write flows the other way and is never wrapped.
Nothing in ctlseqs connects the two.

For the read direction the answer is also no: the reply is a bare OSC 52 sequence,
not bracketed-paste-wrapped (xterm `misc.c`, foot `osc.c`).

One ordering interaction exists, in foot only — **VERIFIED**: OSC 52 replies share
foot's paste-data pipeline, and its code short-circuits with
`if (term->is_sending_paste_data) { /* FIXME: we should wait for the paste to end … */ }`,
so a read query issued mid-paste gets an empty reply. foot's CHANGELOG records the
related fix: "Other output (key presses, query replies etc) being mixed with paste
data, both interactive pastes and OSC-52 ([#2307])".

Adjacent but distinct: xterm's `allowPasteControls` (default `"false"`) and
`disallowedPasteControls` filter control characters out of *pastes* and do not
affect OSC 52 in either direction. VERIFIED.

### Raw mode and alternate screen

**Neither affects an OSC 52 write.**

- **Raw mode** (`ICANON`/`ECHO` off) is a line-discipline setting on the pty and is
  invisible to the emulator's escape parser. Writing OSC 52 to stdout behaves
  identically in cooked and raw mode. VERIFIED for the mechanism via termios(3).

  What *does* change is the **read** path: in canonical mode the reply lands in the
  line buffer, is subject to the 4096-char truncation quoted in Q2, is not readable
  until a delimiter arrives, and `ECHO` will print it back. This is why every OSC 52
  *query* implementation puts the tty in raw mode first.

- **Alternate screen** (`CSI ? 1049 h`) — **INFERRED**. None of the seven
  implementations read (xterm, foot, kitty, Ghostty, Konsole, contour, Windows
  Terminal) gates OSC 52 on screen mode, and no terminal documents an interaction.
  Absence of any check across seven implementations is strong but is not a positive
  statement by any source.

**The runtime conditions that actually swallow writes are focus and permission, not
mode** — see the list in Q5.

---

# Part 2 — Native clipboard crates

## Q7 — Maintenance status and backends

### arboard

| Fact | Value |
| --- | --- |
| Latest version | **3.6.1**, released **2025-08-23** |
| Repository | <https://github.com/1Password/arboard> |
| Maintenance | **Active**, but no release in ~12 months. `master` HEAD dated 2026-07-20; repo not archived; unreleased commits exist (`Cargo.toml` on master still says 3.6.1). |
| Unmaintained notice | **None.** README: "Please note that this is not an official 1Password product. Feature requests will be considered like any other volunteer-based crate." |

All **VERIFIED** via the crates.io API and the GitHub repository.

Backends — **VERIFIED (local)** from the vendored `arboard-3.6.1/Cargo.toml.orig`
and `src/platform/`:

- **Linux/X11** — `x11rb = "0.13"`, using `RustConnection`. `src/platform/linux/x11.rs`.
- **Linux/Wayland** — `wl-clipboard-rs = "0.9.0"`, **behind the non-default feature
  `wayland-data-control`**:

  ```toml
  [features]
  default = ["image-data"]
  wayland-data-control = ["wl-clipboard-rs"]
  ```

  Selection logic, `src/platform/linux/mod.rs`: Wayland is attempted only if the
  feature is compiled in **and** `WAYLAND_DISPLAY` is set; on failure it logs a
  `warn!` and falls back to X11.
- **macOS** — `objc2` 0.6, `objc2-foundation` 0.3, `objc2-app-kit` 0.3 (`NSPasteboard`).
- **Windows** — `windows-sys` (`>=0.52.0, <0.61.0`) **and** `clipboard-win = "5.3.1"`.
- Other Linux deps: `log`, `parking_lot` 0.12, `percent-encoding` 2.3.1, optional
  `image` 0.25.

### copypasta

| Fact | Value |
| --- | --- |
| Latest version | **0.10.2**, released **2025-04-25** |
| Repository | <https://github.com/alacritty/copypasta> (note: **not** rust-windowing; that URL redirects) |
| Maintenance | **Low activity.** Last commit 2025-05-10 ("Update objc2 dependencies"); not archived. |
| Unmaintained notice | None. |

Fork status and alacritty usage — **VERIFIED**. README line 1: "copypasta is a
[rust-clipboard](https://github.com/aweinstock314/rust-clipboard) fork, adding
support for the Wayland clipboard." Upstream `rust-clipboard` was last pushed
2023-05-19. Alacritty depends on it
(`copypasta = { version = "0.10.1", default-features = false }`) and re-enables the
backends through its own `x11`/`wayland` features.

Backends:

- **Linux/X11** — `x11-clipboard = "0.9.1"` (feature `x11`).
- **Linux/Wayland** — `smithay-clipboard = "0.7.0"` (feature `wayland`).
- Features: `default = ["x11", "wayland", "wayland-dlopen"]` — Wayland **is** on by
  default.
- **Crucial caveat, VERIFIED:** the Wayland backend is not auto-selected. `src/lib.rs`
  aliases `pub type ClipboardContext = x11_clipboard::X11ClipboardContext;` on all
  unix-non-mac targets. Wayland is reachable only via
  `unsafe fn create_clipboards_from_external(display: *mut c_void)`, i.e. **you must
  already own a `wl_display` pointer**. This makes it unusable for a windowless CLI
  on Wayland.
- With `--no-default-features` on Linux, `ClipboardContext` does not exist at all.
- **macOS** — `objc2` 0.6.1 stack. **Windows** — `clipboard-win = "5.4.0"`.

### cli-clipboard

| Fact | Value |
| --- | --- |
| Latest version | **0.4.0**, released **2022-12-13** |
| Repository | `actuallyallie/cli-clipboard`, now redirecting to `allie-wake-up/cli-clipboard` |
| Maintenance | **Effectively unmaintained.** Last commit 2023-02-24 (README only); last code commit 2022-12-12. |
| Unmaintained notice | None, but the README's "Alternatives" section points readers at arboard ("very active rust-clipboard fork") and copypasta. |

Backends — **VERIFIED**, no feature flags at all:

- **Linux** — `wl-clipboard-rs = "0.7"` **and** `x11-clipboard = "0.7"`, both
  unconditional. `src/linux_clipboard.rs` tries **Wayland first**, falls back to X11:

  ```rust
  match WaylandClipboardContext::new() {
      Ok(context) => Ok(.. LinuxContext::Wayland(context)),
      Err(_) => match X11ClipboardContext::<Clipboard>::new() { .. }
  }
  ```

- **macOS** — the old, unmaintained `objc = "0.2"` / `objc_id` / `objc-foundation`.
- **Windows** — `clipboard-win = "4.4"`, two majors behind the others.

---

## Q8 — The X11/Wayland clipboard-ownership lifetime problem

### Background (ICCCM)

**VERIFIED** — <https://tronche.com/gui/x/icccm/sec-2.html>:

- §2.2, owner responsibilities: the owner "receives a **SelectionRequest** event",
  "should use the target to decide the form into which the selection should be
  converted", and "should place the data resulting from converting the selection into
  the specified property on the requestor window." **The data lives in the owner
  process; nothing is stored in the X server.**
- §2.3.1, giving up ownership: "the client may destroy the window used as the owner
  value of the **SetSelectionOwner** request, or the client may terminate. In both
  cases, the ownership of the selection involved will revert to **None**."
- §2.6.3, CLIPBOARD: "It should assert ownership of the CLIPBOARD. If it succeeds in
  acquiring ownership, it should be prepared to respond to a request for the contents
  of the CLIPBOARD in the usual way (retaining the data to be able to return it)."

arboard cites these itself in `src/platform/linux/x11.rs`.

### arboard: what `set().wait()` actually does

**API — VERIFIED (local)**, `src/platform/linux/mod.rs`:

```rust
pub trait SetExtLinux: private::Sealed {
    fn wait(self) -> Self;
    fn wait_until(self, deadline: std::time::Instant) -> Self;
    fn clipboard(self, selection: LinuxClipboardKind) -> Self;
    fn exclude_from_history(self) -> Self;
}

pub(crate) enum WaitConfig { Until(Instant), Forever, #[default] None }
```

**It blocks the calling thread. There is no async variant.** **VERIFIED (local)**,
`src/platform/linux/x11.rs`, `Inner::write`:

```rust
match wait {
    WaitConfig::None => {}
    WaitConfig::Forever => { drop(data_guard); selection.data_changed.wait(&mut guard); }
    WaitConfig::Until(deadline) => { drop(data_guard); selection.data_changed.wait_until(&mut guard, deadline); }
}
```

**It unblocks on ownership loss, not on paste.** The `data_changed`
`parking_lot::Condvar` has exactly two notify sites — **VERIFIED (local)** by grep
over `x11.rs`:

1. `serve_requests`, on `Event::SelectionClear` — another X client took ownership of
   that selection, i.e. the user copied something else.
2. `Inner::write` itself — the same process overwrote the selection.

A `SelectionRequest` (an actual paste) does **not** wake it. `parking_lot`'s Condvar
does not wake spuriously, so `Forever` really is forever.

**Documentation contradiction — flagged.** arboard's **README** claims `.wait()`
"will block the calling thread until another app has requested, and then received,
the data." **The source does not implement that.** The rustdoc on
`SetExtLinux::wait` is the accurate one: "this method will not only have the
contents of the clipboard be set, but will also wait and continue to serve requests
until the clipboard is overwritten." Trust the rustdoc.

`wait_until(deadline)` discards the returned `WaitTimeoutResult`, so **you cannot
tell whether it timed out or the clipboard was actually replaced**. VERIFIED (local).

### arboard spawns a background thread unconditionally

Even without `.wait()`. **VERIFIED (local)**, `x11.rs`:

```rust
static CLIPBOARD: Mutex<Option<GlobalClipboard>> = parking_lot::const_mutex(None);
...
pub(crate) fn new() -> Result<Self> {
    let mut global_cb = CLIPBOARD.lock();
    if let Some(global_cb) = &*global_cb { return Ok(Self { inner: Arc::clone(&global_cb.inner) }); }
    let ctx = Arc::new(Inner::new()?);
    join_handle = std::thread::spawn(move || { if let Err(error) = serve_requests(ctx) { error!(..) } });
    *global_cb = Some(GlobalClipboard { inner: Arc::clone(&ctx), server_handle: join_handle });
```

It is a **process-global singleton** shared by every `Clipboard` instance. It dies
only when the **last** one is dropped — `impl Drop for Clipboard`:

```rust
const MIN_OWNERS: usize = 3; // global, server thread, self
if Arc::strong_count(&self.inner) == MIN_OWNERS {
    if let Err(e) = self.inner.ask_clipboard_manager_to_request_our_data() { .. }
    let global_cb = global_cb.take();
    self.inner.server.conn.destroy_window(self.inner.server.win_id)  // -> ownership reverts to None
    ..
    server_handle.join()
}
```

Cost summary: **one thread per process, not per call; no fork; `Clipboard::new()`
does not block.** Only `.wait()` blocks.

### What happens on process exit without `.wait()`

arboard's own docs — **VERIFIED (local)**, `src/platform/linux/mod.rs`, mirrored at
<https://docs.rs/arboard/3.6.1/arboard/trait.SetExtLinux.html>:

> The Wayland and X11 clipboards work by having the clipboard content being, at any
> given time, "owned" by a single process, and that process is expected to reply to
> all the requests from any other system process that wishes to access the
> clipboard's contents. **As a consequence, when that process exits the contents of
> the clipboard will effectively be cleared since there is no longer anyone around to
> serve requests for it.**
>
> This poses a problem for short-lived programs that just want to copy to the
> clipboard and then exit […] you can offload the actual work to a newly-spawned
> daemon process which will run in the background (potentially outliving the current
> process) and serve all the requests.

`Clipboard`'s own rustdoc adds: "when the last `Clipboard` instance is dropped, the
contents may become unavailable to other apps."

**Debug-build warning — VERIFIED (local)**, `x11.rs` under `#[cfg(debug_assertions)]`:
if the `Clipboard` is dropped less than 100 ms after a write, arboard prints to
stderr (or `log::warn!` if stderr is not a terminal):

> Clipboard was dropped very quickly after writing ({elapsed}ms); clipboard managers
> may not have seen the contents. Consider keeping `Clipboard` in more persistent
> state somewhere or keeping the contents alive longer using `SetLinuxExt` and/or
> threads.

### Clipboard-manager handoff on drop

**arboard actively participates in the freedesktop CLIPBOARD_MANAGER protocol.**

Spec — **VERIFIED**, <https://www.freedesktop.org/wiki/ClipboardManager/> (note this
is *not* ICCCM, though it builds on ICCCM §1.2.6 manager selections and §2.6.3
side-effect targets):

> If a client needs to exit while owning the CLIPBOARD selection, it should request
> the clipboard manager to take over the ownership of the clipboard, using the
> SAVE_TARGETS mechanism. If there is no clipboard manager, or if the SAVE_TARGETS
> conversion fails, the application should simply exit.

arboard's implementation — **VERIFIED (local)**, `Inner::ask_clipboard_manager_to_request_our_data`:

```rust
self.server.conn.convert_selection(
    self.server.win_id, self.atoms.CLIPBOARD_MANAGER, self.atoms.SAVE_TARGETS,
    self.atoms.ARBOARD_CLIPBOARD, Time::CURRENT_TIME)?;
*handover_state = ManagerHandoverState::InProgress;
let max_handover_duration = Duration::from_millis(100);
let result = self.handover_cv.wait_for(&mut handover_state, max_handover_duration);
```

Cost and caveats: **only `CLIPBOARD` is handed over** (per the spec), the budget is a
hard **100 ms**, and on timeout arboard only logs
`warn!("Could not hand the clipboard contents over to the clipboard manager. The request timed out.")`
and returns `Ok(())` — **silent data loss**. `exclude_from_history()` deliberately
skips the handover and calls `clear()` instead, so managers do not persist secrets.

**copypasta and cli-clipboard do NOT do this.** **VERIFIED by absence** —
`x11-clipboard`'s public API is only `new`/`load`/`load_wait`/`store`; there is no
`store_wait`, no `CLIPBOARD_MANAGER`, no `SAVE_TARGETS`. With those crates you can
only rely on a manager that proactively polls or XFixes-watches the selection
(klipper, GNOME's mutter clipboard manager, clipmenu, greenclip); a manager relying
solely on the exit-time handshake will lose the data.

### No daemonize helper in the crate

**VERIFIED (local)** — grep for `daemon` across `arboard/src/` finds only doc
comments. The documented pattern is `examples/daemonize.rs`, linked from the
`wait()` rustdoc. It **re-execs the current binary** with a sentinel argument rather
than calling `fork(2)`:

```rust
const DAEMONIZE_ARG: &str = "__internal_daemonize";
#[cfg(target_os = "linux")]
if env::args().nth(1).as_deref() == Some(DAEMONIZE_ARG) {
    Clipboard::new()?.set().wait().text("Hello, world!")?;
    return Ok(());
}
...
process::Command::new(env::current_exe()?)
    .arg(DAEMONIZE_ARG)
    .stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null())
    .current_dir("/")
    .spawn()?;
```

### Wayland

arboard maps wait to wl-clipboard-rs' foreground flag — **VERIFIED (local)**,
`src/platform/linux/wayland.rs` (identical in `set_text`, `set_html`, `set_image`,
`set_file_list`):

```rust
let mut opts = Options::new();
opts.foreground(matches!(wait, WaitConfig::Forever));
```

**Finding: `wait_until(deadline)` is silently ignored on Wayland.**
`WaitConfig::Until(_)` does not match `Forever`, so `foreground(false)` is used and
the call returns immediately with no deadline honoured. VERIFIED (local).

**wl-clipboard-rs spawns a thread; it does not fork.** **VERIFIED (local)**,
`wl-clipboard-rs-0.9.3/src/copy.rs`:

```rust
pub(crate) fn copy_internal(options: Options, sources: Vec<MimeSource>, socket_name: Option<OsString>) -> Result<(), Error> {
    if options.foreground {
        prepare_copy_internal(options, sources, socket_name)?.serve()
    } else {
        // The copy must be prepared on the thread because PreparedCopy isn't Send.
        let (tx, rx) = sync_channel(1);
        thread::spawn(move || match prepare_copy_internal(options, sources, socket_name) {
            Ok(prepared_copy) => { drop(tx.send(None)); drop(prepared_copy.serve()); }
            Err(err) => drop(tx.send(Some(err))),
        });
        ...
    }
}
```

`Options::foreground` docs — **VERIFIED (local)**: "Setting this flag will result in
the call to `copy()` **blocking** until all data sources it creates are destroyed,
e.g. until someone else copies something into the clipboard."

`prepare_copy` docs — **VERIFIED (local)**: "This function can be used instead of
`copy()` when it's desirable to separately prepare the copy operation, handle any
errors that this may produce, and then start the serving loop, **potentially past a
fork (which is how `wl-copy` uses it)**. It is meant to be used in the foreground
mode and **does not spawn any threads**." It panics if `foreground` is false.

So forking is done by the `wl-copy` **binary**, not by the library. arboard never
sets `serve_requests`, so it is always `ServeRequests::Unlimited`.

**The lifetime problem is identical on Wayland**: the `data_source` object is served
by the owning process, so process exit destroys it. The only difference from X11 is
that the default non-foreground path leaves a *detached* thread — dropping arboard's
`Clipboard` does not stop it, but exiting does.

**No SAVE_TARGETS analogue exists on Wayland.** `wlr-data-control` /
`ext-data-control` *is* the clipboard-manager protocol — **VERIFIED**,
<https://wayland.app/protocols/wlr-data-control-unstable-v1>: "This protocol allows a
privileged client to control data devices. In particular, the client will be able to
manage the current selection and take the role of a clipboard manager." A manager
(cliphist, wl-clip-persist, Klipper) re-owns the selection after you exit.
**INFERRED**: with no manager running, Wayland content dies with the process exactly
as on X11.

**GNOME/mutter caveat — VERIFIED by source-tree listing.** `src/wayland/` in
GNOME/mutter contains only `meta-wayland-data-{device,offer,source}[-primary].{c,h}`
— no `*data-control*` files. Mutter implements neither `wlr-data-control` nor
`ext-data-control`. It has its own internal clipboard manager
(`src/core/meta-clipboard-manager.c`), which is what preserves content on GNOME.
**Practical effect: arboard's `wayland-data-control` backend does not work under
GNOME Wayland and falls back to XWayland**, matching arboard's README advice: "If you
or a user's desktop doesn't support these protocols, `arboard` won't function in a
pure Wayland environment. It is recommended to enable `XWayland` for these cases."

---

## Q9 — No display server at all (plain SSH, no `$DISPLAY`, no `$WAYLAND_DISPLAY`)

**None of the three panic. All return `Err`. None hangs. None has any fallback.**

**VERIFIED**: `grep -rin "clip.exe\|wsl\|OSC 52\|osc52\|ssh"` across `arboard/src`,
`copypasta/src`, `cli-clipboard/src` and `arboard/README.md` returns **zero matches**.

### arboard — reproduced empirically

**VERIFIED (local).** A probe built against arboard 3.6.1 with default features:

```rust
fn main() {
    match arboard::Clipboard::new() {
        Ok(_) => println!("OK: clipboard created"),
        Err(e) => println!("ERR debug={:?} display={}", e, e),
    }
}
```

```console
$ ./target/debug/arbtest                                    # with a display
OK: clipboard created

$ env -u DISPLAY -u WAYLAND_DISPLAY ./target/debug/arbtest  # no display server
ERR debug=Unknown { .. } - "Unknown error while interacting with the clipboard: X11 server connection timed out because it was unreachable" display=Unknown error while interacting with the clipboard: X11 server connection timed out because it was unreachable

$ time (env -u DISPLAY -u WAYLAND_DISPLAY ./target/debug/arbtest)
... 0.00s user 0.00s system 93% cpu 0.002 total
```

Three facts follow:

1. It returns `Err`, does **not** panic.
2. It fails in **~2 ms** — despite the message, nothing actually times out, so there
   is no hang to design around.
3. The variant is **`Error::Unknown { description: "X11 server connection timed out
   because it was unreachable" }` — NOT `Error::ClipboardNotSupported`.**

The message is actively misleading and the cause is discarded — **VERIFIED (local)**,
`x11.rs`:

```rust
let (conn, screen_num): (RustConnection, _) =
    RustConnection::connect(None).map_err(|_| {
        Error::unknown("X11 server connection timed out because it was unreachable")
    })?;
```

Underneath, `x11rb`'s `parse_display(None)` returns
`DisplayParsingError::DisplayNotSet` when `$DISPLAY` is absent; `map_err(|_| ..)`
throws that away.

`arboard::Error` variants are `ContentNotAvailable`, `ClipboardNotSupported`,
`ClipboardOccupied`, `ConversionFailure`, `Unknown { description: String }` —
**VERIFIED (local)**, `src/common.rs`. `ClipboardNotSupported` is documented as
covering "Using the Primary clipboard with an older Wayland compositor" and "Using
the Secondary clipboard on Wayland"; it is **not** used for "no display server".

Implication: **do not pattern-match on the error string, and do not surface it to
users verbatim** — over SSH it will falsely claim a timeout.

Related report: <https://github.com/1Password/arboard/issues/98>.

### copypasta

Returns `Err(Box<dyn Error + Send + Sync>)`. On Linux `ClipboardContext` aliases the
X11 backend, so `X11ClipboardContext::new()` → `RustConnection::connect(None)?` →
`XcbConnect(ConnectError::DisplayParsingError(DisplayNotSet))`, displayed as
"XCB - couldn't establish conection: DisplayParsingError(DisplayNotSet)" (the typo is
upstream). VERIFIED.

It never even tries Wayland, since that backend needs an externally supplied
`wl_display`. Note that *alacritty* calls `ClipboardContext::new().unwrap()`, so
alacritty panics — but the crate does not.

### cli-clipboard

`LinuxClipboardContext::new()` tries Wayland, discards the error, then X11, and
returns the X11 error as `Box<dyn Error>`. No panic, no fallback. VERIFIED.

---

## Q10 — WSL

**None of the three crates has WSL-specific code, and none shells out to `clip.exe`.**
**VERIFIED** — grep for `clip.exe` and `wsl` across all three `src/` trees returns
nothing. `clip.exe` is a widely used *user-level* convention
(`echo hi | clip.exe`) but is not a code path in any of these crates.

**Under WSLg there is a display server.** **VERIFIED** —
<https://github.com/microsoft/wslg> README:

> The system distro is a containerized Linux environment where the WSLg XServer,
> Wayland server and Pulse Audio server are running.
>
> We preconfigure the user distro environment variables **DISPLAY, WAYLAND_DISPLAY**
> and PULSE_SERVER to refer these servers by default so WSLg lights up out of the box.

WSLg's compositor is **Weston** with XWayland. Consequences:

- **arboard, default features** — X11 backend over XWayland: works. VERIFIED path,
  **INFERRED** outcome (not executed under WSL).
- **arboard + `wayland-data-control`** — `WAYLAND_DISPLAY` is set, so Wayland is tried
  first and **fails**, logs the fallback warning, and drops to X11. **Weston
  implements neither `wlr-data-control` nor `ext-data-control`** — VERIFIED by a
  full-tree grep for `data.control` over the Weston repository, which returns zero
  hits.
- **copypasta** — X11 over XWayland works; its Wayland backend remains unreachable
  without a `wl_display`.
- **cli-clipboard** — tries Wayland (fails on Weston), falls back to X11: works.
- **WSL1/WSL2 without WSLg** (headless, no `$DISPLAY`) — all three fail exactly as in
  Q9.

**INFERRED**: on WSLg, arboard-over-XWayland writes to the *Linux* clipboard; WSLg
does bridge X/Wayland to the Windows clipboard, but the ownership problem still
applies, so a short-lived process must `.wait()` or daemonize.

---

## Q11 — Build and runtime dependencies on Linux

### x11rb is pure Rust in the configuration all three use

**VERIFIED** — `x11rb` 0.13's `Cargo.toml` puts the FFI path behind an opt-in feature:

```toml
# Without this feature, all uses of `unsafe` in the crate are forbidden via
# #![deny(unsafe_code)]. This has the effect of disabling the XCB FFI bindings.
allow-unsafe-code = ["libc", "as-raw-xcb-connection"]
dl-libxcb = ["allow-unsafe-code", "libloading", "once_cell"]
```

`libc`, `libloading` and `as-raw-xcb-connection` are all optional. There is **no
`build.rs` and no `links = "xcb"`**. Transport is `rustix` over raw Unix-domain/TCP
sockets. arboard explicitly uses `x11rb::rust_connection::RustConnection`.

**Conclusion: no `libX11`, no `libxcb`, no `libXfixes` — nothing from `xorg-dev` — is
needed at build or run time by any of the three.**

**cli-clipboard's README is stale and wrong.** It says "On Linux, you'll need to have
xorg-dev and libxcb-composite0-dev to compile." That was true for `x11-clipboard`
≤ 0.5.x, which depended on the `xcb` FFI crate. From 0.7.0 onward the dependency is
`x11rb`, and cli-clipboard 0.4.0 pins `x11-clipboard = "0.7"`. VERIFIED.

### D-Bus and shelling out

**Neither.** **VERIFIED** — no `dbus`/`zbus`/`libdbus-sys` crate appears in any of the
three dependency trees, and there is no `Command::new("wl-copy")`/`xclip`/`xsel`
anywhere in any `src/`. `wl-clipboard-rs` speaks the Wayland wire protocol directly;
the `wl-copy`/`wl-paste` binaries live in a separate workspace member
(`wl-clipboard-rs-tools`) that arboard does not depend on. `smithay-clipboard`
likewise speaks the protocol via `wayland-client`.

### arboard: default vs `wayland-data-control`

**Default features (`image-data`)** — full Linux dependency set: `image`, `log`,
`parking_lot`, `percent-encoding`, `x11rb` (with `gethostname`, `rustix`,
`x11rb-protocol`).

**System libraries required: none beyond libc.** No `*-sys` crate, no `build.rs`
probing pkg-config, no `links =`. `libc` enters only via `parking_lot_core`. arboard
opens `/tmp/.X11-unix/X<n>` (or TCP) itself and reads `~/.Xauthority`.

**With `--features wayland-data-control`** — adds `wl-clipboard-rs` and its tree
(`os_pipe`, `rustix`, `thiserror`, `tree_magic_mini`, `wayland-backend`,
`wayland-client`, `wayland-protocols`, `wayland-protocols-wlr`).

**Still no system libraries.** The critical detail — **VERIFIED**: `wayland-backend`
resolves with **no features**, so `wayland-sys` is compiled with no features, and
`wayland-sys/build.rs` probes pkg-config only when `CARGO_FEATURE_CLIENT`/`SERVER`/
`CURSOR`/`EGL` is set:

```rust
fn main() {
    if std::env::var_os("CARGO_FEATURE_DLOPEN").is_some() { return; }  // Do not link to anything
    if std::env::var_os("CARGO_FEATURE_CLIENT").is_some() { Config::new().probe("wayland-client").unwrap(); }
    ...
}
```

So **arboard + `wayland-data-control` does not link or dlopen
`libwayland-client.so`.** Runtime requirements are purely environmental:
`$XDG_RUNTIME_DIR`, the `$WAYLAND_DISPLAY` socket, and a compositor implementing
`ext-data-control-v1` or `wlr-data-control-unstable-v1`.

### copypasta does need libwayland

**VERIFIED.** With default features, `smithay-clipboard` hard-requires
`wayland-backend/client_system`, which enables `wayland-sys/client`:

- With copypasta's default `wayland-dlopen` feature, `wayland-sys/dlopen` is also on,
  `build.rs` returns early, and `libwayland-client.so.0` is **dlopen'd at runtime**.
- **If you disable `wayland-dlopen` but keep `wayland`, the build runs
  `pkg_config::probe("wayland-client").unwrap()`** — you then need `libwayland-dev` at
  build time and link `-lwayland-client`.
- `wayland-backend` also carries `cc` as a build dependency, invoked only when
  `CARGO_FEATURE_LOG` is set.
- The X11 side is pure Rust, as with arboard.

### cli-clipboard

`wl-clipboard-rs 0.7` → `wayland-client 0.29.5` / `wayland-sys 0.29.5` with no
features (same feature-gated pkg-config probe, so no libwayland linked), plus
`nix 0.24`, `tempfile`, `tree_magic_mini`; and `x11-clipboard 0.7.1` → `x11rb 0.10.1`.
**No system libs beyond libc**, despite the README. The downside is that it is stuck
on the pre-0.30 wayland-rs stack.

### musl and static linking

- **arboard: works.** **VERIFIED** empirically by the researching agent —
  `cargo check --target x86_64-unknown-linux-musl --features wayland-data-control`
  completes without errors. Consistent with the dependency graph: no `*-sys`, no
  pkg-config, no `links=`, and `rustix` on the `linux-raw-sys` backend. Good fit for
  a fully static musl binary.
- **copypasta with default features on static musl: broken by construction.**
  **INFERRED**, strongly grounded: the Wayland backend obtains
  `libwayland-client.so.0` via `dlopen`, and a fully statically linked musl binary
  has no working dynamic loader. Workarounds: `--no-default-features --features x11`
  (pure Rust, fully static), or build dynamically linked.
- **copypasta without `wayland-dlopen`** needs `wayland-client.pc` for the target and
  a `-lwayland-client` link — exactly the case that breaks cross and static builds.
- **cli-clipboard on musl**: no `*-sys` linking in the graph, so it should build.
  **INFERRED**; not verified empirically.
- No open musl or static-linking issue was found in `1Password/arboard`.

---

## Cross-cutting comparison

| | arboard 3.6.1 | copypasta 0.10.2 | cli-clipboard 0.4.0 |
| --- | --- | --- | --- |
| Maintained | Yes (commits to 2026-07) | Barely (last commit 2025-05) | No (last commit 2023-02) |
| Wayland for a *windowless* CLI | Yes, `wayland-data-control` (opt-in) | **No** — needs a `wl_display` pointer | Yes, always on |
| X11 stack | x11rb (pure Rust) | x11-clipboard 0.9 → x11rb (pure Rust) | x11-clipboard 0.7 → x11rb 0.10 (pure Rust) |
| Blocking "keep clipboard alive" API | `SetExtLinux::wait()` / `wait_until(Instant)` | **none** | **none** |
| CLIPBOARD_MANAGER / SAVE_TARGETS handoff on exit | Yes (100 ms budget) | **No** | **No** |
| `wait_until` honoured on Wayland | **No — silently ignored** | n/a | n/a |
| System libs on Linux | none (even with Wayland) | libwayland-client (dlopen) for Wayland | none |
| Error with no display | `Error::Unknown{ "X11 server connection timed out because it was unreachable" }` | `XcbConnect(DisplayParsingError(DisplayNotSet))` | same as copypasta |
| OSC 52 / SSH / `clip.exe` fallback | none | none | none |

---

## Open items

1. **GNU screen was not tested empirically** — it is not installed on the survey
   machine, and `git.savannah.gnu.org` became unreachable partway through the
   investigation, so the findings could not be re-verified against a fresh clone. The
   `screen-v4` branch was never reached; the historical evidence comes from the 2012
   `next` branch. The conclusion (no OSC 52 anywhere) is source-solid but untested.
2. **Konsole's behaviour on a `?` read query** — inferred to clear the selection from
   reading the code path; not reproduced against a running Konsole.
3. **kitty's `no-append` token** — referenced in older material, absent from the
   current `clipboard_control` implementation. Its removal date was not established
   from a primary source.
4. **Terminal.app** — no Apple statement either way was found; the finding rests on
   absence of `Ms` in a third-party terminfo description.

---

## Sources

Primary sources consulted, by area.

**Specifications**
- XTerm Control Sequences — <https://invisible-island.net/xterm/ctlseqs/ctlseqs.html>
- ICCCM §2, selections — <https://tronche.com/gui/x/icccm/sec-2.html>
- freedesktop Clipboard Manager Specification — <https://www.freedesktop.org/wiki/ClipboardManager/>
- `wlr-data-control-unstable-v1` — <https://wayland.app/protocols/wlr-data-control-unstable-v1>
- termios(3) — <https://man7.org/linux/man-pages/man3/termios.3.html>

**Terminals**
- xterm — `man xterm` (410, local); `misc.c`, `charproc.c`, `button.c`, `ptyx.h`, `main.h`, `configure.in`
- kitty — <https://sw.kovidgoyal.net/kitty/conf/>, <https://sw.kovidgoyal.net/kitty/clipboard/>, <https://sw.kovidgoyal.net/kitty/graphics-protocol/>; `kitty/clipboard.py`, `kitty/vt-parser.c`
- alacritty — `extra/man/alacritty.5.scd`, `CHANGELOG.md`, `alacritty/src/event.rs`, `alacritty_terminal/src/term/mod.rs`
- wezterm — <https://wezterm.org/escape-sequences.html>; `term/src/terminalstate/performer.rs`
- foot — `doc/foot.ini.5.scd`, `CHANGELOG.md`, `osc.c`
- Ghostty — <https://ghostty.org/docs/config/reference>; `src/config/Config.zig`, `src/terminal/osc.zig`
- iTerm2 — <https://iterm2.com/documentation-preferences-general.html>; `sources/Settings/iTermPreferences.m`, `sources/VT100/VT100XtermParser.m`, `VT100Terminal.m`
- Windows Terminal — `src/cascadia/TerminalSettingsModel/MTSMSettings.h`, `doc/cascadia/profiles.schema.json`, `src/cascadia/TerminalCore/TerminalApi.cpp`, `src/host/outputStream.cpp`
- VTE — `src/parser-osc.hh`, `src/vteseq.cc`; issue <https://gitlab.gnome.org/GNOME/vte/-/issues/2495>
- Konsole — `src/Vt102Emulation.{h,cpp}`, commit `9f7a2b846`
- st — <https://git.suckless.org/st>, `config.def.h`, `st.c`, `st.info`
- contour — `src/vtbackend/screen/Screen.cpp`, `src/vtbackend/vt/Sequence.hpp`
- mintty — `docs/mintty.1`, `src/config.c`, `src/termout.c`
- PuTTY — `terminal/terminal.c`
- rxvt-unicode — `src/rxvt.h`, urxvt(7)

**Multiplexers**
- tmux — `man tmux` (3.7c, local), `options-table.c`, `input.c`, `tty.c`,
  `tty-term.c`, `tty-features.c`, `tty-keys.c`, `window-copy.c`, `screen-write.c`,
  `tmux.h`, `CHANGES`, `regress/input-osc.sh` — <https://github.com/tmux/tmux>
- GNU screen — `src/ansi.c`, `src/display.c`, `src/screen.h`, `src/window.h`,
  `src/comm.c`, `src/doc/screen.1`, `src/NEWS` —
  <https://git.savannah.gnu.org/cgit/screen.git>, branches `master`, `screen-v5`
  (5.0.2), `next`
- zellij — <https://zellij.dev/documentation/options>;
  `zellij-server/src/panes/grid.rs`, `zellij-server/src/tab/clipboard.rs`,
  `zellij-server/src/tab/copy_command.rs`, `zellij-server/src/tab/mod.rs`,
  `zellij-server/src/screen.rs`, `zellij-server/src/host_query.rs`,
  `zellij-utils/src/input/options.rs`, `zellij-utils/assets/config/default.kdl`,
  `zellij-server/src/panes/unit/grid_tests.rs`,
  `zellij-integration-tests/tests/paste_read.rs`, `CHANGELOG.md` —
  <https://github.com/zellij-org/zellij> at 0.46.0

**Crates**
- arboard — <https://github.com/1Password/arboard>, <https://docs.rs/arboard/3.6.1/>; vendored `arboard-3.6.1` source read locally
- wl-clipboard-rs — <https://github.com/YaLTeR/wl-clipboard-rs>, <https://docs.rs/wl-clipboard-rs/0.9.3/>; vendored `wl-clipboard-rs-0.9.3` source read locally
- copypasta — <https://github.com/alacritty/copypasta>
- cli-clipboard — <https://github.com/allie-wake-up/cli-clipboard>
- x11rb — <https://github.com/psychon/x11rb>, tag v0.13.0
- wayland-rs — `wayland-sys/build.rs`, `wayland-backend/Cargo.toml`
- mutter — `src/wayland/`, `src/core/meta-clipboard-manager.c`
- WSLg — <https://github.com/microsoft/wslg>
