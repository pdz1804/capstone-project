# Excel RAG Pipeline Quickstart Guide

This guide covers how to test and run the Excel parsing, chunking, and RAG pipeline.

---

## 🧪 Testing Commands Summary

### 1. Chunking Only (no LLM, no API key needed)
Use this to verify the table-aware chunking logic separately.
```bash
cd Phase_2/backend/test_parsing
python3 run_excel_chunking.py --json output/excel/courseware.json --chunk-only -q
```

### 2. E2E Script (chunk → retrieve → LLM answer)
Runs a single query through the full pipeline using the local test providers.
```bash
cd Phase_2/backend/test_parsing
python3 run_excel_e2e.py --json output/excel/courseware.json \
    --query "Giải tích 1 do ai dạy?" \
    --use-local-llm
```

### 3. Automated Tests (mock / full / e2e)
Comprehensive test suite powered by `pytest`.
```bash
cd Phase_2/backend/test_parsing

# Mock Tests (no files, no LLM) — fast verification of logic
python3 -m pytest test_excel_pipeline.py -m mock -v

# Full Tests (real files, no LLM) — verifies chunking on actual data
python3 -m pytest test_excel_pipeline.py -m full -v

# E2E Tests (real files + real LLM call — needs OPENAI_API_KEY in .env)
python3 -m pytest test_excel_pipeline.py -m e2e -v
```

---

## 🚀 Running the Full Stack (Frontend + Backend)

### Terminal 1 — Backend (FastAPI)

```bash
cd Phase_2/backend

# 1. Create .env with your OpenAI key
echo 'OPENAI_API_KEY="sk-..."' > .env

# 2. Start the API server
cd api
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
The backend serves at **`http://localhost:8000`**. Swagger docs available at `http://localhost:8000/docs`.

### Terminal 2 — Frontend (Vite + React)

```bash
cd Phase_2/frontend

# 1. Install dependencies (first time only)
npm install

# 2. Create .env
echo 'VITE_API_URL="http://localhost:8000"' > .env

# 3. Start development server
npm run dev
```
The frontend serves at **`http://localhost:3000`** and automatically proxies `/api/*` requests to the backend.

---

## 📋 Testing Excel Parsing via the Web UI

Once both servers are running, follow these steps in the browser:

| Step | Action | Pipeline Effect |
|------|--------|-----------------|
| **1. Upload** | Drag your `.xlsx` file into the UI | File is saved to `backend/input/` |
| **2. Process** | Click "Process" | Runs `ExcelPreprocessor` → `ExcelTableChunker` → output saved to `backend/output/processing/` |
| **3. Index** | Click "Index" | BM25 + Dense indexes are built in `backend/output/retrieval/` |
| **4. Query** | Type a question and hit Search | Retrieves chunks → LLM generates answer → displays with `[X.Y]` citations |

### Manual Testing via cURL
If you prefer testing the API directly:

```bash
# Upload an Excel file
curl -X POST http://localhost:8000/api/upload \
  -F "files=@/path/to/your/file.xlsx"

# Process documents
curl -X POST "http://localhost:8000/api/process"

# Build retrieval index
curl -X POST "http://localhost:8000/api/index"

# Query the RAG system
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Giải tích 1 do ai dạy?", "top_k": 5}'
```
