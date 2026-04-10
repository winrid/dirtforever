#!/bin/bash

cd /home/winrid/dirtforever-web/web

.venv/bin/python -m gunicorn \
          --access-logfile - \
          --error-logfile - \
          --workers 4 \
          --timeout 300 \
          --bind 127.0.0.1:5050 \
          server:app
