# QueueCTL - Docker Container Setup

This guide explains how to run QueueCTL in a Docker container.

## Quick Start

### Option 1: Using the Docker Run Script

1. **Make the script executable:**
   ```bash
   chmod +x docker-run.sh
   ```

2. **Run commands:**
   ```bash
   # Check status
   ./docker-run.sh status

   # Enqueue a job
   ./docker-run.sh enqueue '{"id":"test1","command":"echo hello"}'

   # Start workers
   ./docker-run.sh worker start --count 2

   # List jobs
   ./docker-run.sh list
   ```

### Option 2: Using Docker Compose

1. **Start the services:**
   ```bash
   docker-compose up -d
   ```

2. **Run commands in the container:**
   ```bash
   # Execute commands in the queuectl container
   docker exec -it queuectl python queuectl.py status
   docker exec -it queuectl python queuectl.py enqueue '{"id":"test1","command":"echo hello"}'
   docker exec -it queuectl python queuectl.py worker start --count 2
   ```

3. **Stop the services:**
   ```bash
   docker-compose down
   ```

### Option 3: Manual Docker Commands

1. **Build the image:**
   ```bash
   docker build -t queuectl .
   ```

2. **Create a volume for the database:**
   ```bash
   docker volume create queuectl-data
   ```

3. **Run a container:**
   ```bash
   docker run -it --rm \
     -v queuectl-data:/app/data \
     -v $(pwd)/queuectl.py:/app/queuectl.py \
     queuectl \
     python queuectl.py status
   ```

4. **Run interactively:**
   ```bash
   docker run -it --rm \
     -v queuectl-data:/app/data \
     -v $(pwd)/queuectl.py:/app/queuectl.py \
     queuectl \
     bash
   ```

## Complete Example Workflow

```bash
# 1. Build and start
./docker-run.sh

# 2. Check status
./docker-run.sh status

# 3. Enqueue jobs
./docker-run.sh enqueue '{"id":"job1","command":"echo Hello"}'
./docker-run.sh enqueue '{"id":"job2","command":"python -c \"print(42)\""}'

# 4. Start workers
./docker-run.sh worker start --count 2

# 5. Check status
./docker-run.sh status

# 6. List completed jobs
./docker-run.sh list --state completed

# 7. Stop workers
./docker-run.sh worker stop
```

## Database Persistence

The database is stored in a Docker volume (`queuectl-data`) or in the `./data` directory when using docker-compose. This ensures data persists across container restarts.

## Running All Commands Sequentially

You can also run the shell script inside the container:

```bash
docker exec -it queuectl-container bash -c "bash run_all_commands.sh"
```

Or copy the script and run it:

```bash
docker cp run_all_commands.sh queuectl-container:/app/
docker exec -it queuectl-container bash run_all_commands.sh
```

## Troubleshooting

### Container won't start
- Check if port conflicts exist
- Verify Docker is running: `docker ps`

### Database not persisting
- Ensure volumes are properly mounted
- Check volume exists: `docker volume ls`

### Permission issues
- On Linux/Mac, you may need `sudo` for Docker commands
- On Windows, ensure Docker Desktop is running

## Clean Up

```bash
# Stop and remove containers
docker-compose down

# Remove volumes (WARNING: deletes data)
docker volume rm queuectl-data

# Remove image
docker rmi queuectl
```

