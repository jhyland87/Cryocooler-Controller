#!/usr/bin/env bash

pio run -e esp32s3 &&
	curl -vF "firmware=@.pio/build/esp32s3/firmware.bin" http://cryocooler.local/ota &&
	printf "\nWaiting for device.." &&
	until nc -z 192.168.0.42 80; do
		printf ".";
		sleep 1;
	done &&
	printf "\nDone\n"