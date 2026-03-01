/**
 * @file SPI.h
 * @brief Minimal Arduino SPI stub for native unit-test builds.
 *
 * SPIClass and SPISettings are declared in Arduino.h (which is on the
 * include path).  This thin wrapper lets third-party libraries that
 * #include <SPI.h> directly (e.g. Adafruit BusIO) find the stub.
 */

#ifndef SPI_H
#define SPI_H

#include "Arduino.h"

#endif // SPI_H
