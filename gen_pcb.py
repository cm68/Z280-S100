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
    ("U1",  "Z280 (PLCC-68)",   "libfp", "Package_LCC:PLCC-68_THT-Socket", 0, 76.2, 81.28, 0),
    ("U4",  "ATF1508 control",  "libfp", "Package_LCC:PLCC-84_THT-Socket", 0, 136.144, 76.708, 0),
    ("U5",  "ATF1508 data",     "libfp", "Package_LCC:PLCC-84_THT-Socket", 0, 219.71, 75.946, 0),
    # memory: SRAM (DIP-32) + flash (DIP-28), clustered on the left, ~10 mm gaps
    ("U6", "SRAM bank0 even", "libfp", "Package_DIP:DIP-32_W15.24mm", 0, 75.7, 27.4692, 0),
    ("U7", "SRAM bank0 odd", "libfp", "Package_DIP:DIP-32_W15.24mm", 0, 99.7, 27.4692, 0),
    ("U8", "SRAM bank1 even", "libfp", "Package_DIP:DIP-32_W15.24mm", 0, 123.7, 27.4692, 0),
    ("U9", "SRAM bank1 odd", "libfp", "Package_DIP:DIP-32_W15.24mm", 0, 147.7, 27.4692, 0),
    ("U10", "28C256 even", "libfp", "Package_DIP:DIP-28_W15.24mm", 0, 171.7, 32.5492, 0),
    ("U11", "28C256 odd", "libfp", "Package_DIP:DIP-28_W15.24mm", 0, 195.7, 32.5492, 0),
    # bus drivers (one row near the top)
    ("U15", "74HCT245 addr0", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 142.386, 116.332, 0),
    ("U16", "74HCT245 addr1", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 155.622, 116.332, 0),
    ("U17", "74HCT245 addr2", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 89.4412, 116.332, 0),
    ("U18", "74HCT245 status", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 195.331, 116.332, 0),
    ("U19", "74HCT245 control", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 129.15, 116.332, 0),
    ("U20", "74HCT245 pHLDA", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 209.936, 115.951, 0),
    # S-100 data bus transceivers (74F245) + address demux latch (74HC573).
    # The 74F245s drive DO0-7 / DI0-7 (the ATF1508 can't meet the IEEE-696
    # 24 mA bus-drive spec); the 74HC573s latch A3-A15 back out of the data
    # CPLD to make room for the DO_DIR/DI_DIR buffer controls.
    ("U25", "74F245 DO", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 168.859, 116.332, 0),
    ("U26", "74F245 DI", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 182.095, 116.332, 0),
    ("U2", "74HC573 latch", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 50.4763, 42.799, 0),
    ("U3", "74HC573 latch", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 62.9223, 42.799, 0),
    # decode + BTI buffer + config straps (top right)
    ("U22", "74F138 decode", "libfp", "Package_DIP:DIP-16_W7.62mm", 0, 102.677, 121.412, 0),
    ("U23", "74F521 flash win", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 76.205, 116.332, 0),
    ("U24", "74F521 slave win", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 115.914, 116.332, 0),
    ("U21", "74HCT244 BTI", "libfp", "Package_DIP:DIP-20_W7.62mm", 0, 37.2683, 42.799, 0),
    ("J10", "Config (3x8)",      "hdr3x8", 8, 2.54, 31.496, 65.405, 180),
    # console / power / clock / reset
    ("U14", "MAX232", "libfp", "Package_DIP:DIP-16_W7.62mm", 0, 221.112, 42.418, 0),
    # MAX232 charge-pump + bypass caps (netlist-wired)
    ("C1", "0.1uF", "libfp", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 0, 234.315, 44.851, -90),
    ("C2", "0.1uF", "libfp", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 0, 234.315, 55.138, -90),
    ("C3", "0.1uF", "libfp", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 0, 216.789, 45.74, -90),
    ("C4", "0.1uF", "libfp", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 0, 216.916, 57.404, 90),
    ("C5", "0.1uF", "libfp", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm", 0, 226.187, 37.973, 180),
    ("J7",  "Serial (2x5)",     "libfp", "Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical", 0, 229.362, 30.48, -90),
    ("U12", "7805",             "hdr",  3,  2.54, 22.73, 139.25, 0),
    ("U27", "LM323K",           "libfp", "Package_TO_SOT_THT:TO-3", 0, 53.616, 133.604, 180),
    ("U13", "DS1813 reset",     "hdr",  3,  1.27, 168.91, 97.663, 0),
    ("Y1",  "24 MHz crystal",   "hdr",  2,  4.83, 48.131, 90.043, 0),
    # pull-up resistors
    ("R1",  "1k pRDY",          "hdr",  2,  7.62, 21.463, 81.026, 0),
    ("R2",  "1k XRDY",          "hdr",  2,  7.62, 21.209, 86.36, 0),
    ("R3",  "1k SLAVE_ONLY",    "hdr",  2,  7.62, 242.57, 51.308, 0),
    ("J11", "SLAVE_ONLY jumper","libfp", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", 0, 250.0, 51.308, 0),
    ("R4",  "1k SIXTN",         "hdr",  2,  7.62, 21.463, 91.948, 0),
    # JTAG header
    ("J9",  "JTAG (1x6)",       "hdr",  6,  2.54, 256.286, 94.996, -90),
]

# Decoupling / charge-pump capacitors (0.1uF), wired to explicit nets because
# they are not yet in the schematic/netlist.
CAPS = [
    # 0.1uF bypass cap on each DIP (below the DIP-20 row / right of SRAM & flash)
    ("C6",  "0.1uF", "+5V",       "GND", 40.894, 36.703),
    ("C7",  "0.1uF", "+5V",       "GND", 53.848, 36.703),
    ("C8",  "0.1uF", "+5V",       "GND", 66.04, 36.703),
    ("C9",  "0.1uF", "+5V",       "GND", 68.1, 30),
    ("C10", "0.1uF", "+5V",       "GND", 95.3, 40),
    ("C11", "0.1uF", "+5V",       "GND", 119.3, 40),
    ("C12", "0.1uF", "+5V",       "GND", 143.3, 40),
    ("C13", "0.1uF", "+5V",       "GND", 179.07, 27.051),
    ("C14", "0.1uF", "+5V",       "GND", 202.819, 27.051),
    ("C15", "0.1uF", "+5V",       "GND", 98.298, 93.726),
    ("C16", "0.1uF", "+5V",       "GND", 112, 92),
    ("C17", "0.1uF", "+5V",       "GND", 162.814, 108.966),
    ("C18", "0.1uF", "+5V", "GND", 192.151, 93.218),
    ("C19", "0.1uF", "+5V", "GND", 55.245, 96.139),
    # bypass caps for the four new data/address parts (U2/U3 74HC573, U25/U26 74F245)
    ("C20", "0.1uF", "+5V", "GND", 68.961, 116.332),
    ("C21", "0.1uF", "+5V", "GND", 106.934, 114.173),
    ("C22", "0.1uF", "+5V", "GND", 176.911, 108.585),
    ("C23", "0.1uF", "+5V", "GND", 191.643, 108.839),
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
                   '    (hatch edge 0.5)\n'
                   '    (connect_pads thru_hole_only (clearance 0.2))\n'
                   '    (min_thickness 0.2)\n'
                   '    (filled_areas_thickness no)\n'
                   '    (fill yes (thermal_gap 0.2) (thermal_bridge_width 0.3))\n'
                   '    (polygon (pts %s))\n'
                   '  )' % (code, net, layer, str(uuid.uuid4()), pts))
    # +8V copper island on In2.Cu (bottom-left, U-shaped), priority 1 so it
    # cuts out of the +5V plane. Covers U12 pin 1 + U27 pin 1 + the +8V via.
    island = "(xy 18.5 131) (xy 55 131) (xy 55 147.5) (xy 51 147.5) (xy 51 138) (xy 24 138) (xy 24 144.5) (xy 21 144.5) (xy 21 140.5) (xy 24 140.5) (xy 24 147.5) (xy 18.5 147.5)"
    out.append('  (zone\n'
               '    (net %d)\n'
               '    (net_name "+8V")\n'
               '    (layer "In2.Cu")\n'
               '    (uuid "%s")\n'
               '    (hatch edge 0.5)\n'
               '    (priority 1)\n'
               '    (connect_pads thru_hole_only (clearance 0.2))\n'
               '    (min_thickness 0.2)\n'
               '    (filled_areas_thickness no)\n'
               '    (fill yes (thermal_gap 0.2) (thermal_bridge_width 0.3))\n'
               '    (polygon (pts %s))\n'
               '  )' % (NETIDX.get("+8V", 0), str(uuid.uuid4()), island))
    return "\n".join(out)


def patch_area():
    """16 x 10 sea of PTH holes (no net) to the right of U20, for prototyping.
    0.1" pitch, 1.6 mm pad / 0.8 mm drill. The power planes get a clearance
    punchout around each hole automatically when the zones are filled."""
    out = ['  (footprint "PATCH" (layer "F.Cu")',
           '    (uuid "%s")' % uuid.uuid4(),
           '    (at 222.0 114.0)',
           '    (attr through_hole)']
    for r in range(10):
        for c in range(16):
            out.append('    (pad "%d" thru_hole circle (at %.4f %.4f) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask") (net 0 "") (uuid "%s"))'
                       % (r * 16 + c + 1, c * 2.54, r * 2.54, uuid.uuid4()))
    out.append('  )')
    return "\n".join(out)

# Exact S-100 connector test-point geometry, cloned from the hand-tuned board
# (slavishly: every via coordinate and every finger->via trace segment).
# via = (net, x, y)  size 1.0 mm / drill 0.508 mm, spans all four copper layers.
# trace = (net, layer, x0, y0, x1, y1, width) -- 0.2032 mm signal, 0.6096 mm power.
TEST_VIAS = [
    ('+8V', 53.6160, 146.5580),
    ('GND', 60.3250, 145.0340),
    ('S100_XRDY', 62.1030, 146.6850),
    ('S100_sXTRQ', 76.2000, 146.6850),
    ('S100_A19', 79.3750, 146.6850),
    ('S100_SIXTN', 82.5500, 146.6850),
    ('S100_A20', 85.7250, 146.6850),
    ('S100_NMI', 88.9000, 146.6850),
    ('S100_A21', 90.2970, 146.6850),
    ('S100_A22', 92.0750, 146.6850),
    ('S100_A23', 96.4780, 146.6850),
    ('S100_A16', 101.6000, 146.6850),
    ('S100_SDSB', 107.9500, 146.6850),
    ('S100_CDSB', 111.1250, 146.6850),
    ('GND', 114.3000, 144.7800),
    ('S100_ADSB', 120.6500, 146.6850),
    ('S100_pRDY', 122.4280, 146.6850),
    ('S100_DODSB', 123.8250, 146.6850),
    ('S100_INT', 125.2220, 146.6850),
    ('S100_HOLD', 128.1430, 146.6850),
    ('S100_pSTVAL', 130.1750, 146.6850),
    ('S100_RESET', 131.4450, 146.6850),
    ('S100_pHLDA', 133.3500, 146.6850),
    ('S100_pSYNC', 134.7470, 146.6850),
    ('S100_pWR', 137.7950, 146.6850),
    ('S100_pDBIN', 141.0970, 146.6850),
    ('S100_A5', 142.8750, 146.6850),
    ('S100_A0', 144.2720, 146.6850),
    ('S100_A4', 146.0500, 146.6850),
    ('S100_A1', 147.4470, 146.6850),
    ('S100_A3', 149.2250, 146.6850),
    ('S100_A2', 150.6220, 146.6850),
    ('S100_A15', 152.4000, 146.6850),
    ('S100_A6', 153.6700, 146.6850),
    ('S100_A12', 155.5750, 146.6850),
    ('S100_A7', 157.0990, 146.6850),
    ('S100_A9', 158.7500, 146.6850),
    ('S100_A8', 160.2740, 146.6850),
    ('S100_DO1', 161.9250, 146.6850),
    ('S100_A13', 163.4490, 146.6850),
    ('S100_DO0', 165.1000, 146.6850),
    ('S100_A14', 166.4970, 146.6850),
    ('S100_A10', 168.2750, 146.6850),
    ('S100_A11', 169.6720, 146.6850),
    ('S100_DO4', 171.4500, 146.6850),
    ('S100_DO2', 172.8470, 146.6850),
    ('S100_DO5', 174.6250, 146.6850),
    ('S100_DO3', 176.0220, 146.6850),
    ('S100_DO6', 177.8000, 146.6850),
    ('S100_DO7', 179.1970, 146.6850),
    ('S100_DI2', 180.9750, 146.6850),
    ('S100_DI4', 182.3720, 146.6850),
    ('S100_DI3', 184.1500, 146.6850),
    ('S100_DI5', 185.5470, 146.6850),
    ('S100_DI7', 187.3250, 146.6850),
    ('S100_DI6', 188.7220, 146.6850),
    ('S100_sM1', 190.5000, 146.6850),
    ('S100_DI1', 191.8970, 146.6850),
    ('S100_DI0', 192.7110, 139.1920),
    ('S100_sOUT', 193.6750, 146.6850),
    ('S100_DI0', 195.1990, 146.6850),
    ('S100_sINP', 196.8500, 146.6850),
    ('S100_sINTA', 198.2470, 146.6850),
    ('S100_sMEMR', 200.0250, 146.6850),
    ('S100_sWO', 201.4220, 146.6850),
    ('S100_sHLTA', 203.2000, 146.6850),
    ('GND', 210.0580, 144.7800),
]

TEST_TRACES = [
    ('+8V', "B.Cu", 53.4670, 146.7070, 53.6160, 146.5580, 0.6096),
    ('+8V', "B.Cu", 53.4670, 152.7810, 53.4670, 146.7070, 0.6096),
    ('+8V', "F.Cu", 53.4890, 146.6850, 53.6160, 146.5580, 0.6096),
    ('+8V', "F.Cu", 53.6160, 146.5580, 53.6160, 152.6320, 0.6096),
    ('+8V', "F.Cu", 53.6160, 152.6320, 53.4670, 152.7810, 0.6096),
    ('S100_XRDY', "F.Cu", 60.3250, 148.4630, 62.1030, 146.6850, 0.2032),
    ('GND', "B.Cu", 60.3250, 152.7810, 60.3250, 145.0340, 0.6096),
    ('S100_XRDY', "F.Cu", 60.3250, 152.7810, 60.3250, 148.4630, 0.2032),
    ('S100_sXTRQ', "B.Cu", 76.2000, 152.7810, 76.2000, 146.6850, 0.2032),
    ('S100_A19', "B.Cu", 79.3750, 152.7810, 79.3750, 146.6850, 0.2032),
    ('S100_SIXTN', "B.Cu", 82.5500, 152.7810, 82.5500, 146.6850, 0.2032),
    ('S100_A20', "B.Cu", 85.7250, 152.7810, 85.7250, 146.6850, 0.2032),
    ('S100_NMI', "F.Cu", 88.9000, 146.6850, 88.9000, 146.8120, 0.2032),
    ('S100_NMI', "F.Cu", 88.9000, 146.8120, 88.7730, 146.6850, 0.2032),
    ('S100_A21', "B.Cu", 88.9000, 148.0820, 90.2970, 146.6850, 0.2032),
    ('S100_A21', "B.Cu", 88.9000, 152.7810, 88.9000, 148.0820, 0.2032),
    ('S100_NMI', "F.Cu", 88.9000, 152.7810, 88.9000, 146.8120, 0.2032),
    ('S100_A22', "B.Cu", 92.0750, 152.7810, 92.0750, 146.6850, 0.2032),
    ('S100_A23', "B.Cu", 95.2500, 147.9130, 95.2500, 152.7810, 0.2032),
    ('S100_A23', "B.Cu", 96.4780, 146.6850, 95.2500, 147.9130, 0.2032),
    ('S100_A18', "F.Cu", 98.4250, 152.7810, 98.4250, 146.5580, 0.2032),
    ('S100_A16', "F.Cu", 101.6000, 152.7810, 101.6000, 146.6850, 0.2032),
    ('S100_A17', "F.Cu", 104.7750, 152.7810, 104.7750, 146.5580, 0.2032),
    ('S100_SDSB', "F.Cu", 107.9500, 152.7810, 107.9500, 146.6850, 0.2032),
    ('S100_CDSB', "F.Cu", 111.1250, 152.7810, 111.1250, 146.6850, 0.2032),
    ('GND', "B.Cu", 114.3000, 152.7810, 114.3000, 144.7800, 0.6096),
    ('GND', "F.Cu", 114.3000, 152.7810, 114.3000, 144.7800, 0.6096),
    ('S100_pRDY', "B.Cu", 120.6500, 148.4630, 122.4280, 146.6850, 0.2032),
    ('S100_pRDY', "B.Cu", 120.6500, 152.7810, 120.6500, 148.4630, 0.2032),
    ('S100_ADSB', "F.Cu", 120.6500, 152.7810, 120.6500, 146.6850, 0.2032),
    ('S100_INT', "B.Cu", 123.8250, 148.0820, 125.2220, 146.6850, 0.2032),
    ('S100_INT', "B.Cu", 123.8250, 152.7810, 123.8250, 148.0820, 0.2032),
    ('S100_DODSB', "F.Cu", 123.8250, 152.7810, 123.8250, 146.6850, 0.2032),
    ('S100_HOLD', "B.Cu", 127.0000, 147.8280, 128.1430, 146.6850, 0.2032),
    ('S100_HOLD', "B.Cu", 127.0000, 152.7810, 127.0000, 147.8280, 0.2032),
    ('S100_RESET', "B.Cu", 130.1750, 147.9550, 131.4450, 146.6850, 0.2032),
    ('S100_RESET', "B.Cu", 130.1750, 152.7810, 130.1750, 147.9550, 0.2032),
    ('S100_pSTVAL', "F.Cu", 130.1750, 152.7810, 130.1750, 146.6850, 0.2032),
    ('S100_pSYNC', "B.Cu", 133.3500, 148.0820, 134.7470, 146.6850, 0.2032),
    ('S100_pSYNC', "B.Cu", 133.3500, 152.7810, 133.3500, 148.0820, 0.2032),
    ('S100_pHLDA', "F.Cu", 133.3500, 152.7810, 133.3500, 146.6850, 0.2032),
    ('S100_pWR', "B.Cu", 136.5250, 147.9550, 137.7950, 146.6850, 0.2032),
    ('S100_pWR', "B.Cu", 136.5250, 152.7810, 136.5250, 147.9550, 0.2032),
    ('S100_pDBIN', "B.Cu", 139.7000, 148.0820, 141.0970, 146.6850, 0.2032),
    ('S100_pDBIN', "B.Cu", 139.7000, 152.7810, 139.7000, 148.0820, 0.2032),
    ('S100_A0', "B.Cu", 142.8750, 148.0820, 144.2720, 146.6850, 0.2032),
    ('S100_A0', "B.Cu", 142.8750, 152.7810, 142.8750, 148.0820, 0.2032),
    ('S100_A5', "F.Cu", 142.8750, 152.7810, 142.8750, 146.6850, 0.2032),
    ('S100_A1', "B.Cu", 146.0500, 148.0820, 147.4470, 146.6850, 0.2032),
    ('S100_A1', "B.Cu", 146.0500, 152.7810, 146.0500, 148.0820, 0.2032),
    ('S100_A4', "F.Cu", 146.0500, 152.7810, 146.0500, 146.6850, 0.2032),
    ('S100_A2', "B.Cu", 149.2250, 148.0820, 150.6220, 146.6850, 0.2032),
    ('S100_A2', "B.Cu", 149.2250, 152.7810, 149.2250, 148.0820, 0.2032),
    ('S100_A3', "F.Cu", 149.2250, 152.7810, 149.2250, 146.6850, 0.2032),
    ('S100_A6', "B.Cu", 152.4000, 147.9550, 153.6700, 146.6850, 0.2032),
    ('S100_A6', "B.Cu", 152.4000, 152.7810, 152.4000, 147.9550, 0.2032),
    ('S100_A15', "F.Cu", 152.4000, 152.7810, 152.4000, 146.6850, 0.2032),
    ('S100_A7', "B.Cu", 153.6210, 125.0270, 150.0060, 121.4120, 0.2032),
    ('S100_A7', "B.Cu", 153.6210, 135.8460, 153.6210, 125.0270, 0.2032),
    ('S100_A7', "B.Cu", 154.4780, 136.7030, 153.6210, 135.8460, 0.2032),
    ('S100_A7', "B.Cu", 154.4780, 147.1120, 154.4780, 136.7030, 0.2032),
    ('S100_A7', "B.Cu", 155.5750, 148.2090, 154.4780, 147.1120, 0.2032),
    ('S100_A7', "B.Cu", 155.5750, 148.2090, 157.0990, 146.6850, 0.2032),
    ('S100_A7', "B.Cu", 155.5750, 152.7810, 155.5750, 148.2090, 0.2032),
    ('S100_A12', "F.Cu", 155.5750, 152.7810, 155.5750, 146.6850, 0.2032),
    ('S100_A8', "B.Cu", 158.7500, 148.2090, 160.2740, 146.6850, 0.2032),
    ('S100_A8', "B.Cu", 158.7500, 152.7810, 158.7500, 148.2090, 0.2032),
    ('S100_A9', "F.Cu", 158.7500, 152.7810, 158.7500, 146.6850, 0.2032),
    ('S100_A13', "B.Cu", 161.9250, 148.2090, 163.4490, 146.6850, 0.2032),
    ('S100_A13', "B.Cu", 161.9250, 152.7810, 161.9250, 148.2090, 0.2032),
    ('S100_DO1', "F.Cu", 161.9250, 152.7810, 161.9250, 146.6850, 0.2032),
    ('S100_A14', "B.Cu", 162.0850, 131.1630, 162.9870, 130.2620, 0.2032),
    ('S100_A14', "B.Cu", 162.0850, 141.5730, 162.0850, 131.1630, 0.2032),
    ('S100_A14', "B.Cu", 162.9870, 130.2620, 163.6130, 130.2620, 0.2032),
    ('S100_A14', "B.Cu", 163.6130, 130.2620, 164.3590, 129.5150, 0.2032),
    ('S100_A14', "B.Cu", 164.2570, 143.7440, 162.0850, 141.5730, 0.2032),
    ('S100_A14', "B.Cu", 164.2570, 147.2390, 164.2570, 143.7440, 0.2032),
    ('S100_A14', "B.Cu", 164.3590, 125.0690, 163.2420, 123.9520, 0.2032),
    ('S100_A14', "B.Cu", 164.3590, 129.5150, 164.3590, 125.0690, 0.2032),
    ('S100_A14', "B.Cu", 165.1000, 148.0820, 166.4970, 146.6850, 0.2032),
    ('S100_A14', "B.Cu", 165.1000, 148.0820, 164.2570, 147.2390, 0.2032),
    ('S100_A14', "B.Cu", 165.1000, 152.7810, 165.1000, 148.0820, 0.2032),
    ('S100_DO0', "F.Cu", 165.1000, 152.7810, 165.1000, 146.6850, 0.2032),
    ('S100_A11', "B.Cu", 168.2750, 148.0820, 169.6720, 146.6850, 0.2032),
    ('S100_A11', "B.Cu", 168.2750, 152.7810, 168.2750, 148.0820, 0.2032),
    ('S100_A10', "F.Cu", 168.2750, 152.7810, 168.2750, 146.6850, 0.2032),
    ('S100_DO2', "B.Cu", 171.4500, 148.0820, 172.8470, 146.6850, 0.2032),
    ('S100_DO2', "B.Cu", 171.4500, 152.7810, 171.4500, 148.0820, 0.2032),
    ('S100_DO4', "F.Cu", 171.4500, 152.7810, 171.4500, 146.6850, 0.2032),
    ('S100_DO3', "B.Cu", 174.6250, 148.0820, 176.0220, 146.6850, 0.2032),
    ('S100_DO3', "B.Cu", 174.6250, 152.7810, 174.6250, 148.0820, 0.2032),
    ('S100_DO5', "F.Cu", 174.6250, 152.7810, 174.6250, 146.6850, 0.2032),
    ('S100_DO7', "B.Cu", 177.8000, 148.0820, 179.1970, 146.6850, 0.2032),
    ('S100_DO7', "B.Cu", 177.8000, 152.7810, 177.8000, 148.0820, 0.2032),
    ('S100_DO6', "F.Cu", 177.8000, 152.7810, 177.8000, 146.6850, 0.2032),
    ('S100_DI2', "F.Cu", 180.9750, 146.6850, 180.9750, 146.8120, 0.2032),
    ('S100_DI2', "F.Cu", 180.9750, 146.8120, 181.1020, 146.6850, 0.2032),
    ('S100_DI4', "B.Cu", 180.9750, 148.0820, 182.3720, 146.6850, 0.2032),
    ('S100_DI4', "B.Cu", 180.9750, 152.7810, 180.9750, 148.0820, 0.2032),
    ('S100_DI2', "F.Cu", 180.9750, 152.7810, 180.9750, 146.8120, 0.2032),
    ('S100_DI5', "B.Cu", 184.1500, 148.0820, 185.5470, 146.6850, 0.2032),
    ('S100_DI5', "B.Cu", 184.1500, 152.7810, 184.1500, 148.0820, 0.2032),
    ('S100_DI3', "F.Cu", 184.1500, 152.7810, 184.1500, 146.6850, 0.2032),
    ('S100_DI6', "B.Cu", 187.3250, 148.0820, 188.7220, 146.6850, 0.2032),
    ('S100_DI6', "B.Cu", 187.3250, 152.7810, 187.3250, 148.0820, 0.2032),
    ('S100_DI7', "F.Cu", 187.3250, 152.7810, 187.3250, 146.6850, 0.2032),
    ('S100_DI1', "B.Cu", 190.5000, 148.0820, 191.8970, 146.6850, 0.2032),
    ('S100_DI1', "B.Cu", 190.5000, 152.7810, 190.5000, 148.0820, 0.2032),
    ('S100_sM1', "F.Cu", 190.5000, 152.7810, 190.5000, 146.6850, 0.2032),
    ('S100_DI0', "B.Cu", 192.7110, 147.2450, 192.7110, 139.1920, 0.2032),
    ('S100_DI0', "B.Cu", 193.6750, 148.2090, 195.1990, 146.6850, 0.2032),
    ('S100_DI0', "B.Cu", 193.6750, 148.2090, 192.7110, 147.2450, 0.2032),
    ('S100_DI0', "B.Cu", 193.6750, 152.7810, 193.6750, 148.2090, 0.2032),
    ('S100_sOUT', "F.Cu", 193.6750, 152.7810, 193.6750, 146.6850, 0.2032),
    ('S100_sINTA', "B.Cu", 196.8500, 148.0820, 198.2470, 146.6850, 0.2032),
    ('S100_sINTA', "B.Cu", 196.8500, 152.7810, 196.8500, 148.0820, 0.2032),
    ('S100_sINP', "F.Cu", 196.8500, 152.7810, 196.8500, 146.6850, 0.2032),
    ('S100_sWO', "B.Cu", 200.0250, 148.0820, 201.4220, 146.6850, 0.2032),
    ('S100_sWO', "B.Cu", 200.0250, 152.7810, 200.0250, 148.0820, 0.2032),
    ('S100_sMEMR', "F.Cu", 200.0250, 152.7810, 200.0250, 146.6850, 0.2032),
    ('S100_sHLTA', "F.Cu", 203.2000, 152.7810, 203.2000, 146.6850, 0.2032),
    ('GND', "B.Cu", 210.0580, 152.7810, 210.0580, 144.7800, 0.6096),
    ('GND', "F.Cu", 210.0580, 152.7810, 210.0580, 144.7800, 0.6096),
]

def test_points():
    """Emit the hand-built S-100 test points: one through-hole via per finger
    (a probe point and routing anchor) plus the exact finger->via traces.
    Coordinates, layers and widths are cloned verbatim from the tuned board."""
    out = []
    for net, x, y in TEST_VIAS:
        out.append('  (via\n'
                   '    (at %.4f %.4f)\n'
                   '    (size 1.0)\n'
                   '    (drill 0.508)\n'
                   '    (layers "F.Cu" "B.Cu")\n'
                   '    (net %d)\n'
                   '    (uuid "%s")\n'
                   '  )' % (x, y, NETIDX[net], str(uuid.uuid4())))
    for net, layer, x0, y0, x1, y1, w in TEST_TRACES:
        out.append('  (segment\n'
                   '    (start %.4f %.4f)\n'
                   '    (end %.4f %.4f)\n'
                   '    (width %.4f)\n'
                   '    (layer "%s")\n'
                   '    (net %d)\n'
                   '    (uuid "%s")\n'
                   '  )' % (x0, y0, x1, y1, w, layer, NETIDX[net], str(uuid.uuid4())))
    return "\n".join(out)


def emit():
    # ROUTE_2L=1 emits a 2-layer board (F.Cu + B.Cu, no inner planes) so the
    # Specctra SES round-trip maps cleanly; planes are re-added afterwards.
    r2 = os.environ.get("ROUTE_2L") == "1"
    layers = ['    (0 "F.Cu" signal)']
    if r2:
        layers.append('    (1 "B.Cu" signal)')
    else:
        layers += ['    (4 "In1.Cu" signal)', '    (6 "In2.Cu" signal)', '    (2 "B.Cu" signal)']
    body = ['(kicad_pcb (version 20241229) (generator "gen_pcb")',
            '',
            '  (general (thickness 1.6))',
            '  (paper "A4")',
            '  (layers',
            ] + layers + [
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
            ] + ([
            '      (layer "dielectric 1" (type "core") (thickness 1.6) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))',
            '      (layer "B.Cu" (type "copper") (thickness 0.035))',
            ] if r2 else [
            '      (layer "dielectric 1" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))',
            '      (layer "In1.Cu" (type "copper") (thickness 0.035))',
            '      (layer "dielectric 2" (type "core") (thickness 1.06) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))',
            '      (layer "In2.Cu" (type "copper") (thickness 0.035))',
            '      (layer "dielectric 3" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))',
            '      (layer "B.Cu" (type "copper") (thickness 0.035))',
            ]) + [
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
    if not r2:
        body.append(power_planes())
    body.append(patch_area())
    body.append(test_points())
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
