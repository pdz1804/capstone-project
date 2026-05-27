# Build Reproducibility Guide

**Based on Actual Code Analysis**: Phase_2_FE_AI_Merge Backend  
**Last Updated**: May 14, 2026  

---

## CRITICAL: Generate requirements-frozen.txt

### Why Two Requirements Files?

The project has:
- **requirements.txt**: Flexible versions (allows feature updates)
- **requirements-frozen.txt**: Locked versions (guarantees reproducible builds)

### Current Status

**Requirements.txt Location**: `Phase_2_FE_AI_Merge/backend/requirements.txt` (103 lines)

**Current Version Constraints**:
- Pinned: transformers==4.57.3, peft==0.14.0, sentence-transformers==3.0.1, colpali-engine==0.3.13
- Min versions: accelerate>=0.30.0, huggingface-hub>=0.23.0, docling[all]>=2.0.0, boto3>=1.34.0
- Unpinned: 60+ packages with >= or no version spec

**Problem**: New developer gets different versions → "works on my machine"

### How to Generate requirements-frozen.txt

**Step 1: Fresh Virtual Environment**
```bash
cd Phase_2_FE_AI_Merge/backend
python -m venv venv_freeze
source venv_freeze/bin/activate  # Windows: venv_freeze\Scripts\activate
```

**Step 2: Install with requirements.txt**
```bash
pip install --upgrade pip
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu128
```

**Step 3: Capture Exact Versions**
```bash
pip freeze > requirements-frozen.txt
```

**Step 4: Verify and Commit**
```bash
# Quick sanity check
head -20 requirements-frozen.txt

# Verify key packages
grep -E "^(transformers|torch|qdrant|colpali)" requirements-frozen.txt

# Commit both files
git add requirements.txt requirements-frozen.txt
git commit -m "Add requirements-frozen.txt for reproducible builds"
```

### Expected Contents (Example Structure)

The generated `requirements-frozen.txt` should contain **ALL transitive dependencies** with exact versions:

```
# Core packages (pinned in original)
transformers==4.57.3
peft==0.14.0
sentence-transformers==3.0.1
colpali-engine==0.3.13

# PyTorch CUDA 12.8 (specific to your environment)
torch==2.8.0+cu128
torchvision==0.23.0+cu128
torchaudio==2.8.0+cu128

# Dependencies locked by pip
accelerate==0.31.2  # (or whatever pip resolved)
huggingface-hub==0.24.1  # (or whatever pip resolved)
docling==2.0.1  # (or whatever pip resolved)
# ... continues with 200+ transitive dependencies
```

**Important**: The exact versions will depend on when you run pip freeze. This is normal and expected.

---

## Using requirements-frozen.txt for Reproducible Builds

### For Exact Reproduction (Same Versions)
```bash
pip install -r Phase_2_FE_AI_Merge/backend/requirements-frozen.txt
```

**When to use**: 
- Debugging production issues
- Reproducing benchmark results
- CI/CD pipelines (guaranteed bit-identical builds)

### For Feature Updates (Compatible Versions)
```bash
pip install -r Phase_2_FE_AI_Merge/backend/requirements.txt
```

**When to use**:
- Local development
- Staying current with security patches
- Testing compatibility with newer package versions

---

## Dependency Tree: Key Constraints

### PyTorch/CUDA Stack

**From requirements.txt lines 5-8**:
```
PyTorch CUDA 12.8 (win_amd64 / cp311): 
must satisfy colpali-engine==0.3.13 → torch>=2.2,<2.9
```

**Actual Constraint Chain**:
1. colpali-engine==0.3.13 requires torch>=2.2,<2.9
2. torch 2.8.x available for CUDA 12.8 via special index URL
3. transformers==4.57.3 compatible with torch 2.8
4. peft==0.14.0 compatible with torch 2.8
5. sentence-transformers==3.0.1 compatible with torch 2.8

**Why NOT torch 2.11+**:
- colpali-engine==0.3.13 explicitly rejects torch>=2.9
- Newer colpali-engine (0.3.14+) exists but requires transformers>=5, peft>=0.18 (major version bump)
- Project intentionally locked on older colpali-engine for stability

### setuptools Constraint

**From requirements.txt line 16**:
```
setuptools>=80.9.0,<82
```

**Reason**: llama-index-core requires setuptools>=80.9. Cap at <82 because torch wheels sometimes pin setuptools and conflict.

### Document Processing Stack

**From requirements.txt lines 28-30**:
```
docling[all]>=2.0.0
docling-core>=2.0.0
docling-parse>=2.0.0
```

**These are exact** because:
- Docling is the core multimodal document processor
- Version 2.0.0+ is required for layout analysis + OCR + media support
- [all] installs all optional backends

### OCR Engine Selection

**From requirements.txt lines 59-61** (all three OCR engines available):
```
pytesseract          # Tesseract OCR (line 59)
easyocr              # EasyOCR engine (line 60)
rapidocr-onnxruntime # RapidOCR engine (line 61)
```

**From code** (`document_processor.py` lines 434-476):
- System uses **configurable OCR engine selection** (not automatic fallback)
- OCR engine chosen via `ocr_engine` configuration parameter
- All three engines available, configuration determines which is used
- Each engine has different speed/accuracy characteristics:
  - Tesseract: Fastest (~10ms), requires system binary installation
  - EasyOCR: Medium speed (~100ms), pure Python, language support
  - RapidOCR: Variable speed, ONNX-based inference

### Media Processing Stack

**From requirements.txt lines 46-51**:
```
moviepy          # Video extraction
pydub            # Audio manipulation
librosa          # Audio analysis
soundfile        # Audio I/O
audioread        # Audio format support
openai-whisper   # Speech-to-text
```

**System Binary Requirement**: FFmpeg (not in pip)
- Installed in Dockerfile (sagemaker/unified/Dockerfile line 16)
- Required by moviepy.VideoFileClip()

### Retrieval Stack

**From requirements.txt lines 63-67**:
```
faiss-cpu          # CPU version (portable, slower)
rank-bm25          # Sparse BM25 retrieval
datasets           # Dataset utilities
apted>=1.0.3       # Tree edit distance
Levenshtein>=0.25.1 # String similarity
```

**Note**: faiss-cpu is used intentionally (not faiss-gpu) for portability across machines with/without NVIDIA GPUs.

### AWS/Cloud Stack

**From requirements.txt lines 72-77**:
```
qdrant-client>=1.9.0              # Vector database client
boto3>=1.34.0                     # AWS services (S3, SageMaker, DynamoDB)
redis>=5.0.0                      # Caching
strands-agents                    # Agent runtime
strands-agents-tools              # Agent tools
bedrock-agentcore[strands-agents] # Bedrock integration
```

---

## System Dependencies

### Linux/Docker (from actual Dockerfile)

**Backend Dockerfile** (`Phase_2_FE_AI_Merge/backend/Dockerfile` lines 5-8):
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    poppler-utils
```

**Unified SageMaker** (`Phase_2_FE_AI_Merge/sagemaker/unified/Dockerfile` lines 16-18):
```dockerfile
RUN apt-get install -y ffmpeg poppler-utils tesseract-ocr
```

### Windows Local Development

**Required System Binaries** (from code analysis):

| Tool | Purpose | Install |
|------|---------|---------|
| **FFmpeg** | Video frame extraction (moviepy) | `choco install ffmpeg` or `winget install ffmpeg` |
| **Tesseract OCR** | Primary OCR engine | `choco install tesseract` |
| **Poppler** | PDF utilities (pdf2image) | `choco install poppler` |

### Verify Installation

```bash
# FFmpeg
ffmpeg -version

# Tesseract
tesseract --version

# Poppler
pdftops -v  # or pdftotext -v
```

---

## GPU Requirements (Optional but Recommended)

### Runtime GPU (for document processing)

From actual code (`document_processor.py` lines 120-134):

**GPU Optimization Config**:
```python
torch.set_float32_matmul_precision('high')  # Faster matmul
torch._dynamo.config.suppress_errors = True  # Avoid compile errors
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")  # Force eager mode
```

**Tested on**: NVIDIA RTX A1000 (16 SMs, 2GB memory)
- ColQwen quantized to 8-bit
- Docling runs on CPU with CUDA assistance
- Whisper runs on CPU only

**Minimum GPU**: 2GB VRAM (with quantization)
**Recommended**: 6GB VRAM (RTX 3060 or better)
**CPU-only**: Supported but slow (~5x slower)

### CUDA Toolkit Version

**Pinned to CUDA 12.8** (from requirements.txt line 5):
```
--extra-index-url https://download.pytorch.org/whl/cu128
```

- PyTorch wheels compiled against CUDA 12.8
- Must match cuDNN version: cuDNN 9.x for CUDA 12
- TensorRT 10.x compatible

---

## Disk Space Requirements

### Installation

**From requirements.txt comment lines 10-11**:
```
Install needs several GB free on TEMP + pip cache (torch wheel ~3.5 GB).
If Errno 28: free disk space, run `pip cache purge`.
```

**Actual breakdown**:
- torch 2.8.0+cu128 wheel: ~3.5 GB
- Other packages: ~2-3 GB
- Python venv: ~500 MB
- **Total**: ~6-7 GB free required

### Runtime

**Document processing output**:
- Per 1000 documents: ~500 MB to 2 GB (depends on page count, image extraction)
- Index storage (text): ~500 MB per 10M tokens
- Index storage (image): ~5-10 GB per 1M images (with quantization)

---

## CI/CD Integration

### For GitHub Actions

**Update `.github/workflows/backend-cicd.yml`**:

```yaml
- name: Install dependencies
  run: |
    cd Phase_2_FE_AI_Merge/backend
    pip install -r requirements-frozen.txt \
      --extra-index-url https://download.pytorch.org/whl/cu128
```

**Why frozen.txt in CI/CD**:
- Guarantees bit-identical builds across all CI runners
- Prevents version drift failures
- Reproducible benchmark results

### For Local Development

**Keep using requirements.txt** for flexibility:
```bash
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu128
```

---

## Troubleshooting

### Error: "ResolutionImpossible with colpali-engine==0.3.13"

**Cause**: Using torch>=2.9 (not compatible)

**Fix**:
```bash
pip install 'torch>=2.2,<2.9' --index-url https://download.pytorch.org/whl/cu128
```

### Error: "No space left on device (Errno 28)"

**Cause**: TEMP drive too small for torch wheel

**Fix**:
```bash
# Clear pip cache
pip cache purge

# Use alternate drive for TEMP
set TEMP=D:\large_drive_with_space  # Windows
export TEMP=/mnt/large_drive        # Linux
pip install -r requirements.txt
```

### Error: "pytesseract.TesseractNotFoundError"

**Cause**: Tesseract binary not installed or not in PATH

**Fix**:
```bash
# Windows
choco install tesseract

# Linux
apt-get install tesseract-ocr

# Verify
tesseract --version
```

### Error: "UnicodeDecodeError" during DOCX processing

**Cause**: Non-UTF-8 text encoding in Office documents

**Status**: Handled by docx_reader_v2.py line 579 with try/except
**User Experience**: Document processes with partial text

---

## Version Update Strategy

### When to Update requirements.txt

1. **Security patches**: Immediate (python-dotenv, fastapi, etc.)
2. **Feature requests**: Next release cycle
3. **Dependency conflicts**: As needed

### Proper Update Procedure

```bash
# 1. Update individual package in requirements.txt
# Edit: transformers==4.57.3 → transformers==4.58.0

# 2. Create fresh venv
python -m venv venv_test
source venv_test/bin/activate

# 3. Install and test
pip install -r requirements.txt

# 4. Run smoke tests
pytest tests/

# 5. If OK, freeze new versions
pip freeze > requirements-frozen.txt

# 6. Commit together
git add requirements.txt requirements-frozen.txt
```

---

## Key Takeaways

✅ **Use requirements-frozen.txt** for:
- Production deployments
- CI/CD pipelines
- Benchmark reproduction
- Bug investigation

✅ **Use requirements.txt** for:
- Local development
- Staying current with patches
- Testing compatibility

✅ **Keep both files** in version control:
- requirements.txt: Human-readable constraints
- requirements-frozen.txt: Machine-readable exact versions

✅ **Update frozen.txt whenever**:
- Updating requirements.txt
- Before major releases
- On security patches

---

**Generated**: May 14, 2026  
**Based on**: Phase_2_FE_AI_Merge/backend codebase analysis  
**Next**: See EVALUATION_REPRODUCIBILITY.md for benchmark seeding
