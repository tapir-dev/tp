# Automatic theme selection is a subscription, not a first-run guess

`appearance.theme = "auto"` resolves the active theme at start-up and re-resolves
it whenever the terminal reports that its colour scheme changed. There is no
separate setting for following the terminal, and nothing is written to disk on
first run.

The brief asks for two things — auto-detect the terminal background on first run
to pick a light or dark default, and support a "follow terminal appearance"
selection. They are one mechanism, and both lines narrow.

## Why one mechanism rather than two

The two lines differ only in whether the product keeps listening after the first
answer. Once the notification is enabled, the terminal pushes the change whether
or not anyone asked for it, and re-resolving is a theme epoch bump that already
forces every component to rebuild. There is no work saved by declining to listen,
and no state to keep.

A separate follow setting would therefore be a switch whose "off" position means
*hold a value you know is stale*. The user changed their terminal's appearance;
the request to repaint is the change itself. A mode that ignores it exists to
serve nobody, and it would be a second thing that can disagree with the first —
`theme = "auto"` with follow off is a configuration that has to be explained
rather than read.

## Why nothing is persisted on first run

Detecting once and writing the answer down produces a value that goes stale
silently. The user switches their terminal to light six months later and the
product stays faithful to a measurement nobody remembers taking, with nothing in
the interface to say where it came from. Under a resolution ladder there is no
first run at all: `auto` resolves every run, from the current answer.

Writing to the global configuration layer is also already reserved for a
deliberate gesture — the one that saves a session-only choice as the startup
default — which preserves formatting and triggers a reload. A product that writes
that file by itself on first launch takes an action the user has a gesture for.
That gesture extends to the theme, so persisting remains reachable, by hand.

## Consequences

- **Two lines of the brief narrow, and neither is overturned.** Auto-detection
  happens, and following happens; what goes is the first-run framing and the
  second setting. The capability the brief asked for is delivered whole.
- **An explicit theme neither detects nor follows.** Naming a theme is a
  statement about what the user wants to look at, not a starting point to be
  revised. Only `auto` subscribes.
- **`auto` is a reserved theme name.** The key's value type is a theme's name,
  so the magic value and a legitimate name occupy one space. Reserving the word
  is a build assertion over the built-in themes and a validation error on a user
  theme that claims it. The alternative — a second key naming the mode — creates
  two keys that can contradict each other, and a state where one says fixed and
  the other names nothing.
- **The notification is routed rather than discarded.** Unsolicited colour-scheme
  notifications already arrive from at least one multiplexer and are currently
  consumed and thrown away by the input fork. Recognising this one and delivering
  it is a third case in a patch that already sits at that point in the parser.
- **A change repaints everything, by a mechanism that already exists.** Theme
  changes bump the theme epoch, which misses every renderer cache key and rebuilds
  every component. Nothing new is required to make the switch total.
