# Configuration Reference

This document provides a comprehensive reference for all configuration options in the Unified RAG Pipeline.

## Configuration Methods

The pipeline supports three ways to configure settings (in order of priority, highest first):

1. **CLI Arguments** - Override config file and defaults
2. **YAML Config File** - `config/default.yaml` or custom file via `--config`
3. **Default Values** - Built-in defaults

## Quick Start

```bash
# Use default config
python run_pipeline.py --input input/ --output output/ --mode full

# Use custom config file
python run_pipeline.py --input input/ --output output/ --config config/custom.yaml

# Override specific options via CLI
python run_pipeline.py --input input/ --output output/ --rag-mode both --colqwen-quantization 4bit
```

---

## Pipeline Settings

| Option | CLI Argument | Config Key | Default | Choices | Description |
|--------|--------------|------------|---------|---------|-------------|
| Mode | `--mode` | `pipeline.mode` | `full` | `processing`, `retrieval`, `full`, `test` | Pipeline execution mode |
| RAG Mode | `--rag-mode` | `pipeline.rag_mode` | `text` | `text`, `image`, `both` | Which RAG pipelines to use |
| Config File | `--config`, `-c` | - | `config/default.yaml` | Any YAML file | Custom configuration file |

### Mode Options

- `processing`: Only process documents (normalize, extract text)
- `retrieval`: Only setup retrieval (assumes documents already processed)
- `full`: Complete pipeline (processing + retrieval)
- `test`: Interactive testing mode (requires existing index)

### RAG Mode Options

- `text`: Text-based retrieval only (BM25 + Dense + Hybrid)
- `image`: Image-based retrieval only (ColQwen)
- `both`: Combined text + image retrieval

---

## Text Retrieval Configuration

| Option | CLI Argument | Config Key | Default | Choices | Description |
|--------|--------------|------------|---------|---------|-------------|
| Retrievers | `--retrievers` | `text_retrieval.methods` | `["bm25", "dense", "hybrid"]` | `bm25`, `dense`, `hybrid` | Retrieval methods to use |
| Top-K | `--top-k` | `text_retrieval.top_k` | `10` | 1-100 | Number of chunks to retrieve |
| Embedding Model | - | `text_retrieval.embedding_model` | `all-MiniLM-L6-v2` | HuggingFace model | Dense embedding model |

### Chunking Configuration

| Option | CLI Argument | Config Key | Default | Description |
|--------|--------------|------------|---------|-------------|
| Chunk Size | `--chunk-size` | `text_retrieval.chunking.chunk_size` | `1000` | Characters per chunk |
| Chunk Overlap | `--chunk-overlap` | `text_retrieval.chunking.chunk_overlap` | `200` | Overlap between chunks |
| Disable Chunking | `--no-chunking` | `text_retrieval.chunking.enabled` | `false` | Use full documents |
| Min Chunk Size | - | `text_retrieval.chunking.min_chunk_size` | `50` | Skip chunks smaller than this |

### Reranker Configuration

| Option | CLI Argument | Config Key | Default | Choices | Description |
|--------|--------------|------------|---------|---------|-------------|
| Reranker | `--reranker` | `text_retrieval.reranker.model` | `none` | `none`, `bge-large`, `bge-base`, `minilm-l12` | Reranker model |

**Reranker Models:**
- `bge-large`: `BAAI/bge-reranker-large` - Best quality, slower (~560MB)
- `bge-base`: `BAAI/bge-reranker-base` - Balanced (~280MB)
- `minilm-l12`: `cross-encoder/ms-marco-MiniLM-L-12-v2` - Fastest (~130MB)

---

## Image Retrieval Configuration (ColQwen)

| Option | CLI Argument | Config Key | Default | Choices | Description |
|--------|--------------|------------|---------|---------|-------------|
| Enable | `--image-retrieval` | `image_retrieval.enabled` | `false` | - | Enable image retrieval |
| Top-K | `--image-top-k` | `image_retrieval.top_k` | `5` | 1-50 | Number of pages to retrieve |
| Model | `--colqwen-model` | `image_retrieval.colqwen.model` | `vidore/colqwen2-v1.0` | See below | ColQwen model |
| Data Type | `--colqwen-dtype` | `image_retrieval.colqwen.dtype` | `bfloat16` | `bfloat16`, `float16`, `float32` | Model weight precision |
| Quantization | `--colqwen-quantization` | `image_retrieval.colqwen.quantization` | `none` | `none`, `4bit`, `8bit` | Model quantization |
| PDF DPI | `--pdf-dpi` | `image_retrieval.colqwen.pdf_dpi` | `150` | 72-300 | PDF conversion quality |

### ColQwen Model Options

| Model | colpali-engine Version | Size | Description |
|-------|------------------------|------|-------------|
| `vidore/colqwen2-v1.0` | Any | ~3.5GB | ColQwen 2 (default, most compatible) |
| `vidore/colqwen2.5-v0.2` | >=0.4.0 | ~3.8GB | ColQwen 2.5 (newer, requires updated library) |

### Quantization Options

Quantization reduces memory usage and can speed up inference:

| Option | VRAM Usage | Speed | Quality | Requirements |
|--------|------------|-------|---------|--------------|
| `none` | ~7GB | Baseline | Best | None |
| `8bit` | ~4GB | Similar | Good | `bitsandbytes` |
| `4bit` | ~2.5GB | Slower | Acceptable | `bitsandbytes` |

**Install bitsandbytes for quantization:**
```bash
pip install bitsandbytes
```

### PDF DPI Options

| DPI | Quality | Speed | Memory | Use Case |
|-----|---------|-------|--------|----------|
| 72 | Low | Fast | Low | Quick testing |
| 150 | Good | Medium | Medium | **Default (recommended)** |
| 200 | High | Slow | High | High-quality OCR |
| 300 | Best | Very Slow | Very High | Archival quality |

---

## Generation Configuration (LLM)

| Option | CLI Argument | Config Key | Default | Choices | Description |
|--------|--------------|------------|---------|---------|-------------|
| Disable | `--no-generation` | `generation.enabled` | `true` | - | Disable answer generation |
| Provider | `--llm-provider` | `generation.provider` | `openai` | `openai`, `azure`, `ollama` | LLM provider |
| Model | `--llm-model` | `generation.model` | `gpt-4o-mini` | Any supported model | LLM model name |
| API Key | `--api-key` | `generation.api_key` | `$OPENAI_API_KEY` | - | API key (or use env var) |
| Temperature | - | `generation.temperature` | `0.0` | 0.0-2.0 | Response creativity |
| Max Tokens | - | `generation.max_tokens` | `2000` | 1-4096 | Maximum response length |

---

## Logging Configuration

| Option | CLI Argument | Config Key | Default | Choices | Description |
|--------|--------------|------------|---------|---------|-------------|
| Level | `--log-level` | `logging.level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Log verbosity |
| Disable File | `--no-log-file` | `logging.to_file` | `true` | - | Disable logging to file |
| Log Directory | - | `logging.log_dir` | `output/logs` | Any path | Log file location |

---

## Example Configurations

### High-Quality Processing (Slow but Accurate)

```yaml
# config/high_quality.yaml
pipeline:
  rag_mode: "both"

text_retrieval:
  top_k: 15
  reranker:
    enabled: true
    model: "bge-large"

image_retrieval:
  enabled: true
  top_k: 10
  colqwen:
    model: "vidore/colqwen2-v1.0"
    dtype: "float32"
    pdf_dpi: 200
```

### Fast Processing (Lower Quality, Less Memory)

```yaml
# config/fast.yaml
pipeline:
  rag_mode: "text"

text_retrieval:
  methods: ["bm25", "hybrid"]
  top_k: 5
  chunking:
    chunk_size: 500
    chunk_overlap: 100

image_retrieval:
  enabled: false
```

### Low Memory / Quantized

```yaml
# config/low_memory.yaml
pipeline:
  rag_mode: "both"

text_retrieval:
  top_k: 5

image_retrieval:
  enabled: true
  top_k: 3
  colqwen:
    model: "vidore/colqwen2-v1.0"
    quantization: "4bit"
    pdf_dpi: 100
```

---

## CLI Quick Reference

```bash
# Basic usage
python run_pipeline.py -i input/ -o output/ --mode full

# Text-only RAG with reranker
python run_pipeline.py -i input/ -o output/ --rag-mode text --reranker bge-large

# Image-only RAG
python run_pipeline.py -i input/ -o output/ --rag-mode image --image-retrieval --image-top-k 10

# Combined with 4-bit quantization
python run_pipeline.py -i input/ -o output/ --rag-mode both --image-retrieval --colqwen-quantization 4bit

# Interactive testing
python run_pipeline.py -i output/processing/stage4_rag_ready/ -o output/ --mode test --rag-mode both --interactive

# Using custom config
python run_pipeline.py -i input/ -o output/ --config config/high_quality.yaml
```



