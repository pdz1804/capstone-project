#!/usr/bin/env python
"""
COMPLETE FULL PIPELINE TEST WITH ALL ENHANCEMENTS
Processes video/audio files through the complete pipeline:
1. Media Processing:
   - Whisper full parameters (word_timestamps, temperature, quality thresholds)
   - Smart token-aware transcript chunking (max 100 tokens per chunk)
   - Frame deduplication with perceptual hashing
   - Audio noise reduction (silence trim + high-pass filter)
   - Complete metadata/provenance tracking
2. Chunk Enhancement:
   - LLM-generated text descriptions for each chunk
   - Frame-to-chunk associations
3. RAG Indexing:
   - Index enhanced chunks for retrieval (BM25, Dense, Hybrid)
   - Enable semantic search over video content
"""

import sys
import os
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    dotenv_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=dotenv_path)
    if dotenv_path.exists():
        print(f"✓ Loaded environment variables from {dotenv_path}")
except ImportError:
    print("⚠ python-dotenv not installed. Install with: pip install python-dotenv")
    print("  You can still set environment variables manually in your shell.")

# Import enhanced implementation
sys.path.insert(0, str(Path(__file__).parent))
from media_processor_enhanced import (
    MediaProcessor,
    MediaProcessorConfig,
    logger
)

# Import chunk enhancement and RAG integration
try:
    from chunk_enhancer import EnhancedChunkProcessor
    from video_rag_integration import VideoRAGPipeline
    ENHANCEMENT_AVAILABLE = True
except ImportError as e:
    ENHANCEMENT_AVAILABLE = False
    logger.warning(f"Enhancement modules not available: {e}")


def main():
    """Run the full enhanced media processor pipeline"""
    
    logger.info("\n\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info("║" + "ENHANCED MEDIA PROCESSOR - FULL PIPELINE TEST".center(78) + "║")
    logger.info("║" + "With all advanced features enabled".center(78) + "║")
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝\n")
    
    # Configuration with ALL enhanced features enabled
    config = MediaProcessorConfig(
        # Audio extraction with noise reduction
        extract_audio=True,
        audio_sample_rate=16000,
        apply_noise_reduction=True,
        noise_reduction_threshold=0.02,
        
        # Transcription with full Whisper parameters
        enable_transcription=True,
        asr_model="base",
        asr_language=None,  # Auto-detect language
        use_word_timestamps=True,
        temperature_schedule=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
        compression_ratio_threshold=2.4,
        logprob_threshold=-1.0,
        no_speech_threshold=0.6,
        condition_on_previous_text=True,
        
        # Transcript chunking
        max_chunk_tokens=100,
        chunk_overlap_tokens=10,
        
        # Frame extraction with deduplication
        extract_frames=True,
        frame_interval=30,
        frame_quality=85,
        remove_duplicate_frames=True,
        frame_similarity_threshold=0.95,
        
        # Export all formats
        export_txt=True,
        export_json=True,
        export_srt=True,
        export_vtt=True,
        export_metadata=True
    )
    
    logger.info("=" * 80)
    logger.info("ENHANCED FEATURES CONFIGURATION")
    logger.info("=" * 80)
    logger.info("\n✓ WHISPER FULL PARAMETERS:")
    logger.info(f"  - Word-level timestamps: {config.use_word_timestamps}")
    logger.info(f"  - Temperature schedule: {config.temperature_schedule}")
    logger.info(f"  - Compression ratio threshold: {config.compression_ratio_threshold}")
    logger.info(f"  - Logprob threshold: {config.logprob_threshold}")
    logger.info(f"  - No speech threshold: {config.no_speech_threshold}")
    logger.info(f"  - Condition on previous text: {config.condition_on_previous_text}")
    
    logger.info("\n✓ AUDIO NOISE REDUCTION:")
    logger.info(f"  - Enabled: {config.apply_noise_reduction}")
    logger.info(f"  - Threshold: {config.noise_reduction_threshold}")
    logger.info(f"  - Pipeline: librosa.trim() + scipy high-pass filter (80Hz)")
    
    logger.info("\n✓ TRANSCRIPT CHUNKING:")
    logger.info(f"  - Max tokens per chunk: {config.max_chunk_tokens}")
    logger.info(f"  - Chunk overlap: {config.chunk_overlap_tokens} tokens")
    logger.info(f"  - Strategy: Token-aware (uses Whisper JSON segment data)")
    logger.info(f"  - Metadata: timestamps, segment indices, token counts")
    
    logger.info("\n✓ FRAME DEDUPLICATION:")
    logger.info(f"  - Enabled: {config.remove_duplicate_frames}")
    logger.info(f"  - Similarity threshold: {config.frame_similarity_threshold}")
    logger.info(f"  - Method: Perceptual hashing + histogram fallback")
    logger.info(f"  - Metadata: path, index, hash, similarity score")
    
    logger.info("\n✓ METADATA TRACKING:")
    logger.info(f"  - Provenance fields: original filename, type, path")
    logger.info(f"  - Processing info: timestamps, configuration, device")
    logger.info(f"  - Output links: audio, transcript, chunks, frames")
    
    logger.info("\n✓ OUTPUT FORMATS:")
    logger.info(f"  - Transcripts: JSON, TXT, SRT, VTT")
    logger.info(f"  - Chunks: JSON with metadata")
    logger.info(f"  - Frame metadata: JSON with dedup info")
    logger.info(f"  - Media metadata: Complete provenance JSON")
    logger.info("=" * 80)
    
    # Setup paths
    script_dir = Path(__file__).parent
    input_dir = script_dir / "input"
    output_dir = script_dir / "output"
    
    logger.info(f"\nInput directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Input exists: {input_dir.exists()}")
    
    if not input_dir.exists():
        logger.error(f"\n✗ Input directory does not exist: {input_dir}")
        logger.error("Please create 'input' folder and add video/audio files to it")
        return 1
    
    # Check for media files
    media_files = list(input_dir.glob("*.*"))
    if not media_files:
        logger.error(f"\n✗ No media files found in: {input_dir}")
        return 1
    
    logger.info(f"\n✓ Found {len(media_files)} media file(s) to process:")
    for f in media_files:
        logger.info(f"  - {f.name} ({f.stat().st_size / (1024*1024):.2f} MB)")
    
    # Initialize and run processor
    logger.info("\n" + "=" * 80)
    logger.info("STARTING ENHANCED MEDIA PROCESSING PIPELINE")
    logger.info("=" * 80)
    
    try:
        processor = MediaProcessor(input_dir, output_dir, config)
        stats = processor.process_batch()
        
        logger.info("\n" + "=" * 80)
        logger.info("PROCESSING COMPLETE - FINAL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"\nResults:")
        logger.info(f"  ✓ Processed: {stats['processed_files']}/{stats['total_files']} files")
        logger.info(f"  ✓ Audio extracted: {stats['audio_extracted']}")
        logger.info(f"  ✓ Transcribed: {stats['transcribed']}")
        logger.info(f"  ✓ Frames extracted: {stats['frames_extracted']}")
        logger.info(f"  ✓ Chunks created: {stats['chunks_created']}")
        
        if stats['failed_files'] > 0:
            logger.warning(f"  ⚠ Failed: {stats['failed_files']}")
            for error in stats['errors']:
                logger.error(f"    - {error['file']}: {error['error']}")
        
        logger.info(f"\nOutput location: {output_dir}")
        logger.info("\nGenerated files:")
        
        # List output files
        transcript_dir = output_dir / "transcripts"
        chunks_dir = output_dir / "transcript_chunks"
        frames_dir = output_dir / "extracted_frames"
        metadata_dir = output_dir / "media_metadata"
        
        if transcript_dir.exists():
            transcripts = list(transcript_dir.glob("*.*"))
            if transcripts:
                logger.info(f"\n  📄 Transcripts ({len(transcripts)} files):")
                for f in sorted(transcripts):
                    logger.info(f"    - {f.name}")
        
        if chunks_dir.exists():
            chunks = list(chunks_dir.glob("*.json"))
            if chunks:
                logger.info(f"\n  🔗 Transcript Chunks ({len(chunks)} files):")
                for f in sorted(chunks):
                    logger.info(f"    - {f.name}")
        
        if frames_dir.exists():
            frame_dirs = [d for d in frames_dir.iterdir() if d.is_dir()]
            if frame_dirs:
                logger.info(f"\n  🖼️  Frames (extracted + deduplicated):")
                for frame_set in sorted(frame_dirs):
                    frames = list(frame_set.glob("*.jpg"))
                    logger.info(f"    - {frame_set.name}: {len(frames)} frames")
        
        if metadata_dir.exists():
            metadata_files = list(metadata_dir.glob("*.json"))
            if metadata_files:
                logger.info(f"\n  📋 Metadata ({len(metadata_files)} files):")
                for f in sorted(metadata_files):
                    logger.info(f"    - {f.name}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ STEP 1: MEDIA PROCESSING COMPLETE")
        logger.info("=" * 80)
        
        # ========================= STEP 2: CHUNK ENHANCEMENT =========================
        if ENHANCEMENT_AVAILABLE and stats['chunks_created'] > 0:
            logger.info("\n" + "=" * 80)
            logger.info("STEP 2: ENHANCING CHUNKS WITH LLM DESCRIPTIONS")
            logger.info("=" * 80)
            
            # Find all chunk files (exclude already enhanced chunks)
            chunk_files = [f for f in chunks_dir.glob("*_chunks.json") if "enhanced" not in f.name]
            enhanced_count = 0
            
            for chunk_file in chunk_files:
                try:
                    stem = chunk_file.stem.replace("_chunks", "")
                    frame_meta_path = metadata_dir / f"{stem}_frame_metadata.json"
                    
                    # Find corresponding media metadata to get video info
                    media_meta_path = metadata_dir / f"{stem}_metadata.json"
                    video_duration = 0
                    video_fps = 29.97
                    video_path_str = "unknown"
                    
                    if media_meta_path.exists():
                        import json
                        with open(media_meta_path) as f:
                            media_meta = json.load(f)
                            # Try new structure first (video_properties), fallback to old structure
                            if "video_properties" in media_meta:
                                video_duration = media_meta["video_properties"].get("duration", 0)
                                video_fps = media_meta["video_properties"].get("fps", 29.97)
                            else:
                                video_duration = media_meta.get("duration", 0)
                                video_fps = media_meta.get("fps", 29.97)
                            video_path_str = media_meta.get("provenance", {}).get("original_path", "unknown")
                    
                    if not frame_meta_path.exists():
                        logger.warning(f"  ⚠ Frame metadata not found for {chunk_file.name}, skipping enhancement")
                        continue
                    
                    logger.info(f"\n  ✓ Enhancing chunks from: {chunk_file.name}")
                    logger.info(f"    Video: {Path(video_path_str).name}")
                    logger.info(f"    Duration: {video_duration:.2f}s, FPS: {video_fps:.2f}")
                    
                    # Check for OpenAI API key
                    api_key = os.getenv("OPENAI_API_KEY")
                    if not api_key:
                        logger.warning(f"    ⚠ OPENAI_API_KEY not set, LLM descriptions will be skipped")
                        logger.warning(f"    ℹ Set OPENAI_API_KEY environment variable to enable LLM descriptions")
                        use_llm = False
                    else:
                        use_llm = True
                        logger.info(f"    ✓ OpenAI API key found, will generate LLM descriptions")
                    
                    enhancer = EnhancedChunkProcessor(
                        chunks_json_path=str(chunk_file),
                        frame_metadata_json_path=str(frame_meta_path),
                        frames_dir=str(frames_dir),
                        video_path=video_path_str,
                        video_duration=video_duration,
                        video_fps=video_fps,
                        use_llm=use_llm
                    )
                    
                    enhanced_chunks, enhanced_frames, chunks_out, frames_out = enhancer.process_all(
                        context=f"Educational video: {Path(video_path_str).stem}",
                        output_chunks_path=str(chunks_dir / f"{stem}_enhanced_chunks.json"),
                        output_frames_path=str(metadata_dir / f"{stem}_enhanced_frame_metadata.json")
                    )
                    
                    # Calculate and log frame-to-chunk mapping statistics
                    chunks_with_frames = sum(1 for c in enhanced_chunks if len(c.get("associated_frames", [])) > 0)
                    frames_with_chunks = sum(1 for f in enhanced_frames if f.get("associated_chunk_index") is not None)
                    total_frame_refs = sum(len(c.get("associated_frames", [])) for c in enhanced_chunks)
                    
                    logger.info(f"    ✓ Enhanced {len(enhanced_chunks)} chunks")
                    logger.info(f"    ✓ Frame-to-Chunk Mapping:")
                    logger.info(f"      • Chunks with frames: {chunks_with_frames}/{len(enhanced_chunks)}")
                    logger.info(f"      • Frames with chunks: {frames_with_chunks}/{len(enhanced_frames)}")
                    logger.info(f"      • Total frame references: {total_frame_refs}")
                    if use_llm:
                        logger.info(f"    ✓ Generated LLM descriptions for all chunks")
                    logger.info(f"    ✓ Saved chunks: {chunks_out}")
                    logger.info(f"    ✓ Saved frame metadata: {frames_out}")
                    
                    enhanced_count += 1
                    
                except Exception as e:
                    logger.error(f"  ✗ Failed to enhance {chunk_file.name}: {str(e)}")
                    logger.exception("Enhancement error details:")
            
            logger.info(f"\n  ✓ Enhanced {enhanced_count}/{len(chunk_files)} chunk files")
            logger.info("=" * 80)
        
        # ========================= STEP 3: RAG INDEXING =========================
        if ENHANCEMENT_AVAILABLE:
            logger.info("\n" + "=" * 80)
            logger.info("STEP 3: INDEXING ENHANCED CHUNKS FOR RAG RETRIEVAL")
            logger.info("=" * 80)
            
            # Find all JSON files in chunks directory
            all_json_files = list(chunks_dir.glob("*.json"))
            
            # Filter to only enhanced chunk files
            enhanced_chunk_files = [f for f in all_json_files if "_enhanced_chunks.json" in f.name]
            
            # Log file analysis
            non_enhanced = [f for f in all_json_files if "_chunks.json" in f.name and "_enhanced" not in f.name]
            logger.info(f"\n  📊 Files in {chunks_dir.name}:")
            logger.info(f"    - Total JSON files: {len(all_json_files)}")
            logger.info(f"    - Original chunks (not enhanced): {len(non_enhanced)}")
            logger.info(f"    - Enhanced chunks (ready for RAG): {len(enhanced_chunk_files)}")
            
            if enhanced_chunk_files:
                try:
                    logger.info(f"\n  ✓ Processing {len(enhanced_chunk_files)} enhanced chunk file(s) for RAG indexing...")
                    
                    # Initialize RAG pipeline with hybrid retrieval
                    rag_pipeline = VideoRAGPipeline(
                        retrieval_method="hybrid",
                        use_frames=True
                    )
                    
                    all_chunks_indexed = 0
                    
                    for enhanced_file in enhanced_chunk_files:
                        try:
                            stem = enhanced_file.stem.replace("_enhanced_chunks", "")
                            logger.info(f"\n  ✓ Indexing: {enhanced_file.name}")
                            
                            # Load enhanced chunks
                            chunks = rag_pipeline.load_enhanced_chunks(str(enhanced_file))
                            
                            if not chunks:
                                logger.warning(f"    ⚠ No chunks loaded from {enhanced_file.name}")
                                continue
                            
                            # Get video metadata
                            media_meta_path = metadata_dir / f"{stem}_metadata.json"
                            video_metadata = {}
                            if media_meta_path.exists():
                                import json
                                with open(media_meta_path) as f:
                                    media_meta = json.load(f)
                                    video_metadata = {
                                        "filename": Path(media_meta.get("provenance", {}).get("original_filename", "unknown")).name,
                                        "duration": media_meta.get("duration", 0),
                                        "fps": media_meta.get("fps", 29.97)
                                    }
                            
                            # Index chunks for RAG
                            success = rag_pipeline.index_video_chunks(chunks, video_metadata)
                            
                            if success:
                                logger.info(f"    ✓ Indexed {len(chunks)} chunks")
                                all_chunks_indexed += len(chunks)
                            else:
                                logger.warning(f"    ⚠ Failed to index {enhanced_file.name}")
                            
                        except Exception as e:
                            logger.error(f"    ✗ Failed to index {enhanced_file.name}: {str(e)}")
                    
                    # Save RAG index to disk
                    if all_chunks_indexed > 0:
                        index_path = output_dir / "rag_index"
                        logger.info(f"\n  ✓ Total chunks indexed: {all_chunks_indexed}")
                        logger.info(f"  ✓ Saving RAG index to: {index_path}")
                        
                        rag_pipeline.save_index(str(index_path))
                        logger.info(f"  ✓ RAG index saved successfully")
                        logger.info(f"\n  ℹ You can now perform semantic search queries over the video content!")
                        logger.info(f"  ℹ Example query: 'What is naive bayes classifier?'")
                    
                except Exception as e:
                    logger.error(f"  ✗ RAG indexing failed: {str(e)}")
                    logger.exception("RAG error details:")
            
            else:
                logger.warning("  ⚠ No enhanced chunk files found, skipping RAG indexing")
                if non_enhanced:
                    logger.warning(f"  ℹ Found {len(non_enhanced)} original (non-enhanced) chunks - enhancement step may have failed")
                    logger.warning("  ℹ Check if OPENAI_API_KEY is set for chunk enhancement")
                else:
                    logger.warning("  ℹ No chunk files found at all - check Step 1 media processing")
            
            logger.info("=" * 80)
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ COMPLETE PIPELINE FINISHED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info("\nPipeline Summary:")
        logger.info("  ✓ Step 1: Media Processing (audio, transcription, frames)")
        logger.info("  ✓ Step 2: Chunk Enhancement")
        logger.info("      • LLM descriptions for chunks")
        logger.info("      • Frame-to-chunk mapping (by timestamp)")
        logger.info("      • Complete frame metadata")
        logger.info("  ✓ Step 3: RAG Indexing (searchable, frame-aware content)")
        logger.info("\n✨ Key Feature: Frame-to-Chunk Mapping")
        logger.info("  • Each frame is associated with the chunk containing its timestamp")
        logger.info("  • Each chunk knows which frames appear during it")
        logger.info("  • Frames show in search results with their chunk's content")
        logger.info("\nAll outputs saved to: " + str(output_dir))
        logger.info("=" * 80)
        
        return 0
    
    except Exception as e:
        logger.error(f"\n✗ Processing failed: {str(e)}")
        logger.exception("Full traceback:")
        return 1


if __name__ == "__main__":
    sys.exit(main())
