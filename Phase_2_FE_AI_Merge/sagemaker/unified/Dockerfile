FROM nvidia/cuda:12.6.0-cudnn-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PORT=8080
ENV AWS_REGION=us-west-2
ENV PYTHONPATH=/opt/program/backend

WORKDIR /opt/program

RUN apt-get update && apt-get install -y \
    bash \
    python3.11 python3.11-dev python3-pip \
    wget \
    ffmpeg \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.11 /usr/bin/python

RUN python3.11 -m pip install --upgrade pip setuptools wheel

# Keep torch/cu126 install pattern aligned with Phase_2_PDZ_002_Model_Deploy (already proven).
RUN echo "Installing PyTorch 2.6.0 + cu126..." && \
    python3.11 -m pip install -v torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu126 && \
    python3.11 -c "import torch; assert torch.__version__.startswith('2.6.0'), f'torch version mismatch: {torch.__version__}'; print(f'PyTorch verified: {torch.__version__}')" || { echo "FATAL: torch install/verification failed"; exit 1; }

COPY Phase_2_FE_AI_Merge/sagemaker/unified/requirements.txt /opt/program/requirements.txt
RUN python3.11 -m pip install -v --upgrade pip && python3.11 -m pip install -v -r /opt/program/requirements.txt

COPY Phase_2_FE_AI_Merge/sagemaker/unified/server.py /opt/program/server.py
COPY Phase_2_FE_AI_Merge/sagemaker/unified/sagemaker_entrypoint.sh /usr/local/bin/sagemaker_entrypoint.sh
COPY Phase_2_FE_AI_Merge/backend /opt/program/backend

# Strip CR if the repo was checked out with CRLF; missing interpreter from bad shebang shows as "no such file or directory".
RUN sed -i 's/\r$//' /usr/local/bin/sagemaker_entrypoint.sh && chmod +x /usr/local/bin/sagemaker_entrypoint.sh

ENTRYPOINT ["/bin/bash", "/usr/local/bin/sagemaker_entrypoint.sh"]
