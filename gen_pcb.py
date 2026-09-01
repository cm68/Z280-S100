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

def pad_th(ref, num, x, y, size=1.6, drill=0.8, shape="circle"):
    return ('    (pad "%s" thru_hole %s\n'
            '      (at %.4f %.4f)\n'
            '      (size %.2f %.2f)\n'
            '      (drill %.2f)\n'
            '      (layers "*.Cu" "*.Mask")\n'
            '      (remove_unused_layers no)\n'
            '      %s\n'
            '      (uuid "%s")\n'
            '    )'
            % (num, shape, x, y, size, size, drill, netref(ref, num),
               str(uuid.uuid4())))


def pad_smd(ref, num, x, y, w, h, layers):
    return ('    (pad "%s" smd rect\n'
            '      (at %.4f %.4f)\n'
            '      (size %.2f %.2f)\n'
            '      (layers %s)\n'
            '      %s\n'
            '      (uuid "%s")\n'
            '    )'
            % (num, x, y, w, h, layers, netref(ref, num),
               str(uuid.uuid4())))


def fp_open(name, ref, value, x, y, rot=0):
    return ('  (footprint "%s" (layer "F.Cu")\n'
            '    (uuid "%s")\n'
            '    (at %.4f %.4f %d)\n'
            '    (property "Reference" "%s" (at 0 0 0) (layer "F.SilkS")\n'
            '      (effects (font (size 1 1))))\n'
            '    (property "Value" "%s" (at 0 0 0) (layer "F.Fab")\n'
            '      (effects (font (size 1 1))))'
            % (name, str(uuid.uuid4()), x, y, rot, ref, value))


def fp_rect_silk(x1, y1, x2, y2):
    """Four silkscreen fp_lines forming a body rectangle (local coords)."""
    pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    return "\n".join(
        '    (fp_line (start %.3f %.3f) (end %.3f %.3f)'
        ' (stroke (width 0.15) (type default)) (layer "F.SilkS"))'
        % (a, b, c, d) for (a, b), (c, d) in zip(pts, pts[1:]))


def dip_fp(ref, value, n, x, y, wide=False, rot=0):
    """Through-hole DIP: 2 rows of n/2, 2.54 mm pitch. Pin 1 top-left (square
    pad + silkscreen notch on the pin-1 side)."""
    row = (15.24 if wide else 7.62) / 2.0
    half = n // 2
    L = [fp_open("DIP-%d" % n, ref, value, x, y, rot)]
    by = (half - 1) / 2.0 * 2.54 + 1.5
    L.append(fp_rect_silk(-(row + 1.27), -by, row + 1.27, by))
    # Notch on the pin-1 side: a 1 mm radius semicircle cut into the top edge.
    L.append('    (fp_arc (start -1.0 %.3f) (mid 0 %.3f) (end 1.0 %.3f)'
             ' (stroke (width 0.15) (type default)) (layer "F.SilkS"))'
             % (by, by - 1.0, by))
    for i in range(half):
        py = (half - 1) / 2.0 * 2.54 - i * 2.54
        shape1 = "rect" if i == 0 else "circle"  # pin 1 is square
        L.append(pad_th(ref, str(i + 1), -row, py, shape=shape1))
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
        # Strip the whole line -- header strings can contain ')' (e.g.
        # "(300 mils)"), which the old up-to-first-paren regex truncated.
        txt = re.sub(r'\n\s*\(%s [^\n]*' % field, "", txt)

    # Board placement (uuid + position) goes right after the layer.
    txt = re.sub(r'\(layer "F\.Cu"\)',
                 '(layer "F.Cu")\n  (uuid "%s")\n  (at %.4f %.4f %d)'
                 % (str(uuid.uuid4()), x, y, rot), txt, count=1)

    # Point the reference/value text at this instance.
    txt = re.sub(r'\(property "Reference" "[^"]*"',
                 '(property "Reference" "%s"' % ref, txt, count=1)
    txt = re.sub(r'\(property "Value" "[^"]*"',
                 '(property "Value" "%s"' % value, txt, count=1)
    txt = re.sub(r'\(fp_text user "\$\{REFERENCE\}"',
                 '(fp_text user "%s"' % ref, txt, count=1)

    # Keep the library pad's (remove_unused_layers no); its uuid is a
    # library-scope id, so strip it and re-add a fresh board uuid with the net.
    txt = re.sub(r'\n\s*\(uuid "[0-9a-f-]+"\)', "", txt)

    def pad_net(m):
        return (m.group(0)[:-1].rstrip() + '\n      ' + netref(ref, m.group(1))
                + '\n      (uuid "%s"))' % str(uuid.uuid4()))

    txt = re.sub(r'\(pad "(\d+)" thru_hole (?:rect|circle|roundrect)(.*?)\n\s*\)',
                 pad_net, txt, flags=re.S)
    return txt


def hdr_fp(ref, value, n, x, y, rot=0, pitch=2.54, size=1.6, drill=0.8):
    """Through-hole inline part (TO-220/TO-92/crystal/header/resistor)."""
    L = [fp_open("HDR-%d" % n, ref, value, x, y, rot)]
    half = (n - 1) * pitch / 2.0
    L.append(fp_rect_silk(-(half + 1.27), -1.9, half + 1.27, 1.9))
    for i in range(n):
        L.append(pad_th(ref, str(i + 1), -half + i * pitch, 0, size=size, drill=drill))
    L.append("  )")
    return "\n".join(L)


def hdr_3x8_fp(ref, value, rows, pitch, x, y, rot=0):
    """3-column x N-row 0.1" through-hole header (3*rows pins).

    One row per config bit: col 0 = +5V (HIGH), col 1 = signal, col 2 = GND
    (LOW). Pin 1 = top-left, numbered row-major (row, col -> row*3 + col + 1),
    matching the JP3x8 schematic symbol so the netlist lands on the right pads.
    """
    L = [fp_open("HDR-3x8", ref, value, x, y, rot)]
    w = 2 * pitch                       # 3 columns -> 2 pitches wide
    h = (rows - 1) * pitch              # rows -> (rows-1) pitches tall
    L.append(fp_rect_silk(-1.9, -1.9, w + 1.9, h + 1.9))
    for r in range(rows):
        for c in range(3):
            L.append(pad_th(ref, str(r * 3 + c + 1), c * pitch, r * pitch))
    L.append("  )")
    return "\n".join(L)


def pad_net_th(num, x, y, net, size=1.6, drill=0.8):
    """Through-hole pad wired to an explicit net (for parts not in the netlist)."""
    code = NETIDX.get(net, 0)
    return ('    (pad "%s" thru_hole circle\n'
            '      (at %.4f %.4f)\n'
            '      (size %.2f %.2f)\n'
            '      (drill %.2f)\n'
            '      (layers "*.Cu" "*.Mask")\n'
            '      (remove_unused_layers no)\n'
            '      (net %d "%s")\n'
            '      (uuid "%s")\n'
            '    )'
            % (num, x, y, size, size, drill, code, net, str(uuid.uuid4())))


def cap_fp(ref, value, net1, net2, x, y, rot=0, pitch=2.54):
    """2-pin through-hole capacitor wired between net1 and net2."""
    half = pitch / 2.0
    L = [fp_open("CAP-2", ref, value, x, y, rot)]
    L.append(fp_rect_silk(-(half + 1.5), -2.5, half + 1.5, 2.5))
    L.append(pad_net_th("1", -half, 0, net1))
    L.append(pad_net_th("2", half, 0, net2))
    L.append("  )")
    return "\n".join(L)


def edge_connector():
    """100-pad S-100 card edge (50 front + 50 back), imported from the Z80 V3
    reference board (s100_Z80 V3.kicad_pcb). End fingers 1/50/51/100 are the
    wide 2.794 mm pads; their centres sit 0.508 mm farther out so the 0.125"
    pitch holds between finger *edges*, not centres. A silkscreen rectangle
    marks the connector body."""
    L = ['  (footprint "S100_MALE" (layer "F.Cu")\n'
         '    (uuid "%s")\n'
         '    (at %.4f %.4f)'
         % (str(uuid.uuid4()), CONN_X, CONN_Y),
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
        L.append(pad_smd("J8", i + 1, x, PAD_Y, w, PAD_H, '"F.Cu" "F.Mask"'))
        L.append(pad_smd("J8", i + 51, x, PAD_Y, w, PAD_H, '"B.Cu" "B.Mask"'))
    L.append("  )")
    return "\n".join(L)


# ============================================================================
# component placement: (ref, value, kind, p1, p2, x, y, rot)
#   kind "libfp": p1 = library footprint id ("Library:Name")
#   kind "dip":  p1 = pin count, p2 = wide (1) / narrow (0)
#   kind "hdr":  p1 = pin count, p2 = pitch (mm)
# ============================================================================

# Reference designators follow the schematic's current annotation (the S-100
# edge connector is J8, serial J7, JTAG J9). If the
# schematic is re-annotated in KiCad these refs must be updated to match.
COMPONENTS = [
    # PLCC through-hole sockets (origin at top-left, body extends +Y)
    ("U1",  "Z280 (PLCC-68)",   "libfp", "Package_LCC:PLCC-68_THT-Socket", 0, 60,  75,  0),
    ("U4",  "ATF1508 control",  "libfp", "Package_LCC:PLCC-84_THT-Socket", 0, 135.89, 78.486, 0),
    ("U5",  "ATF1508 data",     "libfp", "Package_LCC:PLCC-84_THT-Socket", 0, 225, 72,  0),
    # memory: SRAM (DIP-32) + flash (DIP-28), clustered on the left, ~10 mm gaps
    ("U6", "SRAM bank0 even", "libfp", "Package_DIP:DIP-32_W15.24mm", 0, 22.352, 63.5, 90),
    ("U7", "SRAM bank0 odd", "libfp", "Package_DIP:DIP-32_W15.24mm", 0, 22.352, 43.18, 90),
    ("U8", "SRAM bank1 even", "libfp", "Package_DIP:DIP-32_W15.24mm", 0, 70.95, 62.62, 90),
    ("U9", "SRAM bank1 odd", "libfp", "Package_DIP:DIP-32_W15.24mm", 0, 70.95, 42.62, 90),
    ("U10", "28C256 even", "libfp", "Package_DIP:DIP-28_W15.24mm", 0, 118.49, 62.62, 90),
    ("U11", "28C256 odd", "libfp", "Package_DIP:DIP-28_W15.24mm", 0, 118.49, 42.62, 90),
    # bus drivers (one row near the top)
    ("U15", "74HCT245 addr0", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 160.02, 114.554, 0),
    ("U16", "74HCT245 addr1", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 177.292, 114.808, 0),
    ("U17", "74HCT245 addr2", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 85.344, 113.284, 0),
    ("U18", "74HCT245 status", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 194.818, 114.554, 0),
    ("U19", "74HCT245 control", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 101.854, 113.284, 0),
    ("U20", "74HCT245 pHLDA", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 38.1, 113.284, 0),
    # S-100 data bus transceivers (74F245) + address demux latch (74HC573).
    # The 74F245s drive DO0-7 / DI0-7 (the ATF1508 can't meet the IEEE-696
    # 24 mA bus-drive spec); the 74HC573s latch A3-A15 back out of the data
    # CPLD to make room for the DO_DIR/DI_DIR buffer controls.
    ("U25", "74F245 DO", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 182.372, 61.214, 90),
    ("U26", "74F245 DI", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 182.372, 45.974, 90),
    ("U2", "74HC573 latch", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 156.972, 38.57, 0),
    ("U3", "74HC573 latch", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 168.656, 38.608, 0),
    # decode + BTI buffer + config straps (top right)
    ("U22", "74F138 decode", "libfp", "Package_DIP:DIP-16_W7.62mm", 0, 176.276, 90.678, 90),
    ("U23", "74F521 flash win", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 54.864, 113.284, 0),
    ("U24", "74F521 slave win", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 69.85, 113.538, 0),
    ("U21", "74HCT244 BTI", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 21.082, 83.058, 0),
    ("J10", "Config (3x8)",      "hdr3x8", 8, 2.54, 21.336, 76.2, 90),
    # console / power / clock / reset
    ("U14", "MAX232", "libfp", "Package_DIP:DIP-16_W7.62mm", 0, 213.106, 60.706, 90),
    # MAX232 charge-pump + bypass caps (netlist-wired)
    ("C1", "0.1uF", "libfp", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 0, 234.696, 28.83, 0),
    ("C2", "0.1uF", "libfp", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 0, 234.696, 32.83, 0),
    ("C3", "0.1uF", "libfp", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 0, 234.696, 36.83, 0),
    ("C4", "0.1uF", "libfp", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 0, 234.696, 40.83, 0),
    ("C5", "0.1uF", "libfp", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 0, 234.696, 44.83, 0),
    ("J7",  "Serial (2x5)",     "libfp", "Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical", 0, 218.948, 30.226, 0),
    ("U12", "7805",             "hdr",  3,  2.54, 24.384, 141.478, 0),
    ("U13", "DS1813 reset",     "hdr",  3,  1.27, 252, 80,  0),
    ("Y1",  "24 MHz crystal",   "hdr",  2,  4.83, 88.138, 90.17, 0),
    # pull-up resistors
    ("R1",  "1k pRDY",          "hdr",  2,  7.62, 108.966, 84.328, 0),
    ("R2",  "1k XRDY",          "hdr",  2,  7.62, 108.712, 89.662, 0),
    ("R3",  "1k SLAVE_ONLY",    "hdr",  2,  7.62, 252.476, 36.83, 0),
    ("R4",  "1k SIXTN",         "hdr",  2,  7.62, 108.966, 95.25, 0),
    # JTAG header
    ("J9",  "JTAG (1x6)",       "hdr",  6,  2.54, 135.382, 127.762, 0),
]

# Decoupling / charge-pump capacitors (0.1uF), wired to explicit nets because
# they are not yet in the schematic/netlist.
CAPS = [
    # 0.1uF bypass cap on each DIP (below the DIP-20 row / right of SRAM & flash)
    ("C6",  "0.1uF", "+5V",       "GND", 25.4, 112.268),
    ("C7",  "0.1uF", "+5V",       "GND", 58.674, 108.204),
    ("C8",  "0.1uF", "+5V",       "GND", 88.9, 107.442),
    ("C9",  "0.1uF", "+5V",       "GND", 106.172, 107.442),
    ("C10", "0.1uF", "+5V",       "GND", 181.864, 107.442),
    ("C11", "0.1uF", "+5V",       "GND", 198.12, 107.696),
    ("C12", "0.1uF", "+5V",       "GND", 73.406, 107.95),
    ("C13", "0.1uF", "+5V",       "GND",     226, 113),
    ("C14", "0.1uF", "+5V",       "GND", 113.792, 54.864),
    ("C15", "0.1uF", "+5V",       "GND", 113.792, 35.306),
    ("C16", "0.1uF", "+5V",       "GND", 66.294, 54.356),
    ("C17", "0.1uF", "+5V",       "GND", 66.294, 36.83),
    ("C18", "0.1uF", "+5V", "GND", 163.83, 91.186),
    ("C19", "0.1uF", "+5V", "GND", 238.252, 57.404),
    # bypass caps for the four new data/address parts (U2/U3 74HC573, U25/U26 74F245)
    ("C20", "0.1uF", "+5V", "GND", 160.528, 32.004),
    ("C21", "0.1uF", "+5V", "GND", 172.466, 31.75),
    ("C22", "0.1uF", "+5V", "GND",     190, 68),
    ("C23", "0.1uF", "+5V", "GND",     190, 30),
]


def build_comp(comp):
    ref, value, kind, p1, p2, x, y, rot = comp
    if kind == "libfp":
        return library_fp(p1, ref, value, x, y, rot)
    if kind == "dip":
        return dip_fp(ref, value, p1, x, y, bool(p2), rot)
    if kind == "hdr3x8":
        return hdr_3x8_fp(ref, value, p1, p2, x, y, rot)
    # Tight-pitch inline parts (e.g. TO-92 at 1.27 mm) need pads smaller than the
    # default 1.6 mm, otherwise adjacent pins short out.
    if p2 < 2.0:
        return hdr_fp(ref, value, p1, x, y, rot, p2, size=1.0, drill=0.55)
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
    body = ['(kicad_pcb (version 20241229) (generator "gen_pcb")',
            '',
            '  (general (thickness 1.6))',
            '  (paper "A4")',
            '  (layers',
            '    (0 "F.Cu" signal)',
            '    (2 "B.Cu" signal)',
            '    (4 "In1.Cu" signal)',
            '    (6 "In2.Cu" signal)',
            '    (5 "F.SilkS" user)',
            '    (7 "B.SilkS" user)',
            '    (1 "F.Mask" user)',
            '    (3 "B.Mask" user)',
            '    (25 "Edge.Cuts" user)',
            '    (29 "B.CrtYd" user)',
            '    (31 "F.CrtYd" user)',
            '    (33 "B.Fab" user)',
            '    (35 "F.Fab" user)',
            '  )',
            '  (setup',
            '    (stackup',
            '      (layer "F.SilkS" (type "Top Silk Screen"))',
            '      (layer "F.Paste" (type "Top Solder Paste"))',
            '      (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))',
            '      (layer "F.Cu" (type "copper") (thickness 0.035))',
            '      (layer "dielectric 1" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))',
            '      (layer "In1.Cu" (type "copper") (thickness 0.035))',
            '      (layer "dielectric 2" (type "core") (thickness 1.06) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))',
            '      (layer "In2.Cu" (type "copper") (thickness 0.035))',
            '      (layer "dielectric 3" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))',
            '      (layer "B.Cu" (type "copper") (thickness 0.035))',
            '      (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))',
            '      (layer "B.Paste" (type "Bottom Solder Paste"))',
            '      (layer "B.SilkS" (type "Bottom Silk Screen"))',
            '      (copper_finish "None")',
            '      (dielectric_constraints no)',
            '    )',
            '    (pad_to_mask_clearance 0)',
            '  )',
            '  (net 0 "")']
    for name in sorted(NETIDX, key=lambda n: NETIDX[n]):
        body.append('  (net %d "%s")' % (NETIDX[name], name))
    body.append('')
    body.append(edge_connector())
    for comp in COMPONENTS:
        body.append(build_comp(comp))
    for ref, value, net1, net2, x, y in CAPS:
        body.append(cap_fp(ref, value, net1, net2, x, y))
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
    nnet = len(re.findall(r'^  \(net \d+ "', out, re.M)) - 1  # minus (net 0 "")
    print("wrote z280-s100.kicad_pcb: %d footprints, %d pads, %d nets" % (nfp, npad, nnet))
