#!/bin/bash
set -euo pipefail

cd /home/winrid/dirtforever-web/web

# Data migrations run before the first request is served. They are idempotent,
# so a restart that ships nothing new is a no-op. A failure aborts the start
# (set -e) rather than serving data the code no longer understands.
.venv/bin/python -m migrations

.venv/bin/python -m gunicorn \
          --access-logfile - \
          --error-logfile - \
          --workers 4 \
          --timeout 300 \
          --bind 127.0.0.1:5050 \
          server:app
