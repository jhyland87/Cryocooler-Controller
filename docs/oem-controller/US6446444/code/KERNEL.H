#if !defined( KERNEL_H )
#define    KERNEL_H
// ---------------------------------------------------------------------------
//  program name : NCP.OUT
//   module name : KERNEL.H
//    copyrights : Copyright (c) 2000 by Superconductor Technologies
//      synopsis :
// ---------------------------------------------------------------------------
#include   "globals.h"

// ----- macro definitions ---------------------------------------------------
#define    MAXTICKS        0xFFFFFFFF
#define    DIFFTIME( old, new ) \
               (((new)>(old)) ? ((new)-(old)) : ((MAXTICKS-(old))+(new+1)))

   // 'pends' and 'posts' events
#define    SCI_RX_DATA_READY   0x0001  // EOS (i.e. CR) found in SciRxBuf[]
#define    SCI_TX_DATA_READY   0x0002  // SciTxBuf[] has data to send
#define    SCI_TX_BUSY         0x0004  // Serial ISR is busy sending data
#define    SYS_DATA_OUT        0x0008  // start the system data out task

// ----- typedef's -----------------------------------------------------------
typedef    unsigned long   TICKS;      // timer tick counter
typedef    unsigned int    EVENTS;     // pend, post events

typedef    struct tcb_tag* pTCB;
typedef    void (*TASK_FUNCTION)( pTCB );

typedef struct tcb_tag  // ----- Task Control Block
 {
  UINT             state;              // current state of TCB FSM
  TASK_FUNCTION    func;               // pointer to task function
  TICKS            delay;              // ticks to delay running the task
  TICKS            last;               // ticks last time task executed
  EVENTS           pends;              // events on which the task is blocking
  EVENTS           posts;              // events posted by this task
 } TCB;

// ----- external declarations -----------------------------------------------
extern EVENTS      gPosts;             // kernel.c
// ----- function prototypes -------------------------------------------------

/* kernel.c 05/10/100 16.34.48 */
int TaskDispatcher (void);
void InitKernelModule (void);

#endif     /*** KERNEL_H ***/
