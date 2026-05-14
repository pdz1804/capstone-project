# Naming Conventions & Code Patterns (B3)

**Based on**: Phase_2_FE_AI_Merge actual implementation  
**Last Updated**: May 14, 2026  
**Scope**: Naming conventions, patterns, and coding standards across the codebase

---

## 1. Python Naming Conventions

### 1.1 Variables & Constants

**Pattern**: `snake_case` for variables and functions, `UPPER_SNAKE_CASE` for module-level constants

**Examples**:
```python
# ✅ Correct
document_id = "doc_123"
max_chunk_size = 512
retriever_type = "hybrid"
BATCH_SIZE = 32  # Module constant
DEFAULT_TOP_K = 10  # Config default

# ❌ Avoid
documentID = "doc_123"  # camelCase for Python vars
max_chunk_size2 = 512  # Numbered suffixes
retriever_Type = "hybrid"  # Mixed case
batchSize = 32  # camelCase for constants
```

**Special Cases**:
- **Private variables**: Prefix with `_` (single underscore)
  ```python
  _internal_cache = {}  # Private module state
  
  class MyClass:
      _private_field = None  # Private instance variable
      __very_private = None  # Name mangling (avoid unless intentional)
  ```
- **Temporary/loop variables**: Keep short only for loops, otherwise spell out
  ```python
  # ✅ OK for loop
  for i in range(10):
      process(chunks[i])
  
  # ✅ Better for non-loop
  for chunk in chunks:
      process(chunk)
  
  # ❌ Avoid
  for i in results:  # 'i' suggests integer index, not clear
      process(i)
  ```

---

### 1.2 Functions

**Pattern**: `snake_case`, verb-first for imperative functions

**Examples**:
```python
# ✅ Correct - clear what action is performed
def process_document(file_path: str) -> ProcessingResult:
    pass

def retrieve_chunks(query: str, top_k: int = 10) -> List[Chunk]:
    pass

def calculate_ndcg_at_k(retrieved: List, relevant: Dict, k: int) -> float:
    pass

def normalize_scores(scores: Dict[str, float]) -> Dict[str, float]:
    pass

# ❌ Avoid
def doc_process(file_path):  # Noun-first, less clear
    pass

def chunks_retrieve(query):  # Wrong word order
    pass

def calc_ndcg(retrieved, relevant, k):  # Abbreviated, less clear
    pass
```

**Naming Patterns by Function Type**:
- **Query/Retrieve functions**: `get_*`, `retrieve_*`, `search_*`
  ```python
  def get_documents_by_user(user_id: str) -> List[Document]:
      pass
  
  def retrieve_relevant_chunks(query: str) -> List[Chunk]:
      pass
  
  def search_with_hybrid_retrieval(query: str) -> SearchResult:
      pass
  ```

- **Processing functions**: `process_*`, `extract_*`, `parse_*`
  ```python
  def process_document(file_path: str) -> ProcessingResult:
      pass
  
  def extract_images_from_pdf(pdf_path: str) -> List[Image]:
      pass
  
  def parse_xlsx_structure(file_path: str) -> ExcelMetadata:
      pass
  ```

- **Calculation/Analysis functions**: `calculate_*`, `compute_*`, `analyze_*`
  ```python
  def calculate_ndcg_at_k(retrieved: List, relevant: Dict, k: int) -> float:
      pass
  
  def compute_rrf_score(doc_id: str, ranks: Dict[str, int]) -> float:
      pass
  
  def analyze_retrieval_quality(results: List, qrels: Dict) -> AnalysisReport:
      pass
  ```

- **Utility/Helper functions**: Shorter, specific action
  ```python
  def normalize_scores(scores: Dict) -> Dict:
      pass
  
  def merge_results(results1: List, results2: List) -> List:
      pass
  
  def format_output(data: Dict) -> str:
      pass
  ```

---

### 1.3 Classes

**Pattern**: `PascalCase` (CapWords)

**Examples**:
```python
# ✅ Correct
class DocumentProcessor:
    pass

class SimpleHybridRetriever(BaseRetriever):
    pass

class ProcessingMetadata:
    pass

class EvaluationMetrics:
    pass

# ❌ Avoid
class document_processor:  # snake_case for class
    pass

class SimpleHybridretriever:  # Inconsistent capitalization
    pass

class _DocumentProcessor:  # Leading underscore (private class, rarely needed)
    pass
```

**Class Naming Patterns**:
- **Processor/Handler classes**: `*Processor`, `*Handler`, `*Manager`
  ```python
  class DocumentProcessor:
      def process_document(self, file_path: str) -> ProcessingResult:
          pass
  
  class MediaProcessor:
      def extract_audio(self, file_path: str) -> AudioData:
          pass
  
  class CacheManager:
      def invalidate(self, key: str) -> None:
          pass
  ```

- **Retriever classes**: `*Retriever`
  ```python
  class BM25Retriever(BaseRetriever):
      pass
  
  class DenseRetriever(BaseRetriever):
      pass
  
  class SimpleHybridRetriever(BaseRetriever):
      pass
  ```

- **Configuration classes**: `*Config`
  ```python
  class ProcessingConfig:
      chunk_size_tokens: int = 512
      ocr_engine: str = "tesseract"
  
  class RetrievalConfig:
      top_k: int = 10
      retriever_type: str = "hybrid"
  ```

- **Data/Model classes**: `*Metadata`, `*Result`, `*Data`, or noun
  ```python
  class ProcessingMetadata:
      document_id: str
      chunk_count: int
  
  class SearchResult:
      text_results: List[Chunk]
      image_results: List[Image]
  
  class ChunkData:
      content: str
      page_number: int
  ```

- **Abstract/Base classes**: `Base*` prefix
  ```python
  class BaseRetriever(ABC):
      @abstractmethod
      def search(self, query: str) -> List[Chunk]:
          pass
  ```

---

### 1.4 Type Hints & Generics

**Pattern**: Use explicit types, import from `typing` module

**Examples**:
```python
from typing import List, Dict, Tuple, Optional, Union, Any

# ✅ Correct
def process_chunks(
    chunks: List[str],
    metadata: Dict[str, Any],
    top_k: int = 10
) -> Tuple[List[str], ProcessingResult]:
    pass

def retrieve_with_filter(
    query: str,
    user_id: Optional[str] = None
) -> List[Chunk]:
    pass

def handle_error(error: Union[ValueError, KeyError]) -> None:
    pass

# ❌ Avoid
def process_chunks(chunks, metadata, top_k=10):  # No type hints
    pass

def retrieve_with_filter(query: str, user_id=None):  # Missing type for optional
    pass

def handle_error(error):  # No type hint
    pass
```

---

## 2. Configuration Parameter Naming

### 2.1 Processing Configuration

**Prefix**: `processing_`, `chunk_`, `ocr_`, `gpu_`

**Examples** (from document_processor.py):
```python
# Document chunking
chunk_size_tokens = 512  # Tokens per chunk
chunk_overlap_tokens = 64  # Overlap between chunks
max_chunks_per_document = 1000  # Safety limit

# OCR configuration
ocr_engine = "tesseract"  # Choice: tesseract, easyocr, rapidocr
ocr_language = "eng"  # Language code (Tesseract format)
ocr_confidence_threshold = 0.5  # Min confidence to keep text

# GPU configuration
gpu_enabled = True
gpu_memory_fraction = 0.8  # Use 80% of available VRAM
use_quantization = True  # 8-bit quantization

# Processing pipeline
preserve_table_structure = True  # For Excel/tables
include_images = True  # Extract and process images
include_audio = True  # Extract and process audio
```

**Pattern**: Use underscores to separate concept from detail
```python
# ✅ Clear separation
batch_size = 32          # What: batch, Where/How: size
max_chunk_size = 512     # What: max_chunk, How: size in tokens
ocr_confidence = 0.5     # What: OCR, How: confidence threshold
gpu_memory_fraction = 0.8 # What: GPU memory, How: fraction

# ❌ Confusing
batch_sz = 32            # Abbreviated, unclear
max_size = 512           # Vague "size" (tokens? bytes? chars?)
ocr_conf = 0.5           # Abbreviated
gpu_mem = 0.8            # Unclear unit (fraction? percent? GB?)
```

---

### 2.2 Retrieval Configuration

**Prefix**: `retriever_`, `search_`, `ranking_`

**Examples** (from rag_retrievers.py, search_routes.py):
```python
# Retrieval mode
retriever_type = "hybrid"  # Choice: bm25, dense, hybrid
search_scope = "text"  # Choice: text, image, all

# Ranking parameters
top_k = 10  # Return top K results
bm25_k1 = 1.5  # BM25 saturation parameter
bm25_b = 0.75  # BM25 length normalization
rrf_constant = 60  # RRF fusion constant: score = 1/(constant + rank)

# Filtering & scoring
min_similarity_score = 0.0  # Minimum score threshold
score_normalization = "minmax"  # Choice: minmax, zscore, none

# Retrieval optimization
use_reranker = False  # Apply cross-encoder reranker
cache_results = True  # Cache search results
cache_ttl_seconds = 86400  # 24-hour cache TTL
```

**Pattern**: Use prefix to group related configs
```python
# ✅ Related configs share prefix
retriever_type = "hybrid"
retriever_timeout = 5.0
retriever_batch_size = 32

# ❌ Scattered, hard to find related configs
ret_type = "hybrid"
timeout = 5.0  # Is this retriever timeout? API timeout?
batch_size = 32  # For what? Retrieval? Processing?
```

---

### 2.3 Generation Configuration

**Prefix**: `generation_`, `generation_model_`, `prompt_`

**Examples**:
```python
# Model selection
generation_model = "gpt-4"  # or "claude-3", "llama-2"
generation_temperature = 0.7  # Randomness: 0=deterministic, 1=random
generation_max_tokens = 512  # Max output length
generation_top_p = 0.9  # Nucleus sampling

# Context
max_context_length = 2048  # Max tokens to pass as context
context_chunk_limit = 10  # Max number of retrieved chunks to use

# Prompting
prompt_system_role = "You are a helpful assistant"
prompt_instruction = "Answer based on provided context"
use_few_shot_examples = False  # Include examples in prompt
```

---

## 3. Database & Collection Naming

### 3.1 Qdrant Collections

**Pattern**: `{modality}_{entity}` or `{entity}_{modality}`

**Examples**:
```python
# Collections in Qdrant (vector databases)
text_chunks          # Main text retrieval collection
image_chunks         # Visual retrieval collection
video_frames         # Video frame embeddings
user_profiles        # User embedding vectors

# Naming structure: [scope]_[modality]_[entity]
# Scope (optional): global, user_specific, project_specific
# Modality: text, image, video, audio
# Entity: chunks, frames, profiles, metadata

# ✅ Clear intent
text_chunks          # Text chunk embeddings
document_metadata    # Document metadata (not embeddings)
user_documents       # Documents per user

# ❌ Ambiguous
embeddings           # Embeddings of what?
vectors              # Vectors of what type?
chunks               # Text chunks? Code chunks? What modality?
```

---

### 3.2 Database Tables / Document Fields

**Pattern**: `{entity}_{attribute}` for fields, `{entity_type}_{state}` for tables

**Examples**:
```python
# Document/Chunk metadata fields (in Qdrant payload)
document_id          # UUID of source document
user_id              # Owner of document (multi-tenancy)
chunk_id             # Sequential chunk number
page_number          # Source page (for PDFs)
modality_type        # "text", "image", "video", "audio"
timestamp            # Temporal position (for video/audio)
content_hash         # MD5 of content for deduplication
confidence_score     # OCR/ASR confidence
created_at           # Indexing timestamp
updated_at           # Last update timestamp

# Example Qdrant payload
payload = {
    "document_id": "doc_123abc",
    "user_id": "user_456def",
    "chunk_id": 5,
    "page_number": 12,
    "modality_type": "text",
    "confidence_score": 0.95,
    "created_at": "2026-05-14T10:30:00Z"
}
```

---

## 4. File & Module Naming

### 4.1 Python Module Naming

**Pattern**: `snake_case.py`, organized by function

**Examples**:
```
# ✅ Correct naming
document_processor.py     # Main processor class
media_processor_enhanced.py  # Enhanced variant
rag_retrievers.py        # Retriever implementations
search_orchestrator.py    # Orchestration logic
evaluation/
  metrics.py             # Metric calculations
  benchmark.py           # Benchmarking framework
processor/
  document_processor.py   # Document processing
  media_processor_enhanced.py  # Media processing
retrieval/
  rag_retrievers.py      # Retriever implementations

# ❌ Avoid
DocumentProcessor.py     # CapWords for module (confusing with class)
doc_proc.py              # Abbreviated
processor_2.py           # Numbered versions
PROCESSOR.py             # All caps
```

**Organizational Pattern**:
```
backend/
  src/
    processor/           # Document & media processing
      document_processor.py
      media_processor_enhanced.py
    retrieval/          # Retrieval strategies
      rag_retrievers.py
      retrieval_orchestrator.py
    evaluation/         # Metrics & benchmarking
      metrics.py
      benchmark.py
    utils/              # Utilities
      phash.py          # Perceptual hashing
      xlsx_reader_v2.py # Excel parsing
  app/
    api/
      routes/           # API endpoints
        search_routes.py
        documents_routes.py
    services/           # Business logic
      search_orchestrator.py
      generation_service.py
```

---

### 4.2 Data Files & Exports

**Pattern**: `{type}_{scope}_{timestamp}.{ext}` or `{feature}_{version}.{ext}`

**Examples**:
```
# Benchmark/evaluation exports
benchmark_results_2026_05_14.json    # Date-stamped results
evaluation_metrics_v2.json           # Version-stamped metrics
retrieval_comparison_baseline.csv    # Feature-focused name

# Model exports
embedding_model_v3.pt                # Model checkpoint with version
ocr_config_tesseract_v2.json         # Config with engine & version

# Configuration files
processing_config_default.yaml
retrieval_config_hybrid.yaml
generation_config_gpt4.yaml

# Logs
application_error_2026_05_14.log
indexing_progress_20260514_103045.log
search_latency_profile_2026_05_14.txt
```

---

## 5. API Endpoint Naming

### 5.1 REST API Routes

**Pattern**: `/api/{resource}/{action}` or `/api/{resource}/{id}/{action}`

**Examples** (from search_routes.py):
```python
# ✅ Correct REST patterns
POST /api/search                 # Create search session/request
POST /api/documents/upload       # Upload document
GET /api/documents/{id}          # Get document details
DELETE /api/documents/{id}       # Delete document
GET /api/search/history          # Get search history
POST /api/collections/create     # Create collection
GET /api/health                  # Health check
GET /api/metrics                 # System metrics

# Method patterns
GET    /api/{resource}           # List/retrieve
POST   /api/{resource}           # Create
GET    /api/{resource}/{id}      # Get by ID
PUT    /api/{resource}/{id}      # Full update
PATCH  /api/{resource}/{id}      # Partial update
DELETE /api/{resource}/{id}      # Delete

# ❌ Avoid
GET /api/searchDocuments         # Verb + noun (should be noun only)
GET /api/search_documents        # snake_case in URL (use kebab-case)
POST /api/newDocument            # "new" prefix (POST implies create)
GET /api/Document/Search         # Capitals in URL
```

---

### 5.2 Query Parameters

**Pattern**: `snake_case` for parameters (matching Python convention)

**Examples**:
```python
# ✅ Correct
GET /api/search?query=test&top_k=10&retriever_type=hybrid
GET /api/documents?user_id=123&page=1&limit=20
POST /api/search with body: {
    "query": "test",
    "top_k": 10,
    "retriever_type": "hybrid",
    "include_images": true
}

# ❌ Avoid
GET /api/search?query=test&topK=10&retrieverType=hybrid  # camelCase
GET /api/search?query=test&TOP_K=10&RETRIEVER_TYPE=hybrid  # UPPER_CASE
GET /api/search?query=test&top_k=10&retriever-type=hybrid  # Mixed separators
```

---

### 5.3 Request/Response Field Names

**Pattern**: `snake_case` in JSON, matching Python field names

**Examples**:
```python
# ✅ Correct
SearchRequest = {
    "query": "test",
    "top_k": 10,
    "retriever_type": "hybrid",
    "search_scope": "text",
    "include_images": true
}

SearchResponse = {
    "text_results": [...],
    "image_results": [...],
    "generation_result": "...",
    "query_time_ms": 150,
    "total_documents": 1000
}

# ❌ Avoid (mixing conventions)
{
    "query": "test",        # snake_case
    "topK": 10,            # camelCase (inconsistent!)
    "retrieverType": "hybrid",  # camelCase
    "search_scope": "text"  # snake_case (back to consistent)
}
```

---

## 6. Variable Naming in Specific Contexts

### 6.1 Loop Variables & Iteration

**Pattern**: Spell out unless single-letter mathematical

```python
# ✅ Correct
for chunk in chunks:
    process(chunk)

for idx, result in enumerate(results):
    print(f"{idx}: {result}")

for query_id, qrels in query_relevance.items():
    compute_metrics(query_id, qrels)

# ❌ Avoid (too short outside math context)
for c in chunks:  # 'c' unclear
    process(c)

for i, r in enumerate(results):  # Both unclear
    print(f"{i}: {r}")

# Mathematical context (OK)
for i in range(n):  # Index iteration, clear
    matrix[i][j] = value
```

---

### 6.2 Score/Ranking Variables

**Pattern**: `{metric}_{context}` or `{source}_{metric}`

**Examples**:
```python
# ✅ Correct
bm25_score = 0.456
dense_score = 0.892
rrf_score = 0.675  # Fused score

relevance_score = 0.9
confidence_score = 0.95  # OCR confidence
similarity_score = 0.88

# From different sources
retriever1_score = result1.score
retriever2_score = result2.score
fused_score = (retriever1_score + retriever2_score) / 2

# ❌ Avoid
score = 0.456  # Which metric? Which retriever?
s1, s2 = 0.456, 0.892  # Cryptic names
bm25 = 0.456  # Naming noun when should be adjective
score1, score2 = 0.456, 0.892  # Numbered (unclear difference)
```

---

### 6.3 Temporal Variables

**Pattern**: Include time unit in name

**Examples**:
```python
# ✅ Correct
timeout_seconds = 30
latency_ms = 150  # Milliseconds
cache_ttl_seconds = 86400  # 24 hours in seconds
timestamp_utc = datetime.now(tz=UTC)
created_at = "2026-05-14T10:30:00Z"

# ❌ Avoid
timeout = 30  # What unit? Seconds? Milliseconds?
latency = 150  # Unclear unit
cache_ttl = 86400  # Is this seconds? Minutes?
timestamp = "2026-05-14T10:30:00Z"  # Missing timezone
created = "2026-05-14T10:30:00Z"  # Incomplete name
```

---

### 6.4 Collection/Container Variables

**Pattern**: Plural for containers, singular for elements

**Examples**:
```python
# ✅ Correct
chunks = [Chunk(...), Chunk(...)]  # Container, plural
documents = [...]  # List
results_by_query = {}  # Dict

for chunk in chunks:  # Singular when iterating
    process_chunk(chunk)

chunk_index = {}  # Index mapping
user_ids = set()  # Set of IDs

# ❌ Avoid
chunk = [Chunk(...), Chunk(...)]  # Singular for plural container
doc = [...]  # Singular for list
result = {}  # Singular for dict (should be results)
```

---

## 7. Import & Module Alias Naming

**Pattern**: Descriptive aliases, avoid single letters except standard conventions

**Examples**:
```python
# ✅ Correct
from torch import nn
from torch import optim
import numpy as np  # Standard convention
import pandas as pd  # Standard convention
import matplotlib.pyplot as plt  # Standard convention
from typing import List, Dict, Optional
from document_processor import DocumentProcessor
from rag_retrievers import SimpleHybridRetriever

# ❌ Avoid
import torch as t  # Too abbreviated
import transformers as tf  # Conflicts with TensorFlow
import numpy as n  # Non-standard (should be np)
from document_processor import DocumentProcessor as DP  # Unnecessary alias
from utils import *  # Wildcard import (pollutes namespace)
```

---

## 8. Test Naming

**Pattern**: `test_{function_name}_{scenario}` or `test_{scenario}_{function_name}`

**Examples**:
```python
# ✅ Correct
def test_retrieve_chunks_with_empty_query():
    """Should return empty results for empty query"""
    pass

def test_calculate_ndcg_with_perfect_ranking():
    """Should return 1.0 for perfect ranking"""
    pass

def test_process_document_with_corrupted_pdf():
    """Should handle corrupted PDFs gracefully"""
    pass

def test_search_with_concurrent_requests():
    """Should handle concurrent requests without race conditions"""
    pass

# ❌ Avoid
def test_retrieve():  # Unclear what scenario
    pass

def test_calc_ndcg():  # Abbreviated function name
    pass

def test1_process_doc():  # Numbered (what's the difference from test2?)
    pass

def test_search_works():  # Vague "works" (all tests should work)
    pass
```

---

## 9. Documentation & Comments

**Pattern**: Inline comments use `#`, docstrings use `"""` for modules/classes/functions

**Examples**:
```python
# ✅ Correct - Module docstring
"""Retrieval Evaluation Metrics for RAG Pipeline Assessment.

Standard information retrieval metrics for quantifying retrieval quality...
"""

class DocumentProcessor:
    """Main document processing pipeline with 7-stage workflow.
    
    Coordinates text extraction, media processing, OCR, and chunking
    for multimodal documents (PDF, DOCX, Excel, video, audio).
    """
    
    def process_document(self, file_path: str) -> ProcessingResult:
        """Process a single document through the 7-stage pipeline.
        
        Args:
            file_path: Path to document file (PDF, DOCX, XLSX, PPTX, etc.)
            
        Returns:
            ProcessingResult with chunks, metadata, and extraction details
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If document format unsupported
        """
        # Stage 1: Normalize document
        normalized = self._normalize_document(file_path)  # Inline comment only if non-obvious
        
        # ❌ Avoid
        def process_document(self, file_path):  # No docstring
            # Do processing  # Vague comment
            return result
```

---

## 10. Enum & Constant Naming

**Pattern**: `UPPER_SNAKE_CASE` for constants, descriptive enum names

**Examples**:
```python
# ✅ Correct
from enum import Enum

# Module constants
DEFAULT_CHUNK_SIZE = 512
MAX_DOCUMENT_SIZE = 500  # pages
SUPPORTED_FORMATS = ["pdf", "docx", "xlsx", "pptx"]
CACHE_TTL_SECONDS = 86400
GPU_MEMORY_MIN_GB = 2
RRF_CONSTANT = 60

# Enums
class RetrieverType(str, Enum):
    BM25 = "bm25"
    DENSE = "dense"
    HYBRID = "hybrid"

class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"

# Usage
retriever = get_retriever(RetrieverType.HYBRID)
for modality in Modality:
    process(modality)

# ❌ Avoid
DEFAULT_chunk_size = 512  # Mixed case constant
default_chunk_size = 512  # lowercase (looks like variable)
MaxDocumentSize = 500     # PascalCase for constant
SupportedFormats = [...]  # PascalCase for constant
```

---

## Summary Table

| Context | Pattern | Example |
|---------|---------|---------|
| Variables | `snake_case` | `document_id`, `chunk_size` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_TOP_K`, `CACHE_TTL_SECONDS` |
| Functions | `snake_case`, verb-first | `process_document()`, `retrieve_chunks()` |
| Classes | `PascalCase` | `DocumentProcessor`, `SimpleHybridRetriever` |
| Private vars | `_snake_case` | `_internal_cache` |
| Parameters | `snake_case` | `top_k`, `ocr_engine` |
| Collections | `{scope}_{entity}` | `text_chunks`, `user_documents` |
| Enum values | `UPPER_SNAKE_CASE` | `RetrieverType.HYBRID` |
| Files | `snake_case.py` | `document_processor.py` |
| API routes | `/api/{resource}/{action}` | `POST /api/search` |
| Query params | `snake_case` | `?top_k=10&user_id=123` |
| Tests | `test_{function}_{scenario}` | `test_retrieve_with_empty_query()` |

---

**Generated**: May 14, 2026  
**Scope**: Code naming conventions and patterns  
**Status**: Complete B3 documentation  
**Next**: Spawn subagents to validate Phase 3 work

