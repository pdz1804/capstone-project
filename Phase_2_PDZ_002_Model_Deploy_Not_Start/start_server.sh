#!/bin/bash
# ============================================================================
# Start the ColQwen inference server
# Run inside the EC2 instance
# ============================================================================
set -e

DEPLOY_DIR="$HOME/colqwen-server"
LOG_FILE="$DEPLOY_DIR/server.log"

# Activate virtual environment
source "$DEPLOY_DIR/venv/bin/activate"

echo "Starting ColQwen inference server..."
echo "  Model: vidore/colqwen2-v1.0"
echo "  Quantization: 8-bit"
echo "  Port: 8000"
echo "  Log: $LOG_FILE"
echo ""

# Check GPU
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "WARNING: nvidia-smi not available"

# Start server in tmux session so it persists after SSH disconnect
# If tmux session already exists, kill it first
tmux kill-session -t colqwen 2>/dev/null || true

tmux new-session -d -s colqwen \
    "cd $DEPLOY_DIR && source venv/bin/activate && python server.py --model vidore/colqwen2-v1.0 --port 8000 2>&1 | tee $LOG_FILE"

echo ""
echo "Server started in tmux session 'colqwen'"
echo ""
echo "Useful commands:"
echo "  tmux attach -t colqwen     # View server logs"
echo "  tmux kill-session -t colqwen  # Stop server"
echo "  curl localhost:8000/health  # Check health"
echo ""
echo "Waiting for model to load (this takes ~60-90 seconds)..."

# Wait for the server to be healthy
for i in $(seq 1 60); do
    sleep 3
    if curl -s http://localhost:8000/health | grep -q '"healthy"'; then
        echo ""
        echo "Server is HEALTHY and ready!"
        curl -s http://localhost:8000/health | python -m json.tool
        exit 0
    fi
    echo "  Still loading... (${i}x3s)"
done

echo ""
echo "Server did not become healthy in 180 seconds."
echo "Check logs: tmux attach -t colqwen"
exit 1
