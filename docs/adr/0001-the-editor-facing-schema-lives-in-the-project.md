# ADR-0001: The editor-facing JSON Schema lives in the project, not in the cache

## Status

Accepted. Resolves [#42](https://github.com/tapir-dev/tp/issues/42); amends [#14](https://github.com/tapir-dev/tp/issues/14)-D8.

## Context

#14-D8 materialises the three generated JSON Schemas into the version-keyed cache
directory, per #11-D6, and has an opt-in gesture write a glob-to-schema mapping
that points at that path. #30 then measured the mechanism against running
servers, and the cache path turns out to be the wrong thing for a *mapping file*
to name:

- The mapping files that carry the association — `.taplo.toml` and `tombi.toml` —
  live at the repository root and are routinely committed. A cache path is
  machine-specific, so a committed file names a path that exists on exactly one
  machine.
- #11-D6 version-keys the cache, so the named path is `…/tp/<version>/schemas/…`
  and dies at the next upgrade. Nothing notices: taplo registers no
  `FileSystemWatcher` anywhere, and its disk schema cache is keyed on `sha1(url)`,
  so a version bump silently orphans the entry.
- An absolute path is the form that is broken on Windows in both servers: a
  leading drive letter parses as a URL scheme before the filesystem branch is
  reached, and the loader fails with an unsupported-scheme error.
- The failure is silent. In the taplo LSP a schema that cannot be loaded produces
  an empty diagnostic list and one line in a trace channel. The user sees
  completion stop working and cannot tell that from "restart your editor".

The alternative considered was an *unversioned* cache path, `…/tp/schemas/`. It
fixes staleness only, leaves the machine-specific and Windows problems standing,
and costs a second materialisation rule plus contention between two installed
`tp` versions writing one file.

## Decision

`tp config schema --write-editor-config` materialises the three schemas into
**`.tp/schemas/`, inside the user's project**, and the mapping it writes or prints
names them by a **project-relative path**. The schemas are meant to be committed
alongside `.tp/config.toml`.

The version-keyed cache materialisation of #11-D6 is untouched and unamended: it
still serves the agent reading its own reference documentation. It simply stops
being the path any editor is pointed at. The two materialisations have different
readers and different lifetimes, which is why they are two.

## Consequences

- The path in the committed mapping file is stable across machines, across `tp`
  upgrades, and carries no drive letter, so the Windows failure mode is not
  reached at all. That last point is **inferred, not measured** — neither research
  pass had a Windows machine.
- A generated JSON artifact appears in the user's repository. This is accepted:
  it is written only on explicit invocation, only under `.tp/`, which `tp`
  already owns, and being a tracked file makes drift visible in a diff rather
  than invisible in a cache.
- If `.tp/schemas/` is *not* committed, a colleague's checkout loses completion
  silently — there is no diagnostic. Worse, the schema is cached for 600 s on
  disk including `file://` sources with no watcher, so it is not picked up
  promptly even once the file appears. The generated documentation must say to
  commit it.
- Relative resolution in `.taplo.toml` is correct only when the editor's
  workspace root is the repository root, because taplo anchors relative paths at
  the workspace root rather than at the config file's directory. VS Code enforces
  this for us (its bundled WASM build does not walk up at all, so the file must
  sit at the workspace root exactly); elsewhere it is a documented limitation.
  `tombi.toml` has no such condition — it anchors at the config file's directory.
- `tp` knows its own embedded schema, so it can compare against `.tp/schemas/`
  and report drift. Nothing else can.
