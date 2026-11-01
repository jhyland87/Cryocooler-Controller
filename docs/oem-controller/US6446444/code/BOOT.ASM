WATCHDOG   .set     1                   ; 0 disables, 1 enables
; ==============================================================================
;   program name : NCP.OUT
;    module name : BOOT.ASM
;     copyrights : Copyright (c) 2000 by Superconductor Technologies
;
;       synopsis : The boot code follows
; ==============================================================================

           .include    F243REGS.INC

; ===== constant declarations =================================================
T_PWM      .set        028Bh            ; PWM period = 651*2*50nS = 65.1uS
                                        ; 65.1uS = 15.36kHz

; ===== external declarations =================================================
           .global     _main            ; defined in MAIN.C
           .ref        _pCount          ; defined in VECTORS.ASM
           .ref        _sIndex          ; defined in ISRS.ASM
           .ref        _sValue          ; defined in ISRS.ASM
           .ref        _sGain           ; defined in ISRS.ASM
           .ref        _sOffset         ; defined in ISRS.ASM
           .ref        _ckticks         ; defined in ISRS.ASM
           .ref        _selFlags        ; defined in ISRS.ASM

; ===== global declarations (defined here) ====================================
           .global     _c_int0          ; defined here
           .global     cinit

__stack:   .usect      ".stack", 0      ; Size is determined by the linker
           .text
; option -stack in the .CMD file
           .sect       ".reset"         ; declare a RESET location so the
                                        ; linker can put it at absolute 0x0040
                                        ; for the serial loader
; ==============================================================================
;  function name : _c_int0
;       synopsis : 1) set up stack
;                  2) initialize
;                  3) call main
; ==============================================================================
_c_int0:                                ; entry point from reset vector
           SETC    INTM                 ; Disable interrupts

   ; Initialize status bit fields *NOT* initialized at reset
           CLRC    XF                   ; Turn off xf bit
           CLRC    SXM                  ; Clear Sign Extension Mode
           CLRC    OVM                  ; Reset Overflow Mode
           CLRC    CNF                  ; Config Block B0 to Data mem.

   ; initialize the stack and frame pointers
           LAR     AR0, #__stack        ; set up frame pointer
           LAR     AR1, #__stack        ; set up stack pointer

           MAR     *, AR0               ; AR = 0

   ; in case the stack over/under flows reset on return
           LACL    #0000h               ; start of hw stack init code
           SACL    *                    ; vectors for underflow
           PSHD    *
           PSHD    *
           PSHD    *
           PSHD    *
           PSHD    *
           PSHD    *
           PSHD    *
           PSHD    *

   ; process initialization tables
           LACC    #cinit
           ADD     #1h
           BCND    skip, EQ
           CALL    _var_init, *, AR1

   ; initialize everything else
skip:
           CALL    _hw_init             ; initialize GP Timer 1, interrupt
           CALL    _main, AR1           ; start the program

terminate:
           B       terminate            ; for now, catch the fatal error
                                        ; of returning from main (should
                                        ; never happen) here
           .text
; ==============================================================================
;   function name : _hw_init
;        synopsis : 1) initialize any global variables
;                   2) setup the digital IO ports
;                   3) initialize the watchdog
;                   4) setup Event Manager
;                   5) setup the PWM outputs
;                   6) setup the timers
;                   8) enable core interrupts
; ==============================================================================
_hw_init

   ;
   ; initialize the watchdog ---------------------------------------------------
   ;
           LDP     #WDCR >> 7           ; watch dog registers @ 7020

   .if WATCHDOG
           CLRC    XF                   ; clear the error LED
           BIT     WDCR, 8              ; test the WD FLAG
           BCND    $1, NTC              ; if it's set the WD timed out
           SETC    XF                   ; so indicate
$1:
           SPLK    #0AFh, WDCR          ; enable watch dog at 2.4Hz rate
   .else
           SPLK    #0EFh, WDCR          ; disable the watch dog
   .endif
           SPLK    #05555h, WDKEY       ; these two instructions
           SPLK    #0AAAAh, WDKEY       ; reset the watch dog counter

   ;
   ; initialize any global variables -------------------------------------------
   ;
           LACL    #0
           LDP     #_pCount
           SACL    _pCount              ; pCount      = 0
           LDP     #_sIndex
           SACL    _sIndex              ; sIndex      = 0
           LDP     #_sValue
           SACL    _sValue              ; sValue      = 0
           LDP     #_sGain
           SACL    _sGain               ; sGain       = 0
           LDP     #_ckticks
           SACL    _ckticks             ; ckticks.lo  = 0
           SACH    _ckticks+1           ; ckticks.hi  = 0
           LDP     #_sOffset
           LACL    #T_PWM               ; ACC.LO      = T_PWM
           SFR                          ; T_PWM >>= 1
           SACL    _sOffset             ; sOffset     = T_PWM/2
           LDP     #_selFlags
           LACC    #0001h               ; turn on by default - ECHO
           SACL    _selFlags

   ;
   ; setup IO output -----------------------------------------------------------
   ;   OCRA     - Output Control Register A
   ;   OCRB     - Output Control Regiater B
   ;   PADATDIR - I/O port A Data and Direction register
   ;   PBDATDIR - I/O port B Data and Direction register
   ;   PCDATDIR - I/O port C Data and Direction register
   ;   PDDATDIR - I/O port D Data and Direction register
   ;
   ;   OCRA ::= 0x00C3 - SCITX,RX, CMP1,2
   ;   OCRA ::= 0x0303 - SCITX,RX, CMP3,4
   ;   OCRA ::= 0x0C03 - SCITX,RX, CMP5,6
   ;
           LDP     #OCRA >> 7           ; DP <= 0x7080
           SPLK    #000C3h, OCRA        ; OCRA[15-8]=0  => IOPB[7-0]
                                        ; OCRA[7-6]=1   => PWM2, PWM1
                                        ; OCRA[5-2]=0   => IOPA[5-2]
                                        ; OCRA[1-0]=1   => SCIRXD, SCITXD
           SPLK    #001FCh, OCRB        ; OCRB[15-10]=0 => reserved
                                        ; OCRB[9]=0     => IOPD1
                                        ; OCRB[8]=1     => IOPD0
                                        ; OCRB[7]=1     => CANRX
                                        ; OCRB[6]=1     => CANTX
                                        ; OCRB[5]=1     => SPISTE
                                        ; OCRB[4]=1     => SPICLK
                                        ; OCRB[3]=1     => SPISOMI
                                        ; OCRB[2]=1     => SPISIMO
                                        ; OCRB[1]=0     => /BIO
                                        ; OCRB[0]=0     => XF

           SPLK    #03800h, PADATDIR    ; PORTA[5-3]    => output,low
           SPLK    #00F00h, PBDATDIR    ; PORTB[7-4]    => input,low
                                        ; PORTB[3-0]    => output,low
           SPLK    #00000h, PCDATDIR    ; PORTC[7-0]    => input,low (don't care)
           SPLK    #0FC1Ch, PDDATDIR    ; PORTD[7]      => output,lo - BYP_RLY
                                        ; PORTD[6]      => output,lo - FLT_RLY
                                        ; PORTD[5]      => output,lo - /LNA_SD
                                        ; PORTD[4]      => output,hi - /EEPROM_WP
                                        ; PORTD[3]      => output,hi - /EEPROM_EN
                                        ; PORTD[2]      => output,hi - /EEPROM_HOLD
                                        ; PORTD[1]      => input,lo  - XINT2
                                        ; PORTD[0]      => input,lo  - /LNA_ERR
   ;
   ; setup Event Manager -------------------------------------------------------
   ;
           LDP     #GPTCON >> 7         ; DP = 0x7400
           SPLK    #0080h,  EVIMRA      ; enable T1PINT interrupt
           SPLK    #0001h,  EVIMRB      ; 0x0001 = enable T2PINT interrupt
           SPLK    #0000h,  EVIMRC      ; mask all C interrupts
           SPLK    #0FFFFh, EVIFRA      ; clear A interrupt flags
           SPLK    #0FFFFh, EVIFRB      ; clear B interrupt flags
           SPLK    #0FFFFh, EVIFRC      ; clear C interrupt flags

           LDP     #GPTCON >> 7
           SPLK    #0040h, GPTCON       ; 0x0400 = T2TOADC starts ADC on T2PINT
                                        ; 0x0040 = compare output enable

   ;
   ; setup ADC's ---------------------------------------------------------------
   ;
           LDP     #ADCTRL1 >> 7
           SPLK    #0C808h, ADCTRL1     ; enable ADC1, disable interrupts,
                                        ; setup ADCIN4 as input
           SPLK    #03800h, ADCTRL2     ; low priority int, just in case
           LACL    ADCTRL1              ; get ADC control reg #1
           OR      #0100h               ; clear the interrupt flag bit
           SACL    ADCTRL1
           LACL    ADCFIFO1             ; clear all the FIFO's
           LACL    ADCFIFO1
           LACL    ADCFIFO2
           LACL    ADCFIFO2

   ;
   ; setup SPI registers -------------------------------------------------------
   ;
           LDP     #SPICCR >> 7         ; DP = 0x7040
           SPLK    #0007h, SPICCR       ; 8-bit character length
           SPLK    #000Eh, SPICTL       ; delay clock, master mode, talk
           SPLK    #0013h, SPIBRR       ; baud rate = 1MHz
           SPLK    #0020h, SPIPRI       ; complete sequence
           LACL    #0080h
           OR      SPICCR
           SACL    SPICCR

   ;
   ; setup SCI registers -------------------------------------------------------
   ;
           LDP     #SCICCR >> 7         ; DP = 0x7050
           SPLK    #0007h, SCICCR       ; COM:baud,n,8,1
           SPLK    #0043h, SCICTL1      ; enable transmit, receive modes,
                                        ; RX err interrupt
           SPLK    #0003h, SCICTL2      ; enable TXRDY, RXRDY/BRKDT...
           SPLK    #0000h, SCIHBAUD     ;  ... interrupts
;;           SPLK    #0040h, SCILBAUD     ; baud rate registers = 38400
           SPLK    #0081h, SCILBAUD     ; baud rate registers = 19200
           SPLK    #0078h, SCIPRI       ; interrupt priorities low, free run
           SPLK    #0063h, SCICTL1      ; bring SCI out of reset

   ;
   ; setup the PWM outputs -----------------------------------------------------
   ;
   ;  ACTR ::= 0x000F - CMP1=HI, CMP2=HI
   ;  ACTR ::= 0x00F0 - CMP3=HI, CMP4=HI
   ;  ACTR ::= 0x0F00 - CMP5=HI, CMP6=HI
   ;
   ;  DBTCON ::= 0x0A24 - DEADBAND = 1.0uS
   ;  DBTCON ::= 0x0F24 - DEADBAND = 1.5uS
   ;  DBTCON ::= 0x0A28 - DEADBAND = 2.0uS
   ;  DBTCON ::= 0x0F28 - DEADBAND = 3.0uS
   ;
           LDP     #GPTCON >> 7         ; DP = 0x7400
           SPLK    #000Fh, ACTR         ; CMP1=HI, CMP2=HI
           SPLK    #0F28h, DBTCON       ; deadband = 3.0uS
           SPLK    #T_PWM/2, CMPR1      ; T_PWM/2
           SPLK    #8600h, COMCON       ;

   ;
   ; setup the timers ----------------------------------------------------------
   ;  GP timer 1 = 130.2uS
   ;  GP timer 2 = 2.08mS (GPT1*16) and is sync'd with GPT1
   ;
           LDP     #GPTCON >> 7         ; DP = 0x7400
           SPLK    #T_PWM, T2CMPR       ; T2 interrupt = 2.08mS
           SPLK    #0000h, T2CNT        ; initiaize T2 counter
           SPLK    #8D81h, T2CON        ; x/32 prescaler, T1CON TENABLE,
                                        ;  T1CON period
           SPLK    #T_PWM, T1PR         ; T1 period = 651*2*50nS=65.1uS
           SPLK    #T_PWM, T1CMPR       ; T1 interrupt = 65.1uS
           SPLK    #0000h, T1CNT        ; initialize the counter reg
           SPLK    #8800h, T1CON        ; cont up/down counting
           SPLK    #8840h, T1CON        ; start

   ;
   ; initialize the system clock -----------------------------------------------
   ;

   ;
   ; mask/unmask and enable core interrupts ------------------------------------
   ;
           LDP     #0
           SPLK    #00016h, IMR         ; mask all interrupts,
                                        ;  except INT2, INT3 & INT5
           SPLK    #000FFh, IFR         ; clear all core interrupt flags
           CLRC    INTM                 ; enable core interrupts
   ; done
           RET
           .newblock
; ==============================================================================
;  function name : _var_init
;       synopsis : Process initialization tables. Tables are in program
;                  memory in the following format;
;
;                  .word  <length of init data in words>
;                  .word  <address of variable to initialize>
;                  .word  <init data>
;                  .word  ...
;
;                  The init table is terminated with a zero length
; ==============================================================================
_var_init:

           ADRK    #2h                  ; allocate two words of local memory
           LACC    #cinit               ; load accumulator with base of table
           MAR     *, AR0

   ; read the initialization record header.
   ; An initialization record with a zero length terminates the list
loop:
           TBLR    *+                   ; read length
           ADD     #1
           TBLR    *                    ; read address

           LAR     AR2, *-              ; load variable address into ar2
           LAR     AR3, *, AR3          ; load count into ar3
           BANZ    copy, *-, AR2        ; check for end of table

   ; end-of-list, return to caller
           MAR     *, AR1               ; restore the SP
           SBRK    #2h                  ; deallocate local variables
           RET                          ; return to _c_int0

   ; perform copy of data from program memory to data (.bss) memory
copy:
           ADD     #1                   ; increment pointer to data
           TBLR    *+, AR3              ; copy data from program to variable
           BANZ    copy, *-, AR2        ; until count is zero

           ADD     #1                   ; point to beginning of next record
           B       loop, AR0            ; go process next record

           .end                         ; BOOT.ASM
