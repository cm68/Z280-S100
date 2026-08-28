#!/usr/bin/env python3
"""Generate a KiCad 9 hierarchical schematic for the Z280 -> S-100 CPU card.

Signal-level connectivity follows extra/docs/z280-s100-cpu-card.md. Pin numbers
are correct for the standard parts and the S-100 connector (taken from the
s100z80 reference design in extra/hardware/s100z80); Z280 and ATF1508 pin
numbers are placeholders that must be checked against their datasheets (see the
NOTES.md this script writes).
"""
import os, uuid

OUT = os.path.dirname(os.path.abspath(__file__))
V = "20250114"  # KiCad 9

def uid():
    return uuid.uuid4().hex

E = {"P": "passive", "I": "input", "O": "output", "B": "bidirectional",
     "W": "power_in", "T": "tri_state", "OC": "open_collector"}

# name -> (ref_prefix, value, footprint, [ (num, name, elec), ... ])
PARTS = {}

PARTS["Z280"] = ("U", "Z280 Z-BUS (12 MHz)", "Package_LCC:PLCC-68_THT-Socket",
    [("1","GND","W"), ("2","AD13","B"), ("3","AD14","B"), ("4","AD15","B"),
     ("5","A16","O"), ("6","A17","O"), ("7","A23","O"), ("8","A18","O"),
     ("9","A19","O"), ("10","B/W","O"), ("11","DMASTB0","O"), ("12","R/W","O"),
     ("13","DMASTB1","O"), ("14","ST0","O"), ("15","ST1","O"), ("16","OE","O"),
     ("17","IE","O"), ("18","VCC","W"), ("19","VCC","W"), ("20","CTIO1","B"),
     ("21","ST2","O"), ("22","ST3","O"), ("23","CTIO2","B"), ("24","DS","O"),
     ("25","CTIN2","I"), ("26","INT-C","I"), ("27","AS","O"), ("28","BUSREQ","I"),
     ("29","WAIT","I"), ("30","CTIO0/GREQ","B"), ("31","BUSACK","O"), ("32","CTIN0/GACK","I"),
     ("33","PAUSE","I"), ("34","OPT","I"), ("35","GND","W"), ("36","INT-B/EOP-B","I"),
     ("37","INT-A/EOP-A","I"), ("38","RESET","I"), ("39","NMI","I"), ("40","AD0","B"),
     ("41","CTIN1","I"), ("42","AD1","B"), ("43","AD2","B"), ("44","AD3","B"),
     ("45","A20","O"), ("46","TXD","O"), ("47","CLK","O"), ("48","RXD","I"),
     ("49","XTALO","O"), ("50","XTALI","I"), ("51","GND","W"), ("52","RESERVED","P"),
     ("53","GND","W"), ("54","AD4","B"), ("55","RDY0","I"), ("56","RDY1","I"),
     ("57","AD5","B"), ("58","RDY3","I"), ("59","A21","O"), ("60","AD6","B"),
     ("61","AD7","B"), ("62","AD8","B"), ("63","RDY2","I"), ("64","AD9","B"),
     ("65","AD10","B"), ("66","A22","O"), ("67","AD11","B"), ("68","AD12","B")])

CPLD_A_IO = [
    ("Z_AS","I"),
    ("Z_DS","I"),
    ("Z_RW","I"),
    ("Z_BW","I"),
    ("Z_ST0","I"),
    ("Z_ST1","I"),
    ("Z_ST2","I"),
    ("Z_ST3","I"),
    ("Z_IE","I"),
    ("Z_BUSACK","I"),
    ("Z_CLK_IN","I"),
    ("Z_RESET","I"),
    ("S100_INT","I"),
    ("S100_NMI","I"),
    ("S100_HOLD","I"),
    ("S100_pRDY","I"),
    ("S100_XRDY","I"),
    ("S100_ADSB","I"),
    ("S100_SDSB","I"),
    ("S100_CDSB","I"),
    ("SRAM_WIN","I"),
    ("FLASH_WIN","I"),
    ("SLAVE_WIN","I"),
    ("BANK","I"),
    ("LA0","I"),
    ("Z_WAIT","O"),
    ("Z_INT","O"),
    ("Z_NMI","O"),
    ("Z_BUSREQ","O"),
    ("CPLD_sMEMR","B"),
    ("CPLD_sWO","B"),
    ("CPLD_sINP","B"),
    ("CPLD_sOUT","B"),
    ("CPLD_sINTA","B"),
    ("CPLD_sHLTA","B"),
    ("CPLD_sXTRQ","B"),
    ("CPLD_pSYNC","O"),
    ("CPLD_pSTVAL","O"),
    ("CPLD_pDBIN","O"),
    ("CPLD_pWR","O"),
    ("CPLD_pHLDA","O"),
    ("MEM_CE0","O"),
    ("MEM_CE1","O"),
    ("MEM_OE","O"),
    ("MEM_WE_L","O"),
    ("MEM_WE_H","O"),
    ("FLASH_CE","O"),
    ("FLASH_OE","O"),
    ("FLASH_WE","O"),
    ("CFG_OE","O"),
    ("S100_A_OE","O"),
    ("S100_S_OE","O"),
    ("S100_C_OE","O"),
    ("MST_RD","O"),
    ("MST_WR","O"),
    ("SLV_RD","O"),
    ("SLV_WR","O"),
    ("XFR16","O"),
    ("SPLIT","O"),
    ("SLAVE","O"),
    ("S100_SIXTN","B"),
    ("TCK","I"),
    ("TMS","I"),
    ("TDI","I"),
    ("TDO","O"),
]
# Verified ATF1508 84-pin PLCC power pins (VCCINT/VCCIO/GND), shared by both CPLDs.
# Also the three dedicated inputs we tie INACTIVE (+5V): GCLR (global clear,
# active low) on pin 1, OE2 on pin 2, OE1 on pin 84. They must not float. GCLK1
# (pin 83) is the clock and is handled as Z_CLK_IN in the signal maps.
_ATF1508_POWER = [
    ("3","VCCINT","W"), ("43","VCCINT","W"),
    ("13","VCCIO","W"), ("26","VCCIO","W"), ("38","VCCIO","W"),
    ("53","VCCIO","W"), ("66","VCCIO","W"), ("78","VCCIO","W"),
    ("7","GND","W"), ("19","GND","W"), ("32","GND","W"), ("42","GND","W"),
    ("47","GND","W"), ("59","GND","W"), ("72","GND","W"), ("82","GND","W"),
    ("1","GCLR","I"), ("2","OE2","I"), ("84","OE1","I"),
]

# signal -> physical pin, matching z280-s100-ctl.pld (the decider; verified
# against the ATF1508 PLCC-84 pinout; JTAG TDI/TMS/TCK/TDO at 14/23/62/71).
_A_PIN = {
    "Z_AS": 77, "Z_DS": 79, "Z_RW": 4, "Z_BW": 5, "Z_ST0": 6, "Z_ST1": 8,
    "Z_ST2": 9, "Z_ST3": 10, "Z_IE": 11, "Z_BUSACK": 15, "Z_CLK_IN": 83, "Z_RESET": 16,
    "S100_INT": 17, "S100_NMI": 18, "S100_HOLD": 20, "S100_pRDY": 21, "S100_XRDY": 22, "S100_ADSB": 12,
    "S100_SDSB": 25, "S100_CDSB": 28, "SRAM_WIN": 30, "FLASH_WIN": 31, "SLAVE_WIN": 29, "BANK": 33,
    "LA0": 27, "Z_WAIT": 34, "Z_INT": 35, "Z_NMI": 36, "Z_BUSREQ": 37, "CPLD_sMEMR": 39,
    "CPLD_sWO": 40, "CPLD_sINP": 41, "CPLD_sOUT": 44, "CPLD_sINTA": 45, "CPLD_sHLTA": 46, "CPLD_sXTRQ": 48,
    "CPLD_pSYNC": 49, "CPLD_pSTVAL": 50, "CPLD_pDBIN": 51, "CPLD_pWR": 52, "CPLD_pHLDA": 54, "MEM_CE0": 55,
    "MEM_CE1": 56, "MEM_OE": 57, "MEM_WE_L": 58, "MEM_WE_H": 60, "FLASH_CE": 61, "FLASH_OE": 63,
    "FLASH_WE": 76, "CFG_OE": 75, "S100_A_OE": 64, "S100_S_OE": 65, "S100_C_OE": 67, "MST_RD": 69,
    "MST_WR": 70, "SLV_RD": 80, "SLV_WR": 81, "XFR16": 74, "SPLIT": 73, "SLAVE": 68,
    "S100_SIXTN": 24, "TCK": 62, "TMS": 23, "TDI": 14, "TDO": 71,
}
_cpld_a_pins = [(str(_A_PIN[name]), name, elec) for name, elec in CPLD_A_IO]
_cpld_a_pins += _ATF1508_POWER
PARTS["ATF1508"] = ("U", "ATF1508AS (PLCC-84)", "Package_LCC:PLCC-84_THT-Socket", _cpld_a_pins)

CPLD_B_IO = [
    ("Z_CLK_IN","I"),
    ("Z_AS","I"),
    ("Z_DS","I"),
    ("S100_DODSB","I"),
    ("MST_RD","I"),
    ("MST_WR","I"),
    ("SLV_RD","I"),
    ("SLV_WR","I"),
    ("XFR16","I"),
    ("SPLIT","I"),
    ("SLAVE","I"),
    ("LA0","O"),
    ("S100_DIR","O"),
    ("A0","B"),
    ("A1","O"),
    ("A2","O"),
    ("A3","O"),
    ("A4","O"),
    ("A5","O"),
    ("A6","O"),
    ("A7","O"),
    ("A8","O"),
    ("A9","O"),
    ("A10","O"),
    ("A11","O"),
    ("A12","O"),
    ("A13","O"),
    ("A14","O"),
    ("A15","O"),
    ("AD0","B"),
    ("AD1","B"),
    ("AD2","B"),
    ("AD3","B"),
    ("AD4","B"),
    ("AD5","B"),
    ("AD6","B"),
    ("AD7","B"),
    ("AD8","B"),
    ("AD9","B"),
    ("AD10","B"),
    ("AD11","B"),
    ("AD12","B"),
    ("AD13","B"),
    ("AD14","B"),
    ("AD15","B"),
    ("S100_DO0","B"),
    ("S100_DO1","B"),
    ("S100_DO2","B"),
    ("S100_DO3","B"),
    ("S100_DO4","B"),
    ("S100_DO5","B"),
    ("S100_DO6","B"),
    ("S100_DO7","B"),
    ("S100_DI0","B"),
    ("S100_DI1","B"),
    ("S100_DI2","B"),
    ("S100_DI3","B"),
    ("S100_DI4","B"),
    ("S100_DI5","B"),
    ("S100_DI6","B"),
    ("S100_DI7","B"),
    ("TCK","I"),
    ("TMS","I"),
    ("TDI","I"),
    ("TDO","O"),
]
# signal -> physical pin, matching z280-s100-ad.pld (the AD manager; verified
# against the ATF1508 PLCC-84 pinout; JTAG TDI/TMS/TCK/TDO at 14/23/62/71).
_B_PIN = {
    "Z_CLK_IN": 83, "Z_AS": 4, "Z_DS": 5, "S100_DODSB": 8, "MST_RD": 9, "MST_WR": 10,
    "SLV_RD": 11, "SLV_WR": 12, "XFR16": 15, "SPLIT": 16, "SLAVE": 17, "LA0": 18,
    "S100_DIR": 6, "A0": 20, "A1": 21, "A2": 22, "A3": 24, "A4": 25,
    "A5": 27, "A6": 28, "A7": 29, "A8": 30, "A9": 31, "A10": 33,
    "A11": 34, "A12": 35, "A13": 36, "A14": 37, "A15": 39, "AD0": 40,
    "AD1": 41, "AD2": 44, "AD3": 45, "AD4": 46, "AD5": 48, "AD6": 49,
    "AD7": 50, "AD8": 51, "AD9": 52, "AD10": 54, "AD11": 55, "AD12": 56,
    "AD13": 57, "AD14": 58, "AD15": 60, "S100_DO0": 61, "S100_DO1": 63, "S100_DO2": 64,
    "S100_DO3": 65, "S100_DO4": 67, "S100_DO5": 68, "S100_DO6": 69, "S100_DO7": 70, "S100_DI0": 73,
    "S100_DI1": 74, "S100_DI2": 75, "S100_DI3": 76, "S100_DI4": 77, "S100_DI5": 79, "S100_DI6": 80,
    "S100_DI7": 81, "TCK": 62, "TMS": 23, "TDI": 14, "TDO": 71,
}
_cpld_b_pins = [(str(_B_PIN[name]), name, elec) for name, elec in CPLD_B_IO]
_cpld_b_pins += _ATF1508_POWER
PARTS["ATF1508B"] = ("U", "ATF1508AS (PLCC-84)", "Package_LCC:PLCC-84_THT-Socket", _cpld_b_pins)

PARTS["IS61C5128AS"] = ("U", "IS61C5128AS-25 (512Kx8)", "Package_DIP:DIP-32",
    [("1","A14","I"),("2","A12","I"),("3","A7","I"),("4","A6","I"),
     ("5","A5","I"),("6","A4","I"),("7","A3","I"),("8","A2","I"),
     ("9","A1","I"),("10","A0","I"),("11","DQ0","B"),("12","DQ1","B"),
     ("13","DQ2","B"),("14","GND","W"),("15","DQ3","B"),("16","DQ4","B"),
     ("17","DQ5","B"),("18","DQ6","B"),("19","DQ7","B"),("20","CE","I"),
     ("21","A10","I"),("22","OE","I"),("23","A11","I"),("24","A9","I"),
     ("25","A8","I"),("26","A13","I"),("27","WE","I"),("28","VCC","W"),
     ("29","A18","I"),("30","A17","I"),("31","A16","I"),("32","A15","I")])

# AT28C256 (256 Kbit, 32Kx8 EEPROM) in a 28-pin DIP socket, JEDEC pinout.
# A boot ROM only lives at boot time, so it need not be fast, wide or big --
# but the Z-BUS has no dynamic bus sizing, so it still takes TWO byte-wide
# parts to answer a 16-bit instruction fetch in one cycle.
#
# Fixed 32Kx8, so the old density jumpers are gone. Note pin 27 = WE# here,
# where a 27C256 EPROM has A14 -- the two are NOT socket-interchangeable.
# A 28C128/28C64 can be fitted if pin 1 (A14) is strapped low.
PARTS["AT28C256"] = ("U", "AT28C256 (32Kx8)", "Package_DIP:DIP-28_W15.24mm",
    [("1","A14","I"),("2","A12","I"),("3","A7","I"),("4","A6","I"),
     ("5","A5","I"),("6","A4","I"),("7","A3","I"),("8","A2","I"),
     ("9","A1","I"),("10","A0","I"),("11","DQ0","B"),("12","DQ1","B"),
     ("13","DQ2","B"),("14","GND","W"),("15","DQ3","B"),("16","DQ4","B"),
     ("17","DQ5","B"),("18","DQ6","B"),("19","DQ7","B"),("20","CE","I"),
     ("21","A10","I"),("22","OE","I"),("23","A11","I"),("24","A9","I"),
     ("25","A8","I"),("26","A13","I"),("27","WE","I"),("28","VCC","W")])

PARTS["JP"] = ("J", "Jumper (2-pin header)", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    [("1","A","P"),("2","B","P")])

PARTS["74HC573"] = ("U", "74HC573", "Package_DIP:DIP-20",
    [("1","OE","I"),("2","D0","I"),("3","D1","I"),("4","D2","I"),
     ("5","D3","I"),("6","D4","I"),("7","D5","I"),("8","D6","I"),
     ("9","D7","I"),("10","GND","W"),("11","LE","I"),("12","Q0","T"),
     ("13","Q1","T"),("14","Q2","T"),("15","Q3","T"),("16","Q4","T"),
     ("17","Q5","T"),("18","Q6","T"),("19","Q7","T"),("20","+5V","W")])

PARTS["74HCT245"] = ("U", "74HCT245", "Package_DIP:DIP-20",
    [("1","DIR","I"),("2","A0","B"),("3","A1","B"),("4","A2","B"),
     ("5","A3","B"),("6","A4","B"),("7","A5","B"),("8","A6","B"),
     ("9","A7","B"),("10","GND","W"),("11","B0","B"),("12","B1","B"),
     ("13","B2","B"),("14","B3","B"),("15","B4","B"),("16","B5","B"),
     ("17","B6","B"),("18","B7","B"),("19","OE","I"),("20","+5V","W")])

# Octal 3-state buffer: drives the jumper-selected BTI value onto AD0-7 during
# the reset-config window (both /OE driven by the control CPLD's CFG_OE, active
# low) and goes high-Z once the 6-clock hold elapses.
PARTS["74HCT244"] = ("U", "74HCT244", "Package_DIP:DIP-20",
    [("1","OE1","I"),("2","A0","I"),("3","Y7","T"),("4","A1","I"),
     ("5","Y6","T"),("6","A2","I"),("7","Y5","T"),("8","A3","I"),
     ("9","Y4","T"),("10","GND","W"),("11","A4","I"),("12","Y3","T"),
     ("13","A5","I"),("14","Y2","T"),("15","A6","I"),("16","Y1","T"),
     ("17","A7","I"),("18","Y0","T"),("19","OE2","I"),("20","+5V","W")])

# 74F138 3-to-8 decoder: A21/A22/A23 -> Y0 = SRAM_WIN (the 2 MB window 000000-1FFFFF).
PARTS["74F138"] = ("U", "74F138", "Package_DIP:DIP-16",
    [("1","A0","I"),("2","A1","I"),("3","A2","I"),("4","G2A","I"),("5","G2B","I"),("6","G1","I"),
     ("7","Y7","O"),("8","GND","W"),("9","Y6","O"),("10","Y5","O"),("11","Y4","O"),("12","Y3","O"),
     ("13","Y2","O"),("14","Y1","O"),("15","Y0","O"),("16","+5V","W")])

# 74F521 8-bit identity comparator (P=Q, /P=Q output). Used for FLASH_WIN and
# the DIP-strappable SLAVE_WIN; taps the inboard A16-23 net so it sees the TMA's
# address in slave mode too.
PARTS["74F521"] = ("U", "74F521", "Package_DIP:DIP-20",
    [("1","G","I"),("2","P0","I"),("3","Q0","I"),("4","P1","I"),("5","Q1","I"),
     ("6","P2","I"),("7","Q2","I"),("8","P3","I"),("9","Q3","I"),("10","GND","W"),
     ("11","Q4","I"),("12","P4","I"),("13","Q5","I"),("14","P5","I"),("15","Q6","I"),
     ("16","P6","I"),("17","Q7","I"),("18","P7","I"),("19","PEQQ","O"),("20","+5V","W")])


PARTS["MAX232"] = ("U", "MAX232", "Package_DIP:DIP-16",
    [("1","C1+","P"),("2","V+","P"),("3","C1-","P"),("4","C2+","P"),
     ("5","C2-","P"),("6","V-","P"),("7","T2OUT","O"),("8","R2IN","I"),
     ("9","R2OUT","O"),("10","T2IN","I"),("11","T1IN","I"),
     ("12","R1OUT","O"),("13","R1IN","I"),("14","T1OUT","O"),
     ("15","GND","W"),("16","+5V","W")])

PARTS["DS1813"] = ("U", "DS1813", "Package_TO_SOT:TO-92",
    [("1","GND","W"),("2","RST","OC"),("3","VCC","W")])

PARTS["LM7805"] = ("U", "LM7805", "Package_TO_SOT:TO-220-3",
    [("1","IN","I"),("2","GND","W"),("3","OUT","O")])

PARTS["Crystal"] = ("Y", "24 MHz", "Crystal:Crystal_HC49",
    [("1","X1","P"),("2","X2","P")])

PARTS["JTAG"] = ("J", "JTAG header (1x6)", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
    [("1","TCK","B"),("2","TMS","B"),("3","TDI","B"),("4","TDO","B"),
     ("5","GND","W"),("6","VCC","W")])

PARTS["SERIAL"] = ("J", "Serial header (2x5)", "Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical",
    [("1","RS232_TX","P"),("2","RS232_RX","P"),("3","GND","W"),("4","GND","W"),
     ("5","GND","W"),("6","GND","W"),("7","GND","W"),("8","GND","W"),
     ("9","GND","W"),("10","GND","W")])

PARTS["R"] = ("R", "1k", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
    [("1","1","P"),("2","2","P")])

# 3-pin config jumper: centre pin selects +5V (high) or GND (low).
PARTS["JP3"] = ("J", "Jumper (3-pin header)", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    [("1","HIGH","P"),("2","SEL","P"),("3","LOW","P")])

S100 = [("1","+8V","W"),("2","+16V","W"),("3","XRDY","B"),("4","VI0","P"),
    ("5","VI1","P"),("6","VI2","P"),("7","VI3","P"),("8","VI4","P"),
    ("9","VI5","P"),("10","VI6","P"),("11","VI7","P"),("12","NMI","B"),
    ("13","PWRFAIL","P"),("14","DMA3","P"),("15","A18","B"),("16","A16","B"),
    ("17","A17","B"),("18","SDSB","B"),("19","CDSB","B"),("20","GND","W"),
    ("21","NC","P"),("22","ADSB","B"),("23","DODSB","B"),("24","PHI","P"),
    ("25","pSTVAL","B"),("26","pHLDA","B"),("27","NC","P"),("28","NC","P"),
    ("29","A5","B"),("30","A4","B"),("31","A3","B"),("32","A15","B"),
    ("33","A12","B"),("34","A9","B"),("35","DO1","B"),("36","DO0","B"),
    ("37","A10","B"),("38","DO4","B"),("39","DO5","B"),("40","DO6","B"),
    ("41","DI2","B"),("42","DI3","B"),("43","DI7","B"),("44","sM1","B"),
    ("45","sOUT","B"),("46","sINP","B"),("47","sMEMR","B"),("48","sHLTA","B"),
    ("49","CLOCK","P"),("50","GND","W"),
    ("51","+8V","W"),("52","-16V","W"),("53","GND","W"),("54","SLAVE_CLR","P"),
    ("55","DMA0","P"),("56","DMA1","P"),("57","DMA2","P"),("58","sXTRQ","B"),
    ("59","A19","B"),("60","SIXTN","B"),("61","A20","B"),("62","A21","B"),
    ("63","A22","B"),("64","A23","B"),("65","NC","P"),("66","NC","P"),
    ("67","PHANTOM","P"),("68","MWRT","P"),("69","NC","P"),("70","GND","W"),
    ("71","NC","P"),("72","pRDY","B"),("73","INT","B"),("74","HOLD","B"),
    ("75","RESET","B"),("76","pSYNC","B"),("77","pWR","B"),("78","pDBIN","B"),
    ("79","A0","B"),("80","A1","B"),("81","A2","B"),("82","A6","B"),
    ("83","A7","B"),("84","A8","B"),("85","A13","B"),("86","A14","B"),
    ("87","A11","B"),("88","DO2","B"),("89","DO3","B"),("90","DO7","B"),
    ("91","DI4","B"),("92","DI5","B"),("93","DI6","B"),("94","DI1","B"),
    ("95","DI0","B"),("96","sINTA","B"),("97","sWO","B"),("98","ERROR","P"),
    ("99","POC","P"),("100","GND","W")]
PARTS["S100_100"] = ("J", "S-100 edge connector (100-pin)", "Connector_Edge", S100)

# ----------------------------------------------------------------------------
# Symbol body width (mm). Pin names are drawn *inside* the body, so a part whose
# names are long (Z280's CTIO0/GREQ, the CPLDs' MASTER_ACTIVE) runs the left- and
# right-hand names into each other across the middle at the default width. These
# three get 1.5x. Keep every value a multiple of 2.54 so pins stay on the 0.1"
# grid, and note body_width() is used by both emit_symbol() and pin_abs() — they
# must agree or the wires and labels detach from the pins.
BODY_W_DEFAULT = 20.32
BODY_W = {"Z280": 30.48, "ATF1508": 30.48, "ATF1508B": 30.48}

def body_width(name):
    return BODY_W.get(name, BODY_W_DEFAULT)

# Reference/Value offsets from the symbol origin, in symbol space (+Y up). Both
# clear the body top edge (+2.54); anything at or below it lands on the pin
# names. HEADROOM is the schematic-space vertical space a placement must leave
# above it for these two lines of text.
TEXT_REF_DY = 7.62
TEXT_VAL_DY = 5.08
HEADROOM = TEXT_REF_DY + 2.54

def body_bottom(name):
    """Schematic-space distance from a symbol's origin down to its body bottom."""
    pins = PARTS[name][3]
    n = len(pins); half = (n + 1) // 2
    return max(half, n - half) * 2.54

def body_metrics(name):
    pins = PARTS[name][3]
    n = len(pins); half = (n + 1) // 2
    return half, 12.7, (max(half, n - half) + 1) * 2.54

def emit_pin(num, name, elec, x, y, angle=0):
    return ('    (pin %s line (at %.2f %.2f %d) (length 2.54)\n'
            '      (name "%s" (effects (font (size 1.27 1.27))))\n'
            '      (number "%s" (effects (font (size 1.27 1.27))))\n    )'
            % (E[elec], x, y, angle, name, num))

def emit_symbol(name, full_name=None):
    if full_name is None:
        full_name = name
    ref, value, fp, pins = PARTS[name]
    n = len(pins); half = (n + 1) // 2
    body_w = body_width(name); max_side = max(half, n - half)
    L = []
    L.append('  (symbol "%s"' % full_name)
    L.append('    (pin_names (offset 1.016))')
    L.append('    (exclude_from_sim no) (in_bom yes) (on_board yes)')
    # Both fields go above the body (symbol space: +Y is up, body top is +2.54).
    # The body interior is filled edge-to-edge with pin names, so a field placed
    # on or inside the rectangle is unreadable. Reference on top, Value beneath.
    L.append('    (property "Reference" "%s" (at 0 %.2f 0) (effects (font (size 1.27 1.27))))' % (ref, TEXT_REF_DY))
    L.append('    (property "Value" "%s" (at 0 %.2f 0) (effects (font (size 1.27 1.27))))' % (value, TEXT_VAL_DY))
    L.append('    (property "Footprint" "%s" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))' % fp)
    L.append('    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    L.append('    (symbol "%s_0_1"' % name)
    L.append('      (rectangle (start -%.2f -%.2f) (end %.2f %.2f) (stroke (width 0.254) (type default)) (fill (type background)))' % (body_w/2, max_side*2.54, body_w/2, 2.54))
    L.append('    )')
    L.append('    (symbol "%s_1_1"' % name)
    for i, (num, nm, e) in enumerate(pins):
        y = -(i % half) * 2.54
        if i < half:
            L.append(emit_pin(num, nm, e, -body_w/2 - 2.54, y, 0))
        else:
            L.append(emit_pin(num, nm, e, body_w/2 + 2.54, y, 180))
    L.append('    )')
    L.append('  )')
    return '\n'.join(L)

def pin_abs(name, num, sym_x, sym_y):
    ref, value, fp, pins = PARTS[name]
    n = len(pins); half = (n + 1) // 2
    body_w = body_width(name)
    for i, (pn, nm, e) in enumerate(pins):
        if str(pn) == str(num):
            y = -(i % half) * 2.54
            if i < half:
                x = -body_w/2 - 2.54; side = -1
            else:
                x = body_w/2 + 2.54; side = 1
            return (sym_x + x, sym_y - y, side)  # symbol Y is negated in schematic space
    raise KeyError((name, num))

def emit_symbol_lib():
    body = ['(kicad_symbol_lib', '  (version %s)' % V,
            '  (generator "gen_kicad")', '  (generator_version "9.0")']
    for pname in PARTS:
        body.append(emit_symbol(pname))
    body.append(')')
    return '\n'.join(body) + '\n'

def emit_label(net, x, y, kind="global", side=1):
    # Left-side pins get a horizontally-mirrored label: text extends left.
    justify = "right" if side < 0 else "left"
    if kind == "global":
        return ('  (global_label "%s" (shape input) (at %.2f %.2f 0)\n'
                '    (effects (font (size 1.27 1.27)) (justify %s))\n'
                '    (uuid "%s")\n'
                '    (property "Intersheetrefs" "${INTERSHEET_REFS}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n  )'
                % (net, x, y, justify, uid()))
    return ('  (label "%s" (at %.2f %.2f 0)\n'
            '    (effects (font (size 1.27 1.27)) (justify %s))\n'
            '    (uuid "%s")\n  )' % (net, x, y, justify, uid()))

def emit_symbol_instance(name, ref, sym_x, sym_y, nets):
    _ref, value, fp, pins = PARTS[name]
    lines = ['  (symbol (lib_id "z280s100:%s")' % name]
    lines.append('    (at %.2f %.2f 0)' % (sym_x, sym_y))
    # fields_autoplaced no: these positions are deliberate, don't let KiCad
    # re-flow them back onto the body.
    lines.append('    (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced no)')
    lines.append('    (uuid "%s")' % uid())
    lines.append('    (property "Reference" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27))))' % (ref, sym_x, sym_y - TEXT_REF_DY))
    lines.append('    (property "Value" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27))))' % (value, sym_x, sym_y - TEXT_VAL_DY))
    lines.append('    (property "Footprint" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27)) hide))' % (fp, sym_x, sym_y))
    lines.append('    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
    for num, nm, e in pins:
        lines.append('    (pin "%s" (uuid "%s"))' % (num, uid()))
    lines.append('    (instances (project "z280-s100" (path "%s" (reference "%s") (unit 1))))' % (OUT, ref))
    lines.append('  )')
    for num, net in nets.items():
        x, y, side = pin_abs(name, num, sym_x, sym_y)
        ex = x + side * 5.08
        lines.append('  (wire (pts (xy %.2f %.2f) (xy %.2f %.2f)) (stroke (width 0) (type default)) (uuid "%s"))' % (x, y, ex, y, uid()))
        lines.append(emit_label(net, ex, y, side=side))
    return '\n'.join(lines)

def lib_symbols_section():
    body = ['  (lib_symbols']
    for name in PARTS:
        body.append(emit_symbol(name, "z280s100:" + name))
    body.append('  )')
    return '\n'.join(body)

def emit_sheet_file(title, instances, paper="A1"):
    body = ['(kicad_sch', '  (version %s)' % V, '  (generator "gen_kicad")',
            '  (generator_version "9.0")', '  (uuid "%s")' % uid(),
            '  (paper "%s")' % paper,
            '  (title_block (title "%s") (date "2026-08-20"))' % title]
    body.append(lib_symbols_section())
    body.extend(instances)
    body.append(')')
    return '\n'.join(body) + '\n'

# ----------------------------------------------------------------------------
def sram_nets(data_nets, we, ce):
    d = {"1":"A15","2":"A13","3":"A8","4":"A7","5":"A6","6":"A5",
         "7":"A4","8":"A3","9":"A2","10":"A1","11":data_nets[0],
         "12":data_nets[1],"13":data_nets[2],"14":"GND","15":data_nets[3],
         "16":data_nets[4],"17":data_nets[5],"18":data_nets[6],"19":data_nets[7],
         "20":ce,"21":"A11","22":"MEM_OE","23":"A12","24":"A10",
         "25":"A9","26":"A14","27":we,"28":"+5V","29":"A19","30":"A18",
         "31":"A17","32":"A16"}
    return d

def flash_nets(data_nets):
    # AT28C256 (32Kx8), JEDEC 28-pin. Word-addressed: ROM A_n = byte A_{n+1},
    # so ROM A0-A14 = LA1-LA15 and the pair spans a 64 KB byte window.
    # WE# is driven by the control CPLD so the boot EEPROM can be reprogrammed
    # in-system; strap it to +5V instead if you want hard write protection.
    d = {"10":"A1","9":"A2","8":"A3","7":"A4","6":"A5","5":"A6",
         "4":"A7","3":"A8","25":"A9","24":"A10","21":"A11","23":"A12",
         "2":"A13","26":"A14","1":"A15",
         "11":data_nets[0],"12":data_nets[1],"13":data_nets[2],"15":data_nets[3],
         "16":data_nets[4],"17":data_nets[5],"18":data_nets[6],"19":data_nets[7],
         "20":"FLASH_CE","22":"FLASH_OE","27":"FLASH_WE",
         "14":"GND","28":"+5V"}
    return d

def _cpld_nets(pins, tag):
    nets = {}
    for num, nm, e in pins:
        if nm in ("VCC", "VCCINT", "VCCIO", "GCLR", "OE1", "OE2"):
            nets[num] = "+5V"
        elif nm == "GND":
            nets[num] = "GND"
        elif nm == "Z_CLK_IN":
            nets[num] = "Z_CLK"                # Z280 CLK output feeds the CPLD clock
        elif nm in ("TCK","TMS"):
            nets[num] = "JTAG_" + nm            # shared across both CPLDs
        elif nm == "TDI":
            nets[num] = "JTAG_TDI" if tag == "A" else "JTAG_CHAIN"
        elif nm == "TDO":
            nets[num] = "JTAG_CHAIN" if tag == "A" else "JTAG_TDO"
        else:
            nets[num] = nm
    return nets

def cpld_a_nets():
    return _cpld_nets(_cpld_a_pins, "A")

def cpld_b_nets():
    return _cpld_nets(_cpld_b_pins, "B")

def s100_nets():
    nets = {}
    for num, nm, e in S100:
        if nm in ("+8V","+16V","-16V","GND"):
            nets[num] = nm
        elif nm == "NC":
            continue
        else:
            nets[num] = "S100_" + nm
    return nets

def buf_nets(alist, blist, dirn, oen):
    d = {"1":dirn, "10":"GND", "19":oen, "20":"+5V"}
    for i, (a, b) in enumerate(zip(alist, blist)):
        d[str(2+i)] = a
        d[str(11+i)] = b
    return d

def single_sheet():
    inst = []
    # CPU (address is latched inside the AD CPLD, U5)
    z = {"40":"AD0","42":"AD1","43":"AD2","44":"AD3","54":"AD4","57":"AD5",
         "60":"AD6","61":"AD7","62":"AD8","64":"AD9","65":"AD10","67":"AD11",
         "68":"AD12","2":"AD13","3":"AD14","4":"AD15",
         "5":"A16","6":"A17","8":"A18","9":"A19","45":"A20","59":"A21","66":"A22","7":"A23",
         "27":"Z_AS","24":"Z_DS","12":"Z_RW","10":"Z_BW",
         "14":"Z_ST0","15":"Z_ST1","21":"Z_ST2","22":"Z_ST3",
         "17":"Z_IE","16":"Z_OE","29":"Z_WAIT","28":"Z_BUSREQ","31":"Z_BUSACK",
         "37":"Z_INT","39":"Z_NMI","38":"Z_RESET",
         "50":"XTALI","49":"XTALO","47":"Z_CLK",
         "34":"+5V","46":"Z_TXD","48":"Z_RXD",
         "18":"+5V","19":"+5V",
         "1":"GND","35":"GND","51":"GND","53":"GND"}
    inst.append(emit_symbol_instance("Z280", "U1", 88.90, 25.4, z))
    # CPLD
    inst.append(emit_symbol_instance("ATF1508", "U4", 162.56, 25.4, cpld_a_nets()))
    inst.append(emit_symbol_instance("ATF1508B", "U5", 162.56, 152.4, cpld_b_nets()))
    # Address decode (external, on the inboard A16-23 net so slave mode works):
    # 74F138 A21-23 -> SRAM_WIN; 74F521 (0xF0) -> FLASH_WIN; 74F521 (2MB strap) -> SLAVE_WIN.
    inst.append(emit_symbol_instance("74F138", "U22", 360.0, 60.0,
                 {"1":"A21","2":"A22","3":"A23","4":"GND","5":"GND","6":"+5V",
                  "15":"SRAM_WIN","8":"GND","16":"+5V"}))
    inst.append(emit_symbol_instance("74F521", "U23", 360.0, 100.0,
                 {"1":"GND","2":"GND","4":"GND","6":"GND","8":"GND",
                  "12":"+5V","14":"+5V","16":"+5V","18":"+5V",
                  "3":"A16","5":"A17","7":"A18","9":"A19","11":"A20","13":"A21","15":"A22","17":"A23",
                  "19":"FLASH_WIN","10":"GND","20":"+5V"}))
    inst.append(emit_symbol_instance("74F521", "U24", 360.0, 140.0,
                 {"1":"GND","14":"GND","16":"GND","18":"GND",
                  "2":"A16","3":"A16","4":"A17","5":"A17","6":"A18","7":"A18","8":"A19","9":"A19",
                  "12":"A20","11":"A20","13":"A21","15":"A22","17":"A23",
                  "19":"SLAVE_WIN","10":"GND","20":"+5V"}))
    # Memory: U6/U8 = even/LO on AD8-15, U7/U9 = odd/HI on AD0-7
    inst.append(emit_symbol_instance("IS61C5128AS", "U6", 231.14, 25.4,
                 sram_nets([f"AD{i}" for i in range(8,16)], "MEM_WE_L", "MEM_CE0")))
    inst.append(emit_symbol_instance("IS61C5128AS", "U7", 231.14, 76.2,
                 sram_nets([f"AD{i}" for i in range(8)], "MEM_WE_H", "MEM_CE0")))
    inst.append(emit_symbol_instance("IS61C5128AS", "U8", 231.14, 127.0,
                 sram_nets([f"AD{i}" for i in range(8,16)], "MEM_WE_L", "MEM_CE1")))
    inst.append(emit_symbol_instance("IS61C5128AS", "U9", 231.14, 177.8,
                 sram_nets([f"AD{i}" for i in range(8)], "MEM_WE_H", "MEM_CE1")))
    # Boot EEPROM: 2x AT28C256 = 32K x 16 = 64 KB at F00000-F0FFFF. Two parts
    # because the Z-BUS has no dynamic bus sizing, not because we need the size.
    # The old density jumpers are gone -- a fixed 32Kx8 part has nothing to strap.
    inst.append(emit_symbol_instance("AT28C256", "U10", 294.64, 25.4,
                 flash_nets([f"AD{i}" for i in range(8,16)])))
    inst.append(emit_symbol_instance("AT28C256", "U11", 294.64, 76.2,
                 flash_nets([f"AD{i}" for i in range(8)])))
    # S-100 connector (the byte-steered data path lives inside CPLD B / U24)
    inst.append(emit_symbol_instance("S100_100", "J8", 421.64, 25.4, s100_nets()))
    # Power / clock / reset / console
    inst.append(emit_symbol_instance("LM7805", "U12", 294.64, 139.7,
                 {"1":"+8V","2":"GND","3":"+5V"}))
    inst.append(emit_symbol_instance("Crystal", "Y1", 294.64, 127.0,
                 {"1":"XTALI","2":"XTALO"}))
    inst.append(emit_symbol_instance("DS1813", "U13", 294.64, 165.1,
                 {"1":"GND","2":"Z_RESET","3":"+5V"}))
    inst.append(emit_symbol_instance("MAX232", "U14", 358.14, 177.8,
                 {"1":"MAX_C1P","2":"MAX_VP","3":"MAX_C1M","4":"MAX_C2P",
                  "5":"MAX_C2M","6":"MAX_VM","7":"NC","8":"NC","9":"NC",
                  "10":"NC","11":"Z_TXD","12":"Z_RXD","13":"MAX_RS232_RX",
                  "14":"MAX_RS232_TX","15":"GND","16":"+5V"}))
    # Serial console header: RS-232 TX/RX + grounds, 2x5 IDC for a DB9 pigtail
    inst.append(emit_symbol_instance("SERIAL", "J7", 358.14, 215.9,
                 {"1":"MAX_RS232_TX","2":"MAX_RS232_RX","3":"GND","4":"GND",
                  "5":"GND","6":"GND","7":"GND","8":"GND","9":"GND","10":"GND"}))
    # S-100 drive buffers (74HCT245): address + status + control
    inst.append(emit_symbol_instance("74HCT245", "U15", 502.92, 25.4,
                 buf_nets(["A0"] + [f"LA{i}" for i in range(1,8)], [f"S100_A{i}" for i in range(8)], "S100_DIR", "S100_A_OE")))
    inst.append(emit_symbol_instance("74HCT245", "U16", 502.92, 63.5,
                 buf_nets([f"LA{i}" for i in range(8,16)], [f"S100_A{i}" for i in range(8,16)], "S100_DIR", "S100_A_OE")))
    inst.append(emit_symbol_instance("74HCT245", "U17", 502.92, 101.6,
                 buf_nets([f"A{i}" for i in range(16,24)], [f"S100_A{i}" for i in range(16,24)], "S100_DIR", "S100_A_OE")))
    inst.append(emit_symbol_instance("74HCT245", "U18", 502.92, 139.7,
                 buf_nets(["CPLD_sMEMR","CPLD_sWO","CPLD_sINP","CPLD_sOUT","CPLD_sINTA","CPLD_sHLTA","CPLD_sXTRQ"],
                          ["S100_sMEMR","S100_sWO","S100_sINP","S100_sOUT","S100_sINTA","S100_sHLTA","S100_sXTRQ"],
                          "S100_DIR", "S100_S_OE")))
    inst.append(emit_symbol_instance("74HCT245", "U19", 502.92, 177.8,
                 buf_nets(["CPLD_pSYNC","CPLD_pSTVAL","CPLD_pDBIN","CPLD_pWR"],
                          ["S100_pSYNC","S100_pSTVAL","S100_pDBIN","S100_pWR"],
                          "S100_DIR", "S100_C_OE")))
    # pHLDA is the permanent master's *exclusive* output, asserted while a TMA
    # holds the bus -- opposite direction from pSYNC/pDBIN/pWR -- so it gets its
    # own always-on driver (74HCT245 strapped A->B). Unused A inputs tied low.
    inst.append(emit_symbol_instance("74HCT245", "U20", 502.92, 215.9,
                 {"1":"+5V","10":"GND","19":"GND","20":"+5V",
                  "2":"CPLD_pHLDA","11":"S100_pHLDA",
                  "3":"GND","4":"GND","5":"GND","6":"GND","7":"GND","8":"GND","9":"GND"}))
    # Local pull-ups for the open-drain ready lines (the backplane also pulls
    # these up; 1k in parallel just strengthens it and keeps the card sane solo).
    inst.append(emit_symbol_instance("R", "R1", 434.34, 241.3, {"1":"+5V","2":"S100_pRDY"}))
    inst.append(emit_symbol_instance("R", "R2", 434.34, 254.0, {"1":"+5V","2":"S100_XRDY"}))
    # SLAVE_ONLY strap: pull down (default = master); jumper to +5V for permanent slave.
    inst.append(emit_symbol_instance("R", "R3", 434.34, 266.7, {"1":"GND","2":"SLAVE_ONLY"}))
    # SIXTN is open-collector (wired-OR); pull up like the ready lines.
    inst.append(emit_symbol_instance("R", "R4", 434.34, 279.4, {"1":"+5V","2":"S100_SIXTN"}))
    # Bus Timing & Initialization config. At reset the Z280 samples AD0-7 to
    # load the BTI register (low-8M wait states + the clock divider). A 74HCT244
    # tri-state driver presents the jumper-selected value on AD0-7 while Z_RESET
    # is asserted: both /OE are active low, so the part drives during reset and
    # goes high-Z the moment reset deasserts. Jumpers J10-J17 select each bit.
    for i in range(8):
        node = f"BTI_AD{i}"
        y = 190.0 + i * 10.0
        inst.append(emit_symbol_instance("JP3", f"J{10+i}", 560.0, y,
                     {"1":"+5V", "2":node, "3":"GND"}))
    # The Z280 latches AD0-7 on the rising edge of RESET (p.545) and needs WAIT
    # held for 6 clocks past that edge (p.541). The control CPLD holds both WAIT
    # and this 244's /OE through a 6-clock counter, so AD0-7 stays driven for the
    # whole sample window. Jumpers J10-J17 select the value.
    inst.append(emit_symbol_instance("74HCT244", "U21", 620.0, 190.0,
        {"1":"CFG_OE","19":"CFG_OE",
         "2":"BTI_AD0","18":"AD0",
         "4":"BTI_AD1","16":"AD1",
         "6":"BTI_AD2","14":"AD2",
         "8":"BTI_AD3","12":"AD3",
         "11":"BTI_AD4","9":"AD4",
         "13":"BTI_AD5","7":"AD5",
         "15":"BTI_AD6","5":"AD6",
         "17":"BTI_AD7","3":"AD7",
         "10":"GND","20":"+5V"}))
    # JTAG programming header: TCK/TMS parallel, TDI->A->B->TDO chained
    inst.append(emit_symbol_instance("JTAG", "J9", 502.92, 292.1,
                 {"1":"JTAG_TCK","2":"JTAG_TMS","3":"JTAG_TDI","4":"JTAG_TDO","5":"GND","6":"+5V"}))
    return emit_sheet_file("Z280 S-100 CPU card", inst)

def emit_pro():
    return ('(kicad_project (version 1) (generator "gen_kicad") (generator_version "9.0")\n'
            '  (uuid "%s")\n)\n' % uid())

NOTES = """# Schematic notes — verify before PCB

Signal connectivity follows `extra/docs/z280-s100-cpu-card.md`. These items need
verification against datasheets before this schematic is PCB-ready.

## Pin numbers to verify
- **Z280 (U1)**: 68-pin PLCC pinout verified — Z80 Family Data Book Fig. 2b
  (Z-BUS, OPT=1), transcribed from `extra/docs/z280-pins.tif`. Power = 2× VCC
  (18/19) + 4× GND (1/35/51/53); shared pins GREQ=CTIO0 (30), GACK=CTIN0 (32),
  EOP-A=INT-A (37), EOP-B=INT-B (36).
- **ATF1508 (U4/U5)**: pin numbers are now verified against the PLCC-84 pinout
  and match `z280-s100-control.pld` / `z280-s100-data.pld` — JTAG TDI/TMS/TCK/TDO
  at 14/23/62/71 (dedicated), VCCINT 3/43 + VCCIO 13/26/38/53/66/78, GND
  7/19/32/42/47/59/72/82. The four DEDICATED INPUT pins are GCLR = 1 (global
  clear, active low), OE2 = 2, GCLK1 = 83, OE1 = 84 — GCLR/OE1/OE2 are tied to
  +5V (inactive) on both CPLDs; GCLK1 = 83 carries Z_CLK_IN. Regular signals
  must NOT sit on pins 1/2/84. Control fits at 59/64 I/O, data at 62/64 (96% —
  the data CPLD is at its ceiling; the re-partition moves decode off it).
- **AT28C256 flash (U10/U11)**: 28-pin DIP, JEDEC 28C256 layout (A14=1, A12=2,
  A7=3 … A0=10, DQ0=11 … DQ7=19, CE#=20, A10=21, OE#=22, A11=23, A9=24, A8=25,
  A13=26, WE#=27, VCC=28, VSS=14). Word-addressed (flash A_n = byte A_{n+1}),
  so A0–A14 = LA1–LA15 and the pair spans 64 KB. Pin 27 is WE# here — where a
  27C256 has A14 — so the two are NOT socket-interchangeable. No density
  jumpers; a 28C128/28C64 fits if pin 1 (A14) is strapped low.

## Corrected S-100 pinout
Taken from `extra/hardware/s100z80/s100_Z80 V2-cache.lib` (S100_MALE). Key pins:
sMEMR=47, sWO=97, sINP=46, sOUT=45, sM1=44, sINTA=96, sHLTA=48, sXTRQ=58,
SIXTN=60, pSYNC=76, pDBIN=78, pWR=77, pSTVAL=25, pHLDA=26, pRDY=72, XRDY=3,
HOLD=74, RESET=75, INT=73, NMI=12, ADSB=22, DODSB=23, SDSB=18, CDSB=19,
DO0=36/DO1=35/DO2=88/DO3=89/DO4=38/DO5=39/DO6=40/DO7=90,
DI0=95/DI1=94/DI2=41/DI3=42/DI4=91/DI5=92/DI6=93/DI7=43.

## Serial console (J7, 2×5 IDC)
- J7 pin 1 = RS-232 TX (from MAX232 T1OUT), pin 2 = RS-232 RX (to MAX232 R1IN),
  pins 3–10 = GND.  Cable pin 1 → DB9-3, pin 2 → DB9-2, any GND → DB9-5.
- MAX232 (U14) still needs its five charge-pump caps (C1+/C1-/C2+/C2- + V+/V-
  bypass, ≈ 0.1 µF each) — not yet placed.

## Bus timing straps (J10–J17 + U21)
- Eight 3-pin jumpers set the value the Z280 samples on AD0-7 at reset to load
  its Bus Timing & Initialization register (low-8M wait states + clock divider).
  Each jumper: centre (pin 2) → a 74HCT244 input, pin 1 = +5V, pin 3 = GND.
  Shunt centre→+5V = 1, centre→GND = 0.
- The 74HCT244 (U21) tri-state driver presents that value on AD0-7 during the
  reset-config window: both /OE (pins 1, 19) tie to CFG_OE from the control
  CPLD. The CPLD asserts WAIT >=4 clocks before reset rises and holds it 15
  clocks after (datasheet p.541/545; 6 is the floor, the extra is free since the
  CPU sits on WAIT), and CFG_OE tracks that same dwell, so AD0-7 stays driven
  through the rising-edge sample and its hold time.
- Default strap = 0b10001110 (AD7..AD0; AD0 = BTI bit 0): direct clock on
  XTAL1, no bootstrap, no multiprocessor, 3 wait states, bus clock = CPU clock.
  J17/J13/J12/J11 = high (+5V), J16/J15/J14/J10 = low (GND). Every bit stays
  jumperable, so the wait field and clock divider can be changed in place.
- Reset must be held low >=512 XTAL1 clocks (~21 us at 24 MHz); the DS1813's
  ~100 ms power-on reset easily satisfies this.

## Wiring gaps (currently labeled but not fully connected)
- Interrupts: S100_INT / S100_NMI route through the CPLD to Z_INT / Z_NMI.
- Reset OR: DS1813 reset and S100_RESET must be OR'd before Z_RESET (diode-OR or
  CPLD input).
- LATCH_LE = ~AS (the CPLD inverts Z_AS to drive the 74HC573 latch enable).
- S-100 address drivers (A0-23, DO, status) need tri-state buffers (e.g. 74HCT244)
  gated by S100_A_OE / ADSB / DODSB / SDSB / CDSB — not yet placed.
- Power flags / ERC cleanup and decoupling caps not yet placed.
"""

def main():
    os.makedirs(OUT, exist_ok=True)
    files = {
        "z280-s100.kicad_sym": emit_symbol_lib(),
        "z280-s100.kicad_pro": emit_pro(),
        "z280-s100.kicad_sch": single_sheet(),
        "sym-lib-table": ('(sym_lib_table\n'
                          '  (version 7)\n'
                          '  (lib (name "z280s100")(type "KiCad")'
                          '(uri "${KIPRJMOD}/z280-s100.kicad_sym")'
                          '(options "")(descr "Z280 S-100 CPU card"))\n'
                          ')\n'),
        "NOTES.md": NOTES,
    }
    for fn, content in files.items():
        path = os.path.join(OUT, fn)
        # Once KiCad has opened the project it rewrites the .kicad_pro as JSON
        # holding net classes and board settings; our stub would throw those
        # away. Seed it only when it is missing.
        if fn == "z280-s100.kicad_pro" and os.path.exists(path):
            print("kept", fn, "(KiCad-managed)")
            continue
        with open(path, "w") as f:
            f.write(content)
        print("wrote", fn, len(content), "bytes")

if __name__ == "__main__":
    main()
