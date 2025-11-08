# QueueCTL - Terminal Commands Guide

Complete guide to run QueueCTL project in terminal.

## 🚀 Quick Start

### 1. Initial Setup (First Time Only)

```bash
# Navigate to project directory
cd queuectl

# Create virtual environment (if not exists)
python -m venv .venv

# Activate virtual environment
# On Windows (Git Bash/PowerShell):
.venv/Scripts/activate
# On Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Basic Commands

#### Check Status
```bash
python queuectl.py status
```

#### Enqueue a Job
```bash
python queuectl.py enqueue '{"id":"job1","command":"echo Hello World"}'
```

#### Start Workers
```bash
# Start 1 worker
python queuectl.py worker start

# Start multiple workers
python queuectl.py worker start --count 3
```

#### List Jobs
```bash
# List all jobs
python queuectl.py list

# List by state
python queuectl.py list --state pending
python queuectl.py list --state completed
python queuectl.py list --state failed
python queuectl.py list --state dead
```

#### Stop Workers
```bash
python queuectl.py worker stop
```

## 📋 Complete Workflow Example

### Step-by-Step Complete Run

```bash
# 1. Activate virtual environment
.venv/Scripts/activate  # Windows
# OR
source .venv/bin/activate  # Linux/Mac

# 2. Check initial status
python queuectl.py status

# 3. Enqueue multiple jobs
python queuectl.py enqueue '{"id":"test1","command":"echo Test Job 1"}'
python queuectl.py enqueue '{"id":"test2","command":"python -c \"print(42)\""}'
python queuectl.py enqueue '{"id":"test3","command":"echo Test Job 3"}'

# 4. List pending jobs
python queuectl.py list --state pending

# 5. Check configuration
python queuectl.py config get

# 6. Start workers (3 workers)
python queuectl.py worker start --count 3

# 7. Wait a few seconds, then check status
python queuectl.py status

# 8. List completed jobs
python queuectl.py list --state completed

# 9. Check Dead Letter Queue
python queuectl.py dlq list

# 10. Stop workers
python queuectl.py worker stop

# 11. Final status check
python queuectl.py status
```

## 🔧 Configuration Commands

### View Configuration
```bash
python queuectl.py config get
```

### Set Configuration
```bash
python queuectl.py config set max_retries 5
python queuectl.py config set backoff_base 3
python queuectl.py config set poll_interval 1.0
python queuectl.py config set job_timeout 300
```

## 📊 Advanced Commands

### Dead Letter Queue (DLQ)
```bash
# List DLQ jobs
python queuectl.py dlq list

# Retry a job from DLQ
python queuectl.py dlq retry job-id-here
```

### Job Examples

#### Simple Job
```bash
python queuectl.py enqueue '{"command":"echo Hello"}'
```

#### Job with Custom ID
```bash
python queuectl.py enqueue '{"id":"my-job","command":"echo Custom Job"}'
```

#### Job with Priority
```bash
python queuectl.py enqueue '{"id":"priority-job","command":"echo High Priority","priority":10}'
```

#### Job with Custom Retries
```bash
python queuectl.py enqueue '{"id":"retry-job","command":"exit 1","max_retries":5}'
```

#### Scheduled Job (Delayed Execution)
```bash
python queuectl.py enqueue '{"id":"scheduled","command":"echo Future","run_at":"2025-11-08T20:00:00Z"}'
```

#### Python Script Job
```bash
python queuectl.py enqueue '{"id":"python-job","command":"python -c \"print(\\\"Hello from Python\\\")\""}'
```

## 🧪 Testing Commands

### Run Test Script
```bash
python test_queuectl.py
```

### Run Validation Script
```bash
python validate_all_requirements.py
```

## 📝 One-Liner Examples

### Quick Test
```bash
python queuectl.py enqueue '{"command":"echo test"}' && python queuectl.py worker start --count 1 && sleep 3 && python queuectl.py status
```

### Enqueue and Process
```bash
python queuectl.py enqueue '{"id":"quick","command":"echo done"}' && python queuectl.py worker start --count 2 && sleep 5 && python queuectl.py list --state completed
```

## 🔄 Common Workflows

### Workflow 1: Basic Job Processing
```bash
# Enqueue job
python queuectl.py enqueue '{"id":"basic","command":"echo Success"}'

# Start worker
python queuectl.py worker start --count 1

# Wait and check
sleep 2
python queuectl.py status
python queuectl.py list --state completed

# Stop worker
python queuectl.py worker stop
```

### Workflow 2: Multiple Jobs with Multiple Workers
```bash
# Enqueue 5 jobs
for i in {1..5}; do
  python queuectl.py enqueue "{\"id\":\"job$i\",\"command\":\"echo Job $i\"}"
done

# Start 3 workers
python queuectl.py worker start --count 3

# Monitor
sleep 5
python queuectl.py status

# Check results
python queuectl.py list --state completed

# Stop workers
python queuectl.py worker stop
```

### Workflow 3: Testing Retry Mechanism
```bash
# Set retry config
python queuectl.py config set max_retries 3

# Enqueue a job that will fail
python queuectl.py enqueue '{"id":"fail-test","command":"exit 1"}'

# Start worker
python queuectl.py worker start --count 1

# Monitor retries
sleep 10
python queuectl.py status
python queuectl.py list --state failed

# After max retries, check DLQ
python queuectl.py dlq list

# Stop worker
python queuectl.py worker stop
```

## 🐳 Docker Commands (If Using Docker)

### Using Docker Compose
```bash
# Start
docker-compose up -d

# Run commands
docker exec -it queuectl python queuectl.py status
docker exec -it queuectl python queuectl.py enqueue '{"id":"test","command":"echo hello"}'

# Stop
docker-compose down
```

### Using Helper Script
```bash
./docker-run.sh status
./docker-run.sh enqueue '{"id":"test","command":"echo hello"}'
./docker-run.sh worker start --count 2
```

## 💡 Tips

1. **Always activate virtual environment first**
   ```bash
   .venv/Scripts/activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```

2. **Check status frequently**
   ```bash
   python queuectl.py status
   ```

3. **Use background workers**
   ```bash
   python queuectl.py worker start --count 3 &
   ```

4. **Monitor in real-time**
   ```bash
   watch -n 1 'python queuectl.py status'  # Linux/Mac
   ```

5. **Stop workers gracefully**
   ```bash
   python queuectl.py worker stop
   ```

## ❓ Troubleshooting

### Workers Not Processing
```bash
# Check if workers are running
python queuectl.py status

# Check pending jobs
python queuectl.py list --state pending

# Restart workers
python queuectl.py worker stop
python queuectl.py worker start --count 2
```

### Database Issues
```bash
# Check database file exists
ls -la queuectl.db

# Reinitialize (if needed)
python queuectl.py status  # This initializes DB
```

### Permission Issues
```bash
# Make script executable (Linux/Mac)
chmod +x queuectl.py
```

## 📚 Command Reference

| Command | Description |
|---------|-------------|
| `status` | Show job and worker status |
| `enqueue <json>` | Add job to queue |
| `list [--state <state>]` | List jobs (optionally filtered) |
| `worker start [--count N]` | Start worker processes |
| `worker stop` | Stop all workers |
| `config get` | Show configuration |
| `config set <key> <value>` | Set configuration |
| `dlq list` | List Dead Letter Queue |
| `dlq retry <job-id>` | Retry job from DLQ |

## 🎯 Quick Reference Card

```bash
# Setup
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -r requirements.txt

# Daily Use
python queuectl.py status
python queuectl.py enqueue '{"command":"echo test"}'
python queuectl.py worker start --count 2
python queuectl.py list
python queuectl.py worker stop
```

