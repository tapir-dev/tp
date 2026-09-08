# Inline, non-alt-screen rendering support in ratatui and crossterm

Research note for [#9](https://github.com/tapir-dev/tp/issues/9). Answers one
question: **how much of tp's scrollback-mode rendering requirements do
`ratatui` and `crossterm` already provide today?** It reports capability only.
It does not propose a rendering architecture — that is a separate, blocked
ticket.

## Versions these findings hold for

| Crate | Version | Released | Notes |
| --- | --- | --- | --- |
| `ratatui` | **0.30.2** | 2026-06-19 | facade crate; real code is in the workspace split below |
| `ratatui-core` | 0.1.2 | — | `Terminal`, `Viewport`, `Buffer`, `Backend`, `Line`/`Span` live here since 0.30.0 |
| `ratatui-crossterm` | 0.1.2 | — | the `CrosstermBackend` |
| `ratatui-widgets` | 0.3.2 | — | |
| `crossterm` | **0.29.0** | 2025-04-05 | CHANGELOG has an unreleased section; no 0.30 yet |
| `unicode-width` | 0.2.2 | 2025-10-06 | |
| `unicode-segmentation` | 1.13.3 | 2026-06-01 | |
| `anstyle-parse` | 1.0.0 | 2026-02-11 | |
| `ratatui-image` | 11.0.8 | 2026-09-04 | |
| `image` | 0.25.10 | 2026-03-10 | |
| `icy_sixel` | 0.7.0 | 2026-09-06 | |

Sources: <https://crates.io/api/v1/crates/ratatui>,
<https://crates.io/api/v1/crates/crossterm>. Statements below were checked
against the published source of those exact versions, not against `main`,
unless a fix is explicitly flagged as unreleased.

Note the default feature set of `ratatui` 0.30.2 is
`["all-widgets", "crossterm", "layout-cache", "macros", "underline-color"]` —
**`scrolling-regions` is not on by default**, which matters in §1.3.

---

## 1. ratatui's inline/viewport modes and their concrete limits

### 1.1 The `Viewport` enum

`ratatui-core-0.1.2/src/terminal/viewport.rs`
([source](https://github.com/ratatui/ratatui/blob/main/ratatui-core/src/terminal/viewport.rs),
[docs](https://docs.rs/ratatui/0.30.2/ratatui/enum.Viewport.html)):

```rust
pub enum Viewport { Fullscreen, Inline(u16), Fixed(Rect) }
```

`Viewport::Inline(h)` resolves, at construction, to
`Rect { x: 0, y: <cursor row>, width: <full terminal width>, height: min(h, terminal_height) }`.
Selected via `TerminalOptions { viewport }` and `Terminal::with_options`; the
convenience entry point is `ratatui::init_with_options`, whose docs state
plainly that "Unlike `init`, this function does not enter the alternate screen
buffer" (`ratatui-0.30.2/src/init.rs`).

So the headline answer is yes: **ratatui can run without the alternate
screen.** The limits are in what that mode can and cannot do.

### 1.2 How the inline viewport reserves its space

`compute_inline_size` in `ratatui-core-0.1.2/src/terminal/inline.rs`:

1. `backend.get_cursor_position()?` — a blocking CPR (`ESC[6n`) round-trip.
2. `backend.append_lines(h - 1)?` — literally prints `h-1` newlines
   (`CrosstermBackend::append_lines` is `for _ in 0..n { Print("\n") }`,
   `ratatui-crossterm-0.1.2/src/lib.rs:330`), letting the terminal scroll.
3. Compensates `y` upward by the number of lines that scrolled.

Consequences: the viewport is full-width, anchored at the cursor row (not
pinned to the bottom), and its **height is fixed for the lifetime of the
`Terminal`**. There is no resize API
([#984](https://github.com/ratatui/ratatui/issues/984) open since 2024-03,
[PR #1964](https://github.com/ratatui/ratatui/pull/1964) still open).

### 1.3 `Terminal::insert_before` — the only path to scrollback

```rust
pub fn insert_before<F>(&mut self, height: u16, draw_fn: F) -> Result<(), B::Error>
where F: FnOnce(&mut Buffer)
```

([docs](https://docs.rs/ratatui/0.30.2/ratatui/struct.Terminal.html#method.insert_before),
`inline.rs:108`.) Returns `Ok(())` silently for non-inline viewports.

Confirmed properties:

- **You must know the height up front.** It allocates
  `Buffer::empty(Rect { x: 0, y: 0, width: viewport_width, height })`. Content
  wider than the terminal is **truncated by the buffer, not wrapped**. The only
  height helper in the whole widget crate is
  `Paragraph::line_count(width) -> usize`
  (`ratatui-widgets-0.3.2/src/paragraph.rs:332`). Open issues asking for
  content-derived height and line-oriented insertion:
  [#1365](https://github.com/ratatui/ratatui/issues/1365),
  [#1426](https://github.com/ratatui/ratatui/issues/1426). #1426 states the
  limitation exactly: "Ideally, when the screen was resized, the overlong lines
  would be re-wrapped by the terminal emulator. For that to happen, ratatui
  would need to output them as overlong lines, and not do the formatting
  itself."
- **Height may exceed the terminal height.** The cap was removed in 0.25.0
  ([PR #596](https://github.com/ratatui/ratatui/pull/596)).
- **Content genuinely reaches native scrollback.** The doc comment
  (`inline.rs:64`): "If more lines are inserted than there is space on the
  screen, then the top lines will go directly into the terminal's scrollback
  buffer. At the limit, if the viewport takes up the whole screen, all lines
  will be inserted directly into the scrollback buffer."
- **Ratatui keeps no copy of what it emitted.** The `Buffer` is a local,
  dropped when the call returns. There is no retained model above the viewport
  and no API to repaint it.
- **Two implementations, chosen at compile time.** The default build uses
  `insert_before_no_scrolling_regions`, which ends with `self.clear()` — the
  viewport is erased and fully repainted on the next `draw()`. With
  `--features scrolling-regions` (added in 0.29.0,
  [PR #1341](https://github.com/ratatui/ratatui/pull/1341)) it uses DECSTBM-style
  scroll regions and does not clear. The flicker issue
  [#584](https://github.com/ratatui/ratatui/issues/584) ("Inline Viewport
  Flickering With High Message Throughput", open since 2023-10, reproduced on
  crossterm/termion/termwiz across Linux/Windows/WSL) is mitigated by that
  feature — **which is off by default**.
- Wide-grapheme corruption in the non-scrolling-regions path:
  [#1332](https://github.com/ratatui/ratatui/issues/1332) /
  [PR #2527](https://github.com/ratatui/ratatui/pull/2527), open.

### 1.4 Resize — the sharpest limit

`autoresize()` runs on every `draw()` for inline viewports
(`ratatui-core-0.1.2/src/terminal/resize.rs`). In **0.30.2** it contains:

```rust
// clear screen on horizontal shrink to avoid line wrapping issues
if next_area.width < self.viewport_area.width {
    next_area.y = 0;
    self.backend.clear_region(ClearType::All)?;
}
```

That is an unconditional full-screen erase on any horizontal shrink, including
inline viewports. [#2666](https://github.com/ratatui/ratatui/issues/2666), filed
against exactly `ratatui 0.30.2 / ratatui-core 0.1.2`, reports the result:
dragging a window narrower leaves "a staircase of duplicated copies of the live
viewport in the scrollback — one (or more) stale copy per resize event", and
destroys committed rows on terminals that discard erased content. The
maintainers' own diagnosis in the fix PR is the general rule worth quoting:

> an inline viewport only owns the rows from its origin down. The rows above it
> were written by `insert_before`, which keeps no copy of them, so the
> application can never repaint them.

[PR #2670](https://github.com/ratatui/ratatui/pull/2670) fixes it, merged
2026-09-04 — **after 0.30.2, unreleased at time of writing.**

### 1.5 The CPR/stdin race

`compute_inline_size` opens with a blocking `crossterm::cursor::position()`.
[#2640](https://github.com/ratatui/ratatui/issues/2640) (open): "CPR queries
race the application's own `stdin` reader: when a `crossterm::event::EventStream`
is active, the `ESC[…R` reply is consumed as an input event and
`get_cursor_position()` deterministically times out."
[PR #2485](https://github.com/ratatui/ratatui/pull/2485) (in 0.30.2) removed
only the *fullscreen* resize query. Two sites remain reachable in 0.30.2:
**inline viewport construction/resize**, and `Terminal::clear()`
(`buffers.rs:148`).

### 1.6 User scrolling

Nothing in `ratatui-core-0.1.2` references user scroll position, scroll offset,
or scrollback position — zero hits. All rendering is absolute-screen-coordinate
`MoveTo`. If the user scrolls the emitted output out of view, behaviour is
entirely at the mercy of the emulator (most snap back to the bottom on output,
which is what makes it appear to work). No issue in the tracker covers this.

---

## 2. Does the buffer-diff model fit an append-to-scrollback stream?

**No.** It assumes a fixed rect that ratatui exclusively owns.

- `Terminal` holds `buffers: [Buffer; 2]`, both sized to `viewport_area`.
  `BufferDiff::new` (`ratatui-core-0.1.2/src/buffer/diff.rs:56`) hard-asserts
  it: `assert!(prev.area.x == next.area.x && prev.area.y == next.area.y && prev.area.width == next.area.width, ...)`.
  Only *height* may differ, and the iterator then uses the minimum.
- `swap_buffers()` resets the back buffer, hence the documented contract: "each
  render pass starts from an empty buffer: your callback is expected to fully
  redraw the viewport every time" — anything not rendered "is treated as empty
  and may clear previously drawn content."
- The diff emits **absolute cursor positioning**.
  `CrosstermBackend::draw` (`ratatui-crossterm-0.1.2/src/lib.rs:232`):

  ```rust
  // Move the cursor if the previous location was not (x - 1, y)
  if !matches!(last_pos, Some(p) if x == p.x + 1 && y == p.y) {
      queue!(self.writer, MoveTo(x, y))?;
  }
  ```

  `MoveTo` is CUP (`ESC[y+1;x+1H`) — absolute rows in the current screen frame.
  The moment a line scrolls off, its row number no longer identifies it, and
  ratatui has no addressing mode that can reach it.
- **There is no line-based or append-only diff mode, and no "first changed
  line" API.** The only public diff entry points are `Buffer::diff` and
  `Buffer::diff_iter`, both strictly per-cell over a same-x/y/width rect.
  (`insert_before` internally diffs a row range against an empty buffer to skip
  blanks and wide-continuations; that is private.)
- **`Buffer` is always `Rect`-shaped**: `pub area: Rect; pub content: Vec<Cell>`
  with `content.len() == area.area()`. No ragged/variable-height representation
  exists.
- If the terminal changes underneath ratatui, the diff goes stale and ratatui
  will not correct it. Its own docs (`terminal.rs:145-157`): "`Terminal::flush`
  only knows about Ratatui's two screen buffers… Ratatui may replay a diff
  computed for the old surface onto the new one." Recovery is `Terminal::clear()`
  or a resize.

### 2.1 No `render(width) -> Vec<Line>` contract, and no ANSI serialization

The only rendering contract is `Widget::render(self, area: Rect, buf: &mut Buffer)`
(`ratatui-core-0.1.2/src/widgets/widget.rs:73`) and its `StatefulWidget` /
`WidgetRef` variants. Grepping `ratatui-widgets-0.3.2/src` for `-> Vec<Line>`
or `-> Text<` returns **zero hits**: no widget can produce lines.

`impl fmt::Display for Line` concatenates span *content only* — no escape
sequences. `TestBackend`'s `Display` discards all style. A colour-aware variant
is [PR #2266](https://github.com/ratatui/ratatui/pull/2266), **open, unmerged**.
The only way to get styled bytes out of ratatui is to implement `Backend` over
your own writer (`CrosstermBackend::new(Vec::new())` works, since it is generic
over `W: Write`).

### 2.2 Styling is not reset at line ends

`CrosstermBackend::draw` tracks `fg`/`bg`/`underline_color`/`modifier` across
the **entire `draw()` call** and re-emits only on change. Exactly one reset is
emitted, at the end of the whole call:

```rust
return queue!(self.writer,
    SetForegroundColor(Reset), SetBackgroundColor(Reset),
    SetUnderlineColor(Reset), SetAttribute(CrosstermAttribute::Reset));
```

The emitted byte stream is therefore **not a sequence of self-contained
lines**. It cannot be sliced per-line, replayed, or appended to a scrollback
stream safely. (Each individual `insert_before` call *is* terminated cleanly,
since it calls `backend.draw` then `backend.flush`.) The brief's "reset all
styling at the end of every rendered line" is not something ratatui does.

---

## 3. Synchronized output (DECSET ?2026)

**ratatui: absent, in every version, and not on `main`.** Grepping the full
sources of `ratatui-0.30.2`, `ratatui-core-0.1.2`, `ratatui-crossterm-0.1.2`,
`ratatui-widgets-0.3.2` for `2026h`/`2026l`/`synchroni`/`SynchronizedUpdate`
returns zero hits outside English prose. The CHANGELOG (all ~10.5k lines, back
to 0.23.0) never mentions it. Code search on `main` and an issue/PR search both
come back empty. There is no feature flag, no backend method, and no open issue
tracking it. Tearing mitigation in ratatui is entirely "minimise bytes via the
diff" plus the `scrolling-regions` feature.

**crossterm: present since 0.26.1** (2023-02-26,
[PR #756](https://github.com/crossterm-rs/crossterm/pull/756); CHANGELOG: "Add
synchronized output/update control"). `src/terminal.rs:433-450`:

```rust
pub struct BeginSynchronizedUpdate;
impl Command for BeginSynchronizedUpdate {
    fn write_ansi(&self, f: &mut impl fmt::Write) -> fmt::Result {
        f.write_str(csi!("?2026h"))
    }
    #[cfg(windows)] fn is_ansi_code_supported(&self) -> bool { true }
}
```

`csi!` expands to `concat!("\x1B[", ...)`, so the emitted bytes are exactly
`\x1b[?2026h` / `\x1b[?2026l`. There is also a blanket-impl helper,
[`SynchronizedUpdate::sync_update`](https://docs.rs/crossterm/0.29.0/crossterm/trait.SynchronizedUpdate.html),
which queues BSU, runs a closure, then `execute`s ESU.

Two caveats:

- `sync_update`'s closure returns `T`, not `Result` — a **panic** inside it
  unwinds past `EndSynchronizedUpdate` and leaves the terminal frozen in BSU.
  Any BSU/ESU pairing needs a panic hook that emits `\x1b[?2026l`.
- **No capability detection.** `grep -rn 'DECRQM\|\$p' src/` → zero hits.
  [#934](https://github.com/crossterm-rs/crossterm/issues/934) ("Support for
  detection function for synchronized output", open since 2024-10) asks for it;
  the filer notes correctly that you cannot build it on top of crossterm,
  because `poll_internal` / `read_internal` / `InternalEvent` are all
  `pub(crate)` (the umbrella issue is
  [#763](https://github.com/crossterm-rs/crossterm/issues/763)).

The spec
([contour-terminal/contour, `docs/vt-extensions/synchronized-output.md`](https://github.com/contour-terminal/contour/blob/master/docs/vt-extensions/synchronized-output.md),
which supersedes the widely-linked gist) says detection is
`CSI ? 2026 $ p`, replying `CSI ? 2026 ; Pm $ y` with `Pm` 0 = not recognised,
2 = supported, 4 = permanently reset. It also warns: "So far there is no real
consensus on we[h]ether a timeout should be and, if so, for how long" — some
terminals auto-release BSU, so do not hold it long. Note that xterm's ctlseqs
does not document mode 2026 at all; xterm does not implement it.

Emitting unconditionally is the accepted practice — a well-formed but
unimplemented private mode is parsed and discarded by conforming terminals
(xterm ctlseqs distinguishes decoding errors from "unimplemented (but correctly
formatted) features"), and crossterm's own docs say the command "will do
nothing on terminals that do not support ANSI codes, or this specific
extension". There is no *normative* text mandating that, but the risk is low
and the practice universal.

### 3.1 A crossterm 0.29.0 bug that constrains any hand-rolled probe

[#1104](https://github.com/crossterm-rs/crossterm/issues/1104) (open, filed
2026-08-07 against 0.29.0). `src/event/sys/unix/parse.rs:180-184`:

```rust
b'?' => match buffer[buffer.len() - 1] {
    b'u' => return parse_csi_keyboard_enhancement_flags(buffer),
    b'c' => return parse_csi_primary_device_attributes(buffer),
    _ => None,        // Ok(None) == "incomplete, keep reading"
},
```

Any `CSI ? … <final>` crossterm cannot parse returns `Ok(None)`, the reader
treats that as "incomplete", never clears the buffer, and **every subsequent
keystroke is appended and discarded forever**. The issue's own repro is
literally the DECRPM reply to a `?2026` query. It is also triggered in the wild
by DEC mode 2031 (colour-scheme change notification, `CSI ? 997 ; 1 n`) —
supported by Ghostty, kitty, Contour, foot, VTE, and forwarded by tmux 3.6+ —
so on 0.29.0 this can fire without us querying anything, just from a
light/dark theme switch. No fix is merged or in the unreleased changelog.

Practical rule: emit BSU/ESU unconditionally; if detection is wanted, do the
raw `/dev/tty` write-and-read **before the event reader exists** (the pattern
crossterm itself uses for kitty flags: `const QUERY: &[u8] = b"\x1B[?u\x1B[c";`,
i.e. query + DA1 sentinel).

---

## 4. What else crossterm gives us for inline mode

crossterm's inline story is much better than ratatui's. Verified against the
`0.29` git tag.

Available and correct as-is:

- **Raw mode** is pure termios (`src/terminal/sys/unix.rs:107-140`). It does
  *not* touch the alternate screen, line wrap (DECAWM), scrollback, or mouse
  reporting. It *does* disable `OPOST`/`ONLCR` — crossterm's own docs: "New
  line character will not be processed therefore `println!` can't be used, use
  `write!` instead." **In raw mode you must emit `\r\n`.**
- **Nothing in crossterm requires the alternate screen.**
  `EnterAlternateScreen`/`LeaveAlternateScreen` are ordinary standalone
  `Command`s with no state coupling anywhere in the crate. Just don't call
  them.
- **Mouse is strictly opt-in.** `EnableMouseCapture` emits
  `CSI ?1000h ?1002h ?1003h ?1015h ?1006h`; omit it and native selection and
  wheel-scroll-to-scrollback stay intact. This is exactly the brief's default.
- **Scrollback-safe erase**: `Clear(CurrentLine)` = `CSI 2K`,
  `Clear(UntilNewLine)` = `CSI K`, `Clear(FromCursorDown)` = `CSI J`. All three
  are safe. `Clear(All)` = `CSI 2J` blanks the whole viewport including output
  we did not write. **`Clear(Purge)` = `CSI 3J` erases saved lines — it
  destroys scrollback.** Never use it.
- **Full SGR reset in one command.** `ResetColor` and
  `SetAttribute(Attribute::Reset)` emit *identical* bytes, `\x1b[0m`
  (`src/style.rs:483-487`; `Attribute::Reset = 0`). The name `ResetColor` is a
  misnomer — it resets colours *and* bold/dim/italic/underline/reverse/hidden/
  strikethrough/underline-colour. For the brief's "reset all styling at the end
  of every rendered line", one 4-byte `ResetColor` is sufficient and correct.
- Events, resize (`Event::Resize` via SIGWINCH), bracketed paste
  (`EnableBracketedPaste`, 0.25.0, `bracketed-paste` default feature), kitty
  keyboard (`Push`/`PopKeyboardEnhancementFlags`, 0.25.0;
  `supports_keyboard_enhancement` 0.26.0; `query_keyboard_enhancement_flags`
  0.29.0). Kitty's own protocol doc sanctions the main-screen pattern: "Emit
  the escape code `CSI > 1 u` at application startup **if using the main
  screen**".
- Async events via `EventStream`, behind the **non-default** `event-stream`
  feature.
- `SetTitle` (OSC 0 + BEL). No title save/restore — there is no OSC 22/23 title
  stack.
- `DisableLineWrap`/`EnableLineWrap` (DECAWM `CSI ?7l`/`?7h`).
- `ScrollUp(n)`/`ScrollDown(n)` (SU/SD). On the main screen, lines scrolled off
  the top go into scrollback.

Gaps and hazards:

- **No scroll region.** `grep -rni 'scroll.region\|DECSTBM\|margin' src/` →
  zero hits. If a fixed bottom dock with native scrollback above is wanted,
  DECSTBM (`CSI {top};{bot}r`) is emitted by hand.
- **`SavePosition`/`RestorePosition` are the wrong tool inline.** They are
  DECSC/DECRC, which save a *viewport-relative* row; if the terminal scrolls in
  between — the normal case for an inline app — the restore lands on the wrong
  line. [#673](https://github.com/crossterm-rs/crossterm/issues/673), open since
  2022, with a repro that differs only by one `\n`. Track your own line count
  and use `MoveUp(n)` + `MoveToColumn(0)`.
- **`cursor::position()` is event-loop-hostile.** It emits `ESC[6n`, blocks on
  the shared global `INTERNAL_EVENT_READER` with a 2000 ms timeout, and toggles
  raw mode globally if it is not already on. Its own doc: "On unix systems,
  this function will block and possibly time out while `crossterm::event::read`
  or `crossterm::event::poll` are being called." Open bugs:
  [#963](https://github.com/crossterm-rs/crossterm/issues/963) (unexplained
  timeouts), [#828](https://github.com/crossterm-rs/crossterm/issues/828)
  (freezes on macOS with piped stdin),
  [#919](https://github.com/crossterm-rs/crossterm/issues/919) (fails with
  piped stdout), [#1095](https://github.com/crossterm-rs/crossterm/issues/1095)
  (Windows: buffer-absolute row after scroll),
  [#459](https://github.com/crossterm-rs/crossterm/issues/459). Best-effort at
  startup only. This is the same call ratatui makes on every inline resize
  (§1.5).
- **crossterm does no buffering of its own.** `queue!` writes into whatever
  `io::Write` you pass; `std::io::stdout()` is a `LineWriter`, so every `\n`
  costs a syscall — including inside a BSU/ESU block. Wrap in
  `BufWriter::new(io::stdout().lock())` and flush once per frame.
- **`NO_COLOR` bug in 0.29.0.** When colour is disabled, `Colored`'s `Display`
  returns empty, but `SetForegroundColor` still writes `csi!("{}m")` —
  producing a bare `\x1b[m`, which terminals treat as `\x1b[0m`, **a full
  attribute reset**. Every colour command silently becomes "reset everything".
  Fixed only in the *unreleased* CHANGELOG section ("Fix color commands
  emitting a bare `CSI m` when colors are disabled via `NO_COLOR`… Affects
  `SetForegroundColor`, `SetBackgroundColor`, `SetUnderlineColor`, and
  `SetColors`"). Mitigate at our own render layer.
- Other open issues worth knowing:
  [#993](https://github.com/crossterm-rs/crossterm/issues/993) (escape
  sequences split across two `read()` calls can misparse — likelier over ssh
  and tmux, exactly where inline apps live),
  [#964](https://github.com/crossterm-rs/crossterm/issues/964) (events stuck
  when a thread sleeps — relevant to timer-driven redraw),
  [#839](https://github.com/crossterm-rs/crossterm/issues/839)
  (`poll(Duration::ZERO)` with `use-dev-tty`).

---

## 5. ANSI-aware, grapheme-correct width utilities

The brief asks for three: `visible_width`, `truncate_to_width`, and
`wrap_preserving_ansi`. Findings here were verified by **executing** test
programs against the crates, not by reading prose — which mattered, because two
crates' claims turned out to be false.

### 5.1 The premise correction: `unicode-width` is already grapheme-aware

Since 0.1.14/0.2.0 (both 2024-09-19), `UnicodeWidthStr::width` applies
*string-level* rules that override the naive char sum. Its own docs: "In the
following cases, the width of a string differs from the sum of the widths of
its constituent characters."

| Input | `UnicodeWidthStr::width` | char-sum | `textwrap` | `ansi-width` | `console` 0.16.4 |
| --- | --- | --- | --- | --- | --- |
| `👨‍🦰` (ZWJ) | **2** | 4 | 4 | 4 | **2** |
| `👨‍👩‍👧‍👦` | **2** | 8 | 8 | 8 | **2** |
| `👍🏽` (skin tone) | **2** | 4 | 4 | 4 | **2** |
| `⁉️` (VS16) | **2** | 1 | 1 | 1 | **2** |
| `1️⃣` (keycap) | **2** | 1 | 1 | 1 | **2** |

So `unicode-segmentation` is **not** needed for correct emoji width — only for
finding safe *cut points*. It provides no width function at all; it is pure
[UAX #29](https://www.unicode.org/reports/tr29/) segmentation.

Known residual limitation, acknowledged by
[UAX #11](https://www.unicode.org/reports/tr11/) itself: Devanagari `क्षि`
measures 3 though terminals render ~1–2. The spec says East_Asian_Width "is not
intended for use by modern terminal emulators without appropriate tailoring."
That is a Unicode-level problem, not a crate-selection one.

### 5.2 Every candidate fails on either OSC or graphemes — never neither

| Input | `textwrap` | `ansi-width` | `console` 0.16.4 | `console` main | correct |
| --- | --- | --- | --- | --- | --- |
| `\x1b[31mCafe\x1b[0m` | 4 | 4 | 4 | 4 | 4 |
| OSC 8 hyperlink (ST) | 4 | 4 | **36** | 4 | 4 |
| OSC 8 hyperlink (BEL) | 4 | 4 | **34** | 4 | 4 |
| `\x1b]0;title\x07abc` | 3 | 3 | **13** | 3 | 3 |
| SGR + `👨‍🦰` | **4** | **4** | 2 | 2 | 2 |

`textwrap` 0.16.2 and `ansi-width` 0.1.0 parse OSC correctly (both terminators)
but sum `UnicodeWidthChar::width` per char, losing the string-level emoji
rules. `console` 0.16.4 uses `UnicodeWidthStr::width` per segment
(grapheme-correct) but does not recognise OSC at all — `strip_ansi_codes`
returns an OSC 8 string verbatim.

`console` fixed the OSC case in commit "ansi: strip OSC and DCS sequences"
(2026-08-02, [issue #280](https://github.com/console-rs/console/issues/280));
verified against git `main`. **But 0.16.5 was tagged on GitHub 2026-08-13 and
never published to crates.io** — the newest installable `console` still has the
bug. Also note `ansi-width` depends on `unicode-width` `^0.1.11`, so it can
never pick up the 0.2.x string-level rules.

### 5.3 Truncation and wrapping

- **`unicode-truncate` 3.0.0** — grapheme-correct (`"ab👨‍🦰cd".unicode_truncate(4)`
  → `"ab👨‍🦰"`), **zero ANSI awareness**:
  `"\x1b[31mHello World\x1b[0m".unicode_truncate(5)` returns `"\x1b[31m"` — it
  counted the escape bytes as five columns.
- **`console::truncate_str`** — preserves SGR well (appends trailing codes) but
  **splits grapheme clusters** (`"ab👨‍🦰cd"` → `"ab👨"`, a bare man emoji), and on
  0.16.4 cuts *inside* OSC sequences (`"\x1b]8;;h"` — the dangling-escape
  failure mode). `main` fixes the OSC case; **grapheme splitting persists.**
- **`textwrap::wrap`** — treats ANSI as zero width, handles CSI and OSC with
  both terminators, but does **not** re-emit state across lines:
  `\x1b[1;31maaa bbb ccc ddd\x1b[0m` at width 7 →
  `["\x1b[1;31maaa bbb", "ccc ddd\x1b[0m"]`. Line 0 is never closed; line 1 is
  never opened. No ANSI feature flag exists.
- **`ansi-str` 0.9.0** — the only crate that genuinely re-emits SGR state.
  `"\x1b[1;31mHello\x1b[32mWorld\x1b[0m".ansi_cut(3..8)` →
  `"\x1b[1;31mlo\x1b[32mWor\x1b[22m\x1b[39m"`: prefix state re-emitted,
  granular closers appended. But it is **byte-indexed, not width-indexed**, and
  **panics** ("One of indexes are not on a UTF-8 code point boundary") on any
  cut landing mid-char. It also opens an OSC 8 link on cut without closing it.
  Its own docs: "The library doesn't guarantee to keep style of usage of ansi
  sequences." Useful as a reference for closer-code mapping, not as a drop-in.
- **`wrap-ansi` 0.1.0** advertises exactly what we want ("preserving ANSI
  escape sequences, colors, styles, and hyperlinks") and is **abandoned and
  broken**. Repo created *and* last pushed 2025-09-08, 4 commits in ~15
  minutes, 0 stars, 0 forks; part of a 4-crate family all published the same
  day with near-identical download counts and no GitHub traction. Confirmed
  bugs: multi-parameter SGR (`\x1b[1;31m`) silently loses all state tracking;
  underline `\x1b[4m` is closed with `\x1b[39m` (default *foreground*) instead
  of `\x1b[24m`; OSC 8 is not re-opened per line despite the claim.
- **`unicode-display-width` 0.3.0** — last released 2023-11-15, Unicode 15.1,
  no ANSI handling, superseded by `unicode-width` 0.2.x.

### 5.4 `anstyle-parse` is the right primitive for the hand-rolled part

`anstyle-parse` 1.0.0 (rust-cli/clap org, 171M recent downloads) is a Paul
Williams VTE state machine. Verified by implementing `Perform` against it:

- `print(char)` yields **only printable text** → accumulate and call
  `UnicodeWidthStr::width` on the buffer (not per char, or the string-level
  rules are lost).
- `csi_dispatch` exposes SGR params structurally, including sub-parameters
  (`\x1b[38:2:255:0:0m` → `[[38, 2, 255, 0, 0]]`).
- `osc_dispatch(params, bell_terminated: bool)` — splits on `;` and **tells you
  which terminator was used**, which is exactly what
  [OSC 8](https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda)
  needs (ST per ECMA-48 §8.3.89, but BEL is common).
- Truncated sequences (`"abc\x1b[31"`, `"abc\x1b]8;;http://x"`) are absorbed
  without panic or spurious output.

One gotcha: with ST-terminated OSC it fires `osc_dispatch` *and* a separate
`esc_dispatch('\\')`, so a re-emitter must reconstruct the terminator itself.
It provides no SGR semantics — map params to `anstyle::Style` yourself.

---

## 6. Terminal graphics for the image component

### 6.1 Protocol choice determines the inline redraw hazard

| Protocol | Cell footprint declarable | Cursor control | Deletion on redraw |
| --- | --- | --- | --- |
| kitty real placement (`a=T`/`a=p`) | yes (`c`, `r`) | `C=1` = don't move | **explicit `a=d` required** |
| kitty unicode placeholders (`U=1`) | yes | it is text | **none — it is text** |
| iTerm2 OSC 1337 | yes (`width=N`, `height=N` in cells) | WezTerm-only `doNotMoveCursor=1` | no primitive exists |
| Sixel | **no — pixels only** | mode-dependent | no primitive exists |

The [kitty spec](https://sw.kovidgoyal.net/kitty/graphics-protocol/) is explicit
that ordinary erasure does not remove a real placement:

> The clear screen escape code (usually `<ESC>[2J`) should also clear all
> images… **The other commands to erase text must have no effect on graphics.
> The dedicated delete graphics commands must be used for those.**

So `EL`, non-`2J` `ED`, and plain overprinting leave the image up — and with
default `z >= 0` it composites *over* the text. A differential redraw of the
bottom N lines would paint text underneath a still-visible image. The delete
form matching a line-range redraw is `<ESC>_Ga=d,d=y,y=<row><ESC>\` — "Delete
all placements that intersect the specified row".

**Unicode placeholders (kitty ≥ 0.28.0) dissolve that entire problem.** From
the same spec:

> Since this character is just normal text, Unicode aware application will move
> it around as needed when they redraw their screens, thereby automatically
> moving the displayed image as well, even though they know nothing about the
> graphics protocol.

> Real images displayed on top of Unicode placeholders are not considered
> placements from the protocol perspective. They cannot be manipulated using
> graphics commands, instead they should be moved, deleted, or modified by
> manipulating the underlying Unicode placeholder as normal text.

The mechanism: `U+10EEEE` cells carrying the image id in the **foreground
colour**, row/column encoded as combining diacritics (297-entry table), placement
id in the **underline colour**. That converts "terminal-side graphics state I
must delete and re-place on every redraw" into "text in my buffer" — which is
what an inline, scrollback-committed renderer needs.

kitty also guarantees images scroll with text and survive into scrollback:
"When scrolling the screen (such as when using index cursor movement commands,
or scrolling through the history buffer), images must be scrolled along with
text." Deletion of image *data* is refused while "the image is not referenced
elsewhere, such as in the scrollback buffer." One unavoidable consequence: the
storage quota is 320 MB per buffer with LRU eviction ("When adding a new image,
if the total size exceeds the quota, the terminal emulator should delete older
images to make space for the new one"), so a long session will eventually see
old scrollback images evicted. That is not fixable.

Sixel and iTerm2 have **no deletion primitive at all**, so for those the only
strategy is prevention: never redraw over an image region.

### 6.2 Cell size: no single reliable mechanism

kitty's own spec recommends `TIOCGWINSZ` and immediately admits it is
unreliable:

> **Note that some terminals return `0` for the width and height values.** Such
> terminals should be modified to return the correct values. Examples of
> terminals that return correct values: `kitty, xterm`

crossterm exposes it as
[`window_size()`](https://docs.rs/crossterm/0.29.0/crossterm/terminal/fn.window_size.html)
→ `WindowSize { rows, columns, width, height }` where `width`/`height` are
pixels. Its own doc comment:

> The width and height in pixels may not be reliably implemented or default to
> 0. For unix, <https://man7.org/linux/man-pages/man4/tty_ioctl.4.html>
> documents them as "unused". For windows it is not implemented.

Windows native returns `ErrorKind::Unsupported`; Windows Terminal + WSL returns
`Ok(WindowSize { rows: 48, columns: 208, width: 0, height: 0 })`
([#1021](https://github.com/crossterm-rs/crossterm/issues/1021), root cause
microsoft/terminal#8581).

The escape-sequence route is xterm XTWINOPS
([ctlseqs](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)):
`CSI 14 t` → `CSI 4 ; height ; width t` (text area in pixels), `CSI 16 t` →
`CSI 6 ; height ; width t` (cell size in pixels). **Height precedes width.**
These "may be disabled using the `allowWindowOps` resource", so even xterm can
refuse. **crossterm has neither** — `grep -rn '14t\|16t\|18t' src/` → zero hits.
The kitty protocol has no cell-size query of its own (`a=q` probes protocol
support only, not geometry).

So a fallback chain is mandatory. `ratatui-image` 11.0.8 implements the only
complete one found: enter raw mode → write one batched query (kitty `a=q` +
`CSI c` DA1 for Sixel + `CSI 16 t` + optional OSC 11 + **`CSI 5 n` DSR as a
sentinel so you never hang**) → read with a timeout thread → fall back to
`tcgetwinsize` with explicit zero-rejection
(`if x == 0 || y == 0 || cols == 0 || rows == 0 { return None; }`) → env hints
(`TERM_PROGRAM`, `WEZTERM_EXECUTABLE`, `KONSOLE_VERSION`, `KITTY_WINDOW_ID`,
`TMUX`) → hard fallback `FontSize::new(10, 20)`. On Windows the ioctl fallback
returns `None` unconditionally, with the note that ConPTY "does not reliably
deliver the responses to the child process".

### 6.3 Crate landscape

| Crate | Version | Released | Status |
| --- | --- | --- | --- |
| `ratatui-image` | 11.0.8 | 2026-09-04 | actively maintained, screenshot CI |
| `image` | 0.25.10 | 2026-03-10 | active; decode + resize |
| `icy_sixel` | 0.7.0 | 2026-09-06 | active, pure Rust, no libsixel C dep |
| `viuer` | 0.11.0 | 2025-12-09 | maintained but slower; docs.rs build failed for 0.11.0 |
| `sixel-rs` / `sixel-sys` | 0.5.0 | 2025 | requires libsixel C library |
| `sixel-bytes` | 0.2.3 | **2023-10-12** | stale; superseded by `icy_sixel` in its own author's project |

**There is no dedicated, maintained kitty-graphics-protocol crate.** kitty
support ships inside `ratatui-image` (`src/protocol/kitty.rs`) and `viuer`.

Critically for us: **`ratatui-image`'s protocol backends do not assume the
alternate screen.** No alt-screen or `1049` reference anywhere in `src/`, and
all three graphics backends use only *relative* cursor motion
(`\x1b[s` / `\x1b[u` / CUF / CUD) — no absolute `MoveTo`. Its doc warning
"should be called after entering alternate screen but before reading terminal
events" is really about stdin exclusivity and query-noise suppression, not an
alt-screen dependency.

What they *do* assume is ratatui's `Buffer`: each backend writes the escape
sequence into the symbol of one cell and marks the rest of the area
`CellDiffOption::Skip` so ratatui's diff never overwrites the image. That
prevention scheme only exists because ratatui owns the diff. **If our renderer
is not ratatui's `Terminal`, the widgets are unusable and we would port the
encoders (which are self-contained) rather than the widgets.**

`viuer` does **no** cell-size detection at all — it hardcodes a 1:2 halfblock
assumption (`let bound_height = 2 * bound_height;`) even for kitty/iTerm2/Sixel
— and defaults `absolute_offset: true`, which issues
`execute!(stdout, MoveTo(config.x, config.y))`. Inline-hostile unless
explicitly configured otherwise.

### 6.4 Terminal support, and tmux

From `ratatui-image` 11.0.8's tested compatibility matrix (screenshot CI):
working — xterm (Sixel, needs `-ti 340`), foot (Sixel), kitty (kitty proto,
"requires Kitty 0.28.0 or later"), WezTerm (iTerm2; "Also would support Sixel
and Kitty, but only iTerm2 actually works bug-free"), Ghostty (kitty with
unicode placeholders), iTerm2, mlterm (Sixel, "quite slow but no glitches"),
Rio (iTerm2). Broken — Konsole ("Not really fixed in 24.12"), Alacritty (fork
only, "does not clear graphics"), Contour, ctx, Warp ("iTerm2 does not clear,
Kitty unicode-placeholders part not implemented").

VS Code's integrated terminal supports "either the Sixel or iTerm inline image
protocols" behind `terminal.integrated.enableImages`, **disabled by default**,
with documented limitations (no persistence across reloads, no animated GIFs).
No kitty protocol.

tmux requires the pane option `allow-passthrough` (off by default), and every
`ESC` in the payload must be doubled inside the `\ePtmux;…\e\\` wrapper. kitty's
spec names tmux as a target of the unicode-placeholder design precisely because
placeholders are ordinary text.

---

## 7. Verdict

Pinned to **ratatui 0.30.2 / ratatui-core 0.1.2 / crossterm 0.29.0**.

| Borrow as-is | Must be hand-rolled (with justification) |
| --- | --- |
| **crossterm raw mode** (`enable_raw_mode`/`disable_raw_mode`) — pure termios, touches neither the alt screen nor scrollback. | **Line-addressed differential redraw.** ratatui's only diff is per-cell over a fixed `Rect` it owns, with `BufferDiff::new` asserting identical `x`/`y`/`width`, and it emits absolute CUP per changed run. Nothing public computes a first-changed-line, and `Buffer` is always `Rect`-shaped. An append-to-scrollback stream cannot be addressed that way. |
| **crossterm relative cursor motion** (`MoveUp`/`MoveDown`/`MoveToColumn`, `Hide`/`Show`) and `SetCursorStyle`. | **The `render(width) -> Vec<Line>` component contract.** ratatui's only contract is `Widget::render(self, area: Rect, buf: &mut Buffer)`; grepping `ratatui-widgets-0.3.2` for `-> Vec<Line>` returns zero hits. No widget can produce lines. |
| **crossterm scrollback-safe erase**: `Clear(CurrentLine)`, `Clear(UntilNewLine)`, `Clear(FromCursorDown)`. | **Per-line ANSI serialization with end-of-line style reset.** `CrosstermBackend::draw` tracks style across the whole `draw()` call and resets once at the end, so its output is not a sequence of self-contained lines. No public "to ANSI" API exists (a colour-aware `TestBackend` `Display` is [PR #2266](https://github.com/ratatui/ratatui/pull/2266), open). We implement `Backend` over our own writer, or emit SGR directly. |
| **crossterm synchronized output**: `BeginSynchronizedUpdate`/`EndSynchronizedUpdate` emit exactly `\x1b[?2026h`/`\x1b[?2026l`, since 0.26.1. **ratatui never emits these — the framing must come from crossterm or from us.** | **Inline anchor bookkeeping.** DECSC/DECRC (`SavePosition`/`RestorePosition`) save a viewport-relative row and break the instant the terminal scrolls ([#673](https://github.com/crossterm-rs/crossterm/issues/673), open since 2022) — the normal case for an inline app. We track emitted line counts ourselves. |
| **crossterm full SGR reset**: `ResetColor` == `SetAttribute(Attribute::Reset)` == `\x1b[0m`. Satisfies "reset styling at every line end" in 4 bytes; no per-attribute unsetting needed. | **BSU/ESU capability detection**, if wanted. crossterm has no DECRQM support and cannot grow one on top of its own reader (`poll_internal`/`read_internal` are `pub(crate)` — [#934](https://github.com/crossterm-rs/crossterm/issues/934), [#763](https://github.com/crossterm-rs/crossterm/issues/763)). Worse, on 0.29.0 feeding a `CSI ? … $y` reply into crossterm's parser **permanently wedges input** ([#1104](https://github.com/crossterm-rs/crossterm/issues/1104)). Any probe is a raw `/dev/tty` round-trip before the event reader exists. |
| **crossterm events, resize, bracketed paste, kitty keyboard** — all work on the main screen with no mouse capture; mouse is strictly opt-in, so native selection and wheel-scroll survive by simply not calling `EnableMouseCapture`. | **A BSU/ESU panic guard.** `sync_update`'s closure returns `T`, not `Result`; a panic unwinds past ESU and leaves the terminal frozen mid-update. |
| **crossterm `DisableLineWrap`/`EnableLineWrap`, `ScrollUp`/`ScrollDown`, `SetTitle`.** | **DECSTBM scroll regions**, if a fixed bottom dock is wanted. `grep -rni 'DECSTBM\|scroll.region' crossterm/src` → zero hits. Emit `\x1b[{top};{bot}r` directly. |
| **`ratatui` `Line`/`Span`/`Style`/`Text` as a *formatting vocabulary*** — data types and layout maths only, no `Terminal`, no `Buffer` diff. | **`visible_width`** (~30 lines). No maintained crate is both OSC-aware and grapheme-correct: `textwrap`/`ansi-width` parse OSC but sum per-char widths (`👨‍🦰` → 4); `console` 0.16.4 is grapheme-correct but scores an OSC 8 hyperlink at 36. `console`'s fix is tagged but **unpublished**. Drive `anstyle-parse`, accumulate `print()` chars, call `UnicodeWidthStr::width` on the buffer. |
| **`unicode-width` 0.2.2** — `UnicodeWidthStr::width` already applies string-level ZWJ/VS16/skin-tone rules; **no grapheme pre-pass needed for width.** | **`truncate_to_width`.** `unicode-truncate` 3.0.0 is grapheme-correct and ANSI-blind (`"\x1b[31mHello"` truncated to 5 returns just `"\x1b[31m"`); `console::truncate_str` is ANSI-aware but splits grapheme clusters *in every version including `main`*. No crate does both. |
| **`unicode-segmentation` 1.13.3** — for cut points only. It has no width function. | **`wrap_preserving_ansi`.** Genuinely absent. `textwrap` emits no state across the boundary; `wrap-ansi` 0.1.0 claims to and is abandoned (4 commits in 15 minutes, 0 stars) and breaks on any multi-parameter SGR and on OSC 8; `ansi-str::ansi_cut` has the right idea but is byte-indexed and panics mid-char. Nothing maintained re-emits active SGR at the start of each wrapped line. |
| **`anstyle-parse` 1.0.0** — a Williams VTE state machine that yields printable text separately, exposes SGR sub-parameters, and reports OSC terminator kind. The correct tokenizer under all three utilities. **`anstyle` 1.0.14** to represent tracked style. | **OSC 8 hyperlink state tracking**, separately from SGR. It needs re-opening per wrapped line and an explicit `\x1b]8;;\x1b\\` close. Every crate tested gets this wrong. Read `ansi-str` 0.9.0's closer mapping (bold→22, fg→39, bg→49) rather than emitting a blanket `\x1b[0m` that would clobber caller-set style. |
| **`image` 0.25.10** (decode/resize) and **`icy_sixel` 0.7.0** (pure-Rust Sixel encode; prefer over `sixel-rs`/`sixel-sys`, which need libsixel; do not use `sixel-bytes`, stale since 2023). | **Inline layout accounting for images.** No crate tracks "how many scrollback rows have I emitted and where did the image land". `ratatui-image` gives sized `Protocol`s; the caller owns the `Rect`. The cell-cap policy (`min(desired_rows, max_rows)` → derive columns from aspect ratio) is ours. |
| **`ratatui-image` 11.0.8's cell-size detection** (`Picker::from_query_stdio` + `font_size()`) — the only complete chain: batched `CSI 16 t` + kitty `a=q` + DA1 + `CSI 5 n` sentinel + timeout thread + zero-rejecting `tcgetwinsize` + env hints + Windows ConPTY handling. crossterm has no `CSI 14t`/`16t`, and its `window_size()` pixel fields are 0 or `Unsupported` on Windows/WSL. | **Redraw/deletion policy for graphics**, if real kitty placements are ever used. The kitty spec: text-erase commands "must have no effect on graphics" — a bottom-N-lines redraw must emit `a=d,d=y,y=<row>` first. `ratatui-image` never emits `a=d` because its `CellDiffOption::Skip` prevention scheme depends on ratatui owning the diff. |
| **`ratatui-image`'s kitty unicode-placeholder encoder and tmux `\ePtmux;` ESC-doubling wrapper** — spec-exact, fiddly, and encodes per-terminal blacklists. All backends use only relative cursor motion, so they are not alt-screen-bound. | **A `NO_COLOR` gate at our render layer.** crossterm 0.29.0 emits a bare `\x1b[m` for colour commands when colour is disabled, which terminals read as a full attribute reset. Fixed only in the unreleased CHANGELOG. |

### The one structural conclusion

`ratatui` can be borrowed as a **formatting library** (`Line`, `Span`, `Style`,
`Text`, and the widget layout maths). It cannot be borrowed as the **renderer**
for scrollback mode: `Terminal` + `Buffer` + `BufferDiff` model a fixed
rectangle addressed by absolute CUP, `insert_before` is a write-once firehose
that keeps no copy of what it emitted, and the resize path in 0.30.2 issues a
full-screen `ClearType::All` on horizontal shrink that visibly corrupts
scrollback ([#2666](https://github.com/ratatui/ratatui/issues/2666); fix merged
2026-09-04, unreleased).

`crossterm`, by contrast, is a near-complete fit: no alt-screen coupling
anywhere, mouse capture opt-in, correct DECSET 2026 framing shipped, and
`ResetColor` is exactly the per-line reset the brief asks for. The hand-rolled
surface concentrates in three places — the line-addressed diff, the ANSI-aware
text utilities, and image layout accounting — each because the primary sources
show the gap is real, not because a crate was overlooked.

### Open items this note does not settle

- Whether `console` 0.16.5 ever reaches crates.io (it would supply a valid
  `visible_width`, though still not truncation).
- Whether `ratatui-image`'s widgets work inside `Terminal::insert_before`'s
  `Buffer` — plausible from the source, undocumented and untested upstream.
- Whether crossterm's numbered-CSI parse path drops `CSI 16 t` replies cleanly
  rather than wedging like the `CSI ?` path in #1104. Read from
  `parse.rs:185-194`; worth a unit test before relying on it.
