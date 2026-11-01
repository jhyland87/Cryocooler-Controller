#if !defined( GLOBALS_H )
#define    GLOBALS_H
// -----------------------------------------------------------------------------
//  program name : NCP.OUT
//   module name : GLOBALS.h
//    copyrights : Copyright (c) 2000 by Superconductor Technologies
//      synopsis : Header file with non-static function declarations and
//                 global variable declarations.
//     Revisions : 3.0.xx (8/25/00)
//                     Complete rewrite of the command set including new
//                     FSM tables and command handlers (see Tasks.c)
//                 3.1.xx (8/26/00)
//                     Rewrite of the task handling, including the TCB
//                     structure, remove dynamic memory allocation
//                     and putting TCB in an array.
// -----------------------------------------------------------------------------
#include   <time.h>                     // get the Standard library time
#if defined( CLOCKS_PER_SEC )           // functions and undef the macro
#undef     CLOCKS_PER_SEC               // that determines ticks-per-sec
#endif                                  // so we can defined our own,
#define    CLOCKS_PER_SEC  480          // based on a 2.083mS tick

#define    DEVELOPMENT                  // define this for development code
#if !defined( DEVELOPMENT )             // and undef (or comment out) for
#define    RELEASE                      // production release code
#endif

#define    TOWER_MOUNT_CODE             // define if this is tower mount code
                                        // and comment out if half-rack
                                        // NOTE: Tower mount code effects
                                        // code in ISRS.ASM, specifically
                                        // the SELECTION FLAG variable that
                                        // controls echoing characters back
                                        // down the serial port. That code
                                        // has to be handled seperately.

// ----- global typedef's ------------------------------------------------------

typedef    unsigned int     UINT;
typedef    unsigned long    ULONG;
typedef    int              BOOL;

// ----- MACRO definitions ----------------------------------------------------
   // Text buffer lengths for SCI and SPI buffers
   // for efficiency (i.e. MOD's are easy) these buffer sizes are powers of 2
   // IMPORTANT: These definitions MUST match those in the .ASM module where
   //                     they are also declared, otherwise unpredictable results will
   //                     occure.
   //
#define    BUF8             8           // generic buffer lengths
#define    BUF16            16
#define    BUF32            32
#define    BUF64            64

   // Boolean definitions
#define    FALSE            0           // typical boolean definitions
#define    TRUE             !FALSE      // which is typedef'd above

   // ASCII definitions
#define    LF               0x0A        // linefeed int 10
#define    CR               0x0D        // carriage return int 13

   // hardware definitions
#define    LED1             0x0008      // IOPA3
#define    LED2             0x0010      // IOPA4
#define    LED3             0x0020      // IOPA5

   // definitions used by the state machine
#define    MIN_IMOT         0L          // this number corresponds to 0App

#if !defined( TOWER_MOUNT_CODE )
//#define   MAX_IMOT         220L         // this number corresponds to ~30App
#define    MAX_IMOT         190L        // this number corresponds to ~26App (12V)
#define    POWER_INCR       0x00010000L // defined for 12V coolers
#else
#define    MAX_IMOT         90L         // this number corresponds to ~12App (48V)
#define    POWER_INCR       0x00008000L // defined for 48V coolers
#endif

#define    TCSW_300K        230         // Tcsw @ 300K, estimated from xfer func
#define    TCSW_70K         965         // Tcsw @ 70K, estimated from xfer func

   // definitions for breaking the following addresses apart
#define    HI( x )          ( (x>>8) & 0x00FF )
#define    LO( x )          ( x & 0x00FF )

   // definitions used by the selFlags (in isrs.asm)
#define    ECHO             0x0001

   // definitions locating data in EEPROM space
#define    NVADDR_KP        0x0780      // Kp constant           - 2 bytes
#define    NVADDR_KI        0x0782      // Ki constant           - 2 bytes
#define    NVADDR_KD        0x0784      // Kd constant           - 2 bytes
#define    NVADDR_KIL       0x0786      // Ki limit constant     - 4 bytes
#define    NVADDR_TSP       0x078A      // Tsp constant          - 2 bytes
#define    NVADDR_TREJ_LO   0x078C      // TrejLoTemp constant   - 2 bytes
#define    NVADDR_TREJ_HI   0x078E      // TrejHiTemp constant   - 2 bytes
#define    NVADDR_TAMB_LO   0x0790      // TambLoTemp constant   - 2 bytes
#define    NVADDR_TAMB_HI   0x0792      // TambHiTemp constant   - 2 bytes
#define    NVADDR_ILNA_LO   0x0794      // IlnaLoCurrent const   - 2 bytes
#define    NVADDR_ILNA_HI   0x0796      // IlnaHiCurrent const   - 2 bytes
#define    NVADDR_VIN_LO    0x0798      // VinLoVolts constant   - 2 bytes
#define    NVADDR_VIN_HI    0x079A      // VinHiVolts constant   - 2 bytes
#define    NVADDR_TCSW_LO   0x079C      // TcswLoTemp constant   - 2 bytes
#define    NVADDR_TCSW_HI   0x079E      // TcswHiTemp constant   - 2 bytes
#define    NVADDR_TCSN_LO   0x07A0      // TcsnLoTemp constant   - 2 bytes
#define    NVADDR_TCSN_HI   0x07A2      // TcsnHiTemp constant   - 2 bytes
#define    NVADDR_IM_LO     0x07A4      // ImLoLimit constant    - 4 bytes
#define    NVADDR_IM_HI     0x07A8      // ImHiLimit constant    - 4 bytes
#define    NVADDR_END       0x07AC

// ----- global declarations ---------------------------------------------------
extern volatile ULONG   ckticks;        // isrs.asm
extern volatile UINT    sGain;          // isrs.asm
extern          UINT    selFlags;       // isrs.asm
extern volatile int     SpinVar;        // main.c
extern volatile int     ImotBuf[];      // main.c
extern volatile char    SciTxBuf[];     // main.c
extern volatile char    SciRxBuf[];     // main.c
extern volatile int     SciTxIndex;     // main.c
extern volatile int     SciRxHead;      // main.c
extern volatile int     SciRxTail;      // main.c
extern volatile char    SpiTxBuf[];     // main.c
extern volatile char    SpiRxBuf[];     // main.c

extern const    char    csVersion[];    // main.c
extern const    char    csNAK[];        // main.c
extern const    char    csACK[];        // main.c
// ----- global function prototypes --------------------------------------------

/* main.c 16/10/100 12.08.02 */
void InitMainModule (void);

/* parser.c 02/10/100 11.00.20 */
int parse (char *sbuf,
       char *command,
       int *index,
       char *operator,
       long *argument);

/* eeprom.c 16/10/100 12.09.46 */
ULONG EEPROM_Read (UINT addr, UINT size);
void EEPROM_Write (UINT addr, ULONG data, UINT size);

#endif     /*** GLOBALS_H ***/
