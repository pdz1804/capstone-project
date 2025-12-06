"""
Text Chunking for RAG Systems

Splits documents into smaller chunks using recursive character text splitting
for better retrieval performance.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

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
    
    def split_text(self, text: str) -> List[str]:
        """
        Split text into chunks.
        
        Args:
            text: The text to split
            
        Returns:
            List of text chunks
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
        
        return processed_chunks
    
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
        
        text_chunks = self.split_text(text)
        
        chunks = []
        for i, chunk_text in enumerate(text_chunks):
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
                    'total_chunks': len(text_chunks),
                    'source': source,
                    'char_start': sum(len(text_chunks[j]) for j in range(i)),
                    'char_length': len(chunk_text)
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

