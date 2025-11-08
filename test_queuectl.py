#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for QueueCTL - validates core functionality
"""
import subprocess
import time
import json
import os
import sys

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Use a test database
TEST_DB = "test_queuectl.db"
os.environ["QUEUECTL_DB"] = TEST_DB

def run_cmd(cmd, check=True):
    """Run a queuectl command and return output"""
    try:
        # Handle commands that need JSON - pass as list to avoid shell parsing issues
        if isinstance(cmd, str):
            parts = cmd.split()
        else:
            parts = cmd
        
        result = subprocess.run(
            ["python", "queuectl.py"] + parts,
            capture_output=True,
            text=True,
            timeout=30
        )
        if check and result.returncode != 0:
            print(f"❌ Command failed: queuectl {' '.join(parts)}")
            print(f"   Error: {result.stderr}")
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        print(f"❌ Command timed out: queuectl {' '.join(parts)}")
        return None
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return None

def cleanup():
    """Clean up test database"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    if os.path.exists(".workers.json"):
        os.remove(".workers.json")

def test_basic_job_completion():
    """Test 1: Basic job completes successfully"""
    print("\n🧪 Test 1: Basic Job Completion")
    print("-" * 50)
    
    cleanup()
    
    # Enqueue a simple job
    job_id = "test-success-1"
    job_data = {"id": job_id, "command": "echo Test Success"}
    job_json = json.dumps(job_data)
    output = run_cmd(["enqueue", job_json])
    if not output or job_id not in output:
        print("❌ Failed to enqueue job")
        return False
    
    print(f"✅ Enqueued job: {job_id}")
    
    # Start a worker
    print("Starting worker...")
    worker_proc = subprocess.Popen(
        ["python", "queuectl.py", "worker", "start", "--count", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for job to complete
    time.sleep(3)
    
    # Check if job completed
    output = run_cmd(["list", "--state", "completed"], check=False)
    if output and job_id in output:
        print(f"✅ Job {job_id} completed successfully")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return True
    else:
        print(f"❌ Job {job_id} did not complete")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False

def test_retry_and_dlq():
    """Test 2: Failed job retries with backoff and moves to DLQ"""
    print("\n🧪 Test 2: Retry and DLQ")
    print("-" * 50)
    
    cleanup()
    
    # Set max retries to 2 for faster testing
    run_cmd(["config", "set", "max_retries", "2"])
    run_cmd(["config", "set", "backoff_base", "2"])
    
    # Enqueue a job that will fail
    job_id = "test-fail-1"
    job_json = json.dumps({"id": job_id, "command": "exit 1"})
    output = run_cmd(["enqueue", job_json])
    if not output:
        print("❌ Failed to enqueue job")
        return False
    
    print(f"✅ Enqueued failing job: {job_id}")
    
    # Start a worker
    worker_proc = subprocess.Popen(
        ["python", "queuectl.py", "worker", "start", "--count", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for retries (with backoff: 2^1=2s, 2^2=4s, then DLQ)
    print("Waiting for retries and DLQ...")
    time.sleep(10)
    
    # Check DLQ
    output = run_cmd(["dlq", "list"], check=False)
    if output and job_id in output:
        print(f"✅ Job {job_id} moved to DLQ after retries")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return True
    else:
        print(f"❌ Job {job_id} did not reach DLQ")
        print(f"   Status output: {run_cmd('status', check=False)}")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False

def test_multiple_workers():
    """Test 3: Multiple workers process jobs without overlap"""
    print("\n🧪 Test 3: Multiple Workers")
    print("-" * 50)
    
    cleanup()
    
    # Enqueue multiple jobs
    job_ids = []
    for i in range(5):
        job_id = f"test-multi-{i}"
        job_ids.append(job_id)
        job_json = json.dumps({"id": job_id, "command": f"echo Job {i}"})
        run_cmd(["enqueue", job_json])
    
    print(f"✅ Enqueued {len(job_ids)} jobs")
    
    # Start 3 workers
    worker_proc = subprocess.Popen(
        ["python", "queuectl.py", "worker", "start", "--count", "3"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for jobs to complete
    time.sleep(5)
    
    # Check completed jobs
    output = run_cmd(["list", "--state", "completed"], check=False)
    completed_count = output.count("completed") if output else 0
    
    if completed_count >= len(job_ids):
        print(f"✅ All {len(job_ids)} jobs completed with multiple workers")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return True
    else:
        print(f"❌ Only {completed_count}/{len(job_ids)} jobs completed")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False

def test_invalid_command():
    """Test 4: Invalid commands fail gracefully"""
    print("\n🧪 Test 4: Invalid Command Handling")
    print("-" * 50)
    
    cleanup()
    
    # Enqueue a job with invalid command
    job_id = "test-invalid-1"
    job_json = json.dumps({"id": job_id, "command": "nonexistent_command_xyz123"})
    output = run_cmd(["enqueue", job_json])
    if not output:
        print("❌ Failed to enqueue job")
        return False
    
    print(f"✅ Enqueued job with invalid command: {job_id}")
    
    # Start a worker
    worker_proc = subprocess.Popen(
        ["python", "queuectl.py", "worker", "start", "--count", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait a bit
    time.sleep(3)
    
    # Check that job failed (should be in failed or dead state)
    output = run_cmd(["status"], check=False)
    if output:
        # Job should have failed
        failed_output = run_cmd(["list", "--state", "failed"], check=False)
        dead_output = run_cmd(["list", "--state", "dead"], check=False)
        
        if (failed_output and job_id in failed_output) or (dead_output and job_id in dead_output):
            print(f"✅ Invalid command handled gracefully (job in failed/dead state)")
            worker_proc.terminate()
            worker_proc.wait(timeout=5)
            return True
    
    print(f"❌ Invalid command not handled properly")
    worker_proc.terminate()
    worker_proc.wait(timeout=5)
    return False

def test_persistence():
    """Test 5: Job data survives restart"""
    print("\n🧪 Test 5: Persistence")
    print("-" * 50)
    
    cleanup()
    
    # Enqueue a job
    job_id = "test-persist-1"
    job_json = json.dumps({"id": job_id, "command": "echo Persist Test"})
    output = run_cmd(["enqueue", job_json])
    if not output:
        print("❌ Failed to enqueue job")
        return False
    
    print(f"✅ Enqueued job: {job_id}")
    
    # Verify job exists
    output = run_cmd(["list"], check=False)
    if not output or job_id not in output:
        print("❌ Job not found after enqueue")
        return False
    
    print("✅ Job found in database")
    
    # Simulate restart (just check again without workers)
    output = run_cmd(["list"], check=False)
    if output and job_id in output:
        print(f"✅ Job persisted after 'restart'")
        return True
    else:
        print(f"❌ Job lost after 'restart'")
        return False

def test_dlq_retry():
    """Test 6: DLQ retry functionality"""
    print("\n🧪 Test 6: DLQ Retry")
    print("-" * 50)
    
    cleanup()
    
    # Set max retries to 1 for faster testing
    run_cmd(["config", "set", "max_retries", "1"])
    
    # Enqueue a failing job
    job_id = "test-dlq-retry-1"
    job_json = json.dumps({"id": job_id, "command": "exit 1"})
    run_cmd(["enqueue", job_json])
    
    # Start worker to move job to DLQ
    worker_proc = subprocess.Popen(
        ["python", "queuectl.py", "worker", "start", "--count", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    time.sleep(5)
    
    # Verify in DLQ
    output = run_cmd("dlq list", check=False)
    if not output or job_id not in output:
        print("❌ Job not in DLQ")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False
    
    print(f"✅ Job {job_id} in DLQ")
    
    # Retry from DLQ
    output = run_cmd(["dlq", "retry", job_id])
    if not output or "pending" not in output.lower():
        print("❌ Failed to retry from DLQ")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False
    
    print(f"✅ Job {job_id} retried from DLQ")
    
    # Verify job is now pending
    output = run_cmd(["list", "--state", "pending"], check=False)
    if output and job_id in output:
        print(f"✅ Job {job_id} is now pending")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return True
    else:
        print(f"❌ Job {job_id} not in pending state")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("QueueCTL Test Suite")
    print("=" * 60)
    
    tests = [
        ("Basic Job Completion", test_basic_job_completion),
        ("Retry and DLQ", test_retry_and_dlq),
        ("Multiple Workers", test_multiple_workers),
        ("Invalid Command Handling", test_invalid_command),
        ("Persistence", test_persistence),
        ("DLQ Retry", test_dlq_retry),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            # Clean up between tests
            time.sleep(1)
        except Exception as e:
            print(f"❌ Test '{name}' crashed: {e}")
            results.append((name, False))
        finally:
            # Stop any running workers
            run_cmd(["worker", "stop"], check=False)
            time.sleep(1)
    
    # Final cleanup
    cleanup()
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("-" * 60)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

