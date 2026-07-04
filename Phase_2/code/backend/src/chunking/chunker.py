"""
Text Chunking for RAG Systems

Splits documents into smaller chunks using recursive character text splitting
for better retrieval performance.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """Configuration for text chunking."""
    
    # Chunk size in characters
    chunk_size: int = 1000
    
    # Overlap between chunks (helps maintain context)
    chunk_overlap: int = 200
    
    # Separators for recursive splitting (in order of priority)
    separators: List[str] = field(default_factory=lambda: ["\n\n", "\n", ". ", " ", ""])
    
    # Minimum chunk size (skip very small chunks)
    min_chunk_size: int = 50
    
    # Whether to strip whitespace from chunks
    strip_whitespace: bool = True


class TextChunker:
    """
    Text chunker using recursive character text splitting.
    
    This approach splits text hierarchically:
    1. First try to split by paragraph breaks (\\n\\n)
    2. Then by line breaks (\\n)
    3. Then by sentences (. )
    4. Then by words ( )
    5. Finally by characters
    
    This preserves semantic meaning better than fixed-size splitting.
    """
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        """Initialize the chunker."""
        self.config = config or ChunkingConfig()
        
        # Try to use LangChain's splitter if available (more robust)
        self._use_langchain = False
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            self._langchain_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                separators=self.config.separators,
                length_function=len
            )
            self._use_langchain = True
            logger.info("Using LangChain RecursiveCharacterTextSplitter")
        except ImportError:
            logger.info("LangChain not available, using built-in recursive splitter")
            self._langchain_splitter = None

    def _locate_chunk_spans(self, text: str, chunks: List[str]) -> List[Dict[str, Any]]:
        """Map split chunk text back to exact character spans in the source text.

        LangChain's ``split_text`` returns only strings, and the built-in splitter
        also post-processes whitespace. For evaluation we need real source spans,
        so each emitted chunk is located with an exact search while allowing the
        next chunk to start inside the previous chunk's overlap region.
        """
        spans: List[Dict[str, Any]] = []
        previous_start = 0
        previous_end = 0

        for chunk in chunks:
            if not chunk:
                continue

            search_start = 0 if not spans else max(
                previous_start + 1,
                previous_end - self.config.chunk_overlap - len(chunk),
            )
            found_at = text.find(chunk, search_start)

            if found_at < 0 and spans:
                # Repeated text plus overlap can make the expected region hard to
                # estimate. Move just past the previous start to avoid remapping
                # to the same occurrence while still permitting overlap.
                found_at = text.find(chunk, previous_start + 1)

            if found_at < 0:
                found_at = text.find(chunk)

            if found_at < 0:
                logger.warning("Could not map chunk back to source offsets")
                start_char = None
                end_char = None
            else:
                start_char = found_at
                end_char = found_at + len(chunk)
                previous_start = start_char
                previous_end = end_char

            spans.append({
                "text": chunk,
                "start_char": start_char,
                "end_char": end_char,
                "char_start": start_char,
                "char_end": end_char,
                "char_length": len(chunk),
            })

        return spans
    
    def _split_text_recursive(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text using separators."""
        if not separators:
            # No more separators, split by chunk_size
            return self._split_by_size(text)
        
        separator = separators[0]
        remaining_separators = separators[1:]
        
        # Split by current separator
        if separator:
            parts = text.split(separator)
        else:
            # Empty separator means split by character
            parts = list(text)
        
        chunks = []
        current_chunk = ""
        
        for i, part in enumerate(parts):
            # Add separator back (except for last part)
            if separator and i < len(parts) - 1:
                part_with_sep = part + separator
            else:
                part_with_sep = part
            
            # Check if adding this part would exceed chunk size
            if len(current_chunk) + len(part_with_sep) <= self.config.chunk_size:
                current_chunk += part_with_sep
            else:
                # Current chunk is full
                if current_chunk:
                    chunks.append(current_chunk)
                
                # If the part itself is too large, recursively split it
                if len(part_with_sep) > self.config.chunk_size:
                    sub_chunks = self._split_text_recursive(part_with_sep, remaining_separators)
                    chunks.extend(sub_chunks[:-1])  # Add all but last
                    current_chunk = sub_chunks[-1] if sub_chunks else ""  # Last becomes new current
                else:
                    current_chunk = part_with_sep
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _split_by_size(self, text: str) -> List[str]:
        """Split text into fixed-size chunks."""
        chunks = []
        for i in range(0, len(text), self.config.chunk_size - self.config.chunk_overlap):
            chunk = text[i:i + self.config.chunk_size]
            if chunk:
                chunks.append(chunk)
        return chunks
    
    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """Add overlap between chunks."""
        if not chunks or self.config.chunk_overlap <= 0:
            return chunks
        
        overlapped_chunks = []
        for i, chunk in enumerate(chunks):
            if i > 0 and len(chunks[i-1]) >= self.config.chunk_overlap:
                # Add end of previous chunk as prefix
                overlap = chunks[i-1][-self.config.chunk_overlap:]
                chunk = overlap + chunk
            overlapped_chunks.append(chunk)
        
        return overlapped_chunks
    
    def split_text_with_offsets(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into chunks and include exact source character offsets.
        
        Args:
            text: The text to split
            
        Returns:
            List of dicts with text, start_char, end_char, and char_length
        """
        if not text:
            return []
        
        # Use LangChain if available
        if self._use_langchain and self._langchain_splitter:
            chunks = self._langchain_splitter.split_text(text)
        else:
            # Use built-in recursive splitter
            chunks = self._split_text_recursive(text, self.config.separators)
            chunks = self._add_overlap(chunks)
        
        # Post-process chunks
        processed_chunks = []
        for chunk in chunks:
            if self.config.strip_whitespace:
                chunk = chunk.strip()
            
            # Skip chunks that are too small
            if len(chunk) >= self.config.min_chunk_size:
                processed_chunks.append(chunk)
        
        return self._locate_chunk_spans(text, processed_chunks)

    def split_text(self, text: str) -> List[str]:
        """
        Split text into chunks.

        Args:
            text: The text to split

        Returns:
            List of text chunks
        """
        return [chunk["text"] for chunk in self.split_text_with_offsets(text)]
    
    def chunk_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk a single document.
        
        Args:
            document: Dict with 'id', 'text', 'source', and optionally other metadata
            
        Returns:
            List of chunk dicts with 'id', 'text', 'source', 'doc_id', 'chunk_index', 'metadata'
        """
        text = document.get('text', '')
        doc_id = document.get('id', 'unknown')
        source = document.get('source', '')
        
        text_chunks = self.split_text_with_offsets(text)
        
        # Derive uniform metadata fields from document
        original_file = source or document.get('original_file', '')
        original_file_format = ''
        if original_file:
            original_file_format = Path(original_file).suffix.lstrip('.').lower()
        uploaded_timestamp = document.get('uploaded_timestamp', datetime.now().isoformat())

        chunks = []
        for i, chunk_info in enumerate(text_chunks):
            chunk_text = chunk_info["text"]
            start_char = chunk_info.get("start_char")
            end_char = chunk_info.get("end_char")
            chunk_name = f"{doc_id}_chunk_{i}"
            chunk = {
                'id': f"{doc_id}_chunk_{i}",
                'text': chunk_text,
                'source': source,
                'doc_id': doc_id,
                'chunk_index': i,
                'total_chunks': len(text_chunks),
                'metadata': {
                    'doc_id': doc_id,
                    'chunk_index': i,
                    'chunk_name': chunk_name,
                    'total_chunks': len(text_chunks),
                    'source': source,
                    'char_start': start_char,
                    'char_end': end_char,
                    'start_char': start_char,
                    'end_char': end_char,
                    'char_length': len(chunk_text),
                    # --- Uniform metadata fields ---
                    'document_type': 'document',
                    'original_file': original_file,
                    'original_file_format': original_file_format,
                    'current_format': 'text',
                    'uploaded_timestamp': uploaded_timestamp,
                    'content_type': 'document_text',
                    'uniform_metadata_version': '1.0'
                }
            }
            # Copy any additional metadata from original document
            for key in document:
                if key not in ['id', 'text', 'source']:
                    chunk['metadata'][key] = document[key]
            
            chunks.append(chunk)
        
        logger.info(f"Document '{doc_id}' split into {len(chunks)} chunks")
        return chunks
    
    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk multiple documents.
        
        Args:
            documents: List of document dicts
            
        Returns:
            List of all chunks from all documents
        """
        all_chunks = []
        
        logger.info(f"Chunking {len(documents)} documents...")
        logger.info(f"  Chunk size: {self.config.chunk_size}")
        logger.info(f"  Chunk overlap: {self.config.chunk_overlap}")
        
        for doc in documents:
            doc_chunks = self.chunk_document(doc)
            all_chunks.extend(doc_chunks)
        
        logger.info(f"Created {len(all_chunks)} total chunks from {len(documents)} documents")
        return all_chunks


# Convenience functions
def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[str]:
    """
    Convenience function to chunk text.
    
    Args:
        text: Text to chunk
        chunk_size: Maximum chunk size in characters
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of text chunks
    """
    config = ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunker = TextChunker(config)
    return chunker.split_text(text)


def chunk_documents(
    documents: List[Dict[str, Any]],
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[Dict[str, Any]]:
    """
    Convenience function to chunk documents.
    
    Args:
        documents: List of document dicts with 'id', 'text', 'source'
        chunk_size: Maximum chunk size in characters
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of chunk dicts
    """
    config = ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunker = TextChunker(config)
    return chunker.chunk_documents(documents)
