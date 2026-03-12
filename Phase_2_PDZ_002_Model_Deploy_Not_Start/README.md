# Phase 2 PDZ 002 - GPU Model Deployment on EC2

## GPU-Dependent Components in Phase 2

After careful analysis of the Phase 2 codebase, the following components **require GPU** to run:

### 1. ColQwen/ColPali (Image Retrieval) — **HEAVY GPU**
- **File**: `Phase_2/backend/src/retrieval/image_retrievers.py`
- **Model**: `vidore/colqwen2-v1.0` (~3B params)
- **Config**: `image_retrieval.colqwen` in `default.yaml`
- **Why GPU**: Vision-language model that embeds PDF pages as images into multi-vector representations (1024 patches/page). Uses `bitsandbytes` for 8-bit quantization.
- **VRAM**: ~3.5GB (8-bit quantized), ~6GB (BF16)
- **Used for**: Both indexing (embedding PDF pages) and querying (embedding search queries)

### 2. Docling with VLM (Document Processing) — **HEAVY GPU**
- **File**: `Phase_2/backend/src/processor/document_processor.py`
- **Model**: `granite_docling` (IBM Granite VLM)
- **Config**: `processing.document.enable_vlm: true` in `default.yaml`
- **Why GPU**: Runs a Vision Language Model to understand document layout, describe pictures, and extract structured content from PDFs.
- **VRAM**: ~2-4GB depending on model variant

### 3. Whisper ASR (Media Processing) — **MODERATE GPU**
- **File**: `Phase_2/backend/src/processor/media_processor_enhanced.py`
- **Model**: OpenAI Whisper (`base`, `small`, `medium`, `large-v3`)
- **Config**: `processing.media.asr_model` in `default.yaml`
- **Why GPU**: Audio transcription model. Runs on CPU too but 5-10x slower.
- **VRAM**: 0.5GB (base) to 3GB (large-v3)

### 4. Sentence Transformers / FAISS-GPU (Text Retrieval) — **LIGHT GPU**
- **File**: `Phase_2/backend/src/retrieval/rag_retrievers.py`
- **Models**: `all-MiniLM-L6-v2`, BGE rerankers
- **Config**: `text_retrieval.embedding_model`, `text_retrieval.reranker`
- **Why GPU**: Dense embedding + reranking benefit from GPU but work fine on CPU
- **VRAM**: ~0.5-1GB

### 5. EasyOCR (OCR) — **LIGHT GPU**
- **File**: `Phase_2/backend/src/processor/document_processor.py`
- **Config**: `processing.document.ocr_engine: easyocr`
- **Why GPU**: Deep-learning based OCR. Uses GPU if available, fallback to CPU.

---

## This Folder: ColQwen Deployment on EC2

This folder contains the code to **deploy the ColQwen model as an inference API** on an AWS EC2 `g4dn.xlarge` instance (NVIDIA T4, 16GB VRAM).

### Architecture
```
EC2 g4dn.xlarge (T4 GPU, 16GB VRAM)
├── FastAPI server (port 8000)
│   ├── POST /embed-images   → Embed PDF page images into multi-vectors
│   ├── POST /embed-query    → Embed a text query
│   ├── POST /score           → Score query vs document embeddings
│   ├── GET  /health          → Health check + GPU status
│   └── POST /shutdown        → Graceful shutdown to save costs
└── 8-bit quantized ColQwen model (~3.5GB VRAM)
```

### Cost Optimization Strategy
- **Instance**: `g4dn.xlarge` ($0.526/hr On-Demand, ~$0.16/hr Spot)
- **8-bit quantization**: Fits comfortably on T4 (3.5GB / 16GB), leaving room for batches
- **Shutdown endpoint**: Call `/shutdown` when not in use → stop instance → $0 compute cost
- **Spot instances**: Use for ingestion workloads (async, fault-tolerant)
- **Savings Plan**: For baseline query instance, 1-year commitment = ~30-50% discount

### Files
```
├── README.md                    # This file
├── server.py                    # FastAPI inference server
├── requirements.txt             # Python dependencies
├── setup_ec2.sh                 # EC2 instance setup script (run once)
├── start_server.sh              # Start the inference server
├── stop_server.sh               # Stop the server gracefully
├── test_server.py               # Test script to validate deployment
└── test_with_pdf.py             # End-to-end test with a real PDF
```

### Quick Start on EC2

```bash
# 1. SSH into your g4dn.xlarge instance
ssh -i your-key.pem ubuntu@<ec2-public-ip>

# 2. Clone/copy this folder to the instance
# 3. Run the setup script (one-time)
chmod +x setup_ec2.sh
./setup_ec2.sh

# 4. Start the server
chmod +x start_server.sh
./start_server.sh

# 5. Test it (from your local machine or the instance)
python test_server.py --host <ec2-public-ip>
```

### On-Demand EC2 Billing — YES, You Pay Even When Idle

**Yes**, On-Demand EC2 instances charge you **per second** (minimum 60 seconds) from the moment you **start** the instance until you **stop** or **terminate** it. Even if no one is sending requests to the model, the instance is running and you are paying.

- `g4dn.xlarge` costs **$0.526/hour** ($12.62/day, $378.72/month if left running 24/7)
- **Stopped** instances: $0 compute charges (you still pay for EBS storage, ~$0.10/GB/month)
- **Terminated** instances: $0 everything

**Cost saving workflow**:
1. When students are not using the system → **stop the instance** (via AWS Console, CLI, or the `/shutdown` endpoint)
2. When needed → **start the instance** (takes ~30-60s to boot, then ~60-90s to load model into GPU)
3. Total cold start: ~2-3 minutes

This is why the `/shutdown` endpoint exists — your backend can call it to auto-stop the GPU instance during off-hours.
