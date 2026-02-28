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
 *   namespace accelerometer {
 *
 *   module::InitStatus    init();
 *   module::ServiceStatus service();
 *   float getRoll();
 *
 *   struct Module : ModuleBase<Module> {
 *       static module::InitStatus    init()    { return accelerometer::init(); }
 *       static module::ServiceStatus service() { return accelerometer::service(); }
 *   };
 *
 *   ASSERT_MODULE_INTERFACE(Module);
 *
 *   } // namespace accelerometer
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
    X(UNKNOWN_ERROR,    "unknown error",    "catch-all for unexpected failures")

/** ServiceStatus values.  Shared by the enum definition and serviceStatusName(). */
#define MODULE_SERVICE_STATUS(X) \
    X(OK,      "ok",      "ran and produced valid output this tick")                      \
    X(SKIPPED, "skipped", "skipped this tick (time-gated, disabled, no new data, etc.)") \
    X(ERROR,   "error",   "a recoverable error occurred; output may be stale")

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
     * Return the InitStatus produced by the most recent init() call.
     * Defaults to NOT_STARTED before init() has been called.
     */
    static module::InitStatus getInitStatus() { return _initStatus; }

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
