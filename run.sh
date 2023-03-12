#!/bin/sh
set -e
ssh-keygen -f "/root/.ssh/known_hosts" -R "github.com"
python main.py
