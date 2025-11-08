# QueueCTL - Quick Docker Start Guide

## Prerequisites
- Docker installed and running
- Docker Compose (optional, but recommended)

## Quick Start (3 Methods)

### Method 1: Using Docker Compose (Recommended)

```bash
# 1. Build and start services
docker-compose up -d

# 2. Run commands
docker exec -it queuectl python queuectl.py status
docker exec -it queuectl python queuectl.py enqueue '{"id":"test1","command":"echo hello"}'
docker exec -it queuectl python queuectl.py worker start --count 2

# 3. Stop services
docker-compose down
```

### Method 2: Using the Helper Script

```bash
# Make script executable (Linux/Mac)
chmod +x docker-run.sh

# Run commands
./docker-run.sh status
./docker-run.sh enqueue '{"id":"test1","command":"echo hello"}'
./docker-run.sh worker start --count 2
./docker-run.sh list
```

### Method 3: Manual Docker Commands

```bash
# 1. Build image
docker build -t queuectl .

# 2. Create volume
docker volume create queuectl-data

# 3. Run container
docker run -it --rm \
  -v queuectl-data:/app/data \
  -v $(pwd)/queuectl.py:/app/queuectl.py \
  -e QUEUECTL_DB=/app/data/queuectl.db \
  queuectl \
  python queuectl.py status
```

## Complete Example

```bash
# Start with docker-compose
docker-compose up -d

# Check status
docker exec -it queuectl python queuectl.py status

# Enqueue jobs
docker exec -it queuectl python queuectl.py enqueue '{"id":"job1","command":"echo Hello"}'
docker exec -it queuectl python queuectl.py enqueue '{"id":"job2","command":"python -c \"print(42)\""}'

# Start workers
docker exec -it queuectl python queuectl.py worker start --count 3

# Wait a few seconds, then check status
docker exec -it queuectl python queuectl.py status

# List completed jobs
docker exec -it queuectl python queuectl.py list --state completed

# Stop workers
docker exec -it queuectl python queuectl.py worker stop

# Stop containers
docker-compose down
```

## Database Persistence

The database is stored in:
- `./data/queuectl.db` (when using docker-compose)
- Docker volume `queuectl-data` (when using docker-run.sh)

Data persists across container restarts!

## Troubleshooting

**Docker not found:**
- Install Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Ensure Docker is running: `docker ps`

**Permission denied:**
- On Linux: Add user to docker group or use `sudo`
- On Windows: Run Docker Desktop as administrator

**Container won't start:**
- Check logs: `docker-compose logs`
- Verify ports aren't in use
- Ensure Docker has enough resources allocated

