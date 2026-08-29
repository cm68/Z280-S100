# Schematic notes — verify before PCB

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
  must NOT sit on pins 1/2/84. Control sits at 59/64 I/O; the data CPLD was at
  62/64 until the A3–A15 latch moved back out to two 74HC573s (freeing pins for
  the DO_DIR/DI_DIR buffer controls), so it now sits near 50/64.
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

## Bus timing straps (J10 3x8 header + U21)
- One 3x8 header (24 pins) sets the value the Z280 samples on AD0-7 at reset to
  load its Bus Timing & Initialization register (low-8M wait states + clock
  divider). One row per bit: col 0 = +5V (HIGH), col 1 = signal (BTI_ADn),
  col 2 = GND (LOW). Shunt col1→+5V = 1, col1→GND = 0.
- The 74HCT244 (U21) tri-state driver presents that value on AD0-7 during the
  reset-config window: both /OE (pins 1, 19) tie to CFG_OE from the control
  CPLD. The CPLD asserts WAIT >=4 clocks before reset rises and holds it 15
  clocks after (datasheet p.541/545; 6 is the floor, the extra is free since the
  CPU sits on WAIT), and CFG_OE tracks that same dwell, so AD0-7 stays driven
  through the rising-edge sample and its hold time.
- Default strap = 0b10001110 (AD7..AD0; AD0 = BTI bit 0): direct clock on
  XTAL1, no bootstrap, no multiprocessor, 3 wait states, bus clock = CPU clock.
  AD7/AD3/AD2/AD1 = high (+5V), AD6/AD5/AD4/AD0 = low (GND). Every bit stays
  jumperable, so the wait field and clock divider can be changed in place.
- Reset must be held low >=512 XTAL1 clocks (~21 us at 24 MHz); the DS1813's
  ~100 ms power-on reset easily satisfies this.

## Data bus (74F245 transceivers, U25/U26)
- The S-100 DO0-7 / DI0-7 lanes are NOT driven by the CPLD any more. CPLD B's
  byte mux drives CPLD_DO0-7 / CPLD_DI0-7 into the A-side of two 74F245s whose
  B-side is the backplane. 74F245 (64 mA sink / 15 mA source) meets the
  IEEE-696 data-bus drive spec that the ATF1508 macrocell outputs cannot.
- DIR = DO_DIR / DI_DIR from the data CPLD (1 = drive the bus). /OE is tied low:
  a 245 in receive mode never drives the bus, so only DIR has to be right, and
  the DIRs are gated by S100_DODSB so a temporary master can float our drivers.

## Address latch (74HC573, U2/U3)
- A3-A15 moved out of CPLD B into two 74HC573s to free pins for DO_DIR/DI_DIR.
  LE = LATCH_LE (= ~AS: transparent while AS is low, holds on the rising edge);
  /OE = SLAVE so the latch floats its Q outputs when a TMA drives address inward.
  A0 (byte lane) and A1/A2 (burst counter) stay in the CPLD — they need the
  SPLIT / load-count logic a plain latch can't do.
- U2 latches AD3-AD10 -> A3-A10, U3 latches AD11-AD15 -> A11-A15 (D5-D7 tied
  low, Q5-Q7 unused). The S-100 address 245s now take A0-A15 directly (the old
  LA1-LA15 net names were a stale leftover from the in-CPLD latch).

## Wiring gaps (currently labeled but not fully connected)
- Interrupts: S100_INT / S100_NMI route through the CPLD to Z_INT / Z_NMI.
- Reset OR: DS1813 reset and S100_RESET must be OR'd before Z_RESET (diode-OR or
  CPLD input).
- Power flags / ERC cleanup and decoupling caps not yet placed.
