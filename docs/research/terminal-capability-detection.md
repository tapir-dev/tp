# Terminal capability detection: OSC 8, truecolor, cursor control

Research question: what can an `auto` capability default honestly mean in a TUI that
queries the terminal **once**, during a start-up handshake, and can never probe again?

Three sub-questions: OSC 8 hyperlinks on non-supporting terminals; truecolor detection;
the "hardware cursor" (visibility and shape).

**Marker discipline.** Every factual claim carries one of:

- **[VERIFIED]** — read in a primary source; URL inline.
- **[VERIFIED-local]** — measured against the local ncurses 6.6 terminfo database via `infocmp -x`.
- **[INFERRED]** — reasoned; the basis is named.
- **[UNKNOWN]** — could not confirm; stated rather than guessed.

Primary sources here means terminal emulator source code, DEC/ECMA specs, xterm's
`ctlseqs`, ncurses man pages and `terminfo.src`, first-party docs, and maintainer
statements on public lists and trackers. Secondary write-ups are cited only where a
maintainer is speaking, and are marked as such.

---

## Executive summary

| Capability | Can a startup probe detect it? | What `auto` can honestly mean |
|---|---|---|
| OSC 8 hyperlinks | **No.** No query exists at any layer. | "Matched a known-good identity" — an allowlist, not a detection. |
| Truecolor | **Partially.** Several signals, none complete. | A promotion ladder: env, then terminfo, then one fenced probe, then name allowlist; else 256. |
| Cursor hide/show | **No probe needed.** Effectively universal. | Just do it. The hard parts are restore-on-exit and accessibility, neither of which is detectable. |

The through-line: **for all three, an honest `auto` is a heuristic ladder, not a
capability test.** That is the argument for an explicit user override being mandatory
rather than a nicety.

---

## 1. OSC 8 hyperlinks on terminals that do not support them

### 1.1 What the spec guarantees

**[VERIFIED]** The sequence is `OSC 8 ; params ; URI ST`, closed with `OSC 8 ; ; ST`.
`ST` is `ESC \`; `BEL` (`\a`) is the widespread non-standard alternative that
"originates from XTerm" —
[OSC 8 spec gist, raw](https://gist.githubusercontent.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda/raw).

**[VERIFIED]** The backward-compatibility clause, verbatim:

> Any terminal that correctly implements OSC parsing according to ECMA-48 is guaranteed
> not to suffer from compatibility issues. That is, even if explicit hyperlinks aren't
> supported, the target URI is silently ignored and the supposed-to-be-visible text is
> displayed, without artifacts.
>
> If a terminal emits garbage upon an OSC 8 explicit hyperlink sequence, that terminal is
> buggy according to ECMA-48. It is, and will always be, outside of the scope of this
> specification to deal with buggy terminals.
>
> At this moment, terminals known to be buggy (OSC 8 resulting in display corruption) are
> VTE versions up to 0.46.2 and 0.48.1, Windows Terminal up to 0.9, Emacs's built-in
> terminal, and screen with 700+ character long URLs.

**[VERIFIED]** The spec also constrains payload bytes: "the parameters and the URI must
not contain any bytes outside of the 32–126 range. If they do, the behavior is undefined."
This matters — a control byte inside the URI is exactly what turns a silent swallow into
an abort on urxvt and a spill on screen.

**[VERIFIED]** The gist's comment thread is gone:
`GET https://api.github.com/gists/eb114294efbcd5adb1944c9f3cb5feda` reports `"comments": 0`
and the comments endpoint returns an empty array. Any prior discussion there is uncitable
today.

### 1.2 Why the safe case is safe

**[VERIFIED]** Paul Williams' VT500 parser ([vt100.net/emu/dec_ansi_parser](https://vt100.net/emu/dec_ansi_parser))
has a dedicated `osc string` state with three actions:

- `osc_start` — "initializes an external parser (the 'OSC Handler') to handle the
  characters from the control string."
- `osc_put` — "passes characters from the control string to the OSC Handler as they
  arrive. There is therefore no need to buffer characters until the end of the control
  string is recognised."
- `osc_end` — "called when the OSC string is terminated by ST, CAN, SUB or ESC, to allow
  the OSC handler to finish neatly."

C0 controls other than CAN/SUB/ESC are ignored during reception. "Earlier terminals treat
OSC in the same way as PM and APC, ignoring the entire control string."

**[VERIFIED]** The safety property is structural: the `Ps` number lives *inside* the
string, so a conforming parser is already in consume-until-terminator state before it ever
sees the `8`. Recognising the command number is a separate, later decision. That is
precisely why xterm, tmux, Konsole, urxvt, the modern Linux console and mosh are all safe
without knowing anything about hyperlinks.

### 1.3 Per-terminal matrix

| Terminal / layer | Native OSC 8 | Unsupported behaviour | Corrupts? |
|---|---|---|---|
| xterm (all patch levels incl. current) | **No** | `do_osc()` `default:` → TRACE + break | No |
| Terminal.app | **[UNKNOWN]** | **[UNKNOWN]** | **[UNKNOWN]** |
| PuTTY | **No** ("we don't ever intend to fix this") | `do_osc()` handles 0/1/2/4/21 only; no-op | No |
| VTE < 0.46.3 / < 0.48.1, and 0.28 | No | **prints garbage** | **Yes** |
| VTE 0.46.3, 0.48.2+ | No | explicitly "swallowed" | No |
| VTE ≥ 0.50 (gnome-terminal 3.26+) | **Yes** | — | — |
| Konsole (since Jul 2020, **off by default**) | Yes | `reportDecodingError()` → log only | No |
| urxvt | **No** | `process_xterm_seq()` falls through | No |
| Linux console ≥ 3.16 | No | `case ESosc: return;` — consumed, discarded | No |
| Linux console < 3.16 | No | **prints payload as text** | **Yes** |
| tmux < 3.4 | No | unknown OSC → `log_debug`, dropped, **not forwarded** | No |
| tmux ≥ 3.4 | **Yes**, gated | re-emits only if outer term has `hyperlinks` feature | No |
| GNU screen (all versions) | **No** | unknown OSC dropped silently | **Yes if string > 767 bytes** |
| mosh ≤ 1.4.0 (latest release) | **No** | parsed, `cmd_num == 8` unhandled, dropped | No |
| mosh master (post 2026-03-22) | **Yes** | — | — |

#### xterm — does not support OSC 8 at all

**[VERIFIED]** `ctlseqs.html` contains no "hyperlink" and no OSC `Ps = 8` entry
([ctlseqs](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)); grepping the full
680 KB [xterm.log.html](https://invisible-island.net/xterm/xterm.log.html) for
`hyperlink` / `OSC 8` returns zero hits across the entire patch history.

**[VERIFIED]** Unknown OSC numbers are dropped —
[misc.c](https://raw.githubusercontent.com/ThomasDickey/xterm-snapshots/master/misc.c):

```c
    case OSC_Unused_30:
    case OSC_Unused_31:
    case OSC_Unused_51:
    default:
	TRACE(("do_osc - unrecognized code\n"));
	break;
    }
```

**[VERIFIED]** Over-long OSC strings are also discarded, not printed. `charproc.c` sets
`string_skip = True` and frees the buffer past `strings_max` (the `maxStringParse`
resource). **[INFERRED]** A URI longer than `maxStringParse` is therefore dropped whole —
still no visible artifact.

**[VERIFIED]** xterm's own documentation on error recovery: "XTerm decodes control
sequences using a state machine. It handles errors in decoding i.e., unexpected
characters, by resetting to the initial (ground) state."

**[VERIFIED]** Corroborated on the ncurses list: G. Branden Robinson notes "xterm is my
daily driver" while explaining he must use gnome-terminal to test OSC 8
([bug-ncurses 2023-08 msg00018](https://lists.gnu.org/archive/html/bug-ncurses/2023-08/msg00018.html)).

#### VTE — the one that actually matters

**[VERIFIED]** Egmont Koblinger, the spec author, on the GCC bug list
([gcc-bugs 2019-12 msg00720](https://gcc.gnu.org/legacy-ml/gcc-bugs/2019-12/msg00720.html)):

> Hyperlinks are supported since VTE 0.50 and a corresponding GNOME Terminal 3.26.
> VTE 0.48.2 and 0.46.3, and newer versions within these stable series silently ignore OSC 8.
> VTE 0.48.[01], 0.46.[012] and older stable series emit garbage.

The GTK2-based VTE 0.28 "also emits garbage."

**[VERIFIED]** Root cause is a hand-rolled non-conforming parser: VTE matched OSC against a
*table of known sequences*, and anything unmatched was rendered as visible text — GNOME bug
403130, "vte doesn't ignore unknown escape sequences". The fix pattern was registering
no-op swallowers:

```c
static void
vte_sequence_handler_urxvt_777(VteTerminalPrivate *that, GValueArray *params)
{
        /* Accept but ignore this for compatibility with downstream-patched vte (bug #711059)*/
}
```

([vte commit "emulation: Swallow urxvt OSC 777"](https://mail.gnome.org/archives/commits-list/2016-May/msg01685.html)).
An analogous "emulation: Swallow OSC 8" commit landed on the 0.46/0.48 branches in April 2017.

This is the single most consequential legacy case: a non-conforming parser in the most
widely deployed Linux terminal family, failing loudly rather than silently.

#### GNU screen — corruption mechanism, at source level

**[VERIFIED]** No OSC 8 support; listed under "Pending feature requests"
([savannah bug 50952](https://savannah.gnu.org/bugs/index.php?50952)). `StringEnd()` in
[src/ansi.c](https://git.savannah.gnu.org/cgit/screen.git/plain/src/ansi.c) handles only
OSC types 83, 0, 1, 2, 11, 20, 39, 49; everything else falls to `break` with no output.

**[VERIFIED]** The spill:

```c
static void StringChar(Window *win, int c)
{
	if (win->w_stringp >= win->w_string + MAXSTR - 1)
		win->w_state = LIT;
	else
		*(win->w_stringp)++ = c;
}
```

`LIT` is screen's literal-printing state. Past `MAXSTR - 1` screen **abandons string
collection and prints the remainder of the URI to the screen**. `MAXSTR` is currently 768.

**[VERIFIED]** The 2020 fix — commit `bfb05c34ba1f961a15ccea04c51444003ba22e57`,
"Increase permitted length of OSC", bug 57718 — only enlarged `w_xtermosc[5][2560]`,
citing the OSC 8 gist's 2083-byte figure. It did **not** raise `MAXSTR`.
**[INFERRED]** screen therefore still corrupts on OSC strings longer than 767 bytes.

#### Linux console — the fix is recent

**[VERIFIED]** Current [vt.c](https://github.com/torvalds/linux/blob/master/drivers/tty/vt/vt.c):
`ESC ]` → `ESnonstd`; a digit → `ESosc`; and `case ESosc: return;` — every payload byte is
consumed and discarded. `handle_ascii()` terminates on BEL inside any control-string state;
`handle_esc()` sets `ESnormal` before its switch, so `ESC \` terminates cleanly and the `\`
is not printed.

**[VERIFIED]** Commit `63f3a16db915096d7a80a96748adba00feb07a32`, "vt: detect and ignore OSC
codes.", Adam Borowski, 2014-02-19, first shipped in **v3.16**:

> Our console doesn't use OSC, unlike everything else, which can lead to junk being
> displayed if a process sends such a code unconditionally.

Termination rules from the same commit message: "0x07 and ESC anything terminate; nothing
else terminates, all 8-bit values including 0x9C are considered a part of the string."

**[VERIFIED]** Confirmed by fetching `vt.c` at tags: v2.6.12, v3.10, v3.14 have no `ESosc`
(`ESC ]` + non-`P`/`R` → straight back to `ESnormal`, so `;;https://…` renders as text);
v3.16, v3.18, v3.19, v4.9, v4.19, v5.4 and later have it.

#### tmux — does not pass unknown OSC through

**[VERIFIED]** [input.c](https://raw.githubusercontent.com/tmux/tmux/master/input.c)
`input_exit_osc()` dispatches a fixed set (0, 2, 4, 7, 8, 9, 10, 11, 12, 52, 104, 110, 111,
112, 133) and ends:

```c
	default:
		log_debug("%s: unknown '%u'", __func__, option);
		break;
	}
```

**[VERIFIED]** Native OSC 8 landed in **tmux 3.4** — CHANGES, "Add support for OSC 8
hyperlinks." in the `CHANGES FROM 3.3a TO 3.4` block. `input_osc_8()` calls
`hyperlinks_put()`.

**[VERIFIED]** **`allow-passthrough` is irrelevant to OSC 8.** It is checked only inside
`input_dcs_dispatch()`, guarding the `DCS tmux; … ST` prefix (`screen_write_rawstring()`);
the OSC path never consults it. It was added in tmux 3.3.

**[VERIFIED]** On tmux ≥ 3.4, forwarding to the *outer* terminal is gated by the
`hyperlinks` terminal feature, capability `Hls`:

```c
"Hls=\\E]8;%?%p1%l%tid=%p1%s%;;%p2%s\\E\\\\",
```

Built-in defaults grant it to `tmux`, `iTerm2`, `foot`, `WezTerm`, `ghostty`, `Rio` only
([tty-features.c](https://raw.githubusercontent.com/tmux/tmux/master/tty-features.c)).
Anything else requires `set -ga terminal-features "*:hyperlinks"`.

**[VERIFIED]** tmux never spews on overflow: `input_input()` sets `INPUT_DISCARD` and
returns past `input_buffer_size`; every dispatcher begins with
`if (ictx->flags & INPUT_DISCARD) return;`.

**[INFERRED]** Net: under tmux < 3.4 OSC 8 is a silent no-op and the link never reaches the
outer terminal even if that terminal supports it. Under tmux ≥ 3.4 with default config and
a non-listed outer terminal, it is also a silent no-op. Either way, no artifacts.

#### mosh

**[VERIFIED]** mosh is a state-synchronising emulator: it parses on the server, syncs
framebuffer state, and re-renders on the client. Nothing is "passed through", so an
unhandled sequence is simply dropped.

**[VERIFIED]** [Issue #1245](https://github.com/mobile-shell/mosh/issues/1245): "the OSC 8
links are not passed from the server to the client" with mosh, while OpenSSH passes them
correctly. No corruption reported. mosh's dispatcher bounds the OSC buffer
(`if ( OSC_string.size() < MAXIMUM_CLIPBOARD_SIZE )`) — silent truncation.

**[VERIFIED]** Support landed on master via
[PR #1360](https://github.com/mobile-shell/mosh/pull/1360), merged 2026-03-22;
`Parse_OSC_8()` rejects bytes outside 32–126 per the spec. **[INFERRED]** As of 2026-09 no
*released* mosh supports it — 1.4.0 (Oct 2022) is still latest per [mosh.org](https://mosh.org/).

#### Others

**PuTTY — [VERIFIED]** Explicit wishlist entry classified "Priority: We don't ever intend
to fix this", with the stated position that "the PuTTY team's current position is that we
don't think this is a good idea"
([wishlist/osc8](https://www.chiark.greenend.org.uk/~sgtatham/putty/wishlist/osc8.html)).
`terminal.h` defines a real OSC string state and a bounded buffer (`OSC_STR_MAX 2048`);
`do_osc()` handles 0/1/2/4/21 and no-ops otherwise. **[INFERRED]** the overflow branch
drops rather than prints, from the `osc_strlen < OSC_STR_MAX` guard and the absence of any
known PuTTY OSC-spew bug.

**Konsole — [VERIFIED]** `if (tokenBuffer[0] == XTERM_EXTENDED::URL_LINK)` with
`URL_LINK == '8'`, calling `extractor->toggleUrlInput()`. Unknown OSC numbers hit
`reportDecodingError()` — a diagnostic, not screen output
([Vt102Emulation.cpp](https://raw.githubusercontent.com/KDE/konsole/master/src/Vt102Emulation.cpp)).
Support dates from Jul 2020 and is **disabled by default**.

**urxvt — [VERIFIED]** `get_to_st()` accepts BEL, `ESC \` and 8-bit ST. On any control
character below 0x20, and on buffer overflow, it returns `NULL` and the sequence is
abandoned — nothing printed. `process_xterm_seq()` has no `default:`
([command.C](https://raw.githubusercontent.com/exg/rxvt-unicode/master/src/command.C)).

**Terminal.app — [UNKNOWN]** No primary source. Apple publishes no control-sequence
documentation, and Terminal.app is absent from
[Alhadis/OSC8-Adoption](https://github.com/Alhadis/OSC8-Adoption/) in both the supported
and pending-feature-request lists. Secondary sources contradict each other.
**[INFERRED]** it parses OSC 0/1/2/7 correctly (title, cwd), which requires a real OSC
string state, so wholesale spew is unlikely — but this is unverified.

### 1.4 Known visible-corruption cases

**[VERIFIED]**, each with a concrete source:

1. **VTE ≤ 0.46.2 / ≤ 0.48.1 and 0.28** — emits garbage (GNOME bug 403130). Ships in every
   gnome-terminal / Tilix / Terminator / xfce4-terminal / Guake older than ~2017.
2. **GNU screen, OSC string > 767 bytes** — `w_state = LIT`, remainder printed literally.
   Source above; savannah bug 57718.
3. **Linux console < 3.16** — no `ESosc` state, payload printed as junk. Kernel commit
   `63f3a16db915` says so explicitly.
4. **Windows Terminal ≤ 0.9** and **Emacs's built-in terminal** — listed as
   display-corrupting by the spec author. **[INFERRED]** from that statement; sources not
   independently read.

**[VERIFIED]** A separate, non-terminal failure class: the `ESC \` terminator is fragile in
*emitter-side* string pipelines. [oven-sh/bun#30693](https://github.com/oven-sh/bun/issues/30693)
is a formatter that ate the backslash of `\x1b\`, leaving a stray `r` on screen in VS Code
and Ghostty. The bug is in the app, not the terminal — but it argues for care when
composing OSC 8 with other markup, and is one reason many emitters prefer BEL.

### 1.5 Is there any query mechanism? No.

**[VERIFIED]** The spec: "Currently there's no way of detecting whether the terminal
emulator supports hyperlinks. We're hoping to address this at some point in the future."

**[VERIFIED]** No terminfo capability in the standard database. On bug-ncurses
([2023-08 msg00018](https://lists.gnu.org/archive/html/bug-ncurses/2023-08/msg00018.html)),
G. Branden Robinson: "We'd like to be able to ask terminfo if the terminal description
supports OSC 8, but we can't." Nicholas Marriott replies that tmux uses a *user-defined*
extension capability `Hls`; Thomas Dickey confirms `user_caps(5)` is the right vehicle:
"yes - it's called user_caps because users can use the feature".

**[VERIFIED]** `Hls` is not in ncurses' shipped `terminfo.src` — searches of
[terminfo.src](https://invisible-island.net/ncurses/terminfo.src.html) and
[user_caps(5)](https://invisible-island.net/ncurses/man/user_caps.5.html) find no `Hls` and
no hyperlink capability. It exists only because tmux injects it into its own children's
environment. **[INFERRED]** Reading `Hls` from terminfo is a reliable *positive* signal
only inside tmux ≥ 3.4 with the feature enabled; its absence proves nothing.

**[VERIFIED]** XTGETTCAP cannot be repurposed portably. Per xterm's ctlseqs: "An invalid
name (one not found in xterm's tables) ends processing of the list of names"; the reply is
`DCS 1 + r … ST` on success and `DCS 0 + r ST` on failure. **[INFERRED]** Since `Hls` is in
nobody's table, a conforming terminal answers "unknown", indistinguishable from "I have
hyperlinks but don't index them by that name". Terminals without XTGETTCAP reply nothing at
all, so any probe must be timeout-driven for a signal that is negative by construction.

**[VERIFIED]** DA1 (`CSI c`) and DA2 (`CSI > c`) do not report hyperlinks. DA1 parameters
cover ReGIS (3), Sixel (4), ANSI colour (22) etc.; DA2 reports terminal type / firmware
version / cartridge. Neither has a hyperlink bit.

**[INFERRED]** The only workable startup probe is *identification*, not *capability*:
XTVERSION (`CSI > 0 q` → `DCS > | <name and version> ST`) plus `$TERM`, `$TERM_PROGRAM`,
`$TERM_PROGRAM_VERSION`, `$VTE_VERSION`, `$KONSOLE_VERSION`, `$WT_SESSION`, mapped against a
hard-coded allowlist. `$VTE_VERSION` is the highest-value single check, being a numeric
build number whose cutover (≥ 5002 ⇒ 0.50.2) is exactly the boundary between "garbage" and
"works".

---

## 2. Truecolor detection

### 2.1 COLORTERM — who sets it, to what

| Emulator | Sets it? | Value | Evidence |
|---|---|---|---|
| VTE (gnome-terminal, Tilix, Guake, Terminator, sakura, Ptyxis, xfce4-terminal…) | yes — **forced, embedder cannot override** | `truecolor` | **[VERIFIED]** [spawn.cc](https://gitlab.gnome.org/GNOME/vte/-/raw/master/src/spawn.cc) `merge_environ`: caller `envp` merged first, then `/* Always set this ourself, not allowing replacing from envp */ g_hash_table_replace(table, g_strdup("COLORTERM"), g_strdup("truecolor"));` |
| kitty | yes | `truecolor` | **[VERIFIED]** `kitty/child.py`: `env['COLORTERM'] = 'truecolor'`; [glossary](https://raw.githubusercontent.com/kovidgoyal/kitty/master/docs/glossary.rst). Re-injected remotely by `kittens/ssh/main.go` |
| WezTerm | yes | `truecolor` | **[VERIFIED]** [config.rs](https://raw.githubusercontent.com/wezterm/wezterm/main/config/src/config.rs): `cmd.env("COLORTERM", "truecolor");`; changelog #875. Pushed across WSL via `WSLENV` |
| Alacritty | yes | `truecolor` | **[VERIFIED]** [tty/mod.rs](https://raw.githubusercontent.com/alacritty/alacritty/master/alacritty_terminal/src/tty/mod.rs) `setup_env()`: `// Advertise 24-bit color support.` |
| foot | yes | `truecolor` | **[VERIFIED]** [slave.c:436](https://codeberg.org/dnkl/foot/raw/branch/master/slave.c) |
| Ghostty | yes | `truecolor` | **[VERIFIED]** [Exec.zig](https://raw.githubusercontent.com/ghostty-org/ghostty/main/src/termio/Exec.zig), both branches. `src/cli/ssh.zig` adds `-o SendEnv=COLORTERM` |
| iTerm2 | yes | `truecolor` | **[VERIFIED at v3.1.7]** [PTYSession.m](https://raw.githubusercontent.com/gnachman/iTerm2/v3.1.7/sources/PTYSession.m): `env[@"COLORTERM"] = @"truecolor";`. **[UNKNOWN for master]** (file exceeds fetch limit) |
| Konsole | yes, via the **default profile**, not hardcoded | `truecolor` | **[VERIFIED]** [Profile.cpp](https://invent.kde.org/utilities/konsole/-/raw/master/src/profile/Profile.cpp) — user-editable, so a customised profile can drop it |
| **xterm** | **no — actively deletes it** | — | **[VERIFIED]** `main.c::xtermTrimEnv()`: `TRIM(1, COLORTERM)`, alongside `TRIM(1, KITTY_)`, `GHOSTTY_`, `VTE_`, `ITERM_`, `WEZTERM`, `WT_SESSION`. Comment: "These are set by other terminal emulators or non-standard libraries, and are a nuisance if one starts xterm from a shell inside one of those." (xterm-411 tarball, [invisible-island.net/xterm](https://invisible-island.net/xterm/)) |
| **mintty** | **no — actively deletes it** | — | **[VERIFIED]** [child.c](https://raw.githubusercontent.com/mintty/mintty/master/src/child.c): `trimenv("COLORTERM");`, which for a non-`_`-suffixed name is `unsetenv(e)` |
| **st** | **no** | — | **[VERIFIED]** [st.c](https://git.suckless.org/st/) sets only `LOGNAME`, `USER`, `SHELL`, `HOME`, `TERM`; `x.c::xsetenv()` adds only `WINDOWID` |
| **Windows Terminal / conhost** | **no** | — | **[VERIFIED]** `ConptyConnection.cpp` inserts only `WT_SESSION` and `WT_PROFILE_ID`; `src/host/srvinit.cpp` has none either. Request [#11057](https://github.com/microsoft/terminal/issues/11057) still open |
| **urxvt** | yes, but a **name, not a capability word** | `rxvt` / `rxvt-xpm` / `rxvt-mono` | **[VERIFIED]** [rxvt.h](https://raw.githubusercontent.com/exg/rxvt-unicode/master/src/rxvt.h) `#define COLORTERMENV "rxvt"`; [init.C](https://raw.githubusercontent.com/exg/rxvt-unicode/master/src/init.C) selects by depth and `HAVE_IMG` |
| xfce4-terminal | yes, a **name** — masked by modern VTE | `xfce4-terminal` | **[VERIFIED]** [terminal-screen.c](https://gitlab.xfce.org/apps/xfce4-terminal/-/raw/master/terminal/terminal-screen.c). **[INFERRED]** VTE applies `envp` before its forced line, so the child sees `truecolor` on current VTE |
| **tmux** | yes, unconditionally, **3.6+** | `truecolor` | **[VERIFIED]** `environ.c::environ_for_session` — see §2.2 |
| **screen** | **no**, and does not strip an inherited value | — | **[VERIFIED]** the [manual](https://www.gnu.org/software/screen/manual/screen.html) documents only `$TERM` and `$STY` |
| Terminal.app (macOS 26) | **[UNKNOWN]** | — | Truecolor confirmed by the reporter in [termstandard/colors#69](https://github.com/termstandard/colors/issues/69), who says "haven't checked" about env vars |

### 2.2 Survival across boundaries

**ssh — does not cross, out of the box. [VERIFIED]**

- [ssh_config(5)](https://man.openbsd.org/ssh_config), SendEnv: "Specifies what variables
  from the local environ(7) should be sent to the server. The server must also support it,
  and the server must be configured to accept these environment variables." …
  **"The default is not to send any environment variables."**
- [sshd_config(5)](https://man.openbsd.org/sshd_config), AcceptEnv: "Specifies what
  environment variables sent by the client will be copied into the session's environ(7)." …
  **"The default is not to accept any environment variables."**
- Only `TERM` is unconditional, both sides: "The TERM environment variable is always
  accepted whenever the client requests a pseudo-terminal as it is required by the protocol."
- **[VERIFIED]** The upstream OpenSSH-portable
  [shipped `sshd_config`](https://raw.githubusercontent.com/openssh/openssh-portable/master/sshd_config)
  contains **no `AcceptEnv` line at all**. The frequently-cited `AcceptEnv LANG LC_*` is a
  *distro* addition (Debian/Ubuntu/Fedora), not upstream — and would not match COLORTERM
  anyway.
- Both ends must be configured; one alone is useless. Two vendors ship workarounds rather
  than rely on it: Ghostty's `ssh` wrapper passes `-o SendEnv=COLORTERM`, and kitty's ssh
  kitten re-adds `COLORTERM=truecolor` remotely.

**tmux. [VERIFIED]**

- `update-environment` default (`options-table.c`) is
  `DISPLAY KRB5CCNAME MSYSTEM SSH_ASKPASS SSH_AUTH_SOCK SSH_AGENT_PID SSH_CONNECTION WAYLAND_DISPLAY WINDOWID XAUTHORITY XDG_CURRENT_DESKTOP XDG_SESSION_DESKTOP XDG_SESSION_TYPE`
  — **COLORTERM is not in it**, so a re-attaching client's value is not propagated into an
  existing session.
- tmux sets it itself, in `environ.c::environ_for_session`:

```c
	if (!no_TERM) {
		value = options_get_string(global_options, "default-terminal");
		environ_set(env, "TERM", 0, "%s", value);
		environ_set(env, "TERM_PROGRAM", 0, "%s", "tmux");
		environ_set(env, "TERM_PROGRAM_VERSION", 0, "%s", getversion());
		environ_set(env, "COLORTERM", 0, "truecolor");
	}
```

- **From tmux 3.6**, commit `29db8ac36eeefcb67eb87d80900b97eb515f2c80` (nicm, 2025-10-30,
  "Set and check COLORTERM as a hint for RGB colour."), `CHANGES FROM 3.5a TO 3.6`. On tmux
  ≤ 3.5a there is no such line and COLORTERM inside a pane is whatever leaked in.
- tmux also *consumes* COLORTERM as an RGB input (`tty-term.c`), matching
  `truecolor`/`24bit` case-insensitively, or any value containing `256` → the `256` feature.

**screen. [VERIFIED]** Does not set it and does not strip it, so an outer
`COLORTERM=truecolor` leaks straight through into a multiplexer that cannot render 24-bit
SGR on ≤ 4.9. Discussed on the maintainers' list as a request to have screen
`unsetenv COLORTERM` at startup: "GNU Emacs 28.1 added code that enables 24-bit color if
the COLORTERM=truecolor, but screen doesn't actually pass through 24-bit color values
correctly."
([screen-devel 2022-07](https://lists.gnu.org/archive/html/screen-devel/2022-07/msg00004.html)).
Workaround is `unsetenv COLORTERM` in `~/.screenrc`.

**sudo — does not survive. [VERIFIED]**
[sudoers(5)](https://www.man7.org/linux/man-pages/man5/sudoers.5.html): `env_reset` "is on
by default", and "If set, sudo will run the command in a minimal environment containing the
TERM, PATH, HOME, MAIL, SHELL, LOGNAME, USER and SUDO_* variables." COLORTERM appears
nowhere in sudoers(5).

**doas — does not survive. [VERIFIED]** [doas(1)](https://man.openbsd.org/doas.1)
constructs a new environment; the only variables named are `HOME`, `LOGNAME`, `PATH`,
`SHELL`, `USER`, `DOAS_USER`, `DISPLAY`, `TERM`.
[doas.conf(5)](https://man.openbsd.org/doas.conf) offers `keepenv` / `setenv` to opt in.

**su (util-linux) — survives both ways. [VERIFIED]**
[su(1)](https://man7.org/linux/man-pages/man1/su.1.html): plain `su user` "defaults to …
only set the environment variables HOME and SHELL (plus USER and LOGNAME if the target user
is not root)" — the rest is inherited. `su --login`: "clear all the environment variables
except TERM, COLORTERM, NO_COLOR and variables specified by --whitelist-environment".
COLORTERM is **explicitly whitelisted by name** — the only boundary in this table treating
it as first-class.

**docker exec — does not survive. [VERIFIED]**
[docs](https://docs.docker.com/reference/cli/docker/container/exec/): "The `docker exec`
command inherits the environment variables that are set at the time the container is
created" — from the image / `docker run`, never from the invoking shell.

### 2.3 False negatives and false positives

**Truecolor but no `COLORTERM=truecolor` (false negatives):**

- **xterm** — deletes it. **[VERIFIED]**
- **mintty** — deletes it. **[VERIFIED]**
- **st** — never sets it. **[VERIFIED]**
- **Windows Terminal / conhost** — never sets it. **[VERIFIED]**
- **Terminal.app (macOS 26)** — truecolor confirmed, COLORTERM **[UNKNOWN]**.
- **Konsole with a customised profile** — droppable, since the value is a profile default.
  **[INFERRED]** from `Profile.cpp` being the profile default table.
- **Anything reached across ssh, sudo, doas, or docker exec** without explicit forwarding.
  **[VERIFIED]** per §2.2.
- PuTTY, mlterm and other truecolor-capable entries in termstandard's list with no
  COLORTERM row — **[INFERRED]**, not read at source.
- **Not Alacritty and not WezTerm.** Both set `truecolor`. **[VERIFIED]** (They are
  invisible to every *query* method, which is a different problem — see §2.6.)

**COLORTERM set but not truecolor (false positives against a naive "is it set?" test):**

- **urxvt** — `rxvt` / `rxvt-xpm` / `rxvt-mono`. Colour support is partial: termstandard
  lists it under "Partial Support" ("Limits maximum number of colors"), and the upstream
  `Changes` through 9.31 (2023-01-02) has no entry mentioning 24-bit or truecolor — the
  well-known truecolor support is an out-of-tree patch. **[VERIFIED for the value;
  per-changelog only for the capability]**
- **GNOME Terminal < 3.14** — `COLORTERM=gnome-terminal`, removed in 3.14. **[VERIFIED]**
  [LP#1429584](https://bugs.launchpad.net/ubuntu/+source/gnome-terminal/+bug/1429584)
- **xfce4-terminal** — `COLORTERM=xfce4-terminal`, still in current source. **[VERIFIED]**
- **S-Lang / Lynx-era terminals**, where presence meant only "has colour" and "the actual
  value assigned to the variable is ignored". **[VERIFIED]**
  [Lynx docs](https://lynx.invisible-island.net/lynx2.8.8/breakout/lynx_help/keystrokes/environments.html)

A strict `value ∈ {truecolor, 24bit}` (case-insensitive) test rejects every entry in the
second list correctly. **[VERIFIED]** The residual true false positive is not a value
problem: `COLORTERM=truecolor` inherited into GNU screen ≤ 4.9, where the variable is
accurate about the outer terminal and wrong about the thing actually rendering.

**tmux ≥ 3.6 sets it unconditionally, so inside tmux it carries zero information.**
**[VERIFIED]** The only guard in `environ_for_session` is `!no_TERM`. There is no check
against the outer terminal's actual RGB capability, nor against the `RGB` feature tmux
computed for the client. Defer to terminfo `Tc`/`RGB` on `$TERM` instead.

### 2.4 Provenance of the convention

- **[VERIFIED]** The `termstandard/colors` README's own first line: "(Previously published
  and discussed at https://gist.github.com/XVilka/8346728.)" — it began as a personal gist
  by XVilka (Anton Kochkov) and was later moved into a community org repo.
  <https://github.com/termstandard/colors>
- **[VERIFIED]** **Status: semi-primary — a community convention document, not a
  standard.** No normative body, no RFC, no ECMA/ISO/DEC anchor, and no standing in
  ncurses: [user_caps(5)](https://invisible-island.net/ncurses/man/user_caps.5.html) lists
  `AX, E3, NQ, RGB, U8, XM`, and COLORTERM is not a terminfo concept at all. The document
  hedges rather than mandates: "Having an extra environment variable (separate from TERM)
  is not ideal: by default it is not forwarded via sudo, ssh, etc… Despite these problems,
  it's currently the best option, so checking `$COLORTERM` is recommended", and "App
  developers can freely choose to check for this variable, or introduce their own method."
- **[VERIFIED]** The `truecolor`/`24bit` value pair is *descriptive*: "The S-Lang library
  has a check that `$COLORTERM` contains either "truecolor" or "24bit" (case sensitive)."
  tmux implements the same test **case-insensitively** — the two most-cited consumers
  already disagree on a detail.
- **[VERIFIED]** The one maintainer statement of record is hostile. Egmont Koblinger (VTE),
  on gnome-terminal dropping COLORTERM in 3.14: "COLORTERM's semantics have nothing to do
  with 256 color support per se, it was a mere coincidence that all terminals that set this
  variable also supported 256 colors", and "COLORTERM should not be necessary ever",
  recommending distros "rather fix whoever relies on this to use better methods (e.g.
  xtermcontrol or equivalent; or $VTE_VERSION) instead". VTE later restored it (0.44 /
  gnome-terminal 3.20) with the **new** truecolor semantics — the current meaning is a
  deliberate reuse of a variable whose maintainers had just deprecated it.
  [LP#1429584](https://bugs.launchpad.net/ubuntu/+source/gnome-terminal/+bug/1429584)

**Net:** cite termstandard as evidence of what implementers converged on, never as a
specification. Where it conflicts with a source file, the source file wins — it already
does on iTerm2 ("compile-time only", stale since ≥ 3.1.7) and on Terminal.app.

### 2.5 The DECRQSS probe — does it discriminate?

The probe: emit `CSI 38;2;1;2;3 m`, then `DCS $ q m ST` (`ESC P $ q m ESC \`), and read the
DECRPSS reply `DCS 1 $ r … m ST`.

| Terminal | Answers `$q m`? | Truecolor reply form | Invalid-request reply | Source **[VERIFIED]** |
|---|---|---|---|---|
| xterm | yes | `38:2::R:G:B` (direct) / **`38:5:N`** (256 mode) | `DCS 0 $ r ST` | `misc.c`, `charproc.c` |
| VTE | yes | `38:2::R:G:B` | `DCS 0 $ r ST` | `src/vteseq.cc` |
| foot | yes | `38:2::R:G:B` | `\033P0$r\033\\` | `dcs.c` |
| Ghostty | yes | `38:2::R:G:B` | `DCS 0 $ r ST` | `dcs.zig`, `Terminal.zig` |
| Windows Terminal | yes | `38:2::R:G:B` | `DCS 0 $ r ST` | `adaptDispatch.cpp` |
| kitty | yes | **`38:2:R:G:B`** (3 fields) | `DCS 0 $ r ST` | `screen.c`, `line.c` |
| iTerm2 | yes (`m` and `SP q` only) | **`38:2:1:R:G:B`** — colour-space id `1`, not empty | `ESC P 0 $ r ESC \` | `sources/VT100Terminal.m` v3.4.23 |
| mintty | yes | **`38:2::R:G:B`** (≥ 3.0.0); **`38;2;R;G;B`** (≤ 2.8.5) | **echoes the request text** | `src/termout.c` @3.0.0 / @2.8.5 |
| **tmux** | intercepts; only `SP q` implemented | — | `\033P0$r\033\\` | `input.c::input_handle_decrqss` |
| **WezTerm** | **no** (`"p`, `r`, `s` only) | — | `DCS 0 $ r ST` | `performer.rs` |
| **Alacritty** | **no — silent** | — | none | `vte/src/ansi.rs`: `hook`/`put`/`unhook` are `debug!` no-ops |
| **Konsole** | **no — silent** | — | none | `Vt102Emulation.cpp` (DCS = Sixel only) |
| **Linux console** | **no — swallows DCS** | — | none | `drivers/tty/vt/vt.c` |

**Does it discriminate?** **[VERIFIED] Yes, but only in one direction, and only on xterm.**
xterm in 256-colour mode replies `38:5:N` — an honest downgrade, and the only real evidence
*against* truecolor anywhere in this table. Every other terminal that answers at all is a
truecolor terminal answering `38:2:…`. Everything else is a false negative:
`DCS 0 $ r ST` is what WezTerm and tmux return **while being fully truecolor**, and silence
is what Alacritty, Konsole and the Linux console return.

**Four wire formats, not two. [VERIFIED]** A reply parser must accept `38:2::R:G:B`,
`38:2:R:G:B`, `38:2:1:R:G:B`, and `38;2;R;G;B`. Practical rule: split on `;`, then split
each parameter on `:`; if the first sub-param is `38`/`48` and the second is `2`, take the
**last three** numeric sub-params as R,G,B.

Two further parser traps, both **[VERIFIED]**:

- iTerm2 builds the reply from an `NSSet` sorted with string `compare:` — SGR codes come
  back in **lexicographic**, not numeric, order. Never assume position.
- mintty violates the spec on failure: `child_printf("\eP0$r%s\e\\", s)` echoes the request
  payload, where ctlseqs specifies a bare `DCS 0 $ r ST`. Do not treat trailing bytes after
  `0$r` as a success indicator.

**Hang risk and the fence. [VERIFIED]** Terminals that never reply (Alacritty, Konsole,
Linux console) will block a naive reader forever. The standard mitigation is a Primary DA
(`CSI c`) fence, documented first-party by kitty for exactly this purpose: "An application
can query the terminal for support of this protocol by sending the escape code querying for
the current progressive enhancement status **followed by request for the primary device
attributes**. If an answer for the device attributes is received without getting back an
answer for the progressive enhancement the terminal does not support this protocol."
<https://sw.kovidgoyal.net/kitty/keyboard-protocol/>

### 2.6 Other probes: XTGETTCAP, terminfo, XTVERSION

**XTGETTCAP (`DCS + q <hex> ST`):**

| Terminal | XTGETTCAP | `RGB` | `Tc` | `Co` | `TN` | Unknown cap |
|---|---|---|---|---|---|---|
| xterm | yes | **yes** (documented) | **[UNKNOWN]** | yes | yes | `DCS 0 + r ST` (bare) |
| WezTerm | yes | **yes → hex("8/8/8")** | via terminfo DB | `"256"` | `term_program` | `0+r` + hex(name) |
| Ghostty | yes (widest set) | **yes → hex("8")** | yes (boolean) | `"256"` | `xterm-ghostty` | **none — `orelse continue`, total silence** |
| kitty | yes | **no** | **yes** (boolean) | yes (256) | yes (`xterm-kitty`) | `0+r` + hex(name) |
| foot | yes | only under `TERM=foot-direct` | yes | yes | yes | `0+r` + hex(name) |
| iTerm2 | yes, but only `TN`, `name`, `iTerm2Profile` | **no** | no | no | yes | bare `ESC P 0 + r ESC \` |
| **Windows Terminal** | **no** — `+q` unhandled | — | — | — | — | none |
| **tmux** | **no** — `+q` silently discarded | — | — | — | — | none |
| **Alacritty** | **no** | — | — | — | — | none |
| **Konsole** | **no** | — | — | — | — | none |

**[VERIFIED]** Sources: `term/src/terminalstate/mod.rs::xt_get_tcap` (WezTerm);
`src/terminfo/Source.zig::xtgettcapMap` — `kvs[1] = .{ "Co", "256" }; kvs[2] = .{ "RGB", "8" };`
(Ghostty); `kitty/terminfo.py` (`'RGB'` absent from every capability dict);
`sources/VT100Terminal.m` `termcapTerminfoNameDictionary` (iTerm2);
`OutputStateMachineEngine.hpp` `DcsActionCodes` — no `VTID("+q")` (Windows Terminal).

**[VERIFIED]** The two `RGB` answers disagree: WezTerm returns `8/8/8` (ncurses' documented
*string* form, "slash-separated list of decimal integers"); Ghostty returns `8`. Per
`user_caps(5)` the numeric form means "what result to add to red, green, and blue", so they
are not the same declaration. Treat any non-empty `RGB` reply as "yes, direct colour"
rather than parsing bit widths — which is what `user_caps(5)` warns about: "applications
that make assumptions about the number of bits per color channel are unlikely to work
reliably."

**Verdict on XTGETTCAP: not a better probe. [VERIFIED]** Querying `RGB` gets "no" from
kitty, *nothing at all* from Ghostty (`orelse continue`), and no reply from Windows
Terminal, Alacritty, Konsole or tmux.

**terminfo. [VERIFIED]** `Tc` is a tmux extension ncurses does not document, and is what
kitty, Ghostty, WezTerm and foot actually ship. `RGB` is documented in `user_caps(5)` but
lives only in `*-direct` entries nobody uses by default. Never equality-test `colors`: it
is 256 by default, 16777216 under `*-direct` with extended numbers, and 32767 under
`*-direct` without them. Test `Tc || RGB || (setrgbf && setrgbb)`.

**XTVERSION (`CSI > q`). [VERIFIED]**

| Terminal | Reply |
|---|---|
| xterm | `DCS > \| text ST` (spec) |
| kitty | `ESC P >\|kitty(<XT_VERSION>) ESC \` |
| foot | `ESC P >\|foot(<maj>.<min>.<patch>[-<extra>]) ESC \` |
| Ghostty | `ESC P >\|ghostty <version> ESC \` |
| WezTerm | `DCS >\|<term_program> <term_version> ST` |
| tmux | `ESC P >\|tmux <version> ESC \` |
| mintty | `ESC P >\|mintty <version> ESC \` |
| iTerm2 | `ESC P >\|iTerm2 <CFBundleShortVersionString> ESC \` |
| **Windows Terminal** | **not implemented** — no `VTID(">q")` in `CsiActionCodes` |
| **Alacritty** | **not implemented** — no `('q', [b'>'])` arm in `csi_dispatch` |

These prefixes are exactly what tmux prefix-matches on. **Note Alacritty and Windows
Terminal: two truecolor terminals invisible to every query-based method** — no DECRQSS, no
XTGETTCAP, no XTVERSION. For them `COLORTERM` (Alacritty) or nothing at all (Windows
Terminal) is the only signal.

---

## 3. The "hardware cursor"

**[VERIFIED]** "Hardware cursor" is curses vocabulary, not DEC vocabulary. ncurses uses it
to mean the terminal's own cursor as distinct from the library's model: "Normally, curses
leaves the hardware cursor at the library's cursor location of the window being refreshed.
The **leaveok** option allows the cursor to be left wherever the update happens to leave it.
It is useful for applications that do not employ a visible cursor, since it reduces the
need for cursor motions."
<https://invisible-island.net/ncurses/man/curs_outopts.3x.html> — DEC's own term is
"text cursor".

### 3.1 DECTCEM — visibility

| | |
|---|---|
| Show | `CSI ? 25 h` |
| Hide | `CSI ? 25 l` |
| Origin | VT220; power-on default **visible** |

**[VERIFIED]** <https://vt100.net/docs/vt510-rm/DECTCEM.html> — "The default state is
visible." And ctlseqs: "Ps = 2 5 -> Show cursor (DECTCEM), VT220."

**[VERIFIED]** DECSTR (soft reset, `CSI ! p`) resets visibility to **visible**. Microsoft
documents this under Soft Reset — "Cursor visibility: visible (DECTEM)"
<https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences> —
and mosh carries the same behaviour with the source comment
`/* per xterm and gnome-terminal */`.

#### terminfo `civis` / `cnorm` / `cvvis`

**[VERIFIED]** <https://invisible-island.net/ncurses/man/terminfo.5.html>:

```
cursor_invisible   civis   vi   make cursor invisible
cursor_normal      cnorm   ve   make cursor appear normal (undo civis/cvvis)
cursor_visible     cvvis   vs   make cursor very visible
```

**[VERIFIED]** `curs_set(0|1|2)` maps to these three
(<https://invisible-island.net/ncurses/man/curs_kernel.3x.html>): "curs_set adjusts the
cursor visibility to 'invisible', 'visible', 'very visible'… It returns the previous
visibility if the requested one is supported, and **ERR** otherwise."

**[INFERRED]** When the terminal lacks `civis`, nothing is emitted and `curs_set(0)`
returns ERR — direct reading of that RETURN VALUE clause; the implementation in
`ncurses/tty/tty_update.c` could not be fetched un-truncated.

**[VERIFIED]** Load-bearing for a TUI, same NOTES section: "The endwin function of both
ncurses and SVr4 curses calls curs_set if the latter has previously been called… **There is
no way for ncurses to determine the initial cursor visibility to restore it.**"

**What `cvvis` actually is. [VERIFIED-local]**, `infocmp -x -1`:

| TERM | `civis` | `cnorm` | `cvvis` |
|---|---|---|---|
| `xterm`, `xterm-256color` | `\E[?25l` | `\E[?12l\E[?25h` | `\E[?12;25h` |
| `alacritty`, `foot`, `kitty`, `ghostty` | `\E[?25l` | `\E[?12l\E[?25h` | `\E[?12;25h` |
| `xterm-kitty` | `\E[?25l` | **`\E[?12h`**`\E[?25h` | `\E[?12;25h` |
| `wezterm` | `\E[?25l` | `\E[?25h` | *(absent)* |
| `linux` | `\E[?25l\E[?1c` | `\E[?25h\E[?0c` | `\E[?25h\E[?8c` |
| `screen`, `tmux-256color` | `\E[?25l` | `\E[34h\E[?25h` | `\E[34l` |
| `vt520` | `\E[?25l` | `\E[?25h` | *(absent)* |

Readings:

- **On xterm-family entries "very visible" literally means "blinking"** — `\E[?12;25h`
  sets private mode 12, "Start blinking cursor (AT&T 610)" **[VERIFIED]** (ctlseqs).
- **`cnorm` is not a pure "show cursor".** It also asserts a blink state, and entries
  assert *opposite* ones: `xterm` sends `?12l` (stop), `xterm-kitty` sends `?12h` (start),
  `wezterm` neither. `tput cnorm` is strictly wider than bare `\E[?25h`. **[VERIFIED-local]**
- **On the Linux console `cvvis` uses the kernel soft-cursor sequence** `ESC [ ? n c`,
  whose first parameter is "0=default, 1=invisible, … 8=full block" **[VERIFIED]**
  <https://raw.githubusercontent.com/torvalds/linux/master/Documentation/admin-guide/vga-softcursor.rst>.
  This sequence is **not** documented in `console_codes(4)` **[VERIFIED]**
  <https://man7.org/linux/man-pages/man4/console_codes.4.html> — the `linux` terminfo entry
  depends on a source-only sequence.
- **`screen`/`tmux` use a private mode 34 with inverted sense** (`CSI 34 l` = very visible).
  Mode 34 is not in xterm's SM/RM table, so it is inert on xterm-family emulators; tmux and
  screen consume it internally. **[VERIFIED]**
- **`cvvis` is absent** from `wezterm`, `vt520` **[VERIFIED-local]** and from the `nsterm`
  entries describing Terminal.app **[VERIFIED]**
  ([bug-ncurses 2015-04](https://lists.gnu.org/archive/html/bug-ncurses/2015-04/msg00018.html),
  Terminal.app 2.5.3/343.7; newer `nsterm-build4xx` variants **[UNKNOWN]**). On those,
  `curs_set(2)` returns ERR.

**Prevalence across the local DB** (1865 entries, ncurses 6.6) **[VERIFIED-local]**:
**696 define `civis`; 451 of those use `\E[?25l`; 78 define `Ss`; 560 define `u7`**, 530 of
them as `\E[6n`. Most of the non-`?25l` remainder is pre-VT220 hardware.

### 3.2 DECSCUSR — shape and blink

`CSI Ps SP q` — **literal SP (0x20) intermediate**, `q` (0x71) final. Microsoft states it
explicitly. **[VERIFIED]**

| Ps | xterm / Microsoft / Ghostty | VT510 manual |
|---|---|---|
| 0 | **contested — see below** | blink block (default) |
| 1 | blinking block (default) | blink block (default) |
| 2 | steady block | steady block |
| 3 | blinking underline | blink underline |
| 4 | steady underline | steady underline |
| 5 | blinking bar — **xterm extension** | — |
| 6 | steady bar — **xterm extension** | — |
| 7 | initial resources — **xterm only** | — |

**[VERIFIED]** <https://vt100.net/docs/vt510-rm/DECSCUSR.html> — the DEC table stops at 4;
there is no 5 or 6. ctlseqs adds 5, 6 and "Ps = 7 -> initial resources, xterm. XTerm
restores the initial state of the cursor using resource settings: cursorBlink,
cursorUnderLine, and cursorBar."

**The "0 = default" ambiguity, first-party on both sides:**

| Source | Meaning of `Ps = 0` |
|---|---|
| VT510 manual | "0, 1 or none → Blink Block (Default)" **[VERIFIED]** |
| xterm ctlseqs | "Ps = 0 → blinking block" **[VERIFIED]** |
| Microsoft Learn | "**User Shape** — Default cursor shape configured by the user" **[VERIFIED]** |
| Ghostty | "0 → Terminal default … **is inconsistent across terminal implementations**" **[VERIFIED]** <https://ghostty.org/docs/vt/csi/decscusr> |
| iTerm2 | "This will reset the cursor to its default appearance. **This is an intentional deviation from the behavior of DEC virtual terminals.**" **[VERIFIED]** <https://iterm2.com/documentation-escape-codes.html> |
| foot | "In foot, Ps=0 means 'use style from foot.ini'." **[VERIFIED]** |
| Alacritty | `0 => None` → falls back to `config.default_cursor_style` **[VERIFIED]** |

**[VERIFIED-local]** The terminfo `Se` strings encode the same three-way split:
`xterm`/`kitty`/`wezterm`/`ghostty` → `\E[2 q` (steady block); `alacritty`/`xterm-kitty` →
`\E[0 q`; `foot` → `\E[ q` (parameter omitted). There is no ecosystem consensus on how to
say "put it back".

**`Ss` / `Se` user caps. [VERIFIED]** Documented **only** in `terminfo.src` comments — they
are **not** in [user_caps(5)](https://invisible-island.net/ncurses/man/user_caps.5.html).
From [terminfo.src](https://invisible-island.net/ncurses/terminfo.src.html): "Ss is used to
set the cursor style as described by the DECSCUSR function to a block or underline. Se
resets the cursor style to the terminal power-on default." Only **78 of 1865** local
entries define `Ss` **[VERIFIED-local]**; `nsterm` (Terminal.app) does not. tmux and neovim
both gate DECSCUSR emission on `Ss` being present.

**[VERIFIED]** tmux's `tty_update_cursor()` is a good model: emit `TTYC_CIVIS` when
`MODE_CURSOR` is clear; otherwise `TTYC_CNORM` then `tty_putcode_i(tty, TTYC_SS, 1..6)`;
for `SCREEN_CURSOR_DEFAULT` prefer `TTYC_SE`, falling back to `Ss` with parameter 0; and
when `Ss` is absent entirely, fall back to `TTYC_CVVIS` for the blinking cases.

**xterm resources and mode 12. [VERIFIED]** `cursorBlink`, `cursorBlinkXOR`,
`cursorOnTime`/`cursorOffTime`, `cursorUnderLine`, `cursorBar`, `cursorColor`
(<https://invisible-island.net/xterm/manpage/xterm.html>). Mode 12 is the writable "AT&T
610" blink toggle — what `cnorm`/`cvvis` manipulate. Modes **13 and 14 are read-only**,
"provided only for reporting their values using this control sequence [DECRQM] … 1 3 and
1 4 correspond to the resources cursorBlink and cursorBlinkXOR." Net: blink is reachable
two ways (mode 12, and the odd/even parity of the DECSCUSR parameter), and they are not the
same state on every terminal — Alacritty makes the coupling explicit:
`blinking: cursor_style_id % 2 == 1`.

**Per-terminal notes. [VERIFIED]**

- **kitty**: no DECSCUSR extension, but a **multiple-cursors protocol** (0.43) whose extra
  cursors are explicitly independent of DECTCEM — "the main cursor's visibility must not
  affect the visibility of the extra cursors."
  <https://sw.kovidgoyal.net/kitty/multiple-cursors-protocol/>. Config adds
  `cursor_shape_unfocused` (with `hollow`, `unchanged`), `cursor_blink_interval` (accepts
  an easing function), `cursor_stop_blinking_after` (default 15 s), `cursor_trail`.
- **kitty shell integration** emits `\e[5 q` / `\e[1 q` at the prompt and **`\e[0 q` before
  running each external command**; opt out with `shell_integration no-cursor`. Your shape
  state is routinely reset out from under you.
  <https://sw.kovidgoyal.net/kitty/shell-integration/>
- **mintty** extends DECSCUSR with `CSI Ps ; blink SP q` and proprietary shapes 11–12; also
  honours the Linux `CSI ? n c` cursor-size sequence.
- **iTerm2** has proprietary `OSC 1337 ; CursorShape=N ST`, and a whole alternative
  capability channel — `TERM_FEATURES`, or `OSC 1337 ; Capabilities ST`, in which `Sc` is a
  3-bit integer "indicat[ing] the features of `DECSCUSR` the terminal supports". Notably it
  carries **no DECTCEM bit** — visibility is assumed universal.
  <https://iterm2.com/feature-reporting/>
- **Konsole implements DECSCUSR** (`token_csi_psp('q', 0..6)`) — it can *set* cursor style
  but cannot *report* it.
- **Linux VC and mosh do not implement DECSCUSR at all.**
- **WezTerm**: no DECSCUSR extension found in its escape-sequence docs. **[UNKNOWN]**
  whether any exists.
- **PuTTY**: no `CSI Ps SP q` handler found in the 2020 mirror; no wishlist entry.
  **[VERIFIED for ≤0.75 / INFERRED for current]**

### 3.3 Is DECTCEM universal? Effectively yes.

| Environment | `?25l` / `?25h` | Evidence |
|---|---|---|
| xterm, urxvt, st, foot, kitty, Alacritty, WezTerm, Ghostty, Konsole, VTE, iTerm2, mintty | **Yes** | source-level |
| PuTTY | **Yes** | `case 25: /* DECTCEM: enable/disable cursor */ … term->cursor_on = state;` **[VERIFIED ≤0.75]** ([github mirror](https://github.com/github/putty/blob/master/terminal.c), newest commit 2020-09-13; `git.tartarus.org` 403s to fetchers, so **[INFERRED]** for 0.83) |
| rxvt-unicode | **Yes** | `{ 25, PrivMode_VisibleCursor }` **[VERIFIED]** |
| st | **Yes** | `case 25: /* DECTCEM */ xsetmode(!set, MODE_HIDE);` **[VERIFIED]** <https://git.suckless.org/st/file/st.c.html> |
| Terminal.app | **Yes** | Indirect only — the `nsterm` entry ncurses ships for it defines `civis=\E[?25l, cnorm=\E[?25h` **[VERIFIED]** |
| Linux VC | **Yes, per console, re-asserted on VT switch** | `CSI_DEC_hl_SHOW_CURSOR = 25, /* TCEM */` → `vc->vc_deccm = on_off;`, consumed in `set_cursor()`. `redraw_screen()` does `hide_cursor(old_vc)` … `set_cursor(vc)`, so Alt+F2/Alt+F1 restores each console's own state **[VERIFIED]** |
| conhost + `ENABLE_VIRTUAL_TERMINAL_PROCESSING` | **Yes** | "The DECTCEM sequences are **generally equivalent to calling SetConsoleCursorInfo**" **[VERIFIED]** |
| **conhost WITHOUT that flag, or pre-Win10 TH2** | **NO — ignored outright** | The doc's own precondition: sequences are intercepted "**if the ENABLE_VIRTUAL_TERMINAL_PROCESSING flag is set** on the screen buffer handle" **[VERIFIED]** |
| **Windows Terminal < ~v0.9 (2019)** | **NO — ignored outright** | [microsoft/terminal#3093](https://github.com/microsoft/terminal/issues/3093) — `printf '\e[?25l'` left the cursor visible on v0.5.2762.0; fixed by PR #4902 before v1.0 **[VERIFIED]** |
| tmux | **Yes, per pane, re-asserted** | below |
| GNU screen | **Yes, per window, re-asserted** | below |
| mosh | **Yes, part of synced state** | below |

**Those are the only two emulators found that ignore `CSI ?25l` outright** — legacy conhost
without VT processing, and pre-1.0 Windows Terminal. Among mainstream Unix emulators,
**none**. **[INFERRED]** from the absence of evidence across the fourteen implementations
above, all of which implement it.

**Windows: the two mechanisms are the same state. [VERIFIED]**
`SetConsoleCursorInfo` now carries a deprecation banner — "no longer a part of our
ecosystem roadmap… This API has a virtual terminal equivalent in the cursor visibility
section with the `^[[?25h` and `^[[?25l` sequences."
<https://learn.microsoft.com/en-us/windows/console/setconsolecursorinfo>. The coupling is
bidirectional in source: `adaptDispatch.cpp` maps `DECTCEM_TextCursorEnableMode` to
`Cursor().SetIsVisible(enable)`, and `src/host/getset.cpp`'s
`SetConsoleCursorInfoImpl()` calls `context.SetCursorInformation(...)` **and**, under
ConPTY, `writer.WriteDECTCEM(isVisible)` — a legacy Win32 call translated into DECTCEM
emitted outward. Note `CONSOLE_CURSOR_INFO.dwSize` has no VT equivalent; only `bVisible`
maps.

**tmux. [VERIFIED]** `input.c`: `case 25: /* TCEM */ screen_write_mode_set(sctx, MODE_CURSOR);`.
State lives in `struct screen::mode`; **every pane has its own base screen plus its own
alternate screen**; `screen_init()` → `s->mode = MODE_CURSOR;`. Pane switch, redraw and
attach are all safe: `server_client_reset_state()` starts `s = wp->screen; … mode = s->mode;`
and ends `tty_update_mode(tty, mode, s)`, recomputing from the currently active pane every
time. On attach, `tty->mode = ALL_MODES;` poisons the diff so nothing is skipped. tmux also
forces the cursor hidden in copy-mode, menus, when scrolled out of the visible offset,
behind scrollbars, and globally via `TTY_NOCURSOR`.

**GNU screen. [VERIFIED]** `src/ansi.c`:

```c
case 25:	/* TCEM: text cursor enable mode */
	win->w_curinv = !i;
	LCursorVisibility(&win->w_layer, win->w_curinv ? -1 : win->w_curvvis);
	break;
```

`window.c:WinRestore()` re-emits `CursorVisibility(...)` on window switch;
`display.c:CursorVisibility()` emits terminfo `D_VI`/`D_VE`/`D_VS` and *always emits `VE`
first "just to be safe"*. screen also implements DECSCUSR, emitting a hardcoded
`"\033[%d q"`.

**mosh. [VERIFIED]** `bool cursor_visible;` is a member of `DrawState`, initialised `true`,
reset to `true` on DECSTR, and participates in `DrawState::operator==` — so it is diffed and
**synchronised**, which is why roaming/resume restores it. `terminaldisplay.cc` emits it
**hardcoded, not via terminfo**. No DECSCUSR (open tickets #352, PR #1355).

**Two structural facts about multiplexers. [VERIFIED]**

1. **Your `?25l` bytes never reach the outer terminal verbatim.** tmux and screen translate
   to the *outer* terminfo's `civis`/`cnorm`/`cvvis`; mosh re-synthesises the sequence.
   Outer-terminal correctness depends on the outer `TERM` entry, not on your bytes.
2. **Feature skew is real**: DECSCUSR is absent where DECTCEM is present — Linux VC, mosh,
   PuTTY (≤0.75), and contested on Terminal.app.

**Non-application ways the cursor ends up hidden. [VERIFIED]**

- **Linux VC**: `vc->vc_deccm = global_cursor_default;` with
  `module_param(global_cursor_default, …)`. Booting with `vt.global_cursor_default=0` starts
  **every** VC with the cursor hidden, before any app runs.
- **Linux VC, second channel**: `ESC [ ? n c` sets `vc_cursor_type`; `CUR_SIZE(...) ==
  CUR_NONE (1)` suppresses the hardware cursor **independently of `vc_deccm`**. So `?25h`
  alone may not bring it back if the shape was set to 1.

**The classic failure: app exits without restoring.** This is the dominant real-world
problem, and it is application-side. **[VERIFIED]**

- [pypa/pip-audit#280](https://github.com/pypa/pip-audit/issues/280) — "the terminal cursor
  remains hidden… This makes it difficult to use the terminal, unless the cursor is
  restored with the `reset` command."
- [console-rs/dialoguer#77](https://github.com/console-rs/dialoguer/issues/77) — "Cursor
  disappears when using SIGINT (ctrl-c)".
- [Textualize/rich#3690](https://github.com/Textualize/rich/pull/3690) — Ctrl+C during
  `Progress`/`Live` skips the restore path; fix adds try/except, a SIGINT handler that shows
  the cursor before re-raising, and an `atexit` handler.

What each fix does:

- **`printf '\e[?25h'`** — minimal; works wherever DECTCEM works, changes nothing else.
  **[VERIFIED]**
- **`tput cnorm`** — emits terminfo `cnorm`, which as shown above **also changes blink
  state** (and on `linux` restores shape). Not a pure restore. **[VERIFIED-local]**
- **`reset`** — "rather than using the terminal initialization strings, it uses the terminal
  reset strings", plus restores cooked/echo
  (<https://invisible-island.net/ncurses/man/tset.1.html>). For xterm the reset string is
  short "because it supports DECSTR" (`\E[!p`), and DECSTR sets visibility back to visible.
  Costs scrollback on many terminals. **[VERIFIED]**
- **`stty sane`** — **does not fix an invisible cursor.** `stty` touches only the termios
  line discipline, never emulator escape-sequence state. **[INFERRED]** from the documented
  split in `tset(1)` (reset termios *and then* send terminal strings); no source states the
  negative explicitly.

### 3.4 Querying cursor state

#### DECRQM `?25`

**[VERIFIED]** Reply values: `0` not recognised / `1` set / `2` reset / `3` permanently set
/ `4` permanently reset — <https://vt100.net/docs/vt510-rm/DECRPM.html>

| Terminal | DECRQM `?25` | visible / hidden | unknown mode | Emits 3 or 4 at all? |
|---|---|---|---|---|
| xterm | **Yes** | `1` / `2` | `0` | Yes (other modes) |
| kitty | **Yes** | `1` / `2` | `0` | **Never** |
| WezTerm | **Yes** | `1` / `2` | `0` | Yes (other modes) |
| foot | **Yes** | `1` / `2` | `0` | Yes (`4` for 9/67/1001/1005) |
| Ghostty | **Yes** (private form only — see quirk) | `1` / `2` | `0` | Yes (`4` for mode 117) |
| Alacritty ≥ 0.13.0 | **Yes** | `1` / `2` | `0` | **Never** (enum is 0/1/2) |
| iTerm2 | **Yes** | `1` / `2` | see quirk | Yes (ANSI form defaults to `4`) |
| VTE / gnome-terminal | **Yes** | `1` / `2` | `0` | Yes (`3`/`4` for fixed modes) |
| Windows Terminal / conhost | **Yes** (undocumented on Learn) | `1` / `2` | `0` | Yes |
| tmux | **Yes**, answered locally | `1` / `2` | `0` | Yes (`4` for DECCOLM) |
| mintty | **Yes** | `1` / `2` | `0` | Yes (`4` for 1048) |
| **Konsole** | **No — silence** | — | — | — |
| **st** | **No — silence** | — | — | — |
| **rxvt-unicode** | **No — silence** | — | — | — |
| **GNU screen** | **No — silence** | — | — | — |
| **mosh** | **No — silence** | — | — | — |
| **Linux VC** | **No — sequence discarded** | — | — | — |
| PuTTY | Probably no **[INFERRED]** | — | — | — |
| Terminal.app | **[UNKNOWN]** | — | — | — |

All rows **[VERIFIED]** at pinned commits except the two noted. Key sources:

- xterm: `do_dec_rqm()` is in **`misc.c`**, not `charproc.c` —
  `case srm_DECTCEM: result = MdBool(screen->cursor_set);` with
  `#define MdBool(bool) ((bool) ? mdMaybeSet : mdMaybeReset)`.
  <https://github.com/ThomasDickey/xterm-snapshots/blob/9489b2056ee51fa9dd6a7087483b9b8f85d6a0c4/misc.c#L5550-L5552>
- kitty: `report_mode_status()` `KNOWN_MODE(DECTCEM)`, `ans` initialised 0.
  <https://github.com/kovidgoyal/kitty/blob/0b12ed8c41b2a2e4c2bb34c9cbc568970540ce5e/kitty/screen.c#L3243-L3279>
- iTerm2: `case 25: return VT100TerminalPromiseOfDECRPMSettingFromBoolean([self.delegate terminalCursorVisible]);`
  <https://github.com/gnachman/iTerm2/blob/b120f0f22acc83c97727bf21262ac862e2757d6f/sources/VT100/VT100Terminal.m#L5572-L5574>
- VTE: `Terminal::DECRQM_DEC` — `eUNKNOWN→0, eALWAYS_SET→3, eALWAYS_RESET→4, default → get(mode) ? 1 : 2`;
  mode 25 is `WRITABLE` so takes the default branch.
  <https://github.com/GNOME/vte/blob/5c8e6172c27c10272d2b9210749af765dfc1898e/src/vteseq.cc#L4660-L4689>
- Konsole negative: `csi_dispatch()` **discards intermediates**, so `CSI ? 25 $ p` becomes
  indistinguishable from `CSI ? 25 p`, and there is no `token_csi_pr('p', …)` case anywhere —
  it falls to `default: reportDecodingError(token);`.
  <https://github.com/KDE/konsole/blob/4e4855ff4d61020586d180de34ec93faf6a5c8f8/src/Vt102Emulation.cpp#L559-L629>

**Build/level gates that make "supported" conditional. [VERIFIED]**

- **xterm**: all of `do_dec_rqm` sits inside `#if OPT_DEC_RECTOPS`. Default on;
  `--disable-rectangles` removes DECRQM entirely.
- **iTerm2**: DECRQM dispatch runs only `if (_vtLevel >= iTermEmulationLevel300)`. Default
  is `iTermEmulationLevel500`, so on by default — but an app that drops the conformance
  level loses it.
- **Ghostty quirk**: in `stream.zig` the `'p'` arm matches only **2** intermediates, so
  `CSI ? Ps $ p` works but the **ANSI form `CSI Ps $ p` is unreachable**.
  <https://github.com/ghostty-org/ghostty/blob/b0c421fcd2e290629d4285c181b52fe2f2095f06/src/terminal/stream.zig#L2167-L2206>
- **iTerm2 quirk**: the *ANSI* DECRQM path returns **`4` (permanently reset)** for
  everything except modes 4 and 12.

**[VERIFIED]** `ghostty.org/docs/vt/csi/decrqm` is a **404** — the evidence for Ghostty is
source-only. And [Terminal Guide's DECRQM page](https://terminalguide.namepad.de/seq/csi_sp__p_t_dollar/)
lists only xterm and vte — it is **stale** and contradicted by source for kitty, foot,
Ghostty, WezTerm, Windows Terminal, tmux, Alacritty and mintty. Do not use it as a negative
signal.

#### DECRQSS for DECSCUSR — do not use it as a shape probe

xterm's contract: `DCS 1 $ r Pt ST` valid / `DCS 0 $ r ST` invalid. **[VERIFIED]**

| Terminal | `$q SP q` | Reply / trap |
|---|---|---|
| xterm | **Yes** | `DCS 1 $ r Ps SP q ST`; `code -= 1` when blinking. Not gated on `OPT_DEC_RECTOPS` |
| kitty | **Yes** | **Trap:** blinking block reports **`0`**, not `1` (`shape = non_blinking ? 2 : 0`) |
| foot | **Yes** | block 2 / underline 4 / beam 6, −1 when blinking |
| Ghostty | **Yes** | `\x1bP1$r{d} q\x1b\\` |
| iTerm2 | **Yes** | block→1, underline→3, vertical→5, `code++` when not blinking |
| VTE | **Yes** | `DECRPSS` param 1 + `DECSCUSR` builder; invalid → param `0` |
| mintty | **Yes** | `\eP1$r%u q\e\\` |
| Windows Terminal | **Yes** | **Trap:** a user-default/non-standard style reports **`1$r0 q`** — deliberately, so apps restore the user default |
| **tmux** | Yes, but **malformed** | Emits `"\033P1$r q%d q\033\\"` — an **extra leading `SP q`**, non-conformant vs xterm, deliberate per the in-code comment. <https://github.com/tmux/tmux/blob/1b87cb752e0cfa5be66235c4c9228aadbe3487d7/input.c#L2552-L2616> |
| **WezTerm** | **No** | Handles only `"p`, `r`, `s`; else `DCS 0 $ r ST` |
| **Alacritty** | **No — total silence** | `vte` crate's `hook`/`put`/`unhook` are debug-log stubs; **no reply at all, not even `0$r`** |
| **Konsole** | **No** | `hook()` accepts `'q'` only with zero intermediates (Sixel) |
| st, urxvt, GNU screen, mosh, Linux VC | **No** | — |

All **[VERIFIED]** at pinned commits. **Four independent traps make the returned `Ps`
untrustworthy even when a reply arrives**: Alacritty is silent (hangs a naive reader),
WezTerm answers "invalid", tmux answers a malformed frame, and kitty/Windows Terminal both
return `0` for legitimate states. DECRQM `?25` is materially more reliable.

#### CPR / DECXCPR as a fence

| Sequence | Name | Reply | Reach |
|---|---|---|---|
| `CSI 6 n` | CPR (DSR 6) | `CSI r ; c R` | **Effectively universal** |
| `CSI ? 6 n` | DECXCPR | `CSI ? r ; c R` | **Much narrower — do not rely on it** |
| `CSI 5 n` | DSR operating status | `CSI 0 n` | Widely supported |
| `CSI c` | Primary DA | `CSI ? … c` | **The correct fence** |

**[VERIFIED]** CPR's reach: terminfo `u7=\E[6n` / `u6=\E[%i%d;%dR` in **530 of 1865** local
entries **[VERIFIED-local]**; `console_codes(4)` documents it for the Linux console;
Microsoft documents `ESC [ 6 n`; tmux answers it locally with `"\033[%u;%uR"`; Ghostty
documents Ps=5 and Ps=6.

**[VERIFIED]** DECXCPR is **not** a safe substitute: tmux's `INPUT_CSI_DSR_PRIVATE` handles
only `?996`, not `?6`; Ghostty says "If any other value of `n` is provided, this sequence
does nothing"; `console_codes(4)` lists no private form.

**Two caveats on CPR as the fence. [VERIFIED]**

1. **A CPR-shaped reply can be user input.** xterm: "it is possible for this sequence to be
   sent by a function key. For example, with the default keyboard configuration the shifted
   F3 key may send… `CSI 1 ; 2 R`, or `CSI 1 ; 5 R`, or `CSI 1 ; 6 R`, etc."
2. **Ghostty's CPR respects origin mode** — with DECOM set, the position is relative to the
   scroll region.

**The canonical fence is Primary DA (`CSI c`), first-party documented as such** by kitty for
both its keyboard protocol and its multiple-cursors protocol (quoted in §2.5). The
synchronized-output spec applies it to DECRQM specifically: "If you get nothing back
(DECRQM not implemented at all) or you get back `CSI ? 2026 ; 0 $ y`, then the feature isn't
supported." **[VERIFIED-secondary]**
<https://gist.github.com/christianparpart/d8a62cc1ab659194337d73e399004036>

**Recipe:** send `<probe>` + `CSI c`; read until either the probe reply or the DA reply
arrives; DA-first means "not supported"; nothing within a timeout means "terminal answers
nothing, degrade". Do not use CPR as the sole fence; do not use `CSI ? 6 n` at all.

### 3.5 Accessibility and self-drawn cursors

#### Screen readers — one terminal has a real problem

**Windows Terminal (UIA): hiding the cursor suppresses caret events. [VERIFIED at source;
not empirically tested with a screen reader]**

The text provider is fine — `ScreenInfoUiaProviderBase::GetSelection` returns a degenerate
range at `GetTextBuffer().GetCursor()` with **no** visibility check, so *asking* "where is
the caret" works while hidden
(<https://github.com/microsoft/terminal/blob/main/src/types/ScreenInfoUiaProviderBase.cpp>).
But the caret *event* is gated, via a four-step chain:

1. `Renderer::_updateCursorInfo()` — `AllowCursorVisibility(InhibitionSource::Client, cursor.IsVisible());`
   … `_currentCursorOptions.isOn = _currentCursorOptions.isVisible && _cursorBlinkerOn;`
2. `Renderer::_invalidateCurrentCursor()` — `if (!_currentCursorOptions.inViewport || !_currentCursorOptions.isOn) { return; }`
   → `pEngine->InvalidateCursor(&rect)` never runs.
3. `UiaEngine::InvalidateCursor` is the only thing that sets `_cursorChanged`;
   `UiaEngine::Present()` calls `_dispatcher->SignalCursorChanged()` only `if (_cursorChanged)`.
4. `TermControlAutomationPeer::SignalCursorChanged()` raises
   `AutomationEvents::TextPatternOnTextSelectionChanged`;
   `HwndTerminalAutomationPeer::SignalCursorChanged` raises `UIA_Text_TextSelectionChangedEventId`.

Net: with `CSI ?25l` in effect, **Windows Terminal raises no UIA caret/selection-changed
event**, so NVDA/JAWS/Narrator get no caret-moved notification. Present identically in
v1.21.2361.0 and v1.24.3504.0 — long-standing, not a regression.

What still works: `UiaEngine::Invalidate()` (text changed) and `NotifyNewText()` →
`NotifyNewOutput` are on a separate path with no cursor involvement, so **new-output
announcements and `TextPatternOnTextChanged` still fire**; only caret tracking dies.
**[VERIFIED]**

Maintainer statement on the same gate (blink phase rather than DECTCEM, but the identical
`isVisible && _cursorBlinkerOn` condition) — Carlos Zamora, Microsoft, Terminal
accessibility owner: "NOTE: it looks like the screen reader normally reads the character
specifically when the cursor blinks. Definitely bizarre." **[VERIFIED]**
<https://github.com/microsoft/terminal/issues/19374>

**conhost differs and is unaffected. [VERIFIED]** `AccessibilityNotifier::CursorChanged()`
— which primes `EVENT_CONSOLE_CARET`, the `ConsoleControl(ConsoleSetCaretInfo)` call, and
the UIA `textSelectionChanged` flag — is called from `_stream.cpp` and `getset.cpp` with
**no** DECTCEM check. A repo-wide audit shows `Cursor::IsVisible()` is consumed only by
renderer inhibitors, the DECRQM reply, `SixelParser`, alt-buffer state copy,
`VtIo::WriteDECTCEM`, the win32 menu, `selectionState`, and tests. **No UIA provider
consults it.**

**[VERIFIED]** NVDA side: `winConsoleUIA.py` notes for Windows Terminal that "Automatic
reading of terminal output is provided by UIA notifications" and blocks notification events
while diffing. **[INFERRED]** This partly mitigates the missing caret event for *output*;
caret-review / "read char under caret" still depends on the caret.

**iTerm2 / VoiceOver — unaffected. [VERIFIED at source]**
`PTYTextView.accessibilityHelperCursorCoord` derives from `[_dataSource cursorX]/cursorY`
only; `insertionPointLineNumber` / `accessibilityRangeOfCursor` / `find_caret` all use that
coord; `refreshAccessibility` posts `NSAccessibilitySelectedTextChangedNotification` purely
on coordinate change, with **no `cursorVisible` check**. `cursorVisible` appears only in the
Metal driver, `iTermMetalPerFrameState`, `PTYTextView` drawing, and session/tab logic —
never in `sources/Accessibility/`. Nice inline comment showing deliberate care with the
*review* cursor: "Do not post NSAccessibilityLayoutChangedNotification here: with
NSAccessibilityUIElementsKey it directs VoiceOver to move its cursor to the listed element,
relocating the user's review cursor to the top of the terminal." No iTerm2 issue linking
DECTCEM to VoiceOver found. **[UNKNOWN]**

**VTE / Orca — unaffected. [VERIFIED at source]** `vte_terminal_get_cursor_position()`
returns `impl->m_screen->cursor.col/row` verbatim, no mode check. `vteaccess.cc` (ATK/GTK3)
and `vteaccess-gtk4.cc` (`GtkAccessibleText`) compute the caret from that, hooked to
`cursor-moved`. `Terminal::queue_cursor_moved()` fires whenever the cursor changed after
processing input — no DECTCEM check. `m_modes_private.DEC_TEXT_CURSOR()` is used in exactly
4 places, all rendering/blink. Orca's terminal script consumes
`AXText.get_caret_offset()` with no visibility notion.
<https://github.com/GNOME/orca/blob/main/src/orca/scripts/terminal/script.py>

**Linux console (Speakup) — unaffected. [VERIFIED]** `drivers/tty/vt/vc_screen.c` builds
the `/dev/vcsa` header via `getconsxy(vc, con_buf + 2)` unfiltered;
`drivers/accessibility/speakup/main.c` tracks `vc->state.x`, `vc->state.y`, `vc->vc_pos`
with no `deccm` / `CUR_NONE` reference.

**Terminal.app + VoiceOver: [UNKNOWN]** — closed source, no Apple documentation found.

**First-party "don't hide the cursor for accessibility" guidance: none found.
[UNKNOWN/negative]** Not in `curs_set(3x)`, not in Windows Terminal docs, not in Apple docs.
Windows Terminal's own screen-reader spec
`doc/specs/#13666 - VT Sequence for Screen Reader Control.md` proposes OSC 200/201/202 and
says **nothing** about DECTCEM or the caret. **[VERIFIED]**

**Counter-current worth knowing about.** A blind Speakup/NVDA user argues hiding the cursor
is an accessibility *benefit*, because a constantly-teleporting visible cursor drowns out
character echo — "The cursor is teleporting all over the screen to update status
indicators, spinners, and history… Speakup tries to read whatever is under the cursor at
that exact millisecond." / "If you cannot guarantee that your application allows the user to
hide the cursor… you are building an inaccessible tool."
(<https://xogium.me/the-text-mode-lie-why-modern-tuis-are-a-nightmare-for-accessibility>).
This is lived experience, not first-party docs, and the stated *mechanism* is contradicted
by the kernel source (Speakup's tracking is not DECTCEM-gated) — **[INFERRED]** the real
effect is more likely that apps which hide the cursor also stop dragging it around during
redraws.

#### IME candidate-window placement

**No terminal examined consults DECTCEM when placing the IME window. [VERIFIED at source
for all six]** All compute the rect from the grid cursor.

| Terminal | Code path | Checks visibility? |
|---|---|---|
| Windows Terminal (TSF) | `Implementation::GetTextExt` → `TsfDataProvider::GetCursorPosition()` → `core->CursorPosition()` + `core->FontSize()` | No |
| kitty | `prepare_ime_position_update_event()` in `kitty/keys.c`: `left += screen->cursor->x * cell_width;` | No |
| WezTerm | `TermWindow::update_text_cursor()` → `pos.pane.get_cursor_position()` → `win.set_text_cursor_position(r)` | No |
| Ghostty | `Surface.imePoint()`: `const cursor = self.renderer_state.terminal.screens.active.cursor;` → `ghostty_surface_ime_point` | No |
| VTE | `Terminal::im_update_cursor()` builds the rect from `m_screen->cursor.col/row`, called unconditionally at the end of `process_incoming()` | No |
| iTerm2 | `PTYTextView firstRectForCharacterRange:actualRange:` via `absCoordRangeForNSRange` | No |

**The real-world bug is "cursor not moved", not "cursor hidden".** **[VERIFIED as issue
text]** anthropics/claude-code#35307: "Claude Code renders a 'fake cursor' in the TUI but
does not move the real terminal cursor to the caret position. The IME overlay anchors to
the real cursor, so it stays at the wrong location" — fix described there is "after each
render, the real terminal cursor needs to be moved to the TUI caret position (CUP),
preserving/restoring SGR state."

A sibling report (anthropics/claude-code#25186) blames the *hiding*: "React Ink… hides the
real terminal cursor and renders a fake cursor via `chalk.inverse()`. macOS IME relies on
the real terminal cursor position… Since the real cursor is hidden, the IME window falls
back to position (0,0)." That attribution is **not supported** by any terminal source read
here, and the accepted fix (Ink's `useCursor` / `setCursorPosition`) both **moves and
shows** the cursor, confounding the two effects. **[INFERRED: the operative factor is
position, not visibility]** Related open reports with unverified root cause:
zed-industries/zed#46055, anthropics/claude-code#50650, #51768.

**One genuine DECTCEM↔IME interaction, and it is rendering not placement. [VERIFIED]**
[GNOME/vte#2873](https://gitlab.gnome.org/GNOME/vte/-/issues/2873) — "pre-edit is hidden
when DEC_TEXT_CURSOR is off": `\e[?25l` made IME preedit text invisible, because preedit was
drawn through the cursor-invalidation path. Fixed; the code now carries:

```cpp
// Note that even with invisible cursor, still need
// to invalidate if preedit is active.
// See https://gitlab.gnome.org/GNOME/vte/-/issues/2873 .
if (m_modes_private.DEC_TEXT_CURSOR() || m_im_preedit_active) {
```

Separately, `Terminal::paint_cursor()` returns early on both `!DEC_TEXT_CURSOR()` **and**
`m_im_preedit_active` — VTE never draws the block cursor during composition.

Not verified: xterm.js (VS Code integrated terminal), Zed's GPUI terminal, Terminal.app.
**[UNKNOWN]**

### 3.6 Sequences that do NOT save cursor visibility

Relevant if you hoped to bracket a hide with a save/restore.

| Sequence | What it saves | Visibility? |
|---|---|---|
| `ESC 7` / `ESC 8` (DECSC/DECRC) | "Cursor position; Character attributes set by the SGR command; Character sets…; Wrap flag; State of origin mode (DECOM); Selective erase attribute; Any single shift 2 (SS2) or single shift 3 (SS3) functions sent" | **No** **[VERIFIED]** <https://vt100.net/docs/vt510-rm/DECSC.html> |
| `CSI ? 1048 h/l`, `CSI ? 1049 h/l` | "Save cursor as in DECSC" | **No** **[VERIFIED]** (ctlseqs) |
| `CSI s` / `CSI u` (SCOSC/SCORC) | cursor position; and **`CSI s` is only save-cursor when DECLRMM is disabled — otherwise it is DECSLRM** | **No**, and ambiguous — avoid **[VERIFIED]** |
| **`CSI ? 25 s` / `CSI ? 25 r` (XTSAVE/XTRESTORE)** | "Ps values are the same as for DECSET… Like Save Cursor (DECSC), this uses a one-level cache. Unlike Save Cursor, specific settings can be saved and restored independently." | **Yes — the only standard mechanism** **[VERIFIED]** |

**[VERIFIED]** Ghostty confirms the DECSC list omits visibility and adds "Primary and
alternate screens have separate saved cursor state"
(<https://ghostty.org/docs/vt/esc/decsc>). Konsole implements
`token_csi_pr('s', 25)` / `('r', 25)`; coverage in other emulators **[UNKNOWN]** — not
audited broadly, so do not treat XTSAVE as portable.

Consequence: **an `auto` default cannot promise "restore whatever was there".** Combined
with ncurses' own admission that it cannot determine the initial visibility, the only honest
restore target is the DEC power-on default, `?25h`.

---

## 4. What `auto` can honestly mean

### 4.1 OSC 8

**[VERIFIED]** There is no capability query at any layer. A startup probe can only
*identify* the terminal, never ask it. **`auto` cannot mean "detected"; it can only mean
"matched a known-good identity".**

**[INFERRED]** Concrete rules:

1. **Default off unless positively identified.** Absence of evidence is not evidence of
   support, and two of the three real corruption cases (old VTE, old Linux console) are
   legacy Linux desktops — where identification is least reliable.
2. **A single probe is fine, because the environment is stable for the process lifetime.**
   The risky case — being reattached to a different outer terminal — happens inside
   tmux/screen, and neither will let a raw OSC 8 reach the new outer terminal anyway. This
   is the one genuinely reassuring result: multiplexers make "the terminal changed under me"
   safe *by dropping*, not by corrupting.
3. **`$VTE_VERSION` is the highest-value single check.** ≥ 5002 ⇒ works; ≥ 4602/4802 ⇒
   safely swallowed; lower, or a VTE-family `$TERM` with no `$VTE_VERSION`, is the
   garbage-emitting range ⇒ hard-disable.
4. **Inside tmux, read `Hls` from terminfo** — present exactly when tmux will forward the
   link. Expect the no-op case to be common (only six outer terminals are granted the
   feature by default) and do not treat it as failure.
5. **Under GNU screen, disable unconditionally.** It never renders links and spills any OSC
   string over ~767 bytes.
6. **Cap URIs under ~700 bytes** regardless — that clears screen's 768, PuTTY's 2048 and
   VTE/iTerm2's 2083.
7. **Prefer BEL over `ESC \`** for legacy safety, and never emit a byte outside 32–126.
8. **Do not build a runtime probe with a timeout** — XTGETTCAP for `Hls` is
   negative-by-construction everywhere outside tmux.

### 4.2 Truecolor

**[VERIFIED]** A promotion ladder, evaluated in order, where **nothing ever demotes**:

1. **Multiplexer first.** If `$TMUX`: do not probe — tmux answers `DCS $ q m ST` with
   `DCS 0 $ r ST`, never forwards it outward, never routes replies inward, and drops
   `DCS + q`. Read terminfo `Tc`/`RGB` on `$TERM` and stop. If `$STY`: assume 256 unless
   overridden — screen ≤ 4.9 mangles 24-bit SGR while happily passing COLORTERM through.
2. **`COLORTERM ∈ {truecolor, 24bit}`, case-insensitive, exact match.** High precision, low
   recall. Reject `rxvt*`, `xfce4-terminal`, `gnome-terminal`. Inside tmux ≥ 3.6 it is set
   unconditionally and means nothing.
3. **terminfo `Tc || RGB || (setrgbf && setrgbb)`.** Never equality-test `colors`.
4. **One fenced round trip, promotion-only.** Write in a single burst:
   `CSI 38;2;1;2;3 m` · `DCS $ q m ST` · `CSI 0 m` · `CSI c`. Stop on the DA1 reply or
   ~100–200 ms, whichever comes first. Parse liberally: `1$r` = valid; accept all four wire
   formats; take the last three sub-params; compare with tolerance (xterm loses low bits on
   <8-bit visuals); scan the whole input stream, since keystrokes interleave.
5. **A negative or absent DECRQSS answer must never demote.** `DCS 0 $ r ST` is what WezTerm
   and tmux return *while being fully truecolor*; silence is what Alacritty, Konsole and the
   Linux console return. **Only `38:5:N` — xterm's honest palette rounding — is real
   evidence against.**
6. **XTGETTCAP is not a better probe.** Useful only as a second promotion path where a DA1
   fence is already in flight.
7. **XTVERSION name-sniffing is the defensible last resort, as an allowlist.** Copy tmux's:
   prefix-match `iTerm2 `, `XTerm(`, `mintty `, `foot(`, `WezTerm `, `ghostty `, `Rio `,
   `kitty(`; exclude `rxvt-unicode`. It will not help for Alacritty or Windows Terminal,
   which implement no version query at all.

**[INFERRED]** So `auto` means: *"truecolor if the terminal told us (COLORTERM), or its
terminfo claims it (`Tc`/`RGB`), or it proved it once at startup, or it identified itself as
a known-truecolor terminal; otherwise 256."* It **cannot** mean "truecolor iff supported" —
Alacritty and Windows Terminal are undetectable by any query, and WezTerm, tmux and Konsole
actively answer "no" or nothing. A single startup handshake is a **promotion ladder, not a
capability test**, which is why an explicit user override is mandatory.

### 4.3 Cursor

**[INFERRED]** **`CSI ?25l` is honoured essentially everywhere — emit it unconditionally.**
Any Unix-ish terminal, inside tmux/screen/mosh, and on Windows given
`ENABLE_VIRTUAL_TERMINAL_PROCESSING` + Win10 1511 / Windows Terminal ≥ 1.0. The only two
environments that ignore it outright are legacy conhost without VT processing and pre-1.0
Windows Terminal, both obsolete. **A startup probe adds essentially nothing to the hide/show
decision.**

What actually bites is not portability:

1. **Restore on every exit path** — normal return, panic, `atexit`, SIGINT/SIGTERM/SIGHUP.
   This is the dominant real-world bug class (pip-audit, dialoguer, rich). The only honest
   restore target is `?25h`; DECSC/DECRC and `?1048`/`?1049` do not save visibility, and
   XTSAVE/XTRESTORE is not portable. **[VERIFIED]**
2. **Windows Terminal suppresses UIA caret events while the cursor is hidden**, and **there
   is no way to detect an attached screen reader**. This wants a user-facing opt-out, not
   autodetection. **[VERIFIED]**
3. **Not moving the real cursor breaks IME placement** — independently of visibility. If the
   TUI draws its own caret, it should still `CUP` the real cursor to the caret position each
   frame. **[VERIFIED / INFERRED as noted in §3.5]**
4. **If you ever query cursor state, DECRQM `?25` is the tool** — a clean tri-state
   (`1`/`2` = known, `0` = speaks DECRQM but not this mode, silence = does not speak
   DECRQM), and **no terminal returns 3 or 4 for mode 25**. But "supports DECRQM" is not a
   stable property of a binary: xterm loses it under `--disable-rectangles`, iTerm2 loses it
   below VT300 conformance, Ghostty's ANSI form is unreachable. A startup probe measures the
   running configuration, not the product. **[VERIFIED]**
5. **Never use DECRQSS-for-DECSCUSR as a shape probe** — four independent traps. **[VERIFIED]**

---

## 5. Residual unknowns

Narrow, and listed so they are not silently treated as settled:

- Terminal.app: OSC 8 behaviour; whether it sets COLORTERM on macOS 26; DECRQM support;
  VoiceOver interaction with DECTCEM.
- PuTTY ≥ 0.76: DECTCEM and DECRQM re-verification (`git.tartarus.org` 403s to fetchers; the
  GitHub mirror stops at 2020-09-13 / ~0.75).
- Whether xterm's XTGETTCAP answers `Tc`.
- iTerm2 master: XTGETTCAP capability set, and whether it still sets COLORTERM (the file
  exceeds fetch limits; verified at v3.1.7).
- mintty ≥ 3.2 DECRQSS reply text.
- Verbatim bodies of `xterm-direct2` / `-16` / `-256` and the other `*-direct` entries.
- Which VTE release first shipped DECRQSS.
- XTSAVE/XTRESTORE (`CSI ? 25 s` / `r`) coverage outside Konsole.
- xterm.js (VS Code integrated terminal) and Zed's GPUI terminal: IME placement paths.
- Windows Terminal UIA caret suppression is verified at source but **not** empirically
  tested with NVDA/JAWS.
