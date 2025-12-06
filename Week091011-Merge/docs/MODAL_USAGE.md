# Modal GPU Usage Guide

Simple guide to run the ColPali retriever on Modal's GPU.

## Setup (One-time)

### 1. Install Modal
```bash
pip install modal
modal setup  # Follow the browser authentication
```

### 2. Create OpenAI Secret
```bash
modal secret create openai-secret OPENAI_API_KEY=your_api_key_here
```

### 3. Upload PDFs to Modal Volume
```bash
# Upload your PDFs to the Modal volume
modal volume put colpali-pdfs /local/path/to/your/pdfs /data/pdfs
```

For example:
```bash
modal volume put colpali-pdfs ./data/pdfs /data/pdfs
```

### 4. Build Indexes (First Time)
```bash
modal run colpali_modal.py --build
```

This will:
- Run OCR on all PDFs using GPU
- Build BM25, ColQwen, and MiniLM indexes
- Save everything to the Modal volume

## Running Queries

### Basic Query
```bash
modal run colpali_modal.py --query "What is the A* algorithm?"
```

### With More Results
```bash
modal run colpali_modal.py --query "What is the A* algorithm?" --top-k 10
```

### Rebuild Indexes
```bash
modal run colpali_modal.py --build --force-rebuild
```

## Example Output

```
🔍 Running query on GPU: What is the A* algorithm?

================================================================================
QUERY: What is the A* algorithm?
================================================================================

================================================================================
PIPELINE_A_BM25
================================================================================

🔍 Retrieved Contexts:
  1. Source: lecture_notes.pdf, Page: 42, Score: 15.2341
  2. Source: lecture_notes.pdf, Page: 43, Score: 12.5678
  ...

🤖 LLM Summary:
  A* is a pathfinding algorithm that combines the benefits of Dijkstra's 
  algorithm and greedy best-first search...

================================================================================
PIPELINE_B_COLQWEN
================================================================================
...
```

## Checking Your Volumes

### List volumes
```bash
modal volume ls
```

### Check what's in your PDF volume
```bash
modal volume ls colpali-pdfs /data/pdfs
```

### Check what's in your index volume
```bash
modal volume ls colpali-indexes /data/indexes
```

## Troubleshooting

### No PDFs found
Make sure you uploaded PDFs first:
```bash
modal volume put colpali-pdfs /path/to/pdfs /data/pdfs
```

### Indexes not found
Run the build command:
```bash
modal run colpali_modal.py --build
```

### Out of memory
The script uses A10G GPU (24GB VRAM). If you still run out of memory, you can:
- Process fewer PDFs at once
- Reduce batch sizes in the code

## Cost Notes

- Modal charges for GPU time
- A10G GPU costs ~$1.10/hour
- Building indexes might take 10-30 minutes depending on PDF count
- Queries are usually fast (1-2 minutes)
- Volumes are free for storage

## Tips

1. **Build once, query many times** - Indexes are persisted in volumes
2. **Upload PDFs in batches** - If you have many PDFs, upload them in groups
3. **Check logs** - Modal shows detailed logs of what's happening
