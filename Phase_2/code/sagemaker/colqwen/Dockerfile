FROM nvidia/cuda:12.6.0-cudnn-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PORT=8080

WORKDIR /opt/program

RUN apt-get update && apt-get install -y \
    python3.11 python3.11-dev python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.11 /usr/bin/python

RUN python3.11 -m pip install --upgrade pip setuptools wheel && \
    python3.11 -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu126

COPY requirements.txt /opt/program/requirements.txt
RUN python3.11 -m pip install -r /opt/program/requirements.txt

COPY server.py /opt/program/server.py
COPY sagemaker_entrypoint.sh /usr/local/bin/sagemaker_entrypoint.sh
RUN chmod +x /usr/local/bin/sagemaker_entrypoint.sh

ENTRYPOINT ["/usr/local/bin/sagemaker_entrypoint.sh"]
