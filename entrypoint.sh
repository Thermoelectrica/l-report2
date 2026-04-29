#!/bin/sh
set -e

# Clone reports from git repository if REPORTS_GIT_URL is provided
if [ -n "$REPORTS_GIT_URL" ]; then
    echo "Cloning reports from $REPORTS_GIT_URL..."
    
    # Set default branch if not specified
    REPORTS_GIT_BRANCH=${REPORTS_GIT_BRANCH:-main}
    
    # Clean up existing reports directory
    rm -rf /reports/*
    
    # Clone the repository
    if [ -n "$REPORTS_GIT_TOKEN" ]; then
        # Use token authentication if provided
        echo "Using token authentication..."
        git clone --depth 1 --branch "$REPORTS_GIT_BRANCH" \
            "https://oauth2:${REPORTS_GIT_TOKEN}@${REPORTS_GIT_URL#https://}" \
            /reports
    else
        # Use URL as-is (for public repos or SSH)
        git clone --depth 1 --branch "$REPORTS_GIT_BRANCH" \
            "$REPORTS_GIT_URL" /reports
    fi
    
    echo "Reports cloned successfully from branch: $REPORTS_GIT_BRANCH"
else
    echo "REPORTS_GIT_URL not set, using existing reports in /reports"
fi

# Use PORT environment variable, default to 8080 if not set
PORT=${PORT:-8080}

echo "Starting reflex on port $PORT"

# Run reflex
exec reflex run --env prod --single-port --frontend-port "$PORT"
