#!/bin/bash
# QueueCTL - Docker Container Runner
# This script helps run QueueCTL commands in a Docker container

set -e

IMAGE_NAME="queuectl"
CONTAINER_NAME="queuectl-container"
DB_VOLUME="queuectl-data"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}QueueCTL Docker Runner${NC}"
echo "===================="
echo ""

# Build the Docker image
echo -e "${GREEN}Building Docker image...${NC}"
docker build -t $IMAGE_NAME .

# Create volume for database if it doesn't exist
if ! docker volume ls | grep -q $DB_VOLUME; then
    echo -e "${GREEN}Creating database volume...${NC}"
    docker volume create $DB_VOLUME
fi

# Check if container is running
if docker ps | grep -q $CONTAINER_NAME; then
    echo -e "${GREEN}Container is already running${NC}"
else
    echo -e "${GREEN}Starting container...${NC}"
    docker run -d \
        --name $CONTAINER_NAME \
        -v $DB_VOLUME:/app/data \
        -v $(pwd)/queuectl.py:/app/queuectl.py \
        -v $(pwd)/job.json:/app/job.json \
        -e QUEUECTL_DB=/app/data/queuectl.db \
        -e DATABASE_URL=sqlite:///data/queuectl.db \
        $IMAGE_NAME \
        tail -f /dev/null
fi

# Run the command passed as argument, or show help
if [ $# -eq 0 ]; then
    echo ""
    echo "Usage examples:"
    echo "  ./docker-run.sh status"
    echo "  ./docker-run.sh enqueue '{\"id\":\"test1\",\"command\":\"echo hello\"}'"
    echo "  ./docker-run.sh worker start --count 2"
    echo "  ./docker-run.sh list"
    echo ""
    echo "Or run interactively:"
    echo "  docker exec -it $CONTAINER_NAME bash"
    echo ""
    docker exec -it $CONTAINER_NAME python queuectl.py --help
else
    echo -e "${GREEN}Running command: $@${NC}"
    docker exec -it $CONTAINER_NAME python queuectl.py "$@"
fi

