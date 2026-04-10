#!/bin/bash

sudo cp dirtforever-web.service /etc/systemd/system/
sudo systemctl enable dirtforever-web
sudo systemctl restart dirtforever-web
