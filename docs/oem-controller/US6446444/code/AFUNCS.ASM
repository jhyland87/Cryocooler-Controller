; ==============================================================================
;   program name : NCP.OUT
;    module name : AFUNCS.ASM - Assembly functions
;     copyrights : Copyright (c) 2000 by Superconductor Technologies
;
;       synopsis : Misc functions that are better written in assembly language
;                  (1) String constants that reside in program memory and
;                      moved by the BlockMove_PM2DM() function
;
; ==============================================================================

           .global     _BlockMove

           .text
; ==============================================================================
;  function name : BlockMove
;           call : BlockMove( (const void*)PMsrc, (void*)DMdest )
;       synopsis : Does a block move from program memory to data memory.
;                  Strings are expected to be in PASCAL format (i.e. length,
;                  then data). This function can be interrupted (i.e. it
;                  doesn't use the RPT counter)
; register usage : AR0 = frame pointer
;                  AR1 = stack pointer
;                  AR2 = base pointer
;                  AR3 = pointer to source (length+data), then count
;                  AR4 = pointer to destination (data)
;                  ACC
; ==============================================================================
_BlockMove
           POPD    *+                   ; *SP++ = RET
           SAR     AR0, *+              ; *SP++ = FP (i.e., AR0)
           SAR     AR1, *               ; *SP   = SP (i.e., AR1)
           LAR     AR0, #1              ; AR0 = 1
           LAR     AR0, *0+, AR2        ; AR0 = *SP (i.e. AR1), SP += 1, CAR = AR2
           LAR     AR2, #-3             ; AR2 = -3
           MAR     *0+                  ; AR2 <= points to the arguments on the stack
 ;
           LAR     AR3, *-              ; AR3 = source
           LAR     AR4, *+              ; AR4 = dest
           LACL    *, AR1               ; ACC = source addr
           TBLR    *                    ; get length into local memory
           LACL    *                    ; get length into ACC
           SUB     #1                   ; and decrement by 1
           SACL    *                    ; store it back
           LAR     AR3, *, AR2          ; just to get it in AR3
           LACL    *, AR4               ; get the source address again
$1:
           ADD     #1
           TBLR    *+, AR3              ; do it
           BANZ    $1, *-, AR4
 ;
           MAR     *, AR1               ; pop off frame
           SBRK    #2                   ;
           LAR     AR0, *-              ; restore frame pointer
           PSHD    *                    ; put return address back on hardware stack
           RET                          ; and return
           .newblock

           .end                         ; AFUNCS.ASM
