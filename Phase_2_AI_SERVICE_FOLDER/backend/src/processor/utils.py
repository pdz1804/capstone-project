"""
Utility functions and helpers for the DocumentProcessor.

This module contains helper functions, constants, and utilities
used throughout the document processing pipeline.
"""

import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import hashlib
import json
from datetime import datetime


# File type mappings for better categorization
MIME_TYPE_CATEGORIES = {
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'office',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'office',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'office',
    'application/msword': 'office',
    'application/vnd.ms-powerpoint': 'office',
    'application/vnd.ms-excel': 'office',
    'image/png': 'image',
    'image/jpeg': 'image',
    'image/tiff': 'image',
    'image/bmp': 'image',
    'audio/wav': 'audio',
    'audio/mpeg': 'audio',
    'audio/mp4': 'audio',
    'text/html': 'web',
    'text/plain': 'text',
    'text/markdown': 'text'
}

# Language codes for OCR
LANGUAGE_CODES = {
    'english': 'eng',
    'vietnamese': 'vie',
    'chinese': 'chi_sim',
    'japanese': 'jpn',
    'korean': 'kor',
    'french': 'fra',
    'german': 'deu',
    'spanish': 'spa'
}

# Common file extensions and their processing requirements
FILE_PROCESSING_HINTS = {
    '.pdf': {'needs_ocr': True, 'supports_vlm': True, 'has_layout': True},
    '.docx': {'needs_ocr': False, 'supports_vlm': False, 'has_layout': True},
    '.pptx': {'needs_ocr': False, 'supports_vlm': True, 'has_layout': True},
    '.xlsx': {'needs_ocr': False, 'supports_vlm': False, 'has_layout': True},
    '.png': {'needs_ocr': True, 'supports_vlm': True, 'has_layout': False},
    '.jpg': {'needs_ocr': True, 'supports_vlm': True, 'has_layout': False},
    '.jpeg': {'needs_ocr': True, 'supports_vlm': True, 'has_layout': False},
    '.tiff': {'needs_ocr': True, 'supports_vlm': True, 'has_layout': False},
    '.wav': {'needs_ocr': False, 'supports_vlm': False, 'needs_asr': True},
    '.mp3': {'needs_ocr': False, 'supports_vlm': False, 'needs_asr': True},
    '.html': {'needs_ocr': False, 'supports_vlm': False, 'has_layout': True},
    '.txt': {'needs_ocr': False, 'supports_vlm': False, 'has_layout': False},
    '.md': {'needs_ocr': False, 'supports_vlm': False, 'has_layout': False}
}


def sanitize_filename_stem(stem: str) -> str:
    """
    Normalize a filename stem for Windows-safe output folders and files.

    Trailing spaces (and dots) in names are invalid on Windows and cause
    mkdir/write to fail or disagree with pathlib/consolidator paths   e.g.
    ``Report .pdf`` -> stem ``Report `` must become ``Report``.
    """
    if not stem:
        return "untitled"
    s = stem.strip()
    while s and s[-1] in ". \t":
        s = s[:-1]
    return s or "untitled"


def get_file_hash(file_path: Path) -> str:
    """
    Generate MD5 hash of a file for duplicate detection.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""


def get_file_mime_type(file_path: Path) -> Optional[str]:
    """
    Get MIME type of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MIME type string or None
    """
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type


def categorize_file_by_mime(file_path: Path) -> str:
    """
    Categorize file based on its MIME type.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File category string
    """
    mime_type = get_file_mime_type(file_path)
    if mime_type in MIME_TYPE_CATEGORIES:
        return MIME_TYPE_CATEGORIES[mime_type]
    
    # Fall back to extension-based categorization
    suffix = file_path.suffix.lower()
    if suffix in FILE_PROCESSING_HINTS:
        # Map to category based on processing hints
        hints = FILE_PROCESSING_HINTS[suffix]
        if hints.get('needs_asr'):
            return 'audio'
        elif hints.get('needs_ocr') and hints.get('supports_vlm'):
            return 'image'
        elif suffix == '.pdf':
            return 'pdf'
        elif suffix in ['.docx', '.pptx', '.xlsx']:
            return 'office'
        elif hints.get('has_layout') and suffix in ['.html']:
            return 'web'
        else:
            return 'text'
    
    return 'unknown'


def get_processing_recommendations(file_path: Path) -> Dict[str, bool]:
    """
    Get processing recommendations based on file type.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with processing recommendations
    """
    suffix = file_path.suffix.lower()
    
    if suffix in FILE_PROCESSING_HINTS:
        return FILE_PROCESSING_HINTS[suffix].copy()
    
    # Default recommendations for unknown files
    return {
        'needs_ocr': True,
        'supports_vlm': True,
        'has_layout': True,
        'needs_asr': False
    }


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    else:
        return f"{size_bytes / 1024 / 1024 / 1024:.1f} GB"


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe filesystem operations.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace problematic characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length and strip whitespace
    filename = filename.strip()[:255]
    
    return filename


def create_processing_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a comprehensive processing summary from results.
    
    Args:
        results: List of processing results
        
    Returns:
        Summary dictionary
    """
    if not results:
        return {'error': 'No results to summarize'}
    
    successful = [r for r in results if r.get('success', False)]
    failed = [r for r in results if not r.get('success', False)]
    
    # Calculate statistics
    total_files = len(results)
    total_time = sum(r.get('processing_time', 0) for r in results)
    total_size = sum(r.get('file_size', 0) for r in results if 'file_size' in r)
    
    # File type distribution
    file_types = {}
    for result in results:
        file_type = result.get('file_type', 'unknown')
        file_types[file_type] = file_types.get(file_type, 0) + 1
    
    # Performance metrics
    avg_time = total_time / total_files if total_files > 0 else 0
    success_rate = len(successful) / total_files * 100 if total_files > 0 else 0
    
    summary = {
        'overview': {
            'total_files': total_files,
            'successful': len(successful),
            'failed': len(failed),
            'success_rate_percent': round(success_rate, 1),
            'total_processing_time': round(total_time, 2),
            'average_time_per_file': round(avg_time, 2),
            'total_data_size': format_file_size(total_size)
        },
        'file_types': file_types,
        'performance': {
            'fastest_file': min(successful, key=lambda x: x.get('processing_time', float('inf')), default={}),
            'slowest_file': max(successful, key=lambda x: x.get('processing_time', 0), default={}),
            'largest_file': max(results, key=lambda x: x.get('file_size', 0), default={}),
            'smallest_file': min(results, key=lambda x: x.get('file_size', float('inf')), default={})
        },
        'errors': [
            {
                'file': r.get('file_path', 'unknown'),
                'type': r.get('file_type', 'unknown'),
                'error': r.get('error', 'unknown error')
            }
            for r in failed
        ],
        'generated_at': datetime.now().isoformat()
    }
    
    return summary


def validate_processing_config(config) -> List[str]:
    """
    Validate processing configuration and return any issues.
    
    Args:
        config: ProcessingConfig object
        
    Returns:
        List of validation error messages
    """
    errors = []
    
    # Check OCR configuration
    if config.enable_ocr:
        if config.ocr_engine not in ['tesseract', 'easyocr', 'rapidocr']:
            errors.append(f"Invalid OCR engine: {config.ocr_engine}")
        
        if not config.ocr_languages:
            errors.append("OCR languages list is empty")
    
    # Check VLM configuration
    if config.enable_vlm:
        if not config.vlm_model:
            errors.append("VLM model not specified")
    
    # Check ASR configuration
    if config.enable_asr:
        if not config.asr_model:
            errors.append("ASR model not specified")
    
    # Check export settings
    if not any([config.export_markdown, config.export_images, 
                config.export_tables, config.export_metadata]):
        errors.append("No export formats enabled")
    
    return errors


def create_file_index(files: List[Path]) -> Dict[str, Any]:
    """
    Create an index of files for quick lookup and organization.
    
    Args:
        files: List of file paths
        
    Returns:
        File index dictionary
    """
    index = {
        'files': [],
        'by_type': {},
        'by_size': {'small': [], 'medium': [], 'large': []},
        'duplicates': {},
        'total_size': 0,
        'created_at': datetime.now().isoformat()
    }
    
    file_hashes = {}
    
    for file_path in files:
        try:
            stat = file_path.stat()
            file_hash = get_file_hash(file_path)
            file_type = categorize_file_by_mime(file_path)
            
            file_info = {
                'path': str(file_path),
                'name': file_path.name,
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'type': file_type,
                'hash': file_hash
            }
            
            index['files'].append(file_info)
            index['total_size'] += stat.st_size
            
            # Group by type
            if file_type not in index['by_type']:
                index['by_type'][file_type] = []
            index['by_type'][file_type].append(file_info)
            
            # Group by size
            if stat.st_size < 1024 * 1024:  # < 1MB
                index['by_size']['small'].append(file_info)
            elif stat.st_size < 10 * 1024 * 1024:  # < 10MB
                index['by_size']['medium'].append(file_info)
            else:
                index['by_size']['large'].append(file_info)
            
            # Track duplicates
            if file_hash in file_hashes:
                if file_hash not in index['duplicates']:
                    index['duplicates'][file_hash] = [file_hashes[file_hash]]
                index['duplicates'][file_hash].append(file_info)
            else:
                file_hashes[file_hash] = file_info
                
        except Exception as e:
            # Skip files that can't be processed
            continue
    
    return index