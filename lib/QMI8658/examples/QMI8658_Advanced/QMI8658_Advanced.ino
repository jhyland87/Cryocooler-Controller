/*
  QMI8658 Advanced Example
  
  This example demonstrates advanced features of the QMI8658 library:
  - Motion detection
  - Data filtering
  - Orientation calculation
  - Calibration
  
  Hardware connections:
  - VCC to 3.3V
  - GND to GND
  - SDA to pin 21 (ESP32) or A4 (Arduino)
  - SCL to pin 22 (ESP32) or A5 (Arduino)
  
  Author: [Your Name]
*/

#include <QMI8658.h>
#include <math.h>

QMI8658 imu;

// Pin definitions (adjust for your board)
#define SDA_PIN 21  // ESP32 default
#define SCL_PIN 22  // ESP32 default

// Motion detection variables
float accelThreshold = 2.0;  // m/s² threshold for motion detection
bool motionDetected = false;
unsigned long lastMotionTime = 0;

// Calibration variables
float accelOffsetX = 0, accelOffsetY = 0, accelOffsetZ = 0;
float gyroOffsetX = 0, gyroOffsetY = 0, gyroOffsetZ = 0;
bool calibrated = false;

// Filter variables (simple low-pass filter)
float filteredAccelX = 0, filteredAccelY = 0, filteredAccelZ = 0;
float filteredGyroX = 0, filteredGyroY = 0, filteredGyroZ = 0;
const float alpha = 0.1; // Filter coefficient (0-1, lower = more filtering)

void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);
    
    Serial.println("QMI8658 Advanced Example");
    Serial.println("========================");
    
    // Initialize IMU
    if (!imu.begin(SDA_PIN, SCL_PIN)) {
        Serial.println("❌ Failed to initialize QMI8658!");
        Serial.println("Check connections and try again.");
        while (1) delay(1000);
    }
    
    Serial.println("✅ QMI8658 initialized successfully!");
    Serial.print("Device ID: 0x");
    Serial.println(imu.getWhoAmI(), HEX);
    
    // Configure sensor
    Serial.println("\n🔧 Configuring sensor...");
    imu.setAccelRange(QMI8658_ACCEL_RANGE_8G);
    imu.setAccelODR(QMI8658_ACCEL_ODR_1000HZ);
    imu.setGyroRange(QMI8658_GYRO_RANGE_512DPS);
    imu.setGyroODR(QMI8658_GYRO_ODR_1000HZ);
    
    // Set units
    imu.setAccelUnit_mps2(true);  // m/s²
    imu.setGyroUnit_rads(false);  // degrees per second
    
    // Enable sensors
    imu.enableSensors(QMI8658_ENABLE_ACCEL | QMI8658_ENABLE_GYRO);
    
    Serial.println("✅ Configuration complete!");
    
    // Perform calibration
    performCalibration();
    
    Serial.println("\n📊 Starting sensor readings...");
    Serial.println("Time(ms)\tMotion\tRoll\tPitch\tYaw\tAccel_Mag\tGyro_Mag\tTemp(°C)");
    Serial.println("-------------------------------------------------------------------------");
}

void loop() {
    QMI8658_Data data;
    
    if (imu.readSensorData(data)) {
        // Apply calibration offsets
        float accelX = data.accelX - accelOffsetX;
        float accelY = data.accelY - accelOffsetY;
        float accelZ = data.accelZ - accelOffsetZ;
        
        float gyroX = data.gyroX - gyroOffsetX;
        float gyroY = data.gyroY - gyroOffsetY;
        float gyroZ = data.gyroZ - gyroOffsetZ;
        
        // Apply low-pass filter
        filteredAccelX = alpha * accelX + (1 - alpha) * filteredAccelX;
        filteredAccelY = alpha * accelY + (1 - alpha) * filteredAccelY;
        filteredAccelZ = alpha * accelZ + (1 - alpha) * filteredAccelZ;
        
        filteredGyroX = alpha * gyroX + (1 - alpha) * filteredGyroX;
        filteredGyroY = alpha * gyroY + (1 - alpha) * filteredGyroY;
        filteredGyroZ = alpha * gyroZ + (1 - alpha) * filteredGyroZ;
        
        // Calculate orientation (roll, pitch, yaw)
        float roll, pitch, yaw;
        calculateOrientation(filteredAccelX, filteredAccelY, filteredAccelZ,
                           filteredGyroX, filteredGyroY, filteredGyroZ,
                           roll, pitch, yaw);
        
        // Motion detection
        float accelMagnitude = sqrt(accelX*accelX + accelY*accelY + accelZ*accelZ);
        float gyroMagnitude = sqrt(gyroX*gyroX + gyroY*gyroY + gyroZ*gyroZ);
        
        checkMotion(accelMagnitude, gyroMagnitude);
        
        // Print results
        Serial.print(millis());
        Serial.print("\t");
        Serial.print(motionDetected ? "YES" : "NO");
        Serial.print("\t");
        Serial.print(roll, 1);
        Serial.print("\t");
        Serial.print(pitch, 1);
        Serial.print("\t");
        Serial.print(yaw, 1);
        Serial.print("\t");
        Serial.print(accelMagnitude, 2);
        Serial.print("\t");
        Serial.print(gyroMagnitude, 2);
        Serial.print("\t");
        Serial.println(data.temperature, 1);
        
        // Check for calibration command
        if (Serial.available()) {
            String command = Serial.readString();
            command.trim();
            if (command == "cal" || command == "calibrate") {
                Serial.println("\n🔄 Recalibrating...");
                performCalibration();
            }
        }
    }
    
    delay(50); // 20Hz update rate
}

void performCalibration() {
    Serial.println("\n🎯 Starting calibration...");
    Serial.println("Place the sensor on a flat, stable surface.");
    Serial.println("Calibration will start in 3 seconds...");
    
    for (int i = 3; i > 0; i--) {
        Serial.print(i);
        Serial.println("...");
        delay(1000);
    }
    
    Serial.println("📈 Collecting calibration data...");
    
    const int numSamples = 1000;
    float accelSumX = 0, accelSumY = 0, accelSumZ = 0;
    float gyroSumX = 0, gyroSumY = 0, gyroSumZ = 0;
    int validSamples = 0;
    
    for (int i = 0; i < numSamples; i++) {
        QMI8658_Data data;
        if (imu.readSensorData(data)) {
            accelSumX += data.accelX;
            accelSumY += data.accelY;
            accelSumZ += data.accelZ;
            
            gyroSumX += data.gyroX;
            gyroSumY += data.gyroY;
            gyroSumZ += data.gyroZ;
            
            validSamples++;
        }
        
        if (i % 100 == 0) {
            Serial.print(".");
        }
        
        delay(10);
    }
    
    if (validSamples > 0) {
        // Calculate offsets
        accelOffsetX = accelSumX / validSamples;
        accelOffsetY = accelSumY / validSamples;
        accelOffsetZ = (accelSumZ / validSamples) - 9.81; // Remove gravity
        
        gyroOffsetX = gyroSumX / validSamples;
        gyroOffsetY = gyroSumY / validSamples;
        gyroOffsetZ = gyroSumZ / validSamples;
        
        calibrated = true;
        
        Serial.println("\n✅ Calibration complete!");
        Serial.print("Accel offsets: ");
        Serial.print(accelOffsetX, 3); Serial.print(", ");
        Serial.print(accelOffsetY, 3); Serial.print(", ");
        Serial.println(accelOffsetZ, 3);
        
        Serial.print("Gyro offsets: ");
        Serial.print(gyroOffsetX, 3); Serial.print(", ");
        Serial.print(gyroOffsetY, 3); Serial.print(", ");
        Serial.println(gyroOffsetZ, 3);
        
        Serial.println("💡 Type 'cal' to recalibrate anytime.");
    } else {
        Serial.println("\n❌ Calibration failed! No valid samples collected.");
    }
}

void calculateOrientation(float ax, float ay, float az, 
                         float gx, float gy, float gz,
                         float &roll, float &pitch, float &yaw) {
    // Calculate roll and pitch from accelerometer
    roll = atan2(ay, sqrt(ax * ax + az * az)) * 180.0 / M_PI;
    pitch = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / M_PI;
    
    // Simple yaw integration from gyroscope (not accurate for long term)
    static float yawIntegrated = 0;
    static unsigned long lastTime = 0;
    
    unsigned long currentTime = millis();
    if (lastTime > 0) {
        float dt = (currentTime - lastTime) / 1000.0; // Convert to seconds
        yawIntegrated += gz * dt;
    }
    lastTime = currentTime;
    
    yaw = yawIntegrated;
    
    // Keep yaw in range [-180, 180]
    while (yaw > 180) yaw -= 360;
    while (yaw < -180) yaw += 360;
}

void checkMotion(float accelMag, float gyroMag) {
    // Check if current acceleration deviates significantly from gravity
    float accelDeviation = abs(accelMag - 9.81);
    
    if (accelDeviation > accelThreshold || gyroMag > 10.0) {
        if (!motionDetected) {
            Serial.println("\n🚶 Motion detected!");
        }
        motionDetected = true;
        lastMotionTime = millis();
    } else {
        // No motion for 2 seconds
        if (motionDetected && (millis() - lastMotionTime > 2000)) {
            Serial.println("🛑 Motion stopped.");
            motionDetected = false;
        }
    }
}
