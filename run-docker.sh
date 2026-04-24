#!/bin/bash
set -e

# Script to run the Docker container locally

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create a .env file based on .env.example"
    exit 1
fi

# Image name
IMAGE_NAME="report2-app"
CONTAINER_NAME="report2-app-local"

# Stop and remove existing container if running
echo "Stopping existing container (if any)..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# Build the image
echo "Building Docker image..."
docker build -t $IMAGE_NAME .

# Run the container
echo "Starting container on port $PORT..."
docker run -d \
    --name $CONTAINER_NAME \
    --env-file .env \
    -p 8080:8080 \
    -p 8000:8000 \
    -v "$(pwd)/uploaded_files:/app/uploaded_files" \
    -v "$(pwd)/output:/app/output" \
    -v "$(pwd)/sample_reports:/app/sample_reports" \
    $IMAGE_NAME

echo ""
echo "Container started successfully!"
echo "Application is running at: http://localhost:$PORT"
echo ""
echo "Useful commands:"
echo "  View logs:        docker logs -f $CONTAINER_NAME"
echo "  Stop container:   docker stop $CONTAINER_NAME"
echo "  Remove container: docker rm $CONTAINER_NAME"
echo "  Shell access:     docker exec -it $CONTAINER_NAME /bin/sh"
