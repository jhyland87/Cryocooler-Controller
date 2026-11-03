/***************************************************************************/
/* file name : NCP.CMD                                                     */
/*  synopsis : This is the linker command file.                            */
/*             Note that the linker refers to PROGRAM memory as PAGE 0 and */
/*             DATA memory as PAGE 1. The memory map is setup for the      */
/*             TMS320F243 device, i.e.,                                    */
/*               ROM (PAGE 0)                                              */
/*                 Interrupt vectors   = 0x0000 - 0x003F   (64 words)      */
/*                 Executable code     = 0x0040 - 0x1FFF   (8128 words)    */
/*               RAM (PAGE 1)                                              */
/*                 Memory-Mapped regs  = 0x0000 - 0x005F   (96 words)      */
/*                 DARAM B2            = 0x0060 - 0x007F   (32 words)      */
/*                 DARAM B0            = 0x0200 - 0x02FF   (256 words)     */
/*                 DARAM B1            = 0x0300 - 0x037F   (128 words)     */
/*                 DARAM STK           = 0x0380 - 0x03FF   (128 words)     */
/*                 Peripherials        = 0x7000 - 0x73FF   (1024 words)    */
/*                 Event Manager       = 0x7400 - 0x743F   (64 words)      */
/*                 external RAM        = 0x8000 - 0xFFFF   (32768 words)   */
/*                                                                         */
/*             Not all memory spaces are utilized.                         */
/***************************************************************************/

MEMORY
{
 PAGE 0 :      VECS    : origin =  0000h, length =  0040h  /* VECTORS      */
               RESET   : origin =  0040h, length =  0040h  /* RESET        */
               PROG    : origin =  0080h, length = 01E80h  /* PROGRAM      */

 PAGE 1 :      MMRS    : origin =  0000h, length =  0060h  /* MEM MAP      */
               B2      : origin =  0060h, length =  0020h  /* DARAM B2     */
               BSS     : origin =  0200h, length =  0180h  /* DARAM B0     */
               STACK   : origin =  0380h, length =  0080h  /* STK          */
}

SECTIONS
{
 .vectors      : > VECS    PAGE = 0    /* Interrupt vector table           */
 .reset        : > RESET   PAGE = 0    /* Reset vector                     */
 .text         : > PROG    PAGE = 0    /* Code                             */
 .const        : > PROG    PAGE = 0    /* put constants in ROM             */
 .bss          : > BSS     PAGE = 1    /* Uninitialized data               */
 .stack        : > STACK   PAGE = 1    /* stack space                      */
}
