"""
config.py — Central Configuration (supports Docker + Qdrant Cloud)
====================================================================

This module loads all settings from a .env file (using python-dotenv)
and exposes them as a clean Python dataclass called `Config`.

TWO MODES — controlled by QDRANT_MODE in your .env:

  QDRANT_MODE=docker
    Connects to a local Qdrant container via host:port (no API key).
    Start the container first:
        docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest

  QDRANT_MODE=cloud
    Connects to Qdrant Cloud via HTTPS URL + API key.
    Get credentials from https://cloud.qdrant.io/

HOW TO USE IN YOUR OWN SCRIPTS:
  from config import cfg          # import the shared singleton
  print(cfg.mode)                 # "docker" or "cloud"
  client = cfg.build_client()     # returns a ready QdrantClient
  cfg.validate()                  # raises if any required field is missing
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field

# python-dotenv: reads KEY=VALUE pairs from a file called .env
# and loads them into os.environ so os.getenv() can access them.
# override=True means the .env file wins over any pre-existing env vars.
from dotenv import load_dotenv

# Locate .env in the same folder as this script
_ENV_FILE = Path(__file__).parent / ".env"

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=True)
    logging.getLogger(__name__).debug(f"Loaded .env from: {_ENV_FILE}")
else:
    logging.getLogger(__name__).warning(
        f".env file not found at {_ENV_FILE}. "
        "Copy .env.example to .env and fill in your credentials."
    )


# ===========================================================
# CONFIG DATACLASS
# ===========================================================

@dataclass
class Config:
    """
    Central configuration object.

    All values are read from environment variables (loaded from .env).
    Default values are provided where possible.

    QDRANT CONCEPTS:
    - Mode       : "docker" (local container) or "cloud" (managed Qdrant Cloud)
    - URL        : The network address of your Qdrant server / cloud cluster
    - API key    : Secret token required ONLY for Qdrant Cloud (not needed for Docker)
    - Collection : A named bucket of vectors (like a "table" in SQL)
    - Vector name: Collections can hold multiple sets of vectors under different names
    - Distance   : The math used to compare vectors (DOT, COSINE, EUCLID)
    """

    # -----------------------------------------------------------
    # CONNECTION MODE
    # -----------------------------------------------------------

    # "docker" → local Docker container, no authentication required
    # "cloud"  → Qdrant Cloud, requires QDRANT_URL + QDRANT_API_KEY
    # Reads from QDRANT_MODE in .env (default: "docker" so newcomers can start immediately)
    mode: str = field(
        default_factory=lambda: os.getenv("QDRANT_MODE", "docker").strip().lower()
    )

    # -----------------------------------------------------------
    # DOCKER MODE SETTINGS  (used when mode == "docker")
    # -----------------------------------------------------------

    # Hostname where the Qdrant Docker container is reachable
    # Default is localhost — override if running Docker on a remote machine
    qdrant_host: str = field(
        default_factory=lambda: os.getenv("QDRANT_HOST", "localhost")
    )

    # REST API port exposed by the container (-p 6333:6333 in the docker run command)
    qdrant_port: int = field(
        default_factory=lambda: int(os.getenv("QDRANT_PORT", "6333"))
    )

    # -----------------------------------------------------------
    # CLOUD MODE SETTINGS  (used when mode == "cloud")
    # -----------------------------------------------------------

    # Full HTTPS URL of your Qdrant Cloud cluster
    # Format: https://<cluster-id>.<region>.cloud.qdrant.io:6333
    qdrant_url: str = field(
        default_factory=lambda: os.getenv("QDRANT_URL", "")
    )

    # API key for authenticating with Qdrant Cloud
    # Keep this secret! Never print it in logs.
    qdrant_api_key: str = field(
        default_factory=lambda: os.getenv("QDRANT_API_KEY", "")
    )

    # -----------------------------------------------------------
    # SHARED SETTINGS
    # -----------------------------------------------------------

    # Name of the Qdrant collection (will be created if it doesn't exist)
    collection_name: str = field(
        default_factory=lambda: os.getenv("COLLECTION_NAME", "colpali_images_test")
    )

    # -----------------------------------------------------------
    # COLPALI / COLQWEN MODEL
    # -----------------------------------------------------------

    # HuggingFace model ID — must match Phase_2 config
    colqwen_model: str = field(
        default_factory=lambda: os.getenv("COLQWEN_MODEL", "vidore/colqwen2-v1.0")
    )

    # Projection dimension of ColQwen patch embeddings.
    # ColQwen2 (v1.0) and ColQwen2.5 both output 128-dimensional embeddings.
    # You can verify this at runtime: embedding.shape[-1]
    embedding_dim: int = 128

    # Name of the vector field inside the Qdrant collection.
    # A collection can store multiple named vectors (e.g., "colpali", "clip", etc.)
    # Using a descriptive name keeps things clear.
    vector_name: str = "colpali_multivec"

    # -----------------------------------------------------------
    # IMAGE INPUT
    # -----------------------------------------------------------

    # Directory containing the images to index
    input_dir: Path = field(
        default_factory=lambda: Path(__file__).parent / "input"
    )

    # Image file extensions that will be loaded
    image_extensions: tuple = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")

    # -----------------------------------------------------------
    # SEARCH SETTINGS
    # -----------------------------------------------------------

    # How many top results to return per query
    top_k: int = 5

    # Minimum score to include a result (None = no threshold filtering)
    score_threshold: float = None

    # -----------------------------------------------------------
    # MODEL LOADING (mirrors Phase_2 ColQwen config)
    # -----------------------------------------------------------

    # PyTorch dtype for the ColQwen model weights.
    # - "bfloat16" : preferred on modern GPUs (Ampere+), same as Phase_2 default
    # - "float16"  : works on older GPUs
    # - "float32"  : always safe, even on CPU (2x more RAM than float16)
    torch_dtype: str = "bfloat16"

    # Model weight quantization (uses BitsAndBytes — same options as Phase_2)
    # NOTE: This is DIFFERENT from Qdrant's vector storage quantization!
    #   - Model weight quantization  → reduces GPU memory used by the neural network
    #   - Qdrant storage quantization → reduces disk/RAM used by stored vectors in DB
    load_in_4bit: bool = False   # 4-bit NF4 quantization (needs bitsandbytes)
    # 8-bit int8 is ON by default — ~8 GB VRAM instead of ~16 GB, minimal accuracy loss.
    # BitsAndBytes handles device placement; the explicit .to("cuda") is skipped automatically.
    # Set False only if bitsandbytes is not installed or you want full bfloat16 precision.
    load_in_8bit: bool = True    # 8-bit LLM.int8() quantization (needs bitsandbytes)

    # -----------------------------------------------------------
    # INFERENCE MODE
    # -----------------------------------------------------------
    # "local"  — load ColQwen2 directly on this machine (requires a GPU).
    # "remote" — call a remote HTTP API server that hosts the model on a GPU.
    #            Set INFERENCE_URL to the server base URL, e.g. http://10.0.0.5:8080
    #
    # The remote server must expose:
    #   POST /embed/image  { "image_base64": "..." }  → { "embedding": [[...], ...] }
    #   POST /embed/query  { "query_text":   "..." }  → { "embedding": [[...], ...] }
    #
    # Use "remote" in production to keep the model on a dedicated GPU server
    # (see README Section 5 for a minimal FastAPI server example).
    inference_mode: str = field(
        default_factory=lambda: os.environ.get("INFERENCE_MODE", "local").strip().lower()
    )
    inference_url: str = field(
        default_factory=lambda: os.environ.get("INFERENCE_URL", "http://localhost:8080").strip()
    )


    # -----------------------------------------------------------

    def build_client(self):
        """
        Build and return a configured QdrantClient based on the current mode.

        DOCKER mode:
          QdrantClient(host="localhost", port=6333)
          → No API key needed; the local container trusts all connections.

        CLOUD mode:
          QdrantClient(url="https://...", api_key="...")
          → Authenticates over HTTPS; the API key is sent as a header.

        Usage:
            from config import cfg
            client = cfg.build_client()   # works for both modes automatically
        """
        from qdrant_client import QdrantClient

        if self.mode == "docker":
            logging.getLogger(__name__).info(
                f"[Qdrant] Mode=DOCKER  →  http://{self.qdrant_host}:{self.qdrant_port}"
            )
            return QdrantClient(
                host=self.qdrant_host,
                port=self.qdrant_port,
                timeout=30,
            )
        else:
            # cloud mode
            key = self.qdrant_api_key
            masked = (key[:6] + "..." + key[-4:]) if len(key) > 10 else "***"
            logging.getLogger(__name__).info(
                f"[Qdrant] Mode=CLOUD  →  {self.qdrant_url}  key={masked}"
            )
            return QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key,
                timeout=30,
            )

    # -----------------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------------

    def validate(self) -> None:
        """
        Check that required settings are filled in for the chosen mode.
        Raises ValueError with a clear, actionable error message.
        """
        valid_modes = ("docker", "cloud")
        if self.mode not in valid_modes:
            raise ValueError(
                f"\n[CONFIG ERROR] QDRANT_MODE='{self.mode}' is not valid.\n"
                f"  Set QDRANT_MODE to one of: {valid_modes}\n"
                f"  Edit your .env file and re-run."
            )

        if self.mode == "docker":
            # For Docker mode we only need host + port, which have safe defaults.
            # Alert if host looks like it was never changed from a placeholder.
            if not self.qdrant_host:
                raise ValueError(
                    "\n[CONFIG ERROR] QDRANT_HOST is empty!\n"
                    "  For Docker mode, set QDRANT_HOST=localhost (or your Docker host IP)"
                )
        else:
            # Cloud mode requires URL + API key
            if not self.qdrant_url or self.qdrant_url.startswith("https://your-cluster"):
                raise ValueError(
                    "\n[CONFIG ERROR] QDRANT_URL is not set (or still contains the placeholder)!\n"
                    "  1. Go to https://cloud.qdrant.io/ and create a cluster\n"
                    "  2. Copy the cluster URL into QDRANT_URL in your .env file\n"
                    "  3. Re-run the script"
                )
            if not self.qdrant_api_key or self.qdrant_api_key == "your-api-key-here":
                raise ValueError(
                    "\n[CONFIG ERROR] QDRANT_API_KEY is not set (or still contains the placeholder)!\n"
                    "  1. Go to https://cloud.qdrant.io/ → API Keys\n"
                    "  2. Generate a key and paste it into QDRANT_API_KEY in your .env file\n"
                    "  3. Re-run the script"
                )

    def __repr__(self) -> str:
        """
        Safe string representation — masks the API key so it's not accidentally logged.
        """
        key = self.qdrant_api_key
        masked = (key[:6] + "..." + key[-4:]) if len(key) > 10 else "***"
        if self.mode == "docker":
            conn = f"docker  →  {self.qdrant_host}:{self.qdrant_port}"
        else:
            conn = f"cloud   →  {self.qdrant_url}  (key={masked})"
        return (
            f"Config(\n"
            f"  mode           = '{self.mode}'\n"
            f"  connection     = {conn}\n"
            f"  collection     = '{self.collection_name}'\n"
            f"  model          = '{self.colqwen_model}'\n"
            f"  embedding_dim  = {self.embedding_dim}\n"
            f"  vector_name    = '{self.vector_name}'\n"
            f"  input_dir      = '{self.input_dir}'\n"
            f"  top_k          = {self.top_k}\n"
            f"  torch_dtype    = '{self.torch_dtype}'\n"
            f"  load_in_4bit   = {self.load_in_4bit}\n"
            f"  load_in_8bit   = {self.load_in_8bit}\n"
            f")"
        )


# -----------------------------------------------------------
# MODULE-LEVEL SINGLETON
# -----------------------------------------------------------
# Import `cfg` in any script to get the shared config:
#   from config import cfg
cfg = Config()
