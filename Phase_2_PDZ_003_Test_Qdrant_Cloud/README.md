# Phase 2 PDZ-003: Qdrant Vector Store with ColPali Multi-Vector Embeddings

**Subject:** Capstone Thesis - BK-MInD: AI-Powered Lecture Learning System
**Module:** Phase 2 PDZ-003 - Qdrant Cloud and ColPali Multi-Vector Learning Lab
**Contributor:** Nguyen Quang Phu (PDZ)

---

## Overview

This module is a self-contained learning laboratory for understanding how multi-vector image embeddings are stored, indexed, and retrieved using the Qdrant Vector Database. It is designed as an educational companion to the main Phase 2 RAG pipeline, with heavy comments throughout every source file to explain not just what the code does but why each decision was made.

The module demonstrates two deployment configurations for the vector store (a local Docker container and the managed Qdrant Cloud service), two execution modes for the ColQwen2 model (local inference and a remote API server), and the full end-to-end flow from raw image files through multi-vector embedding storage and late-interaction MaxSim retrieval.

The three Python scripts are meant to be studied and run in sequence. Each one is a standalone program with its own detailed inline documentation.

---

## 1. Processing Flow and System Architecture

### 1.1 End-to-End Data Flow

The module processes image files through three sequential stages, each implemented as a separate Python script.

```
input/ images
     |
     v
ColQwen2 model (local GPU or remote API server)
     |
     | [1, num_patches, 128] per image -- typically 755 patches for a 1224x1584 slide
     v
Qdrant vector store (Docker or Cloud)
     |
     | Stores each image as a list-of-lists (multi-vector point)
     | Each point carries: id, multi-vector, payload (filename, width, height, ...)
     v
MaxSim search at query time
     |
     | Query (text or image) -> ColQwen2 -> [num_query_tokens, 128]
     | Qdrant computes: score(Q, D) = sum_i  max_j  dot(Q_i, D_j)
     v
Top-k ScoredPoint results with metadata and latency breakdown
```

### 1.2 What Makes Multi-Vector Different from a Flat Vector

A standard dense retrieval system encodes each document into a single high-dimensional vector. At search time, the similarity score is a single dot product between query and document vectors. ColPali takes a fundamentally different approach: each image is divided into a spatial grid of patches (similar to how a vision transformer works), and each patch becomes its own 128-dimensional vector. A typical lecture slide produces approximately 755 patch vectors.

At search time, for every token in the query embedding, the system finds the single document patch with the highest dot product score, then sums those per-token maximum scores across all query tokens. This is the MaxSim operator. The result is that a query about one corner of a slide still scores well even if the rest of the slide contains unrelated content, because MaxSim only cares about the best match per query token, not an average over the whole image.

### 1.3 Project File Structure

```
Phase_2_PDZ_003_Test_Qdrant_Cloud/
    .env.example                    -- copy to .env and fill in your configuration
    config.py                       -- loads .env, exposes cfg singleton, builds QdrantClient
    utils.py                        -- Timer, LatencyTracker, load_images, print_results
    01_create_client_collection.py  -- Step 1: connect to Qdrant, create multi-vector collection
    02_embed_and_store.py           -- Step 2: embed images with ColQwen2, batch upsert to Qdrant
    03_search_retrieve.py           -- Step 3: text and image queries, MaxSim search, latency report
    requirements.txt
    input/                          -- place your .jpg / .png image files here
```

---

## 2. Installation and Prerequisites

### 2.1 Python Environment

The module targets Python 3.10 or 3.11. It is recommended to use the project-level virtual environment.

```powershell
cd d:\PDZ\BKU\Learning\LVTN\GD1\Code
.\.venv\Scripts\Activate.ps1
pip install -r Phase_2_PDZ_003_Test_Qdrant_Cloud\requirements.txt
```

### 2.2 Key Dependencies

| Package | Version | Purpose |
|---|---|---|
| colpali-engine | 0.3.13 | ColQwen2 model and processor for multi-vector image embedding |
| qdrant-client | latest | Qdrant Python SDK (supports Docker and Cloud) |
| torch | latest | PyTorch, required for model inference |
| transformers | latest | HuggingFace Transformers, ColQwen2 base architecture |
| bitsandbytes | latest | 8-bit and 4-bit model weight quantization (reduces VRAM) |
| Pillow | latest | Image loading and preprocessing |
| python-dotenv | latest | Reading .env files into environment variables |

### 2.3 GPU Requirements

ColQwen2 is a large vision-language model based on Qwen2-VL-2B. Running it locally requires a GPU with sufficient VRAM. The memory requirements vary depending on the quantization setting chosen in `config.py`.

| Quantization | VRAM Required | Inference Speed |
|---|---|---|
| bfloat16 (no quantization) | approximately 16 GB | fastest per-call after load, large memory footprint |
| 8-bit LLM.int8() (default) | approximately 8 GB | slightly slower, half the memory, recommended setting |
| 4-bit NF4 | approximately 5 GB | further reduced memory with small accuracy trade-off |

The default configuration in `config.py` uses `load_in_8bit=True`. This is handled automatically by the BitsAndBytes library. No code changes are required to use 8-bit loading.

---

## 3. Configuration

### 3.1 Creating the .env File

All configuration is read from a `.env` file in the module directory. Copy the provided example and edit it before running any script.

```powershell
cd Phase_2_PDZ_003_Test_Qdrant_Cloud
copy .env.example .env
```

The `config.py` module reads this file at startup and exposes a single `cfg` object used by all three scripts. This centralizes all tunable parameters in one place and avoids hardcoding any values in the scripts themselves.

### 3.2 Configuration Reference

```
QDRANT_MODE        -- "docker" (local container) or "cloud" (Qdrant Cloud managed service)
QDRANT_HOST        -- Docker only: hostname of the Qdrant container, default localhost
QDRANT_PORT        -- Docker only: REST API port, default 6333
QDRANT_URL         -- Cloud only: full HTTPS URL of the cluster, e.g. https://abc.cloud.qdrant.io:6333
QDRANT_API_KEY     -- Cloud only: API key from the Qdrant Cloud console

COLLECTION_NAME    -- name of the Qdrant collection, default colpali_images_test
VECTOR_NAME        -- name of the named vector slot inside the collection, default colpali_multivec
EMBEDDING_DIM      -- dimension of each patch vector, must be 128 for ColQwen2
TOP_K              -- default number of results to return from search, default 5
SCORE_THRESHOLD    -- minimum MaxSim score to include a result, default 0.0

COLQWEN_MODEL      -- HuggingFace model identifier, default vidore/colqwen2-v1.0
TORCH_DTYPE        -- compute dtype for the model, default bfloat16
INPUT_DIR          -- path to the folder of images to index, default ./input

INFERENCE_MODE     -- "local" (load model on this machine) or "remote" (call an HTTP API)
INFERENCE_URL      -- Remote only: base URL of the inference API server, e.g. http://10.0.0.5:8080
```

---

## 4. Vector Store Configuration: Docker vs Cloud

### 4.1 Motivation

The Qdrant client library (`qdrant-client`) provides a unified Python SDK that abstracts over the transport layer. Whether you are connecting to a local Docker container or to a managed cloud cluster, the Python API surface is identical. The only difference is how the client is constructed: Docker mode uses a hostname and port, while Cloud mode uses an HTTPS URL and an API key for authentication.

In this module, all three scripts call `cfg.build_client()` rather than constructing the client directly. The `build_client()` method in `config.py` reads `QDRANT_MODE` from the environment and returns the correctly configured client. This design means that switching between Docker and Cloud requires only a change to the `.env` file, with no modifications to any of the scripts.

### 4.2 Option A: Docker (Recommended for Local Development)

Docker mode runs Qdrant entirely on the local machine. It requires no account, no internet connection, and no API key. Data is stored inside the container by default, or can be persisted to a local folder.

Pull and start the container:

```powershell
docker pull qdrant/qdrant:latest

docker run -d -p 6333:6333 -p 6334:6334 --name qdrant qdrant/qdrant:latest
```

The REST API used by the Python SDK is on port 6333. Port 6334 exposes the gRPC interface, which is optional for this module but useful at high throughput. After starting the container, the Qdrant web dashboard is available at `http://localhost:6333/dashboard`. It shows all collections, their sizes, vector configurations, and individual stored points.

To persist data across container restarts, mount a local directory:

```powershell
docker run -d -p 6333:6333 -p 6334:6334 --name qdrant `
    -v "${PWD}/qdrant_storage:/qdrant/storage" `
    qdrant/qdrant:latest
```

Configure `.env` for Docker:

```
QDRANT_MODE=docker
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

Manage the container:

```powershell
docker stop qdrant        # stop the container, data is preserved
docker start qdrant       # restart where it left off
docker rm -f qdrant       # delete the container and all data inside it
```

### 4.3 Option B: Qdrant Cloud (Managed Service)

Qdrant Cloud is the managed version of Qdrant. It handles infrastructure, scaling, backups, and high availability. A free-tier cluster is available for evaluation and learning purposes.

To set up a cluster, visit `https://cloud.qdrant.io`, create an account, and follow the steps to create a new cluster. Note the cluster URL (of the form `https://CLUSTER-ID.REGION.cloud.qdrant.io:6333`) and generate an API key from the API Keys page of the console.

Configure `.env` for Cloud:

```
QDRANT_MODE=cloud
QDRANT_URL=https://your-cluster-id.region.cloud.qdrant.io:6333
QDRANT_API_KEY=your-api-key-here
```

The `QDRANT_HOST` and `QDRANT_PORT` fields are not used when `QDRANT_MODE=cloud` and can be left empty.

### 4.4 Switching Between Docker and Cloud

To switch between the two modes, change `QDRANT_MODE` in `.env` and, for Cloud mode, add the URL and API key. No other change is needed anywhere in the codebase.

```
# Local development
QDRANT_MODE=docker

# Production or team-shared cluster
QDRANT_MODE=cloud
QDRANT_URL=https://...
QDRANT_API_KEY=...
```

---

## 5. Model Inference Configuration: Local vs Remote API

### 5.1 Motivation and the Production Architecture Pattern

When running locally, both `02_embed_and_store.py` and `03_search_retrieve.py` load the ColQwen2 model directly into the Python process on the local GPU. This is convenient for development and experimentation, but it has a significant limitation: every script that needs embeddings must load the model independently, and the model must be present on the same machine as the application. In a production system, this does not scale well.

The more robust approach, which is also shown in the system architecture diagram for the BK-MInD project, is to operate a dedicated GPU Model Server as a separate process or service. This server holds the model in GPU memory at all times, accepting HTTP requests that contain images or text and returning embedding vectors. The main application (including the embed-and-store pipeline and the search API) then calls this remote server over the network instead of loading the model locally. This architecture separates the GPU compute concern from the application logic concern.

This module supports this pattern through the `INFERENCE_MODE` configuration field.

### 5.2 Option A: Local Inference (Default)

When `INFERENCE_MODE=local`, the model is loaded directly by the Python script using the local GPU. This is the default and works out of the box with no additional setup.

```
INFERENCE_MODE=local
```

The 8-bit quantized model loads in approximately 25 to 30 seconds on first run (downloading model weights from HuggingFace Hub if not cached). After that initial load, each text query encodes in approximately 400 ms and each image encodes in approximately 7 to 8 seconds on a mid-range GPU.

### 5.3 Option B: Remote API Inference

When `INFERENCE_MODE=remote`, the scripts do not load the model locally. Instead, they send HTTP POST requests to the inference server specified by `INFERENCE_URL`. This requires you to have a running inference server that exposes two endpoints.

```
INFERENCE_MODE=remote
INFERENCE_URL=http://YOUR_SERVER_IP:8080
```

The expected API contract is:

```
POST /embed/image
  Body: { "image_base64": "<base64-encoded PNG or JPEG>" }
  Returns: { "embedding": [[f0, f1, ..., f127], [f0, ...], ...] }

POST /embed/query
  Body: { "query_text": "your search query" }
  Returns: { "embedding": [[f0, f1, ..., f127], [f0, ...], ...] }
```

The server returns a `List[List[float]]` in both cases, which is the same format that Qdrant's multi-vector storage and search expect. No other changes are needed in the scripts.

### 5.4 How to Build the Remote Inference Server

A minimal FastAPI server that wraps ColQwen2 for remote inference looks like the following. This can be deployed to any machine with a compatible GPU, including an AWS EC2 `g4dn.xlarge` (NVIDIA T4, 16 GB VRAM) or `p3.2xlarge` (NVIDIA V100).

```python
# inference_server.py  --  run on the GPU machine
import base64, io, torch
from fastapi import FastAPI
from pydantic import BaseModel
from PIL import Image
from colpali_engine.models import ColQwen2, ColQwen2Processor
from transformers import BitsAndBytesConfig

app = FastAPI()

# Load the model once at startup
bnb = BitsAndBytesConfig(load_in_8bit=True)
processor = ColQwen2Processor.from_pretrained("vidore/colqwen2-v1.0")
model = ColQwen2.from_pretrained("vidore/colqwen2-v1.0",
                                  quantization_config=bnb).eval()

class ImageRequest(BaseModel):
    image_base64: str

class QueryRequest(BaseModel):
    query_text: str

@app.post("/embed/image")
def embed_image(req: ImageRequest):
    img = Image.open(io.BytesIO(base64.b64decode(req.image_base64))).convert("RGB")
    inputs = processor.process_images([img]).to(model.device)
    with torch.no_grad():
        emb = model(**inputs)
    return {"embedding": emb[0].float().tolist()}

@app.post("/embed/query")
def embed_query(req: QueryRequest):
    inputs = processor.process_queries([req.query_text]).to(model.device)
    with torch.no_grad():
        emb = model(**inputs)
    return {"embedding": emb[0].float().tolist()}
```

Start the server with:

```bash
uvicorn inference_server:app --host 0.0.0.0 --port 8080
```

Once the server is running, set `INFERENCE_MODE=remote` and `INFERENCE_URL=http://SERVER_IP:8080` in the `.env` file on the machine running the embed-and-store or search scripts. The application scripts become thin clients that do not require a local GPU at all.

### 5.5 Practical Hosting Options for the Inference Server

Any Linux machine with an NVIDIA GPU and the CUDA toolkit installed can run the inference server described above. The following options are common in practice.

An AWS EC2 instance of type `g4dn.xlarge` provides a T4 GPU with 16 GB of VRAM and is sufficient to run the 8-bit quantized ColQwen2 model. The estimated cost at on-demand pricing is approximately 0.50 USD per hour. For periodic processing jobs rather than always-on serving, using a spot instance reduces this cost by 60 to 70 percent.

A Google Cloud `n1-standard-4` instance with a T4 GPU accelerator attached provides a comparable option. The setup process is the same: install the NVIDIA driver, install CUDA, install dependencies, and start the FastAPI server.

For teams already using AWS, the GPU Model Server shown in the BK-MInD system architecture diagram is intended to be a separate EC2 instance inside the same VPC as the main backend. The backend ECS container calls the inference server over the private network, avoiding internet transit for the embedding requests.

### 5.6 Summary: What Changes When Switching Inference Mode

| Aspect | local | remote |
|---|---|---|
| GPU required on this machine | Yes | No |
| Model loaded at script startup | Yes | No |
| Network call per embedding | No | Yes (POST to INFERENCE_URL) |
| Change needed in scripts | None | None |
| Change needed in .env | INFERENCE_MODE=local | INFERENCE_MODE=remote + INFERENCE_URL |

---

## 6. Running the Scripts

Place at least one `.jpg` or `.png` file in the `input/` directory, then run the three scripts in order.

```powershell
cd Phase_2_PDZ_003_Test_Qdrant_Cloud

# Step 1: Create the Qdrant collection with multi-vector and scalar quantization config
python 01_create_client_collection.py

# Step 2: Embed all images in input/ and batch upsert them to Qdrant
python 02_embed_and_store.py

# Step 3: Run text and image queries, view results and latency breakdowns
python 03_search_retrieve.py
```

Each script validates the configuration on startup, connects to Qdrant, logs every significant operation with timestamps, and prints a summary at the end.

---

## 7. Key Concepts Reference

| Term | Explanation |
|---|---|
| Collection | The top-level named container in Qdrant, analogous to a table in a relational database. Created in `01_`. |
| Point | One stored record: an id, one or more named vectors, and a JSON payload. One point per image in this module. |
| Named vector | A collection can store multiple different vector types under separate names. This enables storing both ColPali multi-vectors and a flat CLIP vector on the same point for hybrid retrieval. |
| Multi-vector | Each point stores a list of vectors rather than a single vector. ColPali's core representation: one 128-d vector per image patch. |
| Payload | Arbitrary JSON metadata attached to a point. In this module: filename, image dimensions, number of patches, embedding dimension. Used for display and for payload-filtered search. |
| MaxSim | Late-interaction scoring: score(Q, D) = sum_i max_j dot(Q_i, D_j). Sums the best patch match for each query token. Scores are not bounded to [0, 1]; typical text-query scores are 8 to 15, image-query scores are 400 to 800. |
| Storage quantization | Qdrant compresses stored vectors to save RAM. Options: none, scalar (int8, 4x compression), binary (1-bit, 32x compression). Configured in `01_`. Entirely separate from model weight quantization. |
| Model weight quantization | BitsAndBytes reduces the ColQwen2 model's weights from bfloat16 to 8-bit or 4-bit precision, cutting VRAM use by 2x to 4x. Configured in `config.py` via `load_in_8bit`. |
| Payload filter | A Qdrant filter applied before MaxSim scoring to restrict the search to a subset of points matching metadata conditions (e.g., all images from a specific lecture). Demonstrated in Demo 4 of `03_`. |

---

## 8. Observed Results

The following results were recorded on a machine with an NVIDIA GPU running the 8-bit quantized ColQwen2 model, with Qdrant running in Docker mode on localhost, indexing 5 lecture slide images (1224 x 1584 pixels, 755 patches each).

### 8.1 Text Query Results

For the query "Introduction about LLM", the top result was `page_003_full.png` with a MaxSim score of 9.81, and all five indexed slides were returned. Scores for text queries in this experiment ranged from 8.2 to 13.5 depending on query specificity and content relevance. Queries with longer and more specific text (for example, "Diagram of VideoRAG framework") produced higher absolute MaxSim scores because they generated more query tokens, each contributing to the sum.

### 8.2 Image-to-Image Search Results

When using `page_002_full.png` as the query image, the same image was returned as the top result with a MaxSim score of 755.00, which is the theoretical maximum for a document of 755 patches (a perfect self-match scores 1.0 per patch summed over all query patches). The second and third results scored 488.8 and 475.4, indicating high visual similarity among lecture slides from the same presentation.

The substantially higher absolute scores for image-to-image search compared to text-to-image search are expected. An image query produces 755 query vectors, while a text query produces only 12 to 17 query tokens. The MaxSim sum accumulates proportionally to the number of query vectors.

### 8.3 Latency Profile

All latency numbers below are approximate and reflect the first run (no model warm-up cache).

| Operation | Observed Time |
|---|---|
| Model load (8-bit, colqwen2-v1.0) | approximately 27 seconds |
| Text query encoding (12-17 tokens) | 400 to 450 ms after warm-up (first query: approximately 2 seconds) |
| Image query encoding (755 patches) | approximately 7.8 seconds |
| Qdrant MaxSim search over 5 points | 13 to 105 ms |
| Total per text query after warm-up | approximately 440 to 500 ms |

The first text query in a session is significantly slower than subsequent ones because CUDA kernels are compiled and cached on first use. From the second query onward, text encoding stabilizes at approximately 400 ms.

Image encoding is substantially slower than text encoding because the image input produces 755 vectors to compute versus 12 to 17 for a text query. For production-scale indexing of many images, the embed-and-store pipeline batches images and can benefit from a GPU with higher VRAM to allow larger batch sizes.

---

## 9. Troubleshooting

**Connection refused on localhost:6333**
The Docker container is not running. Check the container list with `docker ps`. If the container name `qdrant` appears but is stopped, start it with `docker start qdrant`. If it does not appear, run the `docker run` command from Section 4.2.

**Collection not found**
Run `01_create_client_collection.py` first. The collection must exist before points can be upserted.

**Collection is empty when running 03_**
Run `02_embed_and_store.py` and confirm that there are image files in the `input/` directory with `.jpg` or `.png` extensions.

**CONFIG ERROR: QDRANT_MODE is not valid**
The `.env` file is missing or `QDRANT_MODE` contains an unsupported value. Valid values are `docker` and `cloud` (lowercase). Make sure the file is named `.env` and is located in the `Phase_2_PDZ_003_Test_Qdrant_Cloud/` directory.

**colpali_engine import failed**
Run `pip install colpali-engine==0.3.13`.

**torch_dtype deprecation warning**
This has been resolved in the current version of `02_embed_and_store.py` and `03_search_retrieve.py`. Both files now use the `dtype=` keyword argument in `from_pretrained`, which is the current HuggingFace convention.

**Out of GPU memory during embedding**
The default `load_in_8bit=True` in `config.py` requires approximately 8 GB of VRAM. If the GPU has less memory, set `load_in_4bit=True` in `config.py` instead (requires approximately 5 GB). Alternatively, set both to False and use `torch_dtype=float32` to run on CPU, which is much slower but requires no GPU.

**bitsandbytes is not installed**
Run `pip install bitsandbytes`. It is listed in `requirements.txt` and should be installed automatically. On Windows, bitsandbytes requires CUDA 11.x or 12.x to be installed system-wide.

