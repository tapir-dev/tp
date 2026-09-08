# A delivery lane lives as long as its boundary

A delivery lane's lifetime is the lifetime of its delivery boundary. Steer and
follow-up wait on a state of the agent, so they are **run-scoped**: in memory,
never durable, gone when the run ends. Next-turn waits on an action of the user,
so it is **session-scoped**: durable, carried by a session record in the
transcript file.

## Why the question is not "is the queue durable"

Asked of the three lanes together, queue durability has no good answer, because
the three do not have the same kind of boundary. Steer delivers at the end of
the current tool batch, follow-up when the agent is idle, next-turn at the
user's next prompt. The first two are positions inside a run. The third is a
gesture.

A process that dies takes its run with it. After the restart there is no "end of
the current tool batch" and no "this agent went idle" — the pending steer message
has not lost its queue, it has lost the event it was waiting for. It stopped
being something enqueued and became text. "The user's next prompt", by contrast,
crosses the restart untouched.

So durability is not a property to be granted or withheld per lane. It is
already determined, and one rule reads it off: **a lane lives as long as the
event it waits for.**

## What the rule decides on its own

Four questions that looked separate collapse into consequences.

- **Restart.** Steer and follow-up are empty, and nothing was lost that could
  have been kept. Next-turn is loaded and painted, waiting for the boundary it
  still has.
- **A run that fails or is cancelled.** The run is over, so the boundaries of
  steer and follow-up are gone and both lanes are discarded. This is what keeps
  the brief's definition of `agent_settled` — *nothing left: no retry, no
  compaction, no queued follow-up* — **literally** true at the same time as the
  retry decision's rule that `agent_settled` is emitted even on failure. The two
  lines looked contradictory and are not; a queued follow-up cannot outlive the
  run that would have delivered it. A pending next-turn never blocked settling,
  because its boundary is the user's gesture and not a state of the agent.
- **A leaf that moves under tree navigation.** Steer and follow-up are empty by
  construction, because the confirm flow already refuses to run with a run in
  flight, so no fourth confirm precondition is needed. Next-turn survives: the
  queue is on screen throughout, painted from the full snapshot the queue event
  carries, and it appends at whichever leaf is current when the user prompts.
- **A read-only session.** A prompt is an append, so in a read-only session the
  boundary "the user's next prompt" can never be honoured. The lane has lost its
  boundary, and by the same sentence it stops being a queue and becomes text: it
  is loaded, shown, and discarded into the editor. The user takes the text,
  forks — the escape hatch the tree browser already provides — and re-queues.

Nothing in that list is a special case. It is one sentence applied four times.

## Considered options

- **Durable for all three lanes.** Rejected on the point of the rule. It would
  resurrect, without a fresh gesture from the user, a steer message typed in a
  process that no longer exists, against a run that no longer exists, at a
  boundary that can never arrive. The mechanism would have to invent a boundary
  to deliver it at, and any invented boundary is a message delivered somewhere
  the user did not ask for.
- **Durable for none.** Rejected because it is wrong about next-turn for the
  same reason the previous option is wrong about steer. "Next time I prompt,
  also carry this" is a standing intention, and the event it waits for is still
  there after the restart. Dropping it loses something that was never at risk.
- **Durable for all three, but never auto-delivered — returned to the editor on
  resume instead.** This was attractive and is strictly more machinery for a
  worse result: it needs a durable medium for steer and follow-up in order to
  hand their contents straight back, and it demotes next-turn from a queue the
  user can rely on to a note that has to be re-queued by hand every restart.

## Where the durable lane lives, and why that costs nothing

Next-turn is a **session record** in the session's JSONL: `parent_id: null`, a
type of its own, last-wins, its body the whole lane. The three candidates were
weighed by how many closed decisions each amends, and this one amends none.

The **sidecar** costs two. The durability decision states that the store carries
*only* the ephemeral sidecar and the control projection, and a queue of the
user's text is the opposite of ephemeral — it exists in order to survive. And
the sidecar's keys are operation-scoped under a closed prefix enum whose
exhaustive cleanup is per-operation, so a session-scoped table would sit outside
the one guarantee that enum exists to give.

**A file of its own** in the session directory runs into the reference test:
everything the transcript references lives inside the session directory,
everything that references nothing and is referenced by nothing lives outside.
The queue references nothing and nothing references it, and that test is what
puts the debug tap outside.

A session record is already defined as session-scoped, last-wins, and never
reaching the model — which is the queue described exactly. Last-wins *is* the
full snapshot the queue event already carries, so the durable shape and the wire
shape are the same shape. And read-only refuses to enqueue through the very
mechanism that refuses to deliver, because both are appends: one mechanism
rather than two.

The near precedent is `session_info`, which is durable interface state and is a
record. The apparent precedent against — the rejected `leaf_move` entry, refused
for polluting the transcript with navigation — does not reach: that was refused
for creating a *second* source of truth about something already derivable from
the file. The queue is derivable from nothing.

## Consequences

- **Fork and clone copy neither lane.** Records are already copied selectively
  rather than wholesale, so this is one line in a rule that exists, not an
  exception carved into a verbatim copy. A pending queue is an intention the user
  is watching on the source session's screen and will keep watching there;
  copying it would make two copies of one intention, where delivering either
  does not remove the other. Duplicated intention is worse than lost intention.
- **A discard returns its text.** Losing a run does not entitle the product to
  lose what the user typed. The clear gesture already defines the shape — the
  removed text goes back to the editor — and a discard is a clear nobody asked
  for.
- **Steer's boundary must include the end of the run**, which is an amendment to
  the ticket that placed the lanes. Under `one_at_a_time` a lane can still hold
  messages when the run ends, and "the end of the current tool batch" would then
  be a boundary that never arrives again. The boundary is therefore *the end of
  the current tool batch, or the end of the run, whichever comes first*. The
  alternative — promoting a held steer message into the follow-up lane — was
  rejected for undoing the thing that made lanes coherent: a lane *is* its
  boundary, so a message that changes lanes changes what the user asked for.
- **Steer is delivered before follow-up** when both boundaries fall at the same
  instant, which happens on a run that ends with no tool calls at all. Not a
  tiebreak: steer means "as soon as you can" and follow-up means "when you are
  done", so delivering a follow-up ahead of a pending steer inverts the only
  thing the user chose by picking a lane.
- **The reference test has a hole, recorded rather than fixed.** Its
  contrapositive is not sound: the debug tap is outside the session directory for
  a *positive* reason — it is read after something went wrong, including after
  the session was deleted — and not because the test excluded it. Queued text has
  the opposite positive reason: deleting a session must destroy the text queued
  against it. No amendment is needed here, because a session record is inside a
  file that is already inside, but the next file to be invented will meet this
  gap.
