FROM nvidia/cuda:12.6.0-cudnn-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /opt/program

# Install Python and pip
RUN apt-get update && apt-get install -y python3.11 python3.11-dev python3-pip wget && rm -rf /var/lib/apt/lists/*

# Create python symlink
RUN ln -s /usr/bin/python3.11 /usr/bin/python

# Upgrade pip for python3.11 (critical: use python3.11 -m pip, not pip3)
RUN python3.11 -m pip install --upgrade pip setuptools wheel

# Install PyTorch with explicit error checking and verbose output
RUN echo "Installing PyTorch 2.6.0 with cu126..." && \
    python3.11 -m pip install -v torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu126 && \
    echo "PyTorch installation completed" && \
    python3.11 -c "import torch; assert torch.__version__.startswith('2.6.0'), f'torch version mismatch: {torch.__version__}'; print(f'✓ PyTorch {torch.__version__} verified')" || { echo "FATAL: torch not installed correctly"; exit 1; }

COPY requirements.txt /opt/program/requirements.txt
RUN python3.11 -m pip install -v --upgrade pip && python3.11 -m pip install -v -r /opt/program/requirements.txt

COPY server.py /opt/program/server.py
COPY sagemaker_entrypoint.sh /usr/local/bin/sagemaker_entrypoint.sh
RUN chmod +x /usr/local/bin/sagemaker_entrypoint.sh

ENV PORT=8080
ENTRYPOINT ["/usr/local/bin/sagemaker_entrypoint.sh"]
