/**
 * @file rgb_cycle_example.cpp
 * @brief Non-blocking RGB LED cycle example for ESP32-S3-DevKitC-1-N32R16V
 *
 * Cycles the onboard WS2812 LED (GPIO 38) through Red → Green → Blue,
 * stepping up through a brightness table each time the colour sequence wraps.
 * Uses neopixelWrite() (built into the ESP32 Arduino core) instead of
 * FastLED. No blocking calls, no library dependencies.
 *
 * neopixelWrite() initialises the RMT channel once and reuses it on
 * subsequent calls, unlike FastLED which calls rmtInit() on every show().
 */

 #include <Arduino.h>
 #include <array>
 #include <cinttypes>
 #include <cstdint>


 #define RGB_LED_PIN 38

 // ---------------------------------------------------------------------------
 // Constants
 // ---------------------------------------------------------------------------

 static constexpr uint8_t  LED_PIN           = RGB_LED_PIN;  // Onboard WS2812
 static constexpr uint32_t PHASE_DURATION_MS = 100; // Time per colour

 // Brightness range — adjust these three values to taste.
 // BRIGHTNESS_STEP must divide evenly into (BRIGHTNESS_MAX - BRIGHTNESS_MIN).
 // e.g. min=8, max=16, step=2  →  levels: 8, 10, 12, 14, 16  (5 colour cycles)
 static constexpr uint8_t BRIGHTNESS_MIN  =  2;
 static constexpr uint8_t BRIGHTNESS_MAX  = 32;
 static constexpr uint8_t BRIGHTNESS_STEP =  2;

 // ---------------------------------------------------------------------------
 // Types — defined before any function so Arduino IDE's forward-declaration
 // injector does not reference them before they exist.
 // ---------------------------------------------------------------------------

 struct RgbColor {
     uint8_t     r;
     uint8_t     g;
     uint8_t     b;
     const char* name;
 };

 /** Result of a single brightness ping-pong step. */
 struct BrightnessStep {
     uint8_t index; ///< New brightness index
     int8_t  dir;   ///< New direction (+1 = ramping up, -1 = ramping down)
 };

 // ---------------------------------------------------------------------------
 // Colour table  (full-intensity channel values; brightness applied separately)
 // ---------------------------------------------------------------------------

 static constexpr std::array<RgbColor, 3> k_colors = {{
     { 255,   0,   0, "Red"   },
     {   0, 255,   0, "Green" },
     {   0,   0, 255, "Blue"  },
 }};

 // ---------------------------------------------------------------------------
 // Brightness table — generated at compile time from the three constants above
 // ---------------------------------------------------------------------------

 static constexpr uint8_t BRIGHTNESS_COUNT =
     static_cast<uint8_t>((BRIGHTNESS_MAX - BRIGHTNESS_MIN) / BRIGHTNESS_STEP) + 1;

 template<uint8_t N>
 constexpr std::array<uint8_t, N> makeBrightnessLevels(uint8_t min, uint8_t step, uint8_t max)
 {
     std::array<uint8_t, N> levels{};
     for (uint8_t i = 0; i < N; ++i) {
         const uint16_t val = static_cast<uint16_t>(min) + i * step;
         levels[i] = static_cast<uint8_t>(val > max ? max : val);
     }
     return levels;
 }

 static constexpr auto k_brightness =
     makeBrightnessLevels<BRIGHTNESS_COUNT>(BRIGHTNESS_MIN, BRIGHTNESS_STEP, BRIGHTNESS_MAX);

 // ---------------------------------------------------------------------------
 // Pure state-transition helpers (unit-testable, no hardware dependencies)
 // ---------------------------------------------------------------------------

 /**
  * Return the next colour index, or the current one if the phase hasn't ended.
  */
 inline uint8_t nextColorIndex(uint32_t elapsed,
                                uint8_t  current,
                                uint32_t duration,
                                uint8_t  count)
 {
     if (elapsed >= duration) {
         return static_cast<uint8_t>((current + 1) % count);
     }
     return current;
 }

 /**
  * Return true when the colour index has just wrapped back to 0, signalling
  * that a full colour cycle has completed and brightness should step.
  */
 inline bool colorWrapped(uint8_t prev, uint8_t next)
 {
     return (next == 0) && (prev != 0);
 }

 /**
  * Advance brightness by one step in the current direction, bouncing at both
  * ends instead of wrapping.  The direction flips when an endpoint is reached
  * so the endpoint value is held for one colour cycle before reversing.
  *
  * @param current  Current brightness index
  * @param dir      Current direction (+1 or -1)
  * @param count    Total number of brightness levels
  */
 inline BrightnessStep nextBrightnessStep(uint8_t current, int8_t dir, uint8_t count)
 {
     const int16_t next = static_cast<int16_t>(current) + dir;
     if (next <= 0) {
         return { 0, 1 };
     }
     if (next >= static_cast<int16_t>(count - 1)) {
         return { static_cast<uint8_t>(count - 1), -1 };
     }
     return { static_cast<uint8_t>(next), dir };
 }

 /**
  * Scale a full-intensity channel value by a brightness factor (0–255).
  */
 inline uint8_t applyBrightness(uint8_t channel, uint8_t brightness)
 {
     return static_cast<uint8_t>((static_cast<uint16_t>(channel) * brightness) / 255);
 }

 // ---------------------------------------------------------------------------
 // Module state
 // ---------------------------------------------------------------------------

 static uint8_t  s_colorIdx      = 0;
 static uint8_t  s_brightnessIdx = 0;
 static int8_t   s_brightnessDir = 1;   // +1 = ramping up, -1 = ramping down
 static uint32_t s_lastChangeMs  = 0;

 // ---------------------------------------------------------------------------
 // Helpers
 // ---------------------------------------------------------------------------

 static void showCurrent()
 {
     const auto& c  = k_colors[s_colorIdx];
     const uint8_t  b  = k_brightness[s_brightnessIdx];
     neopixelWrite(LED_PIN,
                   applyBrightness(c.r, b),
                   applyBrightness(c.g, b),
                   applyBrightness(c.b, b));
 }

 static void logState(uint32_t nowMs)
 {
     const auto& c = k_colors[s_colorIdx];
     const uint8_t  b = k_brightness[s_brightnessIdx];
     Serial.printf("[%8" PRIu32 "] LED -> %-5s  brightness=%" PRIu8 "/255"
                   "  (r=%" PRIu8 " g=%" PRIu8 " b=%" PRIu8 ")\n",
                   nowMs,
                   c.name,
                   b,
                   applyBrightness(c.r, b),
                   applyBrightness(c.g, b),
                   applyBrightness(c.b, b));
 }

 // ---------------------------------------------------------------------------
 // Arduino entry points
 // ---------------------------------------------------------------------------

 void setup()
 {
     Serial.begin(115200);
     while (!Serial) { /* wait for USB CDC on native-USB boards */ }

     Serial.printf("[%8" PRIu32 "] RGB cycle example starting"
                   " — %zu colours, %" PRIu32 " ms/phase"
                   "  |  brightness: min=%" PRIu8 " max=%" PRIu8
                   " step=%" PRIu8 " → %zu levels\n",
                   millis(),
                   k_colors.size(),
                   PHASE_DURATION_MS,
                   BRIGHTNESS_MIN,
                   BRIGHTNESS_MAX,
                   BRIGHTNESS_STEP,
                   k_brightness.size());

     s_lastChangeMs = millis();
     showCurrent();
     logState(s_lastChangeMs);
 }

 void loop()
 {
     const uint32_t now     = millis();
     const uint32_t elapsed = now - s_lastChangeMs;
     const uint8_t  next    = nextColorIndex(elapsed,
                                              s_colorIdx,
                                              PHASE_DURATION_MS,
                                              static_cast<uint8_t>(k_colors.size()));

     if (next != s_colorIdx) {
         if (colorWrapped(s_colorIdx, next)) {
             const auto step = nextBrightnessStep(
                 s_brightnessIdx,
                 s_brightnessDir,
                 static_cast<uint8_t>(k_brightness.size())
             );
             s_brightnessIdx = step.index;
             s_brightnessDir = step.dir;
         }

         s_colorIdx     = next;
         s_lastChangeMs = now;

         showCurrent();
         logState(now);
     }
 }
