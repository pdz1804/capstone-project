"""
Stage 4 Consolidator

Consolidates processed files from Stage 1-3 into a unified RAG-ready structure.

For regular documents (PDFs, DOCX, etc.):
- file.pdf (optional - if normalized PDF exists)
- file.md (required - from Docling processing)
- docling_additional/ (extracted images, tables, metadata)

For media files (video/audio - from Stage 2):
- file.md (transcript markdown)
- transcript_chunks.json (pre-built chunks with uniform metadata)
- frames/ (extracted video frames, if any)
- media_manifest.json (marks this as a media document)
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
    Also handles media files from Stage 2 directly (skipping Docling).
    """
    
    def __init__(
        self,
        stage1_dir: Union[str, Path],
        stage3_dir: Union[str, Path],
        output_dir: Union[str, Path],
        stage2_dir: Union[str, Path] = None,
        config: Optional[ConsolidatorConfig] = None
    ):
        self.stage1_dir = Path(stage1_dir)
        self.stage2_dir = Path(stage2_dir) if stage2_dir else None
        self.stage3_dir = Path(stage3_dir)
        self.output_dir = Path(output_dir)
        self.config = config or ConsolidatorConfig()
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats = {
            'total_documents': 0,
            'with_pdf': 0,
            'without_pdf': 0,
            'with_markdown': 0,
            'with_additional': 0,
            'media_documents': 0,
            'media_with_chunks': 0,
            'media_with_frames': 0,
            'errors': []
        }
    
    def consolidate(self) -> Dict:
        """
        Consolidate all processed documents into unified structure.
        """
        print("="*80)
        print("STAGE 4: RAG-READY CONSOLIDATION")
        print("="*80)
        
        # Part A: Consolidate regular documents from Stage 3 (Docling output)
        doc_folders = [d for d in self.stage3_dir.iterdir() if d.is_dir() and d.name != 'logs']
        
        print(f"Found {len(doc_folders)} Docling-processed documents to consolidate")
        
        for doc_folder in tqdm(doc_folders, desc="Consolidating documents"):
            try:
                self._consolidate_document(doc_folder)
                self.stats['total_documents'] += 1
            except Exception as e:
                logger.error(f"Failed to consolidate {doc_folder.name}: {e}")
                self.stats['errors'].append({
                    'document': doc_folder.name,
                    'error': str(e)
                })
        
        # Part B: Consolidate media files from Stage 2 (pre-built chunks)
        if self.stage2_dir and self.stage2_dir.exists():
            media_count = self._consolidate_media_files()
            if media_count > 0:
                print(f"Consolidated {media_count} media documents from Stage 2")
        
        # Part C: Count Excel documents already placed by Excel processing stage
        # (The Excel pipeline writes directly to stage4_rag_ready, so we just count them)
        excel_count = 0
        for doc_folder in self.output_dir.iterdir():
            if doc_folder.is_dir():
                manifest = doc_folder / "excel_manifest.json"
                if manifest.exists():
                    excel_count += 1
                    self.stats['total_documents'] += 1
        if excel_count > 0:
            print(f"Found {excel_count} Excel documents (pre-processed by custom parser)")
        
        # Save statistics
        self._save_stats()
        
        # Print summary
        self._print_summary()
        
        return self.stats
    
    def _consolidate_media_files(self) -> int:
        """
        Consolidate media files from Stage 2 into RAG-ready structure.
        
        Media files have pre-built transcript chunks with uniform metadata,
        extracted frames, and media metadata. These bypass Docling entirely.
        
        Returns:
            Number of media documents consolidated
        """
        chunks_dir = self.stage2_dir / "transcript_chunks"
        transcripts_dir = self.stage2_dir / "transcripts"
        frames_dir = self.stage2_dir / "extracted_frames"
        metadata_dir = self.stage2_dir / "media_metadata"
        
        if not chunks_dir.exists():
            logger.info("No transcript chunks found in Stage 2, skipping media consolidation")
            return 0
        
        chunk_files = list(chunks_dir.glob("*_chunks.json"))
        if not chunk_files:
            return 0
        
        print(f"\nConsolidating {len(chunk_files)} media documents from Stage 2...")
        
        count = 0
        for chunk_file in tqdm(chunk_files, desc="Consolidating media"):
            try:
                # Extract stem: "10_Naive_Bayes1_19_chunks.json" -> "10_Naive_Bayes1_19"
                stem = chunk_file.stem.replace("_chunks", "")
                
                output_folder = self.output_dir / stem
                output_folder.mkdir(exist_ok=True)
                
                # 1. Copy transcript markdown
                md_file = transcripts_dir / f"{stem}.md"
                if md_file.exists():
                    shutil.copy2(md_file, output_folder / f"{stem}.md")
                    logger.info(f"  ✓ Copied transcript markdown: {stem}.md")
                else:
                    logger.warning(f"  ⚠ No transcript markdown for {stem}")
                
                # 2. Copy pre-built transcript chunks JSON
                dest_chunks = output_folder / "transcript_chunks.json"
                shutil.copy2(chunk_file, dest_chunks)
                logger.info(f"  ✓ Copied transcript chunks: {chunk_file.name}")
                self.stats['media_with_chunks'] += 1
                
                # 3. Copy extracted frames (if any)
                stem_frames_dir = frames_dir / stem
                if stem_frames_dir.exists() and any(stem_frames_dir.iterdir()):
                    dest_frames_dir = output_folder / "frames"
                    if dest_frames_dir.exists():
                        shutil.rmtree(dest_frames_dir)
                    shutil.copytree(stem_frames_dir, dest_frames_dir)
                    frame_count = sum(1 for _ in dest_frames_dir.glob("*.jpg")) + sum(1 for _ in dest_frames_dir.glob("*.png"))
                    logger.info(f"  ✓ Copied {frame_count} extracted frames")
                    self.stats['media_with_frames'] += 1
                
                # 4. Copy media metadata (if any)
                media_meta_file = metadata_dir / f"{stem}_metadata.json"
                if media_meta_file.exists():
                    shutil.copy2(media_meta_file, output_folder / "media_metadata.json")
                    logger.info(f"  ✓ Copied media metadata")
                
                # 5. Create media manifest (identifies this as a media document for retrieval)
                manifest = {
                    "document_type": "media",
                    "stem": stem,
                    "has_transcript_chunks": True,
                    "has_frames": (stem_frames_dir.exists() if frames_dir.exists() else False),
                    "has_metadata": media_meta_file.exists() if metadata_dir.exists() else False,
                    "consolidated_at": datetime.now().isoformat(),
                    "source_stage": "stage2_media_processed"
                }
                with open(output_folder / "media_manifest.json", 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2)
                
                self.stats['media_documents'] += 1
                self.stats['total_documents'] += 1
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to consolidate media file {chunk_file.name}: {e}")
                self.stats['errors'].append({
                    'document': chunk_file.name,
                    'error': str(e),
                    'type': 'media'
                })
        
        return count
    
    def _consolidate_document(self, doc_folder: Path):
        """
        Consolidate a single Docling-processed document into RAG-ready structure.
        
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
            md_candidates = sorted(doc_folder.glob("*.md"))
            if len(md_candidates) == 1:
                stage3_md = md_candidates[0]
                logger.info(f"Using single markdown in folder: {stage3_md.name}")
            else:
                raise FileNotFoundError(f"Markdown file not found: {doc_folder / f'{doc_name}.md'}")
        
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
        
        # 7. Copy full page renders (page_*_full.png) from Docling
        if self.config.include_images:
            for page_img in doc_folder.glob("page_*_full.*"):
                shutil.copy2(page_img, additional_dir / page_img.name)
                logger.debug(f"  ✓ Copied page image: {page_img.name}")
                has_additional = True
        
        # 8. Copy original source file for image inputs (they don't produce a
        #    normalized PDF, so the original is the only visual reference)
        image_exts = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
        originals_dir = self.stage1_dir / "original_files"
        if originals_dir.exists():
            for ext in image_exts:
                original_file = originals_dir / f"{doc_name}{ext}"
                if original_file.exists():
                    dest = output_folder / f"{doc_name}{ext}"
                    shutil.copy2(original_file, dest)
                    logger.info(f"  ✓ Copied original image: {dest.name}")
                    has_additional = True
                    break
        
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
        print(f"  Regular (Docling): {self.stats['total_documents'] - self.stats['media_documents']}")
        print(f"    With Markdown: {self.stats['with_markdown']}")
        print(f"    With PDF: {self.stats['with_pdf']}")
        print(f"    Without PDF: {self.stats['without_pdf']}")
        print(f"  Media (Stage 2): {self.stats['media_documents']}")
        print(f"    With chunks: {self.stats['media_with_chunks']}")
        print(f"    With frames: {self.stats['media_with_frames']}")
        
        if self.stats['errors']:
            print(f"\nErrors: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:
                print(f"  - {error['document']}: {error['error']}")
        
        print("="*80)
