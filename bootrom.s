; ============================================================================
;  bootrom.s  --  Z280 S-100 CPU card boot ROM (64 KB flash @ physical 0x400000)
;
;  The Z280 is a 16-bit CPU: the program counter and all logical addresses live
;  in a 64K logical space (0000H-FFFFH).  The on-chip MMU translates that into
;  the 24-bit PHYSICAL space (16 MB) through 16 page descriptor registers (PDRs).
;
;  THIS BUILD runs with program/data separation enabled (SPD): the 64K logical
;  space is 8 pages of 8K, and instruction fetches (plus PC-relative data) use
;  PDRs 8-15 while ordinary data accesses use PDRs 0-7.  Both sets point at the
;  same 64K flash so the CPU sees a unified program+data image.
;
;  At RESET the MMU is DISABLED: logical addresses pass straight through to
;  physical A0-A15 with A16-A23 = 0, so the reset fetch at logical 0000H lands
;  on physical 000000H -- exactly where the control CPLD aliases the flash while
;  BOOTED=0.
;
;  This code's whole job is to stand up the MMU so logical 0000H-FFFFH maps
;  onto physical 400000H-40FFFFH (the flash's real home), then drop the alias
;  with the first memory write.
;
;  MMU facts (Z280 MPU manual ch.7):
;   - 16 PDRs per mode (system + user).  With SPD: 8K pages, PDR 0-7 = data,
;     PDR 8-15 = program; the page-frame field's LSB (PDR bit 4) is unused.
;   - PDR = [15:5] 11-bit page frame (physical A23-A13) | [4] unused
;           | [3:0] M,C,WP,V.
;   - logical[15:13] selects the PDR; logical[12:0] is the in-page offset.
;   - programmed via I/O page FF:  Master Control   FFxxF0H (STE=14, SPD=15)
;                                  PDR Pointer      FFxxF1H (byte, 00-1FH)
;                                  Block Move       FFxxF4H (word, auto-steps)
;   - at reset the MMU is disabled and the I/O Page register is 0.
; ============================================================================

        ORG     0000H           ; assembled in the 64K logical space

; ---- reset vector: logical 0000H -> physical 000000H (flash aliased) -------
RESET:
        ; 1. Set I/O Page = FF so the on-chip MMU registers are reachable.
        ;    (control register 8 is the I/O Page -- verify against Fig 3-1.)
        LD      C, 08H          ; control register number = I/O Page
        LD      HL, 00FFH       ; value FFH (high byte 0)
        LDCTL   (C), HL         ; I/O Page := FFH

        ; 2. Point the PDR pointer at system PDR 0 (system set = 10H-1FH).
        LD      A, 10H          ; system PDR 0
        LD      BC, 00F1H       ; port FF00F1H (PDR Pointer)
        OUT     (C), A          ; set the pointer

        ; 3. Block-write 16 descriptors: 8 data (PDR 0-7) then 8 program
        ;    (PDR 8-15).  Each 8K page N maps to physical 400000H + N*2000H:
        ;    descriptor = (200H + N) << 5 | 05H  (05H = C cacheable + V valid).
        LD      HL, PDR_TABLE   ; descriptor table lives in the flash image
        LD      BC, 10F4H       ; B = 16 words, C = Block Move port FF00F4H
        OTIRW                   ; write 16 descriptors, pointer auto-increments

        ; 4. Enable the MMU with program/data separation:
        ;    STE (System Translate Enable) = bit 14, SPD (Separation) = bit 15.
        LD      HL, 0C000H      ; bits 14 and 15 set
        LD      BC, 00F0H       ; port FF00F0H (Master Control)
        OUTW    (C), HL         ; MMU on: logical 0-FFFFH -> physical 400000-40FFFFH

        ; From here instruction fetches use the program PDRs and data accesses
        ; the data PDRs, both resolving to the same flash at 400000H.

        ; 5. First memory write clears BOOTED, dropping the flash alias.  The
        ;    CALL's push is that write: FLASH_WE is held off while BOOTED=0, so
        ;    it is a no-op on the flash, but the CPLD sees MEM&WRITE and sets
        ;    BOOTED.  The MMU already maps us onto physical 400000H, so the
        ;    instruction stream is continuous.
        CALL    INIT

        JP      MAIN

; ---- page descriptor table: 8 data pages + 8 program pages, 8K each -------
;   (both halves map the same flash: logical page N -> physical 400000H+N*2000H)
PDR_TABLE:
        DEFW    4005H           ; data  page 0 -> 400000H
        DEFW    4025H           ; data  page 1 -> 402000H
        DEFW    4045H           ; data  page 2 -> 404000H
        DEFW    4065H           ; data  page 3 -> 406000H
        DEFW    4085H           ; data  page 4 -> 408000H
        DEFW    40A5H           ; data  page 5 -> 40A000H
        DEFW    40C5H           ; data  page 6 -> 40C000H
        DEFW    40E5H           ; data  page 7 -> 40E000H
        DEFW    4005H           ; prog  page 0 -> 400000H
        DEFW    4025H           ; prog  page 1 -> 402000H
        DEFW    4045H           ; prog  page 2 -> 404000H
        DEFW    4065H           ; prog  page 3 -> 406000H
        DEFW    4085H           ; prog  page 4 -> 408000H
        DEFW    40A5H           ; prog  page 5 -> 40A000H
        DEFW    40C5H           ; prog  page 6 -> 40C000H
        DEFW    40E5H           ; prog  page 7 -> 40E000H

; ---- low-level init (the flash alias is already dropped) -------------------
INIT:   ; Physical RAM is at 000000H-3FFFFFH; the flash is now only at
        ; 400000H-40FFFFH.  Set up the real page map (RAM pages + I/O), the
        ; system stack, then hand off.
        RET

; ---- main ------------------------------------------------------------------
MAIN:
        ; ... bring up the OS ...
        HALT

        END
