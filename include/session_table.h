/**
 * @file session_table.h
 * @brief Table of logged-in dashboard sessions, held as hashes of their IDs.
 *
 * Header-only and free of Arduino calls, so the same logic runs on the ESP32
 * and in the native unit tests.  The caller hashes the session ID and supplies
 * the clocks.  Two kinds of session share the table:
 *   - remembered: saved to flash by the caller, expires at a wall-clock time
 *   - temporary:  RAM only, expires at an uptime
 * Each kind has its own slots; when they are full the oldest one is replaced.
 */

#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>

class SessionTable {
public:
    static constexpr size_t HASH_BYTES     = 32;  ///< SHA-256 of the session ID
    static constexpr size_t SLOTS_PER_KIND = 4;

    struct Session {
        uint8_t  hash[HASH_BYTES];
        int64_t  expires;     ///< remembered: Unix seconds; temporary: uptime seconds
        uint32_t order;       ///< larger = added later
        bool     remembered;
        bool     live;
    };

    /**
     * Add a session, replacing the oldest of its kind when that kind is full.
     * @param hash        HASH_BYTES bytes.
     * @param remembered  true for a session that is also saved to flash.
     * @param expires     Unix seconds (remembered) or uptime seconds (temporary).
     */
    void add(const uint8_t* hash, bool remembered, int64_t expires) {
        Session* target = nullptr;
        const bool hasRoom = freeSlots(remembered) > 0;
        for (Session& session : sessions_) {
            if (hasRoom && !session.live) {
                target = &session;
                break;
            }
            const bool sameKind = session.live && session.remembered == remembered;
            if (!hasRoom && sameKind && (target == nullptr || session.order < target->order)) {
                target = &session;
            }
        }
        memcpy(target->hash, hash, HASH_BYTES);
        target->expires    = expires;
        target->order      = ++lastOrder_;
        target->remembered = remembered;
        target->live       = true;
    }

    /**
     * Look a session up, dropping it if it has expired.
     * @param hash          HASH_BYTES bytes.
     * @param epochSeconds  Wall clock, or 0 when it isn't set yet. Remembered
     *                      sessions can't be aged without it, so they stay valid.
     * @param uptimeSeconds Time since boot.
     * @return true if the session is live.
     */
    bool contains(const uint8_t* hash, int64_t epochSeconds, int64_t uptimeSeconds) {
        for (Session& session : sessions_) {
            if (!session.live || !sameHash(session.hash, hash)) {
                continue;
            }
            const int64_t now     = session.remembered ? epochSeconds : uptimeSeconds;
            const bool    expired = (now != 0) && now >= session.expires;
            if (expired) {
                session.live = false;
            }
            return !expired;
        }
        return false;
    }

    /**
     * End one session.
     * @return true if it was live and remembered, so the saved copy needs updating.
     */
    bool remove(const uint8_t* hash) {
        for (Session& session : sessions_) {
            if (session.live && sameHash(session.hash, hash)) {
                session.live = false;
                return session.remembered;
            }
        }
        return false;
    }

    /** End every session. */
    void clear() {
        for (Session& session : sessions_) {
            session.live = false;
        }
    }

    /**
     * Copy out the remembered sessions, for saving.
     * @param out  Receives up to SLOTS_PER_KIND sessions.
     * @return how many were copied.
     */
    size_t copyRemembered(Session* out) const {
        size_t count = 0;
        for (const Session& session : sessions_) {
            if (session.live && session.remembered) {
                out[count++] = session;
            }
        }
        return count;
    }

    /** @return how many sessions of one kind are live. */
    size_t count(bool remembered) const {
        return SLOTS_PER_KIND - freeSlots(remembered);
    }

private:
    size_t freeSlots(bool remembered) const {
        size_t used = 0;
        for (const Session& session : sessions_) {
            if (session.live && session.remembered == remembered) {
                ++used;
            }
        }
        return SLOTS_PER_KIND - used;
    }

    /** Compare without stopping at the first difference, so timing says nothing. */
    static bool sameHash(const uint8_t* left, const uint8_t* right) {
        uint8_t difference = 0;
        for (size_t byteIndex = 0; byteIndex < HASH_BYTES; ++byteIndex) {
            difference |= static_cast<uint8_t>(left[byteIndex] ^ right[byteIndex]);
        }
        return difference == 0;
    }

    Session  sessions_[SLOTS_PER_KIND * 2] = {};
    uint32_t lastOrder_                    = 0;
};
