#!/bin/bash
# QueueCTL - Complete Terminal Demo Script
# This script runs all QueueCTL commands sequentially

echo "=========================================="
echo "QueueCTL - Complete Terminal Demo"
echo "=========================================="
echo ""

# Use Python from virtual environment
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
$PYTHON queuectl.py enqueue '{"id":"bash-demo-1","command":"echo Hello from Bash Script"}'
$PYTHON queuectl.py enqueue '{"id":"bash-demo-2","command":"python -c \"print(42)\""}'
$PYTHON queuectl.py enqueue '{"id":"bash-demo-3","command":"echo Job with priority","priority":5}'
$PYTHON queuectl.py enqueue '{"id":"bash-demo-4","command":"echo Another bash test job"}'
$PYTHON queuectl.py enqueue '{"id":"bash-demo-5","command":"echo Final bash demo job"}'
echo ""

echo "3. Listing pending jobs..."
$PYTHON queuectl.py list --state pending
echo ""

echo "4. Checking configuration..."
$PYTHON queuectl.py config get
echo ""

echo "5. Status before starting workers..."
$PYTHON queuectl.py status
echo ""

echo "6. Starting 3 workers..."
$PYTHON queuectl.py worker start --count 3 &
WORKER_PID=$!
echo "Workers started (background process)"
echo ""

echo "7. Waiting 5 seconds for jobs to process..."
sleep 5
echo ""

echo "8. Status after processing..."
$PYTHON queuectl.py status
echo ""

echo "9. Listing completed jobs (bash-demo jobs)..."
$PYTHON queuectl.py list --state completed | grep -E "bash-demo" || echo "No bash-demo jobs found"
echo ""

echo "10. Checking Dead Letter Queue..."
$PYTHON queuectl.py dlq list
echo ""

echo "11. Testing configuration update..."
$PYTHON queuectl.py config set poll_interval 0.5
$PYTHON queuectl.py config get
echo ""

echo "12. Enqueuing final test job..."
$PYTHON queuectl.py enqueue '{"id":"bash-final","command":"echo Final bash demonstration"}'
echo ""

echo "13. Waiting 3 seconds for final job..."
sleep 3
echo ""

echo "14. Status after final job..."
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

echo "16. Sample of all jobs (first 10)..."
$PYTHON queuectl.py list | head -10
echo ""

echo "17. Final status summary..."
$PYTHON queuectl.py status
echo ""

echo "18. Stopping workers..."
$PYTHON queuectl.py worker stop
echo ""

echo "19. Final status after stopping workers..."
$PYTHON queuectl.py status
echo ""

echo "=========================================="
echo "All Commands Completed Successfully!"
echo "=========================================="

