/**
 * @file esp_log.h
 * @brief Minimal ESP-IDF logging stub for native (host-PC) unit tests.
 *
 * Silences all ESP_LOG* macros so that source files that include esp_log.h
 * compile cleanly under the native toolchain without any hardware dependency.
 */
#pragma once

#define ESP_LOGE(tag, fmt, ...) do {} while (0)
#define ESP_LOGW(tag, fmt, ...) do {} while (0)
#define ESP_LOGI(tag, fmt, ...) do {} while (0)
#define ESP_LOGD(tag, fmt, ...) do {} while (0)
#define ESP_LOGV(tag, fmt, ...) do {} while (0)
