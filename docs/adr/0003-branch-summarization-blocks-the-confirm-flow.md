# Branch summarization blocks the confirm flow

Moving the leaf in the session tree browser is an in-memory cursor operation, so
it costs nothing and is recorded only by the next append. Branch summarization,
which annotates that move, is a model call. Running it in the background — the
obvious choice, since the navigation itself does not need it — lets the user
send a new message before the summary returns: the ordinary append lands first
at the new leaf, and the `branch_summary` node then lands with the same
`parent_id`, manufacturing a branch point where nobody branched.

The file is append-only and is never rewritten, so that spurious branch point is
permanent. We block instead: the browser stays open and suspended, the
summarization dialog becomes a loader with abort-on-escape, and the browser
closes only once the summary has landed, been aborted, or failed.

## Consequences

- The leaf move is committed to the cursor the moment the choice is made, so
  abort and failure both leave the navigation intact and unrecorded — the next
  ordinary append records it. The summary is strictly an annotation, never a
  precondition of the move.
- The browser cannot close on confirm, which is also what keeps the dialog
  alive: it is anchored to the browser, and closing an overlay cascades to
  everything anchored to it.
- A slow or unreachable provider holds an overlay open. Escape is always the way
  out, and the cost of taking it is losing an annotation, not a navigation.
