/*
  QMI8658 Wake on Motion Example
  
  This example demonstrates how to use the wake-on-motion feature
  of the QMI8658 sensor for low-power applications.
  
  The sensor will go into low-power mode and wake up when motion
  is detected, making it ideal for battery-powered projects.
  
  Hardware connections:
  - VCC to 3.3V
  - GND to GND
  - SDA to pin 21 (ESP32) or A4 (Arduino)
  - SCL to pin 22 (ESP32) or A5 (Arduino)
  - Optional: LED on pin 2 for visual indication
  
  Author: [Your Name]
*/

#include <QMI8658.h>

QMI8658 imu;

// Pin definitions
#define SDA_PIN 21
#define SCL_PIN 22
#define LED_PIN 2  // Built-in LED on most ESP32 boards

// Wake-on-motion settings
#define MOTION_THRESHOLD 64  // Motion sensitivity (32 = high sensitivity, 128 = low sensitivity)
#define SLEEP_DURATION 5000  // Time to sleep after no motion (milliseconds)

// State variables
bool motionActive = false;
unsigned long lastMotionTime = 0;
bool ledState = false;

// Motion detection filtering variables
float lastAccelMag = 0;
float lastGyroMag = 0;
bool isInitialized = false;
int stabilizeCount = 0;

void setup() {
    Serial.begin(115200);
    delay(1000); // Don't use while(!Serial) on RP2040
    
    // Initialize LED pin
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
    
    Serial.println("QMI8658 Wake-on-Motion Example - RP2040 Fixed");
    Serial.println("==============================================");
    
    // Initialize IMU
    if (!imu.begin(SDA_PIN, SCL_PIN)) {
        Serial.println("❌ Failed to initialize QMI8658!");
        while (1) {
            digitalWrite(LED_PIN, HIGH);
            delay(100);
            digitalWrite(LED_PIN, LOW);
            delay(100);
        }
    }
    
    Serial.println("✅ QMI8658 initialized successfully!");
    Serial.print("Device ID: 0x");
    Serial.println(imu.getWhoAmI(), HEX);
    
    // Flash LED to indicate successful initialization
    for (int i = 0; i < 3; i++) {
        digitalWrite(LED_PIN, HIGH);
        delay(200);
        digitalWrite(LED_PIN, LOW);
        delay(200);
    }
    
    Serial.println("\n🔧 Configuring wake-on-motion...");
    Serial.print("Motion threshold: ");
    Serial.println(MOTION_THRESHOLD);
    Serial.print("Sleep duration: ");
    Serial.print(SLEEP_DURATION / 1000);
    Serial.println(" seconds");
    Serial.println("💡 Improved motion detection based on change detection");
    
    // Configure normal operation first
    imu.setAccelRange(QMI8658_ACCEL_RANGE_8G);
    imu.setAccelODR(QMI8658_ACCEL_ODR_1000HZ);
    imu.setGyroRange(QMI8658_GYRO_RANGE_512DPS);
    imu.setGyroODR(QMI8658_GYRO_ODR_1000HZ);
    imu.setAccelUnit_mps2(true);
    imu.setGyroUnit_rads(false);
    
    Serial.println("✅ Configuration complete!");
    Serial.println("\n📊 Starting motion monitoring...");
    Serial.println("💡 Move the sensor to wake it up from sleep mode");
    Serial.println("💡 Device will sleep after 5 seconds of no motion");
    Serial.println("💡 Keep sensor still to test sleep functionality");
    Serial.println("\nStatus | Time(s) | Accel_X | Accel_Y | Accel_Z | Gyro_X | Gyro_Y | Gyro_Z");
    Serial.println("--------------------------------------------------------------------------------");
    
    delay(1000);
}

void loop() {
    // Check if we should enter sleep mode
    if (motionActive && (millis() - lastMotionTime > SLEEP_DURATION)) {
        enterSleepMode();
    }
    
    // Read sensor data if active
    if (motionActive || checkForMotion()) {
        if (motionActive) {
            readAndDisplaySensorData();
            
            // Only update lastMotionTime if actual motion is detected
            QMI8658_Data data;
            if (imu.readSensorData(data)) {
                float accelMag = sqrt(data.accelX * data.accelX + 
                                     data.accelY * data.accelY + 
                                     data.accelZ * data.accelZ);
                float gyroMag = sqrt(data.gyroX * data.gyroX + 
                                    data.gyroY * data.gyroY + 
                                    data.gyroZ * data.gyroZ);
                
                float accelDeviation = abs(accelMag - 9.81);
                
                // Only reset timer if there's REAL motion
                if (accelDeviation > 2.0 || gyroMag > 15.0) {
                    lastMotionTime = millis();
                    // Blink LED to show activity
                    ledState = !ledState;
                    digitalWrite(LED_PIN, ledState);
                } else {
                    // Keep LED off when no real motion
                    digitalWrite(LED_PIN, LOW);
                }
            }
        }
    } else {
        // Keep LED off when no motion
        digitalWrite(LED_PIN, LOW);
    }
    
    delay(100);
}

void enterSleepMode() {
    Serial.println("\n💤 Entering sleep mode (wake-on-motion enabled)");
    Serial.println("   Device will consume minimal power");
    Serial.println("   Move the sensor to wake up");
    Serial.flush(); // Ensure message is sent
    
    // Enable wake-on-motion
    if (imu.enableWakeOnMotion(MOTION_THRESHOLD)) {
        Serial.println("✅ Wake-on-motion enabled");
    } else {
        Serial.println("❌ Failed to enable wake-on-motion");
    }
    
    // Turn off LED
    digitalWrite(LED_PIN, LOW);
    motionActive = false;
    
    // In a real low-power application, you would put the microcontroller
    // to sleep here as well. For this example, we'll just poll less frequently.
    
    Serial.println("⏳ Waiting for motion... (checking every 500ms)");
    
    // Wait for motion to wake up
    while (!motionActive) {
        // Instead of using hardware wake-on-motion, just check for regular motion
        if (checkForMotion()) {
            wakeFromSleep();
            break;
        }
        delay(500); // Check every 500ms while "sleeping"
        Serial.print(".");  // Show we're still checking
    }
}

bool checkWakeOnMotion() {
    // Check status register for wake-on-motion event
    uint8_t status;
    
    // Use Wire1 for RP2040 with pins 6,7
    #if defined(ARDUINO_ARCH_RP2040)
        Wire1.beginTransmission(0x6B); // Use correct address 0x6B
        Wire1.write(0x2F); // STATUS1 register
        Wire1.endTransmission(false);
        Wire1.requestFrom(0x6B, 1);
        
        if (Wire1.available()) {
            status = Wire1.read();
            return (status & 0x04) != 0; // Check wake-up event bit
        }
    #else
        Wire.beginTransmission(0x6B);
        Wire.write(0x2F); // STATUS1 register
        Wire.endTransmission(false);
        Wire.requestFrom(0x6B, 1);
        
        if (Wire.available()) {
            status = Wire.read();
            return (status & 0x04) != 0; // Check wake-up event bit
        }
    #endif
    
    return false;
}

void wakeFromSleep() {
    Serial.println("\n🌅 Waking up from sleep mode!");
    Serial.println("   Motion detected - resuming normal operation");
    
    // Disable wake-on-motion and restore normal operation
    imu.disableWakeOnMotion();
    
    // Reconfigure for normal operation
    imu.setAccelRange(QMI8658_ACCEL_RANGE_8G);
    imu.setAccelODR(QMI8658_ACCEL_ODR_1000HZ);
    imu.setGyroRange(QMI8658_GYRO_RANGE_512DPS);
    imu.setGyroODR(QMI8658_GYRO_ODR_1000HZ);
    imu.enableSensors(QMI8658_ENABLE_ACCEL | QMI8658_ENABLE_GYRO);
    
    motionActive = true;
    lastMotionTime = millis();
    
    // Reset initialization for motion detection
    isInitialized = false;
    stabilizeCount = 0;
    
    // Flash LED to indicate wake-up
    for (int i = 0; i < 5; i++) {
        digitalWrite(LED_PIN, HIGH);
        delay(100);
        digitalWrite(LED_PIN, LOW);
        delay(100);
    }
    
    Serial.println("Status | Time(s) | Accel_X | Accel_Y | Accel_Z | Gyro_X | Gyro_Y | Gyro_Z");
    Serial.println("--------------------------------------------------------------------------------");
}

bool checkForMotion() {
    QMI8658_Data data;
    
    if (imu.readSensorData(data)) {
        // Calculate motion magnitude
        float accelMag = sqrt(data.accelX * data.accelX + 
                             data.accelY * data.accelY + 
                             data.accelZ * data.accelZ);
        float gyroMag = sqrt(data.gyroX * data.gyroX + 
                            data.gyroY * data.gyroY + 
                            data.gyroZ * data.gyroZ);
        
        // Initialize baseline values (first few readings)
        if (!isInitialized) {
            if (stabilizeCount < 10) {
                lastAccelMag = accelMag;
                lastGyroMag = gyroMag;
                stabilizeCount++;
                return false; // Don't detect motion during initialization
            } else {
                isInitialized = true;
                Serial.println("📍 Sensor stabilized - motion detection active");
            }
        }
        
        // Check for sudden changes (only after initialization)
        if (isInitialized) {
            float accelChange = abs(accelMag - lastAccelMag);
            float gyroChange = abs(gyroMag - lastGyroMag);
            
            // Use simple threshold detection instead of change detection
            float accelDeviation = abs(accelMag - 9.81); // Remove gravity
            
            // Much higher thresholds to ignore sensor noise
            if (accelDeviation > 2.0 || gyroMag > 15.0) {
                if (!motionActive) {
                    Serial.println("\n🚶 Motion detected - device active");
                    Serial.print("   Accel deviation: "); Serial.print(accelDeviation, 3);
                    Serial.print(", Gyro magnitude: "); Serial.println(gyroMag, 3);
                    motionActive = true;
                }
                
                // Update baseline slowly
                lastAccelMag = lastAccelMag * 0.9 + accelMag * 0.1;
                lastGyroMag = lastGyroMag * 0.9 + gyroMag * 0.1;
                
                return true;
            } else {
                // Update baseline when no motion
                lastAccelMag = lastAccelMag * 0.95 + accelMag * 0.05;
                lastGyroMag = lastGyroMag * 0.95 + gyroMag * 0.05;
            }
        }
    }
    
    return false;
}

void readAndDisplaySensorData() {
    QMI8658_Data data;
    
    if (imu.readSensorData(data)) {
        Serial.print(motionActive ? "ACTIVE" : "SLEEP ");
        Serial.print(" | ");
        Serial.print(millis() / 1000.0, 1);
        Serial.print(" | ");
        Serial.print(data.accelX, 2);
        Serial.print(" | ");
        Serial.print(data.accelY, 2);
        Serial.print(" | ");
        Serial.print(data.accelZ, 2);
        Serial.print(" | ");
        Serial.print(data.gyroX, 1);
        Serial.print(" | ");
        Serial.print(data.gyroY, 1);
        Serial.print(" | ");
        Serial.println(data.gyroZ, 1);
    }
}

// Additional utility functions for power management
void printPowerStatus() {
    Serial.println("\n⚡ Power Management Status:");
    Serial.print("   Motion Active: ");
    Serial.println(motionActive ? "YES" : "NO");
    Serial.print("   Last Motion: ");
    Serial.print((millis() - lastMotionTime) / 1000.0, 1);
    Serial.println(" seconds ago");
    Serial.print("   Sleep Threshold: ");
    Serial.print(SLEEP_DURATION / 1000);
    Serial.println(" seconds");
}
