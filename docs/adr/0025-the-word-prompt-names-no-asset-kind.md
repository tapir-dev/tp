# The word prompt names no asset kind

`prompt` is not a kind on the scope ladder. It is a word the brief uses for
three different things, each of which already has an owner:

- the **built-in prompt** — the system prompt `tp` embeds — which is a **doc**,
  reached by its path in the embedded tree;
- the brief's **`prompts` resource-path array**, which is `commands.paths`;
- the **system prompt override**, which is `context.system_prompt`, a config
  key, global layer only.

The asset kinds are therefore `theme`, `command`, `doc` and `skill` — the same
four tokens `tp assets --kind` accepts. There is no `prompts` axis and no
`docs/config/prompts.md`.

## Why the word survived this long

It was written down first and never revisited. The asset-resolution ticket named
the built-in set "a theme, prompt, or doc" before `command` existed as a term,
and the glossary copied that list verbatim. Everything since has added members
in one direction — `skill` to the glossary's list, `command` to the `--kind`
domain — and removed none, so the two enumerations that should be identical
disagree by exactly one member each, in opposite directions.

The vocabulary had already reached the right answer from the other side without
noticing: `prompt` sits on the *Avoid* line of **Skill**, of **Command**, and
(as *prompt file*) of **Context file**. Three entries rule the word out as a
synonym; none of them says what it is instead. This ADR is that sentence.

## Why prompt cannot be a kind

A kind is addressed by an **asset identity** and can therefore collide: a
Skill's root name, a command's filename, a theme's declared name. Shadowing is
the whole reason the ladder exists. The built-in prompt is one file. There is no
second one for it to lose to, no name a user chooses for it, nothing to warn
about. On the test the assets-surface ticket applied to the JSON Schemas and the
security-posture document — *no identity, so no collision, so not a kind* — it
fails identically, and for the same reason it is resolved the same way: as a
doc.

The stronger objection is that making it a kind would **contradict a closed
decision**. Rung 4 of the ladder is the project directory. A kind is replaceable
at every non-vacuous rung — that is what one ladder means — so a `prompt` kind
would let a trusted project replace the system prompt outright. The commands
ticket decided the opposite in as many words: *a trusted project appends; only
the user replaces*, which is why `context.system_prompt` is global-layer only.
Half a ladder for one kind is the split answer the asset-root ticket already
refused. Between a config key that says only the user may replace it and a
ladder rung that says a project may, only one can stand, and the config key is
the one that was decided.

## Why the built-in prompt is a doc rather than a fourth thing

The honest objection to calling it a doc is that a doc is the
self-configuration reference the agent reads, and the system prompt is not
reference material — it is the instructions themselves. The counter is that
`doc` stopped meaning that when the assets-surface ticket folded the three JSON
Schemas and the security-posture document into it. No editor reads a JSON Schema
as reference either. What `doc` now means is *an embedded file addressed by its
path in the embedded tree*, and the built-in prompt is exactly that.

The alternative — a named embedded file that is not an asset at all — reads
better in the glossary and costs the thing the assets surface was built to
provide. A packager patching the built-in prompt through `TP_ASSET_DIR` has a
documented writer clause and one question: *did my patch win?* Under the fold,
`tp assets which doc <path>` answers it. Under the alternative, the one file a
packager is most likely to patch is the one file the surface cannot see.

## Why the array folds into commands.paths

The brief's `prompts` array sits beside `skills`, `themes`, `extensions` and
`packages`, and the brief's own section title for the artefact it discovers is
*Commands (prompt templates)*. The skills axis, declaring `paths`, said the four
sibling arrays would want the same spelling and left the owner to each axis. The
commands axis then declared `commands.paths` — a pattern list, additive, rung 5
of the ladder — which is that array, key for key.

So the fold adds nothing. A `prompts` axis would carry one key that already
exists elsewhere, which is the trade refused once for `runtime` (a mandatory
reference page to house one integer) and named again by the project-trust
ticket: *an axis invented to hold a key that belongs elsewhere is a page that
exists to avoid a decision*. Here there **is** an elsewhere. The brief's own
thirteen reference pages include `commands.md` and no `prompts.md`, which is the
opposite of the skills case, where a mandated page made the axis unavoidable.

## Consequences

- **Two brief lines are overturned.** The resource-path array named `prompts`
  does not exist under that name; it is `commands.paths`. And *system prompt
  overrides* is listed among the project-local inputs that project trust gates,
  but `context.system_prompt` is global-layer only — a project cannot supply
  one, so there is nothing there to gate. The project-trust ticket's enumeration
  of gated roots carries that item and loses it here.
- **The glossary's asset-kind list changes membership.** `prompt` leaves and
  `command` arrives, making it identical to the `--kind` domain. Those two lists
  are the same list and should have been all along; keeping them in step is
  cheaper than reconciling them a second time.
- **`--kind` gains no token.** The derived domain grows when a kind gains an
  owner. This resolution gives the word an owner without giving it a kind, so
  the domain stays at four.
- **Rung 2 vacuity is unchanged.** `command` remains the only kind for which the
  built-in overlay rung is vacuous. The built-in prompt occupies that rung as a
  doc, exactly as the JSON Schemas and the posture document do.
- **No axis is added, so the completion check does not re-arm.** The result is a
  negative declaration — no `prompts` axis, no `prompts.md` page — written down
  in the form the orphaned-axes ticket asked for, so that the next reader does
  not file this ticket again.
- **The brief's remaining three mentions need no overturn.** *Bundled prompts*
  in asset resolution is the built-in prompt, resolved as a doc; `prompts` in
  the live-reload list is the command templates; `prompts` in the product-goal
  sentence is satisfied by `commands` plus `context.system_prompt`. Each reads
  correctly once the word is disambiguated.
