# tp

`tp` is a terminal coding agent whose every user-facing surface — layout, colors,
keybindings, tools, providers, models, prompts, skills, context, sessions — is
data rather than code.

## Language

### Assets

**Asset**:
A unit of data the product resolves at runtime rather than compiles in: a theme,
a prompt, a doc, a skill.

**Built-in asset**:
An asset that ships as part of the product itself, carried by the binary.
_Avoid_: bundled asset — the brief's term, ambiguous between the content and the
directory it might live in

**Asset root**:
A directory whose files overlay built-in assets of the same name.
_Avoid_: bundled asset directory, asset dir

**Scope ladder**:
The product-wide ordering of the sources an asset may come from, from built-in
at the bottom to a command-line flag at the top. One ladder governs every asset
kind.
_Avoid_: lookup order, precedence chain, search path

### Identity

**Identity**:
The single constant naming the product: the name it uses in paths, the name it
displays, its environment-variable prefix, and its directory name. A rebrand
changes this and nothing else.
_Avoid_: branding, product config, app config

### Trust

**Project trust**:
A per-directory grant deciding whether project-local inputs are loaded at all.
It is a gate on origin, not a sandbox: it does not restrict what tools may do
once granted.
_Avoid_: permission, sandbox, allowlist

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
