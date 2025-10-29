#!/bin/bash
# Startup script for Cloud Run
# This script reads the PORT environment variable set by Cloud Run

set -e

echo "Starting Ninja Tutor Backend..."
echo "PORT environment variable: ${PORT}"

# Use PORT if set, otherwise default to 8000
LISTEN_PORT=${PORT:-8000}

echo "Starting on port: $LISTEN_PORT"

# Start uvicorn with exec to replace the shell process
exec uvicorn main:app --host 0.0.0.0 --port "$LISTEN_PORT"

