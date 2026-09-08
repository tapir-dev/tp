# The cut point is a call group boundary

Compaction's backward walk moves over **call groups**, not over entries. A call
group is an assistant message carrying one or more tool calls together with
every tool result entry that answers it. The cut point falls before a group or
after its last result, never inside it.

The brief states the rule as *the cut point may never land on a tool result*.
That is necessary and insufficient. Because tool results are appended one per
entry in settlement order, a cut placed immediately **after** the assistant
message satisfies the brief's rule and still produces a retained tail that opens
on results whose call was summarised away. Anthropic requires a tool result to
follow its call immediately; a history that opens on an orphaned result is
rejected. The invariant only closes when it is stated over the pair.

## Why the group is indivisible rather than repairable

The alternative is to keep the entry-level walk and repair the damage: elide the
orphaned results, or synthesise the missing call. Both were rejected.

Eliding inside the retained tail would create a **third** meaning for
truncation. Two already exist and the vocabulary separates them with effort:
source truncation cuts a tool's output where the bytes are produced, and
compaction elision shortens an already-recorded result when serialising history
for a summarisation request. A third would apply to the one copy of the text
that is supposed to be what the model sees verbatim, which is the whole value of
a materialised retained tail.

Synthesising the call is worse: it puts a message in the request that no one
sent and that the transcript does not contain. Exactly one divergence of that
kind is accepted anywhere in this spec — the OpenAI image-tool-result split —
and it is accepted only because it is deterministic and declared in a quirk row.
A synthesised call would be neither.

## The cost, which is real

Indivisibility admits a case the entry-level walk did not: a single call group
whose token cost already exceeds `context_window - reserve_tokens`. With eight
concurrent tool calls and source truncation at 50 KB per result this is
reachable on a 128K window, not hypothetical.

That case is **declared unsolvable by compaction** rather than papered over.
Compaction produces the smallest legal retained tail; if it still does not fit,
the turn fails with an error naming the cause — one call group too large for the
window — and pointing at the spill files, which are already on disk. The user
has a real way out: fork before the group. The compaction latch is what stops
this from becoming a retry loop.

## What this replaces

The brief's split-turn handling stops being a mechanism. It says that a turn
exceeding `keep_recent` is cut mid-turn at an assistant-message boundary,
summarised twice — history and turn-prefix — and the two summaries merged. Once
a turn is understood as a sequence of call groups, "an assistant-message
boundary inside a turn" *is* a group boundary, so there is no special cut to
make. With no special cut there is no second summary and nothing to merge: one
summarisation call covers the whole cut span, always.

The merge was the part with no defined semantics — whether it concatenated
sections or required a third model call was never stated. It is deleted rather
than specified.
