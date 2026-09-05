# Known bugs

## S-100 bus RESET does not reset the board

The DS1813 (U13) power-on reset drives `Z_RESET` directly, but the S-100 bus
`RESET` line is not OR'd into it. As a result, an S-100 bus RESET (another bus
master, or a front-panel reset) will not reset the Z280 or the CPLDs — the card
only resets on power-on.

**Fix (board rev 2):** OR `S100_RESET` into `Z_RESET` before it reaches the
CPLD and the Z280 — a diode-OR of the DS1813 reset and `S100_RESET`, or route
`S100_RESET` into the control CPLD and OR it in logic.

## Future improvements

- **Configurable slave window** — `SLAVE_WIN` (U24 74F521) is hardwired to
  `000000`–`1FFFFF`, the same 2 MB window as `SRAM_WIN`. Strapping the
  high-order address lines (A16–A23) with jumpers or a DIP switch would let a
  temporary master see the local SRAM at a movable 2 MB window, avoiding
  address conflicts with other cards on the bus.
