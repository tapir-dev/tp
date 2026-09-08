# Both clipboard paths, ordered by which one can report failure

Copying from fullscreen writes the system clipboard through `arboard` **and**
emits OSC 52, always, in that order — and reports only what was attempted, never
what succeeded. Neither path can be detected in advance and only one of them can
fail out loud, which is what fixes the order.

## Why neither path can be probed

OSC 52 write has no acknowledgement of any kind: none is defined in `ctlseqs`,
and none exists in any implementation. kitty and Ghostty say so in source
comments — "OSC 52 has no way to report errors to the client", "a denied write
simply doesn't happen". Writing a sentinel and reading it back with the `?` query
does not substitute, because read is gated separately from write and is the more
restricted of the two: in tmux, zellij, wezterm, alacritty and Windows Terminal
the default is write-yes, read-no, so silence proves nothing.

The terminfo `Ms` capability is not an answer either. `st` advertises it without
implementing it, and zellij answers XTGETTCAP `Ms` unconditionally — claiming
support regardless of whether the outer terminal can honour it. Reading `Ms` is
the same disease as the `TERM`-keyed capability tables that ADR-0002's ticket
banned, and it is banned here for the same reason.

## Why the order is forced rather than preferred

`arboard` returns `Err` immediately when there is no display server — it does not
panic and does not hang. That is a real signal. OSC 52 produces no signal ever.
So the path whose result means something runs first, and the path that can only
be hoped at runs second and cannot invalidate the first.

Doing both is cheap and covers the cross cases: over SSH with X11 forwarding the
crate succeeds but sets the wrong machine's clipboard, while under `tmux` with
`set-clipboard on` both paths land the same bytes, so they cannot disagree.

## Consequences

- **The status message names the attempt, not the outcome.** "Copied 412 bytes
  (system + OSC 52)" is honest; "Copied" is a claim we cannot support.
- **The OSC 52 payload is capped at 16 KB for the whole sequence**, the envelope
  that clears every implementation surveyed. Over the cap the OSC 52 write is
  skipped and reported, never truncated — half a selection in the clipboard is
  worse than none.
- **`tp` holds one `Clipboard` for the life of the process and never calls
  `.wait()`.** X11 and Wayland keep clipboard contents in the owning process, so
  a short-lived writer loses them; a long-lived one serves requests as a side
  effect of still running. `.wait()` exists to simulate that for short-lived
  processes and, contrary to `arboard`'s README but per its source, unblocks on
  ownership loss rather than on paste.
- **`Drop` must run inside the idempotent teardown**, because that `Drop` is
  where the 100 ms `CLIPBOARD_MANAGER` handover happens. A signal path that
  skips it loses the user's last copy silently, which `arboard` reports only as
  a `warn!`.
- **Some users have no working path at all** — GNOME Terminal over SSH has
  neither a display server nor OSC 52, and GNU screen has never implemented OSC
  52 in any version. They get an explicit action that opens the selection as
  plain unwrapped text in an overlay, for the terminal's own selection to take.
- **The `clipboard` axis is named `all | system | osc52 | off`, not `auto`.**
  `all` says what the code does; `auto` would imply a detection that provably
  cannot exist.

Facts above are from `docs/research/clipboard-osc52.md` on branch
`research/clipboard-osc52`, which marks each claim verified or inferred.
