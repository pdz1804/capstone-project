# Complete Environment Setup Guide

**Last Updated**: May 14, 2026  
**For**: Phase_2_FE_AI_Merge Unified RAG Pipeline  
**Duration**: 30-45 minutes for complete setup

---

## System Requirements

### Operating System
- **Linux** (Recommended): Ubuntu 20.04 LTS or later
- **Windows 11** (WSL2 recommended) or MacOS
- **Docker**: Required for Qdrant, Redis, optional for backend

### Hardware
- **CPU**: 4+ cores
- **RAM**: 16GB minimum (32GB recommended)
- **Disk**: 50GB free (includes model downloads)
- **GPU** (Optional but recommended):
  - NVIDIA GPU with 2GB+ VRAM (RTX 3060, A1000, or better)
  - CUDA 12.8 driver installed
  - NVIDIA CUDA Toolkit 12.8

### Software
- **Python**: 3.11 or 3.12
- **Node.js**: 18+ (for frontend)
- **Docker & Docker Compose**: Latest stable version
- **Git**: 2.30+

### System Binaries (Linux/Docker)
```bash
# Ubuntu/Debian
apt-get install -y ffmpeg tesseract-ocr poppler-utils libgomp1

# macOS (via Homebrew)
brew install ffmpeg tesseract poppler

# Windows (via Chocolatey)
choco install ffmpeg tesseract poppler
```

---

## Step 1: Clone & Setup Directory Structure

```bash
# Clone repository
git clone https://github.com/your-org/llm-capstone.git
cd llm-capstone

# Navigate to main directory
cd Phase_2_FE_AI_Merge

# View structure
tree -L 2 -I '__pycache__|*.egg-info|node_modules'
# Output:
# ├── backend/               # Python FastAPI backend
# │   ├── app/
# │   ├── src/
# │   ├── requirements.txt
# │   ├── Dockerfile
# │   └── main.py
# ├── frontend/              # React frontend
# │   ├── src/
# │   ├── package.json
# │   └── Dockerfile
# ├── sagemaker/             # AWS SageMaker deployment
# ├── terraform/             # IaC for AWS
# └── docker-compose.yml     # Local development stack
```

---

## Step 2: Backend Setup

### 2.1 Create Python Virtual Environment

```bash
cd backend

# Create venv
python3 -m venv venv

# Activate venv
# Linux/macOS:
source venv/bin/activate
# Windows:
# venv\Scripts\activate
```

### 2.2 Install Dependencies

**Option A: Using requirements-frozen.txt (Exact Versions)**
```bash
# For exact reproducibility (recommended for production/benchmarks)
pip install --upgrade pip
pip install -r requirements-frozen.txt \
  --extra-index-url https://download.pytorch.org/whl/cu128
```

**Option B: Using requirements.txt (Latest Compatible)**
```bash
# For development (allows security patches)
pip install --upgrade pip
pip install -r requirements.txt \
  --extra-index-url https://download.pytorch.org/whl/cu128
```

**Note**: Installation requires ~6-7 GB free disk space (torch wheel ~3.5 GB).  
If you get "Errno 28: No space left on device", clear pip cache:
```bash
pip cache purge
# Or use alternate TEMP drive:
set TEMP=D:\large_drive  # Windows
export TEMP=/mnt/large   # Linux
```

### 2.3 Verify Python Packages

```bash
# Check PyTorch installation
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.version.cuda}'); print(f'GPU available: {torch.cuda.is_available()}')"

# Expected output:
# PyTorch: 2.8.0
# CUDA: 12.8
# GPU available: True (if GPU installed)

# Check key packages
python -c "import docling; import transformers; import sentence_transformers; print('All packages OK')"
```

### 2.4 Set Environment Variables

Create `.env` file in `backend/` directory:

```bash
# Basic Configuration
ENVIRONMENT=development
LOG_LEVEL=INFO

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_S3_BUCKET=your-bucket-name

# Backend Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
WORKERS=4

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_key  # For remote Qdrant

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Bedrock/LLM Configuration
BEDROCK_REGION=us-east-1
BEDROCK_MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0

# Document Processing
DOCUMENT_PROCESSING_TIMEOUT=120  # seconds
MAX_FILE_SIZE_MB=500
OCR_ENGINE=tesseract  # or easyocr, rapidocr

# Inference (optional SageMaker)
USE_SAGEMAKER_INFERENCE=false
SAGEMAKER_ENDPOINT_DOCLING=docling-endpoint
SAGEMAKER_ENDPOINT_WHISPER=whisper-endpoint
```

### 2.5 Start Backend Services (with Docker Compose)

```bash
# From Phase_2_FE_AI_Merge root:
docker-compose up -d

# Verify services
docker-compose ps
# Output:
# NAME      IMAGE              STATUS
# redis     redis:7            Up 2 seconds
# qdrant    qdrant/qdrant      Up 2 seconds
# backend   backend:latest     Up 3 seconds
```

### 2.6 Check Qdrant Health

```bash
# Via curl
curl http://localhost:6333/health
# Response: {"status":"ok"}

# Via Python
python -c "from qdrant_client import QdrantClient; c = QdrantClient('localhost', port=6333); print('Connected:', c.get_collections())"
```

---

## Step 3: Frontend Setup

### 3.1 Install Node Dependencies

```bash
cd ../frontend

# Install packages
npm install

# Verify installation
npm list react react-dom  # Should show versions
```

### 3.2 Configure Frontend Environment

Create `.env` file in `frontend/` directory:

```bash
REACT_APP_API_BASE_URL=http://localhost:8000/api
REACT_APP_WEBSOCKET_URL=ws://localhost:8000/ws
REACT_APP_USER_ID=dev_user_123  # For testing
REACT_APP_ENVIRONMENT=development
```

### 3.3 Start Frontend Dev Server

```bash
npm start

# Output: 
# Compiled successfully!
# You can now view the app in the browser.
# Local: http://localhost:3000
```

---

## Step 4: Verification & Health Checks

### 4.1 Backend Health Check

```bash
# From backend directory (venv activated)
curl http://localhost:8000/health
# Response: {"status":"healthy","timestamp":"2026-05-14T10:30:45Z"}

# Extended health
curl http://localhost:8000/api/health
# Response: {"status":"healthy","components":{...},"latency_ms":145}
```

### 4.2 Test Search Endpoint

```bash
# Via curl
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -H "X-User-Id: dev_user_123" \
  -d '{
    "query": "test query",
    "top_k": 5,
    "mode": "retrieval_only"
  }'

# Via Python
python << 'EOF'
import requests
response = requests.post(
    "http://localhost:8000/api/search",
    json={"query": "test", "top_k": 1, "mode": "retrieval_only"},
    headers={"X-User-Id": "dev_user"}
)
print("Status:", response.status_code)
print("Response:", response.json())
EOF
```

### 4.3 Check Available Models

```bash
curl http://localhost:8000/api/search/generation-models \
  -H "X-User-Id: dev_user_123"

# Response shows configured models (Bedrock, OpenAI, etc.)
```

### 4.4 Frontend Access

Open browser to `http://localhost:3000`
- You should see the search interface
- Try a test query
- Verify results appear

---

## Step 5: Document Indexing

### 5.1 Prepare Sample Documents

```bash
# Create sample documents folder
mkdir -p sample_docs
cp /path/to/your/docs/*.pdf sample_docs/

# Or use test documents
python << 'EOF'
import json
from pathlib import Path

# Create minimal test corpus
test_docs = {
    "doc_1": {"text": "Machine learning is a subset of artificial intelligence."},
    "doc_2": {"text": "Deep learning uses neural networks with multiple layers."},
    "doc_3": {"text": "Natural language processing enables computers to understand text."}
}

Path("corpus.json").write_text(json.dumps(test_docs, indent=2))
print("Created corpus.json")
EOF
```

### 5.2 Run Document Processing Pipeline

```bash
cd backend

python << 'EOF'
from app.services.document_processor import DocumentProcessor, ProcessingConfig
from pathlib import Path

config = ProcessingConfig(
    enable_vlm=False,  # Disable for first run
    export_images=True,
    max_pages=10,
    chunk_size=500
)
processor = DocumentProcessor(config)

# Process sample documents
docs_path = Path("../sample_docs")
for doc_path in docs_path.glob("*.pdf"):
    print(f"Processing: {doc_path.name}")
    result = processor.process(str(doc_path))
    print(f"  Chunks: {len(result.chunks)}")
    print(f"  Metadata: {result.metadata}")
EOF
```

### 5.3 Index Documents for Retrieval

```bash
python << 'EOF'
from src.retrieval.rag_retrievers import DenseRetriever, BM25Retriever
from pathlib import Path
import json

# Load processed documents
processed_dir = Path("processed_documents")
documents = []
for chunk_file in processed_dir.glob("*/chunks.json"):
    docs = json.load(chunk_file.open())
    documents.extend(docs)

print(f"Indexing {len(documents)} chunks...")

# Create and index retrievers
bm25 = BM25Retriever("bm25_index")
bm25.index_documents(documents)

dense = DenseRetriever("dense_index")
dense.index_documents(documents)

print("Indexing complete!")
print(f"BM25 indexed: {len(documents)} documents")
print(f"Dense indexed: {len(documents)} documents")
EOF
```

---

## Step 6: Troubleshooting

### Issue: ImportError for docling or transformers

**Cause**: Incorrect PyTorch/CUDA version

**Fix**:
```bash
# Verify CUDA version
nvcc --version  # Should show 12.8

# Reinstall with correct index
pip uninstall torch torchvision torchaudio -y
pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
  --index-url https://download.pytorch.org/whl/cu128
```

### Issue: CUDA Out of Memory

**Cause**: GPU insufficient for models

**Fix**:
```bash
# Use smaller model or 8-bit quantization
export CUDA_VISIBLE_DEVICES=0
pip install bitsandbytes  # For quantization

# In code:
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(load_in_8bit=True)
model = AutoModelForCausalLM.from_pretrained(
    "model_name",
    quantization_config=quantization_config
)
```

### Issue: Qdrant Connection Refused

**Cause**: Qdrant service not running

**Fix**:
```bash
# Check if running
docker ps | grep qdrant

# Restart if needed
docker restart qdrant

# Check logs
docker logs qdrant

# Or run without Docker
./qdrant  # if installed locally
```

### Issue: Redis Connection Error

**Cause**: Redis not running

**Fix**:
```bash
docker restart redis
# Or verify it's running
redis-cli ping  # Should respond with PONG
```

### Issue: Tesseract Not Found

**Cause**: OCR engine not installed

**Fix**:
```bash
# Ubuntu/Debian
apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows
choco install tesseract
# Add to PATH: C:\Program Files\Tesseract-OCR
```

### Issue: "No space left on device" during pip install

**Cause**: Not enough disk space for torch wheel

**Fix**:
```bash
# Check disk space
df -h
# Need ~7GB free

# Clear pip cache
pip cache purge

# Use alternate TEMP
set TEMP=D:\drive_with_space  # Windows
export TMPDIR=/mnt/large      # macOS
export TEMP=/mnt/large        # Linux
```

---

## Step 7: Development Workflow

### Running Tests

```bash
cd backend

# Unit tests
pytest tests/unit -v

# Integration tests (requires services)
pytest tests/integration -v

# Specific test
pytest tests/test_document_processor.py::test_pdf_processing -v
```

### Linting & Type Checking

```bash
# Type check
mypy app/ src/

# Format code
black app/ src/

# Lint
flake8 app/ src/ --max-line-length=120
```

### Debugging

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run backend with debug output
python -m debugpy --listen 5678 --wait-for-client main.py

# Attach debugger from IDE (VS Code, PyCharm)
```

---

## Step 8: Production-Like Local Testing

### Docker Compose (Recommended for Local Dev)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Run backend commands in container
docker-compose exec backend python -c "import torch; print(torch.cuda.is_available())"

# Stop services
docker-compose down
```

### Environment-Specific Configs

```bash
# Development
.env.development  # Use localhost, debug enabled

# Staging
.env.staging      # Remote services, reduced logging

# Production
.env.production   # No debug, optimized settings
```

Load config:
```python
from dotenv import load_dotenv
import os

env_file = os.getenv("ENV_FILE", ".env.development")
load_dotenv(env_file)
```

---

## Quick Start (Minimal Setup)

For quickest setup without all components:

```bash
# 1. Backend only (with local files, no GPU)
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Start essential services
docker-compose up -d qdrant redis

# 3. Run backend
python main.py

# 4. Test (new terminal)
curl http://localhost:8000/health

# 5. Try search (requires indexed documents first)
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test","top_k":5}'
```

---

## Next Steps

1. **Index Documents**: Follow Step 5 to load sample documents
2. **Test Search**: Use curl/Python examples in API_DOCUMENTATION.md
3. **Run Benchmarks**: See EVALUATION_REPRODUCIBILITY.md for benchmark setup
4. **Explore Code**: Check TECHNICAL_DESIGN_DEEP_DIVE.md for architecture overview

---

## Getting Help

- **Logs**: Check `docker logs backend` or stdout
- **Architecture**: Read TECHNICAL_DESIGN_DEEP_DIVE.md
- **API Reference**: See API_DOCUMENTATION.md
- **Error Recovery**: See ERROR_HANDLING_AND_FAILURES.md
- **Troubleshooting**: See OPERATIONS_RUNBOOK.md

---

**Generated**: May 14, 2026  
**Version**: 1.0  
**Status**: Ready for development use
