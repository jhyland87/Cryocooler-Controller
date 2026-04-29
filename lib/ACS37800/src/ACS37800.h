// Copyright (C) Pololu Corporation.  See LICENSE.txt for details.
// Modified: Added SPI transport support alongside original I2C.

/// \file ACS37800.h
///
/// ACS37800 power monitoring library for Arduino — I2C and SPI.
///
/// Original I2C-only library by Pololu:
/// https://github.com/pololu/acs37800-arduino
///
/// SPI transport added for ACS37800 SPI-variant ICs.  The register map
/// is identical between I2C and SPI; only the physical transport differs.

#pragma once

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>

class ACS37800
{
public:
  enum class Transport : uint8_t { I2C, SPI };

  /// Creates a new ACS37800 object configured for I2C.
  ACS37800(uint8_t address = 0x60, TwoWire * bus = &Wire)
    : transport_(Transport::I2C), bus_(bus), address_(address),
      spiBus_(nullptr), csPin_(0) {}

  /// Creates a new ACS37800 object configured for SPI.
  ///
  /// The SPI bus must be initialised (begin() called) before any reads/writes.
  /// The CS pin is managed by this class (driven LOW during transactions).
  ACS37800(SPIClass * spiBus, uint8_t csPin)
    : transport_(Transport::SPI), bus_(nullptr), address_(0),
      spiBus_(spiBus), csPin_(csPin) {}

  /// Returns the transport mode this object is configured for.
  Transport getTransport() { return transport_; }

  /// Configures this object to use the specified I2C bus.  I2C mode only.
  void setBus(TwoWire * bus) { bus_ = bus; }

  /// Returns a pointer to the I2C bus.  I2C mode only.
  TwoWire * getBus() { return bus_; }

  /// Configures this object to use the specified 7-bit I2C address.  I2C only.
  void setAddress(uint8_t address) { address_ = address; }

  /// Returns the 7-bit I2C address.  I2C mode only.
  uint8_t getAddress() { return address_; }

  /// Returns 0 if the last communication was successful, or a non-zero error
  /// code if there was an error.
  uint8_t getLastError() { return lastError; }

  /// Configures this object to use the right calculation parameters for a
  /// Pololu ACS37800 isolated power monitor carrier board.
  ///
  /// The `rsense_kohm` argument should be the Rsense value of your board, in
  /// units of kilohms.  Valid values are 1, 2, and 4.
  void setBoardPololu(uint8_t rsense_kohm)
  {
    icodesMult = 17873;
    icodesShift = 14;
    switch (rsense_kohm)
    {
    case 1:
      vcodesMult = 18623;
      vcodesShift = 9;
      pinstantMult = 1299;
      pinstantShift = 0;
      break;
    case 2:
      vcodesMult = 18627;
      vcodesShift = 10;
      pinstantMult = 10395;
      pinstantShift = 4;
      break;
    default:
    case 4:
      vcodesMult = 18637;
      vcodesShift = 11;
      pinstantMult = 325;
      pinstantShift = 0;
      break;
    }
  }

  /// Configures calculation parameters for a generic board.
  void setBoardParameters(uint8_t isense_range, uint32_t riso, uint32_t rsense)
  {
    calculateApproximation(riso + rsense, 110 * rsense,
      vcodesMult, vcodesShift);
    calculateApproximation(2 * isense_range, 55,
      icodesMult, icodesShift);
    calculateApproximation(
      (uint64_t)isense_range * (riso + rsense) * 5, rsense * 462,
      pinstantMult, pinstantShift);
  }

  /// Writes the ACCESS_CODE to unlock register writes.
  void enableWriteAccess()
  {
    writeReg(0x2F, 0x4F70656E);
  }

  /// Configures the number of samples for RMS / power calculations (32 kHz).
  /// 0 = line-synchronised (zero-crossing to zero-crossing).
  void setSampleCount(uint16_t count)
  {
    enableWriteAccess();
    if (getLastError()) { return; }

    uint32_t reg = readReg(0x1F);
    if (getLastError()) { return; }

    if (count > 1023) { count = 1023; }

    reg &= 0xFE003FFF;
    if (count) { reg |= ((uint32_t)1 << 24) | ((uint32_t)count << 14); }

    writeReg(0x1F, reg);
  }

  /// Reads RMS voltage and current into rmsVoltageMillivolts / rmsCurrentMilliamps.
  void readRMSVoltageAndCurrent()
  {
    uint32_t reg = readReg(0x20);
    uint16_t vrms = (uint16_t)reg;
    uint16_t irms = (uint16_t)(reg >> 16);
    rmsVoltageMillivolts = (int32_t)vrms * vcodesMult >> vcodesShift >> 1;
    rmsCurrentMilliamps = (int32_t)irms * icodesMult >> icodesShift >> 1;
  }

  /// Reads active and reactive power in mW.
  void readActiveAndReactivePower()
  {
    uint32_t reg = readReg(0x21);
    int16_t pactive = (int16_t)reg;
    uint16_t pimag = (uint16_t)(reg >> 16);
    activePowerMilliwatts = (int32_t)pactive * pinstantMult >> pinstantShift;
    reactivePowerMilliwatts = (int32_t)pimag * pinstantMult >> pinstantShift >> 1;
  }

  /// Reads apparent power and returns it in mW.
  int32_t readApparentPowerMilliwatts()
  {
    uint32_t reg = readReg(0x22);
    uint16_t papparent = (uint16_t)reg;
    apparentPowerMilliwatts = (int32_t)papparent * pinstantMult >> pinstantShift >> 1;
    return apparentPowerMilliwatts;
  }

  /// Reads instantaneous voltage and current (VCODES / ICODES).
  void readInstVoltageAndCurrent()
  {
    uint32_t reg = readReg(0x2A);
    int16_t vcodes = (int16_t)reg;
    int16_t icodes = (int16_t)(reg >> 16);
    instVoltageMillivolts = (int32_t)vcodes * vcodesMult >> vcodesShift;
    instCurrentMilliamps = (int32_t)icodes * icodesMult >> icodesShift;
  }

  /// Reads instantaneous power (PINSTANT) in mW.
  int32_t readInstPowerMilliwatts()
  {
    int16_t pinstant = (int16_t)readReg(0x2C);
    instPowerMilliwatts = (int32_t)pinstant * pinstantMult >> pinstantShift;
    return instPowerMilliwatts;
  }

  int32_t readRMSVoltageMillivolts()
  {
    readRMSVoltageAndCurrent();
    return rmsVoltageMillivolts;
  }

  int32_t readRMSCurrentMilliamps()
  {
    readRMSVoltageAndCurrent();
    return rmsCurrentMilliamps;
  }

  int32_t readActivePowerMilliwatts()
  {
    readActiveAndReactivePower();
    return activePowerMilliwatts;
  }

  int32_t readReactivePowerMilliwatts()
  {
    readActiveAndReactivePower();
    return reactivePowerMilliwatts;
  }

  int32_t readInstVoltageMillivolts()
  {
    readInstVoltageAndCurrent();
    return instVoltageMillivolts;
  }

  int32_t readInstCurrentMilliamps()
  {
    readInstVoltageAndCurrent();
    return instCurrentMilliamps;
  }

  /// Sets the 7-bit I2C device address in EEPROM.  I2C mode only.
  void writeEepromI2CAddress(uint8_t address)
  {
    if (transport_ != Transport::I2C) { return; }
    enableWriteAccess();
    if (getLastError()) { return; }
    uint32_t reg = readReg(0x0F);
    if (getLastError()) { return; }
    reg = (reg & ~(uint32_t)0x3FC) | (1 << 9) | ((address & 0x7F) << 2);
    writeReg(0x0F, reg);
  }

  /// Reads a 32-bit sensor register.
  uint32_t readReg(uint8_t reg)
  {
    if (transport_ == Transport::SPI)
      return readRegSPI(reg);
    return readRegI2C(reg);
  }

  /// Writes a 32-bit sensor register.
  void writeReg(uint8_t reg, uint32_t value)
  {
    if (transport_ == Transport::SPI)
      writeRegSPI(reg, value);
    else
      writeRegI2C(reg, value);
  }

  uint16_t vcodesMult = 1, icodesMult = 1, pinstantMult = 1;
  uint8_t vcodesShift = 0, icodesShift = 0, pinstantShift = 0;

  int32_t instVoltageMillivolts;
  int32_t instCurrentMilliamps;
  int32_t instPowerMilliwatts;

  int32_t rmsVoltageMillivolts;
  int32_t rmsCurrentMilliamps;
  int32_t activePowerMilliwatts;
  int32_t reactivePowerMilliwatts;
  int32_t apparentPowerMilliwatts;

private:

  // -- I2C transport ----------------------------------------------------------

  uint32_t readRegI2C(uint8_t reg)
  {
    bus_->beginTransmission(address_);
    bus_->write(reg);
    lastError = bus_->endTransmission();
    if (getLastError()) { return 0; }

    uint8_t byteCount = bus_->requestFrom(address_, (uint8_t)4);
    if (byteCount != 4)
    {
      lastError = 50;
      return 0;
    }

    uint32_t value = bus_->read();
    value |= (uint32_t)bus_->read() << 8;
    value |= (uint32_t)bus_->read() << 16;
    value |= (uint32_t)bus_->read() << 24;
    return value;
  }

  void writeRegI2C(uint8_t reg, uint32_t value)
  {
    bus_->beginTransmission(address_);
    bus_->write(reg);
    bus_->write(value & 0xFF);
    bus_->write(value >> 8 & 0xFF);
    bus_->write(value >> 16 & 0xFF);
    bus_->write(value >> 24 & 0xFF);
    lastError = bus_->endTransmission();
  }

  // -- SPI transport ----------------------------------------------------------
  //
  // ACS37800 SPI protocol (from datasheet):
  //   Command byte: bits 7:1 = 7-bit register address, bit 0 = R/W (1=read, 0=write)
  //   Data: 32 bits, little-endian byte order (LSB first), same as I2C
  //   Clock: 10 MHz max, SPI Mode 3 (CPOL=1 CPHA=1), MSB first
  //   (Clock idles HIGH; data sampled on rising edge / output on falling edge.)
  //
  //   IMPORTANT — reads are pipelined:
  //     Transaction 1: send read command for register R.
  //                     MISO returns data from the PREVIOUS read (stale/undefined).
  //     Transaction 2: send another read (same or different register).
  //                     MISO returns data for register R from transaction 1.
  //
  //   To get a single register value we issue TWO back-to-back read
  //   transactions and return the data from the second one.

  static constexpr uint32_t kSpiClockHz = 1000000;  // 1 MHz (very conservative)

  uint32_t readRegSPI(uint8_t reg)
  {
    SPISettings settings(kSpiClockHz, MSBFIRST, SPI_MODE3);
    const uint8_t cmd = (reg << 1) | 0x01;                 // addr<<1 | R/W=1 (read)

    spiBus_->beginTransaction(settings);
    digitalWrite(csPin_, LOW);

    // Cycle 1 — primes pipeline; MISO returns previous read's data (discarded).
    spiBus_->transfer(cmd);
    spiBus_->transfer(0x00);
    spiBus_->transfer(0x00);
    spiBus_->transfer(0x00);
    spiBus_->transfer(0x00);

    // Cycle 2 — MISO now returns data for the register addressed in cycle 1.
    spiBus_->transfer(cmd);
    uint32_t value  = spiBus_->transfer(0x00);             // byte 0 (LSB)
    value |= (uint32_t)spiBus_->transfer(0x00) << 8;      // byte 1
    value |= (uint32_t)spiBus_->transfer(0x00) << 16;     // byte 2
    value |= (uint32_t)spiBus_->transfer(0x00) << 24;     // byte 3 (MSB)

    digitalWrite(csPin_, HIGH);
    spiBus_->endTransaction();
    lastError = 0;
    return value;
  }

  void writeRegSPI(uint8_t reg, uint32_t value)
  {
    SPISettings settings(kSpiClockHz, MSBFIRST, SPI_MODE3);
    spiBus_->beginTransaction(settings);
    digitalWrite(csPin_, LOW);
    spiBus_->transfer((reg << 1) & 0xFE);                  // addr<<1 | R/W=0 (write)
    spiBus_->transfer(value & 0xFF);                       // byte 0 (LSB)
    spiBus_->transfer((value >> 8) & 0xFF);                // byte 1
    spiBus_->transfer((value >> 16) & 0xFF);               // byte 2
    spiBus_->transfer((value >> 24) & 0xFF);               // byte 3 (MSB)
    digitalWrite(csPin_, HIGH);
    spiBus_->endTransaction();
    lastError = 0;
  }

  // -- Calibration helper -----------------------------------------------------

  static void calculateApproximation(
    uint64_t numerator, uint64_t denominator,
    uint16_t & outputMult, uint8_t & outputShift)
  {
    float k = (float)numerator / denominator;
    uint16_t mult = 0;
    uint8_t shift = 0;
    for (uint8_t shift_candidate = 0; shift_candidate < 32; shift_candidate++)
    {
      uint32_t mult_candidate = round(k * ((uint32_t)1 << shift_candidate));
      if (mult_candidate > 0x7FFF) { break; }
      mult = mult_candidate;
      shift = shift_candidate;
    }
    while ((mult & 1) == 0)
    {
      mult >>= 1;
      shift--;
    }
    outputMult = mult;
    outputShift = shift;
  }

  // -- Members ----------------------------------------------------------------

  Transport transport_;

  // I2C
  TwoWire * bus_;
  uint8_t address_;

  // SPI
  SPIClass * spiBus_;
  uint8_t csPin_;

  uint8_t lastError = 0;
};
