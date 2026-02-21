/**
 * @file Print.h
 * @brief Minimal Print stub for native (host-PC) unit tests.
 *
 * Matches the subset of Arduino's Print class used by serial_commands.cpp:
 * print(const char*) and println(const char*).  Output is accumulated in an
 * internal buffer so tests can inspect it via str() / contains().
 */

#ifndef PRINT_STUB_H
#define PRINT_STUB_H

#include <cstring>
#include <cstdio>
#include <cstddef>

class Print {
public:
    static constexpr size_t kCapacity = 4096;

    Print() { reset(); }

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

    // ----- Arduino Print interface (minimal) -----

    size_t print(const char* s) {
        if (!s) { return 0; }
        const size_t n     = strlen(s);
        const size_t avail = kCapacity - 1 - _len;
        const size_t copy  = (n < avail) ? n : avail;
        memcpy(_buf + _len, s, copy);
        _len += copy;
        _buf[_len] = '\0';
        return copy;
    }

    size_t println(const char* s = "") {
        const size_t n = print(s);
        return n + print("\n");
    }

private:
    char   _buf[kCapacity];
    size_t _len;
};

#endif // PRINT_STUB_H
