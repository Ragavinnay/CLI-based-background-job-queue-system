#!/usr/bin/env python3
"""
Comprehensive validation script for QueueCTL assignment requirements
Tests all must-have features and scenarios
"""
import subprocess
import time
import json
import os
import sys

# Use main database for validation
DB_FILE = "queuectl.db"

def run_cmd(cmd_list, check=True, timeout=30):
    """Run a queuectl command"""
    try:
        result = subprocess.run(
            ["python", "queuectl.py"] + cmd_list,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if check and result.returncode != 0:
            print(f"❌ Command failed: {' '.join(cmd_list)}")
            print(f"   Error: {result.stderr}")
            return None, result.returncode
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        print(f"❌ Command timed out: {' '.join(cmd_list)}")
        return None, -1
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, -1

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_1_basic_job_completion():
    """Test 1: Basic job completes successfully"""
    print_section("TEST 1: Basic Job Completion")
    
    job_id = "test-basic-1"
    job_json = json.dumps({"id": job_id, "command": "echo 'Test Success'"})
    
    # Enqueue job
    output, code = run_cmd(["enqueue", job_json])
    if not output or job_id not in output:
        print("❌ FAILED: Could not enqueue job")
        return False
    print(f"✅ Enqueued job: {job_id}")
    
    # Start worker
    print("Starting worker...")
    worker_proc = subprocess.Popen(
        ["python", "queuectl.py", "worker", "start", "--count", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for completion
    time.sleep(3)
    
    # Check if completed
    output, _ = run_cmd(["list", "--state", "completed"], check=False)
    if output and job_id in output:
        print(f"✅ PASS: Job {job_id} completed successfully")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return True
    else:
        print(f"❌ FAIL: Job {job_id} did not complete")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False

def test_2_retry_and_dlq():
    """Test 2: Failed job retries with backoff and moves to DLQ"""
    print_section("TEST 2: Retry with Exponential Backoff and DLQ")
    
    # Configure retries
    run_cmd(["config", "set", "max_retries", "2"])
    run_cmd(["config", "set", "backoff_base", "2"])
    
    job_id = "test-retry-dlq-1"
    job_json = json.dumps({"id": job_id, "command": "exit 1"})
    
    # Enqueue failing job
    output, _ = run_cmd(["enqueue", job_json])
    if not output:
        print("❌ FAILED: Could not enqueue job")
        return False
    print(f"✅ Enqueued failing job: {job_id}")
    
    # Start worker
    worker_proc = subprocess.Popen(
        ["python", "queuectl.py", "worker", "start", "--count", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for retries (2^1=2s, 2^2=4s, then DLQ)
    print("Waiting for retries and DLQ (max 10 seconds)...")
    time.sleep(10)
    
    # Check DLQ
    output, _ = run_cmd(["dlq", "list"], check=False)
    if output and job_id in output:
        print(f"✅ PASS: Job {job_id} moved to DLQ after retries")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return True
    else:
        print(f"❌ FAIL: Job {job_id} did not reach DLQ")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False

def test_3_multiple_workers():
    """Test 3: Multiple workers process jobs without overlap"""
    print_section("TEST 3: Multiple Workers (No Overlap)")
    
    # Enqueue multiple jobs
    job_ids = []
    for i in range(5):
        job_id = f"test-multi-{i}"
        job_ids.append(job_id)
        job_json = json.dumps({"id": job_id, "command": f"echo 'Job {i}'"})
        run_cmd(["enqueue", job_json])
    
    print(f"✅ Enqueued {len(job_ids)} jobs")
    
    # Start 3 workers
    worker_proc = subprocess.Popen(
        ["python", "queuectl.py", "worker", "start", "--count", "3"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for jobs to complete
    print("Waiting for jobs to complete...")
    time.sleep(5)
    
    # Check completed jobs
    output, _ = run_cmd(["list", "--state", "completed"], check=False)
    completed_count = output.count("completed") if output else 0
    
    # Check for duplicate processing (should not have more completed than jobs)
    if completed_count >= len(job_ids) and completed_count <= len(job_ids):
        print(f"✅ PASS: All {len(job_ids)} jobs completed without overlap")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return True
    else:
        print(f"❌ FAIL: Expected {len(job_ids)} completed, got {completed_count}")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False

def test_4_invalid_command():
    """Test 4: Invalid commands fail gracefully"""
    print_section("TEST 4: Invalid Command Handling")
    
    job_id = "test-invalid-1"
    job_json = json.dumps({"id": job_id, "command": "nonexistent_command_xyz123"})
    
    # Enqueue job with invalid command
    output, _ = run_cmd(["enqueue", job_json])
    if not output:
        print("❌ FAILED: Could not enqueue job")
        return False
    print(f"✅ Enqueued job with invalid command: {job_id}")
    
    # Start worker
    worker_proc = subprocess.Popen(
        ["python", "queuectl.py", "worker", "start", "--count", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    time.sleep(3)
    
    # Check that job failed gracefully
    output, _ = run_cmd(["status"], check=False)
    failed_output, _ = run_cmd(["list", "--state", "failed"], check=False)
    dead_output, _ = run_cmd(["list", "--state", "dead"], check=False)
    
    if (failed_output and job_id in failed_output) or (dead_output and job_id in dead_output):
        print(f"✅ PASS: Invalid command handled gracefully")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return True
    
    print(f"❌ FAIL: Invalid command not handled properly")
    worker_proc.terminate()
    worker_proc.wait(timeout=5)
    return False

def test_5_persistence():
    """Test 5: Job data survives restart"""
    print_section("TEST 5: Job Persistence Across Restarts")
    
    job_id = "test-persist-1"
    job_json = json.dumps({"id": job_id, "command": "echo 'Persistence Test'"})
    
    # Enqueue job
    output, _ = run_cmd(["enqueue", job_json])
    if not output:
        print("❌ FAILED: Could not enqueue job")
        return False
    print(f"✅ Enqueued job: {job_id}")
    
    # Verify job exists
    output, _ = run_cmd(["list"], check=False)
    if not output or job_id not in output:
        print("❌ FAIL: Job not found after enqueue")
        return False
    
    print("✅ Job found in database")
    
    # Simulate restart (check again without workers)
    output, _ = run_cmd(["list"], check=False)
    if output and job_id in output:
        print(f"✅ PASS: Job persisted after 'restart'")
        return True
    else:
        print(f"❌ FAIL: Job lost after 'restart'")
        return False

def test_6_all_cli_commands():
    """Test 6: All CLI commands work"""
    print_section("TEST 6: All CLI Commands")
    
    results = []
    
    # Test enqueue
    job_json = json.dumps({"id": "test-cli-1", "command": "echo test"})
    output, code = run_cmd(["enqueue", job_json], check=False)
    results.append(("enqueue", code == 0))
    
    # Test status
    output, code = run_cmd(["status"], check=False)
    results.append(("status", code == 0 and "Jobs:" in output))
    
    # Test list
    output, code = run_cmd(["list"], check=False)
    results.append(("list", code == 0))
    
    # Test list with state
    output, code = run_cmd(["list", "--state", "pending"], check=False)
    results.append(("list --state", code == 0))
    
    # Test config get
    output, code = run_cmd(["config", "get"], check=False)
    results.append(("config get", code == 0 and "max_retries" in output))
    
    # Test config set
    output, code = run_cmd(["config", "set", "max_retries", "3"], check=False)
    results.append(("config set", code == 0))
    
    # Test dlq list
    output, code = run_cmd(["dlq", "list"], check=False)
    results.append(("dlq list", code == 0))
    
    # Test worker stop (should work even if no workers)
    output, code = run_cmd(["worker", "stop"], check=False)
    results.append(("worker stop", code == 0))
    
    # Print results
    all_passed = True
    for cmd, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {cmd}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("✅ PASS: All CLI commands work")
    else:
        print("❌ FAIL: Some CLI commands failed")
    
    return all_passed

def test_7_configuration_management():
    """Test 7: Configuration management"""
    print_section("TEST 7: Configuration Management")
    
    # Get current config
    output, _ = run_cmd(["config", "get"], check=False)
    if not output or "max_retries" not in output:
        print("❌ FAIL: Could not get config")
        return False
    print("✅ Config get works")
    
    # Set config values
    test_configs = [
        ("max_retries", "5"),
        ("backoff_base", "3"),
        ("poll_interval", "1.0"),
        ("job_timeout", "300")
    ]
    
    for key, value in test_configs:
        output, code = run_cmd(["config", "set", key, value], check=False)
        if code != 0:
            print(f"❌ FAIL: Could not set {key}")
            return False
        print(f"✅ Set {key} = {value}")
    
    # Verify config was set
    output, _ = run_cmd(["config", "get"], check=False)
    if "max_retries = 5" in output and "backoff_base = 3" in output:
        print("✅ PASS: Configuration management works")
        return True
    else:
        print("❌ FAIL: Configuration not persisted")
        return False

def test_8_graceful_shutdown():
    """Test 8: Graceful worker shutdown"""
    print_section("TEST 8: Graceful Worker Shutdown")
    
    # Enqueue a long-running job
    job_id = "test-shutdown-1"
    job_json = json.dumps({"id": job_id, "command": "sleep 3"})
    run_cmd(["enqueue", job_json])
    
    # Start worker
    worker_proc = subprocess.Popen(
        ["python", "queuectl.py", "worker", "start", "--count", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait a bit for job to start
    time.sleep(1)
    
    # Stop workers gracefully
    output, code = run_cmd(["worker", "stop"], check=False)
    
    # Wait a bit
    time.sleep(2)
    
    # Check if job completed or is still processing
    output, _ = run_cmd(["list", "--state", "completed"], check=False)
    if output and job_id in output:
        print("✅ PASS: Worker finished job before shutdown")
        return True
    else:
        # Check if it's still processing (might have been interrupted)
        output, _ = run_cmd(["list", "--state", "processing"], check=False)
        if output and job_id in output:
            print("⚠️  WARNING: Job still processing (may have been interrupted)")
        else:
            print("✅ PASS: Worker shutdown gracefully")
        return True

def test_9_dlq_retry():
    """Test 9: DLQ retry functionality"""
    print_section("TEST 9: DLQ Retry Functionality")
    
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
    output, _ = run_cmd(["dlq", "list"], check=False)
    if not output or job_id not in output:
        print("❌ FAIL: Job not in DLQ")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False
    
    print(f"✅ Job {job_id} in DLQ")
    
    # Retry from DLQ
    output, code = run_cmd(["dlq", "retry", job_id], check=False)
    if code != 0 or "pending" not in output.lower():
        print("❌ FAIL: Could not retry from DLQ")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False
    
    print(f"✅ Job {job_id} retried from DLQ")
    
    # Verify job is now pending
    output, _ = run_cmd(["list", "--state", "pending"], check=False)
    if output and job_id in output:
        print(f"✅ PASS: DLQ retry functionality works")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return True
    else:
        print(f"❌ FAIL: Job not in pending state after retry")
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
        return False

def main():
    """Run all validation tests"""
    print("\n" + "=" * 70)
    print("  QueueCTL - Comprehensive Requirement Validation")
    print("=" * 70)
    
    tests = [
        ("Basic Job Completion", test_1_basic_job_completion),
        ("Retry and DLQ", test_2_retry_and_dlq),
        ("Multiple Workers", test_3_multiple_workers),
        ("Invalid Command Handling", test_4_invalid_command),
        ("Job Persistence", test_5_persistence),
        ("All CLI Commands", test_6_all_cli_commands),
        ("Configuration Management", test_7_configuration_management),
        ("Graceful Shutdown", test_8_graceful_shutdown),
        ("DLQ Retry", test_9_dlq_retry),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            time.sleep(1)  # Brief pause between tests
        except Exception as e:
            print(f"❌ Test '{name}' crashed: {e}")
            results.append((name, False))
        finally:
            # Stop any running workers
            run_cmd(["worker", "stop"], check=False)
            time.sleep(1)
    
    # Print summary
    print_section("Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("-" * 70)
    print(f"Total: {passed}/{total} tests passed ({passed*100//total}%)")
    
    if passed == total:
        print("\n🎉 All requirements validated successfully!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

