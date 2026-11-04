/**
 * @file power_good.h
 * @brief Debounced change detector for a digital power-good input.
 *
 * Header-only and free of Arduino calls, so the same logic runs on the ESP32
 * and in the native unit tests.  The caller reads the pin and passes the level
 * in; PowerGoodMonitor only decides when a change is real and reports it once.
 *
 * ── Usage ────────────────────────────────────────────────────────────────────
 *
 *   static PowerGoodMonitor monitor(50);          // 50 ms debounce
 *   monitor.begin(readPin(), tick::nowMs());      // initial level, no event
 *
 *   // every tick:
 *   switch (monitor.update(readPin(), tick::nowMs())) {
 *       case PowerGoodMonitor::Event::Lost:     ...; break;
 *       case PowerGoodMonitor::Event::Restored: ...; break;
 *       case PowerGoodMonitor::Event::None:     break;
 *   }
 */

#pragma once

#include <stdint.h>

class PowerGoodMonitor {
public:
    /** What update() saw this call. */
    enum class Event : uint8_t {
        None,      ///< no confirmed change
        Lost,      ///< power went from good to not good
        Restored,  ///< power went from not good to good
    };

    /**
     * @param debounceMs  Time a new level must hold before it counts as a
     *                    change; 0 reports a change on the first differing
     *                    sample.
     */
    explicit PowerGoodMonitor(uint32_t debounceMs = 0) : debounceMs_(debounceMs) {}

    /**
     * Set the starting level without raising an event.
     * @param good   True if power is good now.
     * @param nowMs  Current time in milliseconds.
     */
    void begin(bool good, uint32_t nowMs) {
        good_            = good;
        pending_         = false;
        lastChangeMs_    = nowMs;
        changeCount_     = 0;
        lastOutageMs_    = 0;
    }

    /**
     * Feed one sample.
     * @param rawGood  Level read from the pin (true = power good).
     * @param nowMs    Current time in milliseconds (wraps safely at 2^32).
     * @return Event::Lost / Event::Restored once a new level has held for the
     *         debounce time, otherwise Event::None.
     */
    Event update(bool rawGood, uint32_t nowMs) {
        if (rawGood == good_) {
            pending_ = false;  // a glitch that returned to the old level
            return Event::None;
        }
        if (!pending_) {
            pending_      = true;
            pendingSince_ = nowMs;
        }
        if (static_cast<uint32_t>(nowMs - pendingSince_) < debounceMs_) {
            return Event::None;
        }
        // The new level held long enough: it is the time of the first
        // differing sample that the change is dated to.
        pending_ = false;
        good_    = rawGood;
        ++changeCount_;
        if (good_) {
            lastOutageMs_ = static_cast<uint32_t>(pendingSince_ - lastChangeMs_);
        }
        lastChangeMs_ = pendingSince_;
        return good_ ? Event::Restored : Event::Lost;
    }

    /** True while the debounced level is "power good". */
    bool isGood() const { return good_; }

    /** Number of confirmed changes since begin(). */
    uint32_t changeCount() const { return changeCount_; }

    /** Time (ms) of the last confirmed change, or of begin() if none yet. */
    uint32_t lastChangeMs() const { return lastChangeMs_; }

    /** Length (ms) of the most recent outage, valid after an Event::Restored. */
    uint32_t lastOutageMs() const { return lastOutageMs_; }

private:
    uint32_t debounceMs_;
    bool     good_          = false;
    bool     pending_       = false;
    uint32_t pendingSince_  = 0;
    uint32_t lastChangeMs_  = 0;
    uint32_t lastOutageMs_  = 0;
    uint32_t changeCount_   = 0;
};

/**
 * The four +-15 V power-good flags the MCP23S08 GPIO expander reads (LT3097 PGP /
 * PGN and LT8582 PG1 / PG2). Each node is high (true) when its rail is good.
 */
struct RailFlags {
    bool posLdo;     ///< LT3097 +15 V output (PGP)
    bool negLdo;     ///< LT3097 -15 V output (PGN)
    bool posBoost;   ///< LT8582 +16.4 V boost (PG1)
    bool negInvert;  ///< LT8582 -16.5 V inverter (PG2)

    /** True when every rail reports good. */
    bool allGood() const { return posLdo && negLdo && posBoost && negInvert; }
};

/**
 * Decode the GPIO expander port byte into rail flags.
 * @param ioState  Bit n = level of expander pin n.
 * @param bitPosLdo, bitNegLdo, bitPosBoost, bitNegInvert  GPIO numbers of
 *                 the four flags (EXPANDER_PIN_* in pin_config.h).
 * @return The decoded flags.
 * @code
 * RailFlags flags = decodeRailFlags(0b01111, 0, 1, 2, 3);  // all good
 * @endcode
 */
inline RailFlags decodeRailFlags(uint8_t ioState, uint8_t bitPosLdo, uint8_t bitNegLdo,
                                 uint8_t bitPosBoost, uint8_t bitNegInvert) {
    auto bit = [ioState](uint8_t index) { return ((ioState >> index) & 1u) != 0; };
    return RailFlags{bit(bitPosLdo), bit(bitNegLdo), bit(bitPosBoost), bit(bitNegInvert)};
}
