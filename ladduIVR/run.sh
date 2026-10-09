#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/Bluetooth-Audio-Manager-x86_64.AppImage" "$@"
