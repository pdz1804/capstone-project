"""
PDF Preprocessor for RAG Pipeline

Converts the JSON output of ``pdf_reader.py`` (hierarchical heading tree)
into the RAG-ready directory structure expected by the retrieval pipeline:

    stage4_rag_ready/
        <doc_id>/
            <doc_id>.md          <- combined Markdown (all sections)
            pdf_chunks.json      <- pre-built chunks with heading metadata
            pdf_manifest.json    <- identifies this as a born-digital PDF
            images/              <- extracted images (copied from parsed dir)

Mirrors ``docx_preprocessor.py`` since both parsers produce the same
heading-tree JSON format.
"""

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .pdf_chunker import PdfTableChunker, PdfChunkingConfig
from .docx_chunker import IMAGE_PATH_PATTERN

logger = logging.getLogger(__name__)


class PdfPreprocessor:
    """
    Convert parsed PDF JSON -> RAG-ready folder structure.

    Usage::

        preprocessor = PdfPreprocessor(output_dir="stage4_rag_ready")
        preprocessor.process_pdf_json(
            json_path="output/pdf_parsed/report.json",
            original_pdf_path="input/report.pdf",
        )
    """

    def __init__(
        self,
        output_dir: Union[str, Path],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        max_table_chunk_size: int = 2000,
        use_llm_fallback: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.use_llm_fallback = use_llm_fallback
        self.llm_client = None
        if self.use_llm_fallback and OPENAI_AVAILABLE:
            import os
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.llm_client = OpenAI(api_key=api_key)
            else:
                logger.warning("OPENAI_API_KEY not found; LLM fallback disabled.")

        self.chunker = PdfTableChunker(
            PdfChunkingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                max_table_chunk_size=max_table_chunk_size,
            )
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_pdf_json(
        self,
        json_path: Union[str, Path],
        original_pdf_path: Optional[Union[str, Path]] = None,
        doc_id: Optional[str] = None,
        pdf_classification: Optional[Dict] = None,
    ) -> Dict:
        """
        Process a single parsed PDF JSON file into RAG-ready format.

        Args:
            json_path: Path to the JSON produced by ``pdf_reader``.
            original_pdf_path: Path to the original PDF file (for metadata).
            doc_id: Override document ID. Defaults to JSON file stem.
            pdf_classification: Classification metadata from ``pdf_classifier``
                                (included in manifest for diagnostics).

        Returns:
            Summary dict with ``doc_id``, ``num_sections``, ``num_chunks``,
            ``num_images``, ``output_folder``.
        """
        json_path = Path(json_path)
        if not json_path.exists():
            raise FileNotFoundError(f"PDF JSON not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            tree: List[Dict] = json.load(f)

        if doc_id is None:
            doc_id = json_path.stem

        source = str(original_pdf_path) if original_pdf_path else str(json_path)
        uploaded_ts = datetime.now().isoformat()

        # 1. Create output folder
        doc_folder = self.output_dir / doc_id
        doc_folder.mkdir(parents=True, exist_ok=True)

        # 1.5 LLM Fallback for flat documents (no headings detected)
        if self._is_flat_tree(tree) and self.llm_client:
            logger.info("Flat PDF tree detected. Invoking LLM fallback to restructure headings...")
            flat_md = self._build_markdown(tree, doc_id)
            enriched_md = self._enrich_markdown_with_llm(flat_md)
            if enriched_md:
                tree = self._markdown_to_tree(enriched_md)
                logger.info("Successfully rebuilt tree via LLM.")

        # 2. Copy images and rewrite paths in the tree
        # Images are saved by pdf_reader to {json_dir}/_parsed/{stem}/images/
        parsed_images_dir = json_path.parent / "_parsed" / doc_id
        image_paths = self._collect_and_copy_images(tree, doc_folder, parsed_images_dir)
        self._rewrite_image_paths(tree, doc_folder / "images")

        # 3. Build combined Markdown
        md_content = self._build_markdown(tree, doc_id)
        md_path = doc_folder / f"{doc_id}.md"
        md_path.write_text(md_content, encoding="utf-8")
        logger.info(f"Wrote combined Markdown: {md_path}")

        # 4. Chunk with table-aware / heading-aware chunker
        chunks = self.chunker.chunk_pdf_json(
            tree,
            doc_id=doc_id,
            source=source,
            uploaded_timestamp=uploaded_ts,
        )

        # 5. Save pre-built chunks
        num_sections = self._count_sections(tree)
        chunks_data = {
            "metadata": {
                "doc_id": doc_id,
                "source": source,
                "num_sections": num_sections,
                "total_chunks": len(chunks),
                "chunking_config": {
                    "chunk_size": self.chunker.docx_config.chunk_size,
                    "chunk_overlap": self.chunker.docx_config.chunk_overlap,
                    "max_table_chunk_size": self.chunker.docx_config.max_table_chunk_size,
                },
                "created_at": uploaded_ts,
            },
            "chunks": chunks,
        }
        chunks_path = doc_folder / "pdf_chunks.json"
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Wrote {len(chunks)} chunks: {chunks_path}")

        # 6. Write manifest
        manifest = {
            "document_type": "pdf_document",
            "doc_id": doc_id,
            "source": source,
            "num_sections": num_sections,
            "has_pdf_chunks": True,
            "has_images": len(image_paths) > 0,
            "num_images": len(image_paths),
            "consolidated_at": uploaded_ts,
            "source_stage": "pdf_preprocessor",
        }
        if pdf_classification:
            manifest["pdf_type"] = pdf_classification.get("pdf_type", "born_digital")
            manifest["pdf_version"] = pdf_classification.get("pdf_version", "unknown")
            manifest["classification_confidence"] = pdf_classification.get("confidence", 0)

        manifest_path = doc_folder / "pdf_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        summary = {
            "doc_id": doc_id,
            "num_sections": num_sections,
            "num_chunks": len(chunks),
            "num_images": len(image_paths),
            "output_folder": str(doc_folder),
        }
        logger.info(f"PDF preprocessor complete: {summary}")
        return summary

    # ------------------------------------------------------------------
    # Markdown builder (same logic as DocxPreprocessor)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_markdown(
        tree: List[Dict], doc_id: str, depth: int = 0
    ) -> str:
        parts: List[str] = []
        if depth == 0:
            parts.append(f"# {doc_id}\n")

        for node in tree:
            heading = node.get("heading_text", "")
            level = node.get("heading_level", 1)
            content = node.get("content", "").strip()
            children = node.get("children", [])

            if heading:
                md_level = min(level + 1, 6)
                parts.append(f"\n{'#' * md_level} {heading}\n")

            if content:
                parts.append(content)
                parts.append("")

            if children:
                child_md = PdfPreprocessor._build_markdown(
                    children, doc_id, depth=depth + 1
                )
                parts.append(child_md)

        return "\n".join(parts)

    def _is_flat_tree(self, tree: List[Dict]) -> bool:
        if not tree:
            return True
        for node in tree:
            if node.get("children"):
                return False
        return True

    def _enrich_markdown_with_llm(self, text: str) -> Optional[str]:
        if not self.llm_client:
            return None

        prompt = (
            "You are a document structuring assistant. The following text was extracted from a PDF "
            "but lost its structural headings. Please inject appropriate Markdown headings (#, ##, ###) "
            "to reflect logical sections, topics, or pseudo-headings based on the content's natural formatting gaps. "
            "Do NOT summarize, hallucinate, alter, delete, or rewrite any of the actual text or placeholders (e.g., [START_IMAGE_PATH]). "
            "Just output the exact original text, but with appropriate Markdown heading lines injected where they belong:\n\n"
            f"{text}"
        )

        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            result = response.choices[0].message.content
            if result.startswith("```markdown\n") and result.endswith("```"):
                result = result[12:-3]
            elif result.startswith("```\n") and result.endswith("```"):
                result = result[4:-3]
            return result.strip()
        except Exception as e:
            logger.error(f"Failed to enrich markdown with LLM: {str(e)}")
            return None

    def _markdown_to_tree(self, md_text: str) -> List[Dict]:
        tree = []
        stack = []
        current_content = []

        def flush_content():
            if current_content and stack:
                stack[-1][1]["content"] += "\n" + "\n".join(current_content)
            elif current_content:
                tree.append({
                    "heading_text": "",
                    "heading_level": 0,
                    "content": "\n".join(current_content),
                    "children": []
                })
            current_content.clear()

        for line in md_text.splitlines():
            m = re.match(r"^(#{1,6})\s+(.*)$", line)
            if m:
                flush_content()
                level = len(m.group(1))
                heading_text = m.group(2).strip()
                node = {
                    "heading_text": heading_text,
                    "heading_level": level,
                    "content": "",
                    "children": []
                }
                while stack and stack[-1][0] >= level:
                    stack.pop()
                if stack:
                    stack[-1][1]["children"].append(node)
                else:
                    tree.append(node)
                stack.append((level, node))
            else:
                current_content.append(line)

        flush_content()
        return tree

    # ------------------------------------------------------------------
    # Counting
    # ------------------------------------------------------------------

    @staticmethod
    def _count_sections(tree: List[Dict]) -> int:
        count = 0
        for node in tree:
            count += 1
            children = node.get("children", [])
            if children:
                count += PdfPreprocessor._count_sections(children)
        return count

    # ------------------------------------------------------------------
    # Image handling (same logic as DocxPreprocessor)
    # ------------------------------------------------------------------

    def _collect_and_copy_images(
        self, tree: List[Dict], doc_folder: Path,
        parsed_dir: Optional[Path] = None,
    ) -> List[str]:
        all_image_paths = self._gather_image_paths(tree)
        if not all_image_paths:
            return []

        images_dir = doc_folder / "images"
        images_dir.mkdir(exist_ok=True)

        copied = []
        for img_entry in all_image_paths:
            path_str = img_entry.split("|")[0].strip()
            img_path = Path(path_str)

            # Try absolute path first, then resolve relative to parsed dir
            if not img_path.exists() and parsed_dir and not img_path.is_absolute():
                img_path = parsed_dir / path_str

            if img_path.exists():
                dest = images_dir / img_path.name
                try:
                    shutil.copy2(img_path, dest)
                    copied.append(str(img_path))
                    logger.debug(f"Copied image: {img_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to copy image {img_path}: {e}")
            else:
                logger.debug(f"Image not found: {path_str}")
                copied.append(path_str)

        logger.info(f"Collected {len(copied)} images into {images_dir}")
        return copied

    @staticmethod
    def _rewrite_image_paths(tree: List[Dict], images_dir: Path) -> None:
        for node in tree:
            content = node.get("content", "")
            if "[START_IMAGE_PATH]" in content:
                def _replace(m: 're.Match') -> str:
                    entry = m.group(1).strip()
                    path_str = entry.split("|")[0].strip()
                    img_name = Path(path_str).name
                    new_path = str(images_dir / img_name)
                    parts = entry.split("|")
                    if len(parts) > 1:
                        return f"[START_IMAGE_PATH] {new_path}|{parts[1].strip()} [END_IMAGE_PATH]"
                    return f"[START_IMAGE_PATH] {new_path} [END_IMAGE_PATH]"
                node["content"] = re.sub(
                    r"\[START_IMAGE_PATH\]\s*(.*?)\s*\[END_IMAGE_PATH\]",
                    _replace,
                    content,
                )
            children = node.get("children", [])
            if children:
                PdfPreprocessor._rewrite_image_paths(children, images_dir)

    @staticmethod
    def _gather_image_paths(tree: List[Dict]) -> List[str]:
        paths: List[str] = []
        for node in tree:
            content = node.get("content", "")
            paths.extend(IMAGE_PATH_PATTERN.findall(content))
            children = node.get("children", [])
            if children:
                paths.extend(PdfPreprocessor._gather_image_paths(children))
        return paths


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def preprocess_pdf_for_rag(
    json_path: Union[str, Path],
    output_dir: Union[str, Path],
    original_pdf_path: Optional[Union[str, Path]] = None,
    doc_id: Optional[str] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    max_table_chunk_size: int = 2000,
    pdf_classification: Optional[Dict] = None,
) -> Dict:
    """One-call convenience to preprocess a PDF JSON for the RAG pipeline."""
    preprocessor = PdfPreprocessor(
        output_dir=output_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_table_chunk_size=max_table_chunk_size,
    )
    return preprocessor.process_pdf_json(
        json_path=json_path,
        original_pdf_path=original_pdf_path,
        doc_id=doc_id,
        pdf_classification=pdf_classification,
    )
