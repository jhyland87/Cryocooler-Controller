#if !defined( C_REGS_H )
#define    C_REGS_H
// -----------------------------------------------------------------------------
//  program name : NCP.OUT
//   module name : C_REGS.H
//    copyrights : Copyright (c) 2000 by Superconductor Technologies
//                 460 Ward Drive
//                 Santa Barbara, CA
// synopsis : Definitions of TMS320F243 hardware registers suitable for
//                 using in a C program
// -----------------------------------------------------------------------------
#include   "globals.h"

// ----- Digital IO ------------------------------------------------------------
typedef struct DigitalIOtag
 {
  UINT     OCRA;            // Output control reg A          @ 0x7090
  UINT     t00;             // reserved space                @ 0x7091
  UINT     OCRB;            // Output control reg B          @ 0x7092
  UINT     t01;             // reserved space                @ 0x7093
  UINT     t02;             // reserved space                @ 0x7094
  UINT     t03;             // reserved space                @ 0x7095
  UINT     t04;             // reserved space                @ 0x7096
  UINT     t05;             // reserved space                @ 0x7097
  UINT     PADATDIR;        // Port A data direction reg     @ 0x7098
  UINT     t06;             // reserved space                @ 0x7099
  UINT     PBDATDIR;        // Port B data direction reg     @ 0x709A
  UINT     t07;             // reserved space                @ 0x709B
  UINT     PCDATDIR;        // Port C data direction reg     @ 0x709C
  UINT     t08;             // reserved space                @ 0x709D
  UINT     PDDATDIR;        // Port D data direction reg     @ 0x709E
  UINT     t09;             // reserved space                @ 0x709F
 } *pDIO;
// usage : pDIO DIO = (pDIO) 0x7090;

// ----- SCI Module Registers --------------------------------------------------
typedef struct SCItag
 {
  UINT     SCICCR;          // Communications Control reg    @ 0x7050
  UINT     SCICTL1;         // SCI Control reg 1             @ 0x7051
  UINT     SCIHBAUD;        // Baud Rate MSbyte              @ 0x7052
  UINT     SCILBAUD;        // Baud Rate LSbyte              @ 0x7053
  UINT     SCICTL2;         // SCI Control reg 2             @ 0x7054
  UINT     SCIRXST;         // Receiver Status               @ 0x7055
  UINT     SCIRXEMU;        // EMU Data Buffer               @ 0x7056
  UINT     SCIRXBUF;        // Receiver Data Buffer          @ 0x7057
  UINT     t01;
  UINT     SCITXBUF;        // Transmit Data Buffer          @ 0x7059
  UINT     t02;
  UINT     t03;
  UINT     t04;
  UINT     t05;
  UINT     t06;
  UINT     SCIPRI;          // Priority/Emulation Control    @ 0x705F
 } *pSCI;
 // usage : pSCI SCI = (pSCI) 0x7050;

// ----- ADC Module Registers --------------------------------------------------
typedef struct ADCtag
 {
  UINT     ADCTRL1;         // ADC Control Register 1        @ 0x7032
  UINT     t01;
  UINT     ADCTRL2;         // ADC Control Register 2        @ 0x7034
  UINT     t02;
  UINT     ADCFIFO1;        // FIFO Register for ADC #1      @ 0x7036
  UINT     t03;
  UINT     ADCFIFO2;        // FIFO Register for ADC #2      @ 0x7038
 } *pADC;
 // usage : pADC ADC = (pADC) 0x7032;

// ----- SPI Module Registers --------------------------------------------------
typedef struct SPItag
 {
  UINT     SPICCR;          // Configuration Control reg     @ 0x7040
  UINT     SPICTL;          // Operation Control reg         @ 0x7041
  UINT     SPISTS;          // Status reg                    @ 0x7042
  UINT     t01;             // reserved                      @ 0x7043
  UINT     SPIBRR;          // Baud Rate reg                 @ 0x7044
  UINT     t02;             // reserved                      @ 0x7045
  UINT     SPIRXEMU;        // Emulation Buffer reg          @ 0x7046
  UINT     SPIRXBUF;        // Serial Receive Buffer reg     @ 0x7047
  UINT     SPITXBUF;        // Serial Transmit Buffer reg    @ 0x7048
  UINT     SPIDAT;          // Serial Data reg               @ 0x7049
  UINT     t03;             // reserved                      @ 0x704A
  UINT     t04;             // reserved                      @ 0x704B
  UINT     t05;             // reserved                      @ 0x704C
  UINT     t06;             // reserved                      @ 0x704D
  UINT     t07;             // reserved                      @ 0x704E
  UINT     SPIPRI;          // Priority Control reg          @ 0x704F
 } *pSPI;
 // usage : pSPI SPI = (pSPI) 0x7040;

#endif     /*** C_REGS_H ***/
