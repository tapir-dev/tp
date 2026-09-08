# tp

A single-binary terminal coding agent whose every user-facing surface is data
rather than code.

## Language

### Project trust

**Project trust**:
The gate deciding whether project-local inputs are loaded at all. It is not a
sandbox and restricts nothing a tool may do once granted.
_Avoid_: workspace trust, project permission, sandbox, project allow-list

**Project-local input**:
A file or directory discovered inside the project that either joins `tp`'s
configuration or reaches the model's prompt. Built-in assets, directories named
by an environment variable, and paths listed in global config are not
project-local inputs.
_Avoid_: project file, workspace file, local resource, untrusted file

**Trust decision**:
A persisted grant or refusal recorded against one canonical directory. Only
`always` and `never` are recordable; `ask` is the absence of a decision, never a
stored one.
_Avoid_: trust flag, trust setting, trust level

**Trust store**:
The single file under the state root holding trust decisions. It is read after
the global config layer and before any project-local input.
_Avoid_: trust database, trust cache, trust registry

**Closest-parent matching**:
The lookup that resolves a directory to a trust decision by walking from that
directory upward, taking the first ancestor that carries one. A nearer refusal
beats a farther grant, in both directions.
_Avoid_: nearest-ancestor lookup, path prefix matching, longest-prefix match
