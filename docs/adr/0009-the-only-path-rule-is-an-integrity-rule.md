# The only path rule is an integrity rule, and `bash` is outside it by construction

The brief states that the read/write/execute triad means unrestricted filesystem
and command access, and forbids adding theatrical guardrails. The tool execution
contract nevertheless listed "a path outside what is permitted" as an ordinary
error result, with nothing anywhere defining *permitted*. We keep the brief's
posture — v1 has **no filesystem permission boundary** — and repurpose that error
case as an **integrity** rule with a different justification: `write` and `edit`
refuse to mutate an **owned path**, meaning the current session's directory and
the credential store, because a mutation there corrupts bookkeeping that the
durability and session-storage decisions guarantee. It protects `tp`'s accounting
from the model, not the user's machine from the model.

## Consequences

- **`read` is never refused.** The refusal exists to prevent corruption, and a
  read corrupts nothing. This is not merely permissive: the spill file lives
  inside the session directory and the tool contract instructs the model to
  `read` it by absolute path to recover truncated output, so refusing reads there
  would break truncation recovery outright.

- **`bash` is outside the rule, and not by an exception written by hand.** The
  check runs at admission to the file mutation queue, keyed on the path the tool
  declares. `bash` declares no path and therefore never enters the queue, so the
  rule does not reach it for the same structural reason the queue does not. A
  hand-written dispensation would have been the failure this ADR exists to avoid:
  a rule that binds only the tools that were already the safe ones, while reading
  as a defence.

- **One canonicalisation, one stated limitation.** The check reuses the queue's
  existing key — the deepest existing ancestor canonicalised, remainder lexically
  normalised — so symlinks converge into an owned path and hardlinks do not,
  which is the limitation the queue already declares rather than a second one.

- **The owned set is derived, not constant.** The session root is a config key,
  so the set is a pure function of the merged configuration snapshot and the
  current session id, recomputed when the snapshot is replaced.

- **Not configurable.** There is no key to relax or extend the rule. A knob would
  make it a policy, and a policy is the sandbox reading the brief rules out.
