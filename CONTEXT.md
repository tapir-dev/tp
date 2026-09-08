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
