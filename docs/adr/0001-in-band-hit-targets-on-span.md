# Hit targets ride in band on `Span`

A component renders with `render(width) -> Vec<Line>` and never learns its
absolute position or its mode, so it cannot report where anything clickable
landed. Rather than add a `hit_regions(width)` hook — which would have to
return coordinates the component does not know — a `Span` carries a **hit
target** in band, alongside the OSC 8 hyperlink target and image placement it
already holds; the terminal driver knows where each Span landed after layout, so
a cell resolves to a Span and the Span names what was hit.

This mirrors the cursor marker, which solved the same class of problem the same
way: an in-band payload survives slicing, concatenation and reordering, while
out-of-band coordinates force every container to translate its children's
positions.

## Consequences

- The hit target is one field holding an enum (`Link(url) | Target(id)`), not
  two fields plus a tie-break rule. The brief's "hyperlinks take priority over
  parent click regions" then falls out of granularity — a Span-level target is
  narrower than a driver-laid-out region, so it is reached first on the hit
  chain — rather than being a rule anyone has to remember.
- Coarse regions (a whole list row, a scroll view) are published by the driver's
  layout, not by components, because only the driver knows their extents.
- `Span` grows a field that is dead weight in scrollback mode, where the mouse
  is never captured and hit testing does not run at all.
