/**
 * @file dashboard_config.h
 * @brief Cryocooler-specific Serial Studio dashboard layout.
 *
 * Defines the groups, datasets, and actions that make up the Serial Studio
 * dashboard.  Each dataset's telemetryKey is the dot-separated field name
 * used in FrameBuilder / telemetry.h (e.g. "cold_head.k", "dac.target").
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
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 60,
        .widgetMax      = 340,
        .alarmLow       = 60,
        .alarmHigh      = 340,
        .alarmEnabled   = false,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {   // Temperature in Celsius (graph only)
        .title          = "Cold Head Temp (C)",
        .units          = "\xC2\xB0" "C",    // °C  (UTF-8)
        .telemetryKey   = "cold_head.temp_c",
        .alarmLow       = -220,
        .alarmHigh      = 30,
        .graph          = true,
        .log            = true,
    },
    {   // Cooling rate
        .title          = "Cooling Rate",
        .units          = "K/min",
        .telemetryKey   = "cold_head.cooling_rate",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 2,
        .alarmLow       = 0,
        .alarmHigh      = 2,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {   // Ambient temperature
        .title          = "Ambient Temp (C)",
        .units          = "\xC2\xB0" "C",
        .telemetryKey   = "cold_head.ambient_temp_c",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 15,
        .widgetMax      = 35,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {   // Delta below ambient
        .title          = "Temp below ambient",
        .units          = "\xC2\xB0" "C",
        .telemetryKey   = "cold_head.delta_below_ambient_c",
        .graph          = true,
    },
};

// ═════════════════════════════════════════════════════════════════════════════
// Group 2 — DAC Output
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg kDacDatasets[] = {
    {
        .title          = "DAC Target",
        .units          = "V",
        .telemetryKey   = "dac.target",
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,
        .widgetMax      = 10,
        .plotMin        = 0,
        .plotMax        = 10,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "DAC Actual",
        .units          = "V",
        .telemetryKey   = "dac.actual",
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,
        .widgetMax      = 10,
        .plotMin        = 0,
        .plotMax        = 10,
        .graph          = true,
        .log            = true,
    },
};

// ═════════════════════════════════════════════════════════════════════════════
// Group 3 — Safety
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg kSafetyDatasets[] = {
    {
        .title          = "System Voltage",
        .units          = "V",
        .telemetryKey   = "sysinfo.voltage_v",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 15,
        .alarmLow       = 0,
        .alarmHigh      = 15,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "System Current",
        .units          = "A",
        .telemetryKey   = "system.current_a",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 5,
        .alarmLow       = 0,
        .alarmHigh      = 5,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "System Power",
        .units          = "W",
        .telemetryKey   = "system.power_w",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 5,
        .alarmLow       = 0,
        .alarmHigh      = 5,
        .alarmEnabled   = true,
        .graph          = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Relay Normal",
        .units          = "",
        .telemetryKey   = "relay.normal",
        .widget         = ss::WidgetType::Led,
        .widgetMin      = 0,
        .widgetMax      = 1,
        .graph          = true,
        .log            = true,
        .led            = true,
        .ledHigh        = 1,
    },
    {
        .title          = "Alarm Relay",
        .units          = "",
        .telemetryKey   = "relay.alarm",
        .widget         = ss::WidgetType::Led,
        .widgetMin      = 0,
        .widgetMax      = 1,
        .graph          = true,
        .log            = true,
        .led            = true,
        .ledHigh        = 1,
    },
    {
        .title          = "Backoff count",
        .units          = "",
        .telemetryKey   = "status.backoff_count",
    }
};

// ═════════════════════════════════════════════════════════════════════════════
// Group 4 — Overall Status (datagrid)
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg kModuleStatusDatasets[] = {
    {
        .title          = "System Info",
        .units          = "",
        .telemetryKey   = "mod.sysinfo.service"
    },
    {
        .title          = "Cooling",
        .units          = "",
        .telemetryKey   = "mod.cooling.service"
    },
    {
        .title          = "Cold Head",
        .units          = "",
        .telemetryKey   = "mod.cold_head.service"
    },
    {
        .title          = "Waveform",
        .units          = "",
        .telemetryKey   = "mod.waveform.service"
    },
    {
        .title          = "Accelerometer",
        .units          = "",
        .telemetryKey   = "mod.accelerometer.service"
    }
};
static const ss::DatasetCfg kStatusDatasets[] = {
    {
        .title          = "Timestamp",
        .units          = "",
        .telemetryKey   = "timestamp.local"
    },
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
        .title          = "On Duration",
        .units          = "ms",
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
        .led            = true,
        .ledHigh        = 1,
        .overviewDisplay = true
    },
    {
        .title          = "READY",
        .units          = "",
        .telemetryKey   = "indicator.ready",
        .led            = true,
        .ledHigh        = 1,
        .overviewDisplay = true
    },
    {
        .title          = "Cold Head Temp",
        .units          = "\xC2\xB0" "C",
        .telemetryKey   = "cold_head.temp_c",
        .graph          = true,
        .overviewDisplay = true
    },
    {
        .title          = "Cold Head Temp",
        .units          = "K",
        .telemetryKey   = "cold_head.temp_k",
        .widgetMin      = 0,
        .widgetMax      = 100,
        //.plotMin        = 75,
        //.plotMax        = 295,
        .graph          = true,
        .overviewDisplay = true
    },
    {
        .title          = "Cold Head Voltage",
        .units          = "V",
        .telemetryKey   = "cold_head.voltage_v",
        .graph          = true,
        .overviewDisplay = true
    },
    {
        .title          = "Cold Head Current",
        .units          = "A",
        .telemetryKey   = "cold_head.current_a",
        .graph          = true,
        .overviewDisplay = true
    },
    {
        .title          = "Cooldown Percent",
        .units          = "%",
        .telemetryKey   = "cold_head.cooldown_pct",
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,
        .widgetMax      = 100,
        .alarmLow       = 0,
        .alarmHigh      = 100,
        .alarmEnabled   = true,
        .overviewDisplay = true
    },
    {
        .title          = "Cooling Pump",
        .units          = "",
        .telemetryKey   = "cooling.pump_on",
        .widgetMin      = 0,
        .widgetMax      = 100,
        .led            = true,
        .ledHigh        = 1,
        .overviewDisplay = true
    },
    {
        .title          = "Cooling Fans",
        .units          = "%",
        .telemetryKey   = "cooling.fan_speed",
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,
        .widgetMax      = 100,
        .led            = true,
        .ledHigh        = 1,
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
        .telemetryKey   = "accelerometer.x",
        .widgetMin      = -2,
        .widgetMax      = 2,
        .graph          = true,
        .log            = true
    },
    {
        .title          = "Accel Y",
        .units          = "m/s\xC2\xB2",
        .telemetryKey   = "accelerometer.y",
        .graph          = true,
        .log            = true
    },
    {
        .title          = "Accel Z",
        .units          = "m/s\xC2\xB2",
        .telemetryKey   = "accelerometer.z",
        .graph          = true,
        .log            = true
    },
    {
        .title          = "Accel Magnitude",
        .units          = "m/s\xC2\xB2",
        .telemetryKey   = "accelerometer.accel_mag",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 20,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true
    },
    {
        .title          = "Motion / Overstroke",
        .units          = "",
        .telemetryKey   = "accelerometer.motion",
        .widget         = ss::WidgetType::Led,
        .widgetMin      = 0,
        .widgetMax      = 1,
        .alarmLow       = 0,
        .alarmHigh      = 1,
        .alarmEnabled   = true,
        .led            = true,
        .ledHigh        = 1,
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
        .title        = "Module Status",
        .widget       = ss::GroupWidget::Datagrid,
        .datasets     = kModuleStatusDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(kModuleStatusDatasets) / sizeof(kModuleStatusDatasets[0])),
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
