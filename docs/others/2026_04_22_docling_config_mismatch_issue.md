# 🚨 CRITICAL ISSUE: Docling Config Mismatch Between Local and SageMaker

**Date:** 2026-04-22  
**Severity:** HIGH - Causes inconsistent document processing results  
**Status:** REQUIRES IMMEDIATE FIX

---

## 📊 THE PROBLEM

When using V2.1 with SageMaker Docling enabled, the **config settings are NOT matching** between local Docling and SageMaker endpoint.

### What's Configured Locally (V2/V2.1)
```python
# From processing_service.py & pipeline.py
document_config = ProcessingConfig(
    enable_ocr=True,              # ✅ Enabled
    enable_vlm=True,              # ✅ Enabled
    export_markdown=True,         # ✅ Enabled
    export_images=True,           # ✅ Enabled (extracts images)
    export_tables=True,           # ✅ Enabled (extracts tables)
)
```

### What's Configured in SageMaker (server.py defaults)
```python
# From sagemaker/docling/server.py (lines 74-78)
enable_vlm = os.getenv("DOCLING_ENABLE_VLM", default=False)           # ❌ DEFAULT: False
enable_ocr = os.getenv("DOCLING_ENABLE_OCR", default=True)            # ✅ DEFAULT: True
export_images = os.getenv("DOCLING_EXPORT_IMAGES", default=False)     # ❌ DEFAULT: False
export_tables = os.getenv("DOCLING_EXPORT_TABLES", default=False)     # ❌ DEFAULT: False
ocr_engine = os.getenv("DOCLING_OCR_ENGINE", default="rapidocr")      # ✅ DEFAULT: rapidocr
```

---

## ⚠️ CONFIG COMPARISON TABLE

| Setting | Local (V2/V2.1) | SageMaker Default | Match? |
|---------|-----------------|-------------------|--------|
| **OCR Enabled** | `True` | `True` | ✅ YES |
| **VLM Enabled** | `True` | `False` | ❌ NO |
| **Export Images** | `True` | `False` | ❌ NO |
| **Export Tables** | `True` | `False` | ❌ NO |
| **Images Scale** | `2.0` | `2.0` | ✅ YES |
| **OCR Engine** | rapidocr | rapidocr | ✅ YES |

---

## 💥 CONSEQUENCE: INCONSISTENT OUTPUTS

### Processing Same PDF: Local vs SageMaker

**Local Docling (V2/V2.1):**
```
Input: document.pdf (11 pages)

Output folder: document/
├── document.md                    ← Markdown with all text
└── docling_additional/
    ├── images/                    ← ✅ Image extracts (VLM descriptions)
    │   ├── image_001.png
    │   ├── image_002.png
    │   └── ...
    ├── tables/                    ← ✅ Table extracts (structured)
    │   ├── table_001.csv
    │   └── ...
    └── metadata.json

Features:
  ✅ Image descriptions (from VLM)
  ✅ Extracted images
  ✅ Structured tables
  ✅ All text + layout
```

**SageMaker Docling (With Defaults):**
```
Input: document.pdf (11 pages)

Output: {"markdown": "...", "additional_files": {}}

Features:
  ❌ NO image descriptions (VLM disabled)
  ❌ NO image extracts (export_images=False)
  ❌ NO table extracts (export_tables=False)
  ✅ All text (OCR enabled)
  ✅ Layout preserved
```

**Result:** Same PDF produces DIFFERENT outputs! ❌

---

## 🔍 ROOT CAUSE

### How SageMaker Config Works

1. **Endpoint Startup** (One time, when deployed):
   ```bash
   docker run ... \
     -e DOCLING_ENABLE_VLM=false \
     -e DOCLING_EXPORT_IMAGES=false \
     -e DOCLING_EXPORT_TABLES=false \
     sagemaker-docling:latest
   ```

2. **Request Time** (Every request):
   ```python
   # sagemaker/docling/server.py::_process_document()
   # Uses converter built at startup - NO config override possible!
   result = _converter.convert(str(tmp_path))
   ```

### Why It's Set Conservative

From server.py comment (line 11-16):
```
Processing defaults are intentionally conservative (no VLM, no image/table export)
to match backend/config/default.yaml. Override via env:
  DOCLING_ENABLE_VLM=true
  DOCLING_EXPORT_IMAGES=true
  DOCLING_EXPORT_TABLES=true
```

**Translation:** To get VLM + images + tables from SageMaker, you must **redeploy the endpoint** with different env vars!

---

## 🛠️ SOLUTIONS

### Solution 1: Set Environment Variables on SageMaker Endpoint (IMMEDIATE FIX)

When deploying the endpoint, set these env vars:

```bash
# Either via CloudFormation
EnvironmentVariables:
  DOCLING_ENABLE_VLM: "true"
  DOCLING_EXPORT_IMAGES: "true"
  DOCLING_EXPORT_TABLES: "true"
  DOCLING_OCR_ENGINE: "rapidocr"

# Or via Python boto3
response = sagemaker_client.create_model(
    ModelName="docling-model",
    Containers=[{
        "Image": "docling-image:latest",
        "Environment": {
            "DOCLING_ENABLE_VLM": "true",
            "DOCLING_EXPORT_IMAGES": "true",
            "DOCLING_EXPORT_TABLES": "true",
            "DOCLING_OCR_ENGINE": "rapidocr",
        }
    }]
)

# Or via PowerShell
$env:DOCLING_ENABLE_VLM = "true"
$env:DOCLING_EXPORT_IMAGES = "true"
$env:DOCLING_EXPORT_TABLES = "true"
```

### Solution 2: Modify server.py to Accept Per-Request Config (BEST LONG-TERM)

Update `sagemaker/docling/server.py` to accept config in request:

```python
class InvocationRequest(BaseModel):
    operation: str
    filename: str = "document.pdf"
    content_base64: str = ""
    # ADD THESE CONFIG FIELDS:
    config: Optional[Dict[str, Any]] = None

@app.post("/invocations")
async def invocations(req: InvocationRequest = Body(...)):
    op = req.operation.strip().lower()
    if op == "process-document":
        # Use request config if provided, else use env-based converter
        if req.config:
            converter = _build_converter_from_config(req.config)
        else:
            converter = _converter
        result = converter.convert(...)
```

Then in `docling_remote.py`:

```python
def invoke_sagemaker_docling(file_path: Path, runtime_yaml: Dict[str, Any], config: ProcessingConfig = None):
    payload = {
        "operation": "process-document",
        "filename": file_path.name,
        "content_base64": base64.b64encode(raw).decode("ascii"),
        # ADD CONFIG:
        "config": {
            "enable_vlm": bool(config.enable_vlm) if config else True,
            "export_images": bool(config.export_images) if config else True,
            "export_tables": bool(config.export_tables) if config else True,
            "ocr_engine": str(config.ocr_engine) if config else "rapidocr",
        }
    }
```

### Solution 3: Update V2.1 to Match SageMaker Defaults (CONSERVATIVE)

Change V2.1 to use conservative settings when SageMaker enabled:

```python
# In document_processor_v2_1.py
if self.config.use_sagemaker_for_docling:
    # Match SageMaker conservative defaults
    enable_vlm = False
    export_images = False
    export_tables = False
```

---

## ✅ RECOMMENDATION

**Priority 1 (Immediate - Pick ONE):**
- **Option A:** Redeploy SageMaker endpoint with env vars (Solution 1) → ⏱️ 2-5 minutes
- **Option B:** Update V2.1 to conservative mode when SageMaker (Solution 3) → ⏱️ 2 lines of code

**Priority 2 (Long-term):**
- Implement per-request config in server.py (Solution 2) → ⏱️ 30 minutes

---

## 📋 FILES TO CHECK/UPDATE

### Current State
- ✅ `sagemaker/docling/server.py` - Uses env vars (conservative defaults)
- ✅ `src/processor/docling_remote.py` - Sends no config
- ⚠️ `src/processor/document_processor_v2_1.py` - Doesn't know about SageMaker config limitation
- ⚠️ `app/services/processing_service.py` - Builds aggressive config, unaware of SageMaker defaults

### What Needs Change
1. **Quick Fix:** Document the SageMaker env var requirements
2. **Medium Fix:** Add config override to server.py
3. **Long-term:** Wire config through entire stack

---

## 🔄 PROCESSING FLOW (With Fix Applied)

### Before (BROKEN - Inconsistent outputs)
```
PDF → SageMaker → Markdown only (no images/tables)
PDF → Local → Markdown + images + tables
❌ DIFFERENT OUTPUTS
```

### After (FIXED - Consistent outputs)
```
PDF → SageMaker (with DOCLING_ENABLE_VLM=true, etc) → Markdown + images + tables
PDF → Local (same config) → Markdown + images + tables
✅ SAME OUTPUTS
```

---

## 📝 SUMMARY

| Aspect | Current | Issue | Fix |
|--------|---------|-------|-----|
| **Local Config** | VLM=T, Images=T, Tables=T | Aggressive | Intentional |
| **SageMaker Config** | VLM=F, Images=F, Tables=F | Conservative | Mismatch! |
| **Config Passing** | No | Can't sync | Need to add |
| **Per-Request Override** | No | Inflexible | Nice-to-have |

**Action Required:** At minimum, set SageMaker env vars to match local defaults!

---

**Generated:** 2026-04-22  
**Project:** bk_mind Phase 2  
**Branch:** develop
