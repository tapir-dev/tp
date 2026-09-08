# Cancellation is the drop of a future; trace context is ambient

The v1 scope line requires trace propagation to stay structurally separate from
cancellation plumbing even at zero exporters, and the reason the requirement is
hard is that both thread through the same call graph and, done the obvious way,
both look like a value passed alongside every call. Two values of the same
species travelling the same path stay separate only by discipline. We make them
different species instead: **cancellation is control flow** — dropping the
future that owns the work — and **trace context is ambient data**, a task-local
carrying a trace id and a parent measurement id. Neither can be mistaken for the
other, and neither is a parameter, so there is nothing to accidentally thread
through the wrong one.

The choice is also forced from two directions. The provider seam admits exactly
two inputs and the provider-request measurement is emitted by the seam itself,
so a hand-threaded trace context would have to become a third seam input — which
the seam decision already ruled out. And on the cancellation side, the durable
half is already the operation state machine: cancelling writes `Aborted`, which
fences every late write for free, and the in-memory half is scoped to an
invocation, which is exactly the lifetime of a future. A token would have
duplicated a lifetime the runtime already tracks.

The trace context carries a trace id and a parent measurement id and nothing
else. It has no key/value payload, deliberately: that payload is the one route
by which excluded content could re-enter a measurement after the attribute value
type has been closed against it.

## Consequences

Two places pay for this and both are worth naming, because a reader will hit
them and wonder whether the decision was made carelessly.

- **`bash` needs a kill sequence, not a drop.** Killing a child process group
  with `SIGTERM`, a two-second grace period, then `SIGKILL` is asynchronous work
  that has to happen when a synchronous drop runs. It becomes a drop guard that
  hands the kill sequence to the runtime. This is a real cost and it is local to
  one tool.
- **A cancelled tool call must still reach `OutcomeReady(cancelled)` carrying its
  partial output.** A bare drop discards the partial output, so the tool task
  owns its output buffer and the drop path publishes it rather than dropping it.
  The alternative — an explicit cancellation signal for tools and drop for the
  provider — was rejected because it puts the two mechanisms back into the same
  species for half the call graph, which returns the separation to discipline
  after we had made it structural.
