#!/bin/bash
# Start the DR2 community server with debug-clubs mode enabled.
# Usage: run_server_debug.sh <probes_json_file>
set -e
cd "$(dirname "$0")/.."

export DR2_DEBUG_CLUBS_FILE="${1:-$PWD/runtime/discovery/probes_batch1.json}"
export DR2_DISCOVERY_MODE=1
export PYTHONUNBUFFERED=1

echo "DR2_DEBUG_CLUBS_FILE=$DR2_DEBUG_CLUBS_FILE"
echo "DR2_DISCOVERY_MODE=$DR2_DISCOVERY_MODE"

exec python -m dr2server.httpd \
    --ssl-cert "C:/Users/winrid/AppData/Roaming/DirtForever/certs/dr2server-cert.pem" \
    --ssl-key  "C:/Users/winrid/AppData/Roaming/DirtForever/certs/dr2server-key.pem" \
    --data-dir data \
    --capture-dir captures \
    --api-url https://dirtforever.net \
    --api-token df_eabcf8c9db828ab400824dba6a020521
