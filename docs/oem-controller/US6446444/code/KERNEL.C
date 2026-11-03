// -----------------------------------------------------------------------------
//  program name : NCP.OUT
//   module name : KERNEL.C
//    copyrights : Copyright (c) 2000 by Superconductor Technologies
//
//      synopsis :
// -----------------------------------------------------------------------------
#include   "tasks.h"                   // task prototypes are declared here
#include   "globals.h"
// ----- macro definitions -----------------------------------------------------
#define    NUM_TASKS        (sizeof(nTCB)/sizeof(TCB))-1

// ----- global variables -----------------------------------------------------
EVENTS     gPosts;                      // OS event flags
TCB        nTCB[] =
 {
  { -1, MeasMotorCurrent,    0L, 0L, 0, 0, },       // nTCB[ 0 ]
  { -1, MeasTemps,           0L, 0L, 0, 0, },       // nTCB[ 1 ]
  { -1, ADCMeas,             0L, 0L, 0, 0, },       // nTCB[ 2 ]
  { -1, StateMachine,        0L, 0L, 0, 0, },       // nTCB[ 3 ]
  { -1, SciInputReady,       0L, 0L, 0, 0, },       // nTCB[ 4 ]
  { -1, SciOutputReady,      0L, 0L, 0, 0, },       // nTCB[ 5 ]
  { -1, OperationMonitor,    0L, 0L, 0, 0, },       // nTCB[ 6 ]
  { -1, SysDataOut,          0L, 0L, 0, 0, },       // nTCB[ 7 ]
 };

// ----- local function prototypes ---------------------------------------------

// -----------------------------------------------------------------------------
//      function : TaskDispatcher
//     arguments : none
//       returns : 0 for success, otherwise error
//      synopsis : Basic task dispatcher.
//          Note : The SpinVar variable is decremented in TPINT2 ISR every
//                 2.083mS. Therefore 2.083mS * 8 = 16.67mS = 1/60 and the
//                 task manager gets called 60 times a second (i.e. every
//                 16.67mS). These times are determined by TPINT1 and TPINT2
//                 period registers.;
//          Note : The InitTasks() function must be called before calling
//                 the task manager (i.e. TaskDispatcher() ).
// -----------------------------------------------------------------------------
int    TaskDispatcher( void )
 {
  TICKS    elapsedTime, currentTime;
  EVENTS   posts;
  unsigned i;

  SpinVar = 8;                          // initialize the spin variable
  while( 1 )                            // do forever, or at least until
   {                                    //  a fatal error occures
    while( SpinVar > 0 );               // wait for the timer to go off
    SpinVar = 8;                        //  and reload immediately

    for( i=0 ; i<=NUM_TASKS ; i++ )
     {
      currentTime = clock();
      elapsedTime = DIFFTIME( nTCB[i].last, currentTime );

       // --- see if waiting on a delay
      if( elapsedTime < nTCB[i].delay )
       continue;
      nTCB[i].delay = 0L;               // reset delay in task, if desired

       // --- see if waiting for a posted event
      posts =  nTCB[i].pends & gPosts;
      if( nTCB[i].pends && !posts )
       continue;                        // let the task reset the event

       // --- if we made it this far, run the task
      nTCB[i].func( &nTCB[i] );
      nTCB[i].last = clock();
     } // for(...
   } // while( 1 )
 } // TaskDispatcher()

// -----------------------------------------------------------------------------
//      function : InitKernelModule
//     arguments : none
//       returns : 0 if successful, !0 otherwise
//      synopsis : Initializes the kernel. The various TCB data structure
//                 members are initialized to zero. This lets the individual
//                 initialization state (uiState=0) do task initialization.
//                 Also we want to re-initialize if the kernel resets.
// -----------------------------------------------------------------------------
void   InitKernelModule( void )
 {
  unsigned i;

   // initialize OS specific data structures
  gPosts       = 0;
  for( i=0 ; i<=NUM_TASKS ; i++ )
   {
    nTCB[i].state   = -1;               // start in initialization state
    nTCB[i].delay   = 0;                // start with no delay
    nTCB[i].last    = 0;                // start with not run
    nTCB[i].pends   = 0;                // start with no pending events
    nTCB[i].posts   = 0;                // start with no posted events
   }


 } // InitKernel
