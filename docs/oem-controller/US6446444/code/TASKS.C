// -----------------------------------------------------------------------------
//  program name : NCP.OUT
//   module name : TASKS.C
//    copyrights : Copyright (c) 2000 by Superconductor Technologies
//
//      synopsis : All the task functions are here
//                     MeasMotorCurrent
//                     MeasTemps
//                     ADCMeas
//                     StateMachine
//                     SciInputReady
//                     SciOutputReady
//                     OperationMonitor
//                     SysDataOut
// -----------------------------------------------------------------------------
#include   "globals.h"
#include   "tasks.h"                   // includes kernel.h
#include   "C_Regs.h"                  // 243 regs for C code

// ----- debugging macros (undefine to turn off) -------------------------------
//#define    DB_ECHO
//#define    DB_EMU

// ----- macro definitions -----------------------------------------------------
#define    ADCIN00         0x0000      // T_MOT
#define    ADCIN01         0x0002      // T_AMB
#define    ADCIN02         0x0004      // V_LNA
#define    ADCIN03         0x0006      // I_LNA
#define    ADCIN04         0x0008      // ImotBuf (handled in ISR-3)
#define    ADCIN05         0x000A      // V_IN
#define    ADCIN06         0x000C      // CTS1_WR
#define    ADCIN07         0x000E      // CTS1_NR

 // --- IO (Port B) definitions ------------------------------------------------
#define    IOPB0           0x01
#define    IOPB1           0x02
#define    IOPB2           0x04
#define    IOPB3           0x08
#define    IOPB4           0x10
#define    IOPB5           0x20
#define    IOPB6           0x40
#define    IOPB7           0x80

#define    TDX_OK          IOPB1       // bit line that controls the RS232 amp
 // --- SmStatusBitFlag bit field definitions ----------------------------------
 // Among other things, the SmStatusBitFlag keeps the state of the
 // following IO hardware;
 //
 //     FAULT   led     PA3
 //     READY   led     PA4
 //     ALIVE   led     PA5
 //     LNA_SD  bit     PD5

 //     FAULT   relay   PD6
 //     BYPASS  relay   PD7
 //
 // The IO bit is set or reset depending on the desired action required. Then
 // in the 'OperationMonitor' task (which is called every 500mS) the bit
 // fields are examined and the ports updated.
 //
 // bit position   action
 // ------------   -----------------------------------------------------------
 //             0  0 = state machine is in automatic mode
 //                1 = state machine is in maunal mode
 //             1  0 = debug string is not being output
 //                1 = debug string is being output
 //             2      no currently used
 //             3  0 = FAULT led off
 //                1 = FAULT led on
 //             4  0 = READY led off
 //                1 = READY led on
 //             5  0 = ALIVE led off
 //                1 = ALIVE led on
 //             6  0 = FAULT led toggle off
 //                1 = FAULT led toggle on
 //             7  0 = READY led toggle off
 //                1 = READY led toggle on
 //             8  0 = ALIVE led toggle off
 //                1 = ALIVE led toggle on
 //             9  0 = LNA off
 //                1 = LNA on
 //            10  0 = FAULT relay off
 //                1 = FAULT relay on
 //            11  0 = BYPASS relay off
//                1 = BYPASS relay on
 //            12  0 = disable the Tcsn data filter
 //                1 = enable the Tcsn data filter
 //            13      no currently used
 //            14      no currently used
 //            15      no currently used
 //
#define    SMBF_MODE                0x0001      // auto/manual mode
#define    SMBF_DEBUG               0x0002      // debug string
#define    SMBF_NOTUSED_1           0x0004
#define    SMBF_FAULT_LED           0x0008      // FAULT led, matches IO port bit
#define    SMBF_READY_LED           0x0010      // READY led, matches IO port bit
#define    SMBF_ALIVE_LED           0x0020      // ALIVE led, matches IO port bit
#define    SMBF_FAULT_LED_TOGGLE    0x0040      // FAULT led toggle
#define    SMBF_READY_LED_TOGGLE    0x0080      // READY led toggle
#define    SMBF_ALIVE_LED_TOGGLE    0x0100      // ALIVE led toggle
#define    SMBF_LNA_CTRL            0x0200      // LNA control, matches IO >> 4
#define    SMBF_FAULT_RELAY         0x0400      // FAULT relay, matches IO >> 4
#define    SMBF_BYPASS_RELAY        0x0800      // BYPASS relay, matches IO >> 4
#define    SMBF_TCSN_FILTER         0x1000      // enables | disables the Tcsn median filter
#define    SMBF_NOTUSED_2           0x2000
#define    SMBF_NOTUSED_3           0x4000
#define    SMBF_NOTUSED_4           0x8000

 //
 // Definitions to handle the LED states. Turning on an led implies it's not
 // toggling. Toggling the led implies that it is on. Turning off the led requires
 // disabling the toggling. LED's are on PORT A
 //
#define    SHIFT_TO_TOGGLE          3
#define    LED_MASK                 (SMBF_FAULT_LED|SMBF_READY_LED|SMBF_ALIVE_LED)
#define    LED_ON( x )              SmStatusBitFlag |=  (x); SmStatusBitFlag &= ~(x<<SHIFT_TO_TOGGLE)
#define    LED_OFF( x )             SmStatusBitFlag &= ~(x); SmStatusBitFlag &= ~(x<<SHIFT_TO_TOGGLE)
#define    LED_TOGGLE( x )          SmStatusBitFlag |=  (x); SmStatusBitFlag |=  (x<<SHIFT_TO_TOGGLE)

 //
 // Definitions to handle FAULT, BYPASS relays and LNA shutdown
 // These states are mutually exclusive
 //
#define    SHIFT_TO_RELAY           4
#define    RELAY_MASK               ((SMBF_LNA_CTRL|SMBF_FAULT_RELAY|SMBF_BYPASS_RELAY)>>SHIFT_TO_RELAY)
#define    LNA_ON                   (SmStatusBitFlag |= SMBF_LNA_CTRL)
#define    LNA_OFF                  (SmStatusBitFlag &= ~SMBF_LNA_CTRL)
#define    RELAY_ON( x )           (SmStatusBitFlag &= ~(x))
#define    RELAY_OFF( x )            (SmStatusBitFlag |= (x))
//#define    RELAY_ON( x )            (SmStatusBitFlag |= (x))
//#define    RELAY_OFF( x )           (SmStatusBitFlag &= ~(x))

 // --- SmErrorBitFlag bit field definitions -----------------------------------
 // The SmErrorBitFlag keeps the state of any errors while the state machine
 // is operating
 //
 // bit position   description
 // ------------   -----------------------------------------------------------
 //            0  indicates Trej is out of range
 //            1  indicates Tamb is out of range
 //            2  indicates Ilna is out of range
 //            3  indicates Vin  is out of range
 //            4  indicates Tcsw is out of range
 //            5  indicates Tcsn is out of range
 //            6  indicates that Tcsn no tracking TcSp
 //            7  currently not used
 //            8  currently not used
 //            9  currently not used
 //           10  currently not used
 //           11  currently not used
 //           12  currently not used
 //           13  currently not used
 //           14  currently not used
 //           15  currently not used

#define    SM_ERROR_TREJ_RANGE      0x0001      // major fault
#define    SM_ERROR_TAMB_RANGE      0x0002      // minor fault
#define    SM_ERROR_ILNA_RANGE      0x0004      // minor fault
#define    SM_ERROR_VIN_RANGE       0x0008      // major fault
#define    SM_ERROR_TCSW_RANGE      0x0010      // major fault
#define    SM_ERROR_TCSN_RANGE      0x0020      // major fault
#define    SM_ERROR_TCSP_RANGE      0x0040      //

//#define    SM_MINOR_FAULT        (SM_ERROR_TAMB_RANGE | \
//                                  SM_ERROR_ILNA_RANGE)
//#define    SM_MAJOR_FAULT        (SM_ERROR_TREJ_RANGE | \
//                                  SM_ERROR_VIN_RANGE  | \
//                                  SM_ERROR_TCSW_RANGE | \
//                                  SM_ERROR_TCSN_RANGE)

 // --- state machine state definitions ----------------------------------------
#define    SM_INIT         0           // SM initialization state
#define    SM_IDLE         1           // SM idle state
#define    SM_COOLDOWN     2           // SM cooldown state
#define    SM_CONTROL      3           // SM temp control state
#define    SM_POWERDOWN    4           // SM power down state
#define    SM_FINAL        5           // SM final (error) state

 // --- digital filter definitions ---------------------------------------------
#define    TCSN_DATA_SIZE  5           // circular array for Tcsn data

// ----- global variables ------------------------------------------------------
UINT   NvAddress;                      // S12 sets variable, S13 read/write it
ULONG  RunTimeAcc;                     // run time accumulator, 2^32s = 136y
pSCI   SCI     = (pSCI) 0x7050;
pADC   ADC     = (pADC) 0x7032;
pDIO   DIO     = (pDIO) 0x7090;
pSPI   SPI     = (pSPI) 0x7040;

// ----- state machine variables -----------------------------------------------
int    SmCurrentState;                 // current state of the state machine
int    SmLastState;                    // remember the last state we were in
int    SmCurrentPhase;                 // current phase of the state machine
UINT   SmStatusBitFlag;                // bit flag to hold state machine status
UINT   SmErrorBitFlag;                 // bit flag to hold state machine errors
UINT   LastSmErrorBitFlag;             // bit flag to hold previous errors

// ----- motor current variables -----------------------------------------------
long   ImOut;                          // RMS motor current estimate, U(16,16)
long   ImSp;                           // current setpoint, U(16,16)
long   ImEk0;                          // the following variables are used
long   ImEk1;                          // in the control loop routine
long   ImUk0;                          // 'ImServo' to close the motor
long   ImUk1;                          // current control loop.
long   ImSpCoolDown_m;
long   ImSpCoolDown_b;
long   lCdSp;
long   lPidSp;

// ----- temperature variables -------------------------------------------------
int    Trej;                           // motor heat reject temperature
int    Tamb;                           // ambient temperature
int    Vlna;                           // LNA power supply output voltage
int    Ilna;                           // LNA power supply current draw
int    Vin;                            // motor driver input voltage
int    Tcsw;                           // Cold Stage, wide range temp sensor
int    Tcsn;                           // Cold Stage, narrow range temp sensor
int    TcsnData[ TCSN_DATA_SIZE ];     // data array to keep sample data
int    TcsnDataIndex;                  // index into Tcsn data array

// ----- temp control variables (used in the PID calculations) -----------------
long   TcUk0;
long   TcUk1;
long   TcLastI;
int    TcLastTcsn;
int    TcLastD;
int    TcEk0;
int    TcEk1;

// ----- limit variables (read from EEPROM on reset) ---------------------------
long   TcLimI;                         // integrator saturation limit
int    TcKp;                           // proportional gain
int    TcKi;                           // integrator gain
int    TcKd;                           // derivative gain
int    TcSp;                           // Tc setpoint
int    TrejLoTemp;                     // Trej lower temperature limit
int    TrejHiTemp;                     // Trej upper temperature limit
int    TambLoTemp;                     // Tamb lower temperature limit
int    TambHiTemp;                     // Tamb upper temperature limit
int    IlnaLoCurrent;                  // Ilna lower current limit
int    IlnaHiCurrent;                  // Ilna upper current limit
int    VinLoVolts;                     // Vin lower voltage limit
int    VinHiVolts;                     // Vin upper voltage limit
int    TcswLoTemp;                     // Tcsw lower temperature limit
int    TcswHiTemp;                     // Tcsw upper temperature limit
int    TcsnLoTemp;                     // Tcsn lower temperature limit
int    TcsnHiTemp;                     // Tcsn upper temperature limit
long   ImLoLimit;                      // lower drive limit in the idle state
long   ImHiLimit;                      // upper drive limit in all states

// ----- local function prototypes ---------------------------------------------
static int SetCommand (int index, char operator, long argument);
static int InquireCommand (int index, char operator, long argument);
static void MotorOn (BOOL arg);
static long CoolDownSp (void);
static long PidSp (void);
static void ImServo (void);
static unsigned long iSqrt (unsigned long x);
static void SystemDataOut (void);
static void LoadRtConstants (void);
static int MedianFilter (int data[]);
static void logEvent (void);

// -----------------------------------------------------------------------------
//      function : MeasMotorCurrent
//          task : MEASURE_MOTOR_CURRENT
//      pends on : nothing
//         posts : nothing
//     arguments : pTCB - pointer to TCB for this task
//       returns : nothing
//      synopsis : Runs every tick. Takes the 8 new values in the ImotBuf
//                 array and calculates the average current
// -----------------------------------------------------------------------------
void MeasMotorCurrent( pTCB tcb )
 {
  long          tmp;
  long          gMotAvg;
  long          gMotVar;
  unsigned      i;

  if( tcb->state == 0 )     // --- task in run state
   {
       // calculate the average
    gMotAvg = 0L;
    for( i=0 ; i<=(BUF8-1) ; i++ )
     gMotAvg += ImotBuf[ i ];
    gMotAvg >>= 3;                     // divide by 8

       // calculate the variance
    gMotVar = 0L;
    for( i=0 ; i<=(BUF8-1) ; i++ )
     {
      tmp = gMotAvg - ImotBuf[i];
      gMotVar += (tmp*tmp);
     }
    gMotVar >>= 3;                     // divide by 8

       // and the standard deviation
    ImOut = iSqrt( gMotVar );
    ImServo();
   }
  else                     // --- initialization
   {
    tcb->state = 0;
    tcb->delay = 0;
    tcb->pends = 0;
    tcb->posts = 0;
   }
 } // MeasMotorCurrent

// -----------------------------------------------------------------------------
//      function : MeasTemps
//          task : MEASURE_TEMPS
//      pends on : nothing
//         posts : nothing
//     arguments : pTCB - pointer to TCB for this task
//       returns : nothing
//      synopsis : Runs every tick to alternately measure ...
//                     CTS1_WR - ADCIN06, Tcsw
//                     CTS1_NR - ADCIN07, Tcsn
//                 this means that the sample time for these measurements
//                 2/60 = 1/30 sec.
// -----------------------------------------------------------------------------
void MeasTemps( pTCB tcb )
 {
  int      tmp, state;

  tmp   = 0;
  state = tcb->state;

   // we need to turn off the INT3 because we're going to use
   // the ADC. Otherwise we might disrupt the ImotBuf measurement
  asm( " SETC    INTM"    );         // disable interrupts
  asm( " LDP     #0"      );         // load data page 0
  asm( " LACL    0004h"   );         // get IMR into ACC
  asm( " AND     #0FFFBh" );         // mask INT3 in ACC
  asm( " SACL    0004h"   );         // and write back to IMR
  asm( " CLRC    INTM"    );         // re-enable interrupts

  switch( state )
   {
    case 0 :                   // --- measure Tcsw
     {
      ADC->ADCTRL1 &= 0xFFF1;        // clear any previous ch
      ADC->ADCTRL1 |= ADCIN06;       // and select ch 6
      ADC->ADCTRL1 |= 0x0001;        // start the conversion
      while( !(ADC->ADCTRL2 & 0x0018) ); // spin waiting for data
      tmp = ADC->ADCFIFO1 >> 6;      // shift and save it
     }
     break;

    case 1 :                   // --- measure Tcsn
     {
      ADC->ADCTRL1 &= 0xFFF1;        // clear any previous ch
      ADC->ADCTRL1 |= ADCIN07;       // and select ch 7
      ADC->ADCTRL1 |= 0x0001;        // start the conversion
      while( !(ADC->ADCTRL2 & 0x0018) ); // spin waiting for data
      tmp = ADC->ADCFIFO1 >> 6;      // shift and save it
     }
     break;

    default :                  // --- initialize
     {
      tcb->state  = 0;
      tcb->delay  = 0;
      tcb->pends  = 0;
      tcb->posts  = 0;
     }
   } // switch( #1

   // OK, we're done with the ADC so release INT3
  asm( " SETC    INTM"    );         // disable interrupts
  asm( " LDP     #0"      );         // load IMR data page
  asm( " LACL    0004h"   );         // get IMR into ACC
  asm( " OR      #0004h"  );         // unmask INT3 in ACC
  asm( " SACL    0004h"   );         // and write back to IMR
  asm( " CLRC    INTM"    );         // re-enable interrupts

   // we've released the interrupt handler so we can continue
   // with our calculations and filtering ...

  switch( state )
   {
    case  0 :
     {
      Tcsw = tmp;
     }
     break;
    case  1 :
     {
      if( ++TcsnDataIndex >= TCSN_DATA_SIZE )
       TcsnDataIndex = 0;
      TcsnData[ TcsnDataIndex ] = tmp;

      if( SmStatusBitFlag & SMBF_TCSN_FILTER )
       Tcsn = MedianFilter( TcsnData );    // filter the temperature data
      else
       Tcsn = tmp;                         // use raw temperature data
     }
     break;
    default :
     break;
   } // switch( #2 )

  tcb->state = (++state % 2);
 } // MeasTemps

// -----------------------------------------------------------------------------
//      function : ADCMeas
//          task : ADC_MEASUREMENTS
//      pends on : nothing
//         posts : nothing
//     arguments : pTCB - pointer to TCB for this task
//       returns : nothing
//      synopsis : Measures each of the following once a second
//                     T_MOT   - ADCIN00, Trej
//                     T_AMB   - ADCIN01, Tamb
//                     V_LNA   - ADCIN02, Vlna
//                     I_LNA   - ADCIN03, Ilna
//                     V_IN    - ADCIN05, Vin
// -----------------------------------------------------------------------------
void ADCMeas( pTCB tcb )
 {
  int      tmp, state;

  tmp   = 0;
  state = tcb->state;

   // we need to turn off the INT3 because we're going to use
   // the ADC. Otherwise we might disrupt the ImotBuf measurement
  asm( " SETC    INTM"    );           // disable interrupts
  asm( " LDP     #0"      );           // load data page 0
  asm( " LACL    0004h"   );           // get IMR into ACC
  asm( " AND     #0FFFBh" );           // mask INT3 in ACC
  asm( " SACL    0004h"   );           // and write back to IMR
  asm( " CLRC    INTM"    );           // re-enable interrupts

  switch( state )
   {
    case  0 :                  // measure Trej - motor heat reject temperature
     {
      ADC->ADCTRL1 &= 0xFFF1;          // clear any previous ch
      ADC->ADCTRL1 |= ADCIN00;         // and select ch 0
      ADC->ADCTRL1 |= 0x0001;          // start the conversion
      while( !(ADC->ADCTRL2 & 0x0018) ); // spin waiting for data
      tmp = ADC->ADCFIFO1 >> 6;        // shift and store it

     }
     break;
    case  1 :                  // measure Tamb - ambient temperature
     {
      ADC->ADCTRL1 &= 0xFFF1;          // clear any previous ch
      ADC->ADCTRL1 |= ADCIN01;         // and select ch 1
      ADC->ADCTRL1 |= 0x0001;          // start the conversion
      while( !(ADC->ADCTRL2 & 0x0018) ); // spin waiting for data
      tmp = ADC->ADCFIFO1 >> 6;        // shift and store it
     }
     break;
    case  2 :                  // measure Vlna - LNA power supply output voltage
     {
      ADC->ADCTRL1 &= 0xFFF1;          // clear any previous ch
      ADC->ADCTRL1 |= ADCIN02;         // and select ch 2
      ADC->ADCTRL1 |= 0x0001;          // start the conversion
      while( !(ADC->ADCTRL2 & 0x0018) ); // spin waiting for data
      tmp = ADC->ADCFIFO1 >> 6;        // shift and store it
     }
     break;
    case  3 :                  // measure Ilna - LNA power supply current draw
     {
      ADC->ADCTRL1 &= 0xFFF1;          // clear any previous ch
      ADC->ADCTRL1 |= ADCIN03;         // and select ch 3
      ADC->ADCTRL1 |= 0x0001;          // start the conversion
      while( !(ADC->ADCTRL2 & 0x0018) ); // spin waiting for data
      tmp = ADC->ADCFIFO1 >> 6;        // shift and store it
     }
     break;
    case  4 :                  // measure Vin - motor driver input voltage
     {
      ADC->ADCTRL1 &= 0xFFF1;          // clear any previous ch
      ADC->ADCTRL1 |= ADCIN05;         // and select ch 5
      ADC->ADCTRL1 |= 0x0001;          // start the conversion
      while( !(ADC->ADCTRL2 & 0x0018) ); // spin waiting for data
      tmp = ADC->ADCFIFO1 >> 6;        // shift and store it
     }
     break;
    default :                  // --- initialization
     {
      tcb->state = 0;
      tcb->delay = 0;
      tcb->pends = 0;
      tcb->posts = 0;
     }
     break;
   } // switch( #1

  asm( " SETC    INTM"    );           // disable interrupts
  asm( " LDP     #0"      );           // load IMR data page
  asm( " LACL    0004h"   );           // get IMR into ACC
  asm( " OR      #0004h"  );           // unmask INT3 in ACC
  asm( " SACL    0004h"   );           // and write back to IMR

  asm( " CLRC    INTM"    );           // re-enable interrupts

   // after the interrupts are re-enabled we can do the signal processing
  switch( state )
   {

    case  0 :
     {
      Trej = tmp;
     }
     break;
    case  1 :
     {
      Tamb = tmp;
     }
     break;
    case  2 :
     {
      Vlna = tmp;
     }
     break;
    case  3 :
     {
      Ilna = tmp;
     }
     break;
    case  4 :
     {
      Vin = tmp;
     }
     break;
    default:
     break;
   } // switch( #2

  tcb->state = (++state % 5);          // setup next state
  tcb->delay = CLOCKS_PER_SEC / 5;     // setup next capture time
 } // ADCMeas

// -----------------------------------------------------------------------------
//      function : StateMachine
//          task : STATEMACHINE
//      pends on : nothing
//         posts : nothing
//     arguments : pTCB - pointer to TCB for this task
//       returns : nothing
//      synopsis : Implements a nested state machine for "automatic" control
//                 of the system.
//
//         Notes : Error Checking
//                 Some errors are checked for on entry while other require
//                 examination only in certain states. In all events the
//                 system error flag is updated and the error is handled
//                 in the state machine. The error is logged in the
//                 OPERATION_INDICATOR task.
//
// -----------------------------------------------------------------------------
void StateMachine( pTCB tcb )
 {
  static clock_t   start_time, t1, t2 ,t3;

#if !defined( DB_EMU )
   // --- Do fatal error check -------------------------------------------------
  if( Trej < TrejHiTemp )                      // check the motor temp
   {                                           // inequality is reversed because
    SmErrorBitFlag |= SM_ERROR_TREJ_RANGE;     // thermocouple has neg tempco
    SmCurrentState = SM_POWERDOWN;
   }

  if( Vin < VinLoVolts || Vin > VinHiVolts )   // check the input voltage
   {
    SmErrorBitFlag |= SM_ERROR_VIN_RANGE;
    SmCurrentState = SM_POWERDOWN;
   }
#else
  Tamb = 614;                          // 300K
  ImLoLimit = 1638400L;                // 25.0
  Trej = 200;                          // 64C
  Tcsn = 0;
  TcSp = 512;
#endif

   // --- Begin State Machine --------------------------------------------------
  if( tcb->state == 0 )    // --- task in run state
   {
    if( SmCurrentState != SmLastState )     // initialize the phase if we've
     SmCurrentPhase = 0;                    // changed state
    SmLastState = SmCurrentState;

    switch( SmCurrentState )
     {
       // ----------------------------------------------------------------------
       // SM_INIT (0)  : Initialize the state machine
       //                No error checking here, just a 15s delay to facilitate
       //                stopping the state machint before it gets a chance to
       //                get started (programming, debug, etc.)
       // ----------------------------------------------------------------------
      case SM_INIT :
       {
        switch( SmCurrentPhase )
         {
          case 0 :     // --- start the timer, setup the IO
           {
            LED_ON( SMBF_FAULT_LED );          // FAULT LED
            LED_ON( SMBF_READY_LED );          // READY LED
            RELAY_ON( SMBF_FAULT_RELAY );      // FAULT RELAY
            RELAY_ON( SMBF_BYPASS_RELAY );     // BYPASS RELAY
            LNA_OFF;                           // LNA

            start_time = clock();
            t3 = CLOCKS_PER_SEC * 15;
            SmCurrentPhase = 1;
           }
           break;

          case 1 :     // --- wait 15 seconds before beginning
           {
            t1 = clock();
            t2 = t1 - start_time;
            if( t2 > t3 )
             SmCurrentPhase = 2;
           }
           break;

          case 2 :     // --- transition to SM_IDLE in automatic mode
           {
            if( !(SmStatusBitFlag & SMBF_MODE) )
             {
              SmCurrentState = SM_IDLE;
             }
           }
           break;

          default :    // --- Something went wrong so start over
           {
            SmCurrentPhase = 0;
           }
           break;
         } // SM_INIT : switch( SmCurrentPhase )
       }
       break;

       // ----------------------------------------------------------------------
       // SM_IDLE (1)  : Throttle power to ~40W either up or down. This state
       //                is used to check for bad temp sensors and will
       //                transition to SM_POWERDOWN if 70K < Tcsw > 300K.
       //                Should this condition be detected in higher states
       //                there will be a transition back here.
       // ----------------------------------------------------------------------
      case SM_IDLE :
       {
        switch( SmCurrentPhase )
         {
          case 0 :     // --- initialize the local's, timer, motor and IO
           {
            LED_ON( SMBF_FAULT_LED );          // FAULT LED
            LED_OFF( SMBF_READY_LED );         // READY LED
            RELAY_ON( SMBF_FAULT_RELAY );      // FAULT RELAY
            RELAY_ON( SMBF_BYPASS_RELAY );     // BYPASS RELAY
            LNA_OFF;                           // LNA

            start_time = clock();
            ImSp = 0L;
            MotorOn( TRUE );
            SmCurrentPhase = 1;
           }
           break;

          case 1 :     // --- get to idle power
           {
            t1 = clock();              // calculate the elapsed time
            t2 = t1 - start_time;      // then ...
            if( t2 > CLOCKS_PER_SEC )  //  every second until we reach the
             {                         //  idle power
              start_time = t1;

              if( ImSp < ImLoLimit )
               ImSp += POWER_INCR;
              else if( ImSp >= ImLoLimit )
               SmCurrentPhase = 2;
             }
           }
           break;

          case 2 :     // --- wait here until we're within range (or fail)
           {
            if( Tcsw > TcswHiTemp && Tcsw < TcswLoTemp )   // Tcsw == OK
             {
              SmErrorBitFlag &= ~SM_ERROR_TCSW_RANGE;
              if( !(SmStatusBitFlag & SMBF_MODE) )
               SmCurrentState = SM_COOLDOWN;
             }
           }
           break;

          default :    // --- Something went wrong so start over
           {
            SmCurrentPhase = 0;
           }
           break;

         } // SM_IDLE : switch( SmCurrentPhase )
       }
       break;

       // ----------------------------------------------------------------------
       // SM_COOLDOWN (2)  : Calculates the target cooldown setpoint end
       //                    temperature based on Tamb and Tcsw and applies
       //                    drive to tne motor based on the calculation. Once
       //                    Tcsn > TcSp control is passed to the PID
       //                    (i.e., SM_CONTROL) state.
       // ----------------------------------------------------------------------
      case SM_COOLDOWN :
       {
        switch( SmCurrentPhase )
         {
          case 0 :     // --- start the timer, initialize the state variables
           {
            LED_TOGGLE( SMBF_FAULT_LED );      // FAULT LED
            LED_TOGGLE( SMBF_READY_LED );      // READY LED
            RELAY_ON( SMBF_FAULT_RELAY );      // FAULT RELAY
            RELAY_ON( SMBF_BYPASS_RELAY );     // BYPASS RELAY
            LNA_OFF;                           // LNA

            TcUk0 = 0;
            TcUk0 = 0;                         // initialize the PID variables
            TcUk1 = 0;
            TcEk0 = 0;
            TcEk1 = 0;
            TcLastI = 0;
            start_time = 0L;                   // use start_time as a counter in this state

            SmCurrentPhase = 1;
           }
           break;

          case 1 :     // --- calculate the slope and intercept, once
           {
#if defined( TOWER_MOUNT_CODE )
    // slope and intercept based on 90W max drive
            // 48V cooler: Im = 0.20979*Tamb - 52.86047
            t1 = Tamb * 13748;             // U(16, 0) * U( 0,16) = U(16,16)
            t1 -= 3464364;                 // U(16,16) + U(16,16) = U(16,16)
            //            : m = (Im-ImLoLimit)/735
            t2 = (long)t1 - ImLoLimit;     // U(16,16) - U(16,16)
            t2 >>= 16;                     // U(16, 0)

            ImSpCoolDown_m = (long)t2 * 0x00000059;  // U(16, 0) * U( 0,16) = U(16,16)
                                           // but this will always be < 1
            //            : b = ImLoLimit - m * 230 (230 = 300K)
            t1 = ImSpCoolDown_m * 0x00E6;  // U( 0,16) * U(16, 0) = U(16,16)
            ImSpCoolDown_b = ImLoLimit - (long)t1;   // U(16,16) - U(16,16) = U(16,16)

//    // slope and intercept based on 75W max drive
//            // 48V cooler: Im = 0.105*Tamb + 3.566
//            t1 = Tamb * 0x1AE1;            // U(16, 0) * U( 0,16) = U(16,16)
//            t1 += 0x000390E5;              // U(16,16) + U(16,16) = U(16,16)
//            //            : m = (Im-ImLoLimit)/735
//            t2 = (long)t1 - ImLoLimit;     // U(16,16) - U(16,16)
//            t2 >>= 16;                     // U(16, 0)
//
//            ImSpCoolDown_m = (long)t2 * 0x00000059;  // U(16, 0) * U( 0,16) = U(16,16)
//                                           // but this will always be < 1
//            //            : b = ImLoLimit - m * 230 (230 = 300K)
//            t1 = ImSpCoolDown_m * 0x00E6;  // U( 0,16) * U(16, 0) = U(16,16)
//            ImSpCoolDown_b = ImLoLimit - (long)t1;   // U(16,16) - U(16,16) = U(16,16)
#else
//            // 12V cooler: Im = 0.307692 * Tamb + 1.461539
//            t1 = Tamb * 0x4EC4;            // U(16, 0) * U( 0,16) = U(16,16)
//            t1 += 0x00017627;              // U(16,16) + U(16,16) = U(16,16)
//            //            : m = (Im-44)/735
//            t2 = (long)t1 - 0x002C0000;    // U(16,16) - U(16,16)
//            t2 >>= 16;                     // U(16, 0)
//
//            ImSpCoolDown_m = (long)t2 * 0x00000059;  // U(16, 0) * U( 0,16) = U(16,16)
//                                           // but this will always be < 1
//            //            : b = 44 - m * 230
//            t1 = ImSpCoolDown_m * 0x00E6;  // U( 0,16) * U(16, 0) = U(16,16)
//            ImSpCoolDown_b = 0x002C0000 - (long)t1;  // U(16,16) - U916,16) = U(16,16)
#endif

            SmCurrentPhase = 2;
           }
           break;

          case 2 :         // --- approach the cooldown current
           {
            lCdSp = CoolDownSp();              // calc the cooldown sp
            lPidSp = PidSp();                  // and the pid setpoint
            if( (Tcsn < TcSp) && (ImSp <= lCdSp) )
             ImSp += 0x00000456;               // ~3App/min
            else
             SmCurrentPhase = 3;
           }
           break;

          case 3 :         // --- maintain cooldown drive until 78K
           {
            lCdSp = CoolDownSp();              // calc the cooldown sp
            lPidSp = PidSp();                  // and the pid setpoint

            if( (Tcsn < TcSp) && (lCdSp < lPidSp) )
             ImSp = lCdSp;                     // keep tracking the cool down sp
            else                               // impiles Tcsn > TcSp, coolder
             SmCurrentPhase = 4;               // than we need to be
           }                                   // so shift control to the PID code
           break; // --- case 3

          case 4 :     // --- transition to SM_CONTROL in automatic mode
           {
            ImSp = lPidSp;
            if( !(SmStatusBitFlag & SMBF_MODE) )
             SmCurrentState = SM_CONTROL;
            else
              SmCurrentPhase = 4;
           }
           break;

          default :    // --- Something went wrong so start over
           {
            SmCurrentPhase = 0;
           }
           break;
         } // SM_COOLDOWN : switch( SmCurrentPhase )

           // --- error checking -----------------------------------------------
#if !defined( DB_EMU )
        if( Tcsw < TcswHiTemp || Tcsw > TcswLoTemp )   // Tcsw != OK
         {
          SmErrorBitFlag |= SM_ERROR_TCSW_RANGE;
          SmCurrentState = SM_IDLE;
         }
#endif
       }
       break;

       // ----------------------------------------------------------------------
       // SM_CONTROL (3)  : Applies drive to the motor based on TcSp and Tcsn
       //                   using closed-loop PID control
       // ----------------------------------------------------------------------
      case SM_CONTROL :
       {
        int    tmp;

        switch( SmCurrentPhase )
         {
          case 0 :     // --- start the timer, initialize IO
           {
            LED_OFF( SMBF_FAULT_LED );         // FAULT LED
            LED_ON( SMBF_READY_LED );          // READY LED
            RELAY_OFF( SMBF_FAULT_RELAY );     // FAULT RELAY
            RELAY_OFF( SMBF_BYPASS_RELAY );    // BYPASS RELAY
            LNA_ON;                            // LNA
            ImSp = PidSp();
            start_time = clock();
            t3 = CLOCKS_PER_SEC;
            t3 *= 300L;          // 5 min delay
            SmCurrentPhase = 1;
           }
           break;

          case 1 :     // --- wait to turn on the Tscn filter
           {
            ImSp = PidSp();
            t1 = clock();
            t2 = t1 - start_time;
            if( t2 > t3 )
             SmCurrentPhase = 2;
           }
           break;

          case 2 :     // --- engage the Tscn filter and run forever
           {
            ImSp = PidSp();
            SmStatusBitFlag |= SMBF_TCSN_FILTER;
            SmCurrentPhase = 3;
           }
           break;

          case 3 :     // --- loop here forever
           {
            ImSp = PidSp();

               // error checking for ABS(TcSp-Tcsn) > someLimit
            tmp = ( TcEk0 < 0 ) ? -TcEk0 : TcEk0;
            if( tmp > 200 )
             {
              RELAY_OFF( SMBF_BYPASS_RELAY );
              SmErrorBitFlag |= SM_ERROR_TCSP_RANGE;
             }
            else
             {
              RELAY_ON( SMBF_BYPASS_RELAY );
              SmErrorBitFlag &= ~SM_ERROR_TCSP_RANGE;
             }

            SmCurrentPhase = 3;
           }
           break;

          default :    // --- Something went wrong so start over
           {
            SmCurrentPhase = 0;
           }
           break;
         } // SM_CONTROL : switch( SmCurrentPhase )
           // --- error checking -----------------------------------------------
#if !defined( DB_EMU )
        if( Tcsw < TcswHiTemp || Tcsw > TcswLoTemp )   // Tcsw != OK
         {
          SmErrorBitFlag |= SM_ERROR_TCSW_RANGE;
          SmCurrentState = SM_IDLE;
         }

        if( Ilna < IlnaLoCurrent || Ilna > IlnaHiCurrent ) // Ilna != OK
         {
          SmErrorBitFlag |= SM_ERROR_ILNA_RANGE;
         }
        else
         {
          SmErrorBitFlag &= ~SM_ERROR_ILNA_RANGE;
         }
#endif
       }
       break;

       // ----------------------------------------------------------------------
       // SM_POWERDOWN (4)  : At whatever drive level we're at, throttle down
       //                     to zero in preparation to enter the SM_FINAL
       //                     state
       // ----------------------------------------------------------------------
      case SM_POWERDOWN :
       {
        switch( SmCurrentPhase )
         {
          case 0 :     // --- start the timer
           {
            LED_ON( SMBF_FAULT_LED );          // FAULT LED
            LED_OFF( SMBF_READY_LED );         // READY LED
            RELAY_ON( SMBF_FAULT_RELAY );      // FAULT RELAY
            RELAY_ON( SMBF_BYPASS_RELAY );     // BYPASS RELAY
            LNA_OFF;                           // LNA

            start_time = clock();
            t3 = CLOCKS_PER_SEC * 15;
            SmCurrentPhase = 1;
           }
           break;

          case 1 :         // --- ramp ImSp to 0.0
           {
            t1 = clock();                      // calculate the elapsed time
            t2 = t1 - start_time;              // then ...
            if( (t2/(CLOCKS_PER_SEC>>4)) > 0 ) // decrement the power setpoint
             {                                 // until we reach 0
              start_time = clock();
              if( ImSp > POWER_INCR )
               ImSp -= POWER_INCR;
              else
               {
                ImSp = 0L;                     // we're done so drop to error
                MotorOn( FALSE );              // after turning the motor off
                SmCurrentPhase = 2;            // and wait
               }
             }
           }
           break;

          case 2 :     // --- transition to SM_FINAL in any mode
           {
            SmCurrentState = SM_FINAL;
           }
           break;

          default :    // --- Something went wrong so start over
           {
            SmCurrentPhase = 0;
           }
           break;
         } // SM_POWERDOWN : switch( SmCurrentPhase )
       }
       break;

       // --------------------------------------------------------------------
       // SM_FINAL (5) : This amounts to an off state, either by choice
       //                (i.e. entering manual mode) or because of a system
       //                error. System errors are checked here and if they
       //                (Trej, Vin) resolve themselves the system starts
       //                over.
       // --------------------------------------------------------------------

      case SM_FINAL :
       {
        switch( SmCurrentPhase )
         {
          default :
          case 0 :     // --- shut down
           {
            LED_ON( SMBF_FAULT_LED );          // FAULT LED
            LED_OFF( SMBF_READY_LED );         // READY LED
            RELAY_ON( SMBF_FAULT_RELAY );      // FAULT RELAY
            RELAY_ON( SMBF_BYPASS_RELAY );     // BYPASS RELAY
            LNA_OFF;                           // LNA

            SmCurrentPhase = 1;
           }
           break;

           // ----------------------------------------------------------------
           //  We might be here because of a hard error (Trej, Vin).
           //  If so we need to see if it fixed itself and resume normal
           //  operation.
           // ----------------------------------------------------------------

          case 1 :
           {
            if( SmErrorBitFlag & SM_ERROR_TREJ_RANGE )     // motor temp was
             {                                             // too hot. check
              if( Trej > TrejLoTemp )                      // to see if we've
               {                                           // cooled enough to
                SmErrorBitFlag &= ~SM_ERROR_TREJ_RANGE;    // restart and do
                SmCurrentState = SM_INIT;                  // so if we have.
               }
             } // Trej check

            if( SmErrorBitFlag & SM_ERROR_VIN_RANGE )
             {
              if( Vin > VinLoVolts && Vin < VinHiVolts )
               {
                SmErrorBitFlag &= ~SM_ERROR_VIN_RANGE;
                SmCurrentState = SM_INIT;
               }
             } // Vin check
            else
             SmCurrentPhase = 1;       // keep in this state
           }
           break;
         } // SM_FINAL : switch( SmCurrentPhase )
       }
       break;

       // --------------------------------------------------------------------
       // If we get to the default state there is a problem so shut the
       // whole system down
       // --------------------------------------------------------------------

      default :
       {
        SmCurrentState = SM_POWERDOWN;
        SmCurrentPhase = 0;
       }
       break;
     } // switch( SmCurrentState )
   }
  else                     // --- initialization
   {
    SmCurrentState = SM_INIT;         // start in the init state
    SmLastState    = SM_FINAL;        // synchronize phase first time through
    SmCurrentPhase = 0;                // redundant
    tcb->state     = 0;                // setup run state
    tcb->delay     = 0;                // no delay, run 60 times/sec
    tcb->pends     = 0;                // no pends
    tcb->posts     = 0;                // and no posts
   } // else-if( ...
 } // StateMachine

// ---------------------------------------------------------------------------
//      function : SciInputReady
//          task : SCI_INPUT_READY
//      pends on : SCI_RX_DATA_READY
//         posts : nothing
//     arguments : pTCB - pointer to TCB for this task
//       returns : nothing
//      synopsis : If input is ready (i.e. a CR was found) copy the input
//                 to a temporary buffer and parse it to see what the user
//                 wants.
// ---------------------------------------------------------------------------
void SciInputReady( pTCB tcb )
 {
  int          i, j, retval;
  char         sbuf[ BUF16 ];
  char         command, operator;
  int          index;
  long         argument;

  if( tcb->state == 0 )    // --- task in run state
   {
    retval = 0;
    i = SciRxHead;
    j = 0;
    while( i != SciRxTail )            // copy the input data to the output
     {                                 // buffer. This makes it easier to
      sbuf[ j++ ] = SciRxBuf[ i ];     // examine the data without having
      i = (++SciRxHead) % BUF16;       // to wory about wrap-around problems
      SciRxHead = i;
     }

    retval = parse( sbuf, &command, &index, &operator, &argument );
    if( retval != -1 )
     {
      if( command == 'S' )             // SET command
       retval = SetCommand( index, operator, argument );
      else if( command == 'I' )        // INQUIRE command
       retval = InquireCommand( index, operator, argument );
      else if( command == CR )         // possible carriage return
       retval = 0;
      else                             // otherwise,
       retval = -1;                    // indicates problem with command
     }

#if !defined( TOWER_MOUNT_CODE  )
    if( retval == 0 )                  // indicates no data copied to SciTxBuf
     BlockMove( &csACK, SciTxBuf );    // so just send ACK
    else if( retval == -1 )            // else if the scan or command failed
     BlockMove( &csNAK, SciTxBuf );    // send NAK
#endif
                                       // else the command handler copied data into
                                       // SciTxBuf
    if( retval > 0 )
     {
      gPosts |= SCI_TX_DATA_READY;     // post the SCI_TX_DATA_READY event
     }
    gPosts &= ~SCI_RX_DATA_READY;      // clear SCI_RX_DATA_READY event


   } // if( 'in run state'
  else                     // --- initialization
   {
    SciRxHead   = 0;                   // reset the head and tail pointers
    SciRxTail   = 0;                   // for the SCI receive buffer
    tcb->state  = 0;                   // and increment the state variable
    tcb->delay  = 0;                   // no delay, we wait on events
    tcb->pends |= SCI_RX_DATA_READY;   // pend on data in the receive buffer
    tcb->posts  = 0;
   }

 } // SciInputReady

// ---------------------------------------------------------------------------
//      function : SciOutputReady
//          task : SCI_OUTPUT_READY
//      pends on : SCI_TX_DATA_READY
//         posts : nothing
//     arguments : pTCB - pointer to TCB for this task
//       returns : nothing
//      synopsis : Expects a NULL terminated string in SciTxBuf. This task
//                 will wait until the SCI_TX_DATA_READY event is signaled
//                 and then send the first character of the SciTxBuf[] letting
//                 the interrupt handler do the rest.
// ---------------------------------------------------------------------------
void SciOutputReady( pTCB tcb )
 {
  unsigned     cnt, tmp;

  if( tcb->state == 0 )    // --- task in run state
   {
       // --- test to see if we're finished with the serial output
    if( gPosts & SCI_TX_BUSY )         // and if we are then reset
     {                                 // the busy event flag
      if( (SciTxBuf[SciTxIndex] == 0) || (SciTxIndex > BUF32) )
       {
        gPosts &= ~SCI_TX_BUSY;
#if defined( TOWER_MOUNT_CODE )
        tmp = DIO->PBDATDIR;
        tmp &= ~TDX_OK;
        DIO->PBDATDIR = tmp;
#endif
       }
     }
       // --- else we might have data ready to send so...
    else if( gPosts & SCI_TX_DATA_READY )
     {
#if defined( TOWER_MOUNT_CODE )
       // --- this code sets the RS232 amplifier enable and generates
       //     a 300 us delay before it begins the transmit process.
      tmp = DIO->PBDATDIR;
      tmp |= TDX_OK;
      DIO->PBDATDIR = tmp;
      for( cnt=0 ; cnt<600 ; cnt++ ); // ~300 us delay
       // --- this code appends 2 space characters to the tx string
      tmp = 0;
      while( SciTxBuf[tmp] != 0 )
        tmp++;
      SciTxBuf[ tmp++ ] = ' ';
      SciTxBuf[ tmp++ ] = ' ';
      SciTxBuf[ tmp   ] = 0;
       // --- this code prepends 2 space characters to the tx string
      SciTxIndex = tmp + 2;
      while( (signed)tmp >= 0 )
        SciTxBuf[ SciTxIndex-- ] = SciTxBuf[ tmp-- ];
      while( SciTxIndex >= 0 )
            SciTxBuf[ SciTxIndex-- ] = ' ';
#endif
      gPosts &= ~SCI_TX_DATA_READY;    // clear the event that started the xmit
      gPosts |= SCI_TX_BUSY;           // but set the busy event flag
      SciTxIndex = 0;                  // and start the serial xmit
      SCI->SCITXBUF = SciTxBuf[ SciTxIndex ];
     }
       // --- we must be confused, just reset all events and start over
    else
     {
      gPosts &= ~SCI_TX_DATA_READY;
      gPosts &= ~SCI_TX_BUSY;
     }
   }
  else                     // --- initialization
   {
    tcb->state  = 0;
    tcb->delay  = 0;
    tcb->pends |= SCI_TX_DATA_READY;   // run when data ready to send
    tcb->pends |= SCI_TX_BUSY;         // and run when sending data
    tcb->posts  = 0;
   }
 } // SciOutputReady

// ---------------------------------------------------------------------------
//      function : OperationMonitor
//          task : OPERATION_INDICATOR
//      pends on : nothing
//         posts : nothing
//     arguments : pTCB - pointer to TCB for this task
//       returns : nothing
//      synopsis : Task is responsible for turning the LED's on or off
//                 bit accessable hardware (fault, bypass relays)
//                 incrementing the run time accumulator
// ---------------------------------------------------------------------------
void OperationMonitor( pTCB tcb )
 {
  int          state = tcb->state;
  unsigned     tmp;

   // If there's a new error, log the event
  if( SmErrorBitFlag ^ LastSmErrorBitFlag )
   logEvent();
  LastSmErrorBitFlag = SmErrorBitFlag;

  switch( state )
   {
    case 0 :                   // --- LED's on
     {
      tmp  = DIO->PADATDIR;
      tmp &= ~LED_MASK;
      tmp |= (SmStatusBitFlag & LED_MASK);
      DIO->PADATDIR = tmp;
     }
     break;

    case 1 :                   // --- LED's off, increment run time accumulator
     {
      tmp  = DIO->PADATDIR;
      tmp ^= ((SmStatusBitFlag>>SHIFT_TO_TOGGLE) & LED_MASK);
      DIO->PADATDIR = tmp;
      RunTimeAcc++;
     }
     break;

    default :
     {
      tcb->state = 0;
      tcb->delay = 0;
      tcb->pends = 0;
      tcb->posts = 0;
      LED_TOGGLE( SMBF_ALIVE_LED );
      DIO->PADATDIR |= LED3;           // turn the LED on
     }
   } // switch( ...

   // SPI test - debug only

   // update the other IO ports
  tmp  = DIO->PDDATDIR;
  tmp &= ~RELAY_MASK;
  tmp |= ((SmStatusBitFlag>>SHIFT_TO_RELAY) & RELAY_MASK);
  DIO->PDDATDIR = tmp;

    // setup for the next trip through
  tcb->delay = CLOCKS_PER_SEC >> 1;    // reset delay for task
  tcb->state = (++state % 2);
 } // OperationMonitor

// ---------------------------------------------------------------------------
//      function : SysDataOut
//          task : SYSDATAOUT
//      pends on : SYS_DATA_OUT
//         posts : nothing
//     arguments : pTCB - pointer to TCB for this task
//       returns : nothing
//      synopsis :
// ---------------------------------------------------------------------------
void SysDataOut( pTCB tcb )
 {

  switch( tcb->state )
   {
    case 0 :   // --- not sending data out, is it requested
     {
      if( gPosts & SYS_DATA_OUT )      // check to see if we're tunring on
       {
        tcb->pends &= ~SYS_DATA_OUT;   // quit pending, run on delay
        gPosts     &= ~SYS_DATA_OUT;   // clear the event
        tcb->state = 1;                // run the data out state
        tcb->delay = CLOCKS_PER_SEC;   // initialize delay for task
       }
     }
     break;

    case 1 :   // --- sending data out
     {
      if( gPosts & SYS_DATA_OUT )      // check to see if if we're turning off
       {
        tcb->pends |= SYS_DATA_OUT;    // go back to pending on the event
        gPosts     &= ~SYS_DATA_OUT;   // clear the event
        tcb->state = 0;
       }
      else                             // else send the data out the pipe
       {
        SystemDataOut();
        tcb->delay = CLOCKS_PER_SEC;   // reset delay for task
       }
     }
     break;

    default :  // --- initialization or screw-up
     {
      tcb->state = 0;
      tcb->delay = 0;
      tcb->pends |= SYS_DATA_OUT;
      tcb->posts = 0;
     }
   } // switch( state )
 } // SysDataOut

/****************************************************************************
 * Helper functions
 *  InitTasksModule    - Initializes all the module global variables
 *  SetCommand         - Handles SET commands from the user
 *  InquireCommand     - Handles INQUIRE commands from the user
 *  MotorOn            - enables the PWM outputs
 *  CoolDownSp         - calculates the cool down profile setpoint
 *  PidSp              - calculates the cool down profile setpoint
 *  ImServo            - servos the motor current
 *  iSqrt              - called by MeasMotorCurrent task

****************************************************************************/

// ---------------------------------------------------------------------------
//      function : InitTasksModule
//     arguments : none
//       returns : nothing
//      synopsis : Initializes all variables associated with this module
// ---------------------------------------------------------------------------
void InitTasksModule( void )
 {
   // initialize global variables
  NvAddress        = 0;
  RunTimeAcc       = 0L;

   // initialize state machine variables
  SmCurrentState   = 0;
  SmLastState      = 0;
  SmCurrentPhase   = 0;
  SmStatusBitFlag  = 0;
  SmErrorBitFlag   = 0;
  LastSmErrorBitFlag = 0;

   // initialize motor current variables
  ImOut            = 0L;
  ImSp             = 0L;
  ImEk0            = 0L;
  ImEk1            = 0L;
  ImUk0            = 0L;
  ImUk1            = 0L;
  ImSpCoolDown_m   = 0L;
  ImSpCoolDown_b   = 0L;
  lCdSp            = 0L;
  lPidSp           = 0L;
   // initialize temperature variables
  Trej             = 0;
  Tamb             = 0;
  Vlna             = 0;
  Ilna             = 0;
  Vin              = 0;
  Tcsw             = 0;
  Tcsn             = 0;
  for( TcsnDataIndex=TCSN_DATA_SIZE ; TcsnDataIndex ;  )
   TcsnData[--TcsnDataIndex] = 0;

   // initialize control variables
  TcUk0            = 0L;
  TcUk1            = 0L;
  TcLimI           = 0L;
  TcLastI          = 0L;
  TcKp             = 0;
  TcKi             = 0;
  TcKd             = 0;
  TcSp             = 0;
  TcEk0            = 0;
  TcEk1            = 0;
  TcLastTcsn       = 0;
  TcLastD          = 0;

   // load the run-time constants
  LoadRtConstants();
 } // InitTasksModule

// ---------------------------------------------------------------------------
//      function : SetCommand
//     arguments :    index - S number (i.e. index = 23 for S23...)
//                 operator - either '=' or '?'
//                 argument - positive integer
//       returns : -1 on error, otherwise number of characters written to
//                 SciTxBuf
//      synopsis : Handles SET commands from the user (see SciInputReady)
//                 Returns the number of characters copied to the SciTxBuf
//                 but it's up to the caller to actually post the event.
// ---------------------------------------------------------------------------
static int SetCommand( int index, char operator, long argument )
 {
  int      tmp, retval;
  char     tbuf[ BUF16 ];

   // initialize the local variables
  retval = 0;

   // select the command
  switch( index )
   {
    case  0 :          // ----- (S0) set|inquire proportional gain -----------
     {
      if( operator == '=' )            // set operation
       TcKp = (int)( argument & 0x00007FFF );
      else                             // inquiry operation
       retval = LongToAscii( (long)TcKp, SciTxBuf );
     }
     break;

    case  1 :          // ----- (S1) set|inquire integral gain ---------------
     {
      if( operator == '=' )            // set operation
       TcKi = (int)( argument & 0x00007FFF );
      else                             // inquiry operation
       retval = LongToAscii( (long)TcKi, SciTxBuf );
     }
     break;

    case  2 :          // ----- (S2) set|inquire integrator saturation limit -
     {
      if( operator == '=' )            // set operation
       TcLimI = (long)( argument & 0x7FFFFFFF );
      else                             // inquiry operation
       retval = LongToAscii( (long)TcLimI, SciTxBuf );
     }
     break;

    case  3 :          // ----- (S3) set|inquire derivative gain -------------
     {
      if( operator == '=' )            // set operation
       TcKd = (int)( argument & 0x00007FFF );
      else                             // inquiry operation
       retval = LongToAscii( (long)TcKd, SciTxBuf );
     }
     break;

    case  4 :          // ----- (S4) set|inquire temperature setpoint --------
     {
      if( operator == '=' )            // set operation
       TcSp = (int)( argument & 0x000003FF );
      else                             // inquiry operation
       retval = LongToAscii( (long)TcSp, SciTxBuf );
     }
     break;

    case  5 :          // ----- (S5) enable|disable sending debug string -----
     {
      if( operator == '=' )            // set operation
       {
        tmp = 0;
        if( argument == 1 )
         tmp = SMBF_DEBUG;
        if( tmp ^ (SmStatusBitFlag&SMBF_DEBUG) )
         {
          gPosts |= SYS_DATA_OUT;      // set the event, this toggles the task
          SmStatusBitFlag ^= SMBF_DEBUG;   // update the state machine flag
         }
       }
      else                             // inquiry operation
       retval = LongToAscii( (long)((SmStatusBitFlag & SMBF_DEBUG)?1:0), SciTxBuf );
     }
     break;

    case  6 :         // ----- (S6) enable|disable state transition mode -----
     {
      if( operator == '=' )            // set operation
       {
        if( argument == 0 )            // set to automatic mode
         SmStatusBitFlag &= ~SMBF_MODE;
        else
         SmStatusBitFlag |= SMBF_MODE; // set to manual mode
       }
      else                             // inquiry operation
       retval = LongToAscii( (long)((SmStatusBitFlag & SMBF_MODE)?1:0), SciTxBuf );
     }
     break;

    case  7 :         // ----- (S7) set|inquire ImSp
     {
      if( operator == '=' )            // set operation
       {
        if( (SmStatusBitFlag & SMBF_MODE) )
         ImSp = ( argument & 0x000000FF ) << 16;
       }
      else                             // inquiry operation
       retval = LongToAscii( (long)ImSp, SciTxBuf );
     }
     break;

    case  8 :         // ----- (S8) set|inquire SmCurrentState.SmCurrentPhase
     {
      if( operator == '=' )            // set operation
       {
        if( SmStatusBitFlag & SMBF_MODE )    // must be in manual mode
         {
          if( !((argument < 0) || (argument > 5)) )
           SmCurrentState = (int)argument;
         }
       }
      else                             // inquiry operation
       {
        retval = 0;
        SciTxBuf[ retval++ ] = SmCurrentState + '0';
        SciTxBuf[ retval++ ] = '.';
        SciTxBuf[ retval++ ] = SmCurrentPhase + '0';
        SciTxBuf[ retval++ ] = 0;
       }
     }
     break;

    case  9 :         // ----- (S9) set|inquire LNA shut down bit
     {
      if( operator == '=' )            // set operation
       {
        if( argument == 0 )
         LNA_OFF;
        else
         LNA_ON;
       }
      else                             // inquiry operation
       retval = LongToAscii( (long)((SmStatusBitFlag & SMBF_LNA_CTRL)?1:0), SciTxBuf );
     }
     break;

    case 10 :         // ----- (S10) set|inquire FAULT relay setting
     {
      if( operator == '=' )            // set operation
       {
        if( argument == 0 )
         RELAY_ON( SMBF_FAULT_RELAY );
        else
         RELAY_OFF( SMBF_FAULT_RELAY );
       }
      else                             // inquiry operation
       retval = LongToAscii( (long)((SmStatusBitFlag & SMBF_FAULT_RELAY)?1:0), SciTxBuf );
     }
     break;

    case 11 :         // ----- (S11) set|inquire BYPASS relay setting
     {
      if( operator == '=' )            // set operation
       {
        if( argument == 0 )
         RELAY_ON( SMBF_BYPASS_RELAY );
        else
         RELAY_OFF( SMBF_BYPASS_RELAY );
       }
      else                             // inquiry operation
       retval = LongToAscii( (long)((SmStatusBitFlag & SMBF_BYPASS_RELAY)?1:0), SciTxBuf );
     }
     break;

    case 12 :         // ----- (S12) set|inquire NvAddress
     {
      if( operator == '=' )            // set operation
       {
        NvAddress = (int)(argument & 0x000007FF);
       }
      else                             // inquiry operation
       {
        retval = LongToAscii( (long)NvAddress, SciTxBuf );
       }
     }
     break;

    case 13 :         // ----- (S13) set|inquire EEPROM word
     {
      if( operator == '=' )            // set operation
       {
        EEPROM_Write( NvAddress, (argument & 0x000000FF), 1 );
       }
      else                             // inquiry operation
       {
        int i = 0;
        retval = LongToAscii( (long)NvAddress, SciTxBuf );
        SciTxBuf[ --retval ] = ':';
        tmp = (int)EEPROM_Read( NvAddress, 1 );
        LongToAscii( (long)tmp, tbuf );
        while( tbuf[i] != 0 )
         SciTxBuf[ ++retval ] = tbuf[ i++ ];
        SciTxBuf[ ++retval ] = 0;
        retval++;
       }
     }
     break;

    default :          // unhandled command
     retval = -1;
     break;
   } // switch( index )

   // terminate any data that was copied to SciTxBuf
  if( retval > 0 )
   {
    SciTxBuf[ --retval ] = '\r';       // overwrite the NULL
    SciTxBuf[ ++retval ] = 0;          // then add one back
   }

  return retval;
 } // SetCommand

// ---------------------------------------------------------------------------
//      function : InquireCommand
//     arguments :    index - I number (i.e. index = 23 for I23...)
//                 operator - either '=' or '?'
//                 argument - positive integer
//       returns : -1 on error, otherwise number of characters written to
//                 SciTxBuf
//      synopsis : Handles INQUIRE commands from the user (see SciInputReady).
//                 Returns the number of characters copied to the SciTxBuf
//                 but it's up to the caller to actually post the event.
// ---------------------------------------------------------------------------
static int InquireCommand( int index, char operator, long argument )
 {
  int      retval;
  char     tbuf[ BUF16 ];

   // initialize the local variables
  retval = 0;

   // select the command
  switch( index )
   {
    case  0 :          // ----- (I0) Trej, motor heat reject temperature -----
     {
      retval = LongToAscii( (long)Trej, SciTxBuf );
     }
     break;
    case  1 :          // ----- (I1) Tamb, ambient temperature ---------------
     {
      retval = LongToAscii( (long)Tamb, SciTxBuf );
     }
     break;
    case  2 :          // ----- (I2) Vlna, LNA power supply voltage ----------
     {
      retval = LongToAscii( (long)Vlna, SciTxBuf );
     }
     break;
    case  3 :          // ----- (I3) Ilna, LNA power supply current ----------
     {
      retval = LongToAscii( (long)Ilna, SciTxBuf );
     }
     break;
    case  4 :          // ----- (I4) ImOut, RMS motor current estimate -------
     {
      retval = LongToAscii( (long)ImOut, SciTxBuf );
     }
     break;
    case  5 :          // ----- (I5) Vin, motor driver input voltage ---------
     {
      retval = LongToAscii( (long)Vin, SciTxBuf );
     }
     break;
    case  6 :          // ----- (I6) Tcsw, wide range temp sensor ------------
     {
      retval = LongToAscii( (long)Tcsw, SciTxBuf );
     }
     break;
    case  7 :          // ----- (I7) Tcsn, narrow range temp sensor ----------
     {
      retval = LongToAscii( (long)Tcsn, SciTxBuf );
     }
     break;
    case  8 :          // ----- (I8) software version ------------------------
     {
      BlockMove( &csVersion, SciTxBuf );   // copy version string into SciTxBuf
      while( SciTxBuf[retval++] != CR );  // use retval to count to the CR
     }
     break;
    case  9 :          // ----- (I9) error querry ----------------------------
     {
      retval = LongToAscii( (long)SmErrorBitFlag, SciTxBuf );
     }
     break;
    case 10 :          // ----- (I10) display run time accumulator -----------
     {
      retval = LongToAscii( RunTimeAcc, SciTxBuf );
     }
     break;
   } // switch( index )

   // terminate any data that was copied to SciTxBuf
  if( retval > 0 )
   {
    SciTxBuf[ --retval ] = '\r';       // overwrite the NULL
    SciTxBuf[ ++retval ] = 0;          // then add one back
   }

  return retval;

 } // InquireCommand

// ---------------------------------------------------------------------------
//      function : MotorOn
//     arguments : TRUE = ON
//                 FALSE = OFF
//       returns : nothing
//      synopsis : Enables the PWM output ports
// ---------------------------------------------------------------------------
static void MotorOn( BOOL arg )
 {
  sGain = 0;
  if( arg == FALSE )
   {
    asm( " LDP     #0E8h" );
    asm( " SPLK    #000Fh, 07413h" );    // CMP1 forced hi , CMP2 forced hi
   }
  else
   {
    asm( " LDP     #0E8h" );
    asm( " SPLK    #0009h, 07413h" );    // CMP1 act lo, CMP2 act hi
   }
 } // MotorOn

// ---------------------------------------------------------------------------
//      function : CoolDown
//     arguments : none
//       returns : Calculated ImotBuf setpoint in U(16,16)
//      synopsis : Calculated ImotBuf setpoint based on Tcsw and Tamb
// ---------------------------------------------------------------------------
static long CoolDownSp( void )
 {
  long result = ImSpCoolDown_m * Tcsw + ImSpCoolDown_b;
  long t1 = (long)( MAX_IMOT << 16 );
  long delta;

   // check to see what Trej is and compensate for it (rem Trej xfer is inv)
  if( Trej < TrejLoTemp )
   {
    delta = TrejLoTemp - Trej;         // 16 bit number
    delta *= 0x00010000;               // now 32 bit number
    delta &= 0x7FFFFFFF;               // make sure it pos & < 128.0
    result -= delta;
   }

   // bracket the allowable limits
  if( result >= ImLoLimit && result <= t1 )
   return result;
  else if( result > t1 )
   return t1;
  else
   return ImLoLimit;

//  return (result>ImLoLimit) ? result : ImLoLimit;
 } // CoolDown

// ---------------------------------------------------------------------------
//      function : PidSP
//     arguments : none
//       returns : Calculated ImotBuf setpoint in U(16,16)
//      synopsis : Calculated ImotBuf setpoint based on Tcsn and ImSp
// ---------------------------------------------------------------------------
static long PidSp( void )
 {
  long         pt, it, dt;
  long         t1;

  TcEk0 = TcSp - Tcsn;            // calc the error

     // proportional term, A(15,0)*A(15,0) = A(31,0)
  pt = (long)( TcKp * TcEk0 );

     // integral term, A(15,0)*A(15,0) = A(31,0)
  it = (long)( TcKi * (( TcEk0 + TcEk1 ) >> 1 ) ) + TcLastI;
  if( it > TcLimI )                    // limit windup to +TcLimI on the upside
   it = TcLimI;
  else if( it < -TcLimI )              // and -TcLimI on the downside
   it = -TcLimI;
  TcLastI = it;                        // 'it' is bounded
  TcEk1 = TcEk0;

     // differentiator term, A(15,0)*A(15,0) = A(31,0)
  dt = (long)((TcLastD - TcKd * (Tcsn - TcLastTcsn)) >> 1 );
  TcLastD = dt;
  TcLastTcsn = Tcsn;

     // do the control
  TcUk0 = pt + it + dt;
  TcUk0 <<= 7;

  t1 = (long)( MAX_IMOT << 16 );
  if( TcUk0 < MIN_IMOT )               // do the error checking
   TcUk0 = 0;
  if( TcUk0 > t1 )                     // ~30App current
   TcUk0 = t1;

  return TcUk0;
 } // PidSp

// ---------------------------------------------------------------------------
//      function : ImServo
//     arguments : none
//       returns : nothing
//      synopsis : Routine responsible to 'close-the-loop' around the motor
//                 current setpoint and response.
//         notes : 0x000032E4 = 0.1988
//                 0x000001EB = 0.007503
//                 The compensator transfer function into the motor drive:
//                 u[k] = 0.1988*e[k] - 0.007503*e[k-1] + u[k-1]
// ---------------------------------------------------------------------------
static void ImServo( void )
 {
  ImEk0 = ImSp - ImOut;
  ImEk0 /= 256;
  ImUk0 = 0x000032E4 * ImEk0 - 0x000001EB * ImEk1;
  ImUk0 >>= 16;
  ImUk0 += ImUk1;

  if( ImUk0 < 0x00000000 )
   ImUk0 = ImUk1;
  else if( ImUk0 > 0x00007FFF )
   ImUk0 = ImUk1;

  ImUk1 = ImUk0;
  ImEk1 = ImEk0;

  sGain = ImUk0;
 } // ImServo

// ---------------------------------------------------------------------------
//      function : iSqrt - integer square root algorithm
//     arguments : x - number to take the square root of
//       returns : square root of x
//      synopsis : The algorithm is setup to return a 32-bit number in U(16,16)
//                 format.
// ---------------------------------------------------------------------------
static unsigned long iSqrt( unsigned long x )
 {
  int           i;
  unsigned long accumulator, trial, remainder;

  accumulator = 0l;
  trial = 0l;
  remainder = 0l;

  for( i=0 ; i<32 ; i++ )
   {
    remainder <<= 2;
    remainder = remainder + (x >> 30);
    x <<= 2;
    accumulator <<= 1;
    trial = (accumulator << 1) + 1;

    if( remainder >= trial )
     {
      remainder -= trial;
      accumulator++;
     } // if( remainder...
   } // for( i=0 ;...

  return accumulator;
 } // iSqrt

// ---------------------------------------------------------------------------
//      function : SystemDataOut
//     arguments : none
//       returns : nothing
//      synopsis : Outputs the debug info string:
//                     state.phase,Tcsw,Tcsn,ImSp,ImOut
// ---------------------------------------------------------------------------
static void SystemDataOut( void )
 {
  int      i, j;
  char     tbuf[ 16 ];

  j = 0;
  SciTxBuf[ j++ ] = SmCurrentState + '0';
  SciTxBuf[ j++ ] = '.';
  SciTxBuf[ j++ ] = SmCurrentPhase + '0';
  SciTxBuf[ j++ ] = ',';

   // add Tcsw
  LongToAscii( (long)Tcsw, tbuf );
  i = 0;
  while( tbuf[i] != 0 )
   SciTxBuf[ j++ ] = tbuf[ i++ ];
  SciTxBuf[ j++ ] = ',';

   // add Tcsn
  LongToAscii( (long)Tcsn, tbuf );
  i = 0;
  while( tbuf[i] != 0 )
   SciTxBuf[ j++ ] = tbuf[ i++ ];
  SciTxBuf[ j++ ] = ',';

   // add ImSp, integer part
  LongToAscii( (long)(ImSp>>16), tbuf );
  i = 0;
  while( tbuf[i] != 0 )
   SciTxBuf[ j++ ] = tbuf[ i++ ];
  SciTxBuf[ j++ ] = ',';

   // add ImOut, integer part
  LongToAscii( (long)(ImOut>>16), tbuf );
  i = 0;
  while( tbuf[i] != 0 )
   SciTxBuf[ j++ ] = tbuf[ i++ ];

//  // ------------------------------------------------------------------
//  // test code only!
//  // ------------------------------------------------------------------
//  SciTxBuf[ j++ ] = 'O';
//  SciTxBuf[ j++ ] = 'K';
//  // ------------------------------------------------------------------
//  // test code only!
//  // ------------------------------------------------------------------

  SciTxBuf[ j++ ] = '\r';
  SciTxBuf[ j++ ] = 0;
  gPosts |= SCI_TX_DATA_READY;
 } // SystemDataOut

// ---------------------------------------------------------------------------
//      function : LoadRtConstants
//     arguments : none
//       returns : nothing
//      synopsis : Loads all runtime constants from EEPROM (NV memory)
//                 IMPORTANT - ALL ERROR CHACKING HAS BEEN REMOVED!
// ---------------------------------------------------------------------------
static void LoadRtConstants( void )
 {
#if !defined( DB_ECHO )
  TcLimI       =      EEPROM_Read( NVADDR_KIL, 4 );
  TcKp         = (int)EEPROM_Read( NVADDR_KP, 2 );
  TcKi         = (int)EEPROM_Read( NVADDR_KI, 2 );
  TcKd         = (int)EEPROM_Read( NVADDR_KD, 2 );
  TcSp         = (int)EEPROM_Read( NVADDR_TSP, 2 );
  TrejLoTemp   = (int)EEPROM_Read( NVADDR_TREJ_LO, 2 );
  TrejHiTemp   = (int)EEPROM_Read( NVADDR_TREJ_HI, 2 );
  TambLoTemp   = (int)EEPROM_Read( NVADDR_TAMB_LO, 2 );
  TambHiTemp   = (int)EEPROM_Read( NVADDR_TAMB_HI, 2 );
  IlnaLoCurrent  = (int)EEPROM_Read( NVADDR_ILNA_LO, 2 );
  IlnaHiCurrent  = (int)EEPROM_Read( NVADDR_ILNA_HI, 2 );
  VinLoVolts   = (int)EEPROM_Read( NVADDR_VIN_LO, 2 );
  VinHiVolts   = (int)EEPROM_Read( NVADDR_VIN_HI, 2 );
  TcswLoTemp   = (int)EEPROM_Read( NVADDR_TCSW_LO, 2 );
  TcswHiTemp   = (int)EEPROM_Read( NVADDR_TCSW_HI, 2 );
  TcsnLoTemp   = (int)EEPROM_Read( NVADDR_TCSN_LO, 2 );
  TcsnHiTemp   = (int)EEPROM_Read( NVADDR_TCSN_HI, 2 );
  ImLoLimit    =      EEPROM_Read( NVADDR_IM_LO, 4 );
//ImHiLimit    =      EEPROM_Read( NVADDR_IM_HI, 4 );
#else
  TcLimI       =      EEPROM_Read( NVADDR_KIL, 4 );        echo( (long)TcLimI );
  TcKp         = (int)EEPROM_Read( NVADDR_KP, 2 );         echo( (long)TcKp );
  TcKi         = (int)EEPROM_Read( NVADDR_KI, 2 );         echo( (long)TcKi );
  TcKd         = (int)EEPROM_Read( NVADDR_KD, 2 );         echo( (long)TcKd );
  TcSp         = (int)EEPROM_Read( NVADDR_TSP, 2 );        echo( (long)TcSp );
  TrejLoTemp   = (int)EEPROM_Read( NVADDR_TREJ_LO, 2 );    echo( (long)TrejLoTemp );
  TrejHiTemp   = (int)EEPROM_Read( NVADDR_TREJ_HI, 2 );    echo( (long)TrejHiTemp );
  TambLoTemp   = (int)EEPROM_Read( NVADDR_TAMB_LO, 2 );    echo( (long)TambLoTemp );
  TambHiTemp   = (int)EEPROM_Read( NVADDR_TAMB_HI, 2 );    echo( (long)TambHiTemp );
  IlnaLoCurrent  = (int)EEPROM_Read( NVADDR_ILNA_LO, 2 );  echo( (long)IlnaLoCurrent );
  IlnaHiCurrent  = (int)EEPROM_Read( NVADDR_ILNA_HI, 2 );  echo( (long)IlnaHiCurrent );
  VinLoVolts   = (int)EEPROM_Read( NVADDR_VIN_LO, 2 );     echo( (long)VinLoVolts );
  VinHiVolts   = (int)EEPROM_Read( NVADDR_VIN_HI, 2 );     echo( (long)VinHiVolts );
  TcswLoTemp   = (int)EEPROM_Read( NVADDR_TCSW_LO, 2 );    echo( (long)TcswLoTemp );
  TcswHiTemp   = (int)EEPROM_Read( NVADDR_TCSW_HI, 2 );    echo( (long)TcswHiTemp );
  TcsnLoTemp   = (int)EEPROM_Read( NVADDR_TCSN_LO, 2 );    echo( (long)TcsnLoTemp );
  TcsnHiTemp   = (int)EEPROM_Read( NVADDR_TCSN_HI, 2 );    echo( (long)TcsnHiTemp );
  ImLoLimit    =      EEPROM_Read( NVADDR_IM_LO, 4 );      echo( (long)ImLoLimit );
//ImHiLimit    =      EEPROM_Read( NVADDR_IM_HI, 4 );      echo( (long)ImHiLimit );
#endif
 }

// ---------------------------------------------------------------------------
//      function : MedianFilter
//     arguments : data array to filter
//       returns : the median value from a sorted, odd length array
//      synopsis : Implements a non-linear median filter by sorting the
//                 argument array (using a bubble sort) and returning
//                 the median array member. The array should be odd length.
// ---------------------------------------------------------------------------
static int MedianFilter( int data[] )
 {
  int  exchange, tmp, pass, index;

  exchange = 1;
  for( pass=0 ; pass<TCSN_DATA_SIZE && exchange ; pass++ )
   {
    exchange = 0;
    for( index=0 ; index<(TCSN_DATA_SIZE-1-pass) ; index++ )
     {
      if( *(data+index) < *(data+index+1) )
       {
        exchange = 1;
        tmp = *(data+index);
        *(data+index) = *(data+index+1);
        *(data+index+1) = tmp;
       }
     }
   }

  return data[ TCSN_DATA_SIZE >> 1 ];
 }
// ---------------------------------------------------------------------------
//      function : logEvent
//     arguments : none
//       returns : nothing
//      synopsis : When an event (fault) is detected it is written to the
//                 EEPROM for later interrogation.
// ---------------------------------------------------------------------------
static void logEvent( void )
 {
 }

#if defined( DB_ECHO )
// ---------------------------------------------------------------------------
//      function : echo
//     arguments : arg - long
//       returns : nothing
//      synopsis : used to echo long arguments to the terminal before the
//                 state machine starts.
// ---------------------------------------------------------------------------
static void echo( long arg )
 {
  LongToAscii( arg, SciTxBuf );
  SciTxIndex = 0;
  while( SciTxBuf[SciTxIndex] != 0 )
   SciTxIndex++;
  SciTxBuf[SciTxIndex++] = '\r';
  SciTxBuf[SciTxIndex] = 0;
  myputs();
 }

// ---------------------------------------------------------------------------
//      function : myputs
//     arguments : none
//       returns : nothing
//      synopsis : Displays the contents of the SciTxBuf
// ---------------------------------------------------------------------------
static void myputs( void )
 {
  SciTxIndex = 0;
  SCI->SCITXBUF = SciTxBuf[ SciTxIndex ];
  while( SciTxBuf[SciTxIndex] != 0 );
 } // SignOn
#endif

// ---------------------------------------------------------------------------
//      function : SomeTask
//          task :
//      pends on :
//         posts :
//     arguments : pTCB - pointer to TCB for this task
//       returns : nothing
//      synopsis :
// ---------------------------------------------------------------------------
//void SomeTask( pTCB tcb )
// {
//  if( tcb->state == 0 )    // --- task in run state
//   {
//   }
//  else                     // --- initialization
//   {
//    tcb->state = 0;
//    tcb->delay = 0;
//    tcb->pends = 0;
//    tcb->posts = 0;
//   }
// } // SomeTask
//
//  if( Tamb < TambLoTemp || Tamb > TambHiTemp )
//   SmErrorBitFlag |= SM_ERROR_TAMB_RANGE; // ambient temperature out-of-range
//  else                                     // are soft and only require a
//   SmErrorBitFlag &= ~SM_ERROR_TAMB_RANGE; // flashing RED led (see
//  if( SmErrorBitFlag & SM_MINOR_FAULT )
//   {
//    LED_TOGGLE( SMBF_FAULT_LED );
//   }
//  if( SmErrorBitFlag & SM_MAJOR_FAULT )
//   {
//    LED_ON( SMBF_FAULT_LED );
//   }

// ---------------------------------------------------------------------------
//      function :
//     arguments :
//       returns :
//      synopsis :
// ---------------------------------------------------------------------------
