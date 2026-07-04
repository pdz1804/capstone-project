"""
Stage 4 Consolidator

Consolidates processed files from Stage 1-3 into a unified RAG-ready structure.

Output Structure:
- file.pdf (optional - if normalized PDF exists)
- file.md (required - from Docling processing)
- docling_additional/ (extracted images, tables, metadata)
"""

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
import json
from datetime import datetime
from tqdm import tqdm
from loguru import logger


@dataclass
class ConsolidatorConfig:
    """Configuration for Stage 4 consolidation."""
    include_normalized_pdfs: bool = True  # Include PDFs from Stage 1
    include_metadata: bool = True         # Include Docling metadata
    include_tables: bool = True           # Include extracted tables
    include_images: bool = True           # Include extracted images


class Stage4Consolidator:
    """
    Consolidates Stage 1-3 outputs into unified RAG-ready structure.
    """
    
    def __init__(
        self,
        stage1_dir: Union[str, Path],
        stage3_dir: Union[str, Path],
        output_dir: Union[str, Path],
        config: Optional[ConsolidatorConfig] = None
    ):
        self.stage1_dir = Path(stage1_dir)
        self.stage3_dir = Path(stage3_dir)
        self.output_dir = Path(output_dir)
        self.config = config or ConsolidatorConfig()
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats = {
            'total_documents': 0,
            'with_pdf': 0,
            'without_pdf': 0,
            'with_markdown': 0,  # Track markdown files (all should have this)
            'with_additional': 0,  # Track additional files (tables, images, metadata)
            'errors': []
        }
    
    def consolidate(self) -> Dict:
        """
        Consolidate all processed documents into unified structure.
        """
        print("="*80)
        print("STAGE 4: RAG-READY CONSOLIDATION")
        print("="*80)
        
        # Find all document folders in Stage 3
        doc_folders = [d for d in self.stage3_dir.iterdir() if d.is_dir() and d.name != 'logs']
        
        self.stats['total_documents'] = len(doc_folders)
        print(f"Found {len(doc_folders)} documents to consolidate")
        
        # Process each document
        for doc_folder in tqdm(doc_folders, desc="Consolidating documents"):
            try:
                self._consolidate_document(doc_folder)
            except Exception as e:
                logger.error(f"Failed to consolidate {doc_folder.name}: {e}")
                self.stats['errors'].append({
                    'document': doc_folder.name,
                    'error': str(e)
                })
        
        # Save statistics
        self._save_stats()
        
        # Print summary
        self._print_summary()
        
        return self.stats
    
    def _consolidate_document(self, doc_folder: Path):
        """
        Consolidate a single document into RAG-ready structure.
        
        Args:
            doc_folder: Path to Stage 3 document folder
        """
        doc_name = doc_folder.name
        
        # Create output folder
        output_folder = self.output_dir / doc_name
        output_folder.mkdir(exist_ok=True)
        
        # 1. Copy main markdown file (REQUIRED)
        stage3_md = doc_folder / f"{doc_name}.md"
        if not stage3_md.exists():
            raise FileNotFoundError(f"Markdown file not found: {stage3_md}")
        
        output_md = output_folder / f"{doc_name}.md"
        shutil.copy2(stage3_md, output_md)
        logger.info(f"✓ Copied markdown: {output_md.name}")
        self.stats['with_markdown'] += 1
        
        # 2. Copy normalized PDF if exists (OPTIONAL)
        pdf_copied = False
        if self.config.include_normalized_pdfs:
            normalized_pdfs_dir = self.stage1_dir / "normalized_pdfs"
            
            # Try exact match
            stage1_pdf = normalized_pdfs_dir / f"{doc_name}.pdf"
            if stage1_pdf.exists():
                output_pdf = output_folder / f"{doc_name}.pdf"
                shutil.copy2(stage1_pdf, output_pdf)
                logger.info(f"✓ Copied normalized PDF: {output_pdf.name}")
                pdf_copied = True
                self.stats['with_pdf'] += 1
        
        if not pdf_copied:
            self.stats['without_pdf'] += 1
        
        # 3. Create docling_additional/ subfolder
        additional_dir = output_folder / "docling_additional"
        additional_dir.mkdir(exist_ok=True)
        has_additional = False
        
        # 4. Copy metadata
        if self.config.include_metadata:
            stage3_metadata = doc_folder / f"{doc_name}_metadata.json"
            if stage3_metadata.exists():
                output_metadata = additional_dir / "metadata.json"
                shutil.copy2(stage3_metadata, output_metadata)
                logger.debug(f"  ✓ Copied metadata")
                has_additional = True
        
        # 5. Copy extracted tables
        if self.config.include_tables:
            for table_file in doc_folder.glob("table_*"):
                shutil.copy2(table_file, additional_dir / table_file.name)
                logger.debug(f"  ✓ Copied table: {table_file.name}")
                has_additional = True
        
        # 6. Copy extracted images
        if self.config.include_images:
            for image_file in doc_folder.glob("image_*"):
                shutil.copy2(image_file, additional_dir / image_file.name)
                logger.debug(f"  ✓ Copied image: {image_file.name}")
                has_additional = True
        
        # Track additional files
        if has_additional:
            self.stats['with_additional'] += 1
    
    def _save_stats(self):
        """Save consolidation statistics."""
        stats_file = self.output_dir / "consolidation_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)
        print(f"Statistics saved to: {stats_file}")
    
    def _print_summary(self):
        """Print consolidation summary."""
        print("\n" + "="*80)
        print("CONSOLIDATION SUMMARY")
        print("="*80)
        print(f"Total documents: {self.stats['total_documents']}")
        print(f"  With Markdown: {self.stats['with_markdown']}")
        print(f"  With PDF: {self.stats['with_pdf']}")
        print(f"  Without PDF: {self.stats['without_pdf']}")
        
        if self.stats['errors']:
            print(f"\nErrors: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:  # Show first 5 errors
                print(f"  - {error['document']}: {error['error']}")
        
        print("="*80)
