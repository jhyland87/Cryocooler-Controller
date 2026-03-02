/*
  QMI8658 - Arduino Library for QMI8658 6-Axis IMU Sensor

  Implementation file for QMI8658 library

  ── Project patch notes ──────────────────────────────────────────────────────
  This is a vendored copy of the upstream library with the following changes:

  1. begin(TwoWire&, uint8_t): removed `_wire->begin()` call (line 23 in the
     original).  The project initialises the shared Wire bus once in
     hardware::init().  A second begin() call corrupts the ESP-IDF I2C master
     driver handle and causes a StoreProhibited panic inside i2c_master_probe().

  2. printSensorData(): replaced Arduino String objects with const char*
     literals to comply with the project's "no Arduino String class" policy.
  ─────────────────────────────────────────────────────────────────────────────
*/

#include "QMI8658.h"

QMI8658::QMI8658() {
    _wire = nullptr;
    _address = QMI8658_ADDRESS_LOW;
    _accel_lsb_div = 4096;  // Default for ±8g
    _gyro_lsb_div = 64;     // Default for ±512dps
    _accel_unit_mps2 = false;  // Default to mg (more common in IMU applications)
    _gyro_unit_rads = false;   // Default to dps (more intuitive)
    _display_precision = 6;    // Default to 6 decimal places for high precision
    _timestamp = 0;
}

bool QMI8658::begin(TwoWire &wire, uint8_t address) {
    _wire = &wire;
    _address = address;
    // NOTE (patch): _wire->begin() intentionally omitted here.
    // The shared I2C bus is initialised exactly once by hardware::init().
    // Calling begin() again corrupts the ESP-IDF i2c_master_bus_handle_t and
    // causes a StoreProhibited panic when i2c_master_probe() is subsequently
    // called.  See hardware.cpp for the single authoritative begin() call.

    // Test communication
    uint8_t who_am_i = getWhoAmI();
    if (who_am_i != 0x05) {
        // Try the other address
        _address = (_address == QMI8658_ADDRESS_LOW) ? QMI8658_ADDRESS_HIGH : QMI8658_ADDRESS_LOW;
        who_am_i = getWhoAmI();
        if (who_am_i != 0x05) {
            return false;
        }
    }

    // Initialize the sensor
    if (!writeRegister(QMI8658_CTRL1, 0x60)) {
        return false;
    }

    // Set default configuration
    setAccelRange(QMI8658_ACCEL_RANGE_8G);
    setAccelODR(QMI8658_ACCEL_ODR_1000HZ);
    setGyroRange(QMI8658_GYRO_RANGE_512DPS);
    setGyroODR(QMI8658_GYRO_ODR_1000HZ);

    // Enable accelerometer and gyroscope
    enableSensors(QMI8658_ENABLE_ACCEL | QMI8658_ENABLE_GYRO);

    return true;
}

// Platform-specific I2C initialization
static bool initializeI2C(uint8_t sda_pin, uint8_t scl_pin, TwoWire &wire_instance) {
    #if defined(ARDUINO_ARCH_RP2040)
        // RP2040: Auto-select Wire or Wire1 based on pins
        if ((sda_pin == 6 && scl_pin == 7) || (sda_pin == 2 && scl_pin == 3) ||
            (sda_pin == 10 && scl_pin == 11) || (sda_pin == 14 && scl_pin == 15) ||
            (sda_pin == 18 && scl_pin == 19) || (sda_pin == 26 && scl_pin == 27)) {
            // These pins work with Wire1
            Wire1.setSDA(sda_pin);
            Wire1.setSCL(scl_pin);
            Wire1.begin();
            return true;
        } else {
            // Default pins work with Wire
            Wire.setSDA(sda_pin);
            Wire.setSCL(scl_pin);
            Wire.begin();
            return true;
        }
    #elif defined(ESP32) || defined(ESP8266)
        wire_instance.begin(sda_pin, scl_pin);
        return true;
    #else
        // Arduino Uno/Nano - ignore custom pins, use default
        wire_instance.begin();
        return true;
    #endif
}

bool QMI8658::begin(uint8_t sda_pin, uint8_t scl_pin, uint8_t address) {
    _address = address;

    #if defined(ARDUINO_ARCH_RP2040)
        // For RP2040, pins 6,7 specifically need Wire1
        if (sda_pin == 6 && scl_pin == 7) {
            Wire1.setSDA(sda_pin);
            Wire1.setSCL(scl_pin);
            Wire1.begin();
            _wire = &Wire1;
        } else {
            // Other pins use Wire
            Wire.setSDA(sda_pin);
            Wire.setSCL(scl_pin);
            Wire.begin();
            _wire = &Wire;
        }
    #elif defined(ESP32) || defined(ESP8266)
        Wire.begin(sda_pin, scl_pin);
        _wire = &Wire;
    #else
        // Arduino Uno/Nano - use default pins
        Wire.begin();
        _wire = &Wire;
    #endif

    return begin(*_wire, address);
}

bool QMI8658::setAccelRange(QMI8658_AccelRange range) {
    updateAccelScale(range);
    uint8_t ctrl2_value = (range << 4) | 0x03; // Default ODR 1000Hz
    return writeRegister(QMI8658_CTRL2, ctrl2_value);
}

bool QMI8658::setAccelODR(QMI8658_AccelODR odr) {
    uint8_t current_ctrl2;
    if (!readRegister(QMI8658_CTRL2, current_ctrl2)) {
        return false;
    }

    uint8_t new_ctrl2 = (current_ctrl2 & 0xF0) | odr;
    return writeRegister(QMI8658_CTRL2, new_ctrl2);
}

bool QMI8658::setGyroRange(QMI8658_GyroRange range) {
    updateGyroScale(range);
    uint8_t ctrl3_value = (range << 4) | 0x03; // Default ODR 1000Hz
    return writeRegister(QMI8658_CTRL3, ctrl3_value);
}

bool QMI8658::setGyroODR(QMI8658_GyroODR odr) {
    uint8_t current_ctrl3;
    if (!readRegister(QMI8658_CTRL3, current_ctrl3)) {
        return false;
    }

    uint8_t new_ctrl3 = (current_ctrl3 & 0xF0) | odr;
    return writeRegister(QMI8658_CTRL3, new_ctrl3);
}

bool QMI8658::enableAccel(bool enable) {
    uint8_t current_ctrl7;
    if (!readRegister(QMI8658_CTRL7, current_ctrl7)) {
        return false;
    }

    if (enable) {
        current_ctrl7 |= QMI8658_ENABLE_ACCEL;
    } else {
        current_ctrl7 &= ~QMI8658_ENABLE_ACCEL;
    }

    return writeRegister(QMI8658_CTRL7, current_ctrl7);
}

bool QMI8658::enableGyro(bool enable) {
    uint8_t current_ctrl7;
    if (!readRegister(QMI8658_CTRL7, current_ctrl7)) {
        return false;
    }

    if (enable) {
        current_ctrl7 |= QMI8658_ENABLE_GYRO;
    } else {
        current_ctrl7 &= ~QMI8658_ENABLE_GYRO;
    }

    return writeRegister(QMI8658_CTRL7, current_ctrl7);
}

bool QMI8658::enableSensors(uint8_t enableFlags) {
    return writeRegister(QMI8658_CTRL7, enableFlags & 0x0F);
}

bool QMI8658::readAccel(float &x, float &y, float &z) {
    uint8_t buffer[6];
    if (!readRegister(QMI8658_AX_L, buffer, 6)) {
        return false;
    }

    int16_t raw_x = combineBytes(buffer[0], buffer[1]);
    int16_t raw_y = combineBytes(buffer[2], buffer[3]);
    int16_t raw_z = combineBytes(buffer[4], buffer[5]);

    if (_accel_unit_mps2) {
        // Convert to m/s²
        x = convertAccelToMPS2(raw_x);
        y = convertAccelToMPS2(raw_y);
        z = convertAccelToMPS2(raw_z);
    } else {
        // Convert to mg
        x = convertAccelToMG(raw_x);
        y = convertAccelToMG(raw_y);
        z = convertAccelToMG(raw_z);
    }

    return true;
}

bool QMI8658::readGyro(float &x, float &y, float &z) {
    uint8_t buffer[6];
    if (!readRegister(QMI8658_GX_L, buffer, 6)) {
        return false;
    }

    int16_t raw_x = combineBytes(buffer[0], buffer[1]);
    int16_t raw_y = combineBytes(buffer[2], buffer[3]);
    int16_t raw_z = combineBytes(buffer[4], buffer[5]);

    if (_gyro_unit_rads) {
        // Convert to rad/s
        x = convertGyroToRADS(raw_x);
        y = convertGyroToRADS(raw_y);
        z = convertGyroToRADS(raw_z);
    } else {
        // Convert to dps
        x = convertGyroToDPS(raw_x);
        y = convertGyroToDPS(raw_y);
        z = convertGyroToDPS(raw_z);
    }

    return true;
}

// Alternative reading methods with specific units
bool QMI8658::readAccelMG(float &x, float &y, float &z) {
    uint8_t buffer[6];
    if (!readRegister(QMI8658_AX_L, buffer, 6)) {
        return false;
    }

    int16_t raw_x = combineBytes(buffer[0], buffer[1]);
    int16_t raw_y = combineBytes(buffer[2], buffer[3]);
    int16_t raw_z = combineBytes(buffer[4], buffer[5]);

    x = convertAccelToMG(raw_x);
    y = convertAccelToMG(raw_y);
    z = convertAccelToMG(raw_z);

    return true;
}

bool QMI8658::readAccelMPS2(float &x, float &y, float &z) {
    uint8_t buffer[6];
    if (!readRegister(QMI8658_AX_L, buffer, 6)) {
        return false;
    }

    int16_t raw_x = combineBytes(buffer[0], buffer[1]);
    int16_t raw_y = combineBytes(buffer[2], buffer[3]);
    int16_t raw_z = combineBytes(buffer[4], buffer[5]);

    x = convertAccelToMPS2(raw_x);
    y = convertAccelToMPS2(raw_y);
    z = convertAccelToMPS2(raw_z);

    return true;
}

bool QMI8658::readGyroDPS(float &x, float &y, float &z) {
    uint8_t buffer[6];
    if (!readRegister(QMI8658_GX_L, buffer, 6)) {
        return false;
    }

    int16_t raw_x = combineBytes(buffer[0], buffer[1]);
    int16_t raw_y = combineBytes(buffer[2], buffer[3]);
    int16_t raw_z = combineBytes(buffer[4], buffer[5]);

    x = convertGyroToDPS(raw_x);
    y = convertGyroToDPS(raw_y);
    z = convertGyroToDPS(raw_z);

    return true;
}

bool QMI8658::readGyroRADS(float &x, float &y, float &z) {
    uint8_t buffer[6];
    if (!readRegister(QMI8658_GX_L, buffer, 6)) {
        return false;
    }

    int16_t raw_x = combineBytes(buffer[0], buffer[1]);
    int16_t raw_y = combineBytes(buffer[2], buffer[3]);
    int16_t raw_z = combineBytes(buffer[4], buffer[5]);

    x = convertGyroToRADS(raw_x);
    y = convertGyroToRADS(raw_y);
    z = convertGyroToRADS(raw_z);

    return true;
}

bool QMI8658::readTemp(float &temperature) {
    uint8_t buffer[2];
    if (!readRegister(QMI8658_TEMP_L, buffer, 2)) {
        return false;
    }

    int16_t raw_temp = combineBytes(buffer[0], buffer[1]);
    temperature = (float)raw_temp / 256.0f;

    return true;
}

bool QMI8658::readSensorData(QMI8658_Data &data) {
    // Read timestamp
    uint8_t timestamp_buffer[3];
    if (readRegister(QMI8658_TIMESTAMP_L, timestamp_buffer, 3)) {
        uint32_t timestamp = ((uint32_t)timestamp_buffer[2] << 16) |
                           ((uint32_t)timestamp_buffer[1] << 8) |
                           timestamp_buffer[0];
        if (timestamp > _timestamp) {
            _timestamp = timestamp;
        } else {
            _timestamp = (timestamp + 0x1000000 - _timestamp);
        }
        data.timestamp = _timestamp;
    }

    // Read all sensor data at once
    uint8_t sensor_buffer[12];
    if (!readRegister(QMI8658_AX_L, sensor_buffer, 12)) {
        return false;
    }

    // Parse accelerometer data
    int16_t raw_ax = combineBytes(sensor_buffer[0], sensor_buffer[1]);
    int16_t raw_ay = combineBytes(sensor_buffer[2], sensor_buffer[3]);
    int16_t raw_az = combineBytes(sensor_buffer[4], sensor_buffer[5]);

    // Parse gyroscope data
    int16_t raw_gx = combineBytes(sensor_buffer[6], sensor_buffer[7]);
    int16_t raw_gy = combineBytes(sensor_buffer[8], sensor_buffer[9]);
    int16_t raw_gz = combineBytes(sensor_buffer[10], sensor_buffer[11]);

    // Convert accelerometer data using helper functions
    if (_accel_unit_mps2) {
        data.accelX = convertAccelToMPS2(raw_ax);
        data.accelY = convertAccelToMPS2(raw_ay);
        data.accelZ = convertAccelToMPS2(raw_az);
    } else {
        data.accelX = convertAccelToMG(raw_ax);
        data.accelY = convertAccelToMG(raw_ay);
        data.accelZ = convertAccelToMG(raw_az);
    }

    // Convert gyroscope data using helper functions
    if (_gyro_unit_rads) {
        data.gyroX = convertGyroToRADS(raw_gx);
        data.gyroY = convertGyroToRADS(raw_gy);
        data.gyroZ = convertGyroToRADS(raw_gz);
    } else {
        data.gyroX = convertGyroToDPS(raw_gx);
        data.gyroY = convertGyroToDPS(raw_gy);
        data.gyroZ = convertGyroToDPS(raw_gz);
    }

    // Read temperature
    readTemp(data.temperature);

    return true;
}

bool QMI8658::isDataReady() {
    uint8_t status;
    if (!readRegister(QMI8658_STATUS0, status)) {
        return false;
    }
    return (status & 0x03) != 0; // Check if accel or gyro data is ready
}

uint8_t QMI8658::getWhoAmI() {
    uint8_t who_am_i;
    if (!readRegister(QMI8658_WHO_AM_I, who_am_i)) {
        return 0;
    }
    return who_am_i;
}

bool QMI8658::reset() {
    // Soft reset
    return writeRegister(QMI8658_CTRL1, 0x80);
}

void QMI8658::setAccelUnit_mps2(bool use_mps2) {
    _accel_unit_mps2 = use_mps2;
}

void QMI8658::setAccelUnit_mg(bool use_mg) {
    _accel_unit_mps2 = !use_mg;  // Opposite of mg
}

void QMI8658::setGyroUnit_rads(bool use_rads) {
    _gyro_unit_rads = use_rads;
}

void QMI8658::setGyroUnit_dps(bool use_dps) {
    _gyro_unit_rads = !use_dps;  // Opposite of dps
}

// Display precision configuration
void QMI8658::setDisplayPrecision(int decimals) {
    if (decimals >= 0 && decimals <= 10) {  // Reasonable range
        _display_precision = decimals;
    }
}

void QMI8658::setDisplayPrecision(QMI8658_Precision precision) {
    _display_precision = (int)precision;
}

int QMI8658::getDisplayPrecision() {
    return _display_precision;
}

// Get current unit settings
bool QMI8658::isAccelUnit_mps2() {
    return _accel_unit_mps2;
}

bool QMI8658::isAccelUnit_mg() {
    return !_accel_unit_mps2;
}

bool QMI8658::isGyroUnit_rads() {
    return _gyro_unit_rads;
}

bool QMI8658::isGyroUnit_dps() {
    return !_gyro_unit_rads;
}

// Print formatted sensor data
// NOTE (patch): replaced Arduino String objects with const char* literals.
void QMI8658::printSensorData(QMI8658_Data &data) {
    printSensorData(data, _display_precision);
}

void QMI8658::printSensorData(QMI8658_Data &data, int precision) {
    const char* accel_unit = _accel_unit_mps2 ? "m/s^2" : "mg";
    const char* gyro_unit  = _gyro_unit_rads  ? "rad/s" : "dps";

    Serial.print("ACC_X = "); Serial.print(data.accelX, precision); Serial.print(" "); Serial.println(accel_unit);
    Serial.print("ACC_Y = "); Serial.print(data.accelY, precision); Serial.print(" "); Serial.println(accel_unit);
    Serial.print("ACC_Z = "); Serial.print(data.accelZ, precision); Serial.print(" "); Serial.println(accel_unit);
    Serial.print("GYR_X = "); Serial.print(data.gyroX, precision); Serial.print(" "); Serial.println(gyro_unit);
    Serial.print("GYR_Y = "); Serial.print(data.gyroY, precision); Serial.print(" "); Serial.println(gyro_unit);
    Serial.print("GYR_Z = "); Serial.print(data.gyroZ, precision); Serial.print(" "); Serial.println(gyro_unit);
    Serial.print("TEMP  = "); Serial.print(data.temperature, 1); Serial.println(" C");
}

// Unit conversion helpers
float QMI8658::convertAccelToMG(int16_t raw_value) {
    return (raw_value * 1000.0f) / _accel_lsb_div;
}

float QMI8658::convertAccelToMPS2(int16_t raw_value) {
    return (raw_value * ONE_G) / _accel_lsb_div;
}

float QMI8658::convertGyroToDPS(int16_t raw_value) {
    return (float)raw_value / _gyro_lsb_div;
}

float QMI8658::convertGyroToRADS(int16_t raw_value) {
    return (raw_value * 0.01745f) / _gyro_lsb_div; // * pi/180
}

bool QMI8658::enableWakeOnMotion(uint8_t threshold) {
    // Disable all sensors first
    enableSensors(QMI8658_DISABLE_ALL);

    // Configure accelerometer for low power mode
    setAccelRange(QMI8658_ACCEL_RANGE_2G);
    setAccelODR(QMI8658_ACCEL_ODR_LOWPOWER_21HZ);

    // Set wake-on-motion threshold
    if (!writeRegister(0x0B, threshold)) { // Cal1_L register
        return false;
    }

    if (!writeRegister(0x0C, 0x00)) { // Cal1_H register
        return false;
    }

    // Enable accelerometer
    return enableSensors(QMI8658_ENABLE_ACCEL);
}

bool QMI8658::disableWakeOnMotion() {
    enableSensors(QMI8658_DISABLE_ALL);
    return writeRegister(0x0B, 0x00); // Clear Cal1_L register
}

// Private methods
bool QMI8658::writeRegister(uint8_t reg, uint8_t value) {
    if (!_wire) return false;

    _wire->beginTransmission(_address);
    _wire->write(reg);
    _wire->write(value);
    uint8_t error = _wire->endTransmission();

    return (error == 0);
}

bool QMI8658::readRegister(uint8_t reg, uint8_t *buffer, uint8_t length) {
    if (!_wire) return false;

    _wire->beginTransmission(_address);
    _wire->write(reg);
    uint8_t error = _wire->endTransmission(false);

    if (error != 0) return false;

    uint8_t received = _wire->requestFrom(_address, length);
    if (received != length) return false;

    for (uint8_t i = 0; i < length; i++) {
        buffer[i] = _wire->read();
    }

    return true;
}

bool QMI8658::readRegister(uint8_t reg, uint8_t &value) {
    return readRegister(reg, &value, 1);
}

void QMI8658::updateAccelScale(QMI8658_AccelRange range) {
    switch (range) {
        case QMI8658_ACCEL_RANGE_2G:
            _accel_lsb_div = 16384; // 2^14
            break;
        case QMI8658_ACCEL_RANGE_4G:
            _accel_lsb_div = 8192;  // 2^13
            break;
        case QMI8658_ACCEL_RANGE_8G:
            _accel_lsb_div = 4096;  // 2^12
            break;
        case QMI8658_ACCEL_RANGE_16G:
            _accel_lsb_div = 2048;  // 2^11
            break;
        default:
            _accel_lsb_div = 4096;  // Default to 8g
            break;
    }
}

void QMI8658::updateGyroScale(QMI8658_GyroRange range) {
    switch (range) {
        case QMI8658_GYRO_RANGE_32DPS:
            _gyro_lsb_div = 1024;
            break;
        case QMI8658_GYRO_RANGE_64DPS:
            _gyro_lsb_div = 512;
            break;
        case QMI8658_GYRO_RANGE_128DPS:
            _gyro_lsb_div = 256;
            break;
        case QMI8658_GYRO_RANGE_256DPS:
            _gyro_lsb_div = 128;
            break;
        case QMI8658_GYRO_RANGE_512DPS:
            _gyro_lsb_div = 64;
            break;
        case QMI8658_GYRO_RANGE_1024DPS:
            _gyro_lsb_div = 32;
            break;
        case QMI8658_GYRO_RANGE_2048DPS:
            _gyro_lsb_div = 16;
            break;
        case QMI8658_GYRO_RANGE_4096DPS:
            _gyro_lsb_div = 8;
            break;
        default:
            _gyro_lsb_div = 64; // Default to 512dps
            break;
    }
}

int16_t QMI8658::combineBytes(uint8_t lsb, uint8_t msb) {
    return (int16_t)((uint16_t)msb << 8 | lsb);
}
