#!/bin/bash
# ============================================================================
# EC2 Instance Setup Script for ColQwen Model Server
# Run this ONCE after launching a fresh g4dn.xlarge instance (Ubuntu 22.04 AMI)
# ============================================================================
set -e

echo "=========================================="
echo "ColQwen EC2 Setup - g4dn.xlarge"
echo "=========================================="

# ─── System Updates ──────────────────────────────────────────────────────────
echo "[1/6] Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# ─── NVIDIA Drivers (if not pre-installed) ───────────────────────────────────
echo "[2/6] Checking NVIDIA drivers..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "  Installing NVIDIA drivers..."
    sudo apt-get install -y nvidia-driver-535
    echo "  NVIDIA driver installed. You may need to reboot."
    echo "  Run: sudo reboot"
    echo "  Then re-run this script."
else
    echo "  NVIDIA driver already installed:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
fi

# ─── System Dependencies ────────────────────────────────────────────────────
echo "[3/6] Installing system dependencies..."
sudo apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    poppler-utils \
    git \
    htop \
    tmux

# ─── Python Virtual Environment ─────────────────────────────────────────────
echo "[4/6] Setting up Python virtual environment..."
DEPLOY_DIR="$HOME/colqwen-server"
mkdir -p "$DEPLOY_DIR"

if [ ! -d "$DEPLOY_DIR/venv" ]; then
    python3.10 -m venv "$DEPLOY_DIR/venv"
fi

source "$DEPLOY_DIR/venv/bin/activate"

# Upgrade pip
pip install --upgrade pip setuptools wheel

# ─── Install PyTorch with CUDA ──────────────────────────────────────────────
echo "[5/6] Installing PyTorch with CUDA support..."
# g4dn uses T4 GPU which supports CUDA 12.x
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Verify CUDA
python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA available: {torch.cuda.is_available()}')"
python -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0)}') if torch.cuda.is_available() else print('No GPU')"

# ─── Install Server Dependencies ────────────────────────────────────────────
echo "[6/6] Installing server dependencies..."
# Copy requirements.txt to deploy dir first (you should scp this file to the instance)
if [ -f "$DEPLOY_DIR/requirements.txt" ]; then
    pip install -r "$DEPLOY_DIR/requirements.txt"
else
    echo "  requirements.txt not found at $DEPLOY_DIR/requirements.txt"
    echo "  Copying from script directory..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cp "$SCRIPT_DIR/requirements.txt" "$DEPLOY_DIR/"
    pip install -r "$DEPLOY_DIR/requirements.txt"
fi

# ─── Pre-download Model ─────────────────────────────────────────────────────
echo "Pre-downloading ColQwen model (this may take a few minutes)..."
python -c "
from colpali_engine.models import ColQwen2, ColQwen2Processor
print('Downloading ColQwen2 model...')
ColQwen2Processor.from_pretrained('vidore/colqwen2-v1.0')
# Just download, don't load to GPU yet
from huggingface_hub import snapshot_download
snapshot_download('vidore/colqwen2-v1.0')
print('Model downloaded successfully')
"

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Deploy directory: $DEPLOY_DIR"
echo "Virtual env:      $DEPLOY_DIR/venv"
echo ""
echo "Next steps:"
echo "  1. Copy server files to $DEPLOY_DIR/"
echo "     scp server.py test_server.py test_with_pdf.py ubuntu@<ip>:$DEPLOY_DIR/"
echo ""
echo "  2. Start the server:"
echo "     cd $DEPLOY_DIR && ./start_server.sh"
echo ""
echo "  3. Test from your local machine:"
echo "     python test_server.py --host <ec2-public-ip>"
