# The action namespace is context-scoped at fixed depth two

Every keybinding action id is `<binding_context>.<action>` in `snake_case`, at depth exactly
two, over a closed twelve-member binding-context enum. The shape was forced by the config
machinery rather than chosen for taste: the doc-comment is mandatory per key and derived from
the Rust doc-comment, so a map of `action_id -> chain` would have no fields and therefore no
doc-comments, taking the in-editor schema guarantee with it; and config types may not be
recursive, because generation recurses forever and the build hangs rather than erroring. One
struct per binding context with one field per action satisfies both, and makes the context enum
literally the set of top-level fields of the keybindings root type.

## Considered options

The brief's own two examples disagree — `tui.editor.cursor_up` reads *layer.context.object_verb*
while `app.model.select` reads *context.object.verb* — so one of them had to yield regardless of
which shape won. The layer root (`tui.`) is the part that goes: it carries no information the
binding context does not already carry, and keeping it would have made depth three with a
segment that is constant per context.

## Consequences

- **Ids are context-scoped by construction.** Nothing needs to decide whether `confirm` is one id
  reused across contexts or several: it is `session_tree.confirm`, `dialog.accept` and
  `single_line_input.submit`, three ids with three help-text lines.
- **Sharing a word across surfaces is not a collision.** An action id names a keystroke-invocable
  action inside a binding context and nothing else, and is never written without its context, so
  `fork` may also be a headless command and a store verb without ambiguity.
- **There is no mode dimension, and there cannot be one without redesigning the context chain.**
  A binding context is never a mode. This is what makes a genuinely modal Vim preset
  unexpressible: the shipped preset is Vim-flavoured bindings, and modal editing is refused for
  v1 rather than quietly approximated.
- **The namespace is platform-invariant.** Only default binding chains vary by platform; a
  platform-conditional namespace would break the closed enum the generator requires.
