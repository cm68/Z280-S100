# Z280 S-100 — Master / Slave (running-slave) design

> Design notes for the running-slave variation of the Z280 S-100 card.
>
> The same card can be strapped **permanent S-100 bus master** (the current
> design) or **running slave** — a Z280 that keeps executing from local memory
> while exposing its RAM to the backplane and reaching other boards through the
> Z280's **multimicro** facility. This document records the memory map, the
> three-layer arbitration, the external TMA-arbitration GAL, the strap block,
> the I/O routing and the doorbell, as agreed. Not yet an as-built spec: open
> items are collected in §12.

---

## 1. System topology

- **Up to 8 boards** on one backplane. Each board is a Z280 + 2 MB RAM +
  private boot ROM + two ATF1508 CPLDs (control + data path) +, on slave
  boards, one TMA-arbitration GAL (§7).
- Each board's 2 MB RAM occupies **one of 8 static 2-MB windows**, filling the
  16 MB (24-bit) S-100 address space exactly when all 8 boards are present.
- **One board is strapped permanent master**; the other seven are slaves. The
  master owns the bus and never requests it; every slave is a temporary master
  (TMA) with its own priority.
- Every board runs the **same firmware from the same local addresses**; board
  identity is read off the straps (§8).

---

## 2. Memory map — two spaces, not one

The S-100 space and each board's Z280 space are **distinct** spaces joined by a
mapping table.

### 2.1 S-100 space (static, 24-bit)

Eight fixed 2-MB windows at `0`, `2`, `4`, `6`, `8`, `10`, `12`, `14` MB.
Never remapped. A board's 2 MB RAM sits in exactly one window; "global memory"
is whatever occupies the others when fewer than 8 boards are fitted. There is
no fixed "boards-upper / global-lower" split — any window can hold either.

### 2.2 Board space (per Z280, dynamic)

Five windows:

| Z280 range | Size | Meaning |
|---|---|---|
| `000000–7FFFFF` | 8 MB | **local** — 2 MB RAM + private ROM + local register block, rest spare |
| `800000–9FFFFF` | 2 MB | **window 0** |
| `A00000–BFFFFF` | 2 MB | **window 1** |
| `C00000–DFFFFF` | 2 MB | **window 2** |
| `E00000–FFFFFF` | 2 MB | **window 3** |

Each of the four windows is mapped by a **4 × 3 mapping RAM** to *any* of the 8
S-100 windows (aliases allowed — two windows may point at the same target).

### 2.3 Address translation

`A23 = 0` → local, direct. `A23 = 1` → window `k = A22:A21`, and

```
S-100 address = { mapping_ram[A22:A21] (3 bits = which 2-MB window) , A20:A0 (21 bits = offset) }
```

The low 21 bits pass straight through (a 2-MB-aligned offset); the top three
bits are purely the mapping RAM's output, so a board can reach any 2-MB
boundary in the full 16 MB. Example: Z280 `8–10 MB` (window 0) with
`mapping_ram[0] = 0b011` → S-100 `6–8 MB`.

### 2.4 Local register block (in the low 8 MB)

The low 8 MB is local RAM + private ROM + a small register block that a slave
must be able to **poll cheaply** — as a local memory cycle, never a bus grab:

| Entry | Access | Purpose |
|---|---|---|
| mapping RAM (4 × 3) | read/write | the four window targets |
| straps read-back | read | board ID / doorbell range / priority / role |
| interrupt status | **read-to-clear** | clear the doorbell `INT` latch |
| doorbell status registers | write (slave) | latched, read back by a master via `sINP` (§10) |

Because bursts are inhibited for non-instruction operations, and this block is
only ever touched by data accesses, it is never burst-fetched and caching it is
a non-issue.

---

## 3. Memory access cases

Two initiators, keyed on the arbitration each case needs.

### 3.1 Initiated by the local Z280 (on the Z-BUS)

| Case | Target | Path | Arbitration |
|---|---|---|---|
| **Z1** | local RAM (2 MB) | direct SRAM `CE`/`OE`/`WE` | **none** — default owner |
| **Z2** | local ROM (private) | direct flash `CE`/`OE`/`WE` | **none** — private |
| **Z3** | S-100 memory (other board / global) | outbound: multimicro → TMA → mapping RAM | **multimicro grant** |

Z1/Z2 are read+write (ROM write = in-system program), byte+word; Z1 is the
burst/cache fast path. Z3 is the mirror of another board's B1. The Z280's
on-chip DMA issues the same Z-BUS cycles, so it is Z1 or Z3, not a separate
initiator.

### 3.2 Initiated by a bus master (on S-100)

| Case | Target | Path | Arbitration |
|---|---|---|---|
| **B1** | my RAM | inbound: decode boundary → `BUSREQ` → park Z280 → serve SRAM → `pRDY` | **bus-yield** (`BUSREQ`/`BUSACK`) |
| **B2** | my ROM | none — private, never decoded, no `pRDY` | — |
| **B3** | someone else's / global | none — ignored | — |

### 3.3 Not memory (adjacent)

- **Mapping RAM / register block** — local memory accesses (§2.4), never on a bus.
- **Doorbell** — S-100 I/O (§10).
- **`FE`/`FF` (UART, timers, MMU)** — Z280-internal, no external cycle.
- **`INTA`** — none: interrupts are non-vectored (§10).
- **Refresh** — ignored (SRAM board).

---

## 4. Arbitration — three layers

| Layer | Direction | Mechanism |
|---|---|---|
| local (low 8 MB) | Z280 ↔ RAM/ROM | **none** — Z280 is default owner, full-speed fast path |
| outbound (upper 8 MB **and all external I/O**) | Z280 → shared bus | **multimicro** `GREQ`/`GACK` (local) → **TMA** `HOLD`/`pHLDA`/`DMA0–3` (global) |
| inbound | bus master → my RAM | **`BUSREQ`/`BUSACK`** — park the Z280, serve, `pRDY` |

The Z280's own access to low memory **forgoes arbitration in every case**: it is
the default owner and never waits. A bus master reaching the RAM does so through
the plain bus-yield handshake — the Z280 parks, it does not arbitrate. **Only the
ROM is truly private**; the RAM is shared, the low-8M register block is local.

---

## 5. Multimicro facility

The Z280's **multimicro** mode drives the upper 8 MB. Signals:

| Z280 pin | Signal | Direction |
|---|---|---|
| 30 | `GREQ` (grant request) | out — "I want the shared bus" |
| 32 | `GACK` (grant acknowledge) | in — "granted" |

Both pins are currently `CTIO0`/`CTIN0` multifunction and **unconnected** in the
schematic; they must be brought out to the control CPLD. The flow, bridged by the
CPLD and the arbitration GAL (§7):

```
Z280 GREQ  ──► control CPLD ── IWANT ──► GAL ── HOLD* + DMA0–3 ──► S-100
Z280 GACK  ◄── control CPLD ◄─ MINE ─── GAL ◄── pHLDA ───────────── S-100
```

Low memory never participates: the multimicro facility arbitrates the shared
(upper 8 MB) region only.

> **Local/shared boundary is programmable.** The multimicro facility has a
> **local-address register** — a mask + range that matches local-memory cycles —
> so the local/shared split is not hard-wired. Our `A23` split (low 8 MB local,
> upper 8 MB shared) is just the chosen configuration of that register, not a
> fixed hardware decode.

---

## 6. TMA arbitration — external GAL

The IEEE-696 temporary-master arbitration lives in a separate **GAL22V10-class**
part (ATF22V10CQZ, 24-pin DIP, same WinCUPL/ProChip toolchain). Two reasons:
the control CPLD has no spare pins (61/64), and a **master board skips the GAL
socket entirely**.

### 6.1 The IEEE-696 protocol (spec §2.8)

- `DMA0*–DMA3*` (pins 55, 56, 57, 14), open-collector, pulled up. **Higher
  binary number = higher priority**; `DMA3*` is the MSB. Up to 16 TMAs.
- `HOLD*` (74) requests; `pHLDA` (26) grants; grant is taken on the **rising
  edge of `pHLDA`**.
- Each requester drives its priority and does a **bit-wise MSB-first compare**:
  if a line is asserted low *but not by me*, a higher-priority requester is
  present, and I drop my less-significant bits. After settling, the sole
  survivor wins. This is a continuous asynchronous parallel process, not a
  sequential scan.
- Rules (spec §2.8.4): assert `HOLD*` only when free and `pHLDA` low; priority
  asserted whenever `HOLD*` is; loser drops `HOLD*` on `pHLDA` rising; winner
  holds `HOLD*` + priority until done.

### 6.2 The GAL's interface

| GAL pin | Signal | Direction |
|---|---|---|
| 4 | `PRIO[3:0]` | in — 4-bit priority, DIP switch, unique per board |
| 1 | `IWANT` | in — from control CPLD ("Z280 wants the shared bus") |
| 1 | `pHLDA` | in — from S-100 |
| 4 | `DMA3*–DMA0*` | bidir — priority bus |
| 1 | `HOLD*` | bidir — request |
| 1 | `MINE`/`ISME` | out — "you won, on `pHLDA` rising" |

~12 I/O, well inside a 22V10 (which also gives per-macrocell output enable —
exactly what the per-bit arbitration needs). The control CPLD's interface
collapses to **two pins**: `IWANT` out, `MINE` in.

**Open-collector needs external 7406 drivers.** The GAL22V10's output-enable is
a *single product term* per macrocell, so the multi-term "assert" cascade
cannot be expressed in `.OE`. The GAL instead drives totem-pole active-high
`DMA*_DRV`/`HOLD_DRV` outputs into a 7406 (hex open-collector inverter), which
sinks the active-low bus lines; the GAL reads the lines back as inputs for the
compare. The core is a 4-bit `lost[n] = lost[n-1] OR (P[n]=0 AND line_n=LOW)`
ripple → `ISME = !lost[3]`, which `MINE` latches on `pHLDA` rising.

### 6.3 The bus transfer (XS I / XS II)

On winning, the CPLD runs the spec's two-phase transfer:

1. **XS I** — assert `ADSB*`/`SDSB*`/`DODSB*` (float the permanent master's
   address/status/data), and drive the control lines at their *null* levels
   (`pSYNC`=L, `pSTVAL*`=H, `pDBIN`=L, `pWR*`=H).
2. Assert **`CDSB*`** — float the permanent master's control; this board owns
   the bus.
3. Drive cycles (mapping-RAM-translated address).
4. **XS II** — release `CDSB*` first, then `ADSB*`/`SDSB*`/`DODSB*` + `HOLD*`.

The `ADSB*`/`DODSB*`/`SDSB*`/`CDSB*` lines therefore become **bidirectional** on
this board: driven (open-collector) as a TMA, read to float our own drivers
when another TMA is active.

---

## 7. Strap block

Four independent fields:

| Strap | Width | Sets |
|---|---|---|
| board ID | 3 | RAM 2-MB window (which of 8) |
| doorbell range | 6 | I/O range base (§10, 74F521 jumpers) |
| TMA priority | 4 | GAL `DMA0–3` priority (slave only, unique) |
| master/slave | 1 | permanent-master role |

The priority is completely orthogonal to the board ID, so a low-latency board
can sit at any window and still win the bus.

---

## 8. I/O model

- **`FE`/`FF`** (UART, timers, MMU) are inside the Z280 and generate **no
  external bus cycle** — the card never decodes them.
- **Every other external I/O cycle → S-100.** For a slave this is a TMA cycle
  (`HOLD`/`pHLDA`), i.e. the same arbitration as an upper-8M memory access.
- **Local resources are memory-mapped** in the low 8 MB (§2.4), *not*
  I/O-mapped, so a slave polls them without a bus grab.

The "local vs remote" decision is therefore: `A23=0` → local (memory), `A23=1`
→ shared (memory), "is an I/O cycle" → remote. No I/O-address decode for local
resources.

---

## 9. Doorbell

A **4-port I/O range per board**, pure slave logic on the incoming side:

```
A7 A6 A5 A4 A3 A2  A1 A0
└──────┬──────────┘ └─┬─┘
   range base         function
   (6-bit, 74F521      (4 ports)
    vs. jumpers)
```

| `A1:A0` | `sOUT` (master → slave) | `sINP` (slave → master) |
|---|---|---|
| `00` | **interrupt** — set `INT` latch | status register 0 (latched) |
| `01` | **reset** — pulse `Z_RESET` | status register 1 (latched) |
| `10` | spare | spare / status |
| `11` | spare | spare / status |

- **8-bit decode is plenty** — `A8–A15` ignored; the doorbell lives in `A7:A0`.
- **Incoming = pure slave logic**: one 74F521 (6-bit range compare, DIP-set)
  feeding the CPLD, which does the 2-bit function decode — `match & sOUT &
  A1:A0=00` → latch `INT`; `match & sOUT & A1:A0=01` → reset pulse. No `HOLD`,
  no `BUSREQ`, no TMA.
- **Outgoing = a normal I/O cycle** — a TMA I/O cycle for a slave, a direct I/O
  cycle for the permanent master — writing the target board's range.
- **Interrupt** is `INT` (not `NMI`), **Mode 3 non-vectored** (no `INTA`, no
  vector read), and **cleared by a read** of a local memory address (§2.4).
  The write is pure attention; the actual message/command rides in shared
  memory (the four windows), and the ISR polls those to learn what is wanted.
- **Status registers** are latches the slave fills through the local register
  block; a master reads them back with `sINP`. This is the slave→master side of
  the doorbell, left open for whatever the slave wants to publish.
- The range base is a **6-bit jumper field** (64 possible ranges), fully
  decoupled from the board ID — a board's RAM can sit at window 3 while its
  doorbell parks in any 4-port slot that avoids I/O conflicts.

---

## 10. Reset

Two S-100 reset sources, plus the doorbell reset port:

- **`RESET` (pin 75)** — the master reset, OR'd into `Z_RESET` (the BUGS.md #1
  rev-2 fix).
- **`SLAVE CLR` (pin 52)** — open-collector; **any board can assert it at any
  time**, no arbitration. If anyone drives it active and we are a slave, we
  reset. It is both an input (slave reset source) and an output (open-collector
  driver, to clear the slaves when we — as master — reset). This is the
  "derived slave clear": the master's reset also drives `SLAVE CLR`.
- **Doorbell reset port** — a write to our reset port resets us directly.

Any slave reset — `SLAVE CLR`, the doorbell port, or the bus reset — runs the
**full ≥512-clock reset sequence**, not a short pulse.

---

## 11. Cache coherency

A bus-master write to the RAM (case B1) can land behind the Z280's 256-byte
cache. Same rule as the existing design: mark DMA/shared buffers non-cacheable
in the MMU, or flush/invalidate after each DMA. The low-8M register block is
never cached (data-only, never streamed).

---

## 12. Open items

1. **Reset pulse width** — the exact hold time for a doorbell-triggered reset
   (≥512 clocks / ~21 µs is the floor; the DS1813 gives ~100 ms at power-on).
2. **Spare doorbell slots** (`10`, `11`) — eventual function (halt? second
   interrupt? more status?).
3. **Status-register semantics** — what the slave publishes for a master to read.
4. **Multimicro scope on I/O** — the practical question (all external I/O goes
   to S-100 via TMA) is settled; the exact `GREQ` trigger for an I/O cycle vs a
   shared-memory access is a manual detail to confirm at implementation time.

---

## 13. Schematic deltas (rev 2, for reference)

- `HOLD*` (74): CPLD input → GAL output (`HOLD_DRV`) → 7406 → line.
- `pHLDA` (26): CPLD output (U20 driver) → GAL input (pin 1, CLK); U20 not stuffed on slaves.
- `DMA3*–DMA0*` (14, 57, 56, 55): unused → GAL inputs (read) + GAL outputs (`DMA*_DRV`) → 7406 → lines.
- TMA arbiter: +1× GAL22V10 (`z280-s100-arb.pld`) + 1× 7406 (5 gates used).
- `ADSB*`/`DODSB*`/`SDSB*`/`CDSB*` (22, 23, 18, 19): CPLD inputs → bidir.
- `GREQ`/`GACK` (Z280 30/32): unconnected → control CPLD.
- `SLAVE CLR` (52): open-collector bidir — slave reset input, master reset driver.
- Doorbell: +1× 74F521 (6-bit, jumper-conditioned) per board.
- Mapping RAM: +1× 74F670 (4-word × 4-bit register file, 3 bits used) — read `RA[1:0]` = `A22:A21`, `Q` → S-100 `A23:A22:A21`; write via the local register block (`WA[1:0]` + `WD` + `GW`). Kept off-CPLD.
- Straps: board ID (3), doorbell range (6), TMA priority (4), master/slave (1).
- `S100_RESET` → OR into `Z_RESET` (BUGS.md #1).
