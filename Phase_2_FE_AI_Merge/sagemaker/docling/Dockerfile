FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PORT=8080

WORKDIR /opt/program

RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /opt/program/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install -r /opt/program/requirements.txt

COPY server.py /opt/program/server.py
COPY sagemaker_entrypoint.sh /usr/local/bin/sagemaker_entrypoint.sh
RUN chmod +x /usr/local/bin/sagemaker_entrypoint.sh

ENTRYPOINT ["/usr/local/bin/sagemaker_entrypoint.sh"]
