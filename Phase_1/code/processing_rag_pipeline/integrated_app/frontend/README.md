# RAG Pipeline Demo

A simple web UI for the Multimodal RAG Pipeline.

## Architecture

- **Frontend**: React + Tailwind CSS (Vite)
- **Backend**: FastAPI (Python)
- **Pipeline**: Unified RAG Pipeline with text + image retrieval

## Quick Start

### 1. Install API Dependencies

```bash
cd api
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 3. Start the Backend (API)

```bash
cd api
python main.py
# This will start with auto-reload enabled, watching api/, src/, and config/ directories

# Or with uvicorn directly for more control:
cd ..
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 --reload-dir api --reload-dir src --reload-dir config
```

### 4. Start the Frontend

```bash
cd frontend
npm run dev
```

### 5. Open in Browser

Navigate to: http://localhost:3000

## Features

### Upload Files
- Drag & drop or click to upload
- Supports PDF, DOCX, PPTX, TXT, MD, images
- View uploaded files list

### View Processed Files
- See normalized/processed documents
- Preview file contents
- Track processing stages

### View Indexed Files
- See indexed document statistics
- Text index: chunks, documents, retrievers
- Image index: pages, PDFs (ColQwen)

### Search & Query
- Natural language queries
- View text chunk results with scores
- View image page results with scores
- Retrieval info (BM25 rank, Dense rank)
- Expandable result details
- Generated answers from LLM

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Get pipeline status |
| `/api/files` | GET | List all files |
| `/api/upload` | POST | Upload files |
| `/api/files` | DELETE | Delete a file |
| `/api/process` | POST | Process documents |
| `/api/index` | POST | Build/rebuild index |
| `/api/search` | POST | Search documents |
| `/api/health` | GET | Health check |

## Configuration

The API uses `config/default.yaml` for pipeline settings including:
- ColQwen model and quantization
- Retrieval methods (BM25, Dense, Hybrid)
- LLM provider and model
- Processing options
