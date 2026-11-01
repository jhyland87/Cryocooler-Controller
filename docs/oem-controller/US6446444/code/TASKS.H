#if !defined( TASKS_H )
#define    TASKS_H
// ---------------------------------------------------------------------------
//  program name : NCP.OUT
//   module name : TASKS.H
//    copyrights : Copyright (c) 2000 by Superconductor Technologies
//
//      synopsis :
// ---------------------------------------------------------------------------
#include   "kernel.h"

// ----- function prototypes -------------------------------------------------

/* tasks.c 05/10/100 16.25.58 */
void MeasMotorCurrent (pTCB tcb);
void MeasTemps (pTCB tcb);
void ADCMeas (pTCB tcb);
void StateMachine (pTCB tcb);
void SciInputReady (pTCB tcb);
void SciOutputReady (pTCB tcb);
void OperationMonitor (pTCB tcb);
void SysDataOut (pTCB tcb);
void InitTasksModule (void);

#endif     /*** TASKS_H ***/
