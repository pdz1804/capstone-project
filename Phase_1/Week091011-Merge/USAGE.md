# Unified RAG Pipeline - Usage Guide

## Command Line Interface

### Main Entry Point
```bash
python run_pipeline.py [OPTIONS]
```

### Required Arguments
- `--input`, `-i`: Input directory containing documents
- `--output`, `-o`: Output directory for processed results

### Pipeline Modes
- `--mode`: Choose pipeline mode
  - `processing`: Document processing only
  - `retrieval`: Retrieval setup only  
  - `full`: Complete pipeline (default)
  - `test`: Test/demo mode for querying processed documents

### RAG Mode Options
- `--rag-mode`: Choose RAG retrieval mode
  - `text`: Text-based retrieval only (default)
  - `image`: Image-based retrieval only (ColQwen)
  - `both`: Combined text + image retrieval

### Reranker Options
- `--reranker`: Choose reranker model
  - `none`: No reranking (default, fastest)
  - `bge-large`: BGE-Large Reranker (best quality)
  - `minilm-l12`: MiniLM Cross-Encoder (balanced)
  - `bge-base`: BGE-Base Reranker (faster)

### Processing Options
- `--skip-normalization`: Skip document normalization step
- `--skip-media`: Skip video/audio processing
- `--fast-mode`: Disable VLM for faster processing (3-5x speedup)
- `--no-gpu`: Force CPU-only processing

### Retrieval Options
- `--retrievers`: Choose retrieval methods (default: bm25 dense hybrid)
  - Available: `bm25`, `dense`, `hybrid`
- `--top-k`: Number of text chunks to retrieve per query (default: 10)
- `--image-retrieval`: Enable image-based retrieval (ColQwen)
- `--image-top-k`: Number of image pages to retrieve per query (default: 5)
- `--evaluate`: Enable retrieval evaluation
- `--queries`: Path to queries file for evaluation (JSON/JSONL format)

### ColQwen (Image Retrieval) Options
- `--colqwen-model`: ColQwen model to use
  - `vidore/colqwen2-v1.0`: ColQwen 2 (default, most compatible)
  - `vidore/colqwen2.5-v0.2`: ColQwen 2.5 (requires newer colpali-engine)
- `--colqwen-quantization`: Model quantization (requires bitsandbytes)
  - `none`: No quantization (default, ~7GB VRAM)
  - `4bit`: 4-bit quantization (~2.5GB VRAM)
  - `8bit`: 8-bit quantization (~4GB VRAM)
- `--colqwen-dtype`: Data type for model weights
  - `bfloat16`: BFloat16 (default, best for CUDA)
  - `float16`: Float16
  - `float32`: Float32 (more precise, slower)
- `--pdf-dpi`: DPI for PDF to image conversion (default: 150)

### Configuration File
- `--config`, `-c`: Path to YAML configuration file (see `config/default.yaml`)

### Chunking Options
- `--chunk-size`: Chunk size in characters (default: 1000)
- `--chunk-overlap`: Overlap between chunks in characters (default: 200)
- `--no-chunking`: Disable document chunking (use full documents)

### Generation Options
- `--no-generation`: Disable answer generation (retrieval only)
- `--llm-provider`: LLM provider for answer generation (`openai`, `azure`, `ollama`)
- `--llm-model`: LLM model name (default: gpt-4o-mini)
- `--api-key`: API key for LLM provider (or use OPENAI_API_KEY env var)

### Logging Options
- `--log-level`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) (default: INFO)
- `--no-log-file`: Disable logging to file

### Test Mode Options
- `--test-query`: Single query for testing (use with --mode test)
- `--interactive`: Interactive testing mode (use with --mode test)

## Usage Examples

### 1. Basic Usage
```bash
# Complete pipeline with default settings
python run_pipeline.py --input input/ --output output/
```

### 2. Text-based RAG with Reranking
```bash
# Use hybrid retrieval with BGE-Large reranker
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode test \
    --rag-mode text \
    --reranker bge-large \
    --top-k 10 \
    --test-query "What is machine learning?"
```

### 3. Image-based RAG (ColQwen)
```bash
# Use ColQwen for visual document retrieval
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode test \
    --rag-mode image \
    --image-retrieval \
    --image-top-k 5 \
    --test-query "What does the architecture diagram show?"
```

### 4. Image RAG with 4-bit Quantization (Low Memory)
```bash
# Use 4-bit quantization to reduce VRAM from ~7GB to ~2.5GB
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode retrieval \
    --rag-mode image \
    --image-retrieval \
    --colqwen-quantization 4bit \
    --pdf-dpi 100
```

### 5. Combined Text + Image RAG
```bash
# Use both text and image retrieval
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode test \
    --rag-mode both \
    --image-retrieval \
    --top-k 10 \
    --image-top-k 3 \
    --test-query "Explain the methodology"
```

### 6. Using Custom Config File
```bash
# Load settings from YAML config
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --config config/high_quality.yaml
```

### 5. Processing Only
```bash
# Just process documents (fast mode)
python run_pipeline.py --input input/ --output output/ --mode processing --fast-mode
```

### 6. Retrieval Only
```bash
# Setup retrieval on already processed documents
python run_pipeline.py --input output/processing/stage4_rag_ready/ --output output/ --mode retrieval
```

### 7. Custom Retrievers
```bash
# Use only dense and hybrid retrieval
python run_pipeline.py --input input/ --output output/ --retrievers dense hybrid
```

### 8. With Evaluation
```bash
# Run with evaluation using custom queries
python run_pipeline.py --input input/ --output output/ --evaluate --queries my_queries.json
```

### 9. Performance Optimized
```bash
# Fast processing, no GPU, specific retrievers
python run_pipeline.py --input input/ --output output/ --fast-mode --no-gpu --retrievers bm25 dense
```

### 10. Test Mode (Demo/Testing)
```bash
# Test with already processed documents (demo mode)
python run_pipeline.py --input output/processing/stage4_rag_ready/ --output output/ --mode test

# Test with a specific query
python run_pipeline.py --input output/processing/stage4_rag_ready/ --output output/ --mode test --test-query "What is machine learning?"

# Interactive testing mode
python run_pipeline.py --input output/processing/stage4_rag_ready/ --output output/ --mode test --interactive
```

### 11. Custom Chunking
```bash
# Smaller chunks for more precise retrieval
python run_pipeline.py --input input/ --output output/ --chunk-size 500 --chunk-overlap 100

# Larger chunks for more context
python run_pipeline.py --input input/ --output output/ --chunk-size 2000 --chunk-overlap 400

# Disable chunking (use full documents)
python run_pipeline.py --input input/ --output output/ --no-chunking
```

### 12. With Answer Generation
```bash
# Test mode with OpenAI generation
python run_pipeline.py --input input/ --output output/ --mode test --test-query "What is VideoRAG?" --llm-provider openai --llm-model gpt-4o-mini

# Use Ollama for local generation
python run_pipeline.py --input input/ --output output/ --mode test --test-query "Explain the architecture" --llm-provider ollama --llm-model llama2

# Retrieval only (no generation)
python run_pipeline.py --input input/ --output output/ --mode test --test-query "What is RAG?" --no-generation
```

### 13. Custom Top-K Retrieval
```bash
# Retrieve more chunks (20 instead of default 10)
python run_pipeline.py --input input/ --output output/ --mode test --test-query "Explain the method" --top-k 20

# Retrieve fewer chunks for faster response
python run_pipeline.py --input input/ --output output/ --mode test --test-query "What is it?" --top-k 5
```

### 14. Verbose Logging
```bash
# Enable debug logging
python run_pipeline.py --input input/ --output output/ --mode test --log-level DEBUG

# Disable file logging (console only)
python run_pipeline.py --input input/ --output output/ --mode test --no-log-file
```

### 15. Full Production Setup
```bash
# Complete pipeline with reranking, both RAG modes, and evaluation
python run_pipeline.py \
    --input input/ \
    --output output/ \
    --mode full \
    --rag-mode both \
    --reranker bge-large \
    --top-k 10 \
    --image-top-k 5 \
    --chunk-size 1000 \
    --chunk-overlap 200 \
    --log-level INFO
```

## Query File Format

For evaluation, provide queries in JSON or JSONL format:

**JSON format:**
```json
[
  {"id": "q1", "text": "What is machine learning?"},
  {"id": "q2", "text": "How do neural networks work?"}
]
```

**JSONL format:**
```jsonl
{"id": "q1", "text": "What is machine learning?"}
{"id": "q2", "text": "How do neural networks work?"}
```

## Qrels File Format (for benchmarking)

Relevance judgments in TSV format:
```
q1	0	doc1	1
q1	0	doc2	0
q2	0	doc3	1
```

Format: `query_id \t 0 \t doc_id \t relevance`

## Output Structure

```
output/
├── processing/
│   └── stage4_rag_ready/     # Final processed documents
├── retrieval/                # Text retrieval indices
│   ├── documents.json        # Chunked documents
│   ├── index_meta.json       # Index metadata (chunk config, etc.)
│   ├── bm25/                 # BM25 index
│   ├── dense/                # Dense embeddings + FAISS index
│   └── hybrid/               # Hybrid index components
├── image_retrieval/          # Image retrieval indices (ColQwen)
│   ├── image_index_meta.json
│   └── colqwen/
├── logs/                     # Pipeline logs
│   ├── rag_pipeline_*.log
│   ├── retrieval_*.log
│   └── generation_*.log
├── evaluation/               # Evaluation results (if enabled)
└── unified_rag_pipeline_stats.json
```

## Chunking Strategy

Documents are split into smaller chunks using **recursive character text splitting**:

1. **Default settings**: 1000 chars per chunk, 200 chars overlap
2. **Splitting hierarchy**: Paragraphs → Lines → Sentences → Words → Characters
3. **Preserves context**: Overlap ensures no information is lost at boundaries

### Recommended Chunk Sizes

| Use Case | Chunk Size | Overlap | Notes |
|----------|------------|---------|-------|
| Precise Q&A | 500 | 100 | More specific retrieval |
| General RAG | 1000 | 200 | **Default**, balanced |
| Long context | 2000 | 400 | More context per chunk |
| Full docs | N/A | N/A | Use `--no-chunking` |

## RAG Modes Explained

### Text Mode (`--rag-mode text`)
- Uses BM25, Dense, and/or Hybrid retrieval
- Retrieves text chunks from markdown files
- Best for text-heavy documents and general Q&A

### Image Mode (`--rag-mode image`)
- Uses ColQwen 2.5 vision-language model
- Retrieves PDF pages as images
- Best for visual documents, diagrams, charts

### Combined Mode (`--rag-mode both`)
- Uses both text and image retrieval
- Sends both text chunks and images to LLM
- Best coverage for mixed documents

## Reranking Explained

When using `--reranker`:
1. Initial retrieval fetches `top_k * 3` candidates
2. Cross-encoder reranker scores all candidates
3. Final `top_k` results returned after reranking

**Available rerankers:**
| Model | Speed | Quality | Use Case |
|-------|-------|---------|----------|
| `none` | Fastest | Baseline | Development, quick testing |
| `bge-base` | Fast | Good | Production with speed constraints |
| `minilm-l12` | Medium | Better | Balanced quality/speed |
| `bge-large` | Slower | Best | Maximum retrieval quality |

## Hybrid Retrieval

When using `hybrid` retrieval:
- **Expansion factor**: 130% of requested top-k
- If you request 10 chunks, BM25 and Dense each retrieve 13 candidates
- Results are fused using **Reciprocal Rank Fusion (RRF)**
- Final output: top-k results with best combined ranking

## Logging

Pipeline creates separate log files for different operations:

| Log File | Contents |
|----------|----------|
| `rag_pipeline_*.log` | Main pipeline operations |
| `retrieval_*.log` | Retrieval queries and results |
| `generation_*.log` | LLM generation requests and responses |

Logs are stored in `output/logs/` directory.

## Performance Tips

1. **Fast Development**: Use `--fast-mode` for 3-5x speedup
2. **GPU Acceleration**: Ensure CUDA is available for best performance
3. **Memory**: Dense retrieval requires more RAM for large document sets
4. **Reranking**: Adds latency but improves quality significantly
5. **Image RAG**: GPU strongly recommended for ColQwen
6. **Chunking**: Smaller chunks = more precise retrieval, larger chunks = more context
7. **Top-K**: Start with 10, increase if answers lack context

## Troubleshooting

### Common Issues
1. **Import Errors**: Make sure you're using `run_pipeline.py`, not the src file directly
2. **GPU Issues**: Use `--no-gpu` if CUDA is not available
3. **Memory Issues**: Use `--fast-mode` or process smaller batches
4. **Missing Dependencies**: Run `python setup.py` to check system dependencies
5. **Poor Retrieval**: Try adjusting `--chunk-size`, `--top-k`, or enable `--reranker`
6. **Generation Fails**: Check API key with `--api-key` or `OPENAI_API_KEY` env var
7. **ColQwen Errors**: Ensure `colpali-engine` and `pdf2image` are installed
8. **Slow Image RAG**: ColQwen requires GPU; CPU mode is very slow

### Getting Help
```bash
python run_pipeline.py --help
```

## Python API Quick Reference

```python
from src import UnifiedRAGPipeline, UnifiedRAGConfig

# Configure
config = UnifiedRAGConfig(
    rag_mode="both",                    # text, image, or both
    enable_reranker=True,
    reranker_model="bge-large",
    retrieval_top_k=10,
    image_retrieval_top_k=5,
    chunk_size=1000,
    chunk_overlap=200
)

# Initialize
pipeline = UnifiedRAGPipeline("input/", "output/", config)

# Setup (one-time)
pipeline.setup_retrievers()
pipeline.setup_image_retrievers()

# Query
result = pipeline.query(
    "What is the main topic?",
    retriever_type="hybrid",
    rag_mode="both",
    use_reranker=True
)

# Access results
print(result["text_docs"])      # Text retrieval results
print(result["image_docs"])     # Image retrieval results
print(result["answer"])         # Generated answer
```
