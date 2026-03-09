#!/usr/bin/env bash

cd $(git rev-parse --show-toplevel)
http-server -p 8081 data