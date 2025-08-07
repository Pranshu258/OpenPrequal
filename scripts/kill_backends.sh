#!/bin/bash
# Script to kill all backend and proxy servers started by start_backends.sh

# Kill all uvicorn processes running src.server:app or src.proxy:app
ps aux | grep 'uvicorn' | grep -E 'src\.server:app|src\.proxy:app' | grep -v grep | awk '{print $2}' | xargs -r kill

echo "Killed all backend and proxy servers."
