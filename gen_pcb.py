#!/usr/bin/env python3
"""Generate z280-s100.kicad_pcb — S-100 CPU card, components placed + nets wired.

Board edge cuts + edge-connector geometry imported from the Z80 S-100 board
(extra/hardware/s100z80/s100_Z80 V2.brd): the S-100 card outline (bottom bevels
and top connector tab), and

    S100_MALE at (50.8, 157.48), 100 pads, 0.125" pitch, fingers 1.778 x 8.382 mm

Reads z280-s100.net (exported from the schematic) and assigns every pad its net,
so the ratsnest is populated for routing. Four copper layers: F.Cu and B.Cu are
signal; In1.Cu is a solid GND plane and In2.Cu a solid +5V plane (both filled
edge-to-edge over the board outline). Footprints are approximate; replace with
library footprints before routing.
"""
import os
import re
import uuid

INCH = 25.4

# System KiCad footprint library root, for pulling in real library footprints
# (the PLCC through-hole sockets) instead of emitting a fake pad grid.
FPLIB = os.environ.get("KICAD9_FOOTPRINT_DIR", "/usr/share/kicad/footprints")

# ---- S-100 card edge cuts (imported from s100_Z80 V2.brd, layer Edge.Cuts) ----
# 254 x 127 mm card with 45-degree bottom bevels and the top edge-connector tab.
# (x0, y0, x1, y1) in mm; line width 0.381 (0.015").
EDGE_SEGS = [
    (12.7000,  29.2100,  12.7000, 149.8600),  # left edge
    (19.0500,  22.8600,  12.7000,  29.2100),  # bottom-left bevel
    (260.3500, 22.8600,  19.0500,  22.8600),  # bottom edge
    (266.7000, 149.8600, 266.7000,  29.2100), # right edge
    (266.7000, 29.2100, 260.3500,  22.8600),  # bottom-right bevel
    (50.8000, 149.8600,  12.7000, 149.8600),  # top edge (left)
    (50.8000, 157.4800,  50.8000, 149.8600),  # connector tab (left)
    (212.7250, 157.4800,  50.8000, 157.4800), # connector tab (top)
    (212.7250, 149.8600, 212.7250, 157.4800), # connector tab (right)
    (266.7000, 149.8600, 212.7250, 149.8600), # top edge (right)
]

# ---- power-plane fill polygon (the board outline, in loop order) ----
# The two internal copper layers are solid power planes: In1.Cu = GND,
# In2.Cu = +5V, both filled edge-to-edge over this same outline.
PLANE_POLY = [
    (12.7000, 29.2100),
    (12.7000, 149.8600),
    (50.8000, 149.8600),
    (50.8000, 157.4800),
    (212.7250, 157.4800),
    (212.7250, 149.8600),
    (266.7000, 149.8600),
    (266.7000, 29.2100),
    (260.3500, 22.8600),
    (19.0500, 22.8600),
]

# ---- S-100 edge connector (imported from Z80 V3 S100_MALE) ----
CONN_X, CONN_Y = 50.8, 157.48
PITCH = 0.125 * INCH                  # 3.175 mm
PAD_W, PAD_H = 1.778, 8.382           # finger width x length
PAD_Y = -4.699                        # local y of the pad row
TEST_VIA_Y = 147.0                    # single row of test-point vias, between the finger bottoms (~148.6) and the bus drivers

# ---- netlist (ref, pin) -> net name ----
NETMAP = {}
NETIDX = {}


def load_netlist(path):
    global NETMAP, NETIDX
    if not os.path.exists(path):
        print("warning: %s not found — pads left on net 0" % path)
        return
    s = open(path).read()
    nets = re.findall(r'\(net \(code "\d+"\) \(name "([^"]*)"\)(.*?)'
                      r'(?=\n    \(net \(code|\Z)', s, re.S)
    for nm, seg in nets:
        for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "(\d+)"\)', seg):
            NETMAP[(r, int(p))] = nm
    names = sorted(set(NETMAP.values()))
    NETIDX = {n: i + 1 for i, n in enumerate(names)}
    print("loaded %d nets, %d pin assignments" % (len(names), len(NETMAP)))


def netref(ref, num):
    n = NETMAP.get((ref, int(num)))
    if n is None:
        return '(net 0 "")'
    return '(net %d "%s")' % (NETIDX[n], n)


def _u():
    return uuid.uuid4().hex.upper()


# ============================================================================
# pad / footprint emitters
# ============================================================================

def pad_th(ref, num, x, y, size=1.6, drill=0.8):
    return ('    (pad "%s" thru_hole roundrect (at %.4f %.4f) (size %.2f %.2f)'
            ' (drill %.2f) (layers "*.Cu" "*.Mask") %s)'
            % (num, x, y, size, size, drill, netref(ref, num)))


def pad_smd(ref, num, x, y, w, h, layers):
    return ('    (pad "%s" smd rect (at %.4f %.4f) (size %.2f %.2f)'
            ' (layers %s) %s)'
            % (num, x, y, w, h, layers, netref(ref, num)))


def fp_open(name, ref, value, x, y, rot=0):
    return ('  (footprint "%s" (layer "F.Cu") (at %.4f %.4f %d)\n'
            '    (property "Reference" "%s" (at 0 0 0) (layer "F.SilkS")\n'
            '      (effects (font (size 1 1))))\n'
            '    (property "Value" "%s" (at 0 0 0) (layer "F.Fab")\n'
            '      (effects (font (size 1 1))))'
            % (name, x, y, rot, ref, value))


def dip_fp(ref, value, n, x, y, wide=False, rot=0):
    """Through-hole DIP: 2 rows of n/2, 2.54 mm pitch. Pin 1 top-left."""
    row = (15.24 if wide else 7.62) / 2.0
    half = n // 2
    L = [fp_open("DIP-%d" % n, ref, value, x, y, rot)]
    for i in range(half):
        py = (half - 1) / 2.0 * 2.54 - i * 2.54
        L.append(pad_th(ref, str(i + 1), -row, py))
        L.append(pad_th(ref, str(i + 1 + half), row, -py))
    L.append("  )")
    return "\n".join(L)


def library_fp(fpid, ref, value, x, y, rot=0):
    """Load a library footprint (.kicad_mod) and emit it as a board footprint.

    fpid is "Library:Name" (e.g. "Package_LCC:PLCC-68_THT-Socket").  The library
    pads are re-emitted with this board's netlist applied; silkscreen, fab,
    courtyard and the 3D model are carried through unchanged so the part renders
    as the real component rather than a bare pad grid.
    """
    lib, name = fpid.split(":", 1)
    txt = open(os.path.join(FPLIB, lib + ".pretty", name + ".kicad_mod")).read()

    # Library-qualify the footprint name, drop the library-only header fields.
    txt = re.sub(r'^\(footprint "[^"]+"', '(footprint "%s"' % fpid, txt, count=1)
    for field in ("version", "generator", "generator_version", "descr", "tags"):
        txt = re.sub(r'\n\s*\(%s [^\n)]*\)' % field, "", txt)

    # Board placement (tstamp + position) goes right after the layer.
    txt = re.sub(r'\(layer "F\.Cu"\)',
                 '(layer "F.Cu")\n  (tstamp %s)\n  (at %.4f %.4f %d)'
                 % (_u(), x, y, rot), txt, count=1)

    # Point the reference/value text at this instance.
    txt = re.sub(r'\(property "Reference" "[^"]*"',
                 '(property "Reference" "%s"' % ref, txt, count=1)
    txt = re.sub(r'\(property "Value" "[^"]*"',
                 '(property "Value" "%s"' % value, txt, count=1)
    txt = re.sub(r'\(fp_text user "\$\{REFERENCE\}"',
                 '(fp_text user "%s"' % ref, txt, count=1)

    # Drop library-only pad fields, then splice each pad's net in.
    txt = re.sub(r'\n\s*\(remove_unused_layers no\)', "", txt)
    txt = re.sub(r'\n\s*\(uuid "[0-9a-f-]+"\)', "", txt)

    def pad_net(m):
        return m.group(0)[:-1].rstrip() + " " + netref(ref, m.group(1)) + ")"

    txt = re.sub(r'\(pad "(\d+)" thru_hole (?:rect|circle|roundrect)(.*?)\n\s*\)',
                 pad_net, txt, flags=re.S)
    return txt


def hdr_fp(ref, value, n, x, y, rot=0, pitch=2.54):
    """Through-hole inline part (TO-220/TO-92/crystal/header/resistor)."""
    L = [fp_open("HDR-%d" % n, ref, value, x, y, rot)]
    half = (n - 1) * pitch / 2.0
    for i in range(n):
        L.append(pad_th(ref, str(i + 1), -half + i * pitch, 0))
    L.append("  )")
    return "\n".join(L)


def edge_connector():
    """100-pad S-100 card edge (50 front + 50 back), imported from the Z80 V3
    reference board (s100_Z80 V3.kicad_pcb). End fingers 1/50/51/100 are the
    wide 2.794 mm pads; their centres sit 0.508 mm farther out so the 0.125"
    pitch holds between finger *edges*, not centres. A silkscreen rectangle
    marks the connector body."""
    L = ['  (footprint "S100_MALE" (layer "F.Cu") (at %.4f %.4f)'
         % (CONN_X, CONN_Y),
         '    (property "Reference" "J8" (at 0 -11.43 0) (layer "F.SilkS")'
         '      (effects (font (size 1.524 1.524))))',
         '    (property "Value" "S-100 edge" (at 0 -11.43 0) (layer "F.Fab")'
         '      (effects (font (size 1.524 1.524))))']
    # Finger x positions copied from the Z80 V3 S100_MALE: wide end fingers at
    # 2.667 and 159.258, the 48 inner fingers at 3.175 mm pitch from 6.35.
    xs = [2.667] + [6.35 + i * PITCH for i in range(48)] + [159.258]
    # Silkscreen rectangle marking the connector body (local coordinates).
    L.append('    (fp_line (start 161.925 -9.525) (end 161.925 0)'
             ' (stroke (width 0.381) (type default)) (layer "F.SilkS"))')
    L.append('    (fp_line (start 161.925 0) (end 0 0)'
             ' (stroke (width 0.381) (type default)) (layer "F.SilkS"))')
    L.append('    (fp_line (start 0 0) (end 0 -9.525)'
             ' (stroke (width 0.381) (type default)) (layer "F.SilkS"))')
    L.append('    (fp_line (start 0 -9.525) (end 161.925 -9.525)'
             ' (stroke (width 0.381) (type default)) (layer "F.SilkS"))')
    for i, x in enumerate(xs):
        w = 2.794 if i in (0, 49) else PAD_W
        L.append('    (pad "%d" smd rect (at %.4f %.4f) (size %.2f %.2f)'
                 ' (layers "F.Cu" "F.Mask") %s)'
                 % (i + 1, x, PAD_Y, w, PAD_H, netref("J8", i + 1)))
        L.append('    (pad "%d" smd rect (at %.4f %.4f) (size %.2f %.2f)'
                 ' (layers "B.Cu" "B.Mask") %s)'
                 % (i + 51, x, PAD_Y, w, PAD_H, netref("J8", i + 51)))
    L.append("  )")
    return "\n".join(L)


# ============================================================================
# component placement: (ref, value, kind, p1, p2, x, y, rot)
#   kind "libfp": p1 = library footprint id ("Library:Name")
#   kind "dip":  p1 = pin count, p2 = wide (1) / narrow (0)
#   kind "hdr":  p1 = pin count, p2 = pitch (mm)
# ============================================================================

# Reference designators follow the schematic's current annotation (the S-100
# edge connector is J8, flash jumpers J1–J6, serial J7, JTAG J9). If the
# schematic is re-annotated in KiCad these refs must be updated to match.
COMPONENTS = [
    # PLCC through-hole sockets (real library footprints, not a pad grid)
    ("U1",  "Z280 (PLCC-68)",   "libfp", "Package_LCC:PLCC-68_THT-Socket", 0, 60,  85,  0),
    ("U4",  "ATF1508 control",  "libfp", "Package_LCC:PLCC-84_THT-Socket", 0, 140, 85,  0),
    ("U5",  "ATF1508 data",     "libfp", "Package_LCC:PLCC-84_THT-Socket", 0, 225, 85,  0),
    # address latches + bus drivers (DIP-20)
    ("U2",  "74HC573 lo",       "dip",  20, 0,    45,  133, 0),
    ("U3",  "74HC573 hi",       "dip",  20, 0,    65,  133, 0),
    ("U15", "74HCT245 addr0",   "dip",  20, 0,    90,  133, 0),
    ("U16", "74HCT245 addr1",   "dip",  20, 0,    110, 133, 0),
    ("U17", "74HCT245 addr2",   "dip",  20, 0,    130, 133, 0),
    ("U18", "74HCT245 status",  "dip",  20, 0,    150, 133, 0),
    ("U19", "74HCT245 control", "dip",  20, 0,    170, 133, 0),
    ("U20", "74HCT245 pHLDA",   "dip",  20, 0,    190, 133, 0),
    # SRAM + flash (DIP-32, rotated 90, stacked even-over-odd)
    ("U6",  "SRAM bank0 even",  "dip",  32, 1,    60,  52,  90),
    ("U7",  "SRAM bank0 odd",   "dip",  32, 1,    60,  34,  90),
    ("U8",  "SRAM bank1 even",  "dip",  32, 1,    140, 52,  90),
    ("U9",  "SRAM bank1 odd",   "dip",  32, 1,    140, 34,  90),
    ("U10", "27SF020 even",     "dip",  32, 1,    225, 52,  90),
    ("U11", "27SF020 odd",      "dip",  32, 1,    225, 34,  90),
    # console / power / clock / reset
    ("U14", "MAX232",           "dip",  16, 0,    20,  90,  0),
    ("J7",  "Serial (2x5)",     "libfp", "Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical", 0, 20, 70, 0),
    ("U12", "7805",             "hdr",  3,  2.54, 252, 135, 0),
    ("U13", "DS1813 reset",     "hdr",  3,  1.27, 252, 120, 0),
    ("Y1",  "24 MHz crystal",   "hdr",  2,  4.83, 252, 105, 0),
    # pull-up resistors
    ("R1",  "1k pRDY",          "hdr",  2,  7.62, 252, 90,  0),
    ("R2",  "1k XRDY",          "hdr",  2,  7.62, 252, 80,  0),
    ("R3",  "1k SLAVE_ONLY",    "hdr",  2,  7.62, 252, 70,  0),
    ("R4",  "1k SIXTN",         "hdr",  2,  7.62, 252, 60,  0),
    # headers
    ("J9",  "JTAG (1x6)",       "hdr",  6,  2.54, 25,  30,  0),
    ("J1",  "JP VPP",           "hdr",  2,  2.54, 200, 68,  0),
    ("J2",  "JP A15",           "hdr",  2,  2.54, 205, 68,  0),
    ("J3",  "JP A16",           "hdr",  2,  2.54, 210, 68,  0),
    ("J4",  "JP A17/VDD",       "hdr",  2,  2.54, 215, 68,  0),
    ("J5",  "JP PGM",           "hdr",  2,  2.54, 220, 68,  0),
    ("J6",  "JP VDD",           "hdr",  2,  2.54, 225, 68,  0),
]


def build_comp(comp):
    ref, value, kind, p1, p2, x, y, rot = comp
    if kind == "libfp":
        return library_fp(p1, ref, value, x, y, rot)
    if kind == "dip":
        return dip_fp(ref, value, p1, x, y, bool(p2), rot)
    return hdr_fp(ref, value, p1, x, y, rot, p2)


def board_outline():
    L = []
    for x0, y0, x1, y1 in EDGE_SEGS:
        L.append('  (gr_line (start %.4f %.4f) (end %.4f %.4f)'
                 ' (stroke (width 0.381) (type default)) (layer "Edge.Cuts"))'
                 % (x0, y0, x1, y1))
    return "\n".join(L)


def power_planes():
    """Solid copper power planes on the two internal layers: In1.Cu = GND,
    In2.Cu = +5V, both filled edge-to-edge over the full board outline."""
    pts = " ".join("(xy %.4f %.4f)" % (x, y) for x, y in PLANE_POLY)
    out = []
    for layer, net in (("In1.Cu", "GND"), ("In2.Cu", "+5V")):
        code = NETIDX.get(net, 0)
        out.append('  (zone\n'
                   '    (net %d)\n'
                   '    (net_name "%s")\n'
                   '    (layer "%s")\n'
                   '    (uuid "%s")\n'
                   '    (hatch edge 0.508)\n'
                   '    (connect_pads yes (clearance 0.508))\n'
                   '    (min_thickness 0.254)\n'
                   '    (filled_areas_thickness no)\n'
                   '    (fill yes (thermal_gap 0.508) (thermal_bridge_width 0.508))\n'
                   '    (polygon (pts %s))\n'
                   '  )' % (code, net, layer, str(uuid.uuid4()), pts))
    return "\n".join(out)


def test_vias():
    """One through-hole test point per unique S-100 net, in a single row just
    below the edge-connector fingers. The front and back fingers at the same x
    usually carry different signals, so the back finger's via is shifted +1.6 mm
    (half a pitch) to keep them apart. Each via spans all four copper layers and
    carries its finger's net, doubling as a routing anchor and a probe point."""
    xs = [2.667] + [6.35 + i * PITCH for i in range(48)] + [159.258]
    seen = set()
    out = []
    for i, x in enumerate(xs):
        for pin, dx in ((i + 1, 0.0), (i + 51, 1.6)):
            n = NETMAP.get(("J8", pin))
            if n is None or n in seen:
                continue
            seen.add(n)
            out.append('  (via\n'
                       '    (at %.4f %.4f)\n'
                       '    (size 1.27)\n'
                       '    (drill 0.6)\n'
                       '    (layers "F.Cu" "B.Cu")\n'
                       '    (net %d)\n'
                       '    (uuid "%s")\n'
                       '  )' % (CONN_X + x + dx, TEST_VIA_Y, NETIDX[n],
                                str(uuid.uuid4())))
    return "\n".join(out)


def emit():
    body = ['(kicad_pcb (version 20240108) (generator "gen_pcb")',
            '',
            '  (general (thickness 1.6))',
            '  (paper "A4")',
            '  (layers',
            '    (0 "F.Cu" signal)',
            '    (1 "In1.Cu" signal)',
            '    (2 "In2.Cu" signal)',
            '    (31 "B.Cu" signal)',
            '    (36 "F.SilkS" user)',
            '    (37 "B.SilkS" user)',
            '    (38 "F.Mask" user)',
            '    (39 "B.Mask" user)',
            '    (44 "Edge.Cuts" user)',
            '    (46 "B.CrtYd" user)',
            '    (47 "F.CrtYd" user)',
            '    (48 "B.Fab" user)',
            '    (49 "F.Fab" user)',
            '  )',
            '  (setup (pad_to_mask_clearance 0))',
            '  (net 0 "")']
    for name in sorted(NETIDX, key=lambda n: NETIDX[n]):
        body.append('  (net %d "%s")' % (NETIDX[name], name))
    body.append('')
    body.append(edge_connector())
    for comp in COMPONENTS:
        body.append(build_comp(comp))
    body.append(board_outline())
    body.append(power_planes())
    body.append(test_vias())
    body.append(')')
    return "\n".join(body) + "\n"


if __name__ == "__main__":
    load_netlist("z280-s100.net")
    out = emit()
    with open("z280-s100.kicad_pcb", "w") as f:
        f.write(out)
    nfp = len(re.findall(r'^\s*\(footprint', out, re.M))
    npad = len(re.findall(r'^\s*\(pad', out, re.M))
    nnet = len(re.findall(r'^\s*\(net \d+ "', out, re.M)) - 1  # minus (net 0 "")
    print("wrote z280-s100.kicad_pcb: %d footprints, %d pads, %d nets" % (nfp, npad, nnet))
