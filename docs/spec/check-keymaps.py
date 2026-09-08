import tomllib, sys, collections, os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "keymaps") + os.sep

NS = {
    "completion": 4,
    "editor": 35, "single_line_input": 9, "select_list": 7, "transcript": 10,
    "search": 4, "sessions": 3, "session_tree": 7, "branch_summary": 1,
    "picker": 2, "dialog": 2, "settings": 5, "app": 14,
}

# Every chain the driver can assemble, innermost first. app is layer 3 and is
# appended to all of them. A context carrying an advisory context (layer 0) is
# listed twice: once with it, once without, because it is in the chain only
# while its overlay is shown.
CHAINS = [
    ("editor",),                              # base surface, scrollback
    ("editor", "transcript"),                 # base surface, fullscreen
    ("completion", "editor"),
    ("completion", "editor", "transcript"),
    ("single_line_input", "search"),
    ("single_line_input", "branch_summary"),
    ("single_line_input", "settings"),        # the filter, once focused
    ("select_list", "settings"),
    ("select_list", "sessions"),
    ("select_list", "session_tree"),
    ("select_list", "picker"),
    ("dialog",),
    ("single_line_input", "dialog"),          # the text-input dialog primitive
]
CHAINS = [c + ("app",) for c in CHAINS]

TEXT_ENTRY = {"editor", "single_line_input"}

BANNED_PREFIX = ("ctrl+shift+",)
BANNED_KEYS = {
    "ctrl+tab", "ctrl+shift+tab", "shift+space", "shift+backspace",
    "insert", "shift+insert", "ctrl+insert", "ctrl+shift+insert",
    "shift+f10", "f11", "ctrl+page_up", "ctrl+page_down",
    "alt+space", "alt+tab", "ctrl+enter",
    "ctrl+i", "ctrl+m", "ctrl+j", "ctrl+h",
    "ctrl+1", "ctrl+9", "ctrl+0", "ctrl+semicolon",
}

fail = []

d = tomllib.load(open(BASE + "default.toml", "rb"))

# context set and per-context id counts
if set(d) != set(NS):
    fail.append("context set mismatch: %s" % (set(d) ^ set(NS)))
total = 0
for ctx, want in NS.items():
    got = len(d.get(ctx, {}))
    total += got
    if got != want:
        fail.append("%s has %d ids, expected %d" % (ctx, got, want))
if total != 103:
    fail.append("total ids %d, expected 103" % total)

# invariant 1: no two ids in one context share a key
for ctx, acts in d.items():
    seen = collections.defaultdict(list)
    for act, chain in acts.items():
        for k in chain:
            seen[k].append(act)
    for k, who in seen.items():
        if len(who) > 1:
            fail.append("invariant 1: %s shares %r across %s" % (ctx, k, who))

# invariant 2: no id may be shadowed in every chain it appears in.
#
# Keys resolve innermost-first, so an id whose key is claimed by a context
# inner to it is unreachable *in that chain*. That is a defect only when no
# assemblable chain is left in which the id wins. This is what removed
# sessions.switch and session_tree.confirm — select_list sits beneath them in
# every chain, so enter never arrived. It is also why the seven layer-2 close
# ids may all take esc over app.cancel, and why completion may take enter over
# editor.submit: those inner contexts are in the chain only sometimes.
for ctx in d:
    appears = [c for c in CHAINS if ctx in c]
    if not appears:
        fail.append("invariant 2: %s appears in no assemblable chain" % ctx)
        continue
    for act, chain in d[ctx].items():
        if not chain:
            continue  # empty chain is deliberate disablement, and is silent
        if any(
            k not in {kk for inner in c[:c.index(ctx)] for kk in
                      (kk2 for ch in d[inner].values() for kk2 in ch)}
            for c in appears
            for k in chain
        ):
            continue
        fail.append("invariant 2: %s.%s is shadowed in every chain it appears in"
                    % (ctx, act))

# invariant 2, floor clause: reachable *somewhere* is not enough for app.
# The floor exists to be live while the user is typing, so an app id must win
# in the base surface chain — with no advisory context present, since an
# advisory context shadowing the floor is the sanctioned case (a first esc
# closes the completion overlay, a second reaches the run in flight).
ek = {k for c in d["editor"].values() for k in c}
for act, chain in d["app"].items():
    if chain and all(k in ek for k in chain):
        fail.append("invariant 2: app.%s never wins in the base surface chain" % act)

# invariant 3: no bare printable in a context that can hold text entry
TEXTY = sorted({ctx for c in CHAINS for ctx in c
                if ctx not in TEXT_ENTRY and TEXT_ENTRY & set(c)})
for ctx in TEXTY:
    for act, chain in d[ctx].items():
        for k in chain:
            if "+" not in k and (len(k) == 1 or k in
                    {"comma","period","slash","backslash","semicolon","quote",
                     "grave","minus","equal","bracket_left","bracket_right","space"}):
                fail.append("invariant 3: %s.%s binds bare printable %r" % (ctx, act, k))

# invariant 4 + the banned list, across all three files
for name in ("default", "emacs", "vim"):
    doc = tomllib.load(open(BASE + name + ".toml", "rb"))
    # A preset is a merge over the defaults, so it may cover a subset — but an
    # id it names must exist. Nothing checked this before, which is how the
    # preset kept binding complete_* ids after they were renamed and split.
    for ctx, acts in doc.items():
        if ctx not in NS:
            fail.append("%s: unknown context %r" % (name, ctx))
            continue
        for act in acts:
            if act not in d[ctx]:
                fail.append("%s: unknown id %s.%s" % (name, ctx, act))
    for ctx, acts in doc.items():
        for act, chain in acts.items():
            for k in chain:
                if k.startswith(BANNED_PREFIX):
                    fail.append("invariant 4: %s %s.%s uses %r" % (name, ctx, act, k))
                if k in BANNED_KEYS:
                    fail.append("banned key: %s %s.%s uses %r" % (name, ctx, act, k))
                if k.startswith("super+"):
                    fail.append("super in defaults: %s %s.%s" % (name, ctx, act))
                if k.startswith("alt+") and len(k) == 5 and k[4].isdigit():
                    fail.append("alt+digit stolen: %s %s.%s uses %r" % (name, ctx, act, k))

# inherited constraints
if d["editor"]["submit"] != ["enter"]:
    fail.append("editor.submit changed")
if d["editor"]["newline"] != ["shift+enter", "alt+enter"]:
    fail.append("editor.newline changed")
for lane in ("deliver_steer", "deliver_follow_up", "deliver_next_turn"):
    if d["editor"][lane] != []:
        fail.append("%s not empty" % lane)
fk = d["session_tree"]["fork"]
if any("enter" in k for k in fk):
    fail.append("session_tree.fork touches the Enter family")
if "+" in fk[0]:
    fail.append("session_tree.fork first key not reachable at modified_enter=none")
for ctx, act in [("session_tree","close"),("search","close"),("sessions","close"),
                 ("picker","close"),("settings","close"),("dialog","dismiss"),
                 ("branch_summary","cancel")]:
    if d[ctx][act][0] != "esc":
        fail.append("%s.%s does not take esc first" % (ctx, act))
if d["app"]["cancel"][0] != "esc":
    fail.append("app.cancel floor missing esc")
if d["single_line_input"]["cancel"] != []:
    fail.append("single_line_input.cancel must be empty")

if fail:
    print("FAIL (%d)" % len(fail))
    for f in fail:
        print("  -", f)
    sys.exit(1)
print("OK - 103 ids, 13 contexts, 4 invariants, inherited constraints, 3 files parse")
