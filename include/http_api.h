/**
 * @file http_api.h
 * @brief HTTP API server interface
 *
 * Manages the HTTP API server.
 */

 #ifndef HTTP_API_H
 #define HTTP_API_H

 namespace http_api {

 /**
  * Initialize the HTTP API server.
  */
 void init();

 /**
  * Service the HTTP API server.
  */
 void service();

 } // namespace http_api

 #endif // HTTP_API_H
