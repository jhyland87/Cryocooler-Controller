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

namespace module {
    typedef enum {
        MODULE_INIT_NOT_STARTED      = 0,  ///< init() has not been called yet
        MODULE_INIT_IN_PROGRESS      = 1,  ///< init() is still running (calibration, WiFi, etc.)
        MODULE_INIT_SUCCESS          = 2,  ///< init() completed successfully
        MODULE_INIT_HARDWARE_ERROR   = 3,  ///< hardware device failed to respond (I2C/SPI NACK, etc.)
        MODULE_INIT_DEPENDENCY_ERROR = 4,  ///< a required dependency (bus, other module) is unavailable
        MODULE_INIT_CONFIG_ERROR     = 5,  ///< invalid or missing configuration
        MODULE_INIT_TIMEOUT          = 6,  ///< init() exceeded its allowed time budget
        MODULE_INIT_UNKNOWN_ERROR    = 7,  ///< catch-all for unexpected failures
    } InitStatus;

    typedef enum {
        MODULE_SERVICE_OK      = 0,  ///< ran and produced valid output this tick
        MODULE_SERVICE_SKIPPED = 1,  ///< skipped this tick (time-gated, disabled, no new data, etc.)
        MODULE_SERVICE_ERROR   = 2,  ///< a recoverable error occurred; output may be stale
    } ServiceStatus;
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

protected:
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
