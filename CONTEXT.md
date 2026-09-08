# tp

`tp` is a terminal coding agent whose every user-facing surface — keybindings,
themes, prompts, skills, context, sessions — is data rather than code. This
glossary fixes the vocabulary that data model is described in.

## Language

### Skills

**Skill**:
A directory containing a `SKILL.md` file, holding instructions the agent loads
on demand.
_Avoid_: plugin, extension (an Extension is a separate mechanism), prompt

**Skill root**:
The directory that *is* a Skill. Every relative path written in a skill body is
interpreted against it.
_Avoid_: skill directory, skill folder

**Skill identity**:
The name a Skill is known and collides by: the name of its Skill root. Distinct
from the `name` frontmatter field, which is only a display label.
_Avoid_: skill name (ambiguous between the two)

**Discovery root**:
A directory `tp` searches to find Skills. Each carries a Scope and is either
tp-specific or an Interop path.
_Avoid_: search path, skills directory

**Scope**:
Whether a resource comes from the user or from the project. Project scope is
trust-gated; user scope is not.
_Avoid_: level, tier, global (say "user scope")

**Interop path**:
A Discovery root shared with other agent tools rather than owned by `tp`, so
that a Skill placed there is usable by all of them.
_Avoid_: shared path, common directory, cross-agent path

**Ancestor walk**:
Searching a Discovery root not only at the current directory but at each
directory above it, up to the repository root. It exists to make Skills held at
a monorepo's root visible from a package inside it.
_Avoid_: upward search, parent traversal

**Shadowing**:
What happens when two Skills share an identity: the one found first in traversal
order wins and the other is not loaded. Always warned about, never silent.
_Avoid_: overriding, collision (a collision is the condition; shadowing is the
resolution)

**Progressive disclosure**:
Admitting only each Skill's name and description into the system prompt as a
compact index, and loading a body only when that Skill is actually invoked. It
is what keeps the prompt budget honest as a library grows.
_Avoid_: lazy loading, on-demand loading
