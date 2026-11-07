/**
 * @file display.cpp
 * @brief Status screen on the Phoenix 2.4" ST7789V display.
 *
 * Uses Adafruit_ST7789 on the shared Arduino SPI object, so every access is a
 * normal SPI transaction alongside the other devices on the bus. The panel
 * settings after the library's generic init follow Phoenix datasheet 109921
 * section 7 (porch, gate, VCOM and power registers, no display inversion).
 */

#include <Arduino.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

#include "display.h"
#include "amplifier.h"
#include "cold_head.h"
#include "gpio_expander.h"
#include "logger.h"
#include "pin_config.h"
#include "spi_device.h"
#include "state_machine.h"
#include "tick.h"

static LogStream _Log = Log.createChildLogger("display");

namespace display {

static constexpr uint32_t DISPLAY_REFRESH_MS = 1000;
static constexpr uint16_t PANEL_WIDTH        = 240;  // native portrait size
static constexpr uint16_t PANEL_HEIGHT       = 320;
static constexpr uint8_t  ROTATION_LANDSCAPE = 1;
static constexpr uint8_t  TEXT_SIZE          = 2;     // 12 x 16 px glyphs
static constexpr int16_t  LINE_HEIGHT        = 24;
static constexpr int16_t  FIRST_LINE_Y       = 40;
static constexpr int16_t  LEFT_MARGIN        = 8;
static constexpr size_t   LINE_COUNT         = 4;
static constexpr size_t   LINE_LENGTH        = 27;    // 320 px / 12 px per glyph

static constexpr SpiChipSelect sPanelChipSelect(DISP_CS_PIN);
static constexpr SpiChipSelect sTouchChipSelect(TOUCH_CS_PIN);

static Adafruit_ST7789 sPanel(&SPI, sPanelChipSelect.chipSelectId(), DISP_DC_PIN, DISP_RST_PIN);
static char     sShown[LINE_COUNT][LINE_LENGTH] = {};
static uint32_t sLastRefreshMs = 0;

/** One register write with its parameter bytes. */
struct PanelCommand {
    uint8_t command;
    uint8_t length;
    uint8_t data[5];
};

// Phoenix 109921 section 7 settings the generic ST7789 init leaves at their
// defaults (gamma tables are left at the controller's defaults).
static constexpr PanelCommand PANEL_SETTINGS[] = {
    {0xB2, 5, {0x0C, 0x0C, 0x00, 0x33, 0x33}},  // porch control
    {0xB7, 1, {0x35}},                    // gate control
    {0xBB, 1, {0x2B}},                    // VCOM
    {0xC0, 1, {0x2C}},                    // LCM control
    {0xC2, 1, {0x01}},                    // VDV / VRH enable
    {0xC3, 1, {0x11}},                    // VRH
    {0xC4, 1, {0x20}},                    // VDV
    {0xC6, 1, {0x0F}},                    // frame rate 60 Hz
    {0xD0, 2, {0xA4, 0xA1}},              // power control 1
    {0x20, 0, {}},                        // INVOFF: the panel is not inverted
};

/** Applies PANEL_SETTINGS after the library's own init. */
static void applyPanelSettings() {
    for (const PanelCommand& entry : PANEL_SETTINGS) {
        sPanel.sendCommand(entry.command, entry.data, entry.length);
    }
}

bool touchPressed() { return gpio_expander::pinLow(EXPANDER_PIN_TOUCH_IRQ); }

void setBacklight(bool on) {
    gpio_expander::writePin(EXPANDER_PIN_DISP_BL, on);
}

/** Fills @p lines with the current status text. */
static void formatLines(char lines[LINE_COUNT][LINE_LENGTH]) {
    snprintf(lines[0], LINE_LENGTH, "State: %s",
             state_machine::stateName(state_machine::getState()));
    snprintf(lines[1], LINE_LENGTH, "Cold head: %7.1f C", cold_head::getLastTempC());
    RailFlags flags{};
    const bool known = amplifier::railFlags(flags);
    snprintf(lines[2], LINE_LENGTH, "+/-15 V: %s",
             !known ? "unknown" : (flags.allGood() ? "OK" : "FAULT"));
    const uint32_t seconds = tick::nowMs() / 1000;
    snprintf(lines[3], LINE_LENGTH, "Up: %luh %02lum %02lus",
             static_cast<unsigned long>(seconds / 3600),
             static_cast<unsigned long>((seconds / 60) % 60),
             static_cast<unsigned long>(seconds % 60));
}

module::InitStatus init() {
    // the touch controller shares the bus: keep it deselected (strap pin,
    // pulled low at reset)
    sTouchChipSelect.begin();

    sPanel.init(PANEL_WIDTH, PANEL_HEIGHT);
    applyPanelSettings();
    sPanel.setRotation(ROTATION_LANDSCAPE);
    sPanel.fillScreen(ST77XX_BLACK);
    sPanel.setTextWrap(false);
    sPanel.setTextSize(TEXT_SIZE);
    sPanel.setTextColor(ST77XX_CYAN, ST77XX_BLACK);
    sPanel.setCursor(LEFT_MARGIN, 8);
    sPanel.print("Cryocooler Controller");
    setBacklight(true);

    memset(sShown, 0, sizeof(sShown));
    sLastRefreshMs = tick::nowMs() - DISPLAY_REFRESH_MS;
    _Log.println(F("Display initialised (ST7789V 320x240)"));
    return module::MODULE_INIT_SUCCESS;
}

module::ServiceStatus service() {
    const uint32_t now = tick::nowMs();
    if (static_cast<uint32_t>(now - sLastRefreshMs) < DISPLAY_REFRESH_MS) {
        return module::MODULE_SERVICE_SKIPPED;
    }
    sLastRefreshMs = now;

    char lines[LINE_COUNT][LINE_LENGTH];
    formatLines(lines);
    sPanel.setTextColor(ST77XX_WHITE, ST77XX_BLACK);
    for (size_t index = 0; index < LINE_COUNT; ++index) {
        if (strncmp(lines[index], sShown[index], LINE_LENGTH) == 0) continue;
        // pad to the full width so a shorter line clears the old text
        char padded[LINE_LENGTH];
        snprintf(padded, sizeof(padded), "%-*s", static_cast<int>(LINE_LENGTH - 1),
                 lines[index]);
        sPanel.setCursor(LEFT_MARGIN, FIRST_LINE_Y + static_cast<int16_t>(index) * LINE_HEIGHT);
        sPanel.print(padded);
        memcpy(sShown[index], lines[index], LINE_LENGTH);
    }
    return module::MODULE_SERVICE_OK;
}

} // namespace display
