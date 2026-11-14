#!/usr/bin/env bash
# Build, upload over WiFi, and wait for the board to come back.
# The board's name comes from HOSTNAME in include/config/config.h.

cd "$(dirname "$0")/.." || exit 1

HOSTNAME_VALUE=$(sed -nE 's/^#define[[:space:]]+HOSTNAME[[:space:]]+"([^"]+)".*/\1/p' include/config/config.h)
if [ -z "$HOSTNAME_VALUE" ]; then
	echo "HOSTNAME not found in include/config/config.h" >&2
	exit 1
fi
DEVICE_HOST="$HOSTNAME_VALUE.local"

pio run -e esp32s3 &&
	curl -vF "firmware=@.pio/build/esp32s3/firmware.bin" "http://$DEVICE_HOST/ota" &&
	printf "\nWaiting for device.." &&
	until nc -z "$DEVICE_HOST" 80; do
		printf ".";
		sleep 1;
	done &&
	printf "\nDone\n"
