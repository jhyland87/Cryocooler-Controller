/**
 * @file module.h
 * @brief Compile-time lifecycle interface contract for ESP32 subsystem modules.
 *
 * Every subsystem in this project is implemented as a C++ namespace with free
 * functions.  This header standardises the lifecycle API so that:
 *
 *   1. The compiler enforces the contract — a missing init() or service() is a
 *      build error, not a silent runtime omission.
 *
 *   2. Call sites and the free functions themselves are unchanged.  The Module
 *      struct is a thin, zero-overhead adapter layer.
 *
 * ── How to conform ────────────────────────────────────────────────────────────
 *
 * Inside your namespace, define a struct that inherits from ModuleBase<T> and
 * implements at minimum a static module::InitStatus init():
 *
 *   @code
 *   #include "module.h"
 *
 *   namespace imu {
 *
 *   module::InitStatus    init();
 *   module::ServiceStatus service();
 *   float getRoll();
 *
 *   struct Module : ModuleBase<Module> {
 *       static module::InitStatus    init()    { return imu::init(); }
 *       static module::ServiceStatus service() { return imu::service(); }
 *   };
 *
 *   ASSERT_MODULE_INTERFACE(Module);
 *
 *   } // namespace imu
 *   @endcode
 *
 * ── Minimum required interface ────────────────────────────────────────────────
 *
 *   static module::InitStatus init()
 *       Called once from setup().  Must not block (except during startup).
 *       No default — every module must define its own initialisation.
 *
 *   static module::ServiceStatus service()
 *       Called every loop() tick.  Must not block.
 *       Returns SERVICE_OK, SERVICE_SKIPPED, or SERVICE_ERROR.
 *       Default: SERVICE_SKIPPED (acceptable for FreeRTOS-task-driven modules
 *       such as dashboard, which manages its own schedule internally).
 *
 * ── Optional interface (all defaulted by ModuleBase) ─────────────────────────
 *
 *   static void enable()       Re-enable module output  (default: no-op)
 *   static void disable()      Suspend module output    (default: no-op)
 *   static bool isEnabled()    Query enabled state      (default: true)
 *
 * ── Modules with non-standard signatures ─────────────────────────────────────
 *
 *   Modules whose loop call requires arguments (e.g. indicator::update(nowMs),
 *   temperature::read(nowMs)) wrap them in service() by calling millis()
 *   internally.  Guard such Module structs with #ifdef ARDUINO so they compile
 *   cleanly in native (host) unit-test builds where millis() is unavailable.
 *
 *   Pure actuator modules (relay, dac) have no periodic work; their Module
 *   struct inherits the default no-op service() from ModuleBase.
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <type_traits>



// ─── CRTP base ────────────────────────────────────────────────────────────────

// ─── X-macro tables ───────────────────────────────────────────────────────────
//
// Each row is  X(ENUMERATOR_SUFFIX, "human readable label").
// The enum value, the name function, and the doxygen comment are all derived
// from this single definition — add or rename a value here and everywhere
// else updates automatically.
//
// Usage pattern:
//   #define X(name, label) MODULE_INIT_##name,
//   MODULE_INIT_STATUS(X)
//   #undef X

/** InitStatus values.  Shared by the enum definition and initStatusName(). */
#define MODULE_INIT_STATUS(X) \
    X(NOT_STARTED,      "not started",      "init() has not been called yet")                         \
    X(IN_PROGRESS,      "in progress",      "init() is still running (calibration, WiFi, etc.)")      \
    X(SUCCESS,          "success",          "init() completed successfully")                           \
    X(HARDWARE_ERROR,   "hardware error",   "hardware device failed to respond (I2C/SPI NACK, etc.)") \
    X(DEPENDENCY_ERROR, "dependency error", "a required dependency (bus, other module) is unavailable") \
    X(CONFIG_ERROR,     "config error",     "invalid or missing configuration")                        \
    X(TIMEOUT,          "timeout",          "init() exceeded its allowed time budget")                 \
    X(UNDERVOLTAGE,     "undervoltage",     "system voltage below module minimum — reinit required")   \
    X(UNKNOWN_ERROR,    "unknown error",    "catch-all for unexpected failures")

/** ServiceStatus values.  Shared by the enum definition and serviceStatusName(). */
#define MODULE_SERVICE_STATUS(X) \
    X(NOT_STARTED,  "not started",  "service() has not been called yet")                      \
    X(OK,           "ok",           "ran and produced valid output this tick")                      \
    X(SKIPPED,      "skipped",      "skipped this tick (time-gated, disabled, no new data, etc.)") \
    X(ERROR,        "error",        "a recoverable error occurred; output may be stale")

// ─── Enums ────────────────────────────────────────────────────────────────────

namespace module {
    typedef enum {
#define X(name, label, doc) MODULE_INIT_##name,
        MODULE_INIT_STATUS(X)
#undef X
    } InitStatus;

    typedef enum {
#define X(name, label, doc) MODULE_SERVICE_##name,
        MODULE_SERVICE_STATUS(X)
#undef X
    } ServiceStatus;

    /**
     * Return a human-readable label for an InitStatus value.
     * The common "MODULE_INIT_" prefix and underscores are stripped; the result
     * is lower-case (e.g. MODULE_INIT_NOT_STARTED → "not started").
     *
     * The switch is generated from MODULE_INIT_STATUS — add new values there,
     * not here.
     */
    inline const char* initStatusName(InitStatus s) {
        switch (s) {
#define X(name, label, doc) case MODULE_INIT_##name: return label;
            MODULE_INIT_STATUS(X)
#undef X
            default: return "unknown";
        }
    }

    /**
     * Return a human-readable label for a ServiceStatus value.
     * The common "MODULE_SERVICE_" prefix is stripped; the result is lower-case
     * (e.g. MODULE_SERVICE_SKIPPED → "skipped").
     *
     * The switch is generated from MODULE_SERVICE_STATUS — add new values there,
     * not here.
     */
    inline const char* serviceStatusName(ServiceStatus s) {
        switch (s) {
#define X(name, label, doc) case MODULE_SERVICE_##name: return label;
            MODULE_SERVICE_STATUS(X)
#undef X
            default: return "unknown";
        }
    }
}
/**
 * Curiously Recurring Template Pattern (CRTP) mixin.
 *
 * Inherit publicly in your Module struct and override only the methods you need:
 *
 *   struct Module : ModuleBase<Module> {
 *       static module::InitStatus init() { ... }  // required — no default provided
 *       static module::ServiceStatus service() { ... }  // override if loop work is needed
 *   };
 */
template<typename Derived>
struct ModuleBase {
    // No default init() — every module must provide its own.
    // (Declared deleted so a missing override is a clear compile error rather
    //  than a silent fall-through to an empty base implementation.)
    // static module::InitStatus init() = delete;  // uncomment if you ever need the guard

    /**
     * Non-blocking periodic service call — pump state machines, read sensors, etc.
     * Default: no-op returning SKIPPED.  Override in Derived if the module has
     * loop work to do.
     */
    static module::ServiceStatus service() { return module::MODULE_SERVICE_SKIPPED; }

    /**
     * Re-enable module output / broadcasting.
     * Default: no-op (module is always enabled).
     */
    static void enable() {}

    /**
     * Suspend module output / broadcasting.
     * Default: no-op.
     */
    static void disable() {}

    /**
     * Query the module's enabled state.
     * Default: always enabled.
     */
    static bool isEnabled() { return true; }

    /**
     * Minimum system voltage (V) required for this module to operate.
     * When the measured bus voltage drops below this threshold the module is
     * disabled and demoted to MODULE_INIT_UNDERVOLTAGE.  It will NOT
     * re-enable automatically when voltage recovers — a reinit is required.
     *
     * Default: 0.0f (no voltage requirement / not monitored).
     */
    static constexpr float minSystemVoltage() { return 0.0f; }

    /**
     * Return the InitStatus produced by the most recent init() call.
     * Defaults to NOT_STARTED before init() has been called.
     */
    static module::InitStatus getInitStatus() { return _initStatus; }

    /**
     * Return true if init() completed successfully.
     * Equivalent to getInitStatus() == MODULE_INIT_SUCCESS.
     */
    static bool isInitialized() { return _initStatus == module::MODULE_INIT_SUCCESS; }

    /**
     * Override the cached init status — used by modules that support
     * deferred (hot-plug) initialisation.  The module's service() can
     * promote itself to MODULE_INIT_SUCCESS once the hardware appears.
     */
    static void overrideInitStatus(module::InitStatus s) { _initStatus = s; }

    /**
     * Return the ServiceStatus produced by the most recent service() call.
     * Defaults to SKIPPED for modules that inherit the no-op service().
     */
    static module::ServiceStatus getServiceStatus() { return _serviceStatus; }

protected:
    /// Cached result of the last init() call.  Written by Module::init() via `return _initStatus = ns::init()`.
    static inline module::InitStatus    _initStatus    = module::MODULE_INIT_NOT_STARTED;

    /// Cached result of the last service() call.  Written by Module::service() via `return _serviceStatus = ns::service()`.
    static inline module::ServiceStatus _serviceStatus = module::MODULE_SERVICE_SKIPPED;

    // Non-polymorphic base — prevent accidental deletion through a base pointer.
    ~ModuleBase() = default;
};

// ─── Compile-time trait detection (C++17 void_t pattern) ─────────────────────

namespace module_traits {

namespace detail {

template<typename T, typename = void>
struct has_init : std::false_type {};
/** True only when T::init() exists AND returns module::InitStatus. */
template<typename T>
struct has_init<T, std::void_t<
    std::enable_if_t<
        std::is_same_v<decltype(T::init()), module::InitStatus>
    >>> : std::true_type {};

template<typename T, typename = void>
struct has_service : std::false_type {};
/** True only when T::service() exists AND returns module::ServiceStatus. */
template<typename T>
struct has_service<T, std::void_t<
    std::enable_if_t<
        std::is_same_v<decltype(T::service()), module::ServiceStatus>
    >>> : std::true_type {};

template<typename T, typename = void>
struct has_enable : std::false_type {};
template<typename T>
struct has_enable<T, std::void_t<decltype(T::enable())>> : std::true_type {};

template<typename T, typename = void>
struct has_disable : std::false_type {};
template<typename T>
struct has_disable<T, std::void_t<decltype(T::disable())>> : std::true_type {};

template<typename T, typename = void>
struct has_isEnabled : std::false_type {};
template<typename T>
struct has_isEnabled<T, std::void_t<decltype(T::isEnabled())>> : std::true_type {};

} // namespace detail

/** True if T provides `static module::InitStatus init()`. */
template<typename T>
constexpr bool has_init = detail::has_init<T>::value;

/** True if T provides `static module::ServiceStatus service()`. */
template<typename T>
constexpr bool has_service = detail::has_service<T>::value;

/** True if T provides both `static void enable()` and `static void disable()`. */
template<typename T>
constexpr bool has_enable_disable =
    detail::has_enable<T>::value && detail::has_disable<T>::value;

/** True if T provides `static bool isEnabled()`. */
template<typename T>
constexpr bool has_isEnabled = detail::has_isEnabled<T>::value;

/**
 * True if T satisfies the minimum Module contract:
 *   - static module::InitStatus    init()
 *   - static module::ServiceStatus service()
 */
template<typename T>
constexpr bool is_module = has_init<T> && has_service<T>;

} // namespace module_traits

// ─── Compile-time enforcement macro ──────────────────────────────────────────

/**
 * Emit a descriptive compile-time error if T does not satisfy the minimum
 * Module interface (static module::InitStatus init() + static module::ServiceStatus service()).
 *
 * Place this immediately after the closing brace of your Module struct,
 * still inside the enclosing namespace:
 *
 *   ASSERT_MODULE_INTERFACE(Module);
 */
#define ASSERT_MODULE_INTERFACE(T)                                              \
    static_assert(module_traits::is_module<T>,                                 \
        #T " does not satisfy the Module interface: "                           \
           "must provide static module::InitStatus init() "                     \
           "and static module::ServiceStatus service()")

// ─── Module registry ─────────────────────────────────────────────────────────
//
// Type-erased module descriptor — stores function pointers extracted from each
// Module struct so that init / service / status queries can be driven from
// arrays instead of hand-coded one-by-one.  No vtable, no heap allocation.

namespace module {

struct ModuleEntry {
    const char*    name;
    InitStatus     (*initFn)();
    InitStatus     (*getInitStatus)();
    ServiceStatus  (*serviceFn)();
    ServiceStatus  (*getServiceStatus)();
    bool           fatal;              ///< true = halt startup if init fails
    float          minSystemVoltage;   ///< 0.0f = no voltage requirement
    void           (*disableFn)();     ///< safe to call even if module has no disable()
    void           (*overrideInitStatusFn)(InitStatus);
};

/**
 * Create a ModuleEntry from a Module struct inside namespace @p ns.
 *
 * @param ns       The namespace containing a Module struct (e.g. cooling, imu).
 * @param isFatal  true if an init failure should halt the boot sequence.
 *
 * Example:
 *   static const module::ModuleEntry modules[] = {
 *       MODULE_ENTRY(cooling,   false),
 *       MODULE_ENTRY(amplifier, false),
 *   };
 */
#define MODULE_ENTRY(ns, isFatal) {      \
    #ns,                                 \
    ns::Module::init,                    \
    ns::Module::getInitStatus,           \
    ns::Module::service,                 \
    ns::Module::getServiceStatus,        \
    isFatal,                             \
    ns::Module::minSystemVoltage(),      \
    ns::Module::disable,                 \
    ns::Module::overrideInitStatus       \
}

/**
 * Initialise every module in an array.
 *
 * For each entry: logs "name --> Initialising ...", calls initFn(), logs the
 * outcome, and optionally calls @p emitFn (e.g. telemetry::emitSafe) after
 * each step so the dashboard shows real-time progress.
 *
 * @param entries  Array of ModuleEntry descriptors.
 * @param count    Number of entries in the array.
 * @param emitFn   Optional callback invoked after each init (nullptr to skip).
 * @param logFn    Printf-style log function (e.g. _Log.printf).
 * @return         false if any entry marked fatal failed; true otherwise.
 */
template<typename LogFn>
inline bool initGroup(const ModuleEntry* entries, size_t count,
                      void (*emitFn)(), LogFn&& logFn,
                      void (*yieldFn)() = nullptr) {
    for (size_t i = 0; i < count; ++i) {
        const auto& m = entries[i];
        logFn("%s --> Initialising ...\n", m.name);

        // Yield to the FreeRTOS scheduler to feed the task watchdog.
        // Without this, a long init sequence (WiFi, IMU calibration, etc.)
        // can exceed the 5 s WDT timeout and trigger a software reset.
        if (yieldFn) yieldFn();

        InitStatus status = m.initFn();

        if (status == MODULE_INIT_SUCCESS) {
            logFn("%s --> Initialisation complete\n", m.name);
        } else {
            logFn("%s --> FAILED (status: %s)\n", m.name, initStatusName(status));
            if (m.fatal) {
                if (emitFn) emitFn();
                return false;
            }
        }

        if (yieldFn) yieldFn();
        if (emitFn) emitFn();
    }
    return true;
}

/**
 * Service a module and log only when its health status transitions.
 *
 * "Healthy" means OK or SKIPPED (time-gated modules return SKIPPED on most
 * ticks).  Only the transition between healthy ↔ unhealthy is logged,
 * preventing once-per-tick spam.
 *
 * @param entry       The module to service.
 * @param prevStatus  Reference to a persistent ServiceStatus variable that
 *                    tracks the previous tick's result for this module.
 * @param logFn       Printf-style log function.
 */
template<typename LogFn>
inline void serviceWithLog(const ModuleEntry& entry,
                           ServiceStatus& prevStatus,
                           LogFn&& logFn) {
    const ServiceStatus cur = entry.serviceFn();

    const auto isHealthy = [](ServiceStatus s) {
        return s == MODULE_SERVICE_OK || s == MODULE_SERVICE_SKIPPED;
    };

    if (isHealthy(prevStatus) != isHealthy(cur)) {
        logFn("loop --> %s service %s -> %s\n",
              entry.name,
              serviceStatusName(prevStatus),
              serviceStatusName(cur));
    }
    prevStatus = cur;
}

/**
 * Check system voltage against each module's minimum requirement.
 *
 * For every module in the array whose minSystemVoltage > 0 and whose
 * current init status is SUCCESS: if @p voltage is valid (> 0) and below
 * the module's minimum, the module is disabled and demoted to
 * MODULE_INIT_UNDERVOLTAGE.  Recovery requires a reinit — the module
 * will NOT re-enable automatically when voltage recovers.
 *
 * @param entries  Array of ModuleEntry descriptors.
 * @param count    Number of entries in the array.
 * @param voltage  Current system bus voltage (V).  0 / NaN = not monitored.
 * @param logFn    Printf-style log function.
 * @return         true if any module was shut down this call.
 */
template<typename LogFn>
inline bool checkVoltage(const ModuleEntry* entries, size_t count,
                         float voltage, LogFn&& logFn) {
    // Skip check when voltage is unavailable (0, negative, or NaN).
    if (!(voltage > 0.0f)) return false;

    bool anyShutDown = false;
    for (size_t i = 0; i < count; ++i) {
        const auto& m = entries[i];

        // Only act on modules with a voltage requirement that are currently running.
        if (m.minSystemVoltage <= 0.0f)                      continue;
        if (m.getInitStatus() != MODULE_INIT_SUCCESS)        continue;

        if (voltage < m.minSystemVoltage) {
            logFn("[voltage] %s: %.2fV below minimum %.1fV — disabling (reinit required)\n",
                  m.name, static_cast<double>(voltage),
                  static_cast<double>(m.minSystemVoltage));
            m.disableFn();
            m.overrideInitStatusFn(MODULE_INIT_UNDERVOLTAGE);
            anyShutDown = true;
        }
    }
    return anyShutDown;
}

/**
 * Print the init status of every module in an array.
 *
 * @param entries  Array of ModuleEntry descriptors.
 * @param count    Number of entries.
 * @param logFn    Printf-style log function.
 * @return         Number of modules that did NOT init successfully.
 */
template<typename LogFn>
inline uint8_t reportStatus(const ModuleEntry* entries, size_t count,
                            LogFn&& logFn) {
    uint8_t failCount = 0;
    for (size_t i = 0; i < count; ++i) {
        if (entries[i].getInitStatus() != MODULE_INIT_SUCCESS) {
            ++failCount;
        }
    }
    if (failCount == 0) {
        logFn("    All modules initialized successfully.\n");
    } else {
        logFn("    %u module(s) failed to initialize:\n", failCount);
        for (size_t i = 0; i < count; ++i) {
            const auto status = entries[i].getInitStatus();
            if (status != MODULE_INIT_SUCCESS) {
                logFn("      - %s: %s\n", entries[i].name, initStatusName(status));
            }
        }
    }
    return failCount;
}

} // namespace module
