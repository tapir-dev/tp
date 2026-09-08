# The handshake reopens for the appearance query

The start-up handshake gains three sequences ahead of its sentinel: `CSI ? 2031 h`
to enable colour-scheme update notifications, `CSI ? 996 n` to ask the terminal
whether it is light or dark, and `OSC 11 ; ? BEL` to ask for its background
colour. The batch is still one write, still ends in DA1, and still runs under one
budget.

This overturns a line that was recorded as settled: the decision on `auto`
defaults stated that the handshake batch **does not reopen**. It reopens, on the
reasoning that decision itself supplied.

## Why the earlier refusal does not reach this query

Two rules were fixed when `auto` was defined, and neither one covers the
appearance query.

The first was a cost test: a query whose answer the ladder discards in every case
but one is ceremony, not a measurement. The truecolor probe failed it because the
ladder only ever promotes, so the answer changed nothing except on a single
terminal that already approximated for itself. The appearance query is the
opposite case. Its answer is never discarded, because there is no other source
for light or dark. Nothing else in the product can supply it, and the ladder has
no direction to promote in — light and dark are not ordered.

The second was that reading silence as a negative would deny a capability that
terminals demonstrably have. That rule is about silence, and this query does not
read silence. Sequences are processed in order, so placing the appearance query
ahead of the sentinel makes the sentinel's reply a positive statement about it:
if DA1 comes back first, the terminal did not answer, and it did not answer
because it cannot. There is no timeout in that judgement and no terminal is
denied anything it can do.

So the two rules that closed the batch are the two rules that admit this query.
Reopening the batch on any weaker ground would be the drift both rules exist to
prevent, which is why the argument is written down rather than the batch simply
being edited.

## Why it costs nothing to add

The batch already ends in DA1 as its sentinel, already runs under one budget over
the whole write, and already parses its own replies on a raw descriptor before
any event reader exists. The appearance query adds no round trip, no second
budget and no second wait. The technique that makes the query unambiguous is the
sentinel doing a second job it was already in position to do.

## Consequences

- **The sentinel now discharges two obligations.** It ends the batch, and it
  tells each question in the batch apart from a question that was never going to
  be answered. That second job is what keeps this query inside the ban on
  reading silence as a negative.
- **Two multiplexers are handled without a terminal-identity table.** Under
  `screen` the query is forwarded to the outer terminal and its reply arrives out
  of order, after the sentinel; the sentinel therefore fires, the answer is taken
  as unavailable, and the late reply is consumed and discarded by the string
  sequence patch the fork already carries. Under `tmux` the multiplexer answers
  from its own record of the outer terminal rather than forwarding, and that
  answer is accepted as the terminal's. Neither case needs a lookup keyed on
  `TERM`, which is what keeps the ban on those tables intact.
- **The reply is parsed defensively, and the query is terminated with `BEL`.** A
  terminal may reply with `BEL`, with `ST`, or — on one widely deployed emulator
  whose fix is unreleased — with a bare `ESC`, which hangs a reader waiting for
  the second byte of `ST`. Asking with `BEL` avoids that hang, but does not
  determine the answer's terminator: several terminals always reply with `ST`
  whatever they were asked with. Channels carry one to four hex digits and a
  fourth channel may be present.
- **The colour is measured; the cut is declared.** `OSC 11` returns a colour, not
  an appearance. The threshold that turns one into the other is a stated policy
  on the reference page, not a property of the terminal, and saying so is what
  stops the page from claiming to have measured "dark".
- **One emulator can report a background that is not the one it renders.** The
  override exists for that, and the page names the case rather than leaving it to
  be discovered.
- **Teardown grows a sequence.** Notifications enabled by `CSI ? 2031 h` must be
  disabled on exit, or they continue to arrive after the process is gone and land
  in the shell.

## Note on numbering

ADR numbers collide across the unmerged wayfinder branches. This file takes
`0015` as the next free number on `main`, on the same assumption the other
branches have made: numbers are reconciled when the branches land.
