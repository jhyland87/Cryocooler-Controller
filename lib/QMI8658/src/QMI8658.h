/*
  QMI8658 - Arduino Library for QMI8658 6-Axis IMU Sensor
  
  This library provides an easy interface to communicate with the QMI8658
  6-axis inertial measurement unit (IMU) sensor via I2C.
  
  Features:
  - 3-axis accelerometer
  - 3-axis gyroscope
  - Temperature sensor
  - Configurable ranges and output data rates
  - Wake-on-motion functionality
  
  Author: [Your Name]
  Version: 1.0.0
  License: MIT
*/

#ifndef QMI8658_H
#define QMI8658_H

#include <Arduino.h>
#include <Wire.h>

// Make sure Wire1 is available on RP2040
#if defined(ARDUINO_ARCH_RP2040)
extern TwoWire Wire1;
#endif

// Library version
#define QMI8658_LIBRARY_VERSION "1.0.0"

// Default I2C addresses
#define QMI8658_ADDRESS_LOW  0x6A
#define QMI8658_ADDRESS_HIGH 0x6B

// Physical constants
#ifndef M_PI
#define M_PI (3.14159265358979323846f)
#endif
#ifndef ONE_G
#define ONE_G (9.807f)
#endif

// Sensor enable flags
#define QMI8658_DISABLE_ALL    0x00
#define QMI8658_ENABLE_ACCEL   0x01
#define QMI8658_ENABLE_GYRO    0x02
#define QMI8658_ENABLE_MAG     0x04
#define QMI8658_ENABLE_AE      0x08

// Register addresses
enum QMI8658_Register {
    QMI8658_WHO_AM_I        = 0x00,
    QMI8658_REVISION        = 0x01,
    QMI8658_CTRL1          = 0x02,
    QMI8658_CTRL2          = 0x03,  // Accelerometer control
    QMI8658_CTRL3          = 0x04,  // Gyroscope control
    QMI8658_CTRL4          = 0x05,  // Magnetometer control
    QMI8658_CTRL5          = 0x06,  // Data processing settings
    QMI8658_CTRL6          = 0x07,  // AttitudeEngine control
    QMI8658_CTRL7          = 0x08,  // Sensor enable status
    QMI8658_CTRL8          = 0x09,
    QMI8658_CTRL9          = 0x0A,
    QMI8658_STATUS0        = 0x2E,
    QMI8658_STATUS1        = 0x2F,
    QMI8658_TIMESTAMP_L    = 0x30,
    QMI8658_TIMESTAMP_M    = 0x31,
    QMI8658_TIMESTAMP_H    = 0x32,
    QMI8658_TEMP_L         = 0x33,
    QMI8658_TEMP_H         = 0x34,
    QMI8658_AX_L           = 0x35,
    QMI8658_AX_H           = 0x36,
    QMI8658_AY_L           = 0x37,
    QMI8658_AY_H           = 0x38,
    QMI8658_AZ_L           = 0x39,
    QMI8658_AZ_H           = 0x3A,
    QMI8658_GX_L           = 0x3B,
    QMI8658_GX_H           = 0x3C,
    QMI8658_GY_L           = 0x3D,
    QMI8658_GY_H           = 0x3E,
    QMI8658_GZ_L           = 0x3F,
    QMI8658_GZ_H           = 0x40
};

// Accelerometer range options
enum QMI8658_AccelRange {
    QMI8658_ACCEL_RANGE_2G  = 0x00,
    QMI8658_ACCEL_RANGE_4G  = 0x01,
    QMI8658_ACCEL_RANGE_8G  = 0x02,
    QMI8658_ACCEL_RANGE_16G = 0x03
};

// Accelerometer output data rate options
enum QMI8658_AccelODR {
    QMI8658_ACCEL_ODR_8000HZ    = 0x00,
    QMI8658_ACCEL_ODR_4000HZ    = 0x01,
    QMI8658_ACCEL_ODR_2000HZ    = 0x02,
    QMI8658_ACCEL_ODR_1000HZ    = 0x03,
    QMI8658_ACCEL_ODR_500HZ     = 0x04,
    QMI8658_ACCEL_ODR_250HZ     = 0x05,
    QMI8658_ACCEL_ODR_125HZ     = 0x06,
    QMI8658_ACCEL_ODR_62_5HZ    = 0x07,
    QMI8658_ACCEL_ODR_31_25HZ   = 0x08,
    QMI8658_ACCEL_ODR_LOWPOWER_128HZ = 0x0C,
    QMI8658_ACCEL_ODR_LOWPOWER_21HZ  = 0x0D,
    QMI8658_ACCEL_ODR_LOWPOWER_11HZ  = 0x0E,
    QMI8658_ACCEL_ODR_LOWPOWER_3HZ   = 0x0F
};

// Gyroscope range options
enum QMI8658_GyroRange {
    QMI8658_GYRO_RANGE_32DPS   = 0x00,
    QMI8658_GYRO_RANGE_64DPS   = 0x01,
    QMI8658_GYRO_RANGE_128DPS  = 0x02,
    QMI8658_GYRO_RANGE_256DPS  = 0x03,
    QMI8658_GYRO_RANGE_512DPS  = 0x04,
    QMI8658_GYRO_RANGE_1024DPS = 0x05,
    QMI8658_GYRO_RANGE_2048DPS = 0x06,
    QMI8658_GYRO_RANGE_4096DPS = 0x07
};

// Gyroscope output data rate options
enum QMI8658_GyroODR {
    QMI8658_GYRO_ODR_8000HZ   = 0x00,
    QMI8658_GYRO_ODR_4000HZ   = 0x01,
    QMI8658_GYRO_ODR_2000HZ   = 0x02,
    QMI8658_GYRO_ODR_1000HZ   = 0x03,
    QMI8658_GYRO_ODR_500HZ    = 0x04,
    QMI8658_GYRO_ODR_250HZ    = 0x05,
    QMI8658_GYRO_ODR_125HZ    = 0x06,
    QMI8658_GYRO_ODR_62_5HZ   = 0x07,
    QMI8658_GYRO_ODR_31_25HZ  = 0x08
};

// Data structure for sensor readings
struct QMI8658_Data {
    float accelX, accelY, accelZ;  // Acceleration (units depend on setting: m/s² or mg)
    float gyroX, gyroY, gyroZ;     // Angular velocity (units depend on setting: dps or rad/s)
    float temperature;             // Temperature in °C
    uint32_t timestamp;            // Internal timestamp
};

// Display precision options
enum QMI8658_Precision {
    QMI8658_PRECISION_2 = 2,    // 2 decimal places (e.g., 9.81)
    QMI8658_PRECISION_4 = 4,    // 4 decimal places (e.g., 9.8100)
    QMI8658_PRECISION_6 = 6     // 6 decimal places (e.g., 9.810000)
};

class QMI8658 {
public:
    // Constructor
    QMI8658();
    
    // Initialization methods
    bool begin(TwoWire &wire = Wire, uint8_t address = QMI8658_ADDRESS_LOW);
    bool begin(uint8_t sda_pin, uint8_t scl_pin, uint8_t address = QMI8658_ADDRESS_LOW);
    
    // Configuration methods
    bool setAccelRange(QMI8658_AccelRange range);
    bool setAccelODR(QMI8658_AccelODR odr);
    bool setGyroRange(QMI8658_GyroRange range);
    bool setGyroODR(QMI8658_GyroODR odr);
    
    // Enable/disable sensors
    bool enableAccel(bool enable = true);
    bool enableGyro(bool enable = true);
    bool enableSensors(uint8_t enableFlags);
    
    // Data reading methods
    bool readAccel(float &x, float &y, float &z);
    bool readGyro(float &x, float &y, float &z);
    bool readTemp(float &temperature);
    bool readSensorData(QMI8658_Data &data);
    
    // Alternative reading methods with specific units
    bool readAccelMG(float &x, float &y, float &z);     // Always returns mg
    bool readAccelMPS2(float &x, float &y, float &z);   // Always returns m/s²
    bool readGyroDPS(float &x, float &y, float &z);     // Always returns dps
    bool readGyroRADS(float &x, float &y, float &z);    // Always returns rad/s
    
    // Utility methods
    bool isDataReady();
    uint8_t getWhoAmI();
    bool reset();
    
    // Unit configuration (affects readAccel, readGyro, readSensorData)
    void setAccelUnit_mps2(bool use_mps2 = true);  // true = m/s², false = mg
    void setAccelUnit_mg(bool use_mg = true);      // true = mg, false = m/s² (opposite of above)
    void setGyroUnit_rads(bool use_rads = true);   // true = rad/s, false = dps
    void setGyroUnit_dps(bool use_dps = true);     // true = dps, false = rad/s (opposite of above)
    
    // Display precision configuration
    void setDisplayPrecision(int decimals);        // Set decimal places for readSensorData output
    void setDisplayPrecision(QMI8658_Precision precision); // Use enum for precision
    int getDisplayPrecision();                     // Get current precision setting
    
    // Get current unit settings (for display/logging purposes)
    bool isAccelUnit_mps2();    // Returns true if accelerometer is set to m/s²
    bool isAccelUnit_mg();      // Returns true if accelerometer is set to mg
    bool isGyroUnit_rads();     // Returns true if gyroscope is set to rad/s
    bool isGyroUnit_dps();      // Returns true if gyroscope is set to dps
    
    // Wake on motion
    bool enableWakeOnMotion(uint8_t threshold = 32);
    bool disableWakeOnMotion();
    
    // Print formatted sensor data (helper function)
    void printSensorData(QMI8658_Data &data);     // Print with current precision and units
    void printSensorData(QMI8658_Data &data, int precision); // Print with specified precision
    
private:
    TwoWire *_wire;
    uint8_t _address;
    uint16_t _accel_lsb_div;
    uint16_t _gyro_lsb_div;
    bool _accel_unit_mps2;  // true = m/s², false = mg
    bool _gyro_unit_rads;   // true = rad/s, false = dps
    int _display_precision; // Number of decimal places for display
    uint32_t _timestamp;
    
    // Private methods
    bool writeRegister(uint8_t reg, uint8_t value);
    bool readRegister(uint8_t reg, uint8_t *buffer, uint8_t length);
    bool readRegister(uint8_t reg, uint8_t &value);
    void updateAccelScale(QMI8658_AccelRange range);
    void updateGyroScale(QMI8658_GyroRange range);
    int16_t combineBytes(uint8_t lsb, uint8_t msb);
    
    // Unit conversion helpers
    float convertAccelToMG(int16_t raw_value);
    float convertAccelToMPS2(int16_t raw_value);
    float convertGyroToDPS(int16_t raw_value);
    float convertGyroToRADS(int16_t raw_value);
};

#endif // QMI8658_H
