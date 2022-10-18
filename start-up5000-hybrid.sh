#!/bin/bash
#

. /opt/victronenergy/serial-starter/run-service.sh

app="python3 /opt/victronenergy/dbus-up5000-hybrid/dbus-up5000-hybrid.py $*"
start 
