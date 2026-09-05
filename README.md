# Z280 S-100 CPU Card

A 16-bit **Zilog Z280** CPU card for the **IEEE-696 S-100** backplane. All the
glue logic lives in two **Atmel ATF1508AS** CPLDs, and the entire schematic +
PCB are Python-generated (`gen_kicad.py`, `gen_pcb.py`).

## Key characteristics

| | |
|---|---|
| CPU | Zilog Z280, 16-bit, Z-BUS @ **12 MHz** |
| Bus | IEEE-696 S-100, 100-pin edge connector |
| Glue logic | 2× Atmel ATF1508AS (128 macrocells each) |
| RAM | **2 MB** SRAM — 4× IS61C5128AS-25 (512K×8, 25 ns), word-addressed as 1M×16 |
| Boot ROM | **64 KB** EEPROM — 2× AT28C256 (32K×8) |
| Console | RS-232 via MAX232, 2×5 IDC header (J7) |
| Data-bus drive | 74F245 — meets the IEEE-696 24 mA sink spec |

The board is a **bus master** by default: it drives address, status, control and
data onto the backplane. The CPLDs split the work cleanly:

- **Control CPLD** (`U4`, `z280-s100-ctl.pld`) — "the decider". Arbitration, the
  master-bridge state machine, local-memory control, and the pre-qualified
  steering terms (`MST_RD/MST_WR/SLV_RD/SLV_WR`, `XFR16`, `SPLIT`, `SLAVE`).
- **Data CPLD** (`U5`, `z280-s100-ad.pld`) — "everything that moves bits". The
  AD0-15 byte mux to the S-100 DO/DI lanes, the burst address counter, and the
  byte lane.

Address decode is external: a 74F138 (SRAM window) + two 74F521 comparators
(flash window, slave window). The A3–A15 address lines are latched out through
two 74F573s, and the 16-bit data bus runs through two 74F245 transceivers.

## Memory map (24-bit address space)

| Range | Size | Decode | Device |
|---|---|---|---|
| `000000`–`1FFFFF` | 2 MB | 74F138 (`SRAM_WIN`) / 74F521 (`SLAVE_WIN`) | SRAM — board + temporary-master access |
| `F00000`–`F0FFFF` | 64 KB | 74F521, A23:A16 = `F0` | Boot EEPROM |

The boot EEPROM pair is word-addressed (flash A_n = byte A_{n+1}), so the two
parts span 64 KB. They are *not* socket-interchangeable with 27C256s (pin 27 is
`WE#` here, not A14).

## Local-memory DMA (temporary-master access)

Another S-100 master can take the bus and read/write this card's local SRAM
directly — DMA-style, without the Z280:

1. The temporary master (TMA) asserts **HOLD**; the control CPLD forwards the
   request to the Z280 (`Z_BUSREQ`) and waits for `Z_BUSACK`.
2. With `Z_BUSACK` low the board is a **slave**
   (`SLAVE = !Z_BUSACK # SLAVE_ONLY`): the address/status/control 74F245s
   reverse direction, the data 74F245s float (`S100_DODSB`), and the 74F573
   address latches float their outputs.
3. The TMA reaches this card's RAM through the **slave window** — a
   74F521 comparator (`SLAVE_WIN`, hardwired to `000000`–`1FFFFF`) that maps
   the TMA's address space onto the local SRAM.

The **SLAVE_ONLY** strap (J11) forces this state permanently, turning the card
into a plain memory-only card for bring-up and debug.

## Burst mode

The Z280's memory burst mode (consecutive accesses without re-presenting the
address) is handled in the data CPLD:

- a **2-bit burst address counter** (A1/A2) increments during a burst;
- the **byte lane** (A0) is derived from the low-address bit and the 16→8
  **SPLIT** flag, so byte and word cycles share one data path;
- **16-bit transfers** are detected from WORD and the S-100 **SIXTN**
  (16-bit-acknowledge) line: `SPLIT16 = WORD & !SIXTN`.

`SIXTN` is open-collector (wired-OR) and pulled up via R4, like the ready lines.

## Clock options

Two 24 MHz time-base footprints are laid out; populate exactly **one**:

- **Y1** — parallel-resonant crystal (HC49) across `XTALI`/`XTALO`, or
- **Y2** — a DIP-can oscillator (DIP-8 or DIP-14) driving `XTALI`.

The Z280 auto-detects the source: a crystal enables the on-chip oscillator, while
an external clock into `XTALI` bypasses it (leave `XTALO` open). There is no
strap for this. Either way the CPU clock is half the XTAL1 frequency, so
**24 MHz → 12 MHz processor clock**.

## Configuration jumpers

### J10 — BTI register straps (3×8 header)

The Z280 samples AD0-7 on the rising edge of reset to load its **Bus Timing &
Initialization (BTI)** register — the wait-state field, clock divider,
bootstrap and multiprocessor bits. J10 is a 3×8 header, one row per bit: the
centre pin selects +5V (logic 1) or GND (logic 0); a 74HCT244 (U21) drives the
value onto AD0-7 for the whole reset window.

**Default = `0b10001110`** (AD7…AD0): direct clock, no bootstrap, no
multiprocessor, **3 wait states**, bus clock = CPU clock.

### J11 — SLAVE_ONLY

2-pin header. **Open (default)** = normal bus master. **Jumper to +5V** =
permanent slave (memory-only card). R3 (1 kΩ) holds the line low when open.

### SLAVE_WIN — temporary-master window

A 74F521 comparator hardwired to `000000`–`1FFFFF` (the same 2 MB window as
SRAM) selects where a temporary master sees this card's SRAM. Not user-
configurable on this rev.

### FLASH_WE — boot-ROM write protection

The 28C256 `WE#` line is normally driven by the control CPLD (in-system EEPROM
programming). Strap it to +5V to hard-write-protect the boot ROM.

## Repository layout

| Path | Purpose |
|---|---|
| `gen_kicad.py` | Generates the schematic (`.kicad_sch`, `.kicad_sym`, `NOTES.md`) |
| `gen_pcb.py` | Generates the board (`.kicad_pcb`) — components, nets, power planes |
| `sync_pcb.py` | Reads hand-tweaked PCB placement back into `gen_pcb.py` |
| `z280-s100-ctl.pld` | Control CPLD (U4) logic — arbitration, FSM, memory control |
| `z280-s100-ad.pld` | Data CPLD (U5) logic — byte mux, burst counter, byte lane |
| `z280-s100-*.jed` | Compiled CPLD fuse maps (fit with WinCUPL + ProChip, flashed over JTAG) |

CPLDs are flashed over the JTAG header (TDI/TMS/TCK/TDO on pins 14/23/62/71).

## License

[CERN Open Hardware Licence Version 2 - Permissive](LICENSE) (CERN-OHL-P-2.0).
Fork, modify and build it freely — just don't claim you designed it: keep the
attribution.

