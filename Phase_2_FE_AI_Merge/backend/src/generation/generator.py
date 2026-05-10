"""
RAG Answer Generator with Citation Support

Generates answers from retrieved context using LLMs (GPT-4o-mini by default)
with proper citation formatting.
"""

import os
import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

from app.services.citation_uris import sanitize_metadata_for_api

logger = logging.getLogger(__name__)

BEDROCK_VISION_FALLBACK_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def _env_has_value(name: str) -> bool:
    return bool(str(os.getenv(name, "") or "").strip())


def _aws_credentials_configured() -> bool:
    # Fast-path env hints for common local/container setups.
    if any(
        _env_has_value(name)
        for name in (
            "AWS_ACCESS_KEY_ID",
            "AWS_PROFILE",
            "AWS_DEFAULT_PROFILE",
            "AWS_WEB_IDENTITY_TOKEN_FILE",
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
            "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        )
    ):
        return True

    # Fallback to boto3's full credential provider chain so shared/default
    # profile credentials are detected even when AWS_PROFILE is not set.
    try:
        import boto3

        session = boto3.Session(
            region_name=(os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION") or None)
        )
        creds = session.get_credentials()
        if creds is None:
            return False
        frozen = creds.get_frozen_credentials()
        return bool(getattr(frozen, "access_key", None) and getattr(frozen, "secret_key", None))
    except Exception:
        return False


def _looks_like_bedrock_model(model_name: str) -> bool:
    model = (model_name or "").strip().lower()
    return model.startswith(("us.", "eu.", "apac.", "zai.", "google.gemma")) or "anthropic.claude" in model


def _bedrock_model_supports_vision(model_id: str) -> bool:
    """Best-effort capability gate for Bedrock models in this app."""
    mid = str(model_id or "").strip().lower()
    if not mid:
        return True
    # Known text-only Bedrock models in our allowed set.
    if mid.startswith(("google.gemma", "zai.glm")):
        return False
    return True


def _bedrock_vision_fallback_model() -> str:
    return (os.getenv("BEDROCK_VISION_FALLBACK_MODEL") or BEDROCK_VISION_FALLBACK_MODEL).strip()


def _looks_like_bedrock_payload_too_large(exc: Exception) -> bool:
    msg = str(exc or "").lower()
    return (
        "length limit exceeded" in msg
        or "failed to buffer the request body" in msg
        or ("validationexception" in msg and "length" in msg)
    )


_MATH_BLOCK_DELIMITER_RE = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_MATH_INLINE_DELIMITER_RE = re.compile(r"\\\((.+?)\\\)")


def _normalize_math_delimiters(answer: str) -> str:
    """Normalize \(\), \[\] delimiters to markdown math $/$$ for renderer compatibility."""
    text = str(answer or "")
    if not text:
        return text

    def _block_repl(match: re.Match[str]) -> str:
        expr = (match.group(1) or "").strip()
        if not expr:
            return ""
        return f"$$\n{expr}\n$$"

    def _inline_repl(match: re.Match[str]) -> str:
        expr = (match.group(1) or "").strip()
        if not expr:
            return ""
        return f"${expr}$"

    text = _MATH_BLOCK_DELIMITER_RE.sub(_block_repl, text)
    text = _MATH_INLINE_DELIMITER_RE.sub(_inline_repl, text)
    return text


def _display_filename_from_source(source: str) -> str:
    """Basename for citations when ``source`` is a local path or ``s3://`` URI."""
    s = (source or "").strip().replace("\\", "/")
    if not s:
        return "unknown"
    if s.startswith("s3://"):
        tail = s.rsplit("/", 1)[-1]
        return tail or "unknown"
    return Path(s).name if s else "unknown"


def _format_time_hhmmss(seconds: float) -> str:
    total = max(0, int(round(float(seconds))))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _coerce_time_seconds(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _extract_time_window_label(metadata: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], str]:
    start = _coerce_time_seconds(metadata.get("start_time"))
    end = _coerce_time_seconds(metadata.get("end_time"))
    if start is None and end is None:
        return None, None, ""
    if start is not None and end is not None:
        return start, end, f"{_format_time_hhmmss(start)} - {_format_time_hhmmss(end)}"
    if start is not None:
        return start, None, f"from {_format_time_hhmmss(start)}"
    return None, end, f"until {_format_time_hhmmss(end)}"


def _image_citation_chunk(img_doc: Dict[str, Any], idx: int) -> Dict[str, Any]:
    su = (img_doc.get("storage_uri") or "").strip()
    meta = sanitize_metadata_for_api(
        {
            "source": img_doc.get("source", "unknown"),
            "source_path": img_doc.get("source_path", ""),
            "storage_uri": img_doc.get("storage_uri", ""),
            "storage_backend": img_doc.get("storage_backend", ""),
            "page": img_doc.get("page", 0),
            "total_pages": img_doc.get("total_pages", 0),
            "retrieval_type": img_doc.get("retrieval_type", "colqwen_qdrant"),
            "score": img_doc.get("score", 0),
        }
    )
    return {
        "type": "image",
        "source": img_doc.get("source", "unknown"),
        "page": img_doc.get("page", 0),
        "source_path": "" if su else img_doc.get("source_path", ""),
        "storage_uri": img_doc.get("storage_uri", ""),
        "storage_backend": img_doc.get("storage_backend", ""),
        "score": img_doc.get("score", 0),
        "id": f"image-2-{idx}",
        "metadata": meta,
    }


@dataclass
class GenerationConfig:
    """Configuration for answer generation."""
    
    # LLM settings
    provider: str = "openai"  # openai, azure, ollama, bedrock
    model_name: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    bedrock_region: Optional[str] = None
    enable_guardrails: bool = True
    
    # Generation parameters
    temperature: float = 0.0
    max_tokens: int = 2000
    
    # Citation settings
    enable_citations: bool = True
    citation_style: str = "numbered"  # numbered, inline
    
    # Base directory for resolving relative paths
    base_dir: Optional[str] = None
    
    def __post_init__(self):
        # Load API key from environment if not provided
        if self.provider == "bedrock" and _env_has_value("OPENAI_API_KEY") and not _aws_credentials_configured():
            logger.warning(
                "Generation provider configured as Bedrock, but AWS credentials are unavailable; "
                "falling back to OpenAI because OPENAI_API_KEY is set."
            )
            self.provider = "openai"
            if not self.model_name or _looks_like_bedrock_model(self.model_name):
                self.model_name = "gpt-4o-mini"

        if self.api_key is None:
            if self.provider == "openai":
                self.api_key = os.getenv("OPENAI_API_KEY")
            elif self.provider == "azure":
                self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
                self.base_url = os.getenv("AZURE_OPENAI_ENDPOINT")


# Prompt template with citation instructions
CITATION_PROMPT_TEMPLATE = """You are a helpful AI assistant that answers questions based on the provided context documents. 

IMPORTANT INSTRUCTIONS:
1. Use ONLY information from the provided context to answer the question
2. Include inline citations as MARKDOWN HYPERLINKS using the format [X.Y](#chunk-X-Y) for text chunks or [X.Y](#image-X-Y) for images
   - Text chunks start from [1.1], [1.2], etc. and use anchor #chunk-1-1, #chunk-1-2, etc.
   - Image citations start from [2.1], [2.2], etc. and use anchor #image-2-1, #image-2-2, etc.
3. Citation placement rule: place citations at the END of the sentence they support, immediately before sentence punctuation if needed.
    - Correct: "LifePak supports immune health [1.2](#chunk-1-2)."
    - Correct: "Benefits include A, B, and C [1.2](#chunk-1-2), [1.4](#chunk-1-4)."
    - Wrong: "LifePak [1.2](#chunk-1-2) supports immune health."
4. Every factual claim sentence must end with at least one supporting citation. Do not put all citations only at paragraph end.
5. If the context doesn't contain enough information, say so clearly
6. Be concise but thorough
7. **OUTPUT YOUR ANSWER IN MARKDOWN FORMAT**
8. Ensure the final answer is clean, readable Markdown (proper headings, bullets, spacing, and tables).

CRITICAL: MATHEMATICAL FORMULAS MUST USE DOLLAR SIGNS, NOT SQUARE BRACKETS
- Citations use markdown hyperlinks: [1.6](#chunk-1-6) for text or [2.3](#image-2-3) for images
- Math formulas MUST use dollar signs: $formula$ or $$formula$$
- NEVER use square brackets for math formulas like [formula] - this is WRONG
- Citation format: [X.Y](#chunk-X-Y) for text chunks, [X.Y](#image-X-Y) for images

MARKDOWN FORMATTING REQUIREMENTS:
- Use **bold** for important terms and concepts
- Use *italic* for emphasis
- Use proper markdown headings (##, ###) for sections if needed
- For mathematical formulas and equations:
  * ALWAYS use inline math with single dollar signs: $formula$ 
    Example: The score is $E = mc^2$ where $E$ is energy [1.2](#chunk-1-2)
  * ALWAYS use block math with double dollar signs for displayed equations:
    $$
    \\text{{Score}}(q, d) = \\text{{inner product}}(V_q, V_d)
    $$
    Example:
    $$
    \\text{{Score}}(q, d) = \\text{{inner product}}(V_q, V_d)
    $$
    where $V_q$ and $V_d$ are vectors [1.6](#chunk-1-6)
  * NEVER write formulas in square brackets like [formula] - this will NOT render correctly
- Use code blocks with triple backticks for code snippets
- Use bullet points or numbered lists for lists
- Ensure proper paragraph breaks with blank lines

CONTEXT DOCUMENTS:
{context}

QUESTION: {question}

Provide your answer in MARKDOWN format with inline citations as MARKDOWN HYPERLINKS referencing the source documents. 

CRITICAL FORMATTING RULES:
- Citations: Use markdown hyperlink format [X.Y](#chunk-X-Y) for text or [X.Y](#image-X-Y) for images
  - Text chunks: [1.1](#chunk-1-1), [1.2](#chunk-1-2), etc.
  - Images: [2.1](#image-2-1), [2.2](#image-2-2), etc.
- Citation placement: each supporting sentence must end with citation link(s), not in the middle of the sentence.
- Math formulas: MUST use $ for inline or $$ for block math (e.g., $V_q$ or $$\\text{{Score}} = ...$$)
- NEVER mix them up: citations = markdown hyperlinks, math = dollar signs

After your answer, list the files and contents you cited.

ANSWER FORMAT (in Markdown):
<Your answer in markdown format with inline citations as markdown hyperlinks like [1.1](#chunk-1-1) for text or [2.1](#image-2-1) for images>
<ALWAYS use $$ for block math formulas and $ for inline math - NEVER use square brackets for math>

Example of correct format:
The formula for sparse retrieval is:
$$
\\text{{Score}}(q, d) = \\text{{inner product}}(V_q, V_d)
$$
where $V_q$ and $V_d$ are sparse vectors [1.6](#chunk-1-6). For images, you might reference [2.1](#image-2-1) or [2.3](#image-2-3).

Files:
[1] <filename>
[2] <filename>
...

Contents:
[1.1] <brief excerpt from chunk> - <filename>
[1.2] <brief excerpt from chunk> - <filename>
[2.1] <brief excerpt from chunk> - <filename>
...

ANSWER:"""


SIMPLE_PROMPT_TEMPLATE = """You are a helpful AI assistant that answers questions based on the provided context.

IMPORTANT: Output your answer in MARKDOWN format.
Ensure the final answer is clean, readable Markdown (proper headings, bullets, spacing, and tables).

CRITICAL: MATHEMATICAL FORMULAS MUST USE DOLLAR SIGNS, NOT SQUARE BRACKETS
- Math formulas MUST use dollar signs: $formula$ or $$formula$$
- NEVER use square brackets for math formulas like [formula] - this is WRONG

MARKDOWN FORMATTING REQUIREMENTS:
- Use **bold** for important terms and concepts
- Use *italic* for emphasis
- Use proper markdown headings (##, ###) for sections if needed
- For mathematical formulas and equations:
  * ALWAYS use inline math with single dollar signs: $formula$ 
    Example: The score is $E = mc^2$ where $E$ is energy
  * ALWAYS use block math with double dollar signs for displayed equations:
    $$
    \\text{{Score}}(q, d) = \\text{{inner product}}(V_q, V_d)
    $$
    Example:
    $$
    \\text{{Score}}(q, d) = \\text{{inner product}}(V_q, V_d)
    $$
    where $V_q$ and $V_d$ are vectors
  * NEVER write formulas in square brackets like [formula] - this will NOT render correctly
- Use code blocks with triple backticks for code snippets
- Use bullet points or numbered lists for lists
- Ensure proper paragraph breaks with blank lines

Context:
{context}

Question: {question}

Answer based only on the provided context in MARKDOWN format. 

CRITICAL: For mathematical formulas, ALWAYS use $ for inline or $$ for block math (e.g., $V_q$ or $$\\text{{Score}} = ...$$). NEVER use square brackets for math formulas.

If the context doesn't contain enough information, say so.

Answer:"""


class RAGGenerator:
    """
    RAG Answer Generator with citation support.
    
    Uses LLMs to generate answers from retrieved context with proper
    source citations in the format [X.Y] where X is file number and Y is chunk number.
    """
    
    def __init__(self, config: Optional[GenerationConfig] = None, base_dir: Optional[str] = None):
        """Initialize the generator."""
        self.config = config or GenerationConfig()
        # Set base_dir from parameter or config
        self.base_dir = Path(base_dir) if base_dir else (Path(self.config.base_dir) if self.config.base_dir else None)
        self.client = None
        self._setup_client()
        
    def _setup_client(self):
        """Setup the LLM client based on provider."""
        if self.config.provider == "openai":
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.config.api_key)
                logger.info(f"OpenAI client initialized with model: {self.config.model_name}")
            except ImportError:
                raise ImportError("openai package required. Install with: pip install openai")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise
                
        elif self.config.provider == "azure":
            try:
                import openai
                self.client = openai.AzureOpenAI(
                    api_key=self.config.api_key,
                    api_version="2023-12-01-preview",
                    azure_endpoint=self.config.base_url
                )
                logger.info(f"Azure OpenAI client initialized")
            except ImportError:
                raise ImportError("openai package required. Install with: pip install openai")
                
        elif self.config.provider == "ollama":
            # Ollama uses requests, no special client needed
            self.client = None
            logger.info(f"Ollama provider configured with model: {self.config.model_name}")
        elif self.config.provider == "bedrock":
            self.client = None
            logger.info(
                "Bedrock provider (Converse API); model_id=%s region=%s",
                self.config.model_name,
                self.config.bedrock_region or os.getenv("AWS_REGION") or "us-east-1",
            )
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")
    
    def _format_context_with_citations(self, retrieved_docs: List[Dict[str, Any]]) -> tuple:
        """
        Format retrieved documents into context string with citation markers.
        
        Returns:
            tuple: (formatted_context, file_map, chunk_map)
        """
        # Group chunks by source file
        file_chunks = {}
        for doc in retrieved_docs:
            source = doc.get('source', 'unknown')
            filename = _display_filename_from_source(str(source))
            
            if filename not in file_chunks:
                file_chunks[filename] = []
            file_chunks[filename].append(doc)
        
        # Create file numbering
        file_map = {}  # filename -> file_number
        chunk_map = {}  # (file_number, chunk_number) -> doc info
        
        context_parts = []
        file_number = 1
        
        for filename, chunks in file_chunks.items():
            file_map[filename] = file_number
            
            for chunk_idx, chunk in enumerate(chunks, 1):
                citation_id = f"[{file_number}.{chunk_idx}]"
                chunk_map[(file_number, chunk_idx)] = {
                    'filename': filename,
                    'text': chunk.get('text', ''),
                    'score': chunk.get('score', 0),
                    'id': chunk.get('id', ''),
                    'retrieval_info': chunk.get('retrieval_info', {}),  # Include raw scores
                    'metadata': sanitize_metadata_for_api(dict(chunk.get('metadata') or {})),
                }
                
                # Format chunk with citation marker
                text = chunk.get('text', '')
                metadata = sanitize_metadata_for_api(dict(chunk.get('metadata') or {}))
                start_t, end_t, time_label = _extract_time_window_label(metadata)
                chunk_map[(file_number, chunk_idx)]['start_time'] = start_t
                chunk_map[(file_number, chunk_idx)]['end_time'] = end_t
                chunk_map[(file_number, chunk_idx)]['time_range_label'] = time_label

                # Add context hints for spreadsheet / table chunks
                context_hint = ""
                if metadata.get('document_type') == 'spreadsheet':
                    sheet = metadata.get('sheet_name', '')
                    if sheet:
                        context_hint += f" [Sheet: {sheet}]"
                    if metadata.get('is_table'):
                        context_hint += " [Table Data]"
                if time_label:
                    context_hint += f" [Time: {time_label}]"

                context_parts.append(f"{citation_id} Source: {filename}{context_hint}\n{text}\n")
            
            file_number += 1
        
        formatted_context = "\n---\n".join(context_parts)
        return formatted_context, file_map, chunk_map
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        response = self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        return response.choices[0].message.content
    
    def _call_openai_with_images(self, prompt: str, image_paths: List[str]) -> str:
        """Call OpenAI API with images for vision-based generation."""
        import base64
        
        # Build content array with text and images
        content = [{"type": "text", "text": prompt}]
        
        for img_path in image_paths:
            try:
                # Read and encode image
                with open(img_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode('utf-8')
                
                # Determine media type
                ext = Path(img_path).suffix.lower()
                media_type = "image/png" if ext == ".png" else "image/jpeg"
                
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{img_data}",
                        "detail": "high"
                    }
                })
                logger.debug(f"Added image to prompt: {img_path}")
            except Exception as e:
                logger.warning(f"Failed to load image {img_path}: {e}")
        
        response = self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": "user", "content": content}],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        return response.choices[0].message.content
    
    def _render_pdf_page_to_image(self, pdf_path: str, page: int) -> Optional[str]:
        """Render a PDF page to a temporary image file."""
        import tempfile
        try:
            from pdf2image import convert_from_path
            
            images = convert_from_path(
                pdf_path,
                first_page=page,
                last_page=page,
                dpi=150
            )
            
            if images:
                # Save to temp file
                temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                images[0].save(temp_file.name, 'PNG')
                return temp_file.name
        except Exception as e:
            logger.warning(f"Failed to render PDF page: {e}")
        
        return None

    def _materialize_storage_uri_to_temp(self, storage_uri: str, storage_user_id: Optional[str]) -> Optional[str]:
        """Download an S3 object to a temp file for pdf2image / vision (tenant-scoped read)."""
        import os
        import tempfile

        uri = (storage_uri or "").strip()
        if not uri.startswith("s3://") or not storage_user_id:
            return None
        try:
            from app.storage import get_file_storage
            from app.storage.service import S3FileStorage, parse_s3_uri
        except Exception as e:
            logger.warning("Storage import failed for vision materialize: %s", e)
            return None
        st = get_file_storage(storage_user_id)
        if not isinstance(st, S3FileStorage):
            return None
        parsed = parse_s3_uri(uri)
        if not parsed:
            return None
        bucket, key = parsed
        if not st.can_read_object(bucket, key):
            logger.warning("Vision: access denied for storage_uri=%s", uri)
            return None
        try:
            body, _ = st.read_object(bucket, key)
        except Exception as e:
            logger.warning("Vision: S3 read failed for %s: %s", uri, e)
            return None
        suffix = Path(key).suffix.lower() or ".bin"
        fd, name = tempfile.mkstemp(suffix=suffix)
        try:
            os.write(fd, body)
        finally:
            os.close(fd)
        return name
    
    def _call_azure(self, prompt: str) -> str:
        """Call Azure OpenAI API."""
        response = self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        return response.choices[0].message.content
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API."""
        import requests
        
        base_url = self.config.base_url or "http://localhost:11434"
        url = f"{base_url}/api/generate"
        
        data = {
            "model": self.config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature
            }
        }
        
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()["response"]

    def _bedrock_runtime(self):
        import boto3

        region = (self.config.bedrock_region or os.getenv("AWS_REGION") or "us-east-1").strip()
        return boto3.client("bedrock-runtime", region_name=region)

    def _extract_converse_text(self, resp: Dict[str, Any]) -> str:
        parts: List[str] = []
        msg = (resp.get("output") or {}).get("message") or {}
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
        return "".join(parts).strip()

    def _call_bedrock(self, prompt: str, image_paths: Optional[List[str]] = None) -> str:
        from agent.bedrock_guardrail_integration import get_guardrail_config
        
        rt = self._bedrock_runtime()
        
        def _invoke(content_payload: List[Dict[str, Any]]) -> str:
            request = {
                "modelId": self.config.model_name,
                "messages": [{"role": "user", "content": content_payload}],
                "inferenceConfig": {
                    "maxTokens": int(self.config.max_tokens),
                    "temperature": float(self.config.temperature),
                },
            }
            # Add guardrail if enabled for this generator instance.
            guardrail_cfg = get_guardrail_config() if self.config.enable_guardrails else None
            if guardrail_cfg:
                request["guardrailConfig"] = guardrail_cfg
            
            resp = rt.converse(**request)
            return self._extract_converse_text(resp)

        content: List[Dict[str, Any]] = [{"text": prompt}]
        if image_paths:
            for img_path in image_paths:
                try:
                    p = Path(img_path)
                    data = p.read_bytes()
                    ext = p.suffix.lower()
                    fmt = "png" if ext == ".png" else "jpeg"
                    content.append({"image": {"format": fmt, "source": {"bytes": data}}})
                except Exception as e:
                    logger.warning("Bedrock: skip image %s: %s", img_path, e)

        try:
            return _invoke(content)
        except Exception as e:
            if image_paths and _looks_like_bedrock_payload_too_large(e):
                logger.warning(
                    "Bedrock vision payload too large; retrying without images (model=%s, images=%s)",
                    self.config.model_name,
                    len(image_paths),
                )
                return _invoke([{"text": prompt}])
            raise

    def _build_contents_payload(
        self,
        chunk_map: Dict[Tuple[int, int], Dict[str, Any]],
        image_docs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            **{
                f"[{k[0]}.{k[1]}]": {
                    "type": "text",
                    "text": v["text"][:200] + "..." if len(v["text"]) > 200 else v["text"],
                    "full_text": v["text"],
                    "filename": v["filename"],
                    "score": v["score"],
                    "id": f"chunk-{k[0]}-{k[1]}",
                    "retrieval_info": v.get("retrieval_info", {}),
                    "metadata": v.get("metadata", {}),
                    "start_time": v.get("start_time"),
                    "end_time": v.get("end_time"),
                    "time_range_label": v.get("time_range_label", ""),
                }
                for k, v in chunk_map.items()
            },
            **{
                f"[2.{idx}]": _image_citation_chunk(img_doc, idx)
                for idx, img_doc in enumerate(image_docs, 1)
            },
        }
    
    def _call_llm(self, prompt: str, image_paths: List[str] = None) -> str:
        """Call the configured LLM, optionally with images."""
        if self.config.provider == "openai":
            if image_paths:
                return self._call_openai_with_images(prompt, image_paths)
            return self._call_openai(prompt)
        elif self.config.provider == "azure":
            return self._call_azure(prompt)
        elif self.config.provider == "ollama":
            return self._call_ollama(prompt)
        elif self.config.provider == "bedrock":
            return self._call_bedrock(prompt, image_paths)
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")
    
    def generate(
        self, 
        query: str, 
        retrieved_docs: List[Dict[str, Any]],
        include_citations: Optional[bool] = None,
        storage_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an answer from retrieved documents.
        
        Args:
            query: The user's question
            retrieved_docs: List of retrieved documents with 'text', 'source', 'score', 'id'
                           Image docs have 'retrieval_type': 'colqwen' and 'page', 'source_path' fields
            include_citations: Override config.enable_citations
            storage_user_id: Sanitized storage user id for downloading ``storage_uri`` objects from S3 when local cache is missing.
            
        Returns:
            Dict with 'answer', 'citations', 'files', 'contents'
        """
        use_citations = include_citations if include_citations is not None else self.config.enable_citations
        
        if not retrieved_docs:
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "citations": [],
                "files": {},
                "contents": {}
            }
        
        # Separate text and image documents (Qdrant path uses colqwen_qdrant; legacy uses colqwen)
        def _is_image_retrieval_doc(doc: Dict[str, Any]) -> bool:
            rt = (doc.get("retrieval_type") or "").lower()
            return rt in ("colqwen", "colqwen_qdrant")

        text_docs = [doc for doc in retrieved_docs if not _is_image_retrieval_doc(doc)]
        image_docs = [doc for doc in retrieved_docs if _is_image_retrieval_doc(doc)]

        # Collect image paths embedded in spreadsheet chunk metadata
        embedded_image_paths: List[str] = []
        for doc in text_docs:
            meta = doc.get('metadata', {})
            if meta.get('document_type') == 'spreadsheet' and meta.get('has_images'):
                for img_p in meta.get('image_paths', []):
                    if img_p and img_p not in embedded_image_paths:
                        embedded_image_paths.append(img_p)
        
        logger.info(f"Retrieved docs: {len(retrieved_docs)} total, {len(text_docs)} text, {len(image_docs)} images, {len(embedded_image_paths)} embedded spreadsheet images")
        
        has_image_inputs = bool(image_docs or embedded_image_paths)
        if (
            has_image_inputs
            and self.config.provider == "bedrock"
            and not _bedrock_model_supports_vision(self.config.model_name)
        ):
            fallback_model = _bedrock_vision_fallback_model()
            if fallback_model and fallback_model != self.config.model_name:
                logger.info(
                    "Model %s is text-only but request has image inputs; falling back to vision model %s",
                    self.config.model_name,
                    fallback_model,
                )
                self.config.model_name = fallback_model

        allow_vision_inputs = not (
            self.config.provider == "bedrock" and not _bedrock_model_supports_vision(self.config.model_name)
        )
        if image_docs and not allow_vision_inputs:
            logger.info(
                "Model %s is treated as text-only; skipping %s image inputs",
                self.config.model_name,
                len(image_docs),
            )

        # Debug: log image doc info (all images). source_path is the local sync/cache path; storage_uri is canonical S3 when applicable.
        for i, img_doc in enumerate(image_docs):
            logger.info(
                "Image doc %s: source=%s page=%s storage_uri=%s local_path=%s",
                i,
                img_doc.get("source"),
                img_doc.get("page"),
                img_doc.get("storage_uri") or " ",
                img_doc.get("source_path") or " ",
            )
        
        # Prepare image paths for vision model
        image_paths = []
        image_descriptions = []
        temp_files = []  # Track temp files for cleanup

        def _prepare_image_doc(img_doc: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], List[str]]:
            local_temp_files: List[str] = []
            source_path = img_doc.get('source_path', '')
            page = img_doc.get('page', 1)
            source = img_doc.get('source', 'unknown')
            storage_uri = (img_doc.get("storage_uri") or "").strip()

            logger.debug("Processing image doc: %s, page %s, storage_uri=%s path=%s", source, page, storage_uri, source_path)

            local_file: Optional[str] = None

            if storage_user_id and storage_uri.startswith("s3://"):
                temp_download = self._materialize_storage_uri_to_temp(storage_uri, storage_user_id)
                if temp_download:
                    local_file = temp_download
                    local_temp_files.append(temp_download)

            if not local_file and source_path:
                source_path_obj = Path(source_path)
                if not source_path_obj.is_absolute():
                    if self.base_dir:
                        source_path_obj = self.base_dir / source_path
                    else:
                        source_path_obj = Path.cwd() / source_path
                source_path = str(source_path_obj)
                if Path(source_path).exists():
                    local_file = source_path

            if not local_file:
                logger.warning("No local or S3-backed file for image doc (source=%s page=%s)", source, page)
                return None, None, local_temp_files

            lp = Path(local_file)
            canon = storage_uri or local_file
            logger.info("Vision input path=%s canonical=%s page=%s", local_file, canon, page)

            if lp.suffix.lower() == ".pdf":
                temp_img = self._render_pdf_page_to_image(str(lp), page)
                if temp_img:
                    local_temp_files.append(temp_img)
                    logger.info("Rendered PDF page %s for vision model", page)
                    return temp_img, f"Page {page} from {source}", local_temp_files
                logger.warning("Failed to render PDF page %s from %s", page, source)
                return None, None, local_temp_files

            if lp.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
                logger.info("Attached raster %s for vision model", lp.name)
                return str(lp), f"{lp.name} from {source}", local_temp_files

            logger.warning("Unsupported vision source type: %s", lp.suffix)
            return None, None, local_temp_files

        if image_docs and allow_vision_inputs:
            max_workers = min(4, len(image_docs))
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                prepared = list(pool.map(_prepare_image_doc, image_docs))
            for path, desc, local_temps in prepared:
                if local_temps:
                    temp_files.extend(local_temps)
                if path and desc:
                    image_paths.append(path)
                    image_descriptions.append(f"[Image {len(image_paths)}] {desc}")
        
        # Add embedded images from spreadsheet chunks only for vision-capable models.
        if allow_vision_inputs:
            for emb_img in embedded_image_paths:
                emb_path = Path(emb_img)
                if emb_path.exists():
                    image_paths.append(str(emb_path))
                    image_descriptions.append(
                        f"[Image {len(image_paths)}] Embedded spreadsheet image: {emb_path.name}"
                    )
                    logger.info(f"Added embedded spreadsheet image: {emb_path.name}")
        elif embedded_image_paths:
            logger.info(
                "Model %s is treated as text-only; skipping %s embedded spreadsheet image inputs",
                self.config.model_name,
                len(embedded_image_paths),
            )

        # Format context from text docs only
        if use_citations:
            formatted_context, file_map, chunk_map = self._format_context_with_citations(text_docs)
            
            # Add image references to context with proper citation numbering (starting from 2.x)
            if image_descriptions:
                image_context = "\n\nRelevant Images (see attached):\n"
                for idx, desc in enumerate(image_descriptions, 1):
                    image_context += f"[2.{idx}] {desc}\n"
                formatted_context += image_context
            
            prompt = CITATION_PROMPT_TEMPLATE.format(
                context=formatted_context if formatted_context.strip() else "No text context available. Please analyze the provided images.",
                question=query
            )
        else:
            # Simple context without citation markers
            context = "\n\n".join([doc.get('text', '') for doc in text_docs])
            
            # Add image references
            if image_descriptions:
                context += "\n\nRelevant Images (see attached):\n" + "\n".join(image_descriptions)
            
            prompt = SIMPLE_PROMPT_TEMPLATE.format(
                context=context if context.strip() else "No text context available. Please analyze the provided images.",
                question=query
            )
            file_map = {}
            chunk_map = {}
        
        # If we have images, add instruction to analyze them
        if image_paths:
            prompt = f"""You are analyzing both text documents and images to answer a question.
For images, carefully examine any diagrams, charts, figures, or visual content shown.
Extract and describe relevant information from the images to help answer the question.

{prompt}

CRITICAL FORMATTING RULES:
- Output your answer in MARKDOWN format
- For mathematical formulas: ALWAYS use $ for inline math or $$ for block math (e.g., $V_q$ or $$text{{Score}} = ...$$)
- NEVER use square brackets for math formulas like [formula] - only use markdown hyperlinks for citations
- Citations MUST be markdown hyperlinks: [1.1](#chunk-1-1) for text chunks, [2.1](#image-2-1) for images
- If the answer can be found in the images (like diagrams, architecture figures, etc.), describe what you see and use that information to answer."""
        
        # Generate answer
        logger.info(f"Generating answer for query: {query[:50]}... (with {len(image_paths)} images)")
        try:
            answer = self._call_llm(prompt, image_paths if image_paths else None)
            answer = _normalize_math_delimiters(answer)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            files_payload = {v: k for k, v in file_map.items()}
            contents_payload = self._build_contents_payload(chunk_map, image_docs)
            return {
                "answer": f"Error generating answer: {str(e)}",
                "citations": [],
                "files": files_payload,
                "contents": contents_payload,
                "error": str(e)
            }
        finally:
            # Cleanup temp files
            import os
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except:
                    pass
        
        # Build response
        result = {
            "answer": answer,
            "query": query,
            "num_sources": len(retrieved_docs),
            "num_images": len(image_paths),
            "files": {v: k for k, v in file_map.items()},  # file_number -> filename
            "contents": self._build_contents_payload(chunk_map, image_docs),
            "retrieved_docs": retrieved_docs
        }
        
        logger.info(f"Answer generated successfully with {len(file_map)} source files and {len(image_paths)} images")
        return result
    
    def format_answer_for_display(self, result: Dict[str, Any]) -> str:
        """
        Format the generation result for display.
        
        Args:
            result: Output from generate()
            
        Returns:
            Formatted string for display
        """
        output_parts = []
        
        # Main answer
        output_parts.append("=" * 60)
        output_parts.append("📝 ANSWER")
        output_parts.append("=" * 60)
        output_parts.append(result.get("answer", "No answer generated"))
        
        # Files section
        if result.get("files"):
            output_parts.append("\n" + "-" * 60)
            output_parts.append("📁 FILES")
            output_parts.append("-" * 60)
            for file_num, filename in sorted(result["files"].items()):
                output_parts.append(f"[{file_num}] {filename}")
        
        # Contents section
        if result.get("contents"):
            output_parts.append("\n" + "-" * 60)
            output_parts.append("📄 CONTENTS")
            output_parts.append("-" * 60)
            for citation_id, content in sorted(result["contents"].items()):
                output_parts.append(f"{citation_id} {content['text']}")
                output_parts.append(f"    └─ {content['filename']} (score: {content['score']:.4f})")
        
        output_parts.append("=" * 60)
        
        return "\n".join(output_parts)


def create_generator(
    provider: str = "openai",
    model_name: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    enable_citations: bool = True
) -> RAGGenerator:
    """
    Convenience function to create a RAGGenerator.
    
    Args:
        provider: LLM provider (openai, azure, ollama)
        model_name: Model name to use
        api_key: API key (uses env var if not provided)
        enable_citations: Whether to include citations in answers
        
    Returns:
        Configured RAGGenerator instance
    """
    config = GenerationConfig(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        enable_citations=enable_citations
    )
    return RAGGenerator(config)
