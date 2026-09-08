# Content exclusion is enforced by a closed attribute value type

Measurements carry ids, names, counts, durations, statuses and usage numbers
only — never prompts, completions, tool arguments or results, file contents,
provider payloads, headers, or credentials. This is a security property, and a
security property that lives in prose has already failed, so the rule is made
unexpressible rather than merely documented: the attribute value type is a
closed enumeration with an id case, a name case, a compile-time literal case, a
signed integer, a float, a bool and a duration, and **no free-string case at
all**. Code that wants to attach a prompt to a measurement does not fail review;
it fails to compile.

The invariant is stated over **origin**, not over shape, because shape cannot
carry it. A model id, a tool name and a surface id are all runtime strings and
all legitimate attributes. What distinguishes them from a prompt is where they
came from, so the rule is that no string in a measurement may originate from
model output, filesystem bytes, or a provider payload. That is enforceable
because each of those legitimate strings arrives through a newtype whose
constructor is private to the registry that owns it — the model catalog, the
tool registry, the surface table — and none of those registries is fed from an
excluded origin.

A module boundary was considered as the primary mechanism and demoted to a
secondary one, because it cannot hold on its own. The telemetry crate depends on
none of the crates carrying message, tool-result or provider-payload types, so
in most of the product the forbidden content is genuinely out of scope. But the
provider-request measurement is emitted *by* the provider seam rather than
injected into it, and that seam lives in the crate that holds the payloads. At
exactly the point where the risk is highest, the boundary defence is absent and
the type is the whole of the defence. That asymmetry is the reason the type
comes first.

## Consequences

- Adding a case to the attribute value type is a security-relevant change, not a
  convenience one. A test asserts the declared set so the addition is visible in
  review rather than incidental.
- Attaching a genuinely new kind of string to a measurement requires minting a
  newtype and naming the registry that owns it. This is deliberate friction: the
  question "where did this string come from?" has to be answered before the
  attribute can exist.
- Diagnostics are a separate mechanism for this reason. `tracing` diagnostics may
  carry content, are local-only, and never reach a sink — keeping them in the
  same mechanism as measurements would mean a future exporter attached to the
  subscriber picks up the content along with everything else, which is the exact
  retrofit this invariant exists to prevent.
