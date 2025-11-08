#!/usr/bin/env python3
import argparse
import os
import json
import datetime as dt
import sys
import subprocess
import time
import signal
import multiprocessing
import uuid
import threading
import sqlite3
from sqlite3 import Error
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database configuration from environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///queuectl.db")
QUEUECTL_DB = os.getenv("QUEUECTL_DB", "queuectl.db")

DEFAULTS = {
    "max_retries": "3",
    "backoff_base": "2",
    "poll_interval": "0.5",
    "job_timeout": "120",
}

# ---------------- DB helpers ----------------
def _connect():
    # Extract database path from QUEUECTL_DB or DATABASE_URL
    db_path = QUEUECTL_DB
    if db_path.startswith("sqlite:///"):
        db_path = db_path.replace("sqlite:///", "")
    elif DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable named parameters
    return conn

def init_db():
    conn = _connect()
    with conn:
        # Create jobs table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            command TEXT NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            due_at TIMESTAMP WITH TIME ZONE NOT NULL,
            last_error TEXT,
            output TEXT,
            priority INTEGER NOT NULL DEFAULT 0,
            picked_by TEXT
        );
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state_due ON jobs(state, due_at);")
        
        # Create workers table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS workers(
            id TEXT PRIMARY KEY,
            pid INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TIMESTAMP WITH TIME ZONE NOT NULL,
            heartbeat_at TIMESTAMP WITH TIME ZONE NOT NULL,
            stopped_at TIMESTAMP WITH TIME ZONE
        );
        """)
        
        # Create config table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS config(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)
        
        # Seed defaults - using ON CONFLICT for upsert
        for k, v in DEFAULTS.items():
            conn.execute("""
                INSERT INTO config(key, value) 
                VALUES(?, ?) 
                ON CONFLICT (key) DO NOTHING
            """, (k, v))
    conn.close()

def now_iso():
    # Use timezone-aware datetime for UTC
    try:
        # Python 3.11+
        return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    except AttributeError:
        # Fallback for older Python versions
        return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def get_config() -> dict:
    conn = _connect()
    rows = conn.execute("SELECT key,value FROM config").fetchall()
    conn.close()
    cfg = {**DEFAULTS, **{r["key"]: r["value"] for r in rows}}
    return cfg

def set_config(key: str, value: str):
    if key not in DEFAULTS:
        sys.exit(f"Unknown config key: {key}")
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO config(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
    conn.close()

# --------------- Core ops (Step 2 scope) ---------------
def enqueue_job(job_json: str):
    try:
        job = json.loads(job_json)
    except json.JSONDecodeError as e:
        sys.exit(f"Invalid JSON: {e}")

    if "command" not in job:
        sys.exit("Job must include 'command'.")

    cfg = get_config()
    try:
        now_ts = int(dt.datetime.now(dt.timezone.utc).timestamp())
    except AttributeError:
        now_ts = int(dt.datetime.utcnow().timestamp())
    job_id = job.get("id") or f"job-{now_ts}"
    created = now_iso()
    due_at = job.get("run_at") or created
    max_retries = int(job.get("max_retries", cfg["max_retries"]))
    priority = int(job.get("priority", 0))

    row = {
        "id": job_id,
        "command": job["command"],
        "state": "pending",
        "attempts": 0,
        "max_retries": max_retries,
        "created_at": created,
        "updated_at": created,
        "due_at": due_at,
        "last_error": None,
        "output": None,
        "priority": priority,
        "picked_by": None,
    }

    conn = _connect()
    try:
        with conn:
            conn.execute("""
            INSERT INTO jobs(id,command,state,attempts,max_retries,created_at,updated_at,due_at,last_error,output,priority,picked_by)
            VALUES(:id,:command,:state,:attempts,:max_retries,:created_at,:updated_at,:due_at,:last_error,:output,:priority,:picked_by)
            """, row)
    except sqlite3.IntegrityError:
        sys.exit(f"Job with id '{job_id}' already exists.")
    finally:
        conn.close()

    print(f"Enqueued job {job_id}")

def list_jobs(state: str | None):
    conn = _connect()
    q = "SELECT id, state, attempts, max_retries, due_at, command FROM jobs"
    rows = conn.execute(q + (" WHERE state=?" if state else ""), (state,) if state else ()).fetchall()
    conn.close()

    if not rows:
        print("(no jobs)")
        return
    for r in rows:
        print(f"{r['id']:<24} {r['state']:<10} attempts={r['attempts']}/{r['max_retries']} due={r['due_at']} cmd={r['command']}")

def status_summary():
    conn = _connect()
    counts = dict(conn.execute("SELECT state, COUNT(*) FROM jobs GROUP BY state").fetchall())
    workers = conn.execute("SELECT id,pid,status,heartbeat_at FROM workers WHERE status!='stopped'").fetchall()
    conn.close()

    print("Jobs:")
    total = 0
    for st in ["pending","processing","completed","failed","dead"]:
        c = counts.get(st, 0)
        total += c
        print(f"  {st:<10}: {c}")
    print(f"  total     : {total}")

    print("\nWorkers:")
    if not workers:
        print("  (none running)")
    else:
        for w in workers:
            print(f"  {w['id']} pid={w['pid']} status={w['status']} hb={w['heartbeat_at']}")

# ---------------- Worker & Job Processing ---------------- 
def calculate_backoff_delay(attempts: int, base: float) -> float:
    """Calculate exponential backoff delay: base^attempts seconds"""
    return base ** attempts

def pick_next_job(worker_id: str) -> dict | None:
    """Atomically pick the next available job for processing"""
    conn = _connect()
    try:
        # Use a transaction to atomically pick a job
        with conn:
            # Find the oldest pending or failed job that's due
            now = now_iso()
            job = conn.execute("""
                SELECT id, command, attempts, max_retries, state
                FROM jobs
                WHERE state IN ('pending', 'failed')
                  AND due_at <= ?
                ORDER BY priority DESC, due_at ASC, created_at ASC
                LIMIT 1
            """, (now,)).fetchone()
            
            if not job:
                return None
            
            # Atomically claim the job
            result = conn.execute("""
                UPDATE jobs
                SET state = 'processing',
                    picked_by = ?,
                    updated_at = ?
                WHERE id = ? AND state IN ('pending', 'failed')
                RETURNING id, command, attempts, max_retries, state, last_error
            """, (worker_id, now, job['id'])).fetchone()
            
            if result:
                return dict(result)
            return None
    finally:
        conn.close()

def execute_job(job: dict, timeout: int) -> tuple[bool, str, str]:
    """Execute a job command and return (success, output, error)"""
    try:
        proc = subprocess.run(
            job['command'],
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )
        output = proc.stdout + proc.stderr
        success = proc.returncode == 0
        error = None if success else f"Command failed with exit code {proc.returncode}"
        return success, output, error
    except subprocess.TimeoutExpired:
        return False, "", f"Job timed out after {timeout} seconds"
    except Exception as e:
        return False, "", str(e)

def process_job(worker_id: str, shutdown_event: threading.Event):
    """Main worker loop: pick and process jobs"""
    cfg = get_config()
    poll_interval = float(cfg["poll_interval"])
    timeout = int(cfg["job_timeout"])
    backoff_base = float(cfg["backoff_base"])
    
    while not shutdown_event.is_set():
        job = pick_next_job(worker_id)
        
        if not job:
            # No jobs available, wait and check again
            time.sleep(poll_interval)
            continue
        
        job_id = job['id']
        attempts = job['attempts']
        max_retries = job['max_retries']
        
        # Execute the job
        success, output, error = execute_job(job, timeout)
        now = now_iso()
        
        conn = _connect()
        try:
            with conn:
                if success:
                    # Job succeeded
                    conn.execute("""
                        UPDATE jobs
                        SET state = 'completed',
                            attempts = attempts + 1,
                            updated_at = ?,
                            output = ?,
                            last_error = NULL,
                            picked_by = NULL
                        WHERE id = ?
                    """, (now, output[:10000], job_id))  # Limit output size
                else:
                    # Job failed
                    new_attempts = attempts + 1
                    
                    if new_attempts > max_retries:
                        # Move to DLQ
                        conn.execute("""
                            UPDATE jobs
                            SET state = 'dead',
                                attempts = ?,
                                updated_at = ?,
                                last_error = ?,
                                picked_by = NULL
                            WHERE id = ?
                        """, (new_attempts, now, error, job_id))
                    else:
                        # Schedule retry with exponential backoff
                        delay_seconds = calculate_backoff_delay(new_attempts, backoff_base)
                        try:
                            now = dt.datetime.now(dt.timezone.utc)
                            due_at = (now + dt.timedelta(seconds=delay_seconds)).isoformat().replace('+00:00', 'Z')
                        except AttributeError:
                            due_at = (dt.datetime.utcnow() + dt.timedelta(seconds=delay_seconds)).isoformat() + "Z"
                        
                        conn.execute("""
                            UPDATE jobs
                            SET state = 'failed',
                                attempts = ?,
                                updated_at = ?,
                                due_at = ?,
                                last_error = ?,
                                picked_by = NULL
                            WHERE id = ?
                        """, (new_attempts, now, due_at, error, job_id))
        finally:
            conn.close()
        
        # Small delay before picking next job
        time.sleep(0.1)

def worker_process(worker_id: str, shutdown_event: multiprocessing.Event):
    """Worker process entry point"""
    # Update heartbeat periodically
    def heartbeat_loop():
        while not shutdown_event.is_set():
            try:
                conn = _connect()
                try:
                    with conn:
                        conn.execute("""
                            UPDATE workers
                            SET heartbeat_at = ?
                            WHERE id = ?
                        """, (now_iso(), worker_id))
                finally:
                    conn.close()
            except:
                pass
            time.sleep(5)  # Heartbeat every 5 seconds
    
    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    
    # Convert multiprocessing.Event to threading.Event for process_job
    thread_shutdown = threading.Event()
    
    def check_shutdown():
        while not shutdown_event.is_set():
            time.sleep(0.1)
        thread_shutdown.set()
    
    shutdown_checker = threading.Thread(target=check_shutdown, daemon=True)
    shutdown_checker.start()
    
    # Main processing loop
    try:
        process_job(worker_id, thread_shutdown)
    except KeyboardInterrupt:
        pass
    finally:
        # Mark worker as stopped
        conn = _connect()
        try:
            with conn:
                conn.execute("""
                    UPDATE workers
                    SET status = 'stopped',
                        stopped_at = ?
                    WHERE id = ?
                """, (now_iso(), worker_id))
        finally:
            conn.close()

# Global storage for worker processes (for graceful shutdown)
_worker_processes = []

def start_workers(count: int):
    """Start worker processes"""
    global _worker_processes
    processes = []
    worker_ids = []
    
    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\nReceived shutdown signal, stopping workers...")
        stop_workers()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    for i in range(count):
        worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        worker_ids.append(worker_id)
        
        # Register worker in DB
        conn = _connect()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO workers(id, pid, status, started_at, heartbeat_at)
                    VALUES(?, ?, ?, ?, ?)
                """, (worker_id, os.getpid(), "starting", now_iso(), now_iso()))
        finally:
            conn.close()
        
        # Create shutdown event
        shutdown_event = multiprocessing.Event()
        
        # Start worker process
        proc = multiprocessing.Process(
            target=worker_process,
            args=(worker_id, shutdown_event),
            daemon=False
        )
        proc.start()
        
        # Update worker with actual PID
        conn = _connect()
        try:
            with conn:
                conn.execute("""
                    UPDATE workers
                    SET pid = ?,
                        status = 'running'
                    WHERE id = ?
                """, (proc.pid, worker_id))
        finally:
            conn.close()
        
        processes.append((proc, shutdown_event, worker_id))
        _worker_processes.append((proc, shutdown_event, worker_id))
    
    print(f"Started {count} worker(s)")
    for proc, _, wid in processes:
        print(f"  {wid} (PID: {proc.pid})")
    
    # Wait for all processes
    try:
        for proc, _, _ in processes:
            proc.join()
    except KeyboardInterrupt:
        print("\nShutting down workers...")
        stop_workers()

def stop_workers():
    """Stop all running workers gracefully"""
    global _worker_processes
    
    # First, signal all worker processes via their shutdown events
    for proc, shutdown_event, worker_id in _worker_processes:
        if proc.is_alive():
            shutdown_event.set()
    
    # Also check DB for any workers
    conn = _connect()
    workers = conn.execute("""
        SELECT id, pid FROM workers WHERE status = 'running'
    """).fetchall()
    conn.close()
    
    if not workers and not _worker_processes:
        print("No workers running")
        return
    
    # Wait a bit for graceful shutdown
    time.sleep(2)
    
    # Force terminate processes that are still alive
    for proc, _, worker_id in _worker_processes:
        if proc.is_alive():
            try:
                proc.terminate()
                proc.join(timeout=1)
                if proc.is_alive():
                    proc.kill()
            except:
                pass
    
    # Also try to kill by PID from DB
    for w in workers:
        try:
            # Check if process is still running
            os.kill(w['pid'], 0)  # This will raise if process doesn't exist
            # Process exists, try to terminate
            if os.name == 'nt':  # Windows
                os.kill(w['pid'], signal.SIGTERM)
            else:  # Unix
                os.kill(w['pid'], signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass  # Process already dead
        except Exception as e:
            print(f"Error stopping worker {w['id']}: {e}")
    
    # Wait a bit more
    time.sleep(1)
    
    # Force kill if still running
    for w in workers:
        try:
            os.kill(w['pid'], 0)  # Check if alive
            if os.name == 'nt':  # Windows
                os.kill(w['pid'], signal.SIGTERM)
            else:
                os.kill(w['pid'], signal.SIGKILL)
        except:
            pass
    
    # Mark as stopped
    conn = _connect()
    try:
        with conn:
            conn.execute("""
                UPDATE workers
                SET status = 'stopped',
                    stopped_at = ?
                WHERE status = 'running'
            """, (now_iso(),))
    finally:
        conn.close()
    
    _worker_processes.clear()
    print(f"Stopped workers")

# ---------------- DLQ Operations ---------------- 
def dlq_list():
    """List all jobs in the Dead Letter Queue"""
    conn = _connect()
    jobs = conn.execute("""
        SELECT id, command, attempts, max_retries, last_error, created_at, updated_at
        FROM jobs
        WHERE state = 'dead'
        ORDER BY updated_at DESC
    """).fetchall()
    conn.close()
    
    if not jobs:
        print("(no jobs in DLQ)")
        return
    
    print(f"Dead Letter Queue ({len(jobs)} jobs):")
    for j in jobs:
        print(f"\n  ID: {j['id']}")
        print(f"  Command: {j['command']}")
        print(f"  Attempts: {j['attempts']}/{j['max_retries']}")
        print(f"  Last Error: {j['last_error']}")
        print(f"  Created: {j['created_at']}")
        print(f"  Failed: {j['updated_at']}")

def dlq_retry(job_id: str):
    """Retry a job from the DLQ by resetting it to pending"""
    conn = _connect()
    try:
        with conn:
            result = conn.execute("""
                UPDATE jobs
                SET state = 'pending',
                    attempts = 0,
                    due_at = ?,
                    updated_at = ?,
                    last_error = NULL,
                    picked_by = NULL
                WHERE id = ? AND state = 'dead'
                RETURNING id
            """, (now_iso(), now_iso(), job_id)).fetchone()
            
            if not result:
                sys.exit(f"Job '{job_id}' not found in DLQ")
    finally:
        conn.close()
    
    print(f"Reset job '{job_id}' to pending (will retry from beginning)")

# ---------------- CLI ----------------
def build_parser():
    p = argparse.ArgumentParser(prog="queuectl", description="Job Queue CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("enqueue", help="Add a job to the queue")
    sp.add_argument("job_json", help="Job JSON: {id?, command, max_retries?, run_at?, priority?}")
    sp.set_defaults(func=lambda a: enqueue_job(a.job_json))

    sp = sub.add_parser("list", help="List jobs (optionally by state)")
    sp.add_argument("--state", choices=["pending","processing","completed","failed","dead"])
    sp.set_defaults(func=lambda a: list_jobs(a.state))

    sp = sub.add_parser("status", help="Show job/worker status")
    sp.set_defaults(func=lambda a: status_summary())

    csp = sub.add_parser("config", help="Get/Set configuration")
    csub = csp.add_subparsers(dest="ccmd", required=True)
    g = csub.add_parser("get", help="Show config values")
    g.set_defaults(func=lambda a: [print(f"{k} = {v}") for k,v in get_config().items()])
    s = csub.add_parser("set", help="Set a config value")
    s.add_argument("key", choices=list(DEFAULTS.keys()))
    s.add_argument("value")
    s.set_defaults(func=lambda a: (set_config(a.key, a.value), print(f"Set {a.key} = {a.value}")))

    wsp = sub.add_parser("worker", help="Worker process commands")
    wsub = wsp.add_subparsers(dest="wcmd", required=True)
    ws = wsub.add_parser("start", help="Start workers")
    ws.add_argument("--count", type=int, default=1, help="Number of workers to start (default: 1)")
    ws.set_defaults(func=lambda a: start_workers(a.count))
    wst = wsub.add_parser("stop", help="Stop all running workers gracefully")
    wst.set_defaults(func=lambda a: stop_workers())

    dlqsp = sub.add_parser("dlq", help="Dead Letter Queue operations")
    dlqsub = dlqsp.add_subparsers(dest="dlqcmd", required=True)
    dlql = dlqsub.add_parser("list", help="List all jobs in DLQ")
    dlql.set_defaults(func=lambda a: dlq_list())
    dlqr = dlqsub.add_parser("retry", help="Retry a job from DLQ")
    dlqr.add_argument("job_id", help="Job ID to retry")
    dlqr.set_defaults(func=lambda a: dlq_retry(a.job_id))

    return p

def main(argv=None):
    init_db()
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    # Set multiprocessing start method for Windows compatibility
    if os.name == 'nt':
        multiprocessing.set_start_method('spawn', force=True)
    main()
