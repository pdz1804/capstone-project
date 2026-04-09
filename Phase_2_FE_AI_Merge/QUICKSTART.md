# Phase_2_FE_AI_Merge — Quick Start Guide

> **Status**: ✅ READY TO RUN  
> All backend routes from Phase_2_AI_SERVICE_FOLDER + Firebase auth from Phase_2_FE_IMPLEMENT merged successfully  
> TypeScript ✅ | Python ✅ | Syntax checks ✅

---

## One-Minute Setup

### 1. Backend (Terminal 1)

```bash
cd Phase_2_FE_AI_Merge/backend

# Activate venv (Windows)
.venv\Scripts\activate

# Start API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

✅ **Backend ready**: http://localhost:8000/docs (Swagger UI)

### 2. Frontend (Terminal 2)

```bash
cd Phase_2_FE_AI_Merge/frontend

# Start dev server
npm run dev
```

✅ **Frontend ready**: http://localhost:5173

### 3. Qdrant (Terminal 3, optional if using Docker mode)

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```

✅ **Qdrant ready**: http://localhost:6333/dashboard

---

## What Just Got Merged

| Source | Component | Status |
|--------|-----------|--------|
| **Phase_2_AI_SERVICE_FOLDER** | Complete RAG backend (Qdrant, S3, SageMaker, Docling) | ✅ Integrated |
| **Phase_2_FE_IMPLEMENT** | Firebase Google OAuth + user auth | ✅ Integrated |
| **Phase_2_FE_AI_Merge** | Identity routes + DynamoDB users | ✅ Already there |

**Result**: Full-stack system with authentication, document processing, and RAG search.

---

## New Chat Assistant Features (April 2026)

- Persistent chat sessions with **rename / pin / delete**
- Paged chat history list in the Chat Assistant sidebar
- History sync toggle in UI (on/off)
- Session-aware chat stream (`session_id`) with durable message storage
- Runtime switch: local Strands agent or deployed Bedrock AgentCore runtime

---

## Key Files Modified

### Backend
- ✅ `app/services/processing_service.py` — YAML config mapping + HF timeout fixes
- ✅ `config/default.yaml` — `enable_vlm: false` by default (faster)
- ✅ `.env.example` — HF timeout vars documented

### Frontend
- ✅ `src/firebase.ts` — Already has full Google OAuth setup
- ✅ `src/api/client.ts` — Already sends X-User-Id header
- ✅ TypeScript lint: ✅ **NO ERRORS**

---

## Testing the Integration

### 1. Check Backend Health

```bash
curl http://localhost:8000/api/health
# Expected: {"status": "ok", "version": "2.1.0"}
```

### 2. Test Firebase Login (in Frontend)

Click **"Sign in with Google"** button in the UI.

### 3. Upload & Process Document

- Drag & drop a PDF in the dashboard
- Click "Process" button
- Watch the pipeline run (Normalize → Media → Docling → Consolidate)
- Results appear in the RAG Ready folder

### 4. Test Search

- Click "Search" tab
- Enter query like "machine learning"
- See text + image results

### 5. Test Chat History

- Open **Chat Assistant** view
- Create a new chat and send a message
- Rename the session, pin/unpin it, and delete one session
- Verify history paging buttons (Prev/Next) when you have many sessions
- Toggle history sync on/off and confirm behavior:
        - **On**: session APIs are called and chat history persists
        - **Off**: chat still works but history session APIs are skipped

---

## Configuration

### Backend Environment (`.env`)

**Already configured for:**
- ✅ Qdrant Cloud (AWS us-west-2)
- ✅ S3 storage (originals + processed buckets)
- ✅ Firebase auth (service account path)

**Customize if needed:**
```bash
# Switch Qdrant mode
QDRANT_MODE=docker  # or: cloud

# Use local storage instead of S3
FILE_STORAGE_BACKEND=local

# Enable VLM for image descriptions (slower first run, ~5-15 min)
# Add to config/default.yaml:
# processing.document.enable_vlm: true
# processing.document.vlm_model: smolvlm

# Chat runtime switch
CHAT_AGENT_RUNTIME=local  # or: agentcore-runtime
AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:...
AGENTCORE_REGION=us-west-2

# Chat history tables (DynamoDB)
DYNAMODB_CHATBOT_SESSIONS_TABLE=chatbot-session
DYNAMODB_CHATBOT_MESSAGES_TABLE=chatbot-messages
```

### Frontend Environment (`.env.local`, optional)

```bash
VITE_API_BASE_URL=http://localhost:8000/api
```

Default is already `http://localhost:8000/api`, so no config needed for local dev.

---

## Architecture at a Glance

```
Frontend (React + Firebase)
        ↓ (Bearer token + X-User-Id)
Backend (FastAPI)
        ├─ Auth: Verify Firebase token → sync to DynamoDB
        ├─ Upload: Store in S3 / local disk
        ├─ Process: Docling pipeline (OCR, VLM, ASR)
        ├─ Index: Text (BM25, embeddings) + Image (ColPali)
        ├─ Chat: session stream + history APIs
        └─ Search: Hybrid retrieval
        ↓
Qdrant Vector DB → semantic search
DynamoDB → user profiles + chat sessions/messages
S3 → documents
```

---

## Troubleshooting

### "Firebase Admin not configured"
```bash
# Copy Firebase service account to backend root
cp /path/to/firebase-service-account.json Phase_2_FE_AI_Merge/backend/
```

### "Cannot connect to Qdrant"
```bash
# Start Qdrant Docker
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest

# Or update .env to use Qdrant Cloud with valid URL + API key
```

### "Frontend can't reach backend"
```bash
# Ensure backend is running
curl http://localhost:8000/api

# Check frontend env var
echo "VITE_API_BASE_URL=http://localhost:8000/api" > frontend/.env.local
```

### "Slow during first document process"
- First run downloads Docling models (~1-2 GB) if not cached
- This is normal; subsequent runs are much faster
- To enable VLM (slower): see Configuration above

---

## Next Steps

1. **Upload your first document** → Dashboard → Upload
2. **Process it** → Click "Process" → wait for pipeline
3. **Search** → Search tab → enter query
4. **Customize** → Edit `.env` or `config/default.yaml` for your deployment
5. **Deploy** → Use provided Docker configs for production

---

## Verified ✅

- Python syntax: ✅ All files compile
- TypeScript syntax: ✅ No linter errors
- Routes integrated: ✅ All 8 route modules (pipeline, search, auth, users, etc.)
- Firebase auth: ✅ Google OAuth + Firestore sync
- Identity system: ✅ Firebase token verification + DynamoDB user repository
- API client: ✅ Bearer token + X-User-Id headers

---

## Documentation

See **MERGE_SUMMARY.md** for:
- Complete architecture
- All components & their responsibilities
- Full deployment guide
- Scaling notes
- Contributing guidelines

---

**Ready to go! Start the servers and begin processing documents.** 🚀
