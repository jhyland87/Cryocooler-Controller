; ============================================================================
;   program name : NCP.OUT
;    module name : VECTORS.ASM
;     copyrights : Copyright (c) 2000 by Superconductor Technologies
;
;       synopsis : Maps the interrupt vectors
;                  _c_int0             defined in BOOT.ASM
;                  GISR2               defined in ISRS.ASM
;                  GISR3               defined in ISRS.ASM
;                  GISR5               defined in ISRS.ASM
;                  PHANTOM             defined in VECTORS.ASM
;
; ============================================================================

; ===== external declarations ================================================
           .global     RESET
           .ref        _c_int0
           .ref        GISR2, GISR3, GISR5

; ===== global declarations (defined here) ===================================
           .bss        _pCount, 1      ; count variable for phantom ISR
           .global     _pCount         ; and make it global

           .asect  ".vectors", 0       ; define vector space
RESET      B       _c_int0             ; Reset vector          0x0000-0x0001
INT1       B       PHANTOM             ; Interrupt level 1     0x0002-0x0003
INT2       B       GISR2               ; Interrupt level 2     0x0004-0x0005
INT3       B       GISR3               ; Interrupt level 3     0x0006-0x0007
INT4       B       PHANTOM             ; Interrupt level 4     0x0008-0x0009
INT5       B       GISR5               ; Interrupt level 5     0x000A-0x000B
INT6       B       PHANTOM             ; Interrupt level 6     0x000C-0x000D
RESERVED   B       PHANTOM             ; Reserved              0x000E-0x000F
SW_INT08   B       PHANTOM             ; software interrupt    0x0010-0x0011
SW_INT09   B       PHANTOM             ; software interrupt    0x0012-0x0013
SW_INT10   B       PHANTOM             ; software interrupt    0x0014-0x0015
SW_INT11   B       PHANTOM             ; software interrupt    0x0016-0x0017
SW_INT12   B       PHANTOM             ; software interrupt    0x0018-0x0019
SW_INT13   B       PHANTOM             ; software interrupt    0x001A-0x001B
SW_INT14   B       PHANTOM             ; software interrupt    0x001C-0x001D
SW_INT15   B       PHANTOM             ; software interrupt    0x001E-0x001F
SW_INT16   B       PHANTOM             ; software interrupt    0x0020-0x0021
TRAP       B       PHANTOM             ; TRAP                  0x0022-0x0023
NMI        B       PHANTOM             ; NMI                   0x0024-0x0025
EMU_TRAP   B       PHANTOM             ; Emulator trap         0x0026-0x0027
SW_INT20   B       PHANTOM             ; software interrupt    0x0028-0x0029
SW_INT21   B       PHANTOM             ; software interrupt    0x002A-0x002B
SW_INT22   B       PHANTOM             ; software interrupt    0x002C-0x002D
SW_INT23   B       PHANTOM             ; software interrupt    0x002E-0x002F
SW_INT24   B       PHANTOM             ; software interrupt    0x0030-0x0031
SW_INT25   B       PHANTOM             ; software interrupt    0x0032-0x0033
SW_INT26   B       PHANTOM             ; software interrupt    0x0034-0x0035
SW_INT27   B       PHANTOM             ; software interrupt    0x0036-0x0037
SW_INT28   B       PHANTOM             ; software interrupt    0x0038-0x0039
SW_INT29   B       PHANTOM             ; software interrupt    0x003A-0x003B
SW_INT30   B       PHANTOM             ; software interrupt    0x003C-0x003D
SW_INT31   B       PHANTOM             ; software interrupt    0x003E-0x003F

                            .text
; ============================================================================
;  function name : PHANTOM
;       synopsis : Catches, and counts, calls to unimplemented ISR's
; ============================================================================
PHANTOM
           LAC     _pCount             ; increment pCount
           ADDK    #1
           SACL    _pCount
           SETC    XF
           EINT                        ; re-enable interrupts
           RET

           .end
