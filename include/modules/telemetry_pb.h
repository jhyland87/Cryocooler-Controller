/**
 * @file telemetry_pb.h
 * @brief Protobuf binary encoder for telemetry WebSocket frames.
 *
 * Encodes the current telemetry state into a Protobuf binary frame using
 * Nanopb.  The output is sent over WebSocket as a binary message, decoded
 * on the browser side by protobufjs using the shared telemetry.proto schema.
 */

#ifndef TELEMETRY_PB_H
#define TELEMETRY_PB_H

#include <cstddef>
#include <cstdint>
#include "generated/telemetry.pb.h"

namespace telemetry {

/**
 * Fill @p frame from the module getters, with the same service-status NaN
 * gating the WebSocket frames use. The run recorder samples its channels
 * from this so both stay in step.
 *
 * Writes only to @p frame, so callers on different tasks each pass their own.
 *
 * @param frame  Frame to overwrite (zeroed first).
 */
void fillFrame(cryocooler_TelemetryFrame& frame);

/**
 * Encode the current telemetry state into a Protobuf binary frame.
 *
 * Reads from the same module getter functions that emit() uses, so the
 * data is always a fresh snapshot (not a copy of the FrameBuilder).
 *
 * Safe to call at any time, including during startup.  Modules that have
 * not yet initialised contribute zero/empty defaults (proto3 semantics).
 *
 * @param buf      Output buffer for the encoded Protobuf bytes.
 * @param bufSize  Size of the output buffer in bytes.
 * @return         Number of bytes written, or 0 on encoding failure.
 */
size_t encodeProtobuf(uint8_t* buf, size_t bufSize);

} // namespace telemetry

#endif // TELEMETRY_PB_H
