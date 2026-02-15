"""
Unified Document Processing Pipeline

This is the main orchestration script that coordinates:
1. Document Normalization (convert everything to PDF/Markdown)
2. Media Processing (video → audio → text, frame extraction)
3. Document Processing (Docling-based processing of normalized files)
"""

import os
import sys
import json
import shutil
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
import logging
from datetime import datetime
from tqdm import tqdm
import argparse

# Import our modules (relative imports since we're inside src/)
from .normalizer import DocumentNormalizer, NormalizerConfig
from .media_processor import MediaProcessor, MediaProcessorConfig
from .document_processor import MultimodalDocumentProcessor, ProcessingConfig
from .consolidator import Stage4Consolidator, ConsolidatorConfig


@dataclass
class PipelineConfig:
    """Configuration for the entire processing pipeline."""
    
    # Stage control
    enable_normalization: bool = True
    enable_media_processing: bool = True
    enable_document_processing: bool = True
    
    # Normalization settings
    normalizer_config: Optional[NormalizerConfig] = None
    
    # Media processing settings
    media_config: Optional[MediaProcessorConfig] = None
    
    # Document processing settings
    document_config: Optional[ProcessingConfig] = None
    
    # Output organization
    keep_intermediate_files: bool = True  # Keep normalized files
    organize_outputs: bool = True         # Organize by processing stage
    
    # Performance
    use_gpu: bool = True
    parallel_processing: bool = False  # Future enhancement
    
    # Processing cache
    skip_processed: bool = True  # Skip files that were already processed
    
    def __post_init__(self):
        """Initialize sub-configs if not provided."""
        if self.normalizer_config is None:
            self.normalizer_config = NormalizerConfig(
                generate_pdf=True,
                generate_markdown=True
            )
        
        if self.media_config is None:
            self.media_config = MediaProcessorConfig(
                extract_audio=True,
                enable_transcription=True,
                asr_model="base",
                extract_frames=True,
                frame_interval=100
            )
        
        if self.document_config is None:
            self.document_config = ProcessingConfig(
                use_gpu=self.use_gpu,
                enable_ocr=True,
                enable_vlm=True,  # VLM for image descriptions (slower but better)
                export_markdown=True,
                export_images=True,  # Enable to populate docling_additional/
                export_tables=True   # Enable to populate docling_additional/
            )


class DocumentProcessingPipeline:
    """
    Unified pipeline orchestrating all document processing stages.
    """
    
    def __init__(
        self,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path],
        config: Optional[PipelineConfig] = None
    ):
        """
        Initialize the processing pipeline.
        
        Args:
            input_dir: Directory containing raw input files
            output_dir: Directory for all outputs
            config: Pipeline configuration
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.config = config or PipelineConfig()
        
        # Create stage directories
        self.stage_dirs = {
            "raw": self.input_dir,
            "normalized": self.output_dir / "stage1_normalized",
            "media_processed": self.output_dir / "stage2_media_processed",
            "final_processed": self.output_dir / "stage3_document_processed",
            "rag_ready": self.output_dir / "stage4_rag_ready"
        }
        
        for stage_name, stage_dir in self.stage_dirs.items():
            if stage_name != "raw":
                stage_dir.mkdir(parents=True, exist_ok=True)
        
        # Processing cache
        self.cache_file = self.output_dir / ".processing_cache.json"
        self.cache = self._load_cache()
        
        # Setup logging
        self._setup_logging()
        
        # Statistics
        self.pipeline_stats = {
            "start_time": datetime.now().isoformat(),
            "stages": {},
            "total_input_files": 0,
            "total_output_files": 0,
            "errors": []
        }
    
    def _load_cache(self) -> Dict:
        """Load processing cache."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_cache(self):
        """Save processing cache."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception:
            pass
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Get file hash for cache checking."""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            stat = file_path.stat()
            return f"{stat.st_size}_{stat.st_mtime}"
    
    def _is_file_processed(self, file_path: Path) -> bool:
        """Check if file was already processed successfully."""
        if not self.config.skip_processed:
            return False
        
        file_key = str(file_path.relative_to(self.input_dir))
        
        if file_key not in self.cache:
            return False
        
        cached = self.cache[file_key]
        current_hash = self._get_file_hash(file_path)
        
        # Check if file changed
        if cached.get('hash') != current_hash:
            return False
        
        # Check if stage4 output exists
        final_dir = self.stage_dirs["rag_ready"] / file_path.stem
        if not final_dir.exists():
            return False
        
        return cached.get('status') == 'success'
    
    def _mark_file_processed(self, file_path: Path, success: bool = True, error: str = None):
        """Mark file as processed in cache."""
        file_key = str(file_path.relative_to(self.input_dir))
        
        self.cache[file_key] = {
            'hash': self._get_file_hash(file_path),
            'status': 'success' if success else 'failed',
            'timestamp': datetime.now().isoformat(),
            'error': error
        }
        
        self._save_cache()
    
    def _setup_logging(self):
        """Setup pipeline logging."""
        log_file = self.output_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        print("="*80)
        print("Document Processing Pipeline Initialized")
        print("="*80)
        
        if self.config.skip_processed:
            cached_count = len([k for k, v in self.cache.items() if v.get('status') == 'success'])
            if cached_count > 0:
                print(f"⚡ Processing cache: {cached_count} files already processed (will be skipped)")
    
    def run(self) -> Dict:
        """
        Run the complete processing pipeline.
        
        Returns:
            Dictionary with pipeline statistics and results
        """
        print(f"Starting pipeline processing")
        print(f"Input: {self.input_dir}")
        print(f"Output: {self.output_dir}")
        
        # Check for already processed files
        if self.config.skip_processed:
            input_files = [f for f in self.input_dir.rglob("*") if f.is_file()]
            skipped_count = 0
            
            for file_path in input_files:
                if self._is_file_processed(file_path):
                    skipped_count += 1
            
            if skipped_count > 0:
                print(f"⚡ Skipping {skipped_count} already-processed files (use --force to reprocess)")
        
        # Count input files
        self.pipeline_stats["total_input_files"] = self._count_files(self.input_dir)
        print(f"Total input files: {self.pipeline_stats['total_input_files']}")
        
        try:
            # Stage 1: Normalization
            if self.config.enable_normalization:
                print("\n" + "="*80)
                print("STAGE 1: DOCUMENT NORMALIZATION")
                print("="*80)
                norm_stats = self._run_normalization()
                self.pipeline_stats["stages"]["normalization"] = norm_stats
            
            # Stage 2: Media Processing
            if self.config.enable_media_processing:
                print("\n" + "="*80)
                print("STAGE 2: MEDIA PROCESSING (Video/Audio)")
                print("="*80)
                media_stats = self._run_media_processing()
                self.pipeline_stats["stages"]["media_processing"] = media_stats
            
            # Stage 3: Document Processing
            if self.config.enable_document_processing:
                print("\n" + "="*80)
                print("STAGE 3: DOCUMENT PROCESSING (Docling)")
                print("="*80)
                doc_stats = self._run_document_processing()
                self.pipeline_stats["stages"]["document_processing"] = doc_stats
            
            # Stage 4: Consolidation to RAG-ready format
            print("\n" + "="*80)
            print("STAGE 4: CONSOLIDATION (RAG-Ready)")
            print("="*80)
            consolidation_stats = self._run_consolidation()
            self.pipeline_stats["stages"]["consolidation"] = consolidation_stats
            
            # Finalize
            self.pipeline_stats["end_time"] = datetime.now().isoformat()
            self.pipeline_stats["total_output_files"] = self._count_files(self.stage_dirs["rag_ready"])
            
            # Save pipeline statistics
            self._save_pipeline_stats()
            
            # Summary
            self._print_summary()
            
            return self.pipeline_stats
        
        except Exception as e:
            print(f"ERROR: Pipeline failed with error: {str(e)}")
            self.pipeline_stats["errors"].append({
                "stage": "pipeline",
                "error": str(e)
            })
            raise
    
    def _run_normalization(self) -> Dict:
        """
        Run Stage 1: Document Normalization.
        
        Converts various formats to PDF and Markdown.
        """
        print("Normalizing documents to PDF and Markdown formats...")
        
        try:
            normalizer = DocumentNormalizer(
                input_dir=self.input_dir,
                output_dir=self.stage_dirs["normalized"],
                config=self.config.normalizer_config
            )
            
            stats = normalizer.normalize_batch()
            
            print(f"✓ Normalization complete: {stats['normalized_files']}/{stats['total_files']} files")
            return stats
        
        except Exception as e:
            print(f"ERROR: ✗ Normalization failed: {str(e)}")
            raise
    
    def _run_media_processing(self) -> Dict:
        """
        Run Stage 2: Media Processing.
        
        Processes video and audio files (audio extraction, transcription, frame extraction).
        """
        print("Processing video and audio files...")
        
        try:
            # Check if there are any media files to process
            media_input = self.input_dir  # Process from original input
            
            processor = MediaProcessor(
                input_dir=media_input,
                output_dir=self.stage_dirs["media_processed"],
                config=self.config.media_config
            )
            
            stats = processor.process_batch()
            
            print(f"✓ Media processing complete: {stats['processed_files']}/{stats['total_files']} files")
            print(f"  - Audio extracted: {stats['audio_extracted']}")
            print(f"  - Transcribed: {stats['transcribed']}")
            print(f"  - Frames extracted: {stats['frames_extracted']}")
            
            return stats
        
        except Exception as e:
            print(f"ERROR: ✗ Media processing failed: {str(e)}")
            raise
    
    def _get_docling_allowed_extensions(self) -> set:
        """
        Get file extensions allowed by Docling DocumentConverter.
        
        Returns:
            Set of allowed extensions (e.g., {'.pdf', '.docx', '.md'})
        """
        try:
            from docling.document_converter import DocumentConverter
            from docling.datamodel.base_models import InputFormat
            
            # Get default allowed formats from DocumentConverter
            converter = DocumentConverter()
            allowed_formats = converter.allowed_formats
            
            # Map InputFormat to file extensions
            format_to_ext = {
                InputFormat.PDF: ['.pdf'],
                InputFormat.DOCX: ['.docx', '.doc'],
                InputFormat.PPTX: ['.pptx', '.ppt'],
                InputFormat.XLSX: ['.xlsx', '.xls'],
                InputFormat.HTML: ['.html', '.htm', '.xhtml'],
                InputFormat.IMAGE: ['.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.webp'],
                InputFormat.MD: ['.md'],
                InputFormat.CSV: ['.csv'],
                InputFormat.ASCIIDOC: ['.adoc', '.asciidoc', '.asc'],
                InputFormat.VTT: ['.vtt'],
                # Note: AUDIO handled by media_processor, not here
            }
            
            # Collect all extensions for allowed formats
            extensions = set()
            for fmt in allowed_formats:
                if fmt in format_to_ext:
                    extensions.update(format_to_ext[fmt])
            
            return extensions
        except Exception as e:
            print(f"Warning: Could not get Docling allowed formats: {e}")
            # Fallback to known formats
            return {'.pdf', '.docx', '.pptx', '.xlsx', '.png', '.jpg', '.jpeg', 
                   '.tiff', '.tif', '.bmp', '.webp', '.html', '.htm', '.xhtml',
                   '.md', '.csv', '.adoc', '.asciidoc', '.asc', '.vtt'}
    
    def _run_document_processing(self) -> Dict:
        """
        Run Stage 3: Document Processing with Docling.
        
        SMART DEDUPLICATION LOGIC:
        - Normalized PDFs take priority (better quality from conversions)
        - Skip processing original files that were already converted to PDF
        - Only process original files that are NOT in normalized_pdfs
        """
        print("Processing documents with Docling...")
        print("Note: Smart deduplication to avoid processing same file twice")
        
        # Get allowed extensions from Docling
        allowed_extensions = self._get_docling_allowed_extensions()
        print(f"Docling supports: {', '.join(sorted(allowed_extensions))}")
        
        try:
            # Determine inputs for document processing with deduplication
            inputs_to_process = []
            
            # Track which files have been processed in normalized forms
            processed_basenames = set()  # Files already converted to PDF or MD
            
            # STEP 1: Always process normalized PDFs (highest priority - best quality)
            normalized_pdf_dir = self.stage_dirs["normalized"] / "normalized_pdfs"
            
            if normalized_pdf_dir.exists():
                pdf_files = list(normalized_pdf_dir.glob("*.pdf"))
                if pdf_files:
                    print(f"  → Adding {len(pdf_files)} normalized PDFs from: {normalized_pdf_dir}")
                    print(f"    (Converted DOCX/PPTX/HTML - best quality)")
                    inputs_to_process.append(normalized_pdf_dir)
                    
                    # Track base names to avoid duplicate processing
                    for pdf_file in pdf_files:
                        processed_basenames.add(pdf_file.stem)  # filename without extension
            
            # STEP 2: Add markdown files (TXT→MD conversions)
            normalized_md_dir = self.stage_dirs["normalized"] / "normalized_markdown"
            if normalized_md_dir.exists() and any(normalized_md_dir.iterdir()):
                md_files = list(normalized_md_dir.glob("*.md"))
                if md_files:
                    print(f"  → Adding {len(md_files)} markdown files from: {normalized_md_dir}")
                    print(f"    (Converted TXT files)")
                    inputs_to_process.append(normalized_md_dir)
                    
                    # Track base names to avoid duplicate processing
                    for md_file in md_files:
                        processed_basenames.add(md_file.stem)
            
            # STEP 3: Process ONLY original files NOT already converted to PDF or MD
            originals_dir = self.stage_dirs["normalized"] / "original_files"
            if originals_dir.exists():
                original_files = [f for f in originals_dir.iterdir() if f.is_file()]
                
                # Filter out files that were already converted to PDF or MD
                unique_originals = [f for f in original_files if f.stem not in processed_basenames]
                
                # Further filter: only keep formats supported by Docling (dynamic check)
                unique_originals = [f for f in unique_originals if f.suffix.lower() in allowed_extensions]
                
                if unique_originals:
                    print(f"  → Adding {len(unique_originals)} unique original files from: {originals_dir}")
                    print(f"    (Files NOT already converted to PDF/MD, Docling-supported formats only)")
                    # Create temporary list of these specific files for processing
                    inputs_to_process.append(("filtered", originals_dir, unique_originals))
                else:
                    print(f"  ✓ Skipping original_files - all already processed as normalized PDFs/MD or unsupported formats")
            
            # STEP 4: SKIP media transcripts — they already have pre-built chunks from Stage 2.
            # Transcript chunks (with uniform metadata, timing, frame associations) are in
            # stage2_media_processed/transcript_chunks/. These will be handled directly by
            # the consolidator and retrieval pipeline without Docling re-processing.
            transcript_dir = self.stage_dirs["media_processed"] / "transcripts"
            if transcript_dir.exists():
                md_transcripts = list(transcript_dir.glob("*.md"))
                if md_transcripts:
                    print(f"  ⏭ Skipping {len(md_transcripts)} media transcripts (pre-built chunks exist in Stage 2)")
                    print(f"    (Will be consolidated directly from stage2_media_processed/)")
            
            if not inputs_to_process:
                print("WARNING: No inputs found for document processing")
                return {"processed_files": 0, "total_files": 0}
            
            # Process each input directory/file list
            all_stats = {"processed_files": 0, "failed_files": 0, "total_files": 0}
            
            for input_item in inputs_to_process:
                # Handle filtered file lists
                if isinstance(input_item, tuple) and input_item[0] == "filtered":
                    _, input_dir, file_list = input_item
                    print(f"\nProcessing {len(file_list)} filtered files from: {input_dir}")
                    
                    # Process each file individually
                    for file_path in file_list:
                        processor = MultimodalDocumentProcessor(
                            input_dir=file_path.parent,
                            output_dir=self.stage_dirs["final_processed"],
                            config=self.config.document_config
                        )
                        # Process just this one file
                        try:
                            result = processor.process_single_file(file_path)
                            
                            # CRITICAL FIX: Export the outputs (save markdown, metadata, tables, images)
                            if result['success']:
                                processor.export_processed_document(result)
                                all_stats["processed_files"] += 1
                            else:
                                print(f"  ✗ Failed: {file_path.name} - {result.get('error', 'Unknown error')}")
                                all_stats["failed_files"] += 1
                            
                            all_stats["total_files"] += 1
                        except Exception as e:
                            print(f"  ✗ Failed: {file_path.name} - {e}")
                            all_stats["failed_files"] += 1
                            all_stats["total_files"] += 1
                else:
                    # Process entire directory
                    input_path = input_item
                    print(f"\nProcessing all files from: {input_path}")
                    
                    processor = MultimodalDocumentProcessor(
                        input_dir=input_path,
                        output_dir=self.stage_dirs["final_processed"],
                        config=self.config.document_config
                    )
                    
                    stats = processor.process_batch()
                    
                    # Aggregate statistics
                    all_stats["processed_files"] += stats.get("processed_files", 0)
                    all_stats["failed_files"] += stats.get("failed_files", 0)
                    all_stats["total_files"] += stats.get("total_files", 0)
            
            print(f"\n✓ Document processing complete: {all_stats['processed_files']}/{all_stats['total_files']} files")
            print(f"  → Successfully processed: {all_stats['processed_files']}")
            print(f"  → Failed: {all_stats['failed_files']}")
            return all_stats
        
        except Exception as e:
            print(f"ERROR: ✗ Document processing failed: {str(e)}")
            raise
    
    def _run_consolidation(self) -> Dict:
        """
        Run Stage 4: Consolidate outputs into RAG-ready format.
        
        Creates unified output structure:
        - file.pdf (optional, from normalized_pdfs)
        - file.md (required, from Docling output)
        - docling_additional/ (optional, supplementary Docling outputs)
        """
        print("Consolidating outputs into RAG-ready format...")
        
        try:
            consolidator = Stage4Consolidator(
                stage1_dir=self.stage_dirs["normalized"],
                stage2_dir=self.stage_dirs["media_processed"],
                stage3_dir=self.stage_dirs["final_processed"],
                output_dir=self.stage_dirs["rag_ready"],
                config=ConsolidatorConfig()
            )
            
            stats = consolidator.consolidate()
            
            print(f"✓ Consolidation complete: {stats['total_documents']} documents prepared")
            print(f"  → {stats['with_pdf']} documents with PDF")
            print(f"  → {stats['with_markdown']} documents with Markdown")
            print(f"  → {stats['with_additional']} documents with additional files")
            
            # Mark all input files as successfully processed
            if self.config.skip_processed:
                input_files = [f for f in self.input_dir.rglob("*") if f.is_file()]
                for file_path in input_files:
                    if not self._is_file_processed(file_path):
                        self._mark_file_processed(file_path, success=True)
                print(f"  → Updated processing cache for {len(input_files)} files")
            
            return stats
        
        except Exception as e:
            print(f"ERROR: ✗ Consolidation failed: {str(e)}")
            raise
    
    def _count_files(self, directory: Path) -> int:
        """Count all files in a directory recursively."""
        if not directory.exists():
            return 0
        return sum(1 for _ in directory.rglob('*') if _.is_file())
    
    def _save_pipeline_stats(self):
        """Save pipeline statistics to JSON."""
        stats_file = self.output_dir / "pipeline_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.pipeline_stats, f, indent=2)
        print(f"Pipeline statistics saved to: {stats_file}")
    
    def _print_summary(self):
        """Print pipeline execution summary."""
        print("\n" + "="*80)
        print("PIPELINE EXECUTION SUMMARY")
        print("="*80)
        
        print(f"Input files: {self.pipeline_stats['total_input_files']}")
        print(f"Output files: {self.pipeline_stats['total_output_files']}")
        
        for stage_name, stage_stats in self.pipeline_stats["stages"].items():
            print(f"\n{stage_name.upper()}:")
            if isinstance(stage_stats, dict):
                for key, value in stage_stats.items():
                    if key not in ["errors", "by_type"]:
                        print(f"  {key}: {value}")
        
        if self.pipeline_stats["errors"]:
            print(f"WARNING: \nTotal errors: {len(self.pipeline_stats['errors'])}")
        
        print("\n" + "="*80)
        print(f"Pipeline complete! Results in: {self.output_dir}")
        print("="*80)


# ======================== CLI Interface ========================

def create_default_configs():
    """Create default configuration for the pipeline."""
    return PipelineConfig(
        enable_normalization=True,
        enable_media_processing=True,
        enable_document_processing=True,
        use_gpu=True,
        normalizer_config=NormalizerConfig(
            generate_pdf=True,
            generate_markdown=True,
            excel_to_markdown=True,
            csv_to_markdown=True
        ),
        media_config=MediaProcessorConfig(
            extract_audio=True,
            enable_transcription=True,
            asr_model="base",
            extract_frames=True,
            frame_interval=100,
            export_txt=True,
            export_json=True,
            export_srt=True
        ),
        document_config=ProcessingConfig(
            use_gpu=True,
            enable_ocr=True,
            enable_vlm=True,  # VLM for image descriptions (slower but better)
            export_markdown=True,
            export_images=True,  # Enable to populate docling_additional/
            export_tables=True   # Enable to populate docling_additional/
        )
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Unified Document Processing Pipeline for RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all files in input/ directory
  python pipeline.py input/ output/

  # Skip normalization (if files are already normalized)
  python pipeline.py input/ output/ --skip-normalization

  # Process only media files (video/audio)
  python pipeline.py input/ output/ --media-only

  # Use CPU instead of GPU
  python pipeline.py input/ output/ --no-gpu

  # Custom ASR model
  python pipeline.py input/ output/ --asr-model large-v3
        """
    )
    
    parser.add_argument("input_dir", type=str, help="Input directory with documents")
    parser.add_argument("output_dir", type=str, help="Output directory for processed files")
    
    # Stage control
    parser.add_argument("--skip-normalization", action="store_true", help="Skip normalization stage")
    parser.add_argument("--skip-media", action="store_true", help="Skip media processing stage")
    parser.add_argument("--skip-docling", action="store_true", help="Skip document processing stage")
    parser.add_argument("--media-only", action="store_true", help="Process only media files")
    
    # Performance
    parser.add_argument("--no-gpu", action="store_true", help="Disable GPU acceleration")
    parser.add_argument("--asr-model", type=str, default="base", 
                       choices=["tiny", "base", "small", "medium", "large", "large-v3"],
                       help="Whisper ASR model size")
    
    # Features
    parser.add_argument("--no-frames", action="store_true", help="Don't extract video frames")
    parser.add_argument("--frame-interval", type=int, default=100, help="Extract every Nth frame")
    parser.add_argument("--export-images", action="store_true", help="Export images from documents (slower)")
    parser.add_argument("--export-tables", action="store_true", help="Export tables from documents (slower)")
    
    # Processing modes
    parser.add_argument("--fast-mode", action="store_true", help="Fast processing: disable VLM, reduce quality for speed")
    parser.add_argument("--no-vlm", action="store_true", help="Disable VLM (Vision Language Model) for image descriptions")
    
    # Cache control
    parser.add_argument("--force", action="store_true", help="Force reprocess all files (ignore cache)")
    
    args = parser.parse_args()
    
    # Create config
    config = create_default_configs()
    
    # Apply cache setting
    config.skip_processed = not args.force
    
    # Apply CLI arguments
    if args.skip_normalization or args.media_only:
        config.enable_normalization = False
    if args.skip_media:
        config.enable_media_processing = False
    if args.skip_docling or args.media_only:
        config.enable_document_processing = False
    
    if args.no_gpu:
        config.use_gpu = False
        config.media_config.use_gpu = False
        config.document_config.use_gpu = False
    
    config.media_config.asr_model = args.asr_model
    config.media_config.extract_frames = not args.no_frames
    config.media_config.frame_interval = args.frame_interval
    
    # Apply VLM settings
    if args.fast_mode:
        config.document_config.enable_vlm = False
        config.document_config.export_images = False
        config.document_config.export_tables = False
    elif args.no_vlm:
        config.document_config.enable_vlm = False
    
    # Override with explicit export flags if provided
    if args.export_images:
        config.document_config.export_images = True
    if args.export_tables:
        config.document_config.export_tables = True
    
    # Run pipeline
    pipeline = DocumentProcessingPipeline(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        config=config
    )
    
    try:
        stats = pipeline.run()
        print("\n✓ Pipeline completed successfully!")
        print(f"Results saved to: {args.output_dir}")
        return 0
    except Exception as e:
        print(f"\n✗ Pipeline failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
