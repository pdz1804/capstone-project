# 🔍 CODE ANALYSIS: Current Pipeline & CUDA OOM Issue

**Date:** 2026-04-22  
**Focus:** Document Processing Pipeline v2, SageMaker Integration, CUDA Out-of-Memory Issue

---

## 📋 EXECUTIVE SUMMARY

### Current Status: ❌ CUDA OOM ERROR
When processing `EAG_RMF_Slide.pdf`, Docling's layout model runs out of GPU memory during the `layout_predictor.predict_batch()` step.

### Root Cause
**The code is missing a LOCAL vs SAGEMAKER CONFIG SWITCH for Docling and Whisper**

You have:
- ✅ `docling_remote.py` - SageMaker Docling logic exists
- ✅ `should_use_sagemaker_docling()` - Detection function exists
- ❌ **NOT integrated into document_processor_v2.py**
- ❌ **NOT exposed in ProcessingConfigV2 dataclass**
- ❌ **NOT exposed in API config routes**

---

## 🏗️ ARCHITECTURE OVERVIEW

### Pipeline Flow
```
[API Request: /api/process]
         ↓
    [run_api.py or indexing_service.py]
         ↓
    [DocumentProcessorV2]  ← Main entry point
         ↓
    [Smart Router: _route()]
         ↓
    ┌────────────────────────────────────────┐
    │ - docx_reader_v2      (custom)         │
    │ - xlsx_reader_v2      (custom)         │
    │ - pptx_reader         (custom)         │
    │ - pdf_reader          (custom)         │
    │ - docling             (default/fallback) ← CUDA OOM happens here
    └────────────────────────────────────────┘
         ↓
    [Export Results: _export_docling() or _export_custom()]
         ↓
    [S3 Storage or Local Workspace]
```

---

## 📁 KEY FILES & CURRENT STATE

### 1. **document_processor_v2.py** (LINE 45-62)
**Current Config:**
```python
@dataclass
class ProcessingConfigV2:
    prefer_custom_readers: bool = True
    excel_reader_mode: str = "xml"
    pptx_llm_validate_headers: bool = False
    pdf_content_source: str = "hybrid"
    docling_config: Optional[Any] = None  # ← Wraps ProcessingConfig
```

**MISSING:**
- `use_sagemaker_docling: bool = False`
- `sagemaker_docling_endpoint_name: str = ""`
- `use_sagemaker_whisper: bool = False`
- `sagemaker_whisper_endpoint_name: str = ""`
- `aws_region: str = "us-west-2"`

---

### 2. **docling_remote.py** (COMPLETE - NOT USED)
**Functions Exist But Unused:**
- `should_use_sagemaker_docling(runtime_yaml)` - ✅ Has detection logic
- `invoke_sagemaker_docling(file_path, runtime_yaml)` - ✅ Calls SageMaker endpoint
- `write_docling_outputs_from_sagemaker()` - ✅ Writes response to disk

**Problem:** `document_processor_v2.py` NEVER calls these functions!

---

### 3. **document_processor_v2.py::_get_primary_converter()** (LINE 329-417)
**What It Does:**
```python
def _get_primary_converter(self):
    # Lazy-loads Docling locally
    # Uses GPU for layout/VLM/OCR
    # Creates StandardPdfPipeline with DoclingParseV4Backend
```

**ISSUE:**
- Always instantiates Docling locally on GPU
- No check for `use_sagemaker_docling`
- No fallback to SageMaker when local GPU is full

---

### 4. **media_processor_enhanced.py** (HAS SAGEMAKER SUPPORT!)
**Good News - Whisper already uses it:**
```python
if should_use_sagemaker_whisper(media_config=self.config):
    return invoke_sagemaker_whisper(...)
else:
    return transcribe_locally_with_whisper(...)
```

**Why Docling doesn't:**
- Docling remote logic exists separately
- Never integrated into DocumentProcessorV2

---

## 🚨 THE PROBLEM: 3-LAYER FAILURE

### Layer 1: ProcessingConfigV2 Missing Fields
```python
# CURRENT (incomplete)
docling_config: Optional[Any] = None

# NEEDED
use_sagemaker: bool = False
sagemaker_endpoint_name: str = ""
aws_region: str = "us-west-2"
runtime_yaml: Optional[Dict[str, Any]] = None  # for detection
```

### Layer 2: _run_docling() Not Checking SageMaker
```python
# CURRENT (line 282-323)
def _run_docling(self, file_path: Path) -> Any:
    converter = self._get_primary_converter()  # ← Always local!
    try:
        result = converter.convert(str(actual_path))
    except Exception as primary_err:
        ...

# NEEDED
def _run_docling(self, file_path: Path) -> Any:
    if self.config.use_sagemaker_docling:
        return self._run_sagemaker_docling(file_path)
    converter = self._get_primary_converter()
    ...
```

### Layer 3: No SageMaker Method in DocumentProcessorV2
```python
# MISSING METHOD
def _run_sagemaker_docling(self, file_path: Path) -> Dict[str, Any]:
    from .docling_remote import invoke_sagemaker_docling, write_docling_outputs_from_sagemaker
    
    result = invoke_sagemaker_docling(file_path, runtime_yaml={...})
    write_docling_outputs_from_sagemaker(self.output_dir, file_path, result)
    return result  # Format to match _run_docling() contract
```

---

## 🔧 CURRENT ERROR TRACE

```
[PDF PROCESSING]
  → DocumentProcessorV2.process_single_file()
    → processor_key = "docling"  (routed here)
    → _run_docling()
      → _get_primary_converter()
        → StandardPdfPipeline initialized on GPU
        → layout_model.predict_batch() ← CUDA ERROR
          → torch.AcceleratorError: CUDA error: out of memory
```

**Why It Happens:**
1. PDF is 11 pages
2. Each page → layout model inference (large memory footprint)
3. Local GPU (RTX 4090 or similar) has ~24GB VRAM
4. Docling layout model + other models eat it all up
5. **CUDA OOM** when processing page 1-5

---

## ✅ THE SOLUTION: 3-STEP FIX

### Step 1: Add Config Fields to ProcessingConfigV2
```python
@dataclass
class ProcessingConfigV2:
    prefer_custom_readers: bool = True
    excel_reader_mode: str = "xml"
    pptx_llm_validate_headers: bool = False
    pdf_content_source: str = "hybrid"
    docling_config: Optional[Any] = None
    
    # ← NEW FIELDS ←
    use_sagemaker_for_docling: bool = False
    sagemaker_docling_endpoint_name: str = ""
    aws_region: str = "us-west-2"
    
    # ← OPTIONAL: pass runtime.yaml for auto-detection ←
    runtime_yaml: Optional[Dict[str, Any]] = None
```

### Step 2: Add SageMaker Branch to _run_docling()
```python
def _run_docling(self, file_path: Path) -> Any:
    """Run Docling converter (local or SageMaker)."""
    
    # Check if SageMaker should be used
    use_sagemaker = (
        self.config.use_sagemaker_for_docling or
        should_use_sagemaker_docling(self.config.runtime_yaml)
    )
    
    if use_sagemaker:
        return self._run_sagemaker_docling(file_path)
    
    # Existing local logic
    converter = self._get_primary_converter()
    ...
```

### Step 3: Add SageMaker Invocation Method
```python
def _run_sagemaker_docling(self, file_path: Path) -> Dict[str, Any]:
    """Invoke SageMaker Docling endpoint."""
    from .docling_remote import (
        invoke_sagemaker_docling,
        write_docling_outputs_from_sagemaker
    )
    
    runtime_yaml = {
        "inference": {
            "use_aws_sagemaker_docling": True,
            "sagemaker_docling_endpoint_name": self.config.sagemaker_docling_endpoint_name,
            "aws_region": self.config.aws_region,
        }
    }
    
    try:
        response = invoke_sagemaker_docling(file_path, runtime_yaml)
        write_docling_outputs_from_sagemaker(
            self.output_dir, file_path, response
        )
        return response
    except Exception as e:
        logger.error(f"SageMaker Docling failed: {e}. Falling back to local.")
        # Fall through to local converter
        converter = self._get_primary_converter()
        return converter.convert(str(file_path))
```

---

## 🔄 MISSING PIECE: Configuration Exposure

### Where Config Should Be Set

**1. Environment Variables (✅ Already supported by docling_remote.py):**
```bash
export USE_AWS_SAGEMAKER_DOCLING=1
export SAGEMAKER_DOCLING_ENDPOINT_NAME=my-endpoint
export AWS_REGION=us-west-2
```

**2. runtime.yaml Config File (✅ Already supported by docling_remote.py):**
```yaml
inference:
  use_aws_sagemaker_docling: true
  sagemaker_docling_endpoint_name: "my-docling-endpoint"
  aws_region: "us-west-2"
```

**3. API Route / ProcessingConfigV2 (❌ MISSING):**
```python
# app/api/routes/config_routes.py or process_routes.py
config = ProcessingConfigV2(
    use_sagemaker_for_docling=True,  # ← NEW
    sagemaker_docling_endpoint_name="my-endpoint",  # ← NEW
    ...
)
processor = DocumentProcessorV2(input_dir, output_dir, config)
```

---

## 📊 COMPARISON: Local vs SageMaker

| Aspect | Local GPU | SageMaker |
|--------|-----------|-----------|
| **Memory** | Single machine (24-40GB) | Scalable cluster |
| **Speed** | 10-60s per PDF (depends on size) | 30-120s (network latency) |
| **Cost** | EC2 GPU cost | SageMaker endpoint cost + invocation |
| **Reliability** | OOM on large PDFs | Handled by managed service |
| **Config** | ✅ Done | ❌ Not integrated |
| **Fallback** | None | Can fallback to local |

---

## 📝 ISSUES TO FIX (Priority Order)

### 🔴 CRITICAL
1. **Add SageMaker config fields to ProcessingConfigV2**
   - `use_sagemaker_for_docling`
   - `sagemaker_docling_endpoint_name`
   - `aws_region`

2. **Implement SageMaker branch in _run_docling()**
   - Check config flag
   - Call `docling_remote.invoke_sagemaker_docling()`
   - Handle response + write outputs

3. **Expose config via API**
   - Add to request body schema in `/api/process`
   - Or read from env vars at startup

### 🟡 IMPORTANT
4. **Add similar config for Whisper** (if not already done)
   - Check `media_processor_enhanced.py`
   - Ensure `use_sagemaker_whisper` is accessible from API

5. **Update documentation**
   - Add SAGEMAKER env vars to README
   - Document `runtime.yaml` format

### 🟢 NICE-TO-HAVE
6. **Fallback strategy**
   - If SageMaker fails → retry with local GPU
   - If local GPU OOM → retry with SageMaker
   - Log which path was used

---

## 🎯 WHY THIS HAPPENED

1. **SageMaker support added piecemeal** (media_processor_enhanced.py has it, DocumentProcessorV2 doesn't)
2. **docling_remote.py created but never wired** (detection logic exists but unused)
3. **ProcessingConfigV2 incomplete** (doesn't expose SageMaker knobs)
4. **No integration test** (would have caught this)

---

## 🚀 NEXT STEPS

1. ✅ **Understand the current code** (you're here)
2. ⏭️ **Implement the 3-step fix** (add config → add SageMaker branch → add method)
3. ⏭️ **Test with SageMaker endpoint** (if available)
4. ⏭️ **Update API routes to expose config**
5. ⏭️ **Document environment setup**

---

## 📌 KEY CODE LOCATIONS

| Component | File | Lines | Status |
|-----------|------|-------|--------|
| ProcessingConfigV2 | `document_processor_v2.py` | 44-62 | ❌ Incomplete |
| _run_docling() | `document_processor_v2.py` | 282-323 | ❌ No SageMaker check |
| SageMaker Docling | `docling_remote.py` | 1-129 | ✅ Complete but unused |
| Whisper SageMaker | `media_processor_enhanced.py` | ~150-200 | ✅ Already working |
| API Route | `app/api/routes/*.py` | ? | ❌ No config exposure |

---

## 💡 QUICK REFERENCE: What's Working vs What's Not

### ✅ Working
- Custom readers (docx, xlsx, pptx, pdf_reader)
- Docling local processing (when GPU has enough memory)
- Whisper SageMaker integration (already done)
- Config loading from `runtime.yaml`
- SageMaker detection logic

### ❌ Not Working
- Docling SageMaker integration (not wired)
- Config exposure in ProcessingConfigV2
- Config exposure in API routes
- Fallback from local OOM to SageMaker

---

## 🚨 ADDITIONAL ISSUES DISCOVERED (NEW)

### Issue #4: DoclingParseV4DocumentBackend Deprecated
```
FutureWarning: DoclingParseV4DocumentBackend was removed in docling 2.74.0 
and will raise an error in a future release. Use DoclingParseDocumentBackend instead.
```

**Location:** `document_processor_v2.py::_get_primary_converter()` (line 342-349)

**Problem:**
- Code tries to load `DoclingParseV4DocumentBackend` first
- Falls back to `DoclingParseDocumentBackend` if import fails
- But docling 2.74.0+ has REMOVED v4, causing warning

**Current Code:**
```python
try:
    from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
    BACKEND = DoclingParseV4DocumentBackend  # ← WILL ERROR in docling 2.74.0+
except ImportError:
    try:
        from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
        BACKEND = DoclingParseDocumentBackend
    except ImportError:
        BACKEND = PyPdfiumDocumentBackend
```

**Fix:** Skip V4 and go straight to regular backend:
```python
try:
    from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
    BACKEND = DoclingParseDocumentBackend
except ImportError:
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    BACKEND = PyPdfiumDocumentBackend
```

---

### Issue #5: ONNXRuntime Bad Allocation During OCR
```
ERROR:docling.pipeline.standard_pdf_pipeline:Stage ocr failed for run 1: ...
onnxruntime.capi.onnxruntime_pybind11_state.Fail: [ONNXRuntimeError] : 1 : FAIL : bad allocation
```

**Why It Happens:**
1. Layout model uses GPU (CUDA OOM on page 1-5)
2. When layout fails, Docling retries with OCR
3. OCR uses RapidOCR (ONNX Runtime) which tries to allocate memory
4. **Both CUDA and ONNX are fighting for same GPU memory**
5. Result: `bad allocation` error

**Chain of Failures:**
```
PDF Processing
├─ Layout stage
│  └─ CUDA error: out of memory (page 1)
│     └─ Fallback to OCR stage
│        └─ RapidOCR + ONNX Runtime
│           └─ Bad allocation (shared GPU memory exhausted)
└─ Result: Complete failure
```

**Root Cause:**
- GPU memory never freed after layout model OOM
- OCR tries to load another model on same exhausted GPU
- No device reset or memory cleanup between failures

**Solutions:**
1. **Add GPU memory cleanup on exception** (minimal fix):
   ```python
   except torch.cuda.OutOfMemoryError:
       import torch
       torch.cuda.empty_cache()
       torch.cuda.reset_peak_memory_stats()
       # Try fallback
   ```

2. **Use SageMaker for both layout AND OCR** (comprehensive fix):
   - SageMaker isolates processes → no shared memory issues
   - Already supported by `docling_remote.py`
   - V2.1 implements this

3. **Disable OCR when layout fails** (practical quick fix):
   ```python
   pdf_kwargs = {
       "do_ocr": False,  # ← Disable if layout OOM expected
       ...
   }
   ```

---

## 📊 ISSUE PRIORITY & QUICK FIX SUMMARY

| Issue | Type | Severity | Quick Fix |
|-------|------|----------|-----------|
| CUDA OOM (Layout) | Memory | 🔴 CRITICAL | Use SageMaker (V2.1) |
| ONNX Bad Alloc (OCR) | Memory | 🔴 CRITICAL | Disable OCR or use SageMaker |
| DoclingParseV4 Deprecated | Compatibility | 🟡 WARNING | Remove V4 import attempt |

---

**Generated by:** Code Analysis  
**For:** PDZ1804 (bk_mind project)  
**Severity:** CRITICAL - Blocking production use of large PDFs  
**Last Updated:** 2026-04-22 Session 2
