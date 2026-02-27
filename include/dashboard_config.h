/**
 * @file dashboard_config.h
 * @brief Cryocooler-specific Serial Studio dashboard layout.
 *
 * Defines the groups, datasets, and actions that make up the Serial Studio
 * dashboard.  Each dataset's telemetryKey is the dot-separated field name
 * used in FrameBuilder / telemetry.h (e.g. "cold_head.k", "dac.target").
 *
 * The index field is the 1-based column position in the Serial Studio
 * pipe-delimited frame.  It must stay in sync with telemetry.cpp field order.
 */

#ifndef DASHBOARD_CONFIG_H
#define DASHBOARD_CONFIG_H

#include <ss_dashboard_config.h>

namespace dashboard_config {

// ═════════════════════════════════════════════════════════════════════════════
// Actions (command buttons in Serial Studio)
// ═════════════════════════════════════════════════════════════════════════════

static const ss::ActionCfg kActions[] = {
    { .title = "Start",   .txData = "start",   .icon = "Done",        .eol = "\n" },
    { .title = "Stop",    .txData = "stop",    .icon = "Close",       .eol = "\n" },
    { .title = "Status",  .txData = "status",  .icon = "Zoom In",     .eol = "\n" },
    { .title = "Off",     .txData = "off",     .icon = "Shutdown",    .eol = "\n" },
    { .title = "Summary", .txData = "summary", .icon = "System Task", .eol = "\n" },
};

// ═════════════════════════════════════════════════════════════════════════════
// Group 1 — Temperature
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg kTempDatasets[] = {
    {   // Temperature in Kelvin (gauge)
        .title          = "Cold Head Temp (K)",
        .units          = "K",
        .telemetryKey   = "cold_head.temp_k",
        .index          = 4,
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 60,    .widgetMax  = 300,
        //.plotMin        = 60,    .plotMax    = 310,
        .alarmLow       = 60,    .alarmHigh  = 300,
        .alarmEnabled   = false,
        .graph          = true,  .log = true,
        .overviewDisplay = true,
    },
    {   // Temperature in Celsius (graph only)
        .title          = "Cold Head Temp (C)",
        .units          = "\xC2\xB0" "C",    // °C  (UTF-8)
        .telemetryKey   = "cold_head.temp_c",
        .index          = 5,
        //.widgetMin      = -220,  .widgetMax = 30,
        //.plotMin        = -220,  .plotMax   = 30,
        .alarmLow       = -220,  .alarmHigh = 30,
        .graph          = true,  .log = true,
    },
    {   // Cooling rate
        .title          = "Cooling Rate",
        .units          = "K/min",
        .telemetryKey   = "cold_head.cooling_rate",
        .index          = 7,
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,     .widgetMax = 2,
        //.plotMin        = 0,     .plotMax   = 2,
        .alarmLow       = 0,     .alarmHigh = 1,
        .alarmEnabled   = true,
        .graph          = true,  .log = true,
        .overviewDisplay = true,
    },
    {   // Ambient temperature
        .title          = "Ambient Temp",
        .units          = "\xC2\xB0" "C",
        .telemetryKey   = "cold_head.ambient_temp_c",
        .index          = 6,
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 15,    .widgetMax = 35,
        .graph          = true,
        .overviewDisplay = true,
    },
    {   // Delta below ambient
        .title          = "Temp below ambient",
        .units          = "\xC2\xB0" "C",
        .telemetryKey   = "cold_head.delta_below_ambient_c",
        .index          = 21,
        //.widgetMin      = 0,     .widgetMax = 100,
        .graph          = true,
    },
};

// ═════════════════════════════════════════════════════════════════════════════
// Group 2 — DAC Output
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg kDacDatasets[] = {
    {
        .title          = "DAC Target",
        .units          = "",
        .telemetryKey   = "dac.target",
        .index          = 8,
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,     .widgetMax = 4095,
        //.plotMin        = 0,     .plotMax   = 4095,
        .graph          = true,  .log = true,
        .overviewDisplay = true,
    },
    {
        .title          = "DAC Actual",
        .units          = "",
        .telemetryKey   = "dac.actual",
        .index          = 9,
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,     .widgetMax = 4095,
        //.plotMin        = 0,     .plotMax   = 4095,
        .graph          = true,  .log = true,
    },
};

// ═════════════════════════════════════════════════════════════════════════════
// Group 3 — Safety
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg kSafetyDatasets[] = {
    {
        .title          = "RMS Voltage",
        .units          = "VDC",
        .telemetryKey   = "rms.voltage",
        .index          = 10,
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,     .widgetMax = 150,
        //.plotMin        = 0,     .plotMax   = 150,
        .alarmLow       = 0,     .alarmHigh = 120,
        .alarmEnabled   = true,
        .graph          = true,  .log = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Relay Normal",
        .units          = "",
        .telemetryKey   = "relay.normal",
        .index          = 11,
        .widget         = ss::WidgetType::Led,
        .widgetMin      = 0,     .widgetMax = 1,
        .plotMin        = 0,     .plotMax   = 1,
        .graph          = true,  .log = true,
        .led            = true,  .ledHigh = 1,
    },
    {
        .title          = "Alarm Relay",
        .units          = "",
        .telemetryKey   = "relay.alarm",
        .index          = 12,
        .widget         = ss::WidgetType::Led,
        .widgetMin      = 0,     .widgetMax = 1,
        .plotMin        = 0,     .plotMax   = 1,
        .graph          = true,  .log = true,
        .led            = true,  .ledHigh = 1,
    },
    {
        .title          = "Backoff count",
        .units          = "",
        .telemetryKey   = "status.backoff_count",
        //.index          = 20,
        //.widgetMin      = 0,     .widgetMax = 100,
        //.led            = true,  .ledHigh = 2,
    },
    {
        .title          = "Current",
        .units          = "A",
        .telemetryKey   = "rms.current_a",
        // .index          = 19,
        //.widgetMin      = 0,     .widgetMax = 100,
        .graph          = true,
    },
};

// ═════════════════════════════════════════════════════════════════════════════
// Group 4 — Overall Status (datagrid)
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg kStatusDatasets[] = {
    {
        .title          = "Status ID",
        .units          = "",
        .telemetryKey   = "state.id"
    },
    {
        .title          = "Status",
        .units          = "",
        .telemetryKey   = "state.name"
    },
    {
        .title          = "Description",
        .units          = "",
        .telemetryKey   = "state.status_text"
    },
    {
        .title          = "Time in state",
        .units          = "",
        .telemetryKey   = "status.time_in_state"
    },
    {
        .title          = "On Duration Ms",
        .units          = "",
        .telemetryKey   = "status.on_duration_ms"
    },
    {
        .title          = "On Duration",
        .units          = "",
        .telemetryKey   = "status.on_duration"
    },
    {
        .title          = "FAULT",
        .units          = "",
        .telemetryKey   = "indicator.fault",
        .led            = true,  .ledHigh = 1,
        .overviewDisplay = true
    },
    {
        .title          = "READY",
        .units          = "",
        .telemetryKey   = "indicator.ready",
        .led            = true,  .ledHigh = 1,
        .overviewDisplay = true
    },
    {
        .title          = "Cold Head Temp (C)",
        .units          = "\xC2\xB0" "C",
        .telemetryKey   = "cold_head.temp_c",
        .graph          = true,
        .overviewDisplay = true
    },
    {
        .title          = "Cold Head Temp (K)",
        .units          = "K",
        .telemetryKey   = "cold_head.temp_k",
        .widgetMin      = 0,     .widgetMax = 100,
        .plotMin        = 75,    .plotMax   = 295,
        .graph          = true,
        .overviewDisplay = true
    },
    {
        .title          = "Cooldown Percent",
        .units          = "%",
        .telemetryKey   = "cold_head.cooldown_pct",
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,     .widgetMax = 100,
        .alarmLow       = 0,     .alarmHigh = 100,
        .alarmEnabled   = true,
        .overviewDisplay = true
    },
    {
        .title          = "Cooling Pump",
        .units          = "",
        .telemetryKey   = "cooling.pump_on",
        .widgetMin      = 0,     .widgetMax = 100,
        .led            = true,  .ledHigh = 1,
        .overviewDisplay = true
    },
    {
        .title          = "Cooling Fans",
        .units          = "",
        .telemetryKey   = "cooling.fan_speed",
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,     .widgetMax = 100,
        .led            = true,  .ledHigh = 1,
        .overviewDisplay = true
    },
};

// ═════════════════════════════════════════════════════════════════════════════
// Group 5 — Accelerometer
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg kAccelDatasets[] = {
    {
        .title          = "Accel X",
        .units          = "m/s\xC2\xB2",  // m/s²
        .telemetryKey   = "accel.x",
        .graph          = true,  .log = true
    },
    {
        .title          = "Accel Y",
        .units          = "m/s\xC2\xB2",
        .telemetryKey   = "accel.y",
        .graph          = true,  .log = true
    },
    {
        .title          = "Accel Z",
        .units          = "m/s\xC2\xB2",
        .telemetryKey   = "accel.z",
        .graph          = true,  .log = true
    },
    {
        .title          = "Accel Magnitude",
        .units          = "m/s\xC2\xB2",
        .telemetryKey   = "accel.accel_mag",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,     .widgetMax = 20,
        .graph          = true,  .log = true,
        .overviewDisplay = true
    },
    {
        .title          = "Motion / Overstroke",
        .units          = "",
        .telemetryKey   = "accel.motion",
        .widget         = ss::WidgetType::Led,
        .widgetMin      = 0,     .widgetMax = 1,
        .plotMin        = 0,     .plotMax   = 1,
        .alarmLow       = 0,     .alarmHigh = 1,
        .alarmEnabled   = true,
        .led            = true,  .ledHigh = 1,
        .overviewDisplay = true
    },
};

// ═════════════════════════════════════════════════════════════════════════════
// Groups
// ═════════════════════════════════════════════════════════════════════════════

static const ss::GroupCfg kGroups[] = {
    {
        .title        = "Cold Head Temp",
        .widget       = ss::GroupWidget::Multiplot,
        .datasets     = kTempDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(kTempDatasets) / sizeof(kTempDatasets[0])),
    },
    {
        .title        = "DAC Output",
        .widget       = ss::GroupWidget::Multiplot,
        .datasets     = kDacDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(kDacDatasets) / sizeof(kDacDatasets[0])),
    },
    {
        .title        = "Safety",
        .widget       = ss::GroupWidget::None,
        .datasets     = kSafetyDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(kSafetyDatasets) / sizeof(kSafetyDatasets[0])),
    },
    {
        .title        = "Overall Status",
        .widget       = ss::GroupWidget::Datagrid,
        .datasets     = kStatusDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(kStatusDatasets) / sizeof(kStatusDatasets[0])),
    },
    {
        .title        = "Accelerometer",
        .widget       = ss::GroupWidget::Multiplot,
        .datasets     = kAccelDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(kAccelDatasets) / sizeof(kAccelDatasets[0])),
    },
};

// ═════════════════════════════════════════════════════════════════════════════
// Top-level configuration
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DashboardCfg kDashboardCfg = {
    .title       = "Cryocooler Dashboard",
    .groups      = kGroups,
    .groupCount  = static_cast<uint8_t>(sizeof(kGroups) / sizeof(kGroups[0])),
    .actions     = kActions,
    .actionCount = static_cast<uint8_t>(sizeof(kActions) / sizeof(kActions[0])),
};

} // namespace dashboard_config

#endif // DASHBOARD_CONFIG_H
