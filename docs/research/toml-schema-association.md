# How a TOML editor associates a local JSON Schema file — raw catalogue

Research output for [tapir-dev/tp#30](https://github.com/tapir-dev/tp/issues/30).

**Scope.** The mechanisms by which a TOML editor or language server is told which
JSON Schema applies to a given TOML document, restricted to what matters for `tp`:
whether a *local filesystem path* works, whether the mapping file is found where `tp`
would write it, and what the consumer does with the schema shape a Rust derive emits.
This ticket **does not reopen D8**: committed, embedded and materialised schemas plus
`tp config schema` stand regardless of the answer here. The only thing at stake is the
`--write-editor-config` auto-association gesture. No CLI is designed here.

**Method.** Primary sources only. Where documentation exists it is quoted and linked.
Where documentation is silent, ambiguous, or contradicted, the implementation was read
directly: source trees were downloaded and read locally —
[`tamasfe/taplo`](https://github.com/tamasfe/taplo) at `master` (`08f343be0`,
2026-07-28), [`tombi-toml/tombi`](https://github.com/tombi-toml/tombi) at `main`
(`825161b60`, 2026-09-08), and [`jsonschema`](https://github.com/Stranger6667/jsonschema-rs)
`0.17.1` from crates.io. Three small experiments were compiled and run locally against
the real crates (`url` 2.x, `schemars` 0.8.22, `schemars` 1.2.2) — these are marked
`verified (experiment)` and the program is described inline so it can be reproduced.
**No editor was run.** Every claim that would require a live editor to confirm is
marked `unverified` with the experiment that would settle it.

**Doc access date: 2026-09-08.** This ecosystem is small but moving unevenly — taplo
has had no release in ~16 months while tombi ships weekly. Re-verify before relying on
any cell.

**Reading the tables.**

- `verified (docs)` — stated in official documentation; the URL is in the Sources
  section or inline.
- `verified (source)` — read in the implementation; file path and line numbers given.
  The source is a primary source; a blog post is not.
- `verified (experiment)` — established by compiling and running the real crate here.
- `none documented` — searched for and absent. Stronger than unknown: the feature does
  not appear in the primary docs at all.
- `inferred` — a conclusion drawn from two or more verified facts; the reasoning is
  stated so it can be checked.
- `unverified` — cannot be settled without a live editor; the experiment that would
  settle it is named.
- Where the docs and the source disagree, **both** are recorded and the source wins.
  Several such disagreements exist and two of them are load-bearing.

---

## 0. The landscape in one table

There are exactly two TOML language servers with schema support, and they are not
interchangeable.

| | taplo | tombi |
|---|---|---|
| Repo | `tamasfe/taplo` | `tombi-toml/tombi` |
| Latest release | **`0.10.0`, 2025-05-23** | **`v1.5.2`, 2026-09-05** |
| Last commit on default branch | `08f343be0`, 2026-07-28 | `825161b60`, 2026-09-08 |
| VS Code extension | `tamasfe.even-better-toml` `0.21.2`, **last published 2024-12-20**, self-described *"preview extension"* | `tombi-toml.tombi`, last published 2026-09-05 |
| Open issues | 239 | — |
| Archived? | no | no |
| Config file | `.taplo.toml` / `taplo.toml` | `.tombi.toml` / `tombi.toml` / `.config/tombi.toml` / `[tool.tombi]` in `pyproject.toml` |
| Reads the *other's* config | no | no |
| `#:schema` directive | origin of it | implements it, documented as Taplo-compatible |

`verified (source)` — release/commit dates from the GitHub REST API
(`/repos/{owner}/{repo}/releases`, `/commits`, `/repos/{owner}/{repo}`) and the VS Code
Marketplace `extensionquery` API, both read on 2026-09-08. taplo's own README still
says *"The project is very young"*; there is no deprecation or maintenance notice.

The practical consequence, established in §4: **taplo is no longer the default anywhere
except VS Code, Neovim and Helix.** Zed ships no TOML language server at all and its
docs point at tombi; Emacs `eglot` on `master` maps TOML to `tombi`; JetBrains uses
neither.

---

## 1. Table A — Association mechanisms that exist

One row per mechanism. "Local path?" is the load-bearing column.

| # | Mechanism | Consumed by | Local path accepted? | Relative? | Absolute? |
|---|---|---|---|---|---|
| 1 | `#:schema <value>` header directive | taplo (LSP **and** CLI), tombi | **yes** | yes — relative to the *document* | **yes** (Unix); see the Windows note in §2.6 |
| 2 | `"$schema" = "<value>"` root key | taplo, tombi | only if it starts with `.` | yes | **no** — a bare `/abs/path` is rejected |
| 3 | `[schema] path` in `.taplo.toml` | taplo only | **yes** | yes — relative to the *workspace root / cwd*, **not** the config file | **yes** (Unix) |
| 4 | `[[rule]]` + `[rule.schema] path` in `.taplo.toml` | taplo only | same as row 3 | same as row 3 | same as row 3 |
| 5 | `evenBetterToml.schema.associations` in `settings.json` | taplo via the VS Code extension (and any client that answers `workspace/configuration` for section `evenBetterToml`) | **only as `./relative` or a `file://` URL** | yes, if prefixed `./` | **no** — a bare `/abs/path` is silently dropped |
| 6 | `evenBetterToml.rules` in `settings.json` | same as row 5 | **yes** — goes through the row-3/4 code path | yes | yes |
| 7 | `[[schemas]] path` + `include` in `tombi.toml` | tombi only | **yes** | yes — relative to the **directory containing the config file** | **yes** (Unix) |
| 8 | `contributes.tomlValidation` in a VS Code extension manifest | taplo via Even Better TOML, VS Code only | `none documented` — examples show `https://` only | — | — |
| 9 | Schema catalog (SchemaStore) | taplo, tombi, JetBrains | n/a — catalogue of URLs | — | — |
| 10 | `TOML: Select Schema` command | Even Better TOML | n/a — picks from already-known schemas, **session-only, never persisted** | — | — |
| 11 | `.idea/jsonSchemas.xml` | JetBrains IDEs only | **yes** (`relativePathToSchema`) | yes | yes |

`verified (source)` for rows 1–7 and 10–11, `verified (docs)` for rows 8–9. Per-row
detail and citations follow.

### 1.1 The `#:schema` directive — exact syntax

Docs, verbatim (<https://taplo.tamasfe.dev/configuration/directives.html>):

> All directive comments must follow the following pattern: `#:<name> <content>`.
>
> It is possible to override the schema for a specific document by using the `schema`
> header directive. A relative file path or an URL can be provided.
>
> ```toml
> #:schema ./foo-schema.json
> foo = "bar"
> ```
>
> Relative paths are relative to the document file, if the file path is not known,
> Taplo will be unable to find the schema.
>
> Multiple schema directives in the same document are not supported and the behaviour
> is undefined.

`verified (docs)`. The lexing is stricter than the prose suggests:

- The comment token must literally start with `#:`; the remainder is split on
  whitespace, first token is the directive **name**, second token is the **value**.
  Everything after the second token is discarded. **A schema path containing a space
  cannot be expressed.** `verified (source)` — `crates/taplo/src/dom/mod.rs:337-345`.
- It must be a *header* comment: it may only be preceded by other comments, and must
  end before the first item in the document. `verified (source)` —
  `crates/taplo/src/dom/node.rs:314-326` (`header_comments()` is
  `comments().take_while(|c| c.end <= first_item.start)`).
- Only the **first** `schema` directive is used (`break` after the first match).
  `verified (source)` — `crates/taplo-common/src/schema/associations.rs:171-215`.

tombi implements the same directive and says so:
*"Same as [Taplo], `#:schema` is used to specify the schema to use for the document.
However, Tombi only allows document comment directives at the beginning of the
document, so you need to add a blank line after the directive."*
`verified (docs)` — <https://tombi-toml.github.io/tombi/docs/comment-directive/schema-document-directive>.

### 1.2 The `.taplo.toml` schema keys — exact syntax

Docs, verbatim (<https://taplo.tamasfe.dev/configuration/file.html>):

> The `schema` table consists of only two keys:
>
> - `path`: the path of the schema, this can be either path to a local file or an URL
>   with the schemes `taplo`, `http` or `https`. (`file` scheme is also accepted, it is
>   the same as specifying a local path)
> - `enabled`: whether to enable the schema or not (`true` if omitted).

`verified (docs)`. The docs **undercount the keys**: the struct has three.
`verified (source)` — `crates/taplo-common/src/config.rs:355-375`:

```rust
pub struct SchemaOptions {
    pub enabled: Option<bool>,
    /// A local file path to the schema, overrides `url` if set.
    ///
    /// URLs are also accepted here, but it's not a guarantee and might
    /// change in newer releases.
    /// Please use the `url` field instead whenever possible.
    pub path: Option<String>,
    /// A full absolute URL to the schema.
    ///
    /// The url of the schema, supported schemes are `http`, `https`, `file` and `taplo`.
    pub url: Option<Url>,
}
```

Per-file targeting is a `[[rule]]` with an `include` glob:

```toml
[[rule]]
include = ["**/tp.toml"]

[rule.schema]
path = "/home/me/.cache/tp/1/config.schema.json"
```

> In case of overlapping rules, the last defined rule always takes precedence.

`verified (docs)`, same page.

---

## 2. taplo — the load-bearing details

### 2.1 Does a local path work where a URL is expected? **Yes, and here is exactly how**

`verified (source)` — `crates/taplo-common/src/config.rs:242-262`, `Options::prepare`:

```rust
let url = match schema_opts.path.take() {
    Some(p) => {
        if let Ok(url) = p.parse() {          // 1. try to parse as a URL first
            Some(url)
        } else {
            let p = if e.is_absolute(Path::new(&p)) {
                PathBuf::from(p)              // 2. absolute path: used as-is
            } else {
                base.join(p).normalize()      // 3. relative path: joined to `base`
            };
            let s = p.to_string_lossy();
            Some(Url::parse(&format!("file://{s}")).context("invalid schema path")?)
        }
    }
    None => schema_opts.url.take(),
};
```

The resulting `file://` URL is then fetched from disk:

```rust
match schema_url.scheme() {
    "http" | "https" => …,
    "file" => Ok(serde_json::from_slice(&self.env.read_file(…).await?)?),
    scheme => Err(anyhow!("the scheme `{scheme}` is not supported")),
}
```

`verified (source)` — `crates/taplo-common/src/schema/mod.rs:271-293`.

The same "URL first, then path" shape governs the `#:schema` directive
(`associations.rs:182-215`): parse as `Url`; on failure, if the value is an absolute
path emit `file://{value}`, otherwise `doc_url.join(value)` — i.e. relative to the
document. So **both** mechanisms accept an absolute local path on Unix.

The `"$schema"` root key is the odd one out: it only special-cases values starting with
`.`; anything else must parse as a `Url`, so a bare absolute path is rejected with
`tracing::error!("invalid schema url or path given in the `$schema` field")`.
`verified (source)` — `associations.rs:227-246`.

### 2.2 What `base` is — and the resolution mismatch

`Options::prepare(env, base)` is called from exactly two places:

| Caller | `base` | Citation |
|---|---|---|
| taplo CLI | the **current working directory** | `crates/taplo-cli/src/lib.rs:71-83` |
| taplo LSP | the **workspace root** | `crates/taplo-lsp/src/world.rs:256` |

It is **never** the directory containing `.taplo.toml`. This is documented for
`include`/`exclude` (*"Relative paths are **not** relative to the configuration file,
but rather depends on the tool using the configuration"* —
`crates/taplo-common/src/config.rs:29-31`, `verified (source)`) and undocumented for
`schema.path`, which uses the identical `base`.

`inferred`: a relative `schema.path` in a repo-root `.taplo.toml` resolves correctly
only when the editor's workspace root *is* the repo root. Open a subdirectory as the
workspace and the relative path silently resolves to the wrong place. An absolute path
is immune to this.

### 2.3 Is the mapping file's location fixed? **No — it is an upward walk**

The docs say it is fixed:

> By default, every tool looks for one in the working directory or the root of the
> workspace by the following names (in precedence order): `.taplo.toml`, `taplo.toml`

`verified (docs)` — <https://taplo.tamasfe.dev/configuration/file.html>.

**The source disagrees.** `verified (source)` —
`crates/taplo-common/src/environment/native.rs:110-132`:

```rust
async fn find_config_file(&self, from: &Path) -> Option<std::path::PathBuf> {
    let mut p = from;
    loop {
        if let Ok(mut dir) = tokio::fs::read_dir(p).await {
            while let Ok(Some(entry)) = dir.next_entry().await {
                for name in CONFIG_FILE_NAMES {
                    if entry.file_name() == *name {
                        return Some(entry.path());
                    }
                }
            }
        }
        match p.parent() {
            Some(parent) => p = parent,
            None => return None,
        }
    }
}
```

Three findings from this function:

1. **It walks up to the filesystem root**, starting from the workspace root (LSP,
   `world.rs:243`) or the cwd (CLI, `lib.rs:53`). So `.taplo.toml` at the repository
   root is found from anywhere at or below it. This *matches* D14's "walk to the
   repository root" — there is **no mismatch**; taplo is strictly more permissive.
   `inferred` from the two source facts.
2. **The documented name precedence is not implemented.** The loop returns the first
   *directory entry* matching either name, in `read_dir` order, which is
   filesystem-dependent. If both `.taplo.toml` and `taplo.toml` exist in one directory,
   which wins is not determined by the code. `verified (source)`.
3. **It never searches downward.** A `.taplo.toml` in a subdirectory of the workspace
   is invisible. `verified (source)`.

**Exception — detached files.** If the LSP has no workspace folder (VS Code opened on a
single file rather than a folder), the workspace root is the sentinel `root:///` and
config discovery is skipped entirely: `else if self.root != *DEFAULT_WORKSPACE_URL` has
no `else` branch that searches. `verified (source)` —
`crates/taplo-lsp/src/world.rs:84`, `218-252`. In that mode only the in-file `#:schema`
directive works.

### 2.4 Precedence between the mechanisms

`verified (source)` — `crates/taplo-common/src/schema/associations.rs:22-30`, and
`association_for` picks `.max_by_key(|assoc| assoc.priority)` (`associations.rs:303-321`):

```rust
pub const BUILTIN: usize     = 10;
pub const CATALOG: usize     = 25;
pub const CONFIG: usize      = 50;   // [schema] in .taplo.toml
pub const CONFIG_RULE: usize = 51;   // [[rule]] in .taplo.toml
pub const LSP_CONFIG: usize  = 60;   // evenBetterToml.schema.associations
pub const SCHEMA_FIELD: usize = 70;  // "$schema" = "…"
pub const DIRECTIVE: usize   = 75;   // #:schema
pub const MAX: usize         = usize::MAX;  // TOML: Select Schema
```

This matches the documented order at
<https://taplo.tamasfe.dev/configuration/using-schemas.html> exactly. `verified (docs)`
+ `verified (source)`.

Two consequences worth writing down:

- A user's `evenBetterToml.schema.associations` in `settings.json` **silently overrides**
  anything `tp` writes into `.taplo.toml`.
- A `#:schema` directive **always** wins over both.

### 2.5 How the include glob is matched

`[[rule]] include` globs are made absolute against `base` (§2.2) and matched against the
document URI with the scheme stripped:

```rust
AssociationRule::Glob(g) => g.is_match(&*normalize_str(
    url.as_str().strip_prefix(url.scheme()).unwrap().strip_prefix("://").unwrap(),
)),
AssociationRule::Regex(r) => r.is_match(&normalize_str(url.as_str())),
```

`verified (source)` — `crates/taplo-common/src/schema/associations.rs:413-431`. So the
glob is matched against an absolute path, and `include = ["**/tp.toml"]` is the robust
form; `include = ["tp.toml"]` becomes `<workspace-root>/tp.toml` and breaks if the
workspace root is not the repo root.

Note the asymmetry: `.taplo.toml` rules use **globs**; the VS Code
`schema.associations` setting uses **regexes over the whole URI**. They are not
interchangeable text.

### 2.6 Windows: an absolute path in `[schema] path` or `#:schema` is broken

Both code paths try `Url::parse` **before** treating the value as a path. A Windows
absolute path parses as a URL whose scheme is the drive letter.

`verified (experiment)` — a 12-line Rust program linked against `url` 2.x (the version
taplo pins, `url 2.5.0` in its `Cargo.lock`), run here:

```
"C:\\Users\\me\\schema.json"        => Ok(scheme "c")
"C:/Users/me/schema.json"           => Ok(scheme "c")
"/home/me/.cache/tp/schema.json"    => Err(RelativeUrlWithoutBase)
"./schema.json"                     => Err(RelativeUrlWithoutBase)
"file:///home/me/s.json"            => Ok(scheme "file")
Url::parse("file:///home/me/sch ema.json") => "file:///home/me/sch%20ema.json"
```

`inferred` from that plus `fetch_external`'s scheme match: on Windows, a bare absolute
schema path is accepted as a URL with scheme `c` and then fails with
`the scheme `c` is not supported`. Unix absolute and relative paths correctly fall
through to the path branch. **A cross-platform writer must emit `file:///C:/…` on
Windows.** `unverified` for the end-to-end editor behaviour — the experiment that would
settle it is: on Windows, put `[schema] path = "C:\\tmp\\s.json"` in `.taplo.toml`,
open a matching TOML file in VS Code, and read the taplo output channel for the
`the scheme \`c\` is not supported` line.

Separately, taplo builds the URL with `format!("file://{s}")` rather than
`Url::from_file_path`, which is the API that handles drive letters and UNC paths. tombi
uses `Url::from_file_path` — but only *after* the same `Url::from_str` attempt, so it
inherits the same drive-letter hazard. `verified (source)` — taplo `config.rs:255-257`,
tombi `crates/tombi-uri/src/lib.rs:106-110` and
`crates/tombi-schema-store/src/store.rs:267-272`.

### 2.7 Staleness: the schema is cached and nothing is watched

`verified (source)` — `crates/taplo-common/src/schema/cache.rs:13-14` and `54-110`:

```rust
pub const DEFAULT_LRU_CACHE_EXPIRATION_TIME: Duration = Duration::from_secs(60);
pub const DEFAULT_CACHE_EXPIRATION_TIME: Duration = Duration::from_secs(60 * 10);
```

`load_schema` consults the cache before `fetch_external` and stores whatever it fetched
— **including `file://` schemas**; there is no `file://` bypass
(`crates/taplo-common/src/schema/mod.rs:190-218`). The VS Code extension sets a disk
cache path (`editors/vscode/src/client.ts:121`), so a locally materialised schema is
copied into VS Code's `globalStorage` and served from there for up to 600 s. Exposed as
`evenBetterToml.schema.cache.memoryExpiration` (default 60) and
`.diskExpiration` (default 600).

Also `none documented` / `verified (source)` by absence: grepping the whole taplo tree
for `DidChangeWatchedFiles`, `FileSystemWatcher` and `watched_files` returns **nothing**.
Neither `.taplo.toml` nor a `file://` schema is watched. `.taplo.toml` is only re-read
when `workspace/didChangeConfiguration` fires
(`crates/taplo-lsp/src/handlers/configuration.rs:12-29` → `ws.initialize` →
`load_config`), i.e. when the user changes an editor setting.

`inferred`: after `tp` writes `.taplo.toml`, or regenerates the materialised schema, the
user must restart the language server (or touch an editor setting) to see the effect.

---

## 3. tombi — the same questions

### 3.1 Association mechanisms

Priority, verbatim (<https://tombi-toml.github.io/tombi/docs/json-schema>):

> 1. `#:schema` directive in the TOML file's top comment (compatible with Taplo)
> 2. JSON Schema specified in the Tombi configuration file
> 3. JSON Schema from the JSON Schema Store

`verified (docs)`.

The config-file form is an array of tables, not a rule with a nested schema table:

```toml
[[schemas]]
path = "schemas/partial.schema.json"
include = ["tp.toml"]
```

> - `path`: The schema path (URL or local file path)
> - `include`: File match patterns to apply this schema (supports glob patterns)
>
> For local paths, `path` is resolved relative to the directory containing the loaded
> config file.

`verified (docs)`, same page as §3.2. This is the **opposite** of taplo's rule and is the
more useful one: a repo-root `tombi.toml` with a repo-relative path works regardless of
where the editor's workspace root is.

`verified (source)` — `crates/tombi-schema-store/src/store.rs:261-278`:

```rust
let schema_uri = if let Ok(schema_uri) = SchemaUri::from_str(schema.path()) {
    schema_uri
} else if let Ok(schema_uri) = match base_dir_path {
    Some(base_dir_path) => SchemaUri::from_file_path(base_dir_path.join(schema.path())),
    None => SchemaUri::from_file_path(schema.path()),
} { … }
```

`inferred`: because `Path::join` with an absolute argument discards the base (documented
std behaviour), an **absolute** `path` also works and ignores `base_dir_path`.

### 3.2 Config discovery — documented, and it is an upward walk

Verbatim (<https://tombi-toml.github.io/tombi/docs/configuration>):

> **Project Level.** For each directory from the current directory up to the filesystem
> root:
> 1. `.tombi.toml` 2. `tombi.toml` 3. `.config/tombi.toml` 4. `[tool.tombi]` in
> `pyproject.toml`
>
> **User Level.** If nothing is found, Tombi then falls back to: 5.
> `$XDG_CONFIG_HOME/tombi/config.toml` 6. `~/.config/tombi/config.toml` 7.
> `~/Library/Application Support/tombi/config.toml` (macOS), `%APPDATA%\tombi\config.toml`
> (Windows). **System Level.** 8. `/etc/tombi/config.toml` (Linux).
>
> The base directory for configuration search depends on the context: for CLI usage, it
> is the directory where the command is executed; for LSP usage, it is **the directory of
> the currently opened file**.

`verified (docs)`. Filenames confirmed at
`crates/tombi-config/src/lib.rs:33-36`, `verified (source)`. Note tombi walks up from the
*file*, not the workspace root — so it works in detached/no-folder editing where taplo
does not.

### 3.3 The `#:schema` directive in tombi

`verified (source)` — `crates/tombi-ast-syntax/src/ast/impls/comment.rs:39-76` and
`152-184`. Resolution order for the value:

1. `file://.` / `file://..` / `file://./…` / `file://../…` — a tombi extension over
   RFC 8089, resolved against the **document's directory**. Documented:
   *"Although not defined by RFC 8089 … Tombi allows the specification of `.` and `..`
   in the hostname of the `file://` file URI."* `verified (docs)`.
2. Otherwise parse as a URI (`https://`, `file:///abs`, `tombi://…`).
3. Otherwise treat as a path: if relative, join to the document's directory;
   canonicalise; convert with `Url::from_file_path`. **An absolute path lands here and
   works.**

Fragments are supported throughout (`#/definitions/TableValue`, `#tableType`) — see the
committed tests at `crates/tombi-lsp/tests/test_goto_definition.rs:178-251`.

### 3.4 tombi's VS Code extension has no association settings

`verified (source)` — `editors/vscode/package.json` in the tombi repo contributes exactly
three settings: `tombi.path`, `tombi.args`, `tombi.env`. There is no `associations`
escape hatch and no `settings.json` override. The on-disk `tombi.toml` is the only
artifact. This is a *simplification* relative to taplo, not a gap.

---

## 4. Table B — Editors: what actually runs, and what artifact it reads

| Editor | TOML language server | Reads `.taplo.toml`? | Reads `tombi.toml`? | Needs its own artifact? |
|---|---|---|---|---|
| VS Code + `tamasfe.even-better-toml` | **taplo** (bundled `@taplo/lsp` WASM) | **yes**, auto-discovered | no | no — but `settings.json` can override at higher priority |
| VS Code + `tombi-toml.tombi` | **tombi** | no | **yes** | no |
| Neovim + nvim-lspconfig | **taplo** (`lsp/taplo.lua`) or **tombi** (`lsp/tombi.lua`) — user picks | yes (also a root marker) | yes (also a root marker) | **no** |
| Zed | **tombi only** (`zed-extensions/toml` is grammar-only) | **no** | yes | no |
| Helix | **both** — `language-servers = ["taplo", "tombi"]` by default for `toml` | yes | yes | no |
| Emacs `lsp-mode` | **taplo** (`lsp-toml.el`) | yes | no | no |
| Emacs `eglot` (`master` / Emacs 31) | **tombi** — `((toml-ts-mode conf-toml-mode) . ("tombi" "lsp"))` | no | yes | no |
| Emacs `eglot` (Emacs 30) | **none registered** | — | — | user must add a server entry |
| JetBrains IDEs (TOML plugin) | **none — no LSP at all** | **no** | **no** | **yes — `.idea/jsonSchemas.xml`** |
| JetBrains IDEs + tombi plugin | tombi via `com.intellij.platform.lsp` | no | yes | no |

Citations:

- **VS Code / Even Better TOML** — `verified (source)`, `editors/vscode/package.json` in
  `tamasfe/taplo`: dependency `"@taplo/lsp": "^0.8.0"`; setting `evenBetterToml.taplo.bundled`
  default `true`; `evenBetterToml.taplo.configFile.enabled` default `true`, described as
  *"Whether to enable the usage of a Taplo configuration file."*
- **`evenBetterToml.schema.associations`** — `verified (source)`, same file, verbatim
  description: *"The key must be a regular expression, this pattern is used to associate
  schemas with absolute document URIs. Overlapping patterns result in undefined
  behaviour and either matching schema can be used. The value must be an absolute URI to
  the JSON schema."* The doc link embedded in that description
  (`https://taplo.tamasfe.dev/configuration#visual-studio-code`) is a **404**.
  `verified (docs)` by fetching it.
  The value handling is `verified (source)` at `crates/taplo-lsp/src/world.rs:173-193`:

  ```rust
  let url = if schema_url.starts_with("./") { self.root.join(schema_url) }
            else { schema_url.parse() };
  ```

  So `./relative` (resolved against the **workspace root**, not the settings file) and
  `file:///abs` work; a bare `/abs/path` fails `Url::parse` and the association is
  dropped with `tracing::error!(… "invalid schema url")`. `..`-prefixed values are not
  special-cased.
- **`evenBetterToml.rules`** — `verified (source)`, manifest + `world.rs:253`
  (`self.taplo_config.rule.extend(self.config.rules.clone())`). This is the only
  `settings.json` route that accepts a bare local path, because it goes through
  `Options::prepare` (§2.1). Priority `CONFIG_RULE` (51), i.e. *lower* than
  `schema.associations`.
- **`TOML: Select Schema`** — `verified (source)`,
  `editors/vscode/src/commands/schema.ts` + `crates/taplo-lsp/src/handlers/schema.rs`:
  assigns `priority::MAX`, source `MANUAL`, is never written to `settings.json`, and the
  handler carries the comment `// FIXME: there is no way to remove these.`
- **Neovim** — `verified (source)`, `nvim-lspconfig/lsp/taplo.lua` in full:
  `cmd = { 'taplo', 'lsp', 'stdio' }`, `filetypes = { 'toml' }`,
  `root_markers = { '.taplo.toml', 'taplo.toml', '.git' }`. No `settings`, no
  `init_options`. `nvim-lspconfig/lsp/tombi.lua`: `cmd = { 'tombi', 'lsp' }`,
  `root_markers = { 'tombi.toml', 'pyproject.toml', '.git' }`. Neovim core ships no
  `runtime/lsp/` directory — `verified (source)` by absence.
- **Zed** — `verified (docs)`, <https://zed.dev/docs/languages/toml>: *"TOML support is
  available through the TOML extension… A TOML language server is available in the Tombi
  extension."* Taplo is not mentioned. `verified (source)`:
  `zed-extensions/toml/extension.toml` contains only `[grammars.toml]` and **no**
  `[language_servers.*]` block; the `zed-industries/extensions` registry has a `tombi`
  entry and **no** `taplo` entry.
- **Helix** — `verified (source)`, `helix-editor/helix/languages.toml`:
  `taplo = { command = "taplo", args = ["lsp", "stdio"], config = {} }`,
  `tombi = { command = "tombi", args = ["lsp"] }`, and for `name = "toml"`,
  `language-servers = [ "taplo", "tombi" ]`.
- **Emacs `lsp-mode`** — `verified (source)`, `emacs-lsp/lsp-mode/clients/lsp-toml.el`:
  `:server-id 'taplo`, `initializationOptions` = `(:configurationSection "evenBetterToml"
  :cachePath …)`, and the whole `evenBetterToml` settings surface mirrored via
  `lsp-defcustom`, including `lsp-toml-schema-associations` and
  `lsp-toml-taplo-config-file-enabled` (default `t`).
  `verified (docs)` — <https://emacs-lsp.github.io/lsp-mode/page/lsp-toml/>.
- **Emacs `eglot`** — `verified (source)`, `eglot-server-programs` in both
  `emacs-mirror/emacs` `master` `lisp/progmodes/eglot.el:319` and `joaotavora/eglot`
  `eglot.el:318`: `((toml-ts-mode conf-toml-mode) . ("tombi" "lsp"))`. On the
  `emacs-30` branch there is **no** TOML entry at all. `none documented` for any official
  eglot+taplo recipe.
- **JetBrains** — `verified (source)`,
  `intellij-community/plugins/toml/json/src/main/kotlin/org/toml/ide/json/TomlJsonSchemaEnabler.kt`
  and registry key `org.toml.json.schema` default `true` in
  `plugins/toml/core/src/main/resources/intellij.toml.core.xml`. The mapping store is
  `@State(name = "JsonSchemaMappingsProjectConfiguration", storages = @Storage("jsonSchemas.xml"))`
  in `json/backend/src/com/jetbrains/jsonSchema/JsonSchemaMappingsProjectConfiguration.java`,
  entries carrying `relativePathToSchema` + `patterns`. `verified (docs)` for the UI —
  <https://www.jetbrains.com/help/idea/json.html>: Settings → Languages & Frameworks →
  Schemas and DTDs → **JSON Schema Mappings**. SchemaStore catalogue constants live in
  `json/backend/src/com/jetbrains/jsonSchema/remote/JsonSchemaCatalogManager.java`.
  `none documented`: the JetBrains help page never names TOML as a SchemaStore consumer,
  though the mechanism is file-name based and TOML satisfies the enabler.

### 4.1 Does one written file serve them all? **No.**

`inferred`, from Table B:

Of the ten rows in Table B:

- `.taplo.toml` serves **four** (VS Code+EBT, Neovim-on-taplo, Helix, Emacs `lsp-mode`).
- `tombi.toml` serves **six** (VS Code+tombi, Neovim-on-tombi, Zed, Helix, Emacs `eglot`
  on `master`, JetBrains+tombi).
- Together they still miss JetBrains' **native** TOML support, which needs
  `.idea/jsonSchemas.xml` and reads neither, and Emacs 30's `eglot`, which registers no
  TOML server at all.
- The **only** artifact that spans both servers is the in-file `#:schema` directive —
  **eight of ten** rows, missing native JetBrains (no LSP) and Emacs 30 `eglot`
  (no server registered, so nothing to honour it).

An `unverified` corollary for Neovim, Helix and eglot: all three can forward arbitrary
settings to a server that asks for them, and taplo asks for section `evenBetterToml`
(`crates/taplo-lsp/src/config.rs`, default `configuration_section`). So
`vim.lsp.config('taplo', { settings = { evenBetterToml = { schema = { associations = … } } } })`,
Helix `[language-server.taplo.config.evenBetterToml.schema]`, and eglot's
`eglot-workspace-configuration` in `.dir-locals.el` are all mechanically equivalent to
the VS Code setting. `verified (source)` for each client's `workspace/configuration`
handler (`neovim runtime/lua/vim/lsp/handlers.lua` `lookup_section`;
`helix-term/src/application.rs` `MethodCall::WorkspaceConfiguration`; `eglot.el`
`eglot-workspace-configuration`) but `none documented` for the taplo-specific
combination. The experiment that would settle it: run the server with an LSP trace and
confirm the `workspace/configuration` reply carries the associations map.

---

## 5. Schema dialect — what a Rust derive emits vs what the consumer accepts

### 5.1 What taplo actually supports

The docs claim Draft 4:

> All features from the [Draft 4](https://json-schema.org/specification-links.html#draft-4)
> specification are supported, the schemas may contain external and even recursive
> references as well.

`verified (docs)` — <https://taplo.tamasfe.dev/configuration/developing-schemas.html>.
The CLI page says the same (*"validation via JSON Schemas (Draft 4)"*).

**The source says Draft 4/6/7, defaulting to Draft 7, with a silent fallback.**

- `verified (source)` — `crates/taplo-common/Cargo.toml`:
  `jsonschema = { version = "0.17.1", default-features = false }`.
- `verified (source)` — `jsonschema-0.17.1/src/schemas.rs:4-27`: the `Draft` enum has
  `Draft4`, `Draft6`, `Draft7` unconditionally; `Draft201909` and `Draft202012` are
  `#[cfg(feature = "draft201909")]` / `#[cfg(feature = "draft202012")]`. Neither feature
  is in `default` (`default = ["resolve-http", "resolve-file", "cli"]`), and taplo sets
  `default-features = false` anyway. `impl Default for Draft { Draft::Draft7 }`.
- `verified (source)` — `jsonschema-0.17.1/src/schemas.rs:184-206`, `draft_from_url` is
  **plain string equality** against five URIs, each with a **mandatory trailing `#`**:
  `http://json-schema.org/draft-0{4,6,7}/schema#` (plus the two feature-gated `https`
  2019-09/2020-12 ones). It returns `Option`, and the caller
  (`src/compilation/options.rs:301-322`) has no `else`:

  ```rust
  if self.draft.is_none() {
      if let Some(draft) = schemas::draft_from_schema(schema) { config.with_draft(draft); }
  }
  ```

  **An unrecognised `$schema` is not an error. It silently becomes Draft 7.**
- `verified (source)` — taplo never calls `with_draft`:
  `crates/taplo-common/src/schema/mod.rs:260-268` is
  `JSONSchema::options().with_resolver(…).with_format("semver", …).compile(schema)`.

`inferred`, and this is the headline dialect fact: **a schema declaring
`"$schema": "https://json-schema.org/draft/2020-12/schema"` is validated by taplo as
Draft 7, with no warning to anyone.** `prefixItems`, `unevaluatedProperties`,
`unevaluatedItems`, `dependentRequired` and `dependentSchemas` land in
`unmatched_keywords` and are ignored.

Primary evidence that this is observed in the wild, not just implied by the code: taplo
issue [#497](https://github.com/tamasfe/taplo/issues/497), *"Discrepancy in validation
with JSON Schema draft 2020-12"* (open since 2023-10-30), reports exactly that
`unevaluatedProperties: false` fails to invalidate. An issue is a primary source for
*"this is a known defect"*, not for *"this is how it works"* — the mechanism above is
the source-verified explanation.

Note `$defs` itself is fine: taplo resolves `$ref` fragments as raw JSON pointers
(`reference_url` strips the leading `#/`, `resolve_schema` prepends `/` and calls
`Value::pointer`), which is draft-agnostic. `verified (source)` —
`crates/taplo-common/src/schema/mod.rs:240-258`, `627-634`.

### 5.2 What tombi supports

`verified (source)` — `crates/tombi-schema-store/src/json_schema_dialect.rs:5-27`:
`enum JsonSchemaDialect { #[default] Draft07, Draft2019_09, Draft2020_12 }`, selected by
matching the `$schema` URI's **host and path** (so `http`/`https` and a trailing `#` are
both tolerated). Unknown → default Draft07.

The repo's own design document states the policy, verbatim (translated from Japanese;
`design/json-schema-compliance-policy.md`, `verified (source)`):

> The formally supported dialects are the three `draft-07` / `draft-2019-09` /
> `draft-2020-12`. … If `$schema` is specified, the dialect is determined from that URI.
> The default dialect when `$schema` is unspecified is `draft-07`. An unknown `$schema`
> URI is treated the same as unspecified and evaluated as `draft-07`.

So tombi accepts a 2020-12 schema natively where taplo silently downgrades it.

### 5.3 What `schemars` emits — measured, not read

`verified (experiment)`. Two binaries were compiled and run here against the real crates
(`schemars 0.8.22` and `schemars 1.2.2`) over the same input types: a `struct
ConfigPath(String)`, a doc-commented unit enum, a plain unit enum, an externally tagged
enum, an untagged enum, an internally tagged enum, `#[serde(default)]`,
`#[serde(default = "fn")]` and `#[serde(transparent)]`. The relevant output rows:

| Construct | schemars 0.8 (default) | schemars 1.x (default) | schemars 1.x with `SchemaSettings::draft07()` |
|---|---|---|---|
| Root `$schema` | `http://json-schema.org/draft-07/schema#` | `https://json-schema.org/draft/2020-12/schema` | `http://json-schema.org/draft-07/schema#` |
| Definitions | `definitions` | `$defs` | `definitions` |
| Field with metadata + named type | `{"description":…, "default":…, "allOf":[{"$ref":…}]}` | `{"description":…, "$ref":…, "default":…}` | `{"description":…, "allOf":[{"$ref":…}], "default":…}` |
| Unit enum, no variant docs | `{"type":"string","enum":["Quiet","Verbose"]}` | same | same |
| Unit enum, **with** variant docs | `oneOf` of `{"description":…,"type":"string","enum":["quiet"]}` | `oneOf` of `{"description":…,"type":"string","const":"quiet"}` | `oneOf` of `const` |
| Externally tagged enum with data | `oneOf` of wrapper objects, `additionalProperties:false` | same | same |
| Internally tagged (`#[serde(tag)]`) | `oneOf`, tag as `enum:["A"]` | `oneOf`, tag as `const:"A"` | `oneOf`, `const` |
| `#[serde(untagged)]` | **`anyOf`** | **`anyOf`** | `anyOf` |
| `struct ConfigPath(String)` | `{"description":…, "type":"string"}` — **transparent** | same | same |
| `#[serde(transparent)]` newtype | inlined `{"type":"string"}`, no `$defs` entry | same | same |
| `#[serde(default = "f")]` | `"default": "quiet"`, field dropped from `required` | same | same |
| `#[serde(default)]` on `u32` | `"default": 0`, dropped from `required` | same | same |
| Doc comment | whole comment → `description`; `title` only if the first line is a markdown ATX heading | same (whitespace handling differs) | same |

Corroborating `verified (source)` from the schemars trees:
`schemars/src/generate.rs:66-72` (`Default for SchemaSettings` = `draft2020_12()` in 1.x,
`draft07()` in 0.8); the four presets `draft07()`, `draft2019_09()`, `draft2020_12()`,
`openapi3()` with their `meta_schema` and `definitions_path`;
`schemars_derive/src/schema_exprs.rs:471-484` (`let keyword = if unique { "oneOf" } else { "anyOf" }`,
with untagged forcing `unique = false`); `schemars/src/_private/rustdoc.rs`
`get_title_and_description` (heading-gated title split, **not** first-line-vs-rest);
`schemars/src/_private/mod.rs:174-197` (autoref specialisation — the `default` keyword is
silently omitted if the type does not implement `Serialize`).

Two corrections to beliefs stated in the ticket brief:

- **`oneOf` → `anyOf` for untagged enums did not change between 0.8 and 1.x.** 0.8.22
  already emitted `anyOf` for untagged. `verified (source)` —
  `schemars/tests/expected/enum-untagged.json` at `v0.8.22` and the identical comment in
  `schemars_derive/src/schema_exprs.rs`. The real `anyOf`→`oneOf` transition was 0.8.6
  (2021-09-26) and it went the *other* way, for *tagged* enums only. A genuine new 1.x
  case exists: `#[serde(untagged)]` on an *individual variant* (added 1.0.0-alpha.19)
  demotes an otherwise-tagged enum's combiner to `anyOf`.
- **A newtype such as `ConfigPath` is already transparent** in both majors — it produces
  `{"type":"string"}`, not a wrapper. `#[serde(transparent)]` / `#[schemars(transparent)]`
  changes *identity*, not structure: the derive forwards `schema_name`/`schema_id`/
  `json_schema` to the inner type, so the newtype loses its `title` and its `$defs` entry
  entirely — **unless** the struct or its field carries any metadata attribute (a doc
  comment counts), in which case the full-delegation path is disabled and `title`/
  `description`/validation are retained. `verified (source)` —
  `schemars_derive/src/lib.rs:181-198`.

### 5.4 Table C — where it degrades, in terms a user sees

The question is not "does the keyword parse" but "what appears on screen". taplo's
completion and hover walk the raw JSON themselves; only diagnostics go through
`jsonschema`. The two paths degrade differently.

| Construct emitted | Completion offered | Hover description | Diagnostic reported |
|---|---|---|---|
| `{"type":"string","enum":[…]}` (unit enum, no docs) | **yes** — one item per enum value, correct TOML quoting | the schema's `description` | correct `… is not one of […]` |
| `oneOf` of `const` (unit enum **with** variant docs) | **yes** — one item per branch, each carrying its own branch `description` | per-branch descriptions concatenated | see below |
| `oneOf` of objects (tagged / externally tagged enums) | **yes but undiscriminated** — the union of keys from *all* branches is offered, regardless of which variant the document is | descriptions of all matching branches concatenated | **degraded** — see below |
| `anyOf` (untagged enums) | same union behaviour | same | `… is not valid under any of the schemas listed in the 'anyOf' keyword` |
| `{"description":…, "allOf":[{"$ref":…}], "default":…}` (schemars 0.8 / 1.x-draft07) | **yes, with the field's own doc comment and default** | field description lost on key hover; type description shown | fine |
| `{"description":…, "$ref":…, "default":…}` (schemars 1.x default) | **description and default silently dropped** | field description lost; type description shown | fine (annotations only) |
| newtype `ConfigPath` → `{"type":"string"}` | string-value snippet offered | the newtype's doc comment as `description` | correct |
| `"default": …` on a scalar field | offered as a completion item labelled with the TOML rendering of the default | shown | field correctly not `required` |

Citations for each row:

- **Union, not discrimination.** `verified (source)` —
  `crates/taplo-common/src/schema/mod.rs:328-400` (`collect_schemas`) and `496-595`
  (`collect_child_schemas`) both do
  `for one_of in schema["oneOf"].as_array() { recurse(one_of) }` and the same for
  `anyOf`, unconditionally, with no attempt to test the current value against each
  branch. Every branch's keys end up in the completion list.
- **Value completion reads `enum`, `const` and `default` directly.** `verified (source)` —
  `crates/taplo-lsp/src/handlers/completion.rs:460-575`, `add_value_completions`: an
  `enum` array produces one item per value with per-index docs from the `x-taplo` docs
  extension or the schema `description`; then `const`; then `default`.
- **The `$ref`-sibling drop.** `verified (source)` — `collect_child_schemas` starts with
  `if let Some(schema) = self.ref_schema_value(root_url, schema).await { return … }`
  (`mod.rs:496-514`, `ref_schema_value` at `601-620`) — the siblings of `$ref` are
  discarded before anything else happens. The `allOf` form is handled explicitly by a
  special case whose own comment reads
  `// Deal with the { "description": "Foo", "allOf": [{ "$ref": "Bar" }] } pattern.`
  (`mod.rs:529-568`), which merges the resolved `$ref` **under** the wrapper's own keys,
  so `description` and `default` survive. taplo's docs state the rule plainly:
  *"The `x-taplo` field (and any other fields) are ignored if `$ref` is present in an
  object."* `verified (docs)`.
  `inferred`: schemars 0.8's output shape is exactly what taplo was written to handle;
  schemars 1.x's default output is exactly what taplo drops.
- **`oneOf` diagnostics.** `verified (source)` —
  `jsonschema-0.17.1/src/keywords/one_of.rs:68-96`: `get_first_valid` returns the index
  of the first branch that validates; if none does, the *only* error produced is
  `ValidationError::one_of_not_valid`, rendered by
  `src/error.rs:844-848` as
  `"{instance} is not valid under any of the schemas listed in the 'oneOf' keyword"`,
  where `{instance}` is the **whole failing value**. taplo passes that string straight
  through as the diagnostic message
  (`crates/taplo-lsp/src/diagnostics.rs:300-320`, `error.error.to_string()`).
  `inferred`, and this is the concrete user-visible cost: a typo in one key inside an
  externally tagged enum variant produces *one* diagnostic on the entire table saying
  the table matches no variant, instead of "unknown key".
  If two branches both validate, the message is
  `"… is valid under more than one of the schemas listed in the 'oneOf' keyword"`.
- **Known-defect evidence, and a correction.** taplo issue
  [#857](https://github.com/tamasfe/taplo/issues/857) (open, 2026-04-01),
  *"`oneOf` with `const` discriminator validates against wrong branch"*, is widely the
  obvious citation here. **It is filed on the wrong tracker.** Its quoted error text is
  `The value must be one of ["…"], but found "…"`, which is **tombi's** wording —
  `crates/tombi-validator/src/diagnostic.rs:72`,
  `#[error("the value must be one of [{}], but found {actual}", .expected.join(", "))]`.
  Neither taplo nor `jsonschema` 0.17.1 produces that string (`grep` for `must be one of`
  in both trees returns nothing; `jsonschema` says `"{} is not one of {}"`). The reporter
  was in Zed, and Zed runs tombi (§4). `verified (source)`. So #857 is primary evidence
  of a **tombi** wrong-branch defect, not a taplo one. taplo issue
  [#739](https://github.com/tamasfe/taplo/issues/739) is *not* usable either — the
  reporter closed it the same day with *"Never mind. The schema is wrong."*
- **tombi's `oneOf` handling is structurally different.** `verified (source)` — tombi has
  explicit branch-selection machinery that taplo lacks:
  `crates/tombi-validator/src/match_evidence.rs` (a `MatchEvidence` struct counting
  matched root/type/singleton assertions and evaluated locations),
  `crates/tombi-validator/src/branch_evaluation.rs` (`enum BranchApplicability { Applicable,
  Rejected { diagnostic_ranges } }`, `enum Applicator { OneOf, AnyOf }`), and
  `crates/tombi-validator/src/validate/one_of.rs`. Its design doc commits to composing
  `EvaluatedLocations` across `oneOf`/`anyOf`/`allOf`/`if-then-else` rather than
  approximating. `unverified` behaviourally: I read the implementation but could not run
  an editor. Given #857 the machinery is evidently not yet correct in all cases. The
  experiment that would settle it: feed the schemas `tp` will actually emit to
  `tombi lint` and to `taplo lint` from the CLI (both are headless and both apply
  `#:schema`) and diff the diagnostics.

---

## 6. Sources

**taplo** — docs: [directives](https://taplo.tamasfe.dev/configuration/directives.html),
[configuration file](https://taplo.tamasfe.dev/configuration/file.html),
[using schemas](https://taplo.tamasfe.dev/configuration/using-schemas.html),
[developing schemas](https://taplo.tamasfe.dev/configuration/developing-schemas.html),
[CLI validation](https://taplo.tamasfe.dev/cli/usage/validation.html).
Source (`master`, `08f343be0`): `crates/taplo-common/src/config.rs`,
`crates/taplo-common/src/environment/native.rs`,
`crates/taplo-common/src/schema/{mod,associations,cache}.rs`,
`crates/taplo-common/Cargo.toml`,
`crates/taplo-lsp/src/{world,config}.rs`,
`crates/taplo-lsp/src/handlers/{completion,hover,configuration,documents,schema}.rs`,
`crates/taplo-lsp/src/diagnostics.rs`,
`crates/taplo-cli/src/{lib,args}.rs`, `crates/taplo-cli/src/commands/lint.rs`,
`crates/taplo/src/dom/{mod,node}.rs`,
`editors/vscode/package.json`, `editors/vscode/src/client.ts`.
Issues cited: [#497](https://github.com/tamasfe/taplo/issues/497),
[#739](https://github.com/tamasfe/taplo/issues/739),
[#857](https://github.com/tamasfe/taplo/issues/857).

**tombi** — docs: [configuration](https://tombi-toml.github.io/tombi/docs/configuration),
[JSON Schema](https://tombi-toml.github.io/tombi/docs/json-schema),
[schema document directive](https://tombi-toml.github.io/tombi/docs/comment-directive/schema-document-directive),
[differences from Taplo](https://tombi-toml.github.io/tombi/docs/reference/difference-taplo),
[installation](https://tombi-toml.github.io/tombi/docs/installation).
Source (`main`, `825161b60`): `crates/tombi-config/src/lib.rs`,
`crates/tombi-schema-store/src/{store,json_schema_dialect,keyword_support}.rs`,
`crates/tombi-uri/src/{lib,schema_uri}.rs`,
`crates/tombi-ast-syntax/src/ast/impls/comment.rs`,
`crates/tombi-validator/src/{match_evidence,branch_evaluation,diagnostic}.rs`,
`crates/tombi-validator/src/validate/one_of.rs`,
`design/json-schema-compliance-policy.md`, `editors/{vscode,zed,intellij}/`.

**Editors** — `neovim/nvim-lspconfig` `lsp/{taplo,tombi}.lua`; `neovim/neovim`
`runtime/lua/vim/lsp/handlers.lua`; [Zed TOML docs](https://zed.dev/docs/languages/toml),
`zed-extensions/toml/extension.toml`, `zed-industries/extensions/extensions.toml`;
`helix-editor/helix/languages.toml` and `book/src/languages.md`,
`helix-term/src/application.rs`, `helix-lsp/src/client.rs`;
`emacs-lsp/lsp-mode/clients/lsp-toml.el` and
[lsp-toml docs](https://emacs-lsp.github.io/lsp-mode/page/lsp-toml/);
`emacs-mirror/emacs` `lisp/progmodes/eglot.el` (`master` and `emacs-30`);
`JetBrains/intellij-community` `plugins/toml/**` and `json/backend/**`,
[JetBrains JSON help](https://www.jetbrains.com/help/idea/json.html).

**Crates** — [`schemars` 1.2.2](https://docs.rs/schemars/1.2.2/schemars/) and its
`GREsau/schemars` tree at `v1.2.2` / `v0.8.22` (including
`schemars/tests/expected/*.json` and the 1.x snapshot files);
[`jsonschema` 0.17.1](https://docs.rs/jsonschema/0.17.1/) source from crates.io;
`url` 2.x. Local experiments: `url` parse table (§2.6), `schemars` 0.8.22 and 1.2.2
schema generation over the same input types (§5.3), `schemars` 1.2.2 with
`SchemaSettings::draft07()` (§5.3).

**Specs** — [RFC 8089](https://www.rfc-editor.org/rfc/rfc8089) (the `file` URI scheme;
cited because tombi's `file://.` form is explicitly an extension over it).

---

## 7. Consolidated unknowns

| Claim | Why it is not verified |
|---|---|
| Windows end-to-end behaviour of an absolute `[schema] path` / `#:schema` | The `url` parse result is `verified (experiment)`; the resulting editor diagnostic is `unverified`. Experiment: on Windows, set `[schema] path = "C:\\tmp\\s.json"`, open a matching file, read the taplo output channel for ``the scheme `c` is not supported``. |
| Whether Neovim / Helix / eglot actually deliver `evenBetterToml.*` to taplo | Mechanically implied by three source facts; `none documented` for the combination. Experiment: run the server under an LSP trace and inspect the `workspace/configuration` reply. |
| Whether tombi's branch-evidence machinery picks the right `oneOf` branch for schemars-shaped enums | Implementation read, not run, and #857 says it sometimes does not. Experiment: `tombi lint` and `taplo lint` over a fixture using the schema `tp` will emit; diff the diagnostics. |
| Whether `contributes.tomlValidation` accepts a local URL | Only `https://` examples appear in taplo's docs; the manifest schema is not published. `none documented`. |
| Whether JetBrains applies a SchemaStore catalogue entry to a `.toml` file in practice | The catalogue matcher is file-name based and the TOML enabler is on by default, but no JetBrains doc names TOML as a SchemaStore consumer. `none documented`. |
| Exact behaviour when both `.taplo.toml` and `taplo.toml` exist in one directory | `read_dir` order is filesystem-dependent (§2.3). Non-deterministic by construction; do not rely on it. |
| Whether the disk schema cache is keyed in a way that survives a `tp` version bump | The cache key is `sha1(url)` (`cache.rs:140-144`), so a *versioned* cache path yields a new key. Not exercised here. |

---

## 8. Answers to the ticket's five questions

**1. Which association mechanisms actually exist for TOML, and who consumes them.**
Two families. (a) A **per-file header directive**, `#:schema <value>`, invented by taplo
and reimplemented by tombi as an explicit compatibility feature; it is consumed by the
*language server*, in both LSP and CLI modes, not by an editor extension. A sibling
form, `"$schema" = "…"` as a root key, exists in both but is strictly weaker.
(b) An **external mapping file**, which is server-specific and not shared: taplo reads
`.taplo.toml`/`taplo.toml` with `[schema] path` and `[[rule]] include` + `[rule.schema]
path`; tombi reads `.tombi.toml`/`tombi.toml`/`.config/tombi.toml`/`[tool.tombi]` with
`[[schemas]] path` + `include`. On top of that, the VS Code extension adds its **own**
`evenBetterToml.schema.associations` (regexes over document URIs) and
`evenBetterToml.rules`, which sit at *higher* priority than the config file and are
consumed by the extension's LSP client, not by the file.

**2. Does a local filesystem path work where a URL is expected, and may it be relative?**
Yes, in the mechanisms that matter, and both relative and absolute — with three
qualifications. In `.taplo.toml`'s `schema.path`, in tombi's `[[schemas]] path`, and in
both servers' `#:schema` directive, a value that fails to parse as a URL is treated as a
path, absolutised, and converted to a `file://` URL that the loader reads from disk.
Qualification one: **the base for a relative path differs** — taplo resolves it against
the *workspace root* (LSP) or *cwd* (CLI), never the config file; tombi resolves it
against the *directory containing the config file*; the directive resolves against the
*document*. Qualification two: **the VS Code `schema.associations` setting is the
exception** — a bare absolute path is dropped there; it needs `./relative` or a `file://`
URL. Qualification three: **on Windows a bare absolute path is broken everywhere**,
because the drive letter parses as a URL scheme before the path branch is ever reached.
So the answer to the load-bearing question is: a mechanism that only accepts URLs does
*not* foreclose the gesture, because the mechanisms accept paths — but a writer must emit
`file:///C:/…` on Windows, and an absolute path is the only form immune to the
base-directory divergence.

**3. Is the mapping file's location fixed, or discoverable up the tree?**
**Discoverable up the tree, in both servers** — despite taplo's docs saying otherwise.
taplo walks from the workspace root (LSP) or cwd (CLI) to the filesystem root; tombi
walks from the opened file's directory (LSP) or cwd (CLI) to the filesystem root and then
falls back to user- and system-level config. **There is no mismatch with D14**: a file
written at the repository root is found by both, from anywhere at or below it. Two
caveats: taplo skips config discovery entirely for a detached file with no workspace
folder, and taplo's *relative glob* resolution (not the discovery) is anchored to the
workspace root, so a `.taplo.toml` at the repo root plus a subdirectory workspace makes
`include = ["tp.toml"]` point at the wrong path — use `**/tp.toml`.

**4. Is the dialect the Rust derive emits one the consumer accepts, and where does it
degrade?**
Only if the derive is configured for it. `schemars` 1.x defaults to **2020-12**; taplo
supports **Draft 4/6/7 only** and silently reinterprets an unrecognised `$schema` as
Draft 7 — no error, no warning, no diagnostic. tombi accepts 2020-12 natively. Beyond the
dialect label, the specific degradations are: (a) **`oneOf` over enums** — taplo unions
all branches for completion, so every variant's keys are offered at once regardless of
which variant is present, and a failure produces a single opaque
`"… is not valid under any of the schemas listed in the 'oneOf' keyword"` on the whole
table rather than a pointed message; (b) **`$ref` siblings** — schemars 1.x's default
output puts `description` and `default` next to `$ref`, and taplo discards siblings of
`$ref`, so per-field doc comments and defaults vanish from completion; schemars 0.8 and
schemars 1.x under `SchemaSettings::draft07()` emit the `allOf: [{$ref}]` wrapper that
taplo explicitly handles, and the metadata survives; (c) **newtypes such as
`ConfigPath`** — already transparent in both schemars majors, no degradation, they render
as `{"type": "string"}` carrying the type's own doc comment; (d) **defaults** — emitted as
the `default` keyword, the field is correctly dropped from `required`, and taplo offers
the default as a completion item and shows it on hover, *except* in the `$ref`-sibling
case above.

**5. What does the mapping look like across the editors that matter, and does one file
serve them all?**
**No.** `.taplo.toml` serves VS Code (Even Better TOML), Neovim-on-taplo, Helix and Emacs
`lsp-mode`. It serves nothing else. Zed ships no TOML language server and its docs point
at tombi; Emacs `eglot` on `master` maps TOML to tombi; JetBrains uses neither server, has
its own JSON Schema engine for TOML, and stores mappings in `.idea/jsonSchemas.xml`.
Writing one file therefore covers roughly half the field; covering the servers takes two
files (`.taplo.toml` **and** `tombi.toml`) and covering JetBrains takes a third, in an
XML format that is an IDE state file rather than a hand-authored one. The single artifact
that spans both language servers — and therefore every editor that runs one at all —
is the in-file `#:schema` header directive.

---

## 9. What this means for the `--write-editor-config` gesture

**Recommendation: drop it as specified.**

The mechanism is not the problem — an absolute local path in `.taplo.toml` genuinely
works on Unix, and the file is discovered by an upward walk that matches D14 exactly. The
gesture fails on four other grounds, each independently sufficient:

1. **One written file cannot serve the editors.** The gesture's premise is a single
   glob→schema mapping. There is no such thing: `.taplo.toml` reaches four of the ten
   editor configurations in Table B, `tombi.toml` reaches six mostly-different ones, and
   JetBrains' native TOML support reads neither. Writing one
   file means silently choosing a subset of users and, worse, choosing the *shrinking*
   subset — taplo has had no release in sixteen months and no Marketplace publish in
   twenty-one, while its two most visible former hosts (Zed, eglot) have already moved to
   tombi. Writing all three artifacts is a maintenance surface out of all proportion to a
   convenience gesture.

2. **Both candidate files are shared, user-owned config, and both fail closed.** They also
   carry formatting options, `include`/`exclude` for the whole repository, and lint rules.
   taplo parses its config with `#[serde(deny_unknown_fields)]` and, on any parse error,
   logs `tracing::warn!("invalid configuration file")` and falls back to `Config::default()`
   — the user's formatting configuration silently stops applying, with the only evidence in
   a log channel nobody reads. A merging writer for that file is a footgun; a clobbering
   writer is worse.

3. **The value being written is machine-specific, and these files are committed.** The
   materialised path is an absolute path under a versioned cache directory in the user's
   home. Writing it into `.taplo.toml` — a file whose whole purpose is to be checked in —
   produces a repository that is wrong for every other machine and every CI runner. It is
   also outright broken on Windows, where a bare drive-lettered path parses as a URL with
   scheme `c` and is rejected by the loader.

4. **What is written goes stale invisibly.** The schema is cached for 60 s in memory and
   600 s on disk, including `file://` schemas; the disk cache key is `sha1(url)`, so a
   version bump of the cache path silently orphans the old entry; no file watcher is
   registered for either the schema or `.taplo.toml`; and `.taplo.toml` is only re-read
   when the editor sends `didChangeConfiguration`. A user who runs the gesture and sees
   nothing happen has no way to distinguish "it didn't work" from "restart your editor",
   and `tp` cannot tell them which.

**What should exist instead is not a written file but printed text.** `tp config schema`
already knows the materialised path; the honest gesture is to *show* the three-line
snippet for each supported consumer and let the user place it, because only the user
knows which server they run and whether their `.taplo.toml` is committed. That costs one
`println!` and carries none of the four risks above.

**If the team insists on writing something anyway**, the one artifact with a defensible
claim to portability is the `#:schema` header directive — it is honoured by both servers,
at the highest non-manual priority, needs no discovery, needs no second file, and works in
detached/no-folder editing where `.taplo.toml` is not even looked for. But it must point
at a **project-relative** path, not the cache path, because it lives inside the user's
committed `tp.toml`; and materialising a project-relative copy is a different artifact from
the one D8 specified. That is a change to D8, so it is out of scope here and is recorded
only so the option is not lost.

**One finding from this ticket does bear directly on D8 and should be carried back**,
because it costs nothing and is strictly an improvement: **generate the schemas with
`SchemaSettings::draft07()`, not the schemars 1.x default.** Measured here, that single
change emits `$schema: "http://json-schema.org/draft-07/schema#"` — the exact string
`jsonschema` 0.17.1 recognises, trailing `#` included — and restores the
`allOf: [{"$ref": …}]` wrapper that taplo is written to handle, which is what preserves
per-field doc comments and defaults in completion. tombi accepts draft-07 as its own
default dialect, so nothing is lost on that side. The default 2020-12 output is silently
downgraded by taplo *and* loses metadata; the draft-07 output is understood correctly by
both.
