/**
 * @file Wire.h
 * @brief Minimal Arduino I2C (Wire) stub for native unit-test builds.
 *
 * Provides just enough of the TwoWire API to satisfy Adafruit BusIO
 * compilation in the native (host-PC) environment.  All methods are no-ops.
 */

#ifndef WIRE_H
#define WIRE_H

#include <cstdint>
#include <cstddef>

class TwoWire {
public:
    void    begin()                         {}
    void    begin(uint8_t /*addr*/)         {}
    void    setClock(uint32_t /*hz*/)       {}
    void    beginTransmission(uint8_t /*addr*/) {}
    uint8_t endTransmission(bool /*stop*/ = true) { return 0; }
    size_t  requestFrom(uint8_t /*addr*/, size_t /*len*/, bool /*stop*/ = true) { return 0; }
    size_t  write(uint8_t /*b*/)            { return 1; }
    size_t  write(const uint8_t* /*buf*/, size_t /*len*/) { return 0; }
    int     read()                          { return -1; }
    int     available()                     { return 0; }
    int     peek()                          { return -1; }
    void    flush()                         {}
};

extern TwoWire Wire;

#endif // WIRE_H
