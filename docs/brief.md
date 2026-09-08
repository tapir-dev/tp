Build **wayfinder**: a coding agent with a terminal UI, written in Rust, fully
configurable at runtime, shipping internal per-axis documentation that the agent
itself reads in order to reconfigure the project.

## Product goal

A single binary running an LLM coding-agent loop in the terminal. Every
user-facing surface — layout, colors, keybindings, tools, providers, models,
prompts, skills, context, sessions — is data, not code. The binary carries a
self-configuration reference so an agent (or a human) can change any of it
without touching Rust source.

## Workspace decomposition

Four crates, clean seams, no upward dependencies:

- `wayfinder-ai` — provider abstraction, model registry, streaming, auth.
- `wayfinder-agent` — agent loop, message types, sessions, compaction,
  durability. Provider-agnostic.
- `wayfinder-tui` — generic terminal rendering and component primitives. Knows
  nothing about agents.
- `wayfinder` — CLI, interactive mode, product assembly.

Asset resolution (themes, bundled prompts, docs) must work identically under
`cargo run`, `cargo install`, and a packaged standalone binary. Use one path
helper, never `current_exe()` ad hoc. Make the product name, config directory,
and env-var prefix parameterized in one place so a fork/rebrand is a one-line
change.

## Agent core

- Minimal loop: no step limit; run until the model returns a message with no
  tool calls. Handle tool execution, argument validation, event streaming.
- System prompt under ~1000 tokens including tool definitions. Assume the model
  already knows how to be a coding agent.
- Streaming with progressive JSON parsing of tool arguments.
- Thinking levels are an abstraction (`off`/`minimal`/`low`/`medium`/`high`/
  `xhigh`/`max`) mapped per model to whatever the provider actually accepts;
  tri-state per level: default mapping, explicit value, or unsupported/hidden.

### Message delivery

Three delivery modes, not two:

- `steer` — interrupt mid-stream, delivered after the current tool batch.
- `follow_up` — wait until the agent is fully idle.
- `next_turn` — queued for the next user prompt, non-interrupting.

Each of steer and follow-up has an independently configurable drain policy:
`all` (deliver the whole queue) or `one_at_a_time`. Queue state changes emit the
**full** pending queues, not deltas. Clearing the queue returns the removed text
so the UI can restore it into the editor.

Hard invariant: the provider context may only grow at the tail across a lane's
requests. Any insertion before the previous tail invalidates the provider's KV
cache and multiplies cost. This is *why* steered messages land at checkpoint
boundaries rather than immediately.

### Retry

Two independent layers, and do not conflate them:

- Agent-level retry on transient failures (overloaded, rate limit, 5xx) with
  exponential backoff, surfacing `retry_start`/`retry_end` with attempt counts
  and delay so the user sees what is happening.
- Transport/HTTP-level retry, default **0**. Document loudly that raising it
  lets the HTTP layer swallow rate-limit errors before agent-level retry ever
  sees them.

Summarization/compaction calls get their own separate retry loop with its own
events.

### Event taxonomy

Emit a stable, versioned event union. Minimum vocabulary:

- `agent_start` / `agent_end` — one low-level run.
- `turn_start` / `turn_end` — one assistant response plus its tool calls.
- `agent_settled` — nothing left: no retry, no compaction, no queued follow-up.
  Distinct from `agent_end`, and the one consumers actually want.
- `message_start` / `message_update` / `message_end`.
- `tool_execution_start` / `tool_execution_update` / `tool_execution_end`.
- `queue_update`, `compaction`, `extension_error`.

`message_update` carries **deltas only** (`content_index` + delta), never a
cumulative snapshot — a snapshot per delta makes stream size quadratic.
`message_end` is the only authoritative full message. `tool_execution_update`,
by contrast, carries the partial accumulated result and the client replaces its
display wholesale.

Cumulative provider usage may legitimately be zero mid-stream if the provider
only reports at completion. Clients must not assume otherwise.

## Tools

Four core tools, nothing more by default:

- `read` — files and images, `offset`/`limit` for large files.
- `write` — create or overwrite, auto-creating parent directories.
- `edit` — exact-match replacement, fails loudly on ambiguity.
- `bash` — synchronous execution with optional timeout.

Optional, disabled by default: `grep`, `find`, `ls`.

### Tool execution contract

- **Output truncation happens at the source of the bytes**, not in the
  model-facing layer. If execution is ever remote or sandboxed, never ship a
  gigabyte across a boundary just to truncate it. Limits: ~50KB or ~2000 lines,
  whichever hits first, with a lazy spill-to-file past the threshold and a
  `full_output_path` on the result telling the model where the rest went.
- Adaptive update publication for streaming output: first update after idle is
  immediate, then coalesce — roughly `next_delay = max(100ms, bytes * 1000 /
  100KB_per_sec)`. Handle write backpressure properly (pause, resume on drain).
- If tools may run in parallel, a **file mutation queue keyed by canonicalized
  absolute path** is mandatory, and any custom tool that writes files must opt
  into it. Without it, concurrent `edit`/`write` silently lose updates.
- Each tool declares a replay policy: `safe` (read-only/idempotent — may be
  re-run verbatim after a crash with the same invocation id) or `never` (the
  harness synthesizes an error result plus an explicit "external outcome
  unknown" marker instead of re-running).
- Direct shell execution outside the LLM loop (a `!` prefix in the editor) is a
  distinct path from the `bash` tool. Its output enters model context only on
  the *next* prompt, as a synthesized user message. Support a variant that stays
  out of context entirely.

### Non-goals, with rationale in the docs

- No MCP. External capability comes from CLI tools with READMEs read on demand
  via `bash`, so nothing occupies context unless needed.
- No background processes. Long-running work goes through `tmux`, keeping it
  observable.
- No implicit sub-agents. Nesting is an explicit `bash` invocation of the binary.
- No built-in plan or todo mode. Planning state lives in files so it survives
  compaction and stays visible.

## Durability

This is the part that is hard to retrofit. Design it in.

- **Intent → effect → settlement.** Before any uncertain external effect, commit
  an intent record reserving ids and declaring what is about to happen; perform
  the effect; commit the settlement together with the next state in one
  transaction. This is the actual mechanism behind "abort with partial
  recovery," and it should be stated as a pattern rather than reinvented per
  call site.
- **Streaming frames are auxiliary and ephemeral.** Convert provider stream
  events into compact frames appended to a sidecar store; never await disk I/O
  on the token path. Preserve FIFO ordering, retain and await only the latest
  write at settlement, and observe every write's failure. On recovery, fold
  frames into a synthetic partial message with an explicit "interrupted, outcome
  unknown" stop reason. Frames never prove completion — only the scalar
  operation state does. Delete the frame list atomically with the final message
  insert, on every terminal path.
- **Separate durable scopes at the type level** so a transaction cannot mix
  them: the permanent append-only session history versus an ephemeral sidecar
  (streaming frames, pending tool output, invocation memos) that is dropped
  wholesale when the operation settles. This is not a micro-optimization: naive
  frame-per-token appends into the main log produce three orders of magnitude of
  pure scaffolding relative to the settled history.
- **Fence late writes.** Every mutation originating from a tool re-verifies at
  commit time that it still belongs to the current operation/turn/invocation.
  A slow async write must not resurrect state after cancellation.
- **Terminal cleanup** deletes exactly the operation's owned address prefixes,
  enumerated through named prefix constructors rather than raw key patterns.
- **Out-of-order settlement, in-order transcript.** Give a completed tool call a
  distinct `outcome_ready` state between "effect settled" and "placed in the
  tree," so parallel calls can finish in any order while the transcript stays
  source-ordered — and so a call that reached `outcome_ready` never re-executes.
- **Clean shutdown is a controlled crash.** Closing and `SIGKILL` must leave the
  identical durable restart point. Assert this with a test.
- Keep the operation state machine a small, flat, closed enumeration; every
  transition replaces the complete state. No diffing, no journal replay.
- Restore reads only a small fixed control projection — never dereference the
  transcript, tool arguments, or checkpoints during recovery. Bound recovery
  cost independently of session size.

## Sessions

- Append-only JSONL per session. On-disk path derived from the working
  directory plus a timestamp and uuid; document the path-mangling scheme.
- Every entry has `id`, `parent_id` (null at root), `timestamp`, `type`. The
  id/parent_id links *are* the tree; no separate index file.
- Ids are UUIDv7 so they self-sort by creation time. Tool-result ids inherit the
  timestamp prefix of their triggering assistant message so a call-and-results
  group stays cohesive across a midnight boundary.
- Explicit format `version` field with an auto-migration path on load. Decide
  the migration story on day one even if the first migration is years away.
- Entry types beyond plain messages: `session` header (holds cwd and an optional
  pointer to the session it was forked from), `message`, `model_change`,
  `thinking_level_change`, `compaction`, `branch_summary`, `custom` (extension
  state, not sent to the model), `custom_message` (extension-injected, *is* sent
  to the model), `label` (bookmark on any entry), `session_info` (display name).
- Deletion prefers the system trash when available over permanent unlink.
- Expose the session store as a real API, not an internal detail: create, open,
  continue-most-recent, in-memory, fork-from, list; and per-session leaf/branch
  traversal, reset-leaf, branch-with-summary.

### Branching

Three distinct operations with different targets:

- **tree** — move the leaf in place, same file. Selecting a *user* message moves
  the leaf to its parent and prefills the editor with that text for re-editing;
  selecting a non-user entry moves the leaf there with an empty editor;
  selecting the root resets to an empty conversation.
- **fork** — new file, branching from an earlier user message.
- **clone** — new file, duplicating the current active branch as-is.

The tree browser needs filter modes (all / no-tools / user-only / labeled-only)
with a persisted default, fold/unfold, jump between branch segments, and label
display toggles.

**Branch summarization** is a separate mechanism from compaction: on tree
navigation, find the deepest common ancestor of the old and new leaf, walk the
abandoned span backward within a token budget, summarize it, and attach a
summary entry at the new position pointing back at the abandoned leaf. Offer the
user three choices: no summary, default prompt, or custom focus instructions.

Cumulative read/modified file tracking must thread through both nested
compactions and branch summaries — an accumulator that survives repeated
summarization.

## Compaction

- Trigger: `context_tokens > context_window - reserve_tokens`, default reserve
  16384. Check after each tool batch (skip if that batch ends the run with
  nothing queued), before a new user prompt, and after a run ends. Not only on
  overflow.
- Two phases: walk backward accumulating token estimates until `keep_recent`
  (default 20000) is reached to find the cut point, then summarize everything
  before it.
- **Hard invariant: the cut point may never land on a tool result.** It must
  land on a user message, assistant message, shell-execution message, injected
  custom message, or branch summary. A tool result must stay paired with its
  call.
- Split-turn handling: if a single turn exceeds `keep_recent`, cut mid-turn at
  an assistant-message boundary, generate two summaries (history and
  turn-prefix), and merge them.
- Repeated compaction resummarizes from the *previous* compaction's kept
  boundary, not from the compaction entry itself, so surviving messages fold
  into the next summary.
- **A compaction entry is a self-contained checkpoint**: it stores its own
  summary plus the materialized retained tail. Context construction never reads
  past the newest compaction. No chained summary lookups at request time.
- Fixed structured summary format, adopted as a contract: `## Goal`,
  `## Constraints & Preferences`, `## Progress` (Done / In Progress / Blocked),
  `## Key Decisions`, `## Next Steps`, `## Critical Context`, plus read-files and
  modified-files blocks.
- Serialize messages for summarization in a stable labeled text format and
  truncate individual tool results to ~2000 characters with a truncation marker,
  so the summarization request cannot blow its own budget.
- Summarization calls use fresh routing identifiers and disable prompt-cache
  writes — they are one-off and never reused.
- Three reasons threaded through events: `manual`, `threshold`, `overflow` (the
  last being mid-turn recovery after a context-limit error, which auto-resumes
  the aborted prompt).
- Settings: enable/disable auto-compaction while still allowing manual, plus
  `reserve_tokens` and `keep_recent_tokens`.
- Post-compaction, context-usage reporting is legitimately unknown until a fresh
  assistant response arrives. Model it as an explicit transient null state, not
  a zero.

## Configuration

Config is **TOML**. Two layers: global user config and project-local config,
deep-merged over built-in defaults.

Merge semantics, documented explicitly because they are easy to get wrong:

- Tables (objects) deep-merge key by key.
- **Arrays fully replace.** A project-level array replaces the global array
  entirely; it does not append.
- Relative paths in the global config resolve against the global config
  directory; relative paths in project config resolve against the project config
  directory.
- Resource-path arrays (skills, prompts, themes, extensions, packages) support
  glob patterns, `!pattern` exclusion, and `+path` / `-path` force-include and
  force-exclude prefixes.

Keybindings and themes live in their **own files**, not inside the main config —
they have different shapes, different edit cadence, and benefit from schema
validation independently.

Validation produces precise errors: file, key path, expected shape, and the
nearest valid key on a typo. Provide a live reload command that re-reads config,
keybindings, themes, skills, prompts, and context files without restarting.

Provide an in-app settings browser with fuzzy search, and a "save the current
session-only choice as the startup default" gesture inside the model and
thinking pickers.

### Project trust

A separate, lighter gate than sandboxing, and say so plainly: trust controls
whether *project-local inputs* (config, extensions, skills, prompts, themes,
system prompt overrides) are loaded at all. It does not restrict what tools can
do once trusted.

- Interactive mode prompts once per untrusted directory, offering to trust the
  parent.
- Non-interactive modes never prompt; they fall back to a global
  `default_project_trust` of `ask` / `always` / `never`.
- Per-run CLI override in both directions.
- Decisions persist per canonical directory with closest-parent matching.

## Theming

Themes are standalone files, discovered from built-ins, a global directory, a
project directory (trust-gated), config-listed paths, and repeatable CLI flags,
with a flag to disable discovery.

- Schema: a unique `name`, an optional `vars` block of named color aliases, a
  required `colors` table covering every semantic role, and an optional export
  block for HTML export colors with documented fallbacks.
- Color values: 24-bit hex, a 256-color index, a reference to a `vars` key, or
  the empty string meaning "terminal default."
- Render truecolor and degrade to the nearest 256-color approximation on older
  terminals.
- Define the role taxonomy up front and completely, not incrementally. Cover at
  minimum: core UI (accent, borders, muted, dim, text, success/error/warning,
  scrollbar track and thumb), backgrounds and content (selection, search match,
  user message, injected message, tool pending/success/error), markdown, diffs
  (added / removed / context), syntax highlighting (comment, keyword, function,
  variable, string, number, type, operator, punctuation), a per-thinking-level
  border gradient used to signal current reasoning effort, and a distinct border
  color for shell-input mode. Expect on the order of fifty roles. Document
  fallback chains for optional roles.
- Auto-detect terminal background on first run to pick a light or dark default,
  and support a "follow terminal appearance" selection.
- Support a run-scoped theme override that does not persist.
- Hot-reload the currently active theme file on change, for instant feedback
  while authoring.
- Components must never emit raw ANSI — they call theme helpers. **Contract: any
  component that bakes theme colors into cached strings must rebuild its content
  on invalidation, not merely clear its cache.** The TUI invalidates every
  component on theme change.

## Keybindings

Bindings map **namespaced action ids** (`tui.editor.cursor_up`,
`app.model.select`) to keys — never raw key-to-behavior remapping. The action id
is the stable public name used by config, by help text, and by extensions.

- Separate `keybindings.toml`. Each action maps to a key or a list of keys, and
  a user-supplied list **replaces** the default list for that action rather than
  merging. Binding to an empty list disables the action.
- Key grammar: `modifier+key` with combinable `ctrl`, `shift`, `alt`, `super`.
  Note that `super` requires an enhanced keyboard protocol and will not work
  everywhere.
- Distinct binding contexts with their own default sets: editor, single-line
  input, select lists, transcript viewport (fullscreen only), application-global,
  sessions, model and thinking pickers, tree navigation.
- Context-sensitive routing is itself configurable: in fullscreen, unmodified
  navigation keys drive the transcript while their modified variants drive the
  editor; outside fullscreen both drive the editor.
- Document the precedence rule for conflicts explicitly rather than leaving it
  emergent.
- Platform-conditional defaults are unavoidable — the same action needs
  different defaults on native Windows, WSL, and Unix. Some actions (process
  suspend) have no meaningful Windows default and must degrade to a status
  message, not a crash.
- Include an Emacs-style kill-ring (yank / yank-pop) distinct from the system
  clipboard.
- Ship ready-made Emacs and Vim keymap presets as examples.
- Migrate legacy action ids automatically on load.

### Terminal input reality

This is where a TUI silently breaks, so specify it:

- Prefer the Kitty keyboard protocol when available; otherwise request enhanced
  key reporting and support both CSI-u and the legacy xterm `modifyOtherKeys`
  encodings. Document the actual sequences for the ambiguous cases
  (`Ctrl+Enter`, `Shift+Enter`, `Alt+Enter`).
- Provide a tunable escape-timeout to disambiguate a lone `Escape` from the
  start of an Alt-modified sequence — a short default locally, longer over SSH.
- Under `tmux`, extended keys require explicit configuration and a full server
  restart; detect and tell the user rather than silently losing keys.
- Some terminal emulators fundamentally cannot distinguish modified `Enter` from
  plain `Enter`. Maintain a documented compatibility table and degrade honestly.
- Support key-*release* events as a first-class concept where the protocol
  provides them, opt-in per component.

## Terminal UI

Two modes:

- **Scrollback mode (default).** Do not take the alternate screen. Native
  terminal scrolling and search keep working. Do not capture the mouse.
- **Fullscreen mode.** Fixed dock (editor, status, footer, widgets) plus a
  scrolling transcript region, mouse capture, in-transcript search, scrollbar
  policy (auto / always / hidden), selection and copy behavior, and a
  configurable choice of what gets printed on exit.

Rendering:

- Retained mode. Components cache output; a differential pass finds the first
  changed line and redraws from there.
- Wrap frames in synchronized-output escape sequences to avoid flicker.
- Component contract: `render(width) -> Vec<Line>` where no line exceeds the
  width, plus optional input, mouse, and invalidation hooks. Reset all styling
  at the end of every rendered line — styles must not bleed across lines.
- **Cursor placement for IME**: components emit an invisible marker at their
  logical cursor position; the renderer scans output for it and positions the
  real hardware cursor there, so input-method candidate windows appear in the
  right place while the visible cursor stays custom-drawn. Hide the hardware
  cursor by default, with an override. Container components must propagate focus
  to embedded editors or this breaks.
- **Overlay system**: float components over existing content without clearing.
  Support absolute or percentage sizing, nine-point anchoring with offsets,
  margins, a responsive visibility predicate based on terminal size, and a
  handle for programmatic focus, hide, and close. A focused overlay retains
  input ownership across transient UI. Overlays are disposed on close.
- **Mouse model** (fullscreen only): normalized press/release/click/move/drag/
  wheel; handlers return handled/capture/focus/render flags; unhandled wheel
  scrolls the nearest scroll view; unhandled drag performs text selection;
  hyperlinks take priority over parent click regions; auto-scroll when dragging
  past an edge.
- Component library worth building: text, box, container, spacer, markdown,
  image (via terminal graphics protocols, with cell-size caps), select list,
  searchable settings list, bordered loader with abort-on-escape, dynamic border.
- Width utilities must be ANSI-aware and grapheme-correct: visible width,
  truncate-to-width, wrap-preserving-ANSI.
- Ship a debug facility that dumps the raw ANSI stream and the last provider
  request to a file — indispensable for diffing "what was rendered" against
  "what was sent."

Interaction affordances:

- Autocomplete with pluggable providers keyed on trigger characters, stacking
  above built-in slash-command and `@file` completion, with a configurable
  dropdown size.
- `@` fuzzy file mentions; image paste and drag-and-drop.
- Working indicator with customizable message, visibility, and animation frames.
- Status chips in the footer by key, a fully replaceable footer with access to
  git branch state, terminal title control, and persistent widgets anchored
  above or below the editor.
- Dialog primitives — select, confirm, text input, multiline editor, notify —
  each supporting a timeout with a visible countdown and a return value that
  distinguishes timeout from user cancellation.
- Tool rendering has independent slots for the call and the result; a tool may
  override either one, or take over framing entirely. Diff rendering and syntax
  highlighting are theme-driven, not hardcoded.
- Markdown rendering is interceptable by transformers (display-only, aware of
  message type, streaming state, and available width), with settings for code
  block indentation and diagram rendering mode.

## Skills

A skill is a directory containing `SKILL.md`: frontmatter plus a Markdown body.
Sibling directories hold scripts, references, and assets, referenced by relative
path.

- Adopt the existing cross-agent skill convention rather than inventing a
  format, so skill directories can be shared across tools. Document any
  deliberate deviation.
- Discovery: a global skills directory, a project one (trust-gated), and a walk
  up ancestor directories to the repository root for the shared convention path.
  Recursively discover any directory containing a `SKILL.md`; in the
  tool-specific directories, also accept top-level Markdown files that carry
  valid frontmatter.
- Frontmatter: `name`, `description` (required — a skill without one does not
  load), plus optional `license`, `compatibility`, arbitrary `metadata`, an
  allowed-tools list, and a flag that hides the skill from the system prompt so
  it is reachable only by explicit command.
- Name rules: 1–64 characters, lowercase alphanumeric and hyphens, no leading,
  trailing, or consecutive hyphens.
- Validation is lenient: most violations warn and still load. Unknown fields are
  ignored. Name collisions warn and the first discovered wins, deterministically.
- **Progressive disclosure is the point.** Only name and description enter the
  system prompt, as a compact index; the body loads on demand. This is what
  keeps the prompt budget honest with a large library. Note in the docs that
  models do not always self-invoke, so an explicit command matters.
- Each skill auto-registers as a command; trailing arguments append to the skill
  content as literal user text.
- Skill content is untrusted and can carry executable scripts. Same trust
  posture as extensions.

## Commands (prompt templates)

Markdown files with frontmatter; the filename is the command name.

- Frontmatter: `description` (falling back to the first non-empty body line) and
  an argument hint displayed in autocomplete.
- Argument substitution is a small shell-inspired language, not a single
  placeholder: positional `$1`, `$2`; all arguments joined; default-if-empty
  `${1:-default}`; all-arguments-with-default; arguments from the Nth position;
  and a slice of N arguments starting at position M.
- Discovery from global and project directories is **non-recursive** — nested
  templates require explicit registration. Document this edge.
- Every command carries provenance: source kind (extension / template / skill),
  scope (user / project / temporary), and origin. Expose the unified command
  list programmatically.
- On name collision, append numeric suffixes in load order rather than erroring
  or silently overwriting.

## Context

- Hierarchical context files: global, project root, and optionally per-directory
  files that load when work touches that subtree. Merge order is documented and
  configurable; the system prompt can be replaced outright, not only appended to.
- Files referenced from a context file load lazily.
- Report context usage continuously; when compaction happens, say what was
  compacted. Durable state belongs in files on disk.

## Providers and models

Support the major hosted providers plus any OpenAI-compatible endpoint. The hard
part is not base URLs — it is the compatibility layer. Plan for it explicitly.

- **Model source is three-tier**: a compiled built-in catalog, a
  network-refreshed cache persisted to disk (throttled per provider, restorable
  offline, cancellable, reporting per-provider partial failures without
  invalidating successes, with generation counters so a stale in-flight refresh
  cannot clobber newer state), and user-authored overrides.
- User model/provider definitions support: `base_url`, auth mode, capabilities,
  costs, and **partial overrides** that patch built-in model metadata without
  redefining the whole model.
- Cost model needs tiered pricing: an alternate full rate set that swaps in once
  total input usage crosses a threshold, highest matching tier winning.
- A free-form sampling-parameter passthrough merged verbatim into request
  bodies, with user keys winning — the escape hatch for knobs not modeled
  natively.
- Credential and header values are a small resolution DSL: a literal string, an
  environment variable reference, or a shell command whose stdout is used
  (resolved at request time, with documented escaping for literal sigils).
  Availability checks must never execute shell commands.
- Auth precedence, four tiers: explicit runtime override (not persisted) >
  credential store > environment variable > custom-provider fallback resolver.
- **A per-provider/per-model quirk table is unavoidable.** Expect on the order of
  twenty-plus flags covering role support, reasoning-effort field names, usage
  reporting during streaming, finish-reason support, max-tokens field naming,
  tool-result shape requirements, message-ordering requirements, thinking
  serialization format variants, cache-control format, session-affinity headers,
  strict/grammar tool modes, and eager tool-input streaming. Budget for this as a
  first-class subsystem, not an afterthought — it *is* what multi-provider
  support costs.
- OAuth alongside API keys, with a manual-paste fallback for headless and SSH
  sessions where a loopback callback is unreachable. Distinguish subscription
  login from API-key login where a provider offers both, and surface any
  separate billing pool plainly.
- Cross-provider session handoff with best-effort conversion; thinking traces
  degrade to tagged text.
- Model selection scoping: a glob list restricting which models participate in
  cycling, optionally pinning a thinking level per pattern.

### Usage accounting

Track input, output, cache-read, and cache-write tokens **separately**, each with
its own cost, plus a total. Three contributors must all roll up: assistant
messages, LLM calls made *inside* tool execution, and summarization calls.
Report lifetime totals separately from current context-window fill, and report
message counts by role alongside token counts.

## Headless and RPC

- Line-delimited JSON over stdin/stdout, **LF-only framing**. Do not use a line
  reader that also splits on U+2028/U+2029 — those are legal inside JSON strings.
- Every command may carry a correlation id, echoed on the response and on
  related events.
- **Accept-then-stream contract**: a successful response means accepted or
  queued, not completed. Completion and failure arrive later on the event
  stream. There is no second response for the same id.
- Prompting while the agent is already streaming requires an explicit steer or
  follow-up disambiguation; do not silently queue.
- Provide an incremental entry cursor so a client that restarts can resume
  reading without replaying everything.
- Command surface worth mirroring: prompt, steer, follow-up, abort, clear queue,
  new/switch session, get state, get messages, set/cycle model, list models,
  set/cycle thinking level, toggle auto-compaction and auto-retry, direct shell
  execution and its abort, session stats, export, fork, clone, list forkable
  messages, get entries with cursor, get tree, set session name, list commands.
- The headless JSON stream's first line is always the session header.
- Never blindly replay a mutation after an uncertain disconnect: a replayed
  selection is harmless, a replayed prompt is not. Reconnect around stable
  operation-id lookups, not retry-the-last-call.

## Extensions

Decide scope deliberately; this is the single heaviest optional axis. If
included:

- Extensions get a **narrowed capability scope**, not the raw internals — hooks,
  scoped session data, and published services only. Enforce it with module
  boundaries, not convention.
- Tools and providers are contributed into a host-owned draft that is **rebuilt
  from scratch** on every change, composing as nested middleware. Removing an
  extension means rebuilding without its contribution — no unregister logic.
- Separate two mechanisms cleanly: **hooks** intercept live operations and have
  durability classes (an effect is only durable if it commits in the same
  transaction as a state transition; otherwise it silently reruns after a crash);
  **services** configure statically rebuilt behavior. Conflating them destroys
  the recovery story.
- Distinguish three cancellation domains and never blur them: one caller's
  invocation, a service-owned job, and durable operation abort. A transport
  disconnect triggers only the first.
- Hook points worth exposing: session lifecycle, resource discovery, pre-run
  system-prompt and message injection, turn and message lifecycle (with the
  ability to replace a finalized message), blocking tool-call interception with
  mutable input, chainable tool-result middleware, provider header/request/
  response interception, model and thinking selection, user shell interception,
  and raw input interception with continue/transform/handled semantics.
- Custom tools need: a prompt snippet, appended prompt guidelines, argument
  pre-validation for schema drift across resumed sessions, a terminate hint,
  nested usage reporting, and custom render slots.
- Built-in tools must be overridable by name, with execution and rendering
  overridden independently.
- Two parallel extensibility tracks, kept distinct: injected messages that
  participate in model context, and durable session entries that render in the
  transcript but never reach the model.
- Document the session-replacement footgun: after a fork or switch, callbacks
  closed over the old session hold stale references.
- Extensions and any package mechanism run with full system access. Say so.

## Telemetry

- Define a versioned span vocabulary even if most of it is not emitted yet — the
  attribute list is the useful artifact. Cover: provider request (model,
  streaming, stop reason, token and cache counts, cost, HTTP status,
  time-to-first-chunk), top-level operations, checkpoints, turns, tool calls,
  hooks, and storage transactions.
- **Content exclusion rule, baked in from day one**: spans carry ids, names,
  counts, durations, statuses, and usage numbers only — never prompts,
  completions, tool arguments or results, file contents, provider payloads,
  headers, or credentials.
- Keep trace propagation separate from cancellation plumbing.
- Any telemetry that leaves the machine is opt-in, distinct from a version check,
  and both are disabled by a single offline switch.

## Session search

- A standalone, pull-based, rebuildable projection with zero authority over the
  session store. Hit identity is `(session_id, entry_id)`.
- Streaming result API, not collect-then-return, so search-as-you-type can stop
  early and cancel in flight.
- A durable per-session cursor drives catch-up indexing; change notifications
  carry no content and are only a hint — a lost notification self-heals on the
  next sweep.
- Keep index maintenance out of the canonical write path. A failure in optional
  search must never roll back a session write.
- Decide up front how metadata filtering interacts with ranked limits:
  post-filtering a ranked top-N silently drops valid results. Filter before
  restriction, or index the filter field natively.

## Environment variables

- A generic marker announcing "a coding agent launched this process," plus a
  product-specific one, so child processes can detect the context.
- Session context injected into model-invoked shell calls only (not user-typed
  ones): session id, session file, provider, model, reasoning level — resolved
  fresh per command so a model switch takes effect on the next call. Document
  these as the source of truth when the user asks the agent which model it is.
- Overrides for config directory, session directory, and bundled asset directory
  (the last matters for immutable-store packaging).
- A single umbrella offline switch disabling every startup network side effect,
  alongside finer-grained individual toggles.
- Terminal capability overrides: hyperlinks, image protocol, truecolor, hardware
  cursor, escape timeout — each with an `auto` default.
- Standard proxy and external-editor variables.

## Dependency policy

Reuse aggressively; write no infrastructure a maintained crate already provides.
Justify in the docs any place a hand-rolled solution was unavoidable. Starting
points: `ratatui` and `crossterm` for the UI, `tokio` for async, `reqwest` with
an SSE adapter for providers, `serde` with a layered-config crate for TOML,
`clap` for the CLI, `thiserror` and `anyhow` for errors, `schemars` for schema
generation, `tracing` for diagnostics, `uuid` (v7), `unicode-width` and
`unicode-segmentation` for text measurement, `globset` for resource patterns, a
YAML frontmatter parser for skills, `syntect` or `tree-sitter` for highlighting,
and `rusqlite` if search moves beyond scanning. Substitute freely where a better
crate exists.

One caution: do **not** reach for a generic diff or state-tracking library if
you need structural change tracking. General-purpose diffing records effects
rather than intent and degrades pathologically on string-append and array-prepend
workloads — the exact shapes a streaming agent produces constantly.

## Security posture

The read/write/execute triad means unrestricted filesystem and command access.
Do not pretend otherwise or add theatrical guardrails. Document the model
plainly. Present containerization as a spectrum with honest trade-offs rather
than a single recommendation, and be explicit that a read-write bind mount means
container writes hit host files regardless of any other isolation — isolation
covers credentials, process, and network, not the workspace.

## Self-configuration documentation

A first-class deliverable. **One reference file per configurable axis**, plus an
index:

```
docs/config/index.md         intent -> file map
docs/config/layout.md
docs/config/theme.md
docs/config/keybindings.md
docs/config/tools.md
docs/config/providers.md
docs/config/models.md
docs/config/commands.md
docs/config/skills.md
docs/config/context.md
docs/config/sessions.md
docs/config/compaction.md
docs/config/telemetry.md
docs/config/environment.md
```

- Each file documents every key on its axis: type, default, allowed values,
  effect, and a worked TOML example.
- The index maps intent to file — "change the accent color", "rebind submit",
  "add a local model" — so the agent reads exactly one page, never the set.
- Expose it at runtime: a command that prints any page, and a queryable schema,
  so the agent can reconfigure a running instance without network access.
- **Generate these files from the same source of truth as the config types.**
  Drift is a build failure, not a documentation chore.
- Ship a JSON Schema for each of config, keybindings, and theme files so editors
  give completion and validation.

## Project values

- If code and documentation disagree, the code wins. Fix the doc and say so in
  the commit.
- Lead every design document with an explicit non-goals list.
- Prefer small closed enumerations over open-ended unions — it makes
  exhaustiveness checking and recovery-case coverage tractable.
- Keep validating data you do not control; stop revalidating invariants your own
  concurrency model already guarantees.
- Distrust your own benchmarks until you have verified the harness is not the
  thing being measured.
- Do not build migration machinery before the format stabilizes. Add it once,
  immediately before the first incompatible change.

## Deliverables

1. The four-crate workspace with the seams above.
2. The TOML configuration schema, layered loader, and trust gate.
3. Separate keybinding and theme file formats with schemas.
4. The per-axis self-configuration reference, generated and indexed.
5. Session storage with the entry tree, scope separation, and durability
   guarantees, plus a test proving clean close and hard kill are equivalent.
6. A working end-to-end path: launch, converse, call the four tools, load a
   skill, compact, fork a branch, persist, and live-reload after a config change.
