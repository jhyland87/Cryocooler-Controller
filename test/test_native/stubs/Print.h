/**
 * @file Print.h
 * @brief Minimal Print stub for native (host-PC) unit tests.
 *
 * Matches the subset of Arduino's Print class used by serial_commands.cpp and
 * LogStream (log.h): write(uint8_t), write(const uint8_t*, size_t),
 * print(const char*), and println(const char*).
 *
 * Output is accumulated in an internal capture buffer so tests can inspect it
 * via str() / contains().
 *
 * write(uint8_t c) and write(const uint8_t*, size_t) are declared virtual so
 * that subclasses (e.g. LogStream) can override them, exactly as in the real
 * Arduino Print class.  This lets LogStream work correctly in native tests
 * without any ARDUINO-specific code paths.
 */

#ifndef PRINT_STUB_H
#define PRINT_STUB_H

#include <cstring>
#include <cstdio>
#include <cstddef>
#include <cstdint>
#include <cstdarg>

class Print {
public:
    static constexpr size_t kCapacity = 4096;

    Print() { reset(); }
    virtual ~Print() = default;

    /** Clear the captured output. */
    void reset() {
        _len    = 0;
        _buf[0] = '\0';
    }

    /** Return all captured output as a null-terminated string. */
    const char* str() const { return _buf; }

    /** Number of bytes captured so far. */
    size_t length() const { return _len; }

    /** True if the captured output contains the given substring. */
    bool contains(const char* needle) const {
        return strstr(_buf, needle) != nullptr;
    }

    // ----- Arduino Print interface -----

    /**
     * Write a single byte — mirrors Arduino's pure-virtual Print::write(uint8_t).
     * Subclasses (e.g. LogStream) override this to intercept output.
     * The base implementation stores the byte in the capture buffer so tests
     * can inspect all output via str() / contains().
     */
    virtual size_t write(uint8_t character) {
        if (_len < kCapacity - 1) {
            _buf[_len++] = static_cast<char>(character);
            _buf[_len]   = '\0';
        }
        return 1;
    }

    /**
     * Write @p length bytes.  Delegates to write(uint8_t) so subclass overrides
     * intercept bulk writes the same way as single-byte writes.
     */
    virtual size_t write(const uint8_t* buf, size_t length) {
        for (size_t byteIndex = 0; byteIndex < length; ++byteIndex) { write(buf[byteIndex]); }
        return length;
    }

    size_t print(const char* text) {
        if (!text) { return 0; }
        return write(reinterpret_cast<const uint8_t*>(text), strlen(text));
    }

    size_t println(const char* text = "") {
        const size_t written = print(text);
        return written + print("\n");
    }

    /**
     * printf — variadic formatted print, mirrors Arduino's Print::printf.
     * LogStream inherits this so _Log.printf(...) compiles in native tests.
     */
    int printf(const char* fmt, ...) {
        char tmp[512];
        va_list ap;
        va_start(ap, fmt);
        int written = vsnprintf(tmp, sizeof(tmp), fmt, ap);
        va_end(ap);
        if (written > 0) {
            write(reinterpret_cast<const uint8_t*>(tmp),
                  static_cast<size_t>(written < static_cast<int>(sizeof(tmp)) ? written : static_cast<int>(sizeof(tmp)) - 1));
        }
        return written;
    }

private:
    char   _buf[kCapacity];
    size_t _len = 0;
};

#endif // PRINT_STUB_H
