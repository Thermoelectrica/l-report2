#!/bin/sh
set -e

# Use PORT environment variable, default to 8080 if not set
PORT=${PORT:-8080}

echo "Running reflex on port $PORT"

# Run reflex
reflex run --env prod --single-port --frontend-port "$PORT"
