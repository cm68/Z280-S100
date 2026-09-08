;==============================================================================
;  bootrom.s  --  Z280 S-100 CPU card boot ROM   (64 KB flash @ 0x400000)
;
;  Assembled at 0x400000 (the flash's fixed physical address).
;
;  Boot hardware (rev 3): the control CPLD holds BOOTED=0 at reset, which
;  aliases the flash onto EVERY 64 KB boundary.  So the Z280's reset fetch
;  (PC=0) lands in ROM[0], and the whole 64 KB is reachable by a plain jump.
;  The FIRST memory write clears BOOTED, dropping the alias; from that instant
;  the flash answers only at 0x400000-0x40FFFF.
;
;  Boot order:
;    1. reset vector (ROM[0], executed at PC=0) jumps into the 0x400000 range
;    2. the MMU is configured so 0x400000 is a valid, jumpable segment
;    3. the first memory write clears BOOTED -- the write hits the flash chip
;       as a no-op (/WE is held off while BOOTED=0) but MEM&WRITE is what the
;       CPLD watches
;    4. execution continues in the now-decoded flash, already in the 0x400000
;       range, so the instruction stream is never disturbed
;==============================================================================

        ORG     0x400000

; ---- reset vector ----------------------------------------------------------
; Executed at PC=0 (the flash is aliased there while BOOTED=0).  Jump into the
; flash's own address range so the PC matches the assembled addresses.
RESET:  JP      START

        ORG     0x400008            ; gap after the 3-byte vector

; ---- boot entry ------------------------------------------------------------
START:  DI                          ; keep interrupts off until the MMU is live

        ; ---- 1. MMU setup: make 0x400000 (and RAM) addressable -------------
        ; The Z280's memory management is programmed through LDCTL.  Bring up
        ; a flat 1:1 map first so both the 0x400000 flash segment and the
        ; 0x000000 RAM segment are reachable, then switch to the real map
        ; after the first write.  Exact registers are firmware-specific.
        LDCTL   (MSR), A            ; clear Master Status / MMU off (illustrative)
        ; ... load segment/page-table registers for the chosen map ...

        ; ---- 2. stack at the top of the 4 MB RAM ---------------------------
        LD      SP, 0x3FFE          ; word stack, just under the flash segment

        ; ---- 3. FIRST WRITE: this CALL's PUSH clears BOOTED ----------------
        ; The push is the first write cycle.  It lands on the flash (no-op,
        ; /WE held off) and on the RAM (harmless), but MEM&WRITE is what drops
        ; the alias.  From here the flash is only at 0x400000, and we are
        ; already running there.
        CALL    INIT                ; PUSH return addr = first write -> BOOTED=1

        JP      MAIN                ; RET from INIT resumes here

; ---- low-level init (the alias is already dropped) -------------------------
INIT:   ; RAM is now fully visible at 0x000000-0x3FFFFF.
        ; ... size/test RAM, copy vectors into low RAM, load the real map ...
        RET

; ---- main ------------------------------------------------------------------
MAIN:   ; ... enable the MMU, hand off to the kernel ...
        HALT

        END
