import tomllib, sys, collections, os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "keymaps") + os.sep

NS = {
    "editor": 39, "single_line_input": 9, "select_list": 7, "transcript": 10,
    "search": 4, "sessions": 3, "session_tree": 7, "branch_summary": 1,
    "picker": 2, "dialog": 2, "settings": 5, "app": 14,
}

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

# invariant 2: layer-2 must not reuse a key of the layer-1 beneath it
BENEATH = {
    "transcript": "editor",
    "search": "single_line_input",
    "branch_summary": "single_line_input",
    "settings": "select_list",
    "sessions": "select_list",
    "session_tree": "select_list",
    "picker": "select_list",
}
for outer, inner in BENEATH.items():
    ik = {k for c in d[inner].values() for k in c}
    for act, chain in d[outer].items():
        for k in chain:
            if k in ik:
                fail.append("invariant 2: %s.%s key %r shadowed by %s" % (outer, act, k, inner))

# app (layer 3) sits under editor in every surface chain
ek = {k for c in d["editor"].values() for k in c}
for act, chain in d["app"].items():
    for k in chain:
        if k in ek:
            fail.append("invariant 2: app.%s key %r shadowed by editor" % (act, k))

# invariant 3: no bare printable in a context that can hold text entry
TEXTY = ["transcript", "search", "settings", "branch_summary"]
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
print("OK - 103 ids, 12 contexts, 4 invariants, inherited constraints, 3 files parse")
