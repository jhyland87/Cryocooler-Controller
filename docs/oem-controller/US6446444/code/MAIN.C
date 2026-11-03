// -----------------------------------------------------------------------------
//  program name : NCP.OUT
//   module name : MAIN.C
//    copyrights : Copyright (c) 2000 by Superconductor Technologies
//
//      synopsis : main() is here as well as initialization for globals
// -----------------------------------------------------------------------------
#include   "globals.h"                  // constant definitions
#include   "tasks.h"                    // task function declarations
#include   "C_Regs.h"                   // 243 reg defs for C code

// ----- global variables ------------------------------------------------------
volatile int   SpinVar;                     // spin variable
volatile int   ImotBuf[ BUF8 ];             // motor current measurment array
volatile char  SciTxBuf[ BUF32 ];           // SCI transmit buffer
volatile char  SciRxBuf[ BUF16 ];           // SCI receive buffer
volatile int   SciTxIndex;                  // SCI transmit buffer index
volatile int   SciRxHead;                   // SCI receive buffer head pointer
volatile int   SciRxTail;                   // SCI receive buffer tail pointer
volatile char  SpiTxBuf[ BUF8 ];            // SPI transmit buffer
volatile char  SpiRxBuf[ BUF8 ];            // SPI receive buffer


// ----- global string declarations ---------------------------------------------
//
//  (CONST) Strings are placed in ROM storage and copied to an appropriate
//  buffer in RAM for use. They are '0' terminated - after a CR that is used
//  as an EOS character - with their length as the first byte (as in PASCAL).
//
//  The assmebly function 'BlockMove' does the block move from program memory
//  to data memory.
//
//  |--------|------|------|------|------|------|------|------|----|---|
//  | LENGTH | CHAR | CHAR | CHAR | CHAR | CHAR | CHAR | CHAR | CR | 0 |
//  |--------|------|------|------|------|------|------|------|----|---|
//
// ------------------------------------------------------------------------------
#if defined( DEVELOPMENT )
  #if !defined( TOWER_MOUNT_CODE )
const char      csVersion[] = { 18, "4.0.07,05.11.01X\r" };
  #else
const char      csVersion[] = { 18, "4.1.08,05.18.01X\r" };
  #endif
#else
  #if !defined( TOWER_MOUNT_CODE )
const char      csVersion[] = { 17, "4.0.07,05.11.01\r" };
  #else
const char      csVersion[] = { 17, "4.1.08,05.18.01\r" };
  #endif
#endif
const char      csNAK[]     = {  3, "?\r"  };
const char      csACK[]     = {  4, "OK\r" };

// ----- external variable declarations ----------------------------------------
extern pSCI SCI;                        // see tasks.c

// ----- local function prototypes ---------------------------------------------
static void SignOn (void);

// -----------------------------------------------------------------------------
//   function : main
//  arguments : none
//    returns : nothing
//   synopsis : (1) Initializes all global variables
//              (2) Initializes the kernel and tasks
//              (3) starts the task dispatcher, which never returns
// -----------------------------------------------------------------------------
void   main( void )
 {

  InitMainModule();                     // main.c
  InitKernelModule();                   // kernel.c
  InitTasksModule();                    // tasks.c

#if defined( TOWER_MOUNT_CODE )
  selFlags &= ~ECHO;                    // enable echo
#else
  selFlags |= ECHO;                     // enable echo
  SignOn();                             // main.c
#endif

  TaskDispatcher();                     // kernel.c
 } // main

// -----------------------------------------------------------------------------
//      function : InitMainModule
//     arguments : none
//       returns : nothing
//      synopsis : Initializes the global variables.
// -----------------------------------------------------------------------------
void InitMainModule( void )
 {
  unsigned i;

  SciTxIndex    = 0;
  SciRxHead     = 0;
  SciRxTail     = 0;

  for( i=0 ; i<=(BUF8-1) ; i++ )
   ImotBuf[ i ] = 0;
 } // InitMainModule

// -----------------------------------------------------------------------------
//      function : SignOn
//     arguments : none
//       returns : nothing
//      synopsis : Displays the software version when the system resets
// -----------------------------------------------------------------------------
static void SignOn( void )
 {
  BlockMove( &csVersion, SciTxBuf );
  SciTxIndex = 0;
  SCI->SCITXBUF = SciTxBuf[ SciTxIndex ];
  while( SciTxBuf[SciTxIndex] != 0 );
 } // SignOn
