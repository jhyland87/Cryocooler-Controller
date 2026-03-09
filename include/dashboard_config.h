/**
 * @file dashboard_config.h
 * @brief Cryocooler-specific Serial Studio dashboard layout.
 *
 * Defines the groups, datasets, and actions that make up the Serial Studio
 * dashboard.  Each dataset's telemetryKey is the dot-separated field name
 * used in FrameBuilder / telemetry.h (e.g. "cold_head.k", "amplifier.target").
 */

#ifndef DASHBOARD_CONFIG_H
#define DASHBOARD_CONFIG_H

#include <ss_dashboard_config.h>

namespace dashboard_config {

// ═════════════════════════════════════════════════════════════════════════════
// Actions (command buttons in Serial Studio)
// ═════════════════════════════════════════════════════════════════════════════

static const ss::ActionCfg actions[] = {
    { .title = "Start",         .txData = "start",          .icon = "Done",        .eol = "\n" },
    { .title = "Stop",          .txData = "stop",           .icon = "Close",       .eol = "\n" },
    { .title = "Reinit",        .txData = "reinit",         .icon = "Restart",     .eol = "\n" },
    { .title = "Status",        .txData = "status",         .icon = "Zoom In",     .eol = "\n" },
    { .title = "Off",           .txData = "off",            .icon = "Shutdown",    .eol = "\n" },
    { .title = "Summary",       .txData = "summary",        .icon = "System Task", .eol = "\n" },
    { .title = "Clear Faults",  .txData = "fault clear",    .icon = "Erase",       .eol = "\n" },
};

// ═════════════════════════════════════════════════════════════════════════════
// Group 1 — Temperature
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg coreDatasets[] = {
    {
        .title          = "Voltage",
        .units          = "V",
        .telemetryKey   = "system.voltage_v",
        // .widget         = ss::WidgetType::Gauge,
        // .widgetMin      = 0,
        // .widgetMax      = 15,
        // .alarmLow       = 0,
        // .alarmHigh      = 15,
        // .alarmEnabled   = true,
        // .graph          = true,
        // .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Current Consumption",
        .units          = "A",
        .telemetryKey   = "system.current_a",
        // .widget         = ss::WidgetType::Gauge,
        // .widgetMin      = 0,
        // .widgetMax      = 5,
        // .alarmLow       = 0,
        // .alarmHigh      = 5,
        // .alarmEnabled   = true,
        // .graph          = true,
        // .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Power Consumption",
        .units          = "W",
        .telemetryKey   = "system.power_w",
        // .widget         = ss::WidgetType::Gauge,
        // .widgetMin      = 0,
        // .widgetMax      = 5,
        // .alarmLow       = 0,
        // .alarmHigh      = 5,
        // .alarmEnabled   = true,
        // .graph          = true,
        // .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "CPU Usage",
        .units          = "%",
        .telemetryKey   = "system.cpu_usage_percent",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 100,
        .alarmLow       = 0,
        .alarmHigh      = 100,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "CPU Frequency",
        .units          = "MHz",
        .telemetryKey   = "system.cpu_freq_mhz",
        // .widget         = ss::WidgetType::Gauge,
        // .widgetMin      = 0,
        // .widgetMax      = 100,
        // .alarmLow       = 0,
        // .alarmHigh      = 100,
        // .alarmEnabled   = true,
        // .graph          = true,
        // .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Total Heap",
        .units          = "B",
        .telemetryKey   = "system.total_heap_bytes",
        // .widget         = ss::WidgetType::Gauge,
        // .widgetMin      = 0,
        // .widgetMax      = 100,
        // .alarmLow       = 0,
        // .alarmHigh      = 100,
        // .alarmEnabled   = true,
        // .graph          = true,
        // .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Heap Usage",
        .units          = "%",
        .telemetryKey   = "system.heap_usage_percent",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 100,
        .alarmLow       = 0,
        .alarmHigh      = 100,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Total PSRAM",
        .units          = "B",
        .telemetryKey   = "system.total_psram_bytes",
        // .widget         = ss::WidgetType::Gauge,
        // .widgetMin      = 0,
        // .widgetMax      = 100,
        // .alarmLow       = 0,
        // .alarmHigh      = 100,
        // .alarmEnabled   = true,
        // .graph          = true,
        // .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "PSRAM Usage",
        .units          = "%",
        .telemetryKey   = "system.psram_usage_percent",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 100,
        .alarmLow       = 0,
        .alarmHigh      = 100,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Uptime",
        .units          = "ms",
        .telemetryKey   = "system.uptime_ms",
        // .widget         = ss::WidgetType::Gauge,
        // .widgetMin      = 0,
        // .widgetMax      = 100,
        // .alarmLow       = 0,
        // .alarmHigh      = 100,
        // .alarmEnabled   = true,
        // .graph          = true,
        // .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Number of Cores",
        .units          = "",
        .telemetryKey   = "system.num_cores",
        // .widget         = ss::WidgetType::Gauge,
        // .widgetMin      = 0,
        // .widgetMax      = 100,
        // .alarmLow       = 0,
        // .alarmHigh      = 100,
        // .alarmEnabled   = true,
        // .graph          = true,
        // .log            = true,
        .overviewDisplay = true,
    }
};








static const ss::DatasetCfg compressorDatasets[] = {
    {
        .title          = "Compressor Status",
        .units          = "",
        .telemetryKey   = "compressor.status",
        .widget         = ss::WidgetType::Led,
        .widgetMin      = 0,
        .widgetMax      = 1,
        .led            = true,
        .ledHigh        = 1,
        .overviewDisplay = true,
    },
};

static const ss::DatasetCfg tempDatasets[] = {
    {   // Temperature in Kelvin (gauge)
        .title          = "Cold Head Temp (K)",
        .units          = "K",
        .telemetryKey   = "cold_head.temp_k",
        .widget         = ss::WidgetType::Gauge,
        // .widgetMin      = 60,
        // .widgetMax      = 340,
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
        // .widgetMin      = 0,
        // .widgetMax      = 2,
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
// Group 2 — Amplifier Output
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg amplifierDatasets[] = {
    {
        .title          = "Amplifier Target",
        .units          = "VAC",
        .telemetryKey   = "amplifier.target_v",
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,
        .widgetMax      = 130,
        .plotMin        = 0,
        .plotMax        = 130,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Amplifier Actual",
        .units          = "VAC",
        .telemetryKey   = "amplifier.voltage_v",
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,
        .widgetMax      = 130,
        .plotMin        = 0,
        .plotMax        = 130,
        .graph          = true,
        .log            = true,
    },
};

// ═════════════════════════════════════════════════════════════════════════════
// Group 3 — Safety
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg safetyDatasets[] = {
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

static const ss::DatasetCfg moduleStatusDatasets[] = {
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
        .telemetryKey   = "mod.imu.service"
    }
};
static const ss::DatasetCfg statusDatasets[] = {
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
    // {
    //     .title          = "On Duration",
    //     .units          = "ms",
    //     .telemetryKey   = "status.on_duration_ms"
    // },
    {
        .title          = "On Duration",
        .units          = "",
        .telemetryKey   = "status.on_duration"
    },
    {
        .title          = "FAULT LED",
        .units          = "",
        .telemetryKey   = "indicator.fault",
        .led            = true,
        .ledHigh        = 1,
        .overviewDisplay = true
    },
    {
        .title          = "READY LED",
        .units          = "",
        .telemetryKey   = "indicator.ready",
        .led            = true,
        .ledHigh        = 1,
        .overviewDisplay = true
    },
    {
        .title = "Fault count (10min)",
        .units = "",
        .telemetryKey = "faults.count_10m",
        .graph = true,
        .overviewDisplay = true
    },
    {
        .title = "Fault count (30min)",
        .units = "",
        .telemetryKey = "faults.count_30m",
        .graph = true,
        .overviewDisplay = true
    },
    {
        .title = "Fault count (60min)",
        .units = "",
        .telemetryKey = "faults.count_60m",
        .graph = true,
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
        // .widgetMin      = 0,
        // .widgetMax      = 100,
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
        .widget         = ss::WidgetType::Led,
        .widgetMin      = 0,
        .widgetMax      = 1,
        .alarmEnabled   = false,
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

static const ss::DatasetCfg accelDatasets[] = {
    {
        .title          = "Accel X",
        .units          = "m/s\xC2\xB2",  // m/s²
        .telemetryKey   = "imu.x",
        .widgetMin      = -2,
        .widgetMax      = 2,
        .graph          = true,
        .log            = true
    },
    {
        .title          = "Accel Y",
        .units          = "m/s\xC2\xB2",
        .telemetryKey   = "imu.y",
        .graph          = true,
        .log            = true
    },
    {
        .title          = "Accel Z",
        .units          = "m/s\xC2\xB2",
        .telemetryKey   = "imu.z",
        .graph          = true,
        .log            = true
    },
    {
        .title          = "Accel Magnitude",
        .units          = "m/s\xC2\xB2",
        .telemetryKey   = "imu.accel_mag",
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
        .telemetryKey   = "imu.motion",
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
// Group 6 — Cooling
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DatasetCfg coolingDatasets[] = {
    {
        .title          = "Pump On",
        .units          = "",
        .telemetryKey   = "cooling.pump_on",
        .widget         = ss::WidgetType::Led,
        .widgetMin      = 0,
        .widgetMax      = 1,
        .led            = true,
        .ledHigh        = 1,
        .overviewDisplay = true,
    },
    {
        .title          = "Coolant Temp",
        .units          = "\xC2\xB0" "C",
        .telemetryKey   = "cooling.temp_c",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 60,
        .alarmLow       = 0,
        .alarmHigh      = 45,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Flow Rate",
        .units          = "L/min",
        .telemetryKey   = "cooling.flow_rate_lpm",
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
        .title          = "Fan Speed",
        .units          = "%",
        .telemetryKey   = "cooling.fan_speed",
        .widget         = ss::WidgetType::Bar,
        .widgetMin      = 0,
        .widgetMax      = 100,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
    {
        .title          = "Fan RPM",
        .units          = "RPM",
        .telemetryKey   = "cooling.fan_rpm",
        .graph          = true,
        .log            = true,
    },
    {
        .title          = "Coolant Temp Score",
        .units          = "%",
        .telemetryKey   = "score.cooling.coolant_temp",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 100,
        .alarmLow       = 0,
        .alarmHigh      = 100,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
    },
    {
        .title          = "Coolant Flow Score",
        .units          = "%",
        .telemetryKey   = "score.cooling.coolant_flow",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 100,
        .alarmLow       = 0,
        .alarmHigh      = 100,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
    },
    {
        .title          = "Fan Speed Score",
        .units          = "%",
        .telemetryKey   = "score.cooling.fan_speed",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 100,
        .alarmLow       = 0,
        .alarmHigh      = 100,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
    },
    {
        .title          = "Worst Cooling Score",
        .units          = "%",
        .telemetryKey   = "score.cooling.worst",
        .widget         = ss::WidgetType::Gauge,
        .widgetMin      = 0,
        .widgetMax      = 100,
        .alarmLow       = 0,
        .alarmHigh      = 100,
        .alarmEnabled   = true,
        .graph          = true,
        .log            = true,
        .overviewDisplay = true,
    },
};


// ═════════════════════════════════════════════════════════════════════════════
// Groups
// ═════════════════════════════════════════════════════════════════════════════

static const ss::GroupCfg dataGroups[] = {
    {
        .title        = "Core System Info (esp32)",
        .widget       = ss::GroupWidget::Datagrid,
        .datasets     = coreDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(coreDatasets) / sizeof(coreDatasets[0])),
    },
    {
        .title        = "Cold Head Temp",
        .widget       = ss::GroupWidget::Multiplot,
        .datasets     = tempDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(tempDatasets) / sizeof(tempDatasets[0])),
    },
    {
        .title        = "Amplifier Output",
        .widget       = ss::GroupWidget::Multiplot,
        .datasets     = amplifierDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(amplifierDatasets) / sizeof(amplifierDatasets[0])),
    },
    {
        .title        = "Safety",
        .widget       = ss::GroupWidget::None,
        .datasets     = safetyDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(safetyDatasets) / sizeof(safetyDatasets[0])),
    },
    {
        .title        = "Overall Status",
        .widget       = ss::GroupWidget::Datagrid,
        .datasets     = statusDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(statusDatasets) / sizeof(statusDatasets[0])),
    },
    {
        .title        = "Cooling",
        .widget       = ss::GroupWidget::None,
        .datasets     = coolingDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(coolingDatasets) / sizeof(coolingDatasets[0])),
    },
    {
        .title        = "Module Status",
        .widget       = ss::GroupWidget::Datagrid,
        .datasets     = moduleStatusDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(moduleStatusDatasets) / sizeof(moduleStatusDatasets[0])),
    },
    {
        .title        = "Accelerometer",
        .widget       = ss::GroupWidget::Multiplot,
        .datasets     = accelDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(accelDatasets) / sizeof(accelDatasets[0])),
    },
    {
        .title        = "Compressor",
        .widget       = ss::GroupWidget::None,
        .datasets     = compressorDatasets,
        .datasetCount = static_cast<uint8_t>(sizeof(compressorDatasets) / sizeof(compressorDatasets[0])),
    },
};

// ═════════════════════════════════════════════════════════════════════════════
// Top-level configuration
// ═════════════════════════════════════════════════════════════════════════════

static const ss::DashboardCfg dashboardCfg = {
    .title       = "Cryocooler Dashboard",
    .groups      = dataGroups,
    .groupCount  = static_cast<uint8_t>(sizeof(dataGroups) / sizeof(dataGroups[0])),
    .actions     = actions,
    .actionCount = static_cast<uint8_t>(sizeof(actions) / sizeof(actions[0])),
};

} // namespace dashboard_config

#endif // DASHBOARD_CONFIG_H
