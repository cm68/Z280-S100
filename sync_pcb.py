#!/usr/bin/env python3
"""Sync component positions from z280-s100.kicad_pcb back into gen_pcb.py.

Workflow: tweak the layout by hand in KiCad (or by editing the board file), then
run

    python3 sync_pcb.py

It reads every footprint's placement (x, y, rotation) from the board file and
rewrites the matching x/y/rot in gen_pcb.py's COMPONENTS list (and x/y in CAPS),
so the generator stays in sync with the manually-adjusted layout. The next
`python3 gen_pcb.py` reproduces the same placement.

Only COMPONENTS / CAPS entries that exist in the board file are touched. The
S-100 edge connector (J8, emitted separately as edge_connector()) and any other
footprints with no matching entry are left alone.
"""
import re


def read_placements(path="z280-s100.kicad_pcb"):
    """Return {ref: (x, y, rot)} for every footprint in the board file.

    Robust to both this generator's output and KiCad's own re-serialization:
    it walks balanced-paren footprint blocks and picks the footprint-level
    ``(at x y rot)`` (the one that is a direct child of the footprint, not a
    pad's or fp_text's ``(at ...)``), and the Reference property.
    """
    txt = open(path).read()
    out = {}
    i = 0
    n = len(txt)
    while True:
        j = txt.find("(footprint", i)
        if j == -1:
            break
        # find the end of this footprint block (balanced parens)
        depth = 0
        k = j
        while k < n:
            if txt[k] == "(":
                depth += 1
            elif txt[k] == ")":
                depth -= 1
                if depth == 0:
                    k += 1
                    break
            k += 1
        block = txt[j:k]

        ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if not ref:
            i = k
            continue

        # footprint-level placement: (at x y [rot]) that is a direct child
        # (tree depth 1 relative to the footprint). KiCad omits the rotation
        # when it is zero, so it may be 2 or 3 numbers.
        pos = None
        depth = 0
        p = 0
        while p < len(block):
            c = block[p]
            if c == "(":
                if depth == 1 and block.startswith("(at ", p):
                    m = re.match(r"\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)",
                                 block[p:])
                    if m:
                        rot = float(m.group(3)) if m.group(3) else 0.0
                        pos = (float(m.group(1)), float(m.group(2)), rot)
                        break
                depth += 1
            elif c == ")":
                depth -= 1
            p += 1

        if pos is not None:
            out[ref.group(1)] = pos
        i = k
    return out


def _fmt(v):
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return "%g" % v


def _eq(a, b):
    return abs(a - b) < 1e-6


def update_generator(placements, path="gen_pcb.py"):
    """Rewrite COMPONENTS (x, y, rot) and CAPS (x, y) from placements.

    Only lines whose coordinates actually moved are rewritten, so a no-op
    round-trip leaves the file (and its alignment) untouched.
    """
    src = open(path).read().splitlines()
    out = []
    block = None          # None, "COMPONENTS", or "CAPS"
    changed = []

    for line in src:
        stripped = line.strip()
        if stripped == "COMPONENTS = [":
            block = "COMPONENTS"
            out.append(line)
            continue
        if stripped == "CAPS = [":
            block = "CAPS"
            out.append(line)
            continue
        if stripped == "]":
            block = None
            out.append(line)
            continue

        mref = re.match(r'^\s*\(\s*"([^"]+)"', line)
        if not (block and mref):
            out.append(line)
            continue
        ref = mref.group(1)
        if ref not in placements:
            out.append(line)
            continue
        x, y, rot = placements[ref]

        if block == "COMPONENTS":
            mcur = re.search(
                r',\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)\s*,?\s*$',
                line)
            cur = (float(mcur.group(1)), float(mcur.group(2)),
                   float(mcur.group(3)))
            if _eq(cur[0], x) and _eq(cur[1], y) and _eq(cur[2], rot):
                out.append(line)
                continue
            new = re.sub(
                r',\s*-?[\d.]+\s*,\s*-?[\d.]+\s*,\s*-?[\d.]+\s*\)\s*,?\s*$',
                ", %s, %s, %s)," % (_fmt(x), _fmt(y), str(int(round(rot)))),
                line)
        else:  # CAPS: last two numbers are x, y
            mcur = re.search(r',\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)\s*,?\s*$', line)
            cur = (float(mcur.group(1)), float(mcur.group(2)))
            if _eq(cur[0], x) and _eq(cur[1], y):
                out.append(line)
                continue
            new = re.sub(
                r',\s*-?[\d.]+\s*,\s*-?[\d.]+\s*\)\s*,?\s*$',
                ", %s, %s)," % (_fmt(x), _fmt(y)),
                line)

        changed.append((ref, line.strip(), new.strip()))
        out.append(new)

    open(path, "w").write("\n".join(out) + "\n")
    return changed


if __name__ == "__main__":
    placements = read_placements()
    print("read %d footprints from z280-s100.kicad_pcb" % len(placements))
    changed = update_generator(placements)
    if not changed:
        print("gen_pcb.py already in sync — no changes")
    else:
        print("updated %d entries:" % len(changed))
        for ref, old, new in changed:
            print("  %-4s %s -> %s" % (ref, old, new))
