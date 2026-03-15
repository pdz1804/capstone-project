"""
01_create_client_collection.py
===============================
STEP 1: Learn how to connect to Qdrant Cloud and set up a collection
for storing ColPali multi-vector embeddings.

WHAT YOU WILL LEARN IN THIS FILE:
  1. How to create a QdrantClient (connect to cloud or local server)
  2. What a "collection" is in Qdrant and how to configure it
  3. How to configure multi-vector storage for ColPali / ColQwen
     - What "multi-vector" means (late interaction / MaxSim scoring)
  4. Qdrant's built-in STORAGE quantization options:
     - No quantization (full float32)
     - Scalar quantization (int8, ~4× smaller)
     - Binary quantization (~32× smaller — surprisingly good for ColPali!)
  5. How to inspect, list, and delete collections

QDRANT GLOSSARY (beginner's cheat-sheet):
  Client     — your Python object that talks to the Qdrant server
  Collection — a named bucket of vector points  (↔ "table" in SQL)
  Point      — one record: { id, vector(s), payload }
  Vector     — the embedding stored for a point (float array)
  Payload    — arbitrary JSON metadata attached to a point  (↔ "row data")
  Named Vec  — a collection can hold several differently-named vectors per point

RUN THIS SCRIPT:
  python 01_create_client_collection.py
"""

import sys
import logging
from pathlib import Path

# ── Qdrant client imports ────────────────────────────────────────────────────
from qdrant_client import QdrantClient
from qdrant_client.models import (
    # VectorParams: defines ONE named vector slot inside a collection
    VectorParams,

    # Distance metrics — how similarity is computed:
    #   DOT    — inner product (works best when vectors are normalised to unit length)
    #   COSINE — cosine similarity (auto-normalises so you don't have to)
    #   EUCLID — Euclidean (L2) distance (best for dense retrieval without normalisation)
    # ColQwen normalises its output vectors → we use DOT.
    Distance,

    # Multi-vector support (for ColPali/ColBERT-style "late interaction" models):
    #   MultiVectorConfig tells Qdrant that each point stores a LIST of vectors
    #   (one per image patch), not just a single vector.
    #
    # MultiVectorComparator.MAX_SIM is the MaxSim operator:
    #   score(query Q, document D) = Σ_i max_j dot(Q_i, D_j)
    #   i.e., for every query token find its best-matching document token, then sum.
    #   This is exactly the scoring used in the ColPali / ColQwen paper.
    MultiVectorConfig,
    MultiVectorComparator,

    # ── Qdrant storage quantization (NOT the same as model-weight quantization!) ──
    #
    # Storage quantization compresses the VECTORS STORED IN QDRANT to use less
    # memory and disk.  The model weights on your GPU/CPU are unaffected.
    #
    # ScalarQuantization: converts each float32 → int8 (1 byte instead of 4 bytes)
    #   → ~4× storage reduction, tiny accuracy loss
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,

    # BinaryQuantization: converts each float → a single bit (positive=1, negative=0)
    #   → ~32× storage reduction, small accuracy loss
    #   → Research shows ColPali embeddings tolerate binary quant very well!
    BinaryQuantization,
    BinaryQuantizationConfig,

    # PayloadSchemaType: the data type of the payload field to index
    # Required on Qdrant Cloud (and best practice everywhere) before filtering.
    PayloadSchemaType,
)

# ── Our project files ─────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from config import cfg
from utils import setup_logging, Timer

logger = setup_logging(logging.INFO)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: CREATE THE CLIENT
# ─────────────────────────────────────────────────────────────────────────────

def create_client() -> QdrantClient:
    """
    Connect to Qdrant (Docker or Cloud) and return a QdrantClient.

    The client is a long-lived object — create it once and reuse it.
    Under the hood it maintains an HTTP connection pool to the Qdrant server.

    THREE WAYS TO INSTANTIATE A CLIENT (for your reference):
      1. Docker / local:   QdrantClient(host="localhost", port=6333)
      2. Cloud:            QdrantClient(url="https://...", api_key="...")
      3. In-memory (test): QdrantClient(":memory:")  # data lost on exit

    This function delegates to cfg.build_client() which picks the right
    constructor automatically based on QDRANT_MODE in your .env.
    """
    # Validate that .env was properly filled in for the chosen mode
    cfg.validate()

    logger.info("─" * 55)
    logger.info(f"Connecting to Qdrant  [mode={cfg.mode}] …")
    if cfg.mode == "docker":
        logger.info(f"  Host : {cfg.qdrant_host}:{cfg.qdrant_port}")
        logger.info(f"  Auth : none (Docker mode, no API key needed)")
    else:
        logger.info(f"  URL  : {cfg.qdrant_url}")
        logger.info(f"  Key  : {'*' * 8}  (masked for security)")
    logger.info("─" * 55)

    with Timer("qdrant_client_connect"):
        client = cfg.build_client()

    # ── Health check: list all collections ──────────────────────────────────
    # get_collections() returns a CollectionsResponse with a `.collections`
    # list of CollectionDescription objects, each having a `.name` field.
    collections_response = client.get_collections()
    existing_names = [c.name for c in collections_response.collections]

    logger.info(f"Connected successfully!")
    logger.info(
        f"Existing collections: "
        + (str(existing_names) if existing_names else "(none yet)")
    )
    return client


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: CREATE COLLECTION
# ─────────────────────────────────────────────────────────────────────────────

def create_collection(
    client: QdrantClient,
    quantization: str = "scalar",    # "none" | "scalar" | "binary"
    force_recreate: bool = False,
) -> None:
    """
    Create a Qdrant collection configured for ColPali multi-vector embeddings.

    ┌─────────────────────────────────────────────────────────────────────┐
    │  STORAGE SIZE COMPARISON  (per image, ~1030 patches × 128 dims)    │
    │                                                                     │
    │  Quantization   Bytes/vec   Total/image   Compression              │
    │  ──────────────────────────────────────────────────────            │
    │  None (float32)   4 bytes     528 KB        1×  (baseline)         │
    │  Scalar (int8)    1 byte      132 KB        4×  (recommended)      │
    │  Binary (1 bit)  0.125 byte   16.5 KB       32× (great for ColPali)│
    └─────────────────────────────────────────────────────────────────────┘

    Args:
        client         : Connected QdrantClient
        quantization   : Storage quantization strategy (see table above)
        force_recreate : If True, DELETE the existing collection first.
                         WARNING: This permanently erases all stored points!
    """
    name = cfg.collection_name

    # ── Check if collection already exists ──────────────────────────────────
    existing = [c.name for c in client.get_collections().collections]

    if name in existing:
        if force_recreate:
            logger.warning(f"force_recreate=True → deleting '{name}' …")
            client.delete_collection(name)
            logger.info(f"Deleted '{name}'.")
        else:
            logger.info(
                f"Collection '{name}' already exists — skipping creation.\n"
                f"  Pass force_recreate=True to wipe and recreate it."
            )
            return

    # ── Build the storage-quantization config for Qdrant ────────────────────
    # REMINDER: This compresses vectors IN QDRANT, not the model weights!
    quant_config = None

    if quantization == "scalar":
        logger.info("Quantization: SCALAR (int8) — ~4× storage reduction")
        quant_config = ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                # INT8: each float32 value is rounded to nearest integer in [-128, 127]
                type=ScalarType.INT8,
                # quantile=0.99 means the top and bottom 0.5 % of values are clipped
                # before scaling — prevents rare outliers from distorting the range
                quantile=0.99,
                # always_ram=True: keep quantized vectors in RAM (faster search)
                # Set False to save RAM at the cost of some latency
                always_ram=True,
            )
        )

    elif quantization == "binary":
        logger.info("Quantization: BINARY — ~32× storage reduction")
        quant_config = BinaryQuantization(
            binary=BinaryQuantizationConfig(
                # always_ram keeps binary vectors in RAM for sub-millisecond search
                always_ram=True,
            )
        )

    else:
        logger.info("Quantization: NONE (full float32)")

    # ── Configure the named vector for ColPali multi-vector embeddings ──────
    #
    # NAMED VECTORS let one collection store several kinds of embeddings.
    # Example: {"colpali_multivec": ..., "clip_vec": ...}
    # When searching you specify which vector to use via  using="colpali_multivec".
    vector_config = VectorParams(
        # size: the dimensionality of each individual patch embedding
        # ColQwen2 projects every patch to a 128-dimensional vector
        size=cfg.embedding_dim,   # 128

        # distance: the similarity metric used for comparisons
        # DOT  = dot product.  With unit-norm vectors (which ColQwen produces),
        # this is identical to cosine similarity.
        distance=Distance.DOT,

        # ── THE KEY PART FOR COLPALI ──────────────────────────────────────
        # Without multivector_config, Qdrant would expect ONE flat vector per point.
        # With it, we can store a LIST of vectors per point (one per image patch).
        # MAX_SIM tells Qdrant to use the MaxSim scoring operator at search time.
        multivector_config=MultiVectorConfig(
            comparator=MultiVectorComparator.MAX_SIM,
        ),

        # Attach the storage quantization config (None = no quantization)
        quantization_config=quant_config,
    )

    # ── Create the collection ───────────────────────────────────────────────
    logger.info(f"Creating collection '{name}' …")
    logger.info(f"  vector_name   : {cfg.vector_name}")
    logger.info(f"  embedding_dim : {cfg.embedding_dim}")
    logger.info(f"  distance      : DOT  (MaxSim multi-vector)")
    logger.info(f"  quantization  : {quantization}")

    with Timer("create_collection"):
        client.create_collection(
            collection_name=name,
            # vectors_config is a dict mapping vector-name → VectorParams
            vectors_config={
                cfg.vector_name: vector_config
            },
        )

    logger.info(f"Collection '{name}' created successfully!")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: CREATE PAYLOAD INDEXES
# ─────────────────────────────────────────────────────────────────────────────

def create_payload_indexes(client: QdrantClient) -> None:
    """
    Create payload indexes on metadata fields you want to filter by.

    WHY THIS IS REQUIRED ON QDRANT CLOUD:
      Qdrant Cloud enforces that any field used in a Filter() must have a
      pre-built index.  Local Docker is lenient and does a full scan instead,
      but Cloud rejects the request with a 400 error.

    This function is IDEMPOTENT — safe to run multiple times and on a
    collection that already has points in it.  Qdrant builds the index over
    existing data automatically.

    FIELD TYPES:
      PayloadSchemaType.INTEGER  → int fields  (image_width, image_height, …)
      PayloadSchemaType.FLOAT    → float fields
      PayloadSchemaType.KEYWORD  → string equality / keyword fields
      PayloadSchemaType.TEXT     → full-text search fields
    """
    name = cfg.collection_name
    logger.info("─" * 55)
    logger.info(f"Creating payload indexes on '{name}' …")

    # Index every field you plan to use in a Filter().
    # Add more fields here as your project grows.
    fields_to_index = [
        ("image_width",    PayloadSchemaType.INTEGER),
        ("image_height",   PayloadSchemaType.INTEGER),
        ("filename",       PayloadSchemaType.KEYWORD),
        ("original_index", PayloadSchemaType.INTEGER),
    ]

    for field_name, field_type in fields_to_index:
        client.create_payload_index(
            collection_name=name,
            field_name=field_name,
            field_schema=field_type,
        )
        logger.info(f"  ✓  index created: '{field_name}'  ({field_type.value})")

    logger.info("Payload indexes ready.")
    logger.info("─" * 55)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: INSPECT COLLECTION
# ─────────────────────────────────────────────────────────────────────────────

def inspect_collection(client: QdrantClient) -> None:
    """
    Print full details of our collection: status, point count, vector config.

    CollectionInfo fields we care about:
      .status          — "green" (healthy), "yellow" (optimising), "red" (error)
      .points_count    — how many points are stored
      .segments_count  — internal storage segments (Qdrant manages these automatically)
      .config.params.vectors — dict of named VectorParams
    """
    try:
        info = client.get_collection(cfg.collection_name)
    except Exception as e:
        logger.error(f"Could not get collection info: {e}")
        return

    width = 62
    print("\n" + "═" * width)
    print(f"  COLLECTION INFO — '{cfg.collection_name}'")
    print("═" * width)
    print(f"  Status         : {info.status}")
    print(f"  Points stored  : {info.points_count:,}")
    print(f"  Segments       : {info.segments_count}")

    # Vector configuration
    vectors = info.config.params.vectors
    if isinstance(vectors, dict):
        for vec_name, params in vectors.items():
            print(f"\n  Named vector   : '{vec_name}'")
            print(f"    Size (dim)   : {params.size}")
            print(f"    Distance     : {params.distance}")
            if params.multivector_config:
                print(f"    Multi-vector : {params.multivector_config.comparator}")
            if params.quantization_config:
                q_type = type(params.quantization_config).__name__
                print(f"    Storage quant: {q_type}")
            else:
                print(f"    Storage quant: none (float32)")
    print("═" * width + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: LIST ALL COLLECTIONS
# ─────────────────────────────────────────────────────────────────────────────

def list_all_collections(client: QdrantClient) -> None:
    """
    List every collection in the Qdrant cluster (across all your projects).
    Useful for getting an overview of what's on the cloud.
    """
    response = client.get_collections()
    collections = response.collections

    print("\n" + "═" * 45)
    print(f"  ALL COLLECTIONS ({len(collections)} total)")
    print("═" * 45)
    if not collections:
        print("  (none)")
    for c in collections:
        # Each CollectionDescription just has .name
        mark = "◄ this script" if c.name == cfg.collection_name else ""
        print(f"  • {c.name}  {mark}")
    print("═" * 45 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — ties everything together
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 65)
    print("   STEP 1 — Qdrant Client + Collection Setup")
    print("═" * 65 + "\n")

    # ── 1. Connect ───────────────────────────────────────────────────────────
    logger.info("=== SECTION 1: Connecting to Qdrant Cloud ===")
    client = create_client()

    # ── 2. List existing collections ────────────────────────────────────────
    logger.info("\n=== SECTION 2: Listing existing collections ===")
    list_all_collections(client)

    # ── 3. Create our collection ─────────────────────────────────────────────
    logger.info("=== SECTION 3: Creating collection ===")
    create_collection(
        client,
        # Choose your storage quantization strategy:
        #   "none"   — full float32, best accuracy
        #   "scalar" — int8, 4× smaller  ← good starting point
        #   "binary" — 1-bit, 32× smaller, still good for ColPali
        quantization="scalar",
        # Set force_recreate=True to wipe+recreate (useful during experiments)
        force_recreate=False,
    )

    # ── 4. Create payload indexes (required on Qdrant Cloud for filtering) ───
    logger.info("\n=== SECTION 4: Creating payload indexes ===")
    create_payload_indexes(client)

    # ── 5. Inspect what was created ──────────────────────────────────────────
    logger.info("\n=== SECTION 5: Inspecting collection ===")
    inspect_collection(client)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("✓  Collection is ready.")
    print("   Next step → run  02_embed_and_store.py  to index your images.\n")
