# CLI-based Background Job Queue System

A robust, production-grade background job queue system implemented in Python, featuring worker processes, automatic retries with exponential backoff, and Dead Letter Queue (DLQ) support.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 📺 Demo Video

[Watch the demo video on Google Drive](https://drive.google.com/file/d/1hWZieEsgbUfHMgOZsbcaqKXMJCp9L8cb/view?usp=sharing)

## 🚀 Features

- **Job Management**: Enqueue, list, and monitor background jobs
- **Worker Processes**: Run multiple workers in parallel for concurrent job processing
- **Automatic Retries**: Failed jobs retry automatically with exponential backoff
- **Dead Letter Queue**: Permanently failed jobs are moved to DLQ for manual inspection
- **Persistent Storage**: SQLite database ensures jobs survive restarts
- **Graceful Shutdown**: Workers finish current jobs before shutting down
- **Configuration Management**: Configurable retry count, backoff base, and timeouts
- **Job Priority**: Support for job priorities (higher priority jobs processed first)
- **Scheduled Jobs**: Support for delayed execution via `run_at` field

## 📋 Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- Required Python packages (installed via requirements.txt)

## 🔧 Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd queuectl
```

2. Make the script executable (Unix/Linux/Mac):
```bash
chmod +x queuectl.py
```

3. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

4. Install required packages:
```bash
pip install -r requirements.txt
```

5. Set up PostgreSQL:
```bash
# Create database
createdb queuectl

# Or using psql
psql -U postgres
CREATE DATABASE queuectl;
```

6. Configure environment:
Copy the `.env.example` file to `.env` and update the database connection settings:
```bash
cp .env.example .env
# Edit .env with your PostgreSQL connection details
```

## 📖 Usage

### Basic Commands

#### Enqueue a Job

Add a new job to the queue:

```bash
python queuectl.py enqueue '{"id":"job1","command":"echo Hello World"}'
```

Or with auto-generated ID:

```bash
python queuectl.py enqueue '{"command":"sleep 2"}'
```

**Job JSON Fields:**
- `id` (optional): Unique job identifier (auto-generated if not provided)
- `command` (required): Shell command to execute
- `max_retries` (optional): Maximum retry attempts (default: from config)
- `run_at` (optional): ISO timestamp for delayed execution
- `priority` (optional): Job priority (higher = processed first, default: 0)

**Examples:**
```bash
# Simple job
python queuectl.py enqueue '{"command":"echo test"}'

# Job with custom ID and retries
python queuectl.py enqueue '{"id":"my-job","command":"python script.py","max_retries":5}'

# High priority job
python queuectl.py enqueue '{"command":"important-task","priority":10}'

# Scheduled job (run in 1 hour)
python queuectl.py enqueue '{"command":"backup.sh","run_at":"2025-11-08T15:00:00Z"}'
```

#### Start Workers

Start worker processes to process jobs:

```bash
# Start a single worker
python queuectl.py worker start

# Start multiple workers
python queuectl.py worker start --count 3
```

Workers will:
- Continuously poll for available jobs
- Execute jobs in parallel
- Handle retries with exponential backoff
- Update job states atomically to prevent duplicate processing

#### Stop Workers

Gracefully stop all running workers:

```bash
python queuectl.py worker stop
```

Workers will finish their current job before shutting down.

#### Check Status

View summary of jobs and workers:

```bash
python queuectl.py status
```

**Example Output:**
```
Jobs:
  pending   : 5
  processing: 2
  completed : 10
  failed    : 1
  dead      : 0
  total     : 18

Workers:
  worker-a1b2c3d4 pid=12345 status=running hb=2025-11-08T14:30:00Z
  worker-e5f6g7h8 pid=12346 status=running hb=2025-11-08T14:30:01Z
```

#### List Jobs

List all jobs or filter by state:

```bash
# List all jobs
python queuectl.py list

# List only pending jobs
python queuectl.py list --state pending

# List completed jobs
python queuectl.py list --state completed

# List failed jobs
python queuectl.py list --state failed

# List dead jobs (DLQ)
python queuectl.py list --state dead
```

#### Dead Letter Queue (DLQ)

View jobs in the Dead Letter Queue:

```bash
python queuectl.py dlq list
```

Retry a job from DLQ (resets attempts and moves back to pending):

```bash
python queuectl.py dlq retry job1
```

#### Configuration

View current configuration:

```bash
python queuectl.py config get
```

**Configuration Options:**
- `max_retries`: Default maximum retry attempts (default: 3)
- `backoff_base`: Base for exponential backoff calculation (default: 2)
- `poll_interval`: Worker polling interval in seconds (default: 0.5)
- `job_timeout`: Maximum job execution time in seconds (default: 120)

Set configuration values:

```bash
python queuectl.py config set max_retries 5
python queuectl.py config set backoff_base 3
python queuectl.py config set poll_interval 1.0
python queuectl.py config set job_timeout 300
```

## 🔄 Job Lifecycle

Jobs progress through the following states:

1. **pending**: Job is waiting to be picked up by a worker
2. **processing**: Job is currently being executed by a worker
3. **completed**: Job executed successfully
4. **failed**: Job failed but has retries remaining (will retry with backoff)
5. **dead**: Job permanently failed (moved to DLQ after exhausting retries)

### Retry Mechanism

When a job fails:
1. The attempt count is incremented
2. If attempts ≤ max_retries: Job is scheduled for retry with exponential backoff
3. If attempts > max_retries: Job is moved to DLQ (dead state)

**Exponential Backoff Formula:**
```
delay = base^attempts seconds
```

Example with `backoff_base = 2`:
- 1st retry: 2^1 = 2 seconds
- 2nd retry: 2^2 = 4 seconds
- 3rd retry: 2^3 = 8 seconds

## 🏗️ Architecture

### Data Persistence

- **Database**: SQLite with WAL (Write-Ahead Logging) mode for better concurrency
- **Location**: `queuectl.db` (configurable via `QUEUECTL_DB` environment variable)
- **Tables**:
  - `jobs`: Job data with state, attempts, timestamps, etc.
  - `workers`: Worker process tracking
  - `config`: Configuration key-value pairs

### Concurrency & Locking

- **Atomic Job Picking**: Uses SQLite transactions to atomically claim jobs
- **No Duplicate Processing**: Jobs are marked as "processing" when picked up
- **Multiple Workers**: Workers can process different jobs in parallel
- **Database Locking**: SQLite WAL mode handles concurrent reads/writes

### Worker Process Model

- Each worker runs in a separate process
- Workers poll the database for available jobs
- Heartbeat mechanism tracks worker health
- Graceful shutdown: workers finish current job before exiting

## 🧪 Testing

A test script is provided to validate core functionality:

```bash
python test_queuectl.py
```

This script tests:
1. ✅ Basic job completion
2. ✅ Failed job retries with backoff
3. ✅ Multiple workers processing jobs
4. ✅ Invalid commands fail gracefully
5. ✅ Job persistence across restarts
6. ✅ DLQ functionality

### Manual Testing Examples

**Test 1: Basic Success**
```bash
python queuectl.py enqueue '{"id":"test1","command":"echo success"}'
python queuectl.py worker start --count 1
# Wait a few seconds
python queuectl.py list --state completed
```

**Test 2: Retry with Backoff**
```bash
python queuectl.py config set max_retries 3
python queuectl.py enqueue '{"id":"test2","command":"exit 1"}'
python queuectl.py worker start --count 1
# Watch status to see retries
python queuectl.py status
# After max retries, check DLQ
python queuectl.py dlq list
```

**Test 3: Multiple Workers**
```bash
# Enqueue multiple jobs
for i in {1..10}; do
  python queuectl.py enqueue '{"id":"job$i","command":"sleep 1"}'
done
# Start 3 workers
python queuectl.py worker start --count 3
# Watch them process in parallel
python queuectl.py status
```

**Test 4: Persistence**
```bash
# Enqueue jobs
python queuectl.py enqueue '{"id":"persist1","command":"echo test"}'
# Stop workers
python queuectl.py worker stop
# Restart workers - jobs should still be there
python queuectl.py status
python queuectl.py worker start
```

## 📊 Example Workflow

```bash
# 1. Check initial status
python queuectl.py status

# 2. Enqueue some jobs
python queuectl.py enqueue '{"id":"job1","command":"echo Hello"}'
python queuectl.py enqueue '{"id":"job2","command":"sleep 2"}'
python queuectl.py enqueue '{"id":"job3","command":"python -c "print(42)"}'

# 3. Start workers
python queuectl.py worker start --count 2

# 4. Monitor progress
python queuectl.py status
python queuectl.py list

# 5. Check completed jobs
python queuectl.py list --state completed

# 6. Stop workers when done
python queuectl.py worker stop
```

## ⚙️ Configuration

### Environment Variables

- `QUEUECTL_DB`: Path to SQLite database file (default: `queuectl.db`)

### Default Settings

- **max_retries**: 3
- **backoff_base**: 2 (exponential backoff: 2^attempts seconds)
- **poll_interval**: 0.5 seconds
- **job_timeout**: 120 seconds

## 🔍 Troubleshooting

### Workers Not Processing Jobs

1. Check if workers are running: `python queuectl.py status`
2. Verify jobs are in pending state: `python queuectl.py list --state pending`
3. Check worker logs/processes
4. Ensure database is accessible

### Jobs Stuck in Processing

If a worker crashes, jobs may remain in "processing" state. You can manually reset them:

```sql
-- Connect to SQLite
sqlite3 queuectl.db

-- Reset stuck jobs
UPDATE jobs SET state = 'pending', picked_by = NULL WHERE state = 'processing';
```

### Database Locked

If you see "database is locked" errors:
- Ensure only one process is accessing the database at a time
- Check for zombie worker processes
- Restart workers: `python queuectl.py worker stop && python queuectl.py worker start`

## 🎯 Design Decisions & Trade-offs

### Why SQLite?

- **Simplicity**: No external dependencies, easy setup
- **Persistence**: Data survives restarts
- **ACID**: Transactional guarantees for job picking
- **WAL Mode**: Better concurrency for multiple workers
- **Portability**: Single file, easy to backup/move

### Why Multiprocessing for Workers?

- **Isolation**: Worker crashes don't affect other workers
- **True Parallelism**: Multiple jobs can run simultaneously
- **OS-level Process Management**: Easier to monitor and kill

### Trade-offs

- **SQLite Limitations**: Not ideal for very high throughput (thousands of jobs/second)
- **No Distributed Support**: Single database file (can't scale across machines)
- **Simple Priority**: Basic integer-based priority (no complex scheduling)
- **No Job Dependencies**: Jobs are independent (no workflow support)

## 🚧 Future Enhancements (Bonus Features)

Potential improvements:
- [ ] Job timeout handling (partially implemented via config)
- [x] Job priority queues (implemented)
- [x] Scheduled/delayed jobs (implemented via `run_at`)
- [ ] Job output logging to files
- [ ] Metrics/execution stats endpoint
- [ ] Minimal web dashboard for monitoring
- [ ] Job dependencies and workflows
- [ ] Distributed workers across machines

## 📝 License

This project is part of a backend developer internship assignment.

## 👤 Author

Built as part of the QueueCTL assignment requirements.

---

## ✅ Checklist

- [x] Working CLI application (`queuectl`)
- [x] Persistent job storage (SQLite)
- [x] Multiple worker support
- [x] Retry mechanism with exponential backoff
- [x] Dead Letter Queue
- [x] Configuration management
- [x] Clean CLI interface with help texts
- [x] Comprehensive README.md
- [x] Code structured with clear separation of concerns
- [x] Test script to validate core flows