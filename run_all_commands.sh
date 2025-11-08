#!/bin/bash
# QueueCTL - Complete Sequential Command Runner
# This script runs all QueueCTL commands sequentially

echo "=========================================="
echo "QueueCTL - Sequential Command Runner"
echo "=========================================="
echo ""

# Activate virtual environment if on Windows
if [ -f ".venv/Scripts/python.exe" ]; then
    PYTHON=".venv/Scripts/python.exe"
elif [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python"
fi

echo "1. Checking initial status..."
$PYTHON queuectl.py status
echo ""

echo "2. Enqueuing test jobs..."
$PYTHON queuectl.py enqueue '{"id":"script-test-1","command":"echo Test Job 1"}'
$PYTHON queuectl.py enqueue '{"id":"script-test-2","command":"python -c \"print(42)\""}'
$PYTHON queuectl.py enqueue '{"id":"script-test-3","command":"echo Test Job 3","priority":5}'
$PYTHON queuectl.py enqueue '{"id":"script-test-4","command":"echo Test Job 4"}'
$PYTHON queuectl.py enqueue '{"id":"script-test-5","command":"echo Test Job 5"}'
echo ""

echo "3. Listing pending jobs..."
$PYTHON queuectl.py list --state pending
echo ""

echo "4. Checking configuration..."
$PYTHON queuectl.py config get
echo ""

echo "5. Checking status before starting workers..."
$PYTHON queuectl.py status
echo ""

echo "6. Starting 3 workers..."
$PYTHON queuectl.py worker start --count 3 &
WORKER_PID=$!
echo "Workers started (PID: $WORKER_PID)"
echo ""

echo "7. Waiting 5 seconds for jobs to process..."
sleep 5
echo ""

echo "8. Checking status after processing..."
$PYTHON queuectl.py status
echo ""

echo "9. Listing completed jobs..."
$PYTHON queuectl.py list --state completed | grep -E "script-test" || echo "No script-test jobs found"
echo ""

echo "10. Checking Dead Letter Queue..."
$PYTHON queuectl.py dlq list
echo ""

echo "11. Testing configuration update..."
$PYTHON queuectl.py config set poll_interval 0.5
$PYTHON queuectl.py config get
echo ""

echo "12. Enqueuing final test job..."
$PYTHON queuectl.py enqueue '{"id":"script-final","command":"echo Final script test"}'
echo ""

echo "13. Waiting 3 seconds for final job..."
sleep 3
echo ""

echo "14. Final status check..."
$PYTHON queuectl.py status
echo ""

echo "15. Listing all job states..."
echo "Pending:"
$PYTHON queuectl.py list --state pending
echo ""
echo "Failed:"
$PYTHON queuectl.py list --state failed
echo ""
echo "Dead:"
$PYTHON queuectl.py list --state dead
echo ""

echo "16. Stopping workers..."
$PYTHON queuectl.py worker stop
echo ""

echo "17. Final status..."
$PYTHON queuectl.py status
echo ""

echo "=========================================="
echo "All commands completed!"
echo "=========================================="

