// -----------------------------------------------------------------------------
//  program name : NCP.OUT
//   module name : PARSER.C
//    copyrights : Copyright (c) 2000 by Superconductor Technologies
//
//      synopsis :
// -----------------------------------------------------------------------------
#include   "globals.h"                 // AsciiToInt

// ----------- local variable definitions -------------------------------------
const int c_map[ 128 ] = {
// 0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0,      // 0x
   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,      // 1x
   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,      // 2x
   2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 3, 0, 4,      // 3x
   0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0,      // 4x
   0, 0, 0, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,      // 5x
   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,      // 6x
   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,      // 7x
 };

const int r_map[ 9 ] = {
   0,  1,  2,  3,  4,  5,  6,  7,  8,
 };

const int map[ 9 ][ 7 ] = {
//    0   1   2   3   4   5   6
  { -1,100, -1, -1, -1,  6,  1, },                      //  0
  { -1, -1,  2, -1, -1, -1, -1, },                      //  1
  { -1, -1,  2,  4,  3, -1, -1, },                      //  2
  { -1,101, -1, -1, -1, -1, -1, },                      //  3
  { -1, -1,  5, -1, -1, -1, -1, },                      //  4
  { -1,102,  5, -1, -1, -1, -1, },                      //  5
  { -1, -1,  7, -1, -1, -1, -1, },                      //  6
  { -1, -1,  7, -1,  8, -1, -1, },                      //  7
  { -1,103, -1, -1, -1, -1, -1, },                      //  8
 };

// ----------- local function prototypes --------------------------------------
static int next (int state, int c);
// -----------------------------------------------------------------------------
//      function : parser
//     arguments : sbuf, command, index, operator, argument
//                      [S|I]  [0-9]+ = [0-9]+
//                        |     |    |    |--->  argument
//                        |     |    |-------->  operator
//                        |     |------------->  index
//                        |------------------->  command
//       returns : Returns the final state (>99) if a token was found,
//                 otherwise returns -1 to indicate error
//      synopsis : Checks the string for validy then (if valid) parses the
//                 string into recognized tokens
// -----------------------------------------------------------------------------
int    parse( char *sbuf,
              char *command,
              int  *index,
              char *operator,
              long *argument )
 {
  int      state = 0;
  int      i = 0;
  char     *head, *tail;

  state = next( state, sbuf[i++] );
  while( state>0 && state<99 )
   state = next( state, sbuf[i++] );
  if( state > 99 )
   {
    tail = sbuf;
    *command = *tail++;                // get the command
    head = tail;                       // and advance the head pointer
    i = *tail - '0';                   // find the operation character
    while( i>=0 && i<=9 )
     i = *(++tail) - '0';
    *operator = *tail;                 // get the operation
    *index = (int)AsciiToLong( head ); // get the command index
    head = ++tail;                     // reset the head pointer
    *argument = AsciiToLong( head );   // get the argument
   }

  return state;
 } // parser

// -----------------------------------------------------------------------------
//      function : next
//     arguments : state - the current DFA state
//                 c     - the lookahead character
//       returns : The next state, or -1 if transition not defined
//      synopsis : This function is used to walk through the state tables
//                 for the command lexical recognizer.
//         notes : Parts of this function need to be written in assembler
//                 because the TI C compiler doesn't handle references
//                 to 'const' data correctly.
//
//                 (1) 'col' needs to match the number of columns in the
//                     map[row][col] array declared above!
//
//  stack layout : The activation record looks like this
//
//                 |    xxx     |
//                 --------------
//                 |     c      | <- new FP - 4
//                 --------------
//                 |   state    | <- new FP - 3
//                 --------------
//     caller      |  ret addr  |
//     ----------- --------------
//     callee      |  copy FP   |
//                 --------------
//                 |  copy SP   | <- new FP
//                 --------------
//                 |    col     | <- new FP + 1
//                 --------------
//                 |    next    | <- new FP + 2
//                 --------------
//                 |    xxx     | <- new SP
//
// -----------------------------------------------------------------------------
static int next( int state, int c )
 {
  int  col;

//  col = c_map[ c ];
  asm( "   MAR     *, AR3    " );      // AR = 3
  asm( "   LAR     AR3, #1H  " );      // AR3 = 1
  asm( "   MAR     *0+, AR2  " );      // AR3 = AR0 +1, i.e., AR3 => col
  asm( "   LAR     AR2, #-4H " );      // AR2 = -4
  asm( "   MAR     *0+       " );      // AR2 => c
  asm( "   LACC    *, 0, AR3 " );      // ACC = *AR2
  asm( "   ADD     #_c_map, 0" );      //
  asm( "   TBLR    *, AR2    " );      // col = #c_map + c

//  return map[ state ][ col ];
  asm( "   LAR     AR2, #-3H " );      // AR2 => -3
  asm( "   MAR     *0+       " );      // AR2 = AR2 + AR0, i.e., AR2 => state
  asm( "   LT      *         " );      // TREG <= *AR2
  asm( "   MPY     #7H       " );      // IMPORTANT - change for # of map columns
  asm( "   PAC               " );      // ACC = state * col
  asm( "   CLRC    SXM       " );
  asm( "   ADD     #_map     " );
  asm( "   ADRK    #4H       " );
  asm( "   ADD     *, 0      " );
  asm( "   TBLR    *         " );      // *AR2 = &map + ( row * col ) + col
  asm( "   LACC    *, 0, AR1 " );      // ACC = *AR2
 } // next
