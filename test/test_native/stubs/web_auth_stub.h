/**
 * @file web_auth_stub.h
 * @brief Test access to the in-RAM dashboard and OTA password store.
 */

#ifndef WEB_AUTH_STUB_H
#define WEB_AUTH_STUB_H

namespace web_auth_stub {

/** No dashboard password, default OTA password, saves succeed. */
void reset();

const char* dashboardPassword();  ///< "" when none is set
const char* otaPassword();        ///< the default until one is set
void setSaveFails(bool fails);    ///< make the setters report a flash failure

} // namespace web_auth_stub

#endif // WEB_AUTH_STUB_H
