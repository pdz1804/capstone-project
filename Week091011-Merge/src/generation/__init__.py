"""
Answer Generation Module

This module provides LLM-based answer generation for RAG systems
with proper citation formatting.
"""

from .generator import RAGGenerator, GenerationConfig

__all__ = [
    "RAGGenerator",
    "GenerationConfig"
]

