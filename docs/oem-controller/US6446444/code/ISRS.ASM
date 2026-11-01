; ============================================================================
;   program name : NCP.OUT
;    module name : ISRS.ASM - Interrupt Service Routines
;     copyrights : Copyright (c) 2000 by Superconductor Technologies
;       synopsis : ISR's are gathered in this file;
; ----------------------------------------------------------------------------
;        history : 04/13/01  DSC   Added code in the serial interrupt handler
;                                  to ignore spaces (i.e., 0x20)
; ============================================================================
           .include    F243REGS.INC
           .global     I$$SAVE, I$$REST

; ===== external declarations ================================================
           .ref        _SpinVar        ; defined in main.c
           .ref        _SciRxBuf       ; defined in main.c
           .ref        _SciRxTail      ; defined in main.c
           .ref        _SciTxBuf       ; defined in main.c
           .ref        _SciTxIndex     ; defined in main.c
           .ref        _ImotBuf        ; defined in main.c
           .ref        _gPosts         ; defined in kernel.c

 ; **** IMPORTANT ************************************************************
 ; These definitions MUST match those in the C modules which they
 ; represent, otherwise unpredictable results will occure
 ;
BUF32      .set        32              ; globals.h
BUF16      .set        16              ; globals.h
CR         .set        13              ; globals.h
LF         .set        10              ; globals.h
SCIRXREADY .set        00001h          ; kernel.h - SCI_RX_DATA_READY
 ;
 ; **** IMPORTANT ************************************************************

; ===== global declarations (defined here) ===================================
           .global     GISR2, GISR3, GISR5
           .global     _sIndex, _sValue, _sOffset, _sGain, _sTable
           .global     _ckticks, _selFlags

           .bss        _sIndex, 1
           .bss        _sValue, 1
           .bss        _sOffset, 1
           .bss        _sGain, 1
           .bss        _ckticks, 2     ; unsigned long ckticks

   ; =========================================================================
   ; SELECTION FLAG - select various options
   ;   0x0001       - echo characters back to the terminal (see BOOT.ASM)
   ;
   ; =========================================================================
           .bss        _selFlags, 1    ; selection bit flag

           .text
; ============================================================================
;      interrupt : 2
;         vector : 0x0004
;       modifies : SSTx, ACC
;       synopsis : Interrupts handled here;
;                      Name     Description               PIVR    Handled
;                      -------- ------------------------- ------- --------
;                      CMP1INT  Compare 1                 0x0021  NO
;                      CMP2INT  Compare 2                 0x0022  NO
;                      CMP3INT  Compare 3                 0x0023  NO
;                      TPINT1   Timer 1 period            0x0027  YES
;                      TCINT1   Timer 1 compare           0x0028  NO
;                      TUFINT1  Timer 1 underflow         0x0029  NO
;                      TOFINT1  Timer 1 overflow          0x002A  NO
;
;                  TPINT1 - GP timer 1 period interrupt
;                      This timer runs the PWM system
; ============================================================================
GISR2
   ; save the c run-time state
           CALL    I$$SAVE             ; AR0=BP, AR1=SP

   ; figure out which peripheral generated the interrupt
           LDP     #PIVR >> 7h         ; DP = 0x7000
           LACL    PIVR                ; get the interrupt vector into ACC
           XOR     #0027h
           BCND    GISR2_EXIT, NEQ     ; GP timer 1 period interrupt

; ===== GP Timer 1 period interrupt ==========================================
T1PINT_SISR
           SETC    SXM
           LDP     #_sIndex            ; sIndex = (++sIndex) % 256;
           LACL    _sIndex             ;
           ADD     #1                  ;
           AND     #00FFh              ;
           SACL    _sIndex             ;

           ADD     #_sTable            ; sValue = sTable[ sIndex ]
           TBLR    _sValue             ;

           LT      _sValue             ; sValue = sValue * sGain
           MPY     _sGain              ;  note: sGain is in Q15 format
           PAC                         ;        and needs to be scaled
           RPT     #14
           SFR

           ADD     _sOffset            ; sValue = sValue + sOffset

           LDP     #CMPR1 >> 7         ; DP = 0x7400
           SACL    CMPR1               ; CMPR1 = sValue, PWM1,2

   ; reset the GP timer 1 period interrupt flag
           LDP     #EVIFRA >> 7
           LACL    EVIFRA              ; ACC = *(0x742F)
           OR      #0080h              ; ACC |= 0x0080
           SACL    EVIFRA              ; *(0x742F) = ACC

GISR2_EXIT

   ; restore the C run-time state
           B       I$$REST

; ============================================================================
;      interrupt : 3
;         vector : 0x0006
;       modifies : SSTx, ACC, AR2
;       synopsis : Interrupts handled here;
;                      Name     Description               PIVR    Handled
;                      -------- ------------------------- ------- --------
;                      TPINT2   Timer 2 period            0x002B  YES
;                      TCINT2   Timer 2 compare           0x002C  NO
;                      TUFINT2  Timer 2 underflow         0x002D  NO
;                      TOFINT2  Timer 2 overflow          0x002E  NO
;
;                  TPINT2 - GP timer 2 period interrupt
;                      This interrupt -
;                      kicks the watch dog timer
;                      decrements the spin variable (see main.c)
;                      updates the system clock
;                      takes the ImotBuf measurement
; ============================================================================
GISR3
   ; save the c run-time state
           CALL    I$$SAVE             ; AR0=BP, AR1=SP
           CLRC    SXM

   ; figure out which peripheral generated the interrupt
           LDP     #PIVR >> 7h         ; DP = 0x7000
           LACL    PIVR                ; get the interrupt vector into ACC
           XOR     #002Bh
           BCND    GISR3_EXIT, NEQ     ; GP timer 2 period interrupt

; ===== GP Timer 2 period interrupt ==========================================
T2PINT_SISR
   ; kick the watch dog
           LDP     #WDKEY >> 7
           SPLK    #05555h, WDKEY      ; these two instructions
           SPLK    #0AAAAh, WDKEY      ; reset the watch dog counter

   ; setup the ADC to get ImotBuf data
           LDP     #ADCTRL2 >> 7       ; setup Direct addressing for the ADC regs
           LACL    ADCFIFO1            ; clear the FIFO
           LACL    ADCFIFO1            ; clear the FIFO

           LAR     AR2, #ADCTRL1       ; point AR2 to the ADC ctrl reg #1
           MAR     *, AR2              ; and make AR2 the current AR
           LACL    *                   ; load the reg into the ACC
           AND     #0FFF0h             ; mask off channel select
           OR      #0108h              ; setup ADC1, ch4
           SACL    *
           OR      #0001h              ; and start conversion
           SACL    *, AR1

   ; decrement the _SpinVar variable
           LDP     #_SpinVar           ;
           LACL    _SpinVar            ; spin -= 1
           SUB     #1                  ;
           BCND    $1, GEQ             ; if( spin < 0 )
           LACL    #0                  ;  spin = 0
$1
           SACL    _SpinVar            ;

   ; update the system clock
           LDP     #_ckticks           ; ckticks++
           LACL    _ckticks            ;   ACC.LO = ckticks.LSW
           ADD     _ckticks+1, 16      ;   ACC.HI = ckticks.MSW
           ADD     #1                  ;   ACC.LO = ACC.LO + 1
           SACL    _ckticks            ;   ckticks.LSW = ACC.LO
           SACH    _ckticks+1          ;   ckticks.MSW = ACC.HI

   ; make the ImotBuf measurement
           SUB     #1
           AND     #0007h              ; take the ckticks value and mod it with 8
           LDP     #_ImotBuf           ; and then add to array offset
           ADD     #_ImotBuf           ;
           SACL    *                   ; store on the stack (AR1) and point to ADC
           LDP     #_ckticks           ; get the current ckticks count to use as the
           LACL    _ckticks            ; index into the ImotBuf array
           SUB     #1                  ;
           AND     #0007h              ; mask off 3 LSB's
           OR      #0FF40h

           LDP     #ADCTRL2 >> 7       ; setup Direct addressing for the ADC regs
$2
           LACL    ADCTRL2             ; get ADCTRL2 into the ACC
           AND     #0018h              ; and see if FIFO #1 has any data ready
           BCND    $2, EQ              ; spin until it does
           LACL    ADCFIFO1            ; then load it into the ACC
           RPT     #5                  ; and right shift it by 6
           SFR                         ; note the SXM is cleared so not sign extended
           LAR     AR2, *, AR2         ; AR2 holds the destination address
           SACL    *, 0, AR1           ; so put the results there and reset SP to AR1

   ; reset the GP timer 3 period interrupt flag
           LDP     #EVIFRB >> 7
           LACL    EVIFRB              ; ACC = *(0x7430)
           OR      #0001h              ; ACC |= 0x0001
           SACL    EVIFRB              ; *(0x7430) = ACC

GISR3_EXIT
   ; restore the C run-time state
           B       I$$REST
           .newblock

; ============================================================================
;      interrupt : 5
;         vector : 0x000A
;       modifies : SSTx, ACC, AR1, AR2, AR3
;       synopsis : Interrupts handled here;
;                      Name     Description               PIVR    Handled
;                      -------- ------------------------- ------- --------
;                      SPIINT   SPI, low priority          0x0005 NO
;                      RXINT    SCI rc, low priority       0x0006 YES
;                      TXINT    SCI tx, low priority       0x0007 YES
;                      CANMBINT CAN mailbox, low priority  0x0040 NO
;                      CANERINT CAN error, low priority    0x0041 NO
; ============================================================================
GISR5
   ; save the C run-time state
           CALL    I$$SAVE             ; AR1 = SP, AR0 = BP
           SAR     AR0, *+
           SAR     AR1, *
           LAR     AR0, #2
           LAR     AR0, *0+, AR2       ; AR2 = LVP
           LAR     AR2, #1h            ; point to first arg in local frame
           MAR     *0+

   ; figure out which peripheral generated the interrupt
           LDP     #PIVR >> 7h         ; DP = 0x7000
           LACL    PIVR                ; get the interrupt vector into ACC
           XOR     #0005h              ; if PIVR == 5
           BCND    SPIINT_SISR, EQ     ;  goto SPIINT_SISR
           LACL    PIVR                ; get the interrupt vector into ACC
           XOR     #0006h              ; if PIVR == 6
           BCND    SCIRXINT_SISR, EQ   ;  goto SCIRXINT_SISR
           LACL    PIVR                ;
           XOR     #7h                 ; else if PIVR == 7
           BCND    SCITXINT_SISR, EQ   ;  goto SCITXINT_SISR
           B       GISR5_EXIT          ; else
                                       ;  goto GISR5_EXIT
;
; ===== SCI receiver interrupt (low priority)=================================
;  Received characters are put into a circular queue. Overflow is wrapped
;  around. When a CR is found the SCI_RX_DATA_READY event is signaled
;  and the main kernel routine that handles the incomming serial data
;  is triggered.
;
SCIRXINT_SISR:
           LDP     #SCICCR >> 7        ; if( SCIRXST.RXDRY == 1 )
           BIT     SCIRXST, 9          ;
           BCND    SCI_RX_ERROR, NTC   ;
           LACL    SCIRXBUF            ;  {
           SACL    *
   ; =========================================================================
   ; 04/13/01 - check for the space character. If found throwaway and return
   ; =========================================================================
           AND     #~20h, 0
           BCND    $5, NEQ
           B       GISR5_EXIT          ;   return

   ; =========================================================================
   ; UPCASE - BEGIN
   ; =========================================================================
$5
           LACL    *
           SUB     #'a', 0
           BCND    $3, NC
           LACL    *
           SUB     #'z', 0
           BCND    $3, C
           LACL    *
           AND     #0DFh
           SACL    *
$3
           LACL    *
   ; =========================================================================
   ; UPCASE - END
   ; =========================================================================

   ; =========================================================================
   ; ECHO - BEGIN
   ; =========================================================================
           LAR     AR3, #_selFlags
           MAR     *, AR3
           BIT     *, 15, AR2          ; test the ECHO bit
           BCND    $4, NTC
           SACL    *                   ; save the incomming character
$1                                     ;
           BIT     SCICTL2, 9          ; test the tx buffer to see if it's empty
           BCND    $1, NTC             ; and spin until it is
                                       ;
           LACL    SCICTL2             ; load the SCI control reg #2
           AND     #0FEh               ; and disable interrupts
           SACL    SCICTL2             ; store it back
           LACL    *                   ; retrieve the character we saved
           SACL    SCITXBUF            ; and ship it out the serial port
$2                                     ;
           BIT     SCICTL2, 9          ; spin until the tx buffer is empty again
           BCND    $2, NTC             ;
                                       ;
           LACL    SCICTL2             ; get SCI control reg #2
           OR      #01h                ; and re-enable the interrupts
           SACL    SCICTL2             ; store it back
                                       ;
           LACL    *                   ; get the received char back again
   ; =========================================================================
   ; ECHO - END
   ; =========================================================================
$4
           AND     #7Fh, 0             ;   ch = SCIRXBUF & 0x7F
           SACL    *+, 0               ;
                                       ;
           LDP     #_SciRxTail         ;   SciRxBuf[ SciRxTail ] = ch
           LACL    _SciRxTail          ;
           ADD     #_SciRxBuf          ;
           SACL    *, 0                ;
           LAR     AR3, *-             ;
           LACL    *, AR3              ;
           SACL    *, AR2              ;
                                       ;
           LACC    _SciRxTail          ;   SciRxTail = (++SciRxTail) % SCIRXLEN
           ADD     #1                  ;
           AND     #BUF16-1, 0         ;
           SACL    _SciRxTail          ;
                                       ;   if( ch == 0x0D )
           LACL    *                   ;
           XOR     #CR                 ;
           BCND    GISR5_EXIT, NEQ     ;
           SACL    *+, 0               ;    {
           LACC    _SciRxTail          ;     SciRxBuf[ SciRxTail ] = 0
           ADD     #_SciRxBuf          ;
           SACL    *, 0                ;
           LAR     AR3, *-             ;
           LACL    *, AR3              ;
           SACL    *, AR2              ;
           LACC    _SciRxTail          ;     SciRxTail = (++SciRxTail) % SCIRXLEN
           ADD     #1                  ;
           AND     #BUF16-1, 0         ;
           SACL    _SciRxTail          ;
                                       ;
           LDP     #_gPosts            ;     gPosts |= SCI_RX_DATA_READY
           LACC    _gPosts             ;
           OR      #SCIRXREADY         ;
           SACL    _gPosts             ;    }
                                       ;
           B       GISR5_EXIT          ;   return

   ; RX_ERROR error flag is set!
SCI_RX_ERROR:
           LACL    SCICTL1             ; this could be either RX ERROR
           AND     #0DFh, 0            ; or BRKDT. Either way we need to
           SACL    SCICTL1
           NOP                         ; issue a software reset of the SCI
           OR      #020h, 0            ; state machine
           SACL    SCICTL1
           B       GISR5_EXIT          ; return

 ;
 ; ===== SCI transmitter interrupt (low priority)==============================
 ; Loading a character into SCITXBUF generates an interrupt. Because the
 ; output data is NULL terminated we can test on that character to
 ; stop sending data.
 ;
SCITXINT_SISR:
           LAR     AR2, #2h            ;   - make AR2 the LVP
           MAR     *0+                 ;
           LDP     #_SciTxIndex        ; SciTxIndex = SciTxIndex + 1
           LACL    _SciTxIndex         ;
           ADD     #1h, 0              ;
           SACL    _SciTxIndex         ;
           SACL    *                   ;   - save a copy of SciTxIndex
           SUB     #BUF32, 0           ; if( SciTxIndex <= SCITXBUFLEN )
           BCND    GISR5_EXIT, GEQ     ;  {
           LACL    *-                  ;   ch = SciTxBuf[ SciTxIndex ]
           ADD     #_SciTxBuf          ;
           SACL    *, 0                ;
           LAR     AR3, *, AR3         ;
           LACL    *, AR2              ;
           BCND    GISR5_EXIT, EQ      ;   if( ch != 0 )
           LDP     #SCICCR >> 7        ;    SCITXBUF = ch
           SACL    SCITXBUF            ;  }
           B       GISR5_EXIT          ; return

 ;
 ; ===== SPI interrupt (low priority)==========================================
 ;
SPIINT_SISR:
;           B       GISR5_EXIT          ; return

 ;
 ; ===== return from interrupt ================================================
 ;
GISR5_EXIT:
   ; restore the C run-time state
           MAR     *, AR1              ; restore AR1 = SP
           SBRK    #3                  ; clean up local variable space
           LAR     AR0, *              ; restore the origional FP
           B       I$$REST
           .newblock

; ============================================================================
; Sine lookup table
;  256 entries = 360 degrees
;  These values are based on the timers being setup for 65.1uS interrupts.
;  This value comes from (1/60)*(1/256) = 65.1uS. The 60Hz sinusoid is divided
;  into 256 parts and the ISR updates the PWM register every interrupt.
; ============================================================================
           .text
                                       ;INDEX   VALUE
_sTable    .word   0000h               ;    0        0
           .word   0007h               ;    1        7
           .word   000Fh               ;    2       15
           .word   0016h               ;    3       22
           .word   001Eh               ;    4       30
           .word   0026h               ;    5       38
           .word   002Dh               ;    6       45
           .word   0035h               ;    7       53
           .word   003Ch               ;    8       60
           .word   0044h               ;    9       68
           .word   004Bh               ;   10       75
           .word   0053h               ;   11       83
           .word   005Ah               ;   12       90
           .word   0061h               ;   13       97
           .word   0069h               ;   14      105
           .word   0070h               ;   15      112
           .word   0077h               ;   16      119
           .word   007Eh               ;   17      126
           .word   0085h               ;   18      133
           .word   008Ch               ;   19      140
           .word   0093h               ;   20      147
           .word   0099h               ;   21      153
           .word   00A0h               ;   22      160
           .word   00A6h               ;   23      166
           .word   00ADh               ;   24      173
           .word   00B3h               ;   25      179
           .word   00B9h               ;   26      185
           .word   00BFh               ;   27      191
           .word   00C5h               ;   28      197
           .word   00CBh               ;   29      203
           .word   00D1h               ;   30      209
           .word   00D7h               ;   31      215
           .word   00DCh               ;   32      220
           .word   00E1h               ;   33      225
           .word   00E7h               ;   34      231
           .word   00ECh               ;   35      236
           .word   00F1h               ;   36      241
           .word   00F5h               ;   37      245
           .word   00FAh               ;   38      250
           .word   00FFh               ;   39      255
           .word   0103h               ;   40      259
           .word   0107h               ;   41      263
           .word   010Bh               ;   42      267
           .word   010Fh               ;   43      271
           .word   0113h               ;   44      275
           .word   0116h               ;   45      278
           .word   011Ah               ;   46      282
           .word   011Dh               ;   47      285
           .word   0120h               ;   48      288
           .word   0123h               ;   49      291
           .word   0125h               ;   50      293
           .word   0128h               ;   51      296
           .word   012Ah               ;   52      298
           .word   012Ch               ;   53      300
           .word   012Eh               ;   54      302
           .word   0130h               ;   55      304
           .word   0132h               ;   56      306
           .word   0133h               ;   57      307
           .word   0134h               ;   58      308
           .word   0135h               ;   59      309
           .word   0136h               ;   60      310
           .word   0137h               ;   61      311
           .word   0137h               ;   62      311
           .word   0137h               ;   63      311
           .word   0138h               ;   64      312
           .word   0137h               ;   65      311
           .word   0137h               ;   66      311
           .word   0137h               ;   67      311
           .word   0136h               ;   68      310
           .word   0135h               ;   69      309
           .word   0134h               ;   70      308
           .word   0133h               ;   71      307
           .word   0132h               ;   72      306
           .word   0130h               ;   73      304
           .word   012Eh               ;   74      302
           .word   012Ch               ;   75      300
           .word   012Ah               ;   76      298
           .word   0128h               ;   77      296
           .word   0125h               ;   78      293
           .word   0123h               ;   79      291
           .word   0120h               ;   80      288
           .word   011Dh               ;   81      285
           .word   011Ah               ;   82      282
           .word   0116h               ;   83      278
           .word   0113h               ;   84      275
           .word   010Fh               ;   85      271
           .word   010Bh               ;   86      267
           .word   0107h               ;   87      263
           .word   0103h               ;   88      259
           .word   00FFh               ;   89      255
           .word   00FAh               ;   90      250
           .word   00F5h               ;   91      245
           .word   00F1h               ;   92      241
           .word   00ECh               ;   93      236
           .word   00E7h               ;   94      231
           .word   00E1h               ;   95      225
           .word   00DCh               ;   96      220
           .word   00D7h               ;   97      215
           .word   00D1h               ;   98      209
           .word   00CBh               ;   99      203
           .word   00C5h               ;  100      197
           .word   00BFh               ;  101      191
           .word   00B9h               ;  102      185
           .word   00B3h               ;  103      179
           .word   00ADh               ;  104      173
           .word   00A6h               ;  105      166
           .word   00A0h               ;  106      160
           .word   0099h               ;  107      153
           .word   0093h               ;  108      147
           .word   008Ch               ;  109      140
           .word   0085h               ;  110      133
           .word   007Eh               ;  111      126
           .word   0077h               ;  112      119
           .word   0070h               ;  113      112
           .word   0069h               ;  114      105
           .word   0061h               ;  115       97
           .word   005Ah               ;  116       90
           .word   0053h               ;  117       83
           .word   004Bh               ;  118       75
           .word   0044h               ;  119       68
           .word   003Ch               ;  120       60
           .word   0035h               ;  121       53
           .word   002Dh               ;  122       45
           .word   0026h               ;  123       38
           .word   001Eh               ;  124       30
           .word   0016h               ;  125       22
           .word   000Fh               ;  126       15
           .word   0007h               ;  127        7
           .word   0000h               ;  128        0
           .word   0FFF9h              ;  129       -7
           .word   0FFF1h              ;  130      -15
           .word   0FFEAh              ;  131      -22
           .word   0FFE2h              ;  132      -30
           .word   0FFDAh              ;  133      -38
           .word   0FFD3h              ;  134      -45
           .word   0FFCBh              ;  135      -53
           .word   0FFC4h              ;  136      -60
           .word   0FFBCh              ;  137      -68
           .word   0FFB5h              ;  138      -75
           .word   0FFADh              ;  139      -83
           .word   0FFA6h              ;  140      -90
           .word   0FF9Fh              ;  141      -97
           .word   0FF97h              ;  142     -105
           .word   0FF90h              ;  143     -112
           .word   0FF89h              ;  144     -119
           .word   0FF82h              ;  145     -126
           .word   0FF7Bh              ;  146     -133
           .word   0FF74h              ;  147     -140
           .word   0FF6Dh              ;  148     -147
           .word   0FF67h              ;  149     -153
           .word   0FF60h              ;  150     -160
           .word   0FF5Ah              ;  151     -166
           .word   0FF53h              ;  152     -173
           .word   0FF4Dh              ;  153     -179
           .word   0FF47h              ;  154     -185
           .word   0FF41h              ;  155     -191
           .word   0FF3Bh              ;  156     -197
           .word   0FF35h              ;  157     -203
           .word   0FF2Fh              ;  158     -209
           .word   0FF29h              ;  159     -215
           .word   0FF24h              ;  160     -220
           .word   0FF1Fh              ;  161     -225
           .word   0FF19h              ;  162     -231
           .word   0FF14h              ;  163     -236
           .word   0FF0Fh              ;  164     -241
           .word   0FF0Bh              ;  165     -245
           .word   0FF06h              ;  166     -250
           .word   0FF01h              ;  167     -255
           .word   0FEFDh              ;  168     -259
           .word   0FEF9h              ;  169     -263
           .word   0FEF5h              ;  170     -267
           .word   0FEF1h              ;  171     -271
           .word   0FEEDh              ;  172     -275
           .word   0FEEAh              ;  173     -278
           .word   0FEE6h              ;  174     -282
           .word   0FEE3h              ;  175     -285
           .word   0FEE0h              ;  176     -288
           .word   0FEDDh              ;  177     -291
           .word   0FEDBh              ;  178     -293
           .word   0FED8h              ;  179     -296
           .word   0FED6h              ;  180     -298
           .word   0FED4h              ;  181     -300
           .word   0FED2h              ;  182     -302
           .word   0FED0h              ;  183     -304
           .word   0FECEh              ;  184     -306
           .word   0FECDh              ;  185     -307
           .word   0FECCh              ;  186     -308
           .word   0FECBh              ;  187     -309
           .word   0FECAh              ;  188     -310
           .word   0FEC9h              ;  189     -311
           .word   0FEC9h              ;  190     -311
           .word   0FEC9h              ;  191     -311
           .word   0FEC8h              ;  192     -312
           .word   0FEC9h              ;  193     -311
           .word   0FEC9h              ;  194     -311
           .word   0FEC9h              ;  195     -311
           .word   0FECAh              ;  196     -310
           .word   0FECBh              ;  197     -309
           .word   0FECCh              ;  198     -308
           .word   0FECDh              ;  199     -307
           .word   0FECEh              ;  200     -306
           .word   0FED0h              ;  201     -304
           .word   0FED2h              ;  202     -302
           .word   0FED4h              ;  203     -300
           .word   0FED6h              ;  204     -298
           .word   0FED8h              ;  205     -296
           .word   0FEDBh              ;  206     -293
           .word   0FEDDh              ;  207     -291
           .word   0FEE0h              ;  208     -288
           .word   0FEE3h              ;  209     -285
           .word   0FEE6h              ;  210     -282
           .word   0FEEAh              ;  211     -278
           .word   0FEEDh              ;  212     -275
           .word   0FEF1h              ;  213     -271
           .word   0FEF5h              ;  214     -267
           .word   0FEF9h              ;  215     -263
           .word   0FEFDh              ;  216     -259
           .word   0FF01h              ;  217     -255
           .word   0FF06h              ;  218     -250
           .word   0FF0Bh              ;  219     -245
           .word   0FF0Fh              ;  220     -241
           .word   0FF14h              ;  221     -236
           .word   0FF19h              ;  222     -231
           .word   0FF1Fh              ;  223     -225
           .word   0FF24h              ;  224     -220
           .word   0FF29h              ;  225     -215
           .word   0FF2Fh              ;  226     -209
           .word   0FF35h              ;  227     -203
           .word   0FF3Bh              ;  228     -197
           .word   0FF41h              ;  229     -191
           .word   0FF47h              ;  230     -185
           .word   0FF4Dh              ;  231     -179
           .word   0FF53h              ;  232     -173
           .word   0FF5Ah               ;  233     -166
           .word   0FF60h               ;  234     -160
           .word   0FF67h               ;  235     -153
           .word   0FF6Dh               ;  236     -147
           .word   0FF74h               ;  237     -140
           .word   0FF7Bh               ;  238     -133
           .word   0FF82h               ;  239     -126
           .word   0FF89h               ;  240     -119
           .word   0FF90h               ;  241     -112
           .word   0FF97h               ;  242     -105
           .word   0FF9Fh               ;  243      -97
           .word   0FFA6h               ;  244      -90
           .word   0FFADh               ;  245      -83
           .word   0FFB5h               ;  246      -75
           .word   0FFBCh               ;  247      -68
           .word   0FFC4h               ;  248      -60
           .word   0FFCBh               ;  249      -53
           .word   0FFD3h               ;  250      -45
           .word   0FFDAh               ;  251      -38
           .word   0FFE2h               ;  252      -30
           .word   0FFEAh               ;  253      -22
           .word   0FFF1h               ;  254      -15
           .word   0FFF9h               ;  255       -7

           .end                         ; ISRS.ASM
