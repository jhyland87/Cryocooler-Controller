// -----------------------------------------------------------------------------
//  program name : NCP.OUT
//   module name : EEPROM.C
//    copyrights : Copyright (c) 2000 by Superconductor Technologies, Inc.
//      synopsis : All functions that handle SPI interfacing
// -----------------------------------------------------------------------------
#include "globals.h"
#include "C_Regs.h"

extern pSPI SPI;                        // see tasks.c
extern pDIO DIO;                        // see tasks.c

// -----------------------------------------------------------------------------
//      function : SpiShift
//     arguments : length - number of bytes to shift (8 max)
//       returns : nothing
//      synopsis : Expects that the data (including dummy data) is already
//                 available in SpiTxBuf[]. SpiRxBuf will be over-written.
//                 Also expects that the SPI device is already selected.
// -----------------------------------------------------------------------------
static void SpiShift( int length )
 {
  int  index;

  index = SPI->SPIRXBUF;                // do a dummy read of the input buffer
  index = 0;
  while( length > index )
   {
    while( SPI->SPISTS & 0x0020 );      // wait for TX buffer to be clear
    SPI->SPITXBUF = SpiTxBuf[ index ] << 8;
    while( !(SPI->SPISTS & 0x0040) );   // wait for RX buffer to be full
    SpiRxBuf[ index ] = SPI->SPIRXBUF & 0x00FF;
    index++;
   }
 }
// -----------------------------------------------------------------------------
//      function : EEPROM_Read
//     arguments : addr - 16-bit address (upper 5 bits are ignored)
//                 size - number of bytes to retrieve (4 max)
//       returns : byte, word or long depending on 'size' parameter
//      synopsis : Data is shifted into SpiRxBuf[]. It is assumed to be in
//                 Big Endian format (MSB .... LSB). It is then converted
//                 into long or word depending on the 'size' argument.
// -----------------------------------------------------------------------------
ULONG EEPROM_Read( UINT addr, UINT size )
 {
  char *cptr = (char*)SpiTxBuf, *tail;
  ULONG data = 0L;

  *cptr++ = 0x0003;                     // READ instruction
  *cptr++ = HI( addr );
  *cptr++ = LO( addr );

  DIO->PDDATDIR &= ~0x0008;             // assert EEPROM_EN
  SpiShift( size+3 );                   // shift the data out
  DIO->PDDATDIR |= 0x0008;              // de-assert EEPROM_EN

  cptr = (char*)SpiRxBuf + 3;
  tail = cptr + size;
  do
   {
    data <<= 8;
    data += (*cptr++ & 0x00FF);
   }
  while( tail != cptr );

  return data;
 }

// -----------------------------------------------------------------------------
//      function : EEPROM_Write
//     arguments : addr - 16-bit address (upper 5 bits are ignored)
//                 data - byte, word or long data to be written
//                 size - number of bytes to transmit (4 max)
//       returns : nothing
//      synopsis : Writes up to long size data to EEPROM storage. Data is
//                 assumed to be in Big Endian format and will be stored
//                 that way. It is further assumed that data will be either
//                 an int or a long requiring size to be either 2 or 4.
// -----------------------------------------------------------------------------
void EEPROM_Write( UINT addr, ULONG data, UINT size )
 {
  char *cptr = (char*)SpiTxBuf, *tail;

   // set the write enable latch
  *cptr = 0x0006;                       // WREN instruction
  DIO->PDDATDIR &= ~0x0008;             // assert EEPROM_EN
  SpiShift( 1 );                        // shift WREN out
  DIO->PDDATDIR |= 0x0008;              // de-assert EEPROM_EN

  *cptr++ = 0x0002;                     // WRITE instruction
  *cptr++ = HI( addr );
  *cptr   = LO( addr );
  tail    = cptr;
  cptr += size;
  do
   {
    *cptr-- = (UINT)data & 0x00FF;
    data >>= 8;
   }
  while( tail != cptr );

  DIO->PDDATDIR &= ~0x0008;             // assert EEPROM_EN
  SpiShift( size+3 );                   // shift the data out
  DIO->PDDATDIR |= 0x0008;              // de-assert EEPROM_EN
 }

//// -----------------------------------------------------------------------------
////      function : EEPROM_Read
////     arguments : addr - 16-bit address (upper 5 bits are ignored)
////       returns : integer at addr
////      synopsis : Returns the integer at the address
//// -----------------------------------------------------------------------------
//UINT EEPROM_Read( UINT addr )
// {
//  char *cptr = (char*)SpiTxBuf;
//
//  *cptr++ = 0x0003;                     // READ instruction
//  *cptr++ = HI( addr );
//  *cptr   = LO( addr );
//
//  DIO->PDDATDIR &= ~0x0008;             // assert EEPROM_EN
//  SpiShift( 5 );                        // shift the data out
//  DIO->PDDATDIR |= 0x0008;              // de-assert EEPROM_EN
//
//  return ((SpiRxBuf[3]<<8)&0xFF00) + (SpiRxBuf[4]&0x00FF);
// }
//
//// -----------------------------------------------------------------------------
////      function : EEPROM_Write
////     arguments : addr - 16-bit address (upper 5 bits are ignored)
////                 data - word (16-bit) data to be written
////       returns : nothing
////      synopsis : Writes one integer to EEPROM storage.
//// -----------------------------------------------------------------------------
//void EEPROM_Write( UINT addr, UINT data )
// {
//  char *cptr = (char*)SpiTxBuf;
//
//   // set the write enable latch
//  *cptr = 0x0006;                       // WREN instruction
//  DIO->PDDATDIR &= ~0x0008;             // assert EEPROM_EN
//  SpiShift( 1 );                        // shift WREN out
//  DIO->PDDATDIR |= 0x0008;              // de-assert EEPROM_EN
//
//  *cptr++ = 0x0002;                     // WRITE instruction
//  *cptr++ = HI( addr );
//  *cptr++ = LO( addr );
//  *cptr++ = (data>>8) & 0x00FF;
//  *cptr   = data & 0x00FF;
//
//  DIO->PDDATDIR &= ~0x0008;             // assert EEPROM_EN
//  SpiShift( 5 );                        // shift the data out
//  DIO->PDDATDIR |= 0x0008;              // de-assert EEPROM_EN
// }

// -----------------------------------------------------------------------------
//      function : EEPROM_Read
//     arguments : addr - 16-bit address (upper 5 bits are ignored)
//                 size - number of bytes to retrieve (4 max)
//       returns : nothing
//      synopsis : Data is returned in SpiRxBuf[]. It is assumed to be in
//                 Big Endian format (MSB .... LSB)
// -----------------------------------------------------------------------------
//void EEPROM_Read( UINT addr, UINT size )
// {
//  int  i, j;
//
//  i = 0;
//  SpiTxBuf[ i++ ] = 0x0003;            // READ instruction
//  SpiTxBuf[ i++ ] = HI( addr );
//  SpiTxBuf[ i++ ] = LO( addr );
//  for( j=0 ; j<size && j<5 ; j++ )
//   SpiTxBuf[ i++ ] = 0x00FF;
//
//  DIO->PDDATDIR &= ~0x0008;             // assert EEPROM_EN
//  SpiShift( i );                        // shift the data out
//  DIO->PDDATDIR |= 0x0008;              // de-assert EEPROM_EN
// }
//
// -----------------------------------------------------------------------------
//      function : EEPROM_Write
//     arguments : addr - 16-bit address (upper 5 bits are ignored)
//                 data - byte, word or long data to be written
//                 size - number of bytes to transmit (4 max)
//       returns : nothing
//      synopsis : Writes up to long size data to EEPROM storage. Data is
//                 assumed to be in Big Endian format and will be stored
//                 that way. It is further assumed that data will be either
//                 an int or a long requiring size to be either 2 or 4.
// -----------------------------------------------------------------------------
//void EEPROM_Write( UINT addr, ULONG data, UINT size )
// {
//  int  i, j;
//
//  i = 0;
//   // set the write enable latch
//  SpiTxBuf[ i ] = 0x0006;               // WREN instruction
//  DIO->PDDATDIR &= ~0x0008;             // assert EEPROM_EN
//  SpiShift( 1 );                        // shift WREN out
//  DIO->PDDATDIR |= 0x0008;              // de-assert EEPROM_EN
//
//  SpiTxBuf[ i++ ] = 0x0002;            // READ instruction
//  SpiTxBuf[ i++ ] = HI( addr );
//  SpiTxBuf[  i  ] = LO( addr );
//  j = i + size;
//  do
//   {
//    SpiTxBuf[ j-- ] = (UINT)data & 0x00FF;
//    data >>= 8;
//   }
//  while( j > i );
//
//  i = i + size + 1;
//  DIO->PDDATDIR &= ~0x0008;             // assert EEPROM_EN
//  SpiShift( i );                        // shift the data out
//  DIO->PDDATDIR |= 0x0008;              // de-assert EEPROM_EN
// }


// -----------------------------------------------------------------------------
//      function :
//     arguments :
//       returns :
//      synopsis :
// -----------------------------------------------------------------------------
