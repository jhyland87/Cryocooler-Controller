/**
 * @file sensor_mock.cpp
 * @brief Runtime sensor override layer — implementation.
 */

#include "sensor_mock.h"

namespace sensor_mock {

static bool      sActive    = false;
static Overrides sOverrides = {};   // value-initialised to safe defaults

void enable()  { sActive = true;  }
void disable() { sActive = false; }
bool isActive(){ return sActive;  }

Overrides& get() { return sOverrides; }

} // namespace sensor_mock
