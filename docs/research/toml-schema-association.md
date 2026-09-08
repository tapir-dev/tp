# How a TOML editor associates a local JSON Schema file

Research note for [issue #30](https://github.com/tapir-dev/tp/issues/30). Survey date: **2026-09-08**.

D8 left one external fact unverified: whether a glob→schema mapping pointing at an
absolute local path is a thing a TOML editor will actually read. This note settles
it against the two implementations that exist, their source, and a running binary
of each.

**Every claim below carries a verification marker.** The load-bearing answers
(§4, §5, §6) are empirical, because on this question the documentation is wrong
in at least two places and silent in four more.

| Marker | Meaning |
| --- | --- |
| `[D]` | Verified — the claim appears literally in primary documentation |
| `[S]` | Verified — read out of the tool's own source code |
| `[E]` | Verified empirically — reproduced against a running binary during this survey |
| `[X]` | Derived — follows from a verified rule, but is not stated in any source |
| `[I]` | Inferred from an issue (an open ticket is evidence about the state of the world) |
| `[?]` | Could not confirm — treat as unknown, not as absence |

**Binaries used for `[E]`**: `taplo 0.10.0` (`taplo-cli` 0.10.0, `taplo-lsp` 0.8.0,
`taplo-common` 0.6.0, installed from crates.io with `--features lsp`); `tombi 1.5.2`
(x86_64-unknown-linux-gnu, from npm); `schemars 1.2.2`; `rustc`/`cargo` 1.98.0.
LSP behaviour was reproduced by driving each server's stdio JSON-RPC directly, so
"what the editor shows" below means the actual `textDocument/publishDiagnostics`,
`textDocument/completion` and `textDocument/hover` payloads the server emits.

**Source read for `[S]`**: `tamasfe/taplo` at `08f343be` (2026-07-28, one commit
past the 0.10.0 release) and `tombi-toml/tombi` at `825161b6` (2026-09-08).

---

## 1. Executive summary

1. **The gesture works, but not as one file.** There are two TOML language servers
   in the field, they do not share a mapping-file format, and neither reads the
   other's. One written artifact does **not** serve all editors; **two** do —
   `.taplo.toml` and `tombi.toml` at the repository root — and between them they
   cover every editor surveyed, because every editor integration is a shell around
   one of these two servers and both servers read their config file rather than
   editor settings. No `.vscode/settings.json`, `.helix/languages.toml` or
   `.zed/settings.json` is required. `[E]` Both must sit at the **workspace-folder
   root** — see finding 5a.

2. **A bare absolute filesystem path works in three of the four mechanisms, and
   fails silently in the fourth — which is the one the D8 wording implies.** The
   `#:schema` directive accepts one `[E]`. Taplo's `.taplo.toml` `schema.path`
   accepts one `[E]`. Tombi's `tombi.toml` `[[schemas]].path` accepts one `[E]`.
   But `evenBetterToml.schema.associations` — the VS Code setting — rejects it with
   `invalid schema url error=relative URL without a base`, logs to a trace channel
   nobody reads, and produces **no diagnostic and no completion at all**. `[E]`
   There it must be a `file://` URI.

3. **Taplo silently drops the doc-comment of every key whose Rust type is a named
   type.** `schemars` emits `{"description": …, "$ref": …, "default": …}` for such
   a field; taplo's `collect_schemas` returns early the moment it sees `$ref`,
   discarding the siblings (§7.2 `[S]`). Hovering `log_file: ConfigPath` shows
   *"A filesystem path declared in config."* — the newtype's doc — never the key's
   own. `[E]` Under D12 every key carries a mandatory doc-comment; in taplo, for
   every enum-typed and every `ConfigPath`-typed key, that doc-comment is invisible.

4. **One `schemars` setting fixes it: `inline_subschemas = true`.** With `$defs`
   eliminated, every property carries its own `description` and `default` inline,
   and taplo shows them — hover on a `ConfigPath` key becomes *"Where the log
   goes."* and hover on an enum key gains the field's own sentence. `[E]` The cost
   is a larger schema and a hard prohibition on recursive types.

5. **Taplo's relative-path handling is anchored to the wrong thing, twice, and both
   failures are silent.** A relative `include` glob or `schema.path` in
   `.taplo.toml` is resolved against the **process CWD** in the CLI `[S][E]` and
   against the **LSP workspace root** in the server `[S][E]` — never against the
   config file that contains it, which the config's own doc-comments admit
   (*"Relative paths are **not** relative to the configuration file"*) `[S]`.
   Running `taplo lint` from a subdirectory of a project whose `.taplo.toml` lives
   at the root therefore validates nothing, exits 0, and says nothing. `[E]`

5a. **And in VS Code, `.taplo.toml` is not discovered by a walk at all.** Even
   Better TOML runs the bundled **WASM** build, whose `findConfigFile` is a JS
   callback that `path.join`s the two file names onto the directory it was handed
   and returns — no `parent()` loop `[S]`. The ancestor walk verified against
   `taplo lsp stdio` `[E]` is a property of the native binary that Helix, Neovim
   and the CLI run, and does not transfer. The mapping file must be at the
   workspace-folder root exactly.

6. **`"./…"` in `evenBetterToml.schema.associations` resolves one directory too
   high.** Taplo joins the value onto the workspace-root URL, which has no trailing
   slash, so `Url::join` replaces the last segment: workspace `file:///tmp/x/proj`
   plus `./schemas/config.json` yields `file:///tmp/schemas/config.json`. `[S][E]`
   There is no working relative form for that setting; it is absolute `file://` or
   nothing.

7. **Tombi gets every one of these right.** Bare absolute and bare relative paths
   both work in the directive and in `tombi.toml` `[E]`; relative paths and include
   globs are anchored to the **config file's own directory** `[S][E]`; the LSP
   discovers `tombi.toml` by walking up from **the edited document's directory**,
   not from the workspace root `[S]`, which is exactly D14's semantics; and it
   consumes the `schemars` 2020-12 output without losing a single `description` or
   `default` `[E]`. It also has an explicit `JsonSchemaDialect` enum for draft-07 /
   2019-09 / 2020-12 `[S]`, where taplo hands the document to `jsonschema` 0.17.1
   and hopes `[S]`.

8. **Zed is no longer a taplo editor.** Zed's own docs say TOML language-server
   support comes from the **Tombi** extension `[D]`; Helix ships *both*
   (`language-servers = [ "taplo", "tombi" ]`) `[S]`; `nvim-lspconfig` ships both
   `[S]`. A taplo-only artifact would leave Zed users with nothing.

9. **The versioned cache path is the gesture's real weakness, not the mechanism.**
   #11-D6 version-keys the cache directory `[D]`, so an absolute mapping written
   today names `…/tp/<version>/schemas/config.json` and goes stale on the next
   upgrade — leaving a `.taplo.toml` in the user's repository pointing at a deleted
   file. Taplo reports that as one line in a trace channel; the user sees
   completion simply stop working. `[X]`

10. **The `#:schema` directive truncates at the first space.** Taplo's parser is
    `directive_content.split_whitespace()` taking one token `[S]`, so
    `#:schema /home/u/my cache/schemas/config.json` loads
    `file:///home/u/my` `[E]`. `.taplo.toml`'s `schema.path` has no such limit
    `[E]`, and tombi's directive has no such limit `[E]`. Moot for D8 — it forbids
    injecting a directive anyway — but it kills the directive as a fallback on any
    machine whose cache path contains a space.

11. **The third mechanism, a `$schema` key at the document root, is self-defeating
    for `tp`.** Taplo supports it `[S][E]`; tombi ignores it `[E]`. And because D7
    makes an unknown key an error and the schema carries
    `additionalProperties: false`, taplo validates the `$schema` key against the
    schema and reports *"Additional properties are not allowed ('$schema' was
    unexpected)"*. `[E]` It cannot be used.

12. **`oneOf` diagnostics are bad in taplo and acceptable in tombi.** One wrong
    enum tag in a `[provider]` table produces **five identical** taplo errors
    reading *"…is not valid under any of the schemas listed in the 'oneOf'
    keyword"*, smeared across every key of the table `[E]`. Tombi reports *"the
    value must be const value "anthropic", but found "wrong""* at the offending
    value `[E]`. Neither approaches D17's contract, which is `tp`'s own loader's
    job regardless.

---

## 2. The four mechanisms

Association is not one thing. Ranked by taplo's own precedence constants
(`crates/taplo-common/src/schema/associations.rs`) `[S]`:

| Priority | Mechanism | Where it lives |
| --- | --- | --- |
| `MAX` | `taplo/associateSchema` LSP notification | editor plugin, runtime |
| 75 | `#:schema` **directive** | first line of the TOML file |
| 70 | `$schema` **root key** | inside the TOML document |
| 60 | `evenBetterToml.schema.associations` | editor settings, LSP only |
| 51 | `.taplo.toml` `[[rule]]` + `[rule.schema]` | project file |
| 50 | `.taplo.toml` global `[schema]` | project file |
| 25 | schema catalog (`schemastore.org`) | network |
| 10 | built-in (`taplo://taplo.toml`) | binary |

Tombi's ladder is shorter and is documented as: `#:schema` directive, then
`tombi.toml`, then the catalog `[D]`. There is **no editor-settings rung** — the
Tombi VS Code extension contributes exactly three settings, `tombi.path`,
`tombi.args`, `tombi.env`, and nothing about schemas `[S]`.

### 2.1 Who consumes what

| Mechanism | taplo CLI | taplo-lsp | tombi CLI | tombi-lsp |
| --- | --- | --- | --- | --- |
| `#:schema` directive | yes `[E]` | yes `[E]` | yes `[E]` | yes `[X]` |
| `$schema` root key | yes `[E]` | yes `[X]` | **no** `[E]` | **no** `[X]` |
| `.taplo.toml` | yes `[E]` | yes `[E]` | n/a | n/a |
| `tombi.toml` | n/a | n/a | yes `[E]` | yes `[E]` |
| editor settings | **no** `[S]` | yes `[E]` | n/a | n/a (none exist) |

The directive and the config file both live in `taplo-common` / tombi's
`schema-store`, i.e. in the shared core, which is why the CLI and the server agree
on them `[S]`. `evenBetterToml.schema.associations` lives in `taplo-lsp`'s
`LspConfig` and is unreachable from the CLI `[S]`.

### 2.2 Exact syntax

**Directive** — must be a *header* comment, preceded only by other comments or
directives; multiple `#:schema` directives in one document are explicitly
undefined behaviour `[D]`:

```toml
#:schema ./foo-schema.json
foo = "bar"
```

Taplo's docs state it accepts *"a relative file path or an URL"* and that
*"Relative paths are relative to the document file"* `[D]`. The docs do not
mention absolute paths; the source does, and they work (§4).

**`$schema` root key** — a plain TOML key at the document root, read by taplo only:

```toml
"$schema" = "file:///abs/path/config.json"
```

**`.taplo.toml`** — file names `.taplo.toml`, then `taplo.toml` `[S][D]`:

```toml
[[rule]]
include = [".tp/config.toml"]

[rule.schema]
path = "/home/u/.cache/tp/0.1.0/schemas/config.json"
```

`schema.path` is documented as *"A local file path to the schema, overrides `url`
if set. URLs are also accepted here, but it's not a guarantee and might change in
newer releases. Please use the `url` field instead whenever possible."* `[S]`
`schema.url` is typed `Option<Url>` and documented as *"A full absolute URL to the
schema. … supported schemes are `http`, `https`, `file` and `taplo`"* `[S]`.
Rule `include`/`exclude` are globs; overlapping rules resolve last-wins `[D]`.

**`tombi.toml`** — file names `.tombi.toml`, `tombi.toml`, `.config/tombi.toml`,
or `[tool.tombi]` inside `pyproject.toml` `[S]`:

```toml
[[schemas]]
path = "/home/u/.cache/tp/0.1.0/schemas/config.json"
include = [".tp/config.toml"]
```

`path` is a plain `String` `[S]`; `include` is a required non-empty glob list
`[S]`; `exclude` is optional.

**Editor settings (taplo-lsp only)** — the LSP config section defaults to the
string `evenBetterToml` `[S]`, which is why the VS Code extension's settings *are*
the language server's settings. `associations` is a `HashMap<String, String>` whose
key the extension documents as *"a regular expression … used to associate schemas
with absolute document URIs"* and whose value *"must be an absolute URI to the JSON
schema"* `[D]`. It is a **regex**, not a glob — unlike `.taplo.toml`'s `include`.

---

## 3. Question 2, part one: does a local path work in the directive?

Taplo's resolution, verbatim from `SchemaAssociations::add_from_document` `[S]`:

```rust
let schema_url: Url = match value.parse() {
    Ok(url) => url,
    Err(error) => {
        tracing::debug!(%error, "invalid url in directive, assuming file path instead");
        if self.env.is_absolute(Path::new(value)) {
            match format!("file://{value}").parse() { … }
        } else {
            match doc_url.join(value) { … }
        }
    }
};
```

So: parse as a URL; if that fails, an **absolute** path becomes `file://<path>`, and
anything else is joined onto the **document's own URL**. Both branches exist, and
both work.

| Directive value | taplo | tombi |
| --- | --- | --- |
| `/abs/path/config.json` | works `[E]` | works `[E]` |
| `./local/config.json` | works `[E]` | works `[E]` |
| `local/config.json` | works `[E]` | works `[E]` |
| `../../cache/0.1.0/schemas/config.json` | works `[E]` | works `[E]` |
| `file:///abs/path/config.json` | works `[E]` | works `[E]` |
| `~/nope.json` | **no expansion**; resolves to `<doc dir>/~/nope.json` `[E]` | same `[E]` |
| `/abs/my cache/config.json` | **truncates at the space** → `file:///abs/my` `[E]` | works `[E]` |

Relative directive paths are anchored to the **document file's directory** in both
tools — `doc_url.join(value)` in taplo `[S]`, verified `[E]`; documented as such by
taplo `[D]`.

The space truncation is not a URL problem. `Url::parse("file:///home/u/my
cache/config.json")` succeeds and percent-encodes the space `[E]`. It is taplo's
directive lexer: `text.strip_prefix("#:")`, then `split_whitespace()`, then
`.next()` twice — name, value, done `[S]`.

The Windows form is fine, contrary to what `format!("file://{value}")` suggests:
`Url::parse("file://C:\\Users\\First Last\\cache\\config.json")` yields host `None`
and path `/C:/Users/First%20Last/cache/config.json` `[E]`, because the URL spec
special-cases a drive letter in the authority position of a `file:` URL. On Windows
`to_file_path()` maps that back to `C:\…` `[X]`.

Failure is loud in the CLI (`ERROR … failed to load schema file://… ` plus a
non-zero exit `[E]`) and, in tombi, is a *warning with a source location* pointing
at the directive `[E]`. In the taplo **LSP** a bad directive produces no user-visible
signal at all beyond the trace channel `[E]`.

---

## 4. Question 2, part two: does a local path work in the mapping file?

This is the load-bearing table.

| Mechanism | bare absolute | bare relative | `./` relative | `file://` URI |
| --- | --- | --- | --- | --- |
| `.taplo.toml` `schema.path` | **yes** `[E]` | yes, anchored wrong (§5) `[E]` | yes, anchored wrong `[E]` | yes `[E]` |
| `.taplo.toml` `schema.url` | **no** `[E]` | no `[X]` | no `[X]` | yes `[E]` |
| `evenBetterToml.schema.associations` | **no** `[E]` | no `[S]` | **broken** (§4.2) `[E]` | yes `[E]` |
| `tombi.toml` `[[schemas]].path` | **yes** `[E]` | yes, anchored right `[E]` | yes `[E]` | yes `[E]` |
| `$schema` root key (taplo) | **no** `[E]` | no `[S]` | yes `[E]` | yes `[E]` |
| `taplo lint --schema` | **no** `[E]` | no `[X]` | no `[X]` | yes `[X]` |

### 4.1 `schema.url` fails the *whole config file*, quietly

`SchemaOptions.url` is `Option<Url>`, so a bare path is a **deserialisation**
error, not a schema error. Taplo's reaction:

```
WARN taplo:load_config: invalid configuration file error=TOML parse error at line 1, column 1
invalid value: string "/tmp/…/config.json", expected relative URL without a base
```

…and it then proceeds with `Config::default()` `[E]`. So one wrong key silently
discards the user's formatter settings too. In the LSP the same failure path is
`tracing::warn!(%error, "failed to load workspace configuration")` `[S]` — invisible.

`schema.path` is the field that accepts a path, and it *overrides* `url` when both
are set `[S]`. It resolves in `Options::prepare` `[S]`:

```rust
let p = if e.is_absolute(Path::new(&p)) { PathBuf::from(p) } else { base.join(p).normalize() };
Some(Url::parse(&format!("file://{}", p.to_string_lossy()))?)
```

Unlike the directive, this path may contain spaces `[E]` — `Url::parse` encodes
them and nothing splits on whitespace.

### 4.2 The `"./…"` off-by-one in editor settings

`taplo-lsp`'s `WorkspaceState::initialize` `[S]`:

```rust
let url = if schema_url.starts_with("./") {
    self.root.join(schema_url)
} else {
    schema_url.parse()
};
```

`self.root` is the workspace-folder URI, which clients send **without** a trailing
slash. `Url::join` then replaces the final path segment. Reproduced: workspace
`file:///tmp/tptest/proj`, setting value `"./schemas/config.json"`, resulting
schema URL `file:///tmp/schemas/config.json` — the sibling of the project, not a
child `[E]`. The server logs `failed to load schema` and emits an empty diagnostic
list `[E]`.

Consequence: **there is no working project-relative form of
`evenBetterToml.schema.associations`.** A machine-specific absolute `file://` URI
is the only option, which is precisely what makes a checked-in
`.vscode/settings.json` a bad artifact for this.

### 4.3 Tombi resolves the way one would expect

`SchemaStore::load_config_schemas` `[S]`:

```rust
let schema_uri = if let Ok(schema_uri) = SchemaUri::from_str(schema.path()) {
    schema_uri
} else if let Ok(schema_uri) = match base_dir_path {
    Some(base_dir_path) => SchemaUri::from_file_path(base_dir_path.join(schema.path())),
    None => SchemaUri::from_file_path(schema.path()),
} { … }
```

`base_dir_path` is `config_base_dir(config_path)` — the directory holding
`tombi.toml`, or its parent when the config is at `.config/tombi.toml` `[S]`.
`Path::join` with an absolute argument yields the absolute argument, so the same
line serves both cases. Verified from a sub-sub-directory with both an absolute
and a `./`-relative `path`: both validated `[E]`.

---

## 5. Question 3: where the mapping file is looked for

**Taplo discovers by walking up — but anchors relative paths somewhere else.**
`Environment::find_config_file` loops `read_dir` / `p.parent()` until the
filesystem root `[S]`. The anchor for everything *inside* the file is a different
value:

| | discovery starts at | walks up? | `base` for relative `include` / `schema.path` |
| --- | --- | --- | --- |
| taplo CLI | process CWD `[S]` | yes, to `/` `[S][E]` | **process CWD** `[S][E]` |
| taplo-lsp, native binary | LSP workspace root `[S]` | yes, above it `[S][E]` | **workspace root** `[S][E]` |
| taplo-lsp, VS Code bundled | LSP workspace root `[S]` | **no — that one directory only** `[S]` | workspace root `[S]` |
| tombi CLI | process CWD `[S]` | yes, to `/` `[S][E]` | **config file's directory** `[S][E]` |
| tombi-lsp | **the edited document's directory** `[S]` | yes `[S]` | config file's directory `[S]` |

**The walk is the `Environment`'s job, and VS Code's environment does not walk.**
`Environment::find_config_file` is a trait method; the native implementation loops
on `p.parent()` `[S]`, but Even Better TOML runs the **WASM** build by default
(`evenBetterToml.taplo.bundled` defaults `true`, and the bundled path loads
`dist/server.js`, which wraps the `@taplo/lsp` WASM module) `[S]`, and that build
delegates `find_config_file` to a JS callback which is, in full `[S]`:

```js
findConfigFile: from => {
  const fileNames = [".taplo.toml", "taplo.toml"];
  for (const name of fileNames) {
    try {
      const fullPath = path.join(from, name);
      fs.accessSync(fullPath);
      return fullPath;
    } catch {}
  }
}
```

No loop, no `parent()`. So in **VS Code**, `.taplo.toml` must sit exactly at the
workspace-folder root or it is not found at all — where Helix, Neovim and the CLI,
which run the native binary, walk up from there. The `[E]` walk results above were
obtained against the native `taplo lsp stdio` and do **not** transfer to VS Code.

The taplo config's own doc-comments say this outright: *"Relative paths are **not**
relative to the configuration file, but rather depends on the tool using the
configuration."* `[S]` The published docs say `include` globs are *"relative to the
working directory (or root of the workspace)"* `[D]` and describe discovery as
*"the working directory or workspace root"* — understating the walk `[D]`.

**The failure this produces is silent.** With `.taplo.toml` at `proj/` containing
`include = ["**/.tp/config.toml"]`, `taplo lint ../../.tp/config.toml` run from
`proj/sub/deeper` logs `found configuration file path="/tmp/…/proj/.taplo.toml"`,
collects the file, matches no rule (the glob was made absolute against
`proj/sub/deeper`), emits nothing, and **exits 0** `[E]`. The same command with an
absolute `include` glob validates and exits non-zero `[E]`. Same for `schema.path`:
from the subdirectory, `./schemas/config.json` resolves to
`file:///tmp/…/proj/sub/deeper/schemas/config.json` `[E]`.

Under the **LSP** the anchor is the workspace root, so relative `include` and
relative `schema.path` both behave correctly for an editor opened at the project
root `[E]` — including when `.taplo.toml` itself sits *above* the workspace root
`[E]`.

**Against D14.** `tp`'s project layer is the *nearest* `.tp/config.toml` walking up
from CWD to the repository root, so in a monorepo it may live at
`repo/packages/foo/.tp/config.toml`. Taplo only walks **up** from the workspace
root; a `.taplo.toml` written next to that nested `.tp/` is *below* the root of an
editor opened on the repository and will never be found `[X]`. Tombi's LSP, which
walks up from the edited document's own directory `[S]`, finds it. **The gesture
must write at the repository root, not beside the `.tp/` directory it describes** —
and its `include` glob must then be `**/.tp/config.toml` rather than
`.tp/config.toml`.

---

## 6. Question 4: the dialect the Rust derive emits

### 6.1 What `schemars` emits, and whether it is configurable

`schemars` 1.2.2 (current on crates.io at survey date) defaults to
**draft 2020-12**, with `$defs`, `const`, and `$ref` carrying sibling keywords `[E]`:

```json
"mode": { "description": "Rendering mode.", "$ref": "#/$defs/RenderMode", "default": "inline" }
```

It **is** configurable. `SchemaSettings::draft07()` emits
`http://json-schema.org/draft-07/schema#`, `definitions`, and wraps refs as
`"allOf": [{"$ref": …}]` so the siblings remain legal; `SchemaSettings::draft2019_09()`
emits 2019-09 with `$defs`; `SchemaSettings::default()` is 2020-12 `[E]`.
A fourth setting, `inline_subschemas = true`, removes `$defs` entirely `[E]`.

Serde shapes, verified against the generated document `[E]`:

| Rust | JSON Schema |
| --- | --- |
| unit-variant enum | `oneOf` of `{"type":"string","const":"…"}`, one per variant, each with the variant's doc as `description` — **not** an `enum` array |
| externally tagged variant with fields | `oneOf` branch: object with one property named for the variant, `additionalProperties:false` |
| internally tagged (`#[serde(tag="kind")]`) | `oneOf` branch: object with `kind` as `{"type":"string","const":"…"}` plus the variant's fields |
| newtype `ConfigPath(String)` | `$defs/ConfigPath = {"description": …, "type":"string"}`, referenced by `$ref` |
| `Option<T>` | `anyOf: [{"$ref": T}, {"type":"null"}]` |
| `#[serde(default = …)]` | `"default": <value>` **as a sibling of `$ref`** |
| `#[serde(deny_unknown_fields)]` | `"additionalProperties": false` |

### 6.2 Where it degrades in taplo

Taplo validates with the `jsonschema` crate, pinned at **0.17.1** `[S]`, with no
draft selection of its own — the document's `$schema` is whatever `schemars` wrote.
Completion and hover do **not** go through that crate; they walk the schema in
taplo's own `collect_schemas` / `collect_child_schemas` `[S]`.

**Validation is fine.** The 2020-12 document validates correctly:
`additionalProperties:false` produces *"Additional properties are not allowed
('nonexistent_key' was unexpected)"* and a type mismatch produces *"…is not of type
"integer""*, both with correct spans `[E]`.

**Value completion is fine, and better than expected.** `mode = "|"` offers
`"inline"` and `"fullscreen"` with **each variant's own doc-comment** as the item
documentation, identically under 2020-12 and draft-07 `[E]`. `completion.rs`
handles `enum`, `const` and `default` explicitly, and `default_value_snippet`
prefers `const`, then `default`, then the first `enum` value `[S]`. The
`oneOf`-of-`const` shape that `schemars` emits for unit variants is therefore fully
understood — this was the risk that did not materialise.

**The field's doc-comment and default are lost wherever `$ref` appears.**
`collect_child_schemas` special-cases exactly one pattern:

```rust
// Deal with the { "description": "Foo", "allOf": [{ "$ref": "Bar" }] }
// pattern.
```

— the **draft-07** shape `[S]`. The 2020-12 shape hits `ref_schema_value` first and
`return`s, so `description` and `default` beside a `$ref` never reach the client
`[S]`. Measured, hovering the key `log_file: ConfigPath` whose doc-comment is
*"Where the log goes."*:

| schema | taplo hover shows | tombi hover shows |
| --- | --- | --- |
| 2020-12 (`$ref` + siblings) | `"A filesystem path declared in config."` `[E]` | `"Where the log goes." … Value: String?` `[E]` |
| draft-07 (`allOf` + siblings) | `"A filesystem path declared in config."` `[E]` | — |
| 2020-12, `inline_subschemas` | `"Where the log goes."` `[E]` | — |

For `mode: RenderMode`, taplo hover concatenates the branch docs and the *type's*
doc — *"Render inline in scrollback. / Take over the alternate screen. / How the
agent renders."* — and omits the field's *"Rendering mode."* under both dialects
`[E]`. With `inline_subschemas` it appends *"Rendering mode."* `[E]`. Tombi shows
*"Rendering mode."* first, then the enum values, then `Default: "inline"` — the
`$ref` sibling default that taplo dropped `[E]`.

**Key completion duplicates once per `oneOf` branch, and the dialect changes the
count.** For a two-variant enum key under 2020-12, taplo offers **two** `mode`
items, each documented with a *variant's* doc and neither with the field's `[E]`.
Under draft-07 it offers **three** — the two variants plus one merged item carrying
the field's doc `[E]`, because the `allOf` special case fires. Tombi offers **one**
item, documented with the field's doc `[E]`.

**`oneOf` diagnostics are the worst part.** `[provider] kind = "wrong"` yields five
taplo errors, all reading *"{"kind":"wrong","model":"m"} is not valid under any of
the schemas listed in the 'oneOf' keyword"*, at five different spans covering the
table header and every key and value inside it `[E]`. The message names neither the
offending key nor the allowed tags. Tombi, same input: two errors,
*"the value must be const value "anthropic", but found "wrong""* and the same for
`"openai"`, both at the value's span, plus *""base_url" is required"* `[E]`.

**`inline_subschemas = true` is the fix, and it is one line.** It removes `$defs`,
so every property is a self-contained schema and taplo has no `$ref` to bail out on
`[E]`. Verified effects: `log_file` hover and completion both carry the key's own
doc `[E]`; `mode` hover gains the field's sentence `[E]`; value completion is
unchanged `[E]`; the enum key still yields two completion items, which is inherent
to `oneOf` and not fixable from the schema side. Costs: the document grows by the
number of reuses of each named type, and a recursive type would recurse forever
`[X]`.

**Taplo's vendor extension is not a workaround.** `x-taplo` supports
`hidden`, `links`, `docs.main`, `docs.constValue`, `docs.defaultValue`,
`docs.enumValues` and `initKeys` `[S]`, and `schemars` can emit it via
`#[schemars(extend(…))]`. But it would have to be emitted *beside* the `$ref`,
where taplo already discards siblings — so it does not recover anything that the
plain `description` does not `[X]`.

### 6.3 Where it degrades in tombi

Tombi has a first-class `JsonSchemaDialect` enum parsed from `$schema`
(`/draft-07/schema`, `/draft/2019-09/schema`, `/draft/2020-12/schema`), defaulting
to **draft-07** when `$schema` is absent or unrecognised `[S]`. It reads both
`$defs` and `definitions` `[S]` and carries a `keyword_support` table that can warn
that `definitions` is superseded by `$defs` `[S]`. Against the `schemars` 2020-12
output it lost nothing measurable in this survey `[E]`. Its one weakness found: the
value-completion documentation for an enum shows the *type's* doc rather than the
per-variant doc, where taplo shows the per-variant doc `[E]`.

---

## 7. Question 5: the artifact, per editor

Every integration surveyed is a shell around taplo-lsp or tombi-lsp, and both
servers read their project config file. So the artifact set is **two files**, not
one per editor.

### 7.1 `.taplo.toml` — repository root

Serves the taplo CLI, VS Code + Even Better TOML, Helix, Neovim, Emacs `lsp-mode`,
`coc-toml`, and anything else that spawns `taplo lsp stdio`.

```toml
[[rule]]
include = ["**/.tp/config.toml"]

[rule.schema]
path = "/home/u/.cache/tp/0.1.0/schemas/config.json"

[[rule]]
include = ["**/.tp/keybindings.toml"]

[rule.schema]
path = "/home/u/.cache/tp/0.1.0/schemas/keybindings.json"

[[rule]]
include = ["**/.tp/themes/*.toml"]

[rule.schema]
path = "/home/u/.cache/tp/0.1.0/schemas/theme.json"
```

Verified end-to-end under both the CLI and the LSP `[E]`. Note it is a **shared,
user-owned file** — taplo's formatter settings live in it too — so the gesture must
merge rather than overwrite `[X]`.

### 7.2 `tombi.toml` — repository root

Serves the tombi CLI, Zed, VS Code + Tombi, JetBrains + Tombi, Helix, Neovim.

```toml
[[schemas]]
path = "/home/u/.cache/tp/0.1.0/schemas/config.json"
include = ["**/.tp/config.toml"]

[[schemas]]
path = "/home/u/.cache/tp/0.1.0/schemas/keybindings.json"
include = ["**/.tp/keybindings.toml"]

[[schemas]]
path = "/home/u/.cache/tp/0.1.0/schemas/theme.json"
include = ["**/.tp/themes/*.toml"]
```

Verified end-to-end under the CLI and the LSP `[E]`.

### 7.3 What each editor actually needs (and does not)

| Editor | Server | Needs its own artifact? |
| --- | --- | --- |
| VS Code + Even Better TOML `[D]` | taplo-lsp, bundled (`evenBetterToml.taplo.bundled` defaults `true`) `[D]` | **No** — the LSP reads `.taplo.toml` from the workspace root, `evenBetterToml.taplo.configFile.enabled` defaults `true` `[S][E]` |
| VS Code + Tombi `[S]` | tombi-lsp | **No** — extension exposes no schema settings at all `[S]` |
| Zed `[D]` | tombi-lsp, via the Tombi extension (`extension.toml` id `tombi`, v0.2.4) `[S]` | **No** |
| Helix `[S]` | *both*: `language-servers = [ "taplo", "tombi" ]` for TOML `[S]` | **No** |
| Neovim (`nvim-lspconfig`) `[S]` | either; `taplo` root markers `.taplo.toml`, `taplo.toml`, `.git`; `tombi` root markers `tombi.toml`, `pyproject.toml`, `.git` `[S]` | **No** |
| JetBrains | Tombi plugin (id `tombi`, v0.2.0, in-tree) `[S]`. Natively there is **no LSP**; the umbrella ticket [IJPL-104165](https://youtrack.jetbrains.com/issue/IJPL-104165) is open since 2021-11-08 `[I]`, but the companion catalogue reports a shipped `TomlJsonSchemaEnabler` plus registry key `org.toml.json.schema` — see §7.4 | **Yes** natively (`.idea/jsonSchemas.xml`); **no** with the Tombi plugin |
| Emacs `lsp-mode` | taplo, via `lsp-toml` `[?]` | assumed no `[?]` |
| Emacs `eglot` (Emacs 31 / `master`) | tombi — `((toml-ts-mode conf-toml-mode) . ("tombi" "lsp"))`, per the companion catalogue `[?]` | **No** `[X]` |

**If an editor-settings artifact is written anyway**, these are the literal shapes.

VS Code — `.vscode/settings.json`. Regex keys; the value **must** be an absolute
`file://` URI (§4.2):

```json
{
  "evenBetterToml.schema.associations": {
    ".*/\\.tp/config\\.toml$": "file:///home/u/.cache/tp/0.1.0/schemas/config.json"
  }
}
```

Helix — `.helix/languages.toml`. Helix sends `[language-server.NAME.config]` both
as `initializationOptions` and as a `workspace/didChangeConfiguration` after
`initialized` `[S]`, and taplo's `configuration_change` handler feeds the settings
object in **un-nested** `[S]`. Verified by driving taplo with `workspace/configuration`
answered `null` and only the notification carrying the settings — associations
applied `[E]`:

```toml
[language-server.taplo.config.schema.associations]
".*/\\.tp/config\\.toml$" = "file:///home/u/.cache/tp/0.1.0/schemas/config.json"
```

Neovim — `vim.lsp.config`. Neovim answers `workspace/configuration` by looking up
the requested section inside `client.settings` `[S]`, and taplo asks for section
`evenBetterToml` `[S]`, so the nested form is the correct one:

```lua
vim.lsp.config('taplo', {
  settings = { evenBetterToml = { schema = { associations = {
    ['.*/%.tp/config%.toml$'] = 'file:///home/u/.cache/tp/0.1.0/schemas/config.json',
  } } } },
})
```

(Neovim also sends `didChangeConfiguration` with the same table on init `[S]`, so
the un-nested form happens to work too `[X]`. Prefer the nested one.)

All three are strictly worse than `.taplo.toml`: they hard-code a machine-specific
absolute path into a file that is usually committed, and they must be written three
times for three editors.

### 7.4 The companion catalogue on this branch, and where we disagree

A second artifact, `toml-schema-association-catalogue.md`, was produced for this
ticket in parallel. It is a documentation-and-source catalogue and it states
plainly that **no editor was run**; every editor-dependent cell in it is marked
`unverified`. It is worth keeping because it covers ground this note does not, and
worth reading beside this one because the two disagree in three places.

**It covers, and this note does not:**

- **`.idea/jsonSchemas.xml`** as a JetBrains-native mechanism, with
  `relativePathToSchema` + `patterns` entries, sourced to
  `JsonSchemaMappingsProjectConfiguration.java`, and a shipped
  `TomlJsonSchemaEnabler.kt` with registry key `org.toml.json.schema` defaulting to
  `true`. If that reading holds, JetBrains natively supports TOML schema code
  insight and needs a **third** artifact. This note's `[I]` marker on IJPL-104165
  is the weaker claim; the enabler and the meta-issue can both be true at once.
- **Emacs `eglot`** on `master` mapping TOML to `tombi`, and Emacs 30 registering
  no TOML server at all.
- **`schemars` 0.8.22 vs 1.2.2** differences, and a keyword-level table of what
  `jsonschema` 0.17.1 supports per draft.

**Where the two disagree:**

1. **VS Code's config-file discovery.** The catalogue treats `.taplo.toml`
   discovery as a walk. It is not, in VS Code: the bundled server is the WASM build
   and its `findConfigFile` checks one directory (§5) `[S]`. This note's reading is
   the narrower and, on the source, the correct one.
2. **The Helix settings shape.** The catalogue gives
   `[language-server.taplo.config.evenBetterToml.schema]`. This note verified the
   **un-nested** `[language-server.taplo.config.schema.associations]` empirically,
   through the `didChangeConfiguration` path `[E]`. Both are plausible — Helix
   answers `workspace/configuration` by walking the section path into `config`
   `[S]`, so the nested form should also work — but only the un-nested one has been
   run.
3. **Whether one file serves them all.** The catalogue answers "no" over a
   ten-row editor table including JetBrains-native and Emacs 30. This note answers
   "no, two" over the editors that have a language server at all. The difference is
   scope, not fact.

---

## 8. The gesture's fate

**`--write-editor-config` works as specified — for one of the two servers, at one
of the two file locations D14 permits, and only if the mapping is written as a
`.taplo.toml`/`tombi.toml` pair rather than as editor settings.** The three
corrections are cheap; the fourth problem is not the mechanism's.

What must change from the D8 wording, in order of cost:

1. **Write two files, not one.** `.taplo.toml` and `tombi.toml`, both at the
   repository root. Cost: one extra template and a merge path for each. Without
   `tombi.toml`, Zed and JetBrains users get nothing, and Zed is the editor whose
   own documentation now names Tombi `[D]`.

2. **Write at the repository root, and use a globstar-prefixed pattern.** Not beside the `.tp/`
   directory the mapping describes. Taplo only walks up from the editor's workspace
   root `[S]`, so a nested mapping file is unreachable; and a *relative* `include`
   anchored to CWD means the CLI silently no-ops from any subdirectory `[E]`.
   In VS Code the requirement is absolute: the bundled WASM server does not walk
   at all, so the file must be at the workspace-folder root or it is invisible
   `[S]`. `include = ["**/.tp/config.toml"]` at the root covers both the root and the
   nested case. Cost: none.

3. **Use `path`, never `url`, and never editor settings.** `schema.path` is the
   only taplo key that takes a filesystem path `[S][E]`; `schema.url` rejects one
   and discards the entire config file when it sees one `[E]`;
   `evenBetterToml.schema.associations` rejects one silently and has no working
   relative form `[E]`. Cost: none — it is a field name.

4. **Set `inline_subschemas = true` on the `schemars` generator.** Otherwise every
   key whose type is an enum or a `ConfigPath` loses the doc-comment D12 makes
   mandatory, in the editor most `tp` users will have `[E]`. Cost: a larger schema
   file and a build-time prohibition on recursive config types — which the closed
   axis enum of D11 already effectively imposes.

The one problem the gesture cannot fix is **staleness**. #11-D6 version-keys the
cache `[D]`, so the written mapping names `…/tp/<version>/schemas/config.json` and
dies at the next upgrade, leaving a stale line in a file `tp` promised not to touch
uninvited. Three options, none free:

- **Re-run the gesture on upgrade** — but `tp` must then either remember which
  repositories it wrote into, or rewrite on every startup, which is the uninvited
  write D8 forbids.
- **Materialise the schemas to an unversioned path** (`…/tp/schemas/`) beside the
  versioned docs, and point the mapping there. Cost: a second materialisation rule,
  and two `tp` versions on one machine fight over the file. This is the cheapest
  of the three and the one this note recommends.
- **Materialise into the project** (`.tp/schemas/`) and write relative paths. Cost:
  generated files in the user's repository — a bigger violation than the mapping
  file itself.

**Recommendation: keep the gesture, with the four corrections and the unversioned
schema path.** It is not worth dropping: the mechanism is real, local absolute
paths do work in the two config-file formats, and the whole thing is ~60 lines of
TOML templating. But it should be honest about scope in its output — it writes two
files at the repository root, it merges rather than overwrites, and it tells the
user which of the two servers it just configured.

---

## 9. What could not be verified

| Item | Status |
| --- | --- |
| Emacs `lsp-mode` / `lsp-toml` schema-association surface | `[?]` Confirmed only that it wraps taplo, from a secondary index page; the `lsp-toml` source was not read. The companion catalogue reports `eglot` on `master` maps TOML to `tombi`; not independently checked here |
| The WASM taplo build, run | `[?]` Every `[E]` LSP result in this note is from the **native** `taplo lsp stdio`. The WASM build shares `taplo-lsp` and `taplo-common`, so §4.2, §6 and §7 transfer by construction `[X]`; only §5's discovery differs, and that difference was read from source, not run |
| JetBrains native TOML schema code insight | `[?]` This note found only IJPL-104165 (open). The companion catalogue reports a shipped `TomlJsonSchemaEnabler.kt` and a `.idea/jsonSchemas.xml` mapping store; neither was verified here, and no JetBrains IDE was run |
| `coc-toml` | `[?]` Its README says it uses taplo as the LSP engine; not read or run |
| tombi-lsp honouring the `#:schema` directive | `[X]` The directive is handled in tombi's shared `comment-directive` crate and was verified through the CLI; not re-verified through the LSP |
| taplo-lsp honouring the `$schema` root key | `[X]` Verified via the CLI; the code path (`add_from_document`) is shared, but not re-run under the server |
| Windows behaviour of `format!("file://{path}")` end-to-end | `[X]` The `Url::parse` half is `[E]`; the `to_file_path()` half is inferred from the URL spec's drive-letter rule. No Windows machine was available |
| JetBrains native TOML JSON-schema support | `[I]` IJPL-104165 is "In progress", unresolved, created 2021-11-08. Whether a partial implementation ships behind a registry flag today was not established |
| Whether any client sends a workspace-folder URI *with* a trailing slash | `[?]` If one did, the §4.2 off-by-one would not occur for that client. Not checked beyond the servers' own behaviour |
| An upstream taplo issue tracking the §4.2 off-by-one | `[?]` None found; the nearest are #620 / #770 / #773, which are `$ref`-resolution failures against schemastore, not this |
| Even Better TOML's maintenance status | `[I]` v0.21.2, last marketplace update **2024-12-20**, 4.79M installs. The taplo repository is still committed to (HEAD 2026-07-28) but the last release is 0.10.0, 2025-05-23. Read as risk, not as abandonment |

---

## 10. Primary sources

**Taplo**

- Source, `08f343be` — https://github.com/tamasfe/taplo
  - `crates/taplo-common/src/schema/associations.rs` (priority ladder, directive and `$schema` resolution, glob matching)
  - `crates/taplo-common/src/config.rs` (`CONFIG_FILE_NAMES`, `SchemaOptions`, `Options::prepare`, `make_absolute`)
  - `crates/taplo-common/src/schema/mod.rs` (`jsonschema` 0.17.1, `collect_schemas`, `collect_child_schemas`, `reference_url`, `fetch_external`)
  - `crates/taplo-common/src/schema/ext.rs` (`x-taplo`)
  - `crates/taplo-common/src/environment/native.rs` (`find_config_file`)
  - `crates/taplo-lsp/src/world.rs`, `src/config.rs`, `src/handlers/configuration.rs`, `src/handlers/schema.rs`, `src/handlers/completion.rs`
  - `crates/taplo/src/dom/mod.rs` (directive lexer)
  - `editors/vscode/package.json` (`evenBetterToml.*` settings), `editors/vscode/src/client.ts` (bundled server selection), `editors/vscode/src/server.ts` (the JS `findConfigFile` that does not walk)
  - `crates/taplo-wasm/src/environment.rs` (`Environment` delegated to JS)
- Documentation — https://taplo.tamasfe.dev/configuration/directives.html and https://taplo.tamasfe.dev/configuration/file.html
- Issues — [#620](https://github.com/tamasfe/taplo/issues/620), [#770](https://github.com/tamasfe/taplo/issues/770), [#773](https://github.com/tamasfe/taplo/issues/773)

**Tombi**

- Source, `825161b6` — https://github.com/tombi-toml/tombi
  - `crates/tombi-config/src/schema.rs` (`[[schemas]]`, `RootSchema`), `src/lib.rs` (config file names), `src/level.rs` (`config_base_dir`)
  - `crates/tombi-schema-store/src/store.rs` (`load_config`, `load_config_schemas`), `src/json_schema_dialect.rs`, `src/keyword_support.rs`
  - `crates/tombi-lsp/src/config_manager.rs` (per-document config discovery)
  - `rust/serde_tombi/src/config.rs` (`load_with_path_and_level` — the walk)
  - `editors/vscode/package.json`, `editors/zed/extension.toml`, `editors/intellij/gradle.properties`
- Documentation — https://tombi-toml.github.io/tombi/docs/json-schema/

**Editors**

- Zed docs — https://raw.githubusercontent.com/zed-industries/zed/main/docs/src/languages/toml.md
- Helix `languages.toml` — https://raw.githubusercontent.com/helix-editor/helix/master/languages.toml
- Helix `helix-term/src/application.rs`, `helix-lsp/src/client.rs` (config delivery)
- Helix docs — https://docs.helix-editor.com/languages.html
- `nvim-lspconfig` — `lsp/taplo.lua`, `lsp/tombi.lua`
- Neovim — `runtime/lua/vim/lsp/handlers.lua` (`workspace/configuration`), `runtime/lua/vim/lsp/client.lua` (`didChangeConfiguration` on init)
- VS Marketplace gallery API for `tamasfe.even-better-toml`
- JetBrains YouTrack — https://youtrack.jetbrains.com/issue/IJPL-104165

**Schema generation**

- `schemars` 1.2.2 from crates.io; `schemars::generate::SchemaSettings::{draft07, draft2019_09, default}`, `inline_subschemas`
- `url` crate `Url::parse` / `Url::join` / `Url::to_file_path` behaviour, exercised directly
