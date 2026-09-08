# The cross-agent skill directory convention

Research note for [tapir-dev/tp#8](https://github.com/tapir-dev/tp/issues/8).

**Question.** `tp` intends to adopt the existing cross-agent skill convention rather
than invent a format, and to document any deliberate deviation. This note pins down
what that convention actually specifies, then sorts `tp`'s stated requirements into
*agrees* and *deviation*.

## Sources

The convention is no longer Claude-Code-specific folklore. There is a formal open
specification with a reference validator:

| Source | Kind | URL |
| --- | --- | --- |
| Agent Skills specification | **Normative spec** | <https://agentskills.io/specification> |
| Agent Skills client implementation guide | Non-normative guidance for tool authors | <https://agentskills.io/client-implementation/adding-skills-support> |
| `agentskills/agentskills` (incl. `skills-ref` validator) | Reference implementation | <https://github.com/agentskills/agentskills> |
| Claude Code skills reference | One implementation (a superset) | <https://code.claude.com/docs/en/skills> |
| Anthropic Agent Skills overview / Skills API | Another implementation (a strict subset) | <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview> |

Throughout, claims are tagged **[SPEC]** (normative, from the specification),
**[GUIDE]** (recommended practice from the client implementation guide — explicitly
non-mandatory), **[IMPL]** (behaviour of a specific tool), or **[OBSERVED]** (measured
from live skill directories on this machine, see [Observed practice](#observed-practice)).

The distinction matters here: several things `tp` wants are *not* in the normative spec
but *are* in the guide, which changes them from "deviation" to "following the documented
convention".

---

## (a) What the convention specifies

### Directory layout

**[SPEC]** "A skill is a directory containing, at minimum, a `SKILL.md` file". The
canonical tree is:

```
skill-name/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
├── assets/           # Optional: templates, resources
└── ...               # Any additional files or directories
```

The sibling directory names are **conventional, not normative**. The spec heads that
section "Optional directories" and says: "A skill directory may contain any files and
directories beyond the required `SKILL.md`. The conventions below are recommendations
for organizing common types of content."

**[SPEC]** File references: "When referencing other files in your skill, use relative
paths from the skill root", and "Keep file references one level deep from `SKILL.md`.
Avoid deeply nested reference chains." The body has "no format restrictions";
recommended under 500 lines / <5000 tokens.

**[GUIDE]** The skill's **base directory** (the parent of `SKILL.md`) is the anchor an
implementation must track "to resolve relative paths and enumerate bundled resources".

### `SKILL.md` frontmatter

**[SPEC]** The portable field set is exactly six fields:

| Field | Required | Constraints (verbatim) |
| --- | --- | --- |
| `name` | **Yes** | Max 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen. |
| `description` | **Yes** | Max 1024 characters. Non-empty. Describes what the skill does and when to use it. |
| `license` | No | License name or reference to a bundled license file. |
| `compatibility` | No | Max 500 characters. Indicates environment requirements (intended product, system packages, network access, etc.). |
| `metadata` | No | Arbitrary key-value mapping for additional metadata (a map from string keys to string values). |
| `allowed-tools` | No | Space-separated string of pre-approved tools the skill may use. *(Experimental)* |

There is no `version` field and no `model` field in the spec; versions live inside
`metadata` (the spec's own example uses `metadata: {author: example-org, version: "1.0"}`).

**[IMPL]** Claude Code implements a superset, adding roughly a dozen more fields
(`when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`,
`user-invocable`, `disallowed-tools`, `model`, `effort`, `context`, `agent`,
`background`, `hooks`, `paths`, `shell`) and *relaxing* requiredness: `name` is "No —
Display name shown in skill listings. Defaults to the directory name", and
`description` is only "Recommended" — "If omitted, uses the first paragraph of markdown
content".

**[IMPL]** The Anthropic Skills API is *stricter* than the spec, adding that `name`
"Cannot contain XML tags" and "Cannot contain reserved words: 'anthropic', 'claude'".

Field naming is hyphenated (`allowed-tools`) everywhere; there is no `allowed_tools`
underscore variant in any primary source.

### Name rules

**[SPEC]** Verbatim, the required `name` field:

> * Must be 1-64 characters
> * May only contain unicode lowercase alphanumeric characters (`a-z`, `0-9`) and hyphens (`-`)
> * Must not start or end with a hyphen (`-`)
> * Must not contain consecutive hyphens (`--`)
> * **Must match the parent directory name**

Invalid examples given: `PDF-Processing`, `-pdf`, `pdf--processing`.

The brief's stated rule — 1–64 chars, lowercase alphanumeric and hyphens, no leading,
trailing, or consecutive hyphens — is **confirmed exactly**. The brief does not state
the fifth rule (name must match the parent directory name); see the deviations table.

### Discovery paths

**[GUIDE]** The specification "does not mandate where skill directories live (it only
defines what goes inside them)". The guide recommends scanning, per scope, both a
client-specific directory and the cross-client convention:

| Scope | Path | Purpose |
| --- | --- | --- |
| Project | `<project>/.<your-client>/skills/` | Your client's native location |
| Project | `<project>/.agents/skills/` | Cross-client interoperability |
| User | `~/.<your-client>/skills/` | Your client's native location |
| User | `~/.agents/skills/` | Cross-client interoperability |

> "The `.agents/skills/` paths have emerged as a widely-adopted convention for
> cross-client skill sharing. [...] scanning `.agents/skills/` means skills installed by
> other compliant clients are automatically visible to yours, and vice versa."

**[GUIDE]** On the ancestor walk, the guide lists "ancestor directories up to the git
root (useful for monorepos)" among additional locations implementations scan, alongside
`.claude/skills/` "for pragmatic compatibility", XDG config directories, and
user-configured paths.

**[IMPL]** Claude Code implements the ancestor walk normatively for its own path:
"Project skills load from `.claude/skills/` in the directory where you start Claude Code
and in every parent directory up to the repository root." Skills *below* the starting
directory load lazily: "Skills in nested `.claude/skills/` directories below your
starting directory don't load at startup. They load the first time Claude reads or edits
a file in the subdirectory that contains them, and stay available for the rest of the
session."

**[GUIDE]** Scan target and depth: look for "subdirectories containing a file named
exactly `SKILL.md`"; skip `.git/` and `node_modules/`; "Set reasonable bounds (e.g., max
depth of 4-6 levels, max 2000 directories)". So discovery is recursive-but-bounded, not
single-level. The guide's own diagram annotates a sibling `README.md` as
"← ignored (not a skill directory)".

**[GUIDE]** Trust: "Project-level skills come from the repository being worked on, which
may be untrusted [...] Consider gating project-level skill loading on a trust check."

### Allowed-tools and arbitrary metadata

**[SPEC]** `allowed-tools` is "A space-separated string of tools that are pre-approved to
run", example `allowed-tools: Bash(git:*) Bash(jq:*) Read`, and is flagged
"Experimental. Support for this field may vary between agent implementations."

Semantics are a **grant, not a restriction** — "pre-approved". **[IMPL]** Claude Code
makes this explicit: `allowed-tools` are "Tools Claude can use without asking permission
during the turn that invokes this skill", with a separate `disallowed-tools` field for
"Tools removed from Claude's available pool while this skill is active". Claude Code also
widens the syntax: "Accepts a space- or comma-separated string, or a YAML list."

**[SPEC]** Arbitrary data has a designated home: `metadata` is "A map from string keys to
string values. Clients can use this to store additional properties not defined by the
Agent Skills spec. We recommend making your key names reasonably unique to avoid
accidental conflicts."

Crucially, **arbitrary *top-level* keys are not part of the convention** — the spec's
frontmatter table is closed, and strict consumers (the Skills API, claude.ai upload,
`package_skill.py`) hard-error on unknown top-level keys rather than ignoring them.
Claude Code, by contrast, tolerates its own superset.

### Validation failures and name collisions

**[GUIDE]** Recommended validation is explicitly **lenient**, and deliberately relaxes
the spec's own name rules:

| Condition | Recommended behaviour |
| --- | --- |
| Name doesn't match the parent directory name | warn, load anyway |
| Name exceeds 64 characters | warn, load anyway |
| Description missing or empty | skip the skill, log the error |
| YAML completely unparseable | skip the skill, log the error |

> "The [specification] defines strict constraints on the `name` field (matching the
> parent directory, character set, max length). The lenient approach above deliberately
> relaxes these to improve compatibility with skills authored for other clients."

Plus: "Record diagnostics so they can be surfaced to the user [...] but don't block skill
loading on cosmetic issues", and a recommended YAML-repair fallback for the common
unquoted-colon-in-description case.

**[IMPL]** Claude Code degrades rather than skips: "If the frontmatter YAML is malformed,
Claude Code loads the skill body with empty metadata, so `/skill-name` still works but
Claude has no `description` to match against."

**[GUIDE]** Collisions: "When two skills share the same `name`, apply a deterministic
precedence rule. The universal convention across existing implementations:
**project-level skills override user-level skills.**" Within one scope, "either
first-found or last-found is acceptable — pick one and be consistent. Log a warning when
a collision occurs so the user knows a skill was shadowed."

**[IMPL]** Note the contradiction: Claude Code inverts the cross-scope rule — "Across
levels, enterprise overrides personal, and personal overrides project." Plugin skills
sidestep collisions entirely via a `plugin-name:skill-name` namespace.

### Bare top-level Markdown files

**[SPEC]** Not part of the convention. The unit of discovery is a *directory* containing
"a file named exactly `SKILL.md`"; **[GUIDE]** a loose `README.md` beside skill
directories is "ignored (not a skill directory)".

This is distinct from Claude Code's `.claude/commands/*.md` slash commands, which *are*
bare Markdown files with frontmatter but are a **separate mechanism** with its own
directory — `.claude/commands/deploy.md` yields `/deploy` from the *filename*, whereas
`.claude/skills/deploy/SKILL.md` yields `/deploy` from the *directory name*. Confusing
the two is the main hazard when reading second-hand descriptions of "skills".

### Progressive disclosure

**[SPEC]** Three tiers: metadata (`name` + `description`, ~100 tokens, loaded at startup
for all skills), instructions (full body, <5000 tokens recommended, loaded on
activation), resources (loaded only when required). **[GUIDE]** "Each skill adds roughly
50-100 tokens to the catalog."

---

## (b) Where the brief agrees with the convention

| Brief requirement | Convention | Verdict |
| --- | --- | --- |
| A skill is a directory containing `SKILL.md`: frontmatter plus Markdown body | [SPEC] identical | **Agrees** |
| Sibling directories hold scripts, references, assets, referenced by relative path | [SPEC] `scripts/`, `references/`, `assets/`; "use relative paths from the skill root" | **Agrees** (and the brief is right to treat them as conventional, not mandatory) |
| `name`, `description` required; a skill without one does not load | [SPEC] both required; [GUIDE] "Description is missing or empty → skip the skill" | **Agrees** |
| Name rules: 1–64 chars, lowercase alphanumeric and hyphens, no leading/trailing/consecutive hyphens | [SPEC] verbatim match on all four rules | **Agrees** |
| Optional `license` | [SPEC] optional field, defined | **Agrees** — *not* a deviation |
| Optional `compatibility` | [SPEC] optional field, max 500 chars | **Agrees** — *not* a deviation |
| Arbitrary `metadata` | [SPEC] optional `metadata` map for exactly this purpose | **Agrees** — *not* a deviation |
| An allowed-tools list | [SPEC] `allowed-tools`, marked Experimental | **Agrees**, with a syntax caveat (D6) |
| Unknown fields are ignored | [GUIDE] lenient posture; [IMPL] Claude Code tolerates its superset | **Agrees with the guide**; diverges from strict API consumers |
| Lenient validation: most violations warn and still load | [GUIDE] "warn, load anyway" table; "don't block skill loading on cosmetic issues" | **Agrees** — *not* a deviation |
| Global skills directory + project one, trust-gated | [GUIDE] user and project scopes; "Consider gating project-level skill loading on a trust check" | **Agrees** |
| Walk up ancestor directories to the repository root for the shared convention path | [GUIDE] "ancestor directories up to the git root"; [IMPL] Claude Code does exactly this for `.claude/skills/` | **Agrees** |
| Recursively discover any directory containing a `SKILL.md` | [GUIDE] recursive scan for "subdirectories containing a file named exactly `SKILL.md`" | **Agrees**, if bounded (D7) |
| Only name and description enter the system prompt; body loads on demand | [SPEC] progressive disclosure, tiers 1/2/3 | **Agrees** |
| Name collisions warn and resolve deterministically | [GUIDE] "apply a deterministic precedence rule [...] Log a warning" | **Agrees** on mechanism; see D5 on direction |
| Skill content is untrusted and can carry executable scripts | [GUIDE] trust considerations; `scripts/` is a first-class directory | **Agrees** |
| A flag that hides the skill from the system prompt, reachable only by explicit command | [GUIDE] filtering: "The skill has opted out of model-driven activation (e.g., via a `disable-model-invocation` flag)"; "Hide filtered skills entirely from the catalog" | **Agrees with the guide**; deviates from the spec's field list (D2) |
| Explicit user invocation of skills matters | [GUIDE] "Users should also be able to activate skills directly [...] The most common pattern is a slash command or mention syntax" | **Agrees** |

Four items the ticket flagged as *candidate* deviations turn out **not to be deviations**:
`license`, `compatibility`, arbitrary `metadata`, and lenient validation are all part of
the convention as published (the first three normative, the fourth in the implementation
guide).

## (c) Where the brief would be a documented deviation

| # | Brief requirement | What the convention says | Why it is a deviation | Suggested posture |
| --- | --- | --- | --- | --- |
| D1 | Accept **bare top-level Markdown files** with valid frontmatter as skills, in the tool-specific directories | [SPEC] the unit is a directory containing `SKILL.md`; [GUIDE] loose `.md` files beside skill dirs are "ignored (not a skill directory)" | Genuinely outside the convention. No primary source accepts a bare `foo.md` as a skill. | Keep it, but scope it *strictly* to `tp`'s own directory, never the shared `.agents/skills/` path — otherwise `tp` produces artifacts other tools silently drop. Document that such files are non-portable. |
| D2 | A flag that **hides the skill from the system prompt** | `disable-model-invocation` is not one of the six spec fields; it is [IMPL] Claude Code and [GUIDE] acknowledged generically | Semantically endorsed by the guide, but the field name is not normative, and strict consumers hard-error on it | Adopt the name `disable-model-invocation` verbatim for interop (it is what exists in the wild — see Observed practice), and document it as an extension beyond the six-field spec. |
| D3 | **Unknown fields are ignored** | Lenient per [GUIDE], but strict consumers (Skills API, claude.ai upload) hard-error: `Unexpected key(s) in SKILL.md frontmatter: … Allowed properties are: allowed-tools, compatibility, description, license, metadata, name` | Not a deviation from the guide, but it means `tp`-authored skills can fail elsewhere | Ignore-and-warn is right for loading. Consider a `tp skill validate --strict` that reports non-portable keys. |
| D4 | Name rules omit **"must match the parent directory name"** | [SPEC] lists it as a fifth, normative rule | The brief's list is otherwise verbatim, so the omission reads as an oversight rather than a decision | Either add the rule (warn-and-load per [GUIDE]) or state explicitly that `tp` derives the command name from the directory and treats `name` as a display label, which is what Claude Code does. |
| D5 | Collision policy: **"first discovered wins"** | [GUIDE] "project-level skills override user-level skills"; [IMPL] Claude Code inverts this (personal over project) | "First discovered wins" is only deterministic once discovery order is pinned. The convention's cross-scope rule is about *scope*, not traversal order. | Define scope precedence explicitly and pick a side of the existing contradiction. Documenting a deviation here is unavoidable — the two reference points disagree. |
| D6 | `allowed-tools` as a list | [SPEC] "space-separated **string**"; [IMPL] Claude Code also accepts comma-separated or a YAML list | Minor. Accepting a YAML list is a superset, but *emitting* one is non-portable. | Parse all three forms; emit the space-separated string. Note the field is marked Experimental upstream. |
| D7 | "Recursively discover any directory containing a `SKILL.md`", no stated bound | [GUIDE] "Set reasonable bounds (e.g., max depth of 4-6 levels, max 2000 directories)"; skip `.git/`, `node_modules/` | Unbounded recursion in a large monorepo is a startup-latency hazard the guide explicitly calls out | Add bounds and exclusions to the brief; a missing constraint rather than a philosophical deviation. |
| D8 | A skill without `name`/`description` does not load | [SPEC] agrees, but [IMPL] Claude Code makes both optional with fallbacks (`name` → directory name, `description` → first paragraph) | Being stricter here is *more* spec-compliant than Claude Code, but means `tp` refuses skills Claude Code loads | Follow the [GUIDE] split, which the brief already half-matches: missing `description` → skip; missing `name` → warn and fall back to the directory name. |

One additional gap: the brief specifies the shared-convention *walk* but never names the
shared path. The convention's answer is `.agents/skills/` at both project and user scope
— that is the concrete interop surface and should be named explicitly in `tp`'s docs.

---

## Observed practice

Evidence from live skill directories on this machine (`/home/ijanc/.agents/skills/`, 38
skill directories installed by a third-party cross-agent package manager). This is
**observed practice, not specification**, but it shows what the convention looks like when
actually exercised.

Setup: `~/.claude/skills` is a **symlink** to `/home/ijanc/.agents/skills/`. Claude Code
does not scan `~/.agents/skills/` natively, so the symlink is how the cross-agent
convention gets bridged into a client that only knows its own path — concrete evidence
that `.agents/skills/` is a real interop surface, and that native support for it (which
`tp` plans) removes a workaround. The manager's lockfile (`~/.agents/.skill-lock.json`,
`version: 3`, 55 entries) records a `lastSelectedAgents` list of 14 target tools (amp,
antigravity, antigravity-cli, cline, codex, cursor, deepagents, gemini-cli,
github-copilot, kimi-code-cli, opencode, warp, zed, claude-code) — the cross-agent intent
is not hypothetical.

| Metric | Result |
| --- | --- |
| Skill directories | 38 |
| `SKILL.md` present | 38 / 38 |
| Bare top-level `.md` files in the skills root | **0** |
| `name` present | 38 / 38 |
| `description` present | 38 / 38 |
| `name` matches parent directory name | **38 / 38** |
| `name` passes the spec charset rules | 38 / 38, zero violations |
| Frontmatter opens on line 1 | 38 / 38 |
| Only `name` + `description` | 16 / 38 (42%) |
| `disable-model-invocation: true` | 22 / 38 (58%) |
| `argument-hint` | 4 / 38 |
| `license`, `compatibility`, `metadata`, `allowed-tools`, `version`, `model` | **0 / 38 each** |

Only **four distinct frontmatter keys appear in the entire corpus**: `name`,
`description`, `disable-model-invocation`, `argument-hint`. Description lengths run 36 to
421 characters — all well inside the 1024 cap.

Two findings bear directly on the deviations:

1. **`disable-model-invocation` is the de-facto name for the hide-from-prompt flag**
   (D2). It is the third most common key in the corpus, used by a clear majority of
   skills, despite not being in the six-field spec. Adopting any other spelling in `tp`
   would be the real interop break. Reinforcing this: 37 of 38 skills carry a sidecar
   `agents/openai.yaml` written by the package manager, and for skills flagged
   `disable-model-invocation: true` it contains
   `policy: {allow_implicit_invocation: false}` — the same semantic re-expressed for a
   non-Claude runtime, in snake_case. Tooling is already routing around the spec's
   narrowness with sidecar files.

2. **Reference files sit flat at the skill root, not in `references/`.** Subdirectory
   usage across the corpus: `agents/` 37, `scripts/` 2, `references/` **0**, `assets/`
   **0**. The 22 non-`SKILL.md` Markdown files all sit at depth 1 beside `SKILL.md`
   (`SKILL-MECHANICS.md`, `ADR-FORMAT.md`, `triage-labels.md`, …), matching Anthropic's
   own overview examples rather than the spec's `references/` recommendation. Relative
   references are one level deep as the spec advises, in both bare
   (`](SKILL-MECHANICS.md)`) and explicit (`](./triage-labels.md)`) form; the only
   subdirectory reference observed is `](scripts/block-dangerous-git.sh)`. **`tp` must
   not assume `references/` or `assets/` exist** — resolve any relative path against the
   skill root instead.

Also: `~/.claude/commands/` on this machine contains exactly one bare `.md` file
(`orchestrate.md`), in a different directory from skills entirely — the
separate-mechanism distinction from D1, visible in practice.

Finally, 22 of these 38 skills would be **rejected outright** by the strict Skills API
(they use `disable-model-invocation` or `argument-hint`). Real-world skills are already
routinely non-portable to the strict path, which is context for how much weight to give
strict-consumer compatibility in D3.

## Open questions

- D5 is unresolvable by research alone: the guide says project overrides user, Claude
  Code says personal overrides project. `tp` has to pick, and whichever it picks is a
  documented deviation from one of the two references.
- Does `tp` want to emit `agents/*.yaml` sidecars for other runtimes, or treat them as
  foreign files it ignores? The corpus suggests they are becoming load-bearing for
  cross-agent semantics the six-field spec cannot express.
