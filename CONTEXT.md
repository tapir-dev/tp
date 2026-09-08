# tp

A single-binary terminal coding agent whose every user-facing surface is data
rather than code.

## Language

### Security posture

**Owned path**:
A path `tp` itself writes and whose contents another decision depends on — the
current session's directory and the credential store. `write` and `edit` refuse
to mutate one; `read` never refuses, and `bash` is not bound by it.
_Avoid_: protected path, permitted path, restricted path, sandboxed path

**Security posture**:
The document stating in the first person what `tp` can reach and what it
deliberately does not restrict. It records consequences of decisions made
elsewhere and introduces no rule of its own.
_Avoid_: threat model, sandbox policy, security model
