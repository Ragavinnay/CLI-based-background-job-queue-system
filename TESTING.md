# Testing Guide for QueueCTL

This guide covers both automated and manual testing approaches for QueueCTL.

## 🚀 Quick Start - Automated Testing

Run the comprehensive test suite:

```bash
python test_queuectl.py
```

This will run 6 automated tests covering all core functionality.

## 📋 Automated Test Suite

The test script (`test_queuectl.py`) validates:

1. **Basic Job Completion** - Simple jobs execute successfully
2. **Retry and DLQ** - Failed jobs retry and move to DLQ
3. **Multiple Workers** - Parallel processing without conflicts
4. **Invalid Command Handling** - Graceful failure handling
5. **Persistence** - Jobs survive restarts
6. **DLQ Retry** - Jobs can be retried from DLQ

### Running Individual Tests

You can modify `test_queuectl.py` to run specific tests by commenting out others in the `main()` function.

## 🧪 Manual Testing Examples

### Test 1: Basic Job Execution

```bash
# 1. Enqueue a simple job
python queuectl.py enqueue '{"id":"test1","command":"echo Hello World"}'

# 2. Check status
python queuectl.py status

# 3. Start a worker
python queuectl.py worker start --count 1

# 4. Wait a few seconds, then check completed jobs
python queuectl.py list --state completed

# 5. Stop the worker
python queuectl.py worker stop
```

**Expected Result:** Job should appear in `completed` state.

---

### Test 2: Retry Mechanism with Exponential Backoff

```bash
# 1. Configure retries
python queuectl.py config set max_retries 3
python queuectl.py config set backoff_base 2

# 2. Enqueue a failing job
python queuectl.py enqueue '{"id":"fail-test","command":"exit 1"}'

# 3. Start worker
python queuectl.py worker start --count 1

# 4. Monitor the job (run in another terminal)
watch -n 1 'python queuectl.py status'

# 5. Watch the job progress:
#    - First attempt: fails immediately
#    - 2nd attempt: after 2 seconds (2^1)
#    - 3rd attempt: after 4 seconds (2^2)
#    - 4th attempt: after 8 seconds (2^3)
#    - Then moves to DLQ

# 6. Check DLQ
python queuectl.py dlq list

# 7. Stop worker
python queuectl.py worker stop
```

**Expected Result:** Job should retry 3 times with increasing delays, then move to DLQ.

---

### Test 3: Multiple Workers Processing Jobs

```bash
# 1. Enqueue multiple jobs
for i in {1..10}; do
  python queuectl.py enqueue "{\"id\":\"job$i\",\"command\":\"echo Job $i\"}"
done

# 2. Check pending jobs
python queuectl.py list --state pending

# 3. Start 3 workers
python queuectl.py worker start --count 3

# 4. Monitor status (in another terminal)
watch -n 1 'python queuectl.py status'

# 5. Watch jobs get processed in parallel
# You should see jobs moving from pending -> processing -> completed

# 6. Check completed jobs
python queuectl.py list --state completed

# 7. Stop workers
python queuectl.py worker stop
```

**Expected Result:** All 10 jobs should complete, processed by 3 workers in parallel.

---

### Test 4: Job Persistence Across Restarts

```bash
# 1. Enqueue some jobs
python queuectl.py enqueue '{"id":"persist1","command":"echo test1"}'
python queuectl.py enqueue '{"id":"persist2","command":"echo test2"}'

# 2. Verify they're in the database
python queuectl.py list

# 3. Stop any running workers
python queuectl.py worker stop

# 4. Simulate restart - just check again
python queuectl.py status

# 5. Jobs should still be there
python queuectl.py list --state pending

# 6. Start workers again
python queuectl.py worker start

# 7. Jobs should be processed
sleep 3
python queuectl.py list --state completed
```

**Expected Result:** Jobs should persist in the database and be processed after restart.

---

### Test 5: Dead Letter Queue Operations

```bash
# 1. Set low retry count for faster testing
python queuectl.py config set max_retries 1

# 2. Enqueue a failing job
python queuectl.py enqueue '{"id":"dlq-test","command":"exit 1"}'

# 3. Start worker
python queuectl.py worker start --count 1

# 4. Wait for job to fail and move to DLQ
sleep 5

# 5. Check DLQ
python queuectl.py dlq list

# 6. Retry the job from DLQ
python queuectl.py dlq retry dlq-test

# 7. Verify it's back to pending
python queuectl.py list --state pending

# 8. Process it again (or let it fail again)
python queuectl.py worker start --count 1
sleep 3
python queuectl.py status

# 9. Stop worker
python queuectl.py worker stop
```

**Expected Result:** Job should move to DLQ, then be retried and reset to pending.

---

### Test 6: Configuration Management

```bash
# 1. View current config
python queuectl.py config get

# 2. Update configuration
python queuectl.py config set max_retries 5
python queuectl.py config set backoff_base 3
python queuectl.py config set poll_interval 1.0

# 3. Verify changes
python queuectl.py config get

# 4. Test with new settings
python queuectl.py enqueue '{"id":"config-test","command":"exit 1"}'
python queuectl.py worker start --count 1

# 5. Watch retries with new backoff (3^1=3s, 3^2=9s, etc.)
sleep 15
python queuectl.py status
python queuectl.py worker stop
```

**Expected Result:** Configuration should persist and affect job behavior.

---

### Test 7: Job Priority

```bash
# 1. Enqueue jobs with different priorities
python queuectl.py enqueue '{"id":"low","command":"echo low","priority":1}'
python queuectl.py enqueue '{"id":"high","command":"echo high","priority":10}'
python queuectl.py enqueue '{"id":"medium","command":"echo medium","priority":5}'

# 2. Start worker
python queuectl.py worker start --count 1

# 3. Check processing order
sleep 2
python queuectl.py list

# Expected: high priority (10) should be processed first
```

**Expected Result:** Higher priority jobs should be processed first.

---

### Test 8: Scheduled/Delayed Jobs

```bash
# 1. Calculate a future time (e.g., 30 seconds from now)
# On Unix/Mac:
FUTURE=$(date -u -v+30S +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "+30 seconds" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || python -c "from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat().replace('+00:00', 'Z'))")

# 2. Enqueue a scheduled job
python queuectl.py enqueue "{\"id\":\"scheduled\",\"command\":\"echo scheduled\",\"run_at\":\"$FUTURE\"}"

# 3. Check status - should be pending but not due yet
python queuectl.py status

# 4. Start worker
python queuectl.py worker start --count 1

# 5. Job should not be processed immediately
sleep 5
python queuectl.py list --state pending

# 6. After the scheduled time, job should be processed
sleep 30
python queuectl.py list --state completed
python queuectl.py worker stop
```

**Expected Result:** Job should wait until `run_at` time before being processed.

---

### Test 9: Invalid Commands

```bash
# 1. Enqueue job with non-existent command
python queuectl.py enqueue '{"id":"invalid","command":"nonexistent_command_xyz123"}'

# 2. Start worker
python queuectl.py worker start --count 1

# 3. Wait for processing
sleep 3

# 4. Check status - should be in failed or dead state
python queuectl.py status
python queuectl.py list --state failed
python queuectl.py list --state dead

# 5. Stop worker
python queuectl.py worker stop
```

**Expected Result:** Invalid commands should fail gracefully and be retried or moved to DLQ.

---

### Test 10: Concurrent Workers (No Duplicate Processing)

```bash
# 1. Enqueue a single job that takes time
python queuectl.py enqueue '{"id":"concurrent-test","command":"sleep 5"}'

# 2. Start multiple workers
python queuectl.py worker start --count 5

# 3. Monitor status
watch -n 1 'python queuectl.py status'

# 4. Check that only ONE worker picked up the job
# Should see: 1 processing, 0 pending (after pickup)

# 5. Wait for completion
sleep 6
python queuectl.py list --state completed

# 6. Stop workers
python queuectl.py worker stop
```

**Expected Result:** Only one worker should process the job, no duplicates.

---

## 🔍 Debugging Tips

### Check Database Directly

```bash
# View all jobs
sqlite3 queuectl.db "SELECT id, state, attempts, max_retries FROM jobs;"

# View workers
sqlite3 queuectl.db "SELECT id, pid, status, heartbeat_at FROM workers;"

# View config
sqlite3 queuectl.db "SELECT * FROM config;"
```

### Monitor Worker Processes

```bash
# On Unix/Linux/Mac
ps aux | grep queuectl

# On Windows
tasklist | findstr python
```

### Check for Stuck Jobs

If jobs are stuck in "processing" state:

```bash
# Reset stuck jobs (use with caution)
sqlite3 queuectl.db "UPDATE jobs SET state='pending', picked_by=NULL WHERE state='processing';"
```

### Verbose Testing

Add print statements or use Python debugger:

```bash
python -m pdb queuectl.py worker start --count 1
```

---

## ✅ Test Checklist

Before submission, verify:

- [ ] All automated tests pass
- [ ] Basic job completion works
- [ ] Retry mechanism works with exponential backoff
- [ ] Multiple workers process jobs without conflicts
- [ ] Invalid commands fail gracefully
- [ ] Jobs persist across restarts
- [ ] DLQ functionality works (list and retry)
- [ ] Configuration can be set and retrieved
- [ ] Worker start/stop works gracefully
- [ ] Status command shows accurate information

---

## 🐛 Common Issues

### Workers Not Processing

- Check if workers are actually running: `python queuectl.py status`
- Verify jobs are in `pending` state: `python queuectl.py list --state pending`
- Check database is accessible
- Ensure no database locks

### Jobs Stuck in Processing

- Worker may have crashed
- Manually reset: `sqlite3 queuectl.db "UPDATE jobs SET state='pending', picked_by=NULL WHERE state='processing';"`

### Database Locked

- Stop all workers: `python queuectl.py worker stop`
- Check for zombie processes
- Restart workers

### Tests Failing

- Ensure test database is clean: delete `test_queuectl.db`
- Check Python version (3.8+ required)
- Verify all dependencies are available (none required, but check)

---

## 📊 Performance Testing

For stress testing:

```bash
# Enqueue many jobs
for i in {1..100}; do
  python queuectl.py enqueue "{\"id\":\"stress$i\",\"command\":\"echo $i\"}"
done

# Start multiple workers
python queuectl.py worker start --count 10

# Monitor
watch -n 1 'python queuectl.py status'
```

---

## 🎯 Integration Testing

Test the full workflow:

```bash
# 1. Setup
python queuectl.py config set max_retries 3

# 2. Enqueue mix of jobs
python queuectl.py enqueue '{"id":"success1","command":"echo success"}'
python queuectl.py enqueue '{"id":"fail1","command":"exit 1","max_retries":2}'
python queuectl.py enqueue '{"id":"success2","command":"python -c \"print(42)\""}'

# 3. Start workers
python queuectl.py worker start --count 2

# 4. Monitor
sleep 10
python queuectl.py status

# 5. Check results
python queuectl.py list --state completed
python queuectl.py list --state failed
python queuectl.py dlq list

# 6. Cleanup
python queuectl.py worker stop
```

---

Happy Testing! 🚀


