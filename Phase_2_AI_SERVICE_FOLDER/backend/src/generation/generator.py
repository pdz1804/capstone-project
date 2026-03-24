"""
RAG Answer Generator with Citation Support

Generates answers from retrieved context using LLMs (GPT-4o-mini by default)
with proper citation formatting.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Configuration for answer generation."""
    
    # LLM settings
    provider: str = "openai"  # openai, azure, ollama
    model_name: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    
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
3. If the context doesn't contain enough information, say so clearly
4. Be concise but thorough
5. **OUTPUT YOUR ANSWER IN MARKDOWN FORMAT**

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
            # Extract filename from path
            filename = Path(source).name if source else 'unknown'
            
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
                    'metadata': chunk.get('metadata', {})  # Include uniform metadata
                }
                
                # Format chunk with citation marker
                text = chunk.get('text', '')
                metadata = chunk.get('metadata', {})

                # Add context hints for spreadsheet / table chunks
                context_hint = ""
                if metadata.get('document_type') == 'spreadsheet':
                    sheet = metadata.get('sheet_name', '')
                    if sheet:
                        context_hint += f" [Sheet: {sheet}]"
                    if metadata.get('is_table'):
                        context_hint += " [Table Data]"

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
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")
    
    def generate(
        self, 
        query: str, 
        retrieved_docs: List[Dict[str, Any]],
        include_citations: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Generate an answer from retrieved documents.
        
        Args:
            query: The user's question
            retrieved_docs: List of retrieved documents with 'text', 'source', 'score', 'id'
                           Image docs have 'retrieval_type': 'colqwen' and 'page', 'source_path' fields
            include_citations: Override config.enable_citations
            
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
        
        # Separate text and image documents
        text_docs = [doc for doc in retrieved_docs if doc.get('retrieval_type') != 'colqwen']
        image_docs = [doc for doc in retrieved_docs if doc.get('retrieval_type') == 'colqwen']

        # Collect image paths embedded in spreadsheet chunk metadata
        embedded_image_paths: List[str] = []
        for doc in text_docs:
            meta = doc.get('metadata', {})
            if meta.get('document_type') == 'spreadsheet' and meta.get('has_images'):
                for img_p in meta.get('image_paths', []):
                    if img_p and img_p not in embedded_image_paths:
                        embedded_image_paths.append(img_p)
        
        logger.info(f"Retrieved docs: {len(retrieved_docs)} total, {len(text_docs)} text, {len(image_docs)} images, {len(embedded_image_paths)} embedded spreadsheet images")
        
        # Debug: log image doc info (all images)
        for i, img_doc in enumerate(image_docs):
            logger.info(f"Image doc {i}: source={img_doc.get('source')}, path={img_doc.get('source_path')}, page={img_doc.get('page')}")
        
        # Prepare image paths for vision model
        image_paths = []
        image_descriptions = []
        temp_files = []  # Track temp files for cleanup
        
        for img_doc in image_docs:
            source_path = img_doc.get('source_path', '')
            page = img_doc.get('page', 1)
            source = img_doc.get('source', 'unknown')
            
            logger.debug(f"Processing image doc: {source}, page {page}, path: {source_path}")
            
            # Convert to absolute path if relative
            if source_path:
                source_path_obj = Path(source_path)
                if not source_path_obj.is_absolute():
                    # Try to resolve relative to base_dir (if set) or current working directory
                    if self.base_dir:
                        source_path_obj = self.base_dir / source_path
                        logger.debug(f"Converted relative path to absolute (base_dir): {source_path_obj}")
                    else:
                        source_path_obj = Path.cwd() / source_path
                        logger.debug(f"Converted relative path to absolute (cwd): {source_path_obj}")
                source_path = str(source_path_obj)
            
            # Try to render PDF page to image
            if source_path and Path(source_path).exists():
                logger.info(f"Rendering PDF page: {source_path} page {page}")
                temp_img = self._render_pdf_page_to_image(source_path, page)
                if temp_img:
                    image_paths.append(temp_img)
                    temp_files.append(temp_img)
                    image_descriptions.append(f"[Image {len(image_paths)}] Page {page} from {source}")
                    logger.info(f"Successfully rendered image from {source} page {page}")
                else:
                    logger.warning(f"Failed to render image from {source} page {page}")
            else:
                logger.warning(f"Source path not found or empty: {source_path}")
        
        # Add embedded images from spreadsheet chunks
        for emb_img in embedded_image_paths:
            emb_path = Path(emb_img)
            if emb_path.exists():
                image_paths.append(str(emb_path))
                image_descriptions.append(
                    f"[Image {len(image_paths)}] Embedded spreadsheet image: {emb_path.name}"
                )
                logger.info(f"Added embedded spreadsheet image: {emb_path.name}")

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
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {
                "answer": f"Error generating answer: {str(e)}",
                "citations": [],
                "files": file_map,
                "contents": chunk_map,
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
            "contents": {
                **{
                    f"[{k[0]}.{k[1]}]": {
                        "type": "text",
                        "text": v['text'][:200] + "..." if len(v['text']) > 200 else v['text'],
                        "full_text": v['text'],
                        "filename": v['filename'],
                        "score": v['score'],
                        "id": f"chunk-{k[0]}-{k[1]}",
                        "retrieval_info": v.get('retrieval_info', {}),  # Include raw scores
                        "metadata": v.get('metadata', {})  # Include uniform metadata
                    }
                    for k, v in chunk_map.items()
                },
                **{
                    f"[2.{idx}]": {
                        "type": "image",
                        "source": img_doc.get('source', 'unknown'),
                        "page": img_doc.get('page', 0),
                        "source_path": img_doc.get('source_path', ''),
                        "score": img_doc.get('score', 0),
                        "id": f"image-2-{idx}"
                    }
                    for idx, img_doc in enumerate(image_docs, 1)
                }
            },
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
                text_preview = content['text'][:100] + "..." if len(content['text']) > 100 else content['text']
                output_parts.append(f"{citation_id} {text_preview}")
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

