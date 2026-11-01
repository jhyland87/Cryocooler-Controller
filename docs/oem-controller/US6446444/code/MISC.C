// -----------------------------------------------------------------------------
//  program name : NCP.OUT
//   module name : MISC.C
//      synopsis : A collection of miscellaneous 'helper' functions
// -----------------------------------------------------------------------------
#include   "globals.h"                  // includes time.h


 /****************************************************************************
  * Rewrites of stdlib functions                                             *
  *    clock()         returns ticks updated by GISR3 (see ISRS.ASM)         *
  *    AsciiToInt()    replaces atoi()                                       *
  *    LongToAscii()   replaces ltoa()                                       *
  ****************************************************************************/

// -----------------------------------------------------------------------------
//      function : clock
//     arguments : none
//       returns : Returns system time.
//      synopsis : This function is found in the TI Standard Library and is
//                 overridden here. System time is updated every 2.083mS. The
//                 macro CLOCKS_PER_SEC, defined in globals.h can be used to
//                 convert the global variable "ckticks" into seconds.
//                 See documentation in TMS320C2xx Optimizing C Compiler,
//                 Runtime-Support functions (5-57).
//         NOTES : The 2.083mS time comes from
//                     1/60/256 = 65.1uS * 32 = 2.083mS
// -----------------------------------------------------------------------------
clock_t clock( void )
 {
  return ckticks;
 } // clock

// -----------------------------------------------------------------------------
//      function : AsciiToLong
//     arguments : cptr -  pointer to character buffer that holds the number
//                         string
//       returns : conversion of ASCII string into (long) int
//      synopsis : Converts an array of charactes into an integer. Stops
//                 on the first non-numeric character.
// -----------------------------------------------------------------------------
long   AsciiToLong( char *cptr )
 {
  long  t1, sum = 0L;

  t1 = *cptr - '0';
  while( t1>=0 && t1<=9 )
   {
    sum = sum * 10 + t1;
    t1 = *(++cptr) - '0';
   }

  return sum;
 } // AsciiToLong

// -----------------------------------------------------------------------------
//      function : LongToAscii
//     arguments : n - number to be converted
//                 b - buffer to write the converted number to
//       returns : number of chacters in the output buffer, including
//                 NULL terminating character
//      synopsis : Replaces the TI implementation, which killed the compiler
// -----------------------------------------------------------------------------
int    LongToAscii( long n, char b[] )
 {
  char     tbuf[ BUF16 ];
  int      neg = 0, i, j;

  if( n<0L )
   {
    neg++;
    n = -n;
   }

  i = BUF16-1;
  tbuf[ i-- ] = 0;
  do
   {
    tbuf[ i-- ] = (n % 10) + '0';
    n /= 10;
   }
  while( n );
  if( neg )
   tbuf[ i-- ] = '-';

  j = 0;
  while( i<BUF16 )
    b[ j++ ] = tbuf[ ++i ];

  return j-1;
 } // LongToAscii
