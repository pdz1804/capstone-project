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
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
import logging
from datetime import datetime
from tqdm import tqdm
import argparse

# Import our modules  
# Add src directory to path for imports

from src.normalizer import DocumentNormalizer, NormalizerConfig
from src.media_processor import MediaProcessor, MediaProcessorConfig
from src.document_processor import MultimodalDocumentProcessor, ProcessingConfig


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
                enable_vlm=True,
                export_markdown=True,
                export_images=True,
                export_tables=True
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
            "final_processed": self.output_dir / "stage3_document_processed"
        }
        
        for stage_name, stage_dir in self.stage_dirs.items():
            if stage_name != "raw":
                stage_dir.mkdir(parents=True, exist_ok=True)
        
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
    
    def _setup_logging(self):
        """Setup pipeline logging."""
        log_file = self.output_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        print("="*80)
        print("Document Processing Pipeline Initialized")
        print("="*80)
    
    def run(self) -> Dict:
        """
        Run the complete processing pipeline.
        
        Returns:
            Dictionary with pipeline statistics and results
        """
        print(f"Starting pipeline processing")
        print(f"Input: {self.input_dir}")
        print(f"Output: {self.output_dir}")
        
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
            
            # Finalize
            self.pipeline_stats["end_time"] = datetime.now().isoformat()
            self.pipeline_stats["total_output_files"] = self._count_files(self.stage_dirs["final_processed"])
            
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
    
    def _run_document_processing(self) -> Dict:
        """
        Run Stage 3: Document Processing with Docling.
        
        Processes ORIGINAL files (not normalized markdown) through Docling for best quality.
        Normalized PDFs are kept separately for image-based RAG.
        """
        print("Processing documents with Docling...")
        print("Note: Processing ORIGINAL files for best quality extraction")
        
        try:
            # Determine inputs for document processing
            inputs_to_process = []
            
            # IMPORTANT: Process ORIGINAL files (copied in Stage 1), not markdown
            # This gives Docling the full-quality source for better extraction
            originals_dir = self.stage_dirs["normalized"] / "original_files"
            if originals_dir.exists() and any(originals_dir.iterdir()):
                print(f"  → Adding ORIGINAL files from: {originals_dir}")
                print(f"    (PDFs, DOCX, PPTX, HTML, Images - full quality for Docling)")
                inputs_to_process.append(originals_dir)
            
            # Add markdown/text files that were already in that format
            normalized_md_dir = self.stage_dirs["normalized"] / "normalized_markdown"
            if normalized_md_dir.exists() and any(normalized_md_dir.iterdir()):
                print(f"  → Adding markdown files from: {normalized_md_dir}")
                inputs_to_process.append(normalized_md_dir)
            
            # Add transcribed text from media processing
            transcript_dir = self.stage_dirs["media_processed"] / "transcripts"
            if transcript_dir.exists() and any(transcript_dir.iterdir()):
                print(f"  → Adding transcripts from: {transcript_dir}")
                inputs_to_process.append(transcript_dir)
            
            if not inputs_to_process:
                print("WARNING: No inputs found for document processing")
                return {"processed_files": 0, "total_files": 0}
            
            # Process each input directory
            all_stats = {"processed_files": 0, "failed_files": 0, "total_files": 0}
            
            for input_path in inputs_to_process:
                print(f"Processing files from: {input_path}")
                
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
            
            print(f"✓ Document processing complete: {all_stats['processed_files']}/{all_stats['total_files']} files")
            return all_stats
        
        except Exception as e:
            print(f"ERROR: ✗ Document processing failed: {str(e)}")
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
            enable_vlm=True,
            export_markdown=True,
            export_images=True,
            export_tables=True
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
    
    args = parser.parse_args()
    
    # Create config
    config = create_default_configs()
    
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
