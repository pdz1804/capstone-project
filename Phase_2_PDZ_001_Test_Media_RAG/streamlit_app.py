"""
Streamlit Application for Video/Audio RAG Pipeline Testing.

Allows users to upload videos, process them through the enhanced media processor,
and view results including transcripts, chunks, frames with metadata.
"""

import streamlit as st
import json
import logging
import pickle
from pathlib import Path
from datetime import datetime
import pandas as pd
from typing import Optional, Dict, Any
import shutil
import os

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    dotenv_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=dotenv_path)
except ImportError:
    pass  # Silently continue if python-dotenv not installed

try:
    from media_processor_enhanced import MediaProcessor, MediaProcessorConfig
    from chunk_enhancer import EnhancedChunkProcessor
    from video_rag_integration import VideoRAGPipeline
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    IMPORT_ERROR = str(e)

# Configure Streamlit
st.set_page_config(
    page_title="Video/Audio RAG Pipeline",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Color scheme and styling
st.markdown("""
    <style>
        .header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; }
        .subheader { font-size: 1.5rem; font-weight: bold; color: #2ca02c; }
        .metric-box { background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem; }
        .success-box { background-color: #d4edda; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #28a745; }
        .info-box { background-color: #d1ecf1; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #17a2b8; }
        .error-box { background-color: #f8d7da; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #dc3545; }
    </style>
""", unsafe_allow_html=True)


class PipelineState:
    """Manage pipeline state and processed files."""
    
    UPLOAD_DIR = Path("uploads")
    OUTPUT_DIR = Path("output")
    PROCESSED_VIDEOS = "processed_videos.json"
    
    def __init__(self):
        """Initialize state manager."""
        self.UPLOAD_DIR.mkdir(exist_ok=True)
        self.OUTPUT_DIR.mkdir(exist_ok=True)
        self.processed_videos = self._load_processed_videos()
    
    def _load_processed_videos(self) -> Dict[str, Any]:
        """Load list of previously processed videos."""
        if Path(self.PROCESSED_VIDEOS).exists():
            try:
                with open(self.PROCESSED_VIDEOS, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading processed videos: {str(e)}")
        return {}
    
    def _save_processed_videos(self):
        """Save processed videos list."""
        try:
            with open(self.PROCESSED_VIDEOS, 'w') as f:
                json.dump(self.processed_videos, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving processed videos: {str(e)}")
    
    def register_processed_video(self, filename: str, output_paths: Dict[str, str]):
        """Register a successfully processed video."""
        self.processed_videos[filename] = {
            "processed_at": datetime.now().isoformat(),
            "outputs": output_paths
        }
        self._save_processed_videos()


# Initialize session state and pipeline state
if "pipeline_state" not in st.session_state:
    st.session_state.pipeline_state = PipelineState()

if "processing_in_progress" not in st.session_state:
    st.session_state.processing_in_progress = False


def render_header():
    """Render main header."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('<p class="header">🎬 Video/Audio RAG Pipeline</p>', unsafe_allow_html=True)
    with col2:
        st.caption("v1.0 - Enhanced Media Processing")
    
    st.markdown("---")
    st.markdown("""
    This application processes video and audio files through an advanced pipeline that:
    - 🔊 Extracts and processes audio with noise reduction
    - 🗣️ Transcribes audio using Whisper with word-level timestamps
    - 📑 Creates semantic chunks with LLM-generated descriptions
    - 🎞️ Extracts and deduplicates frames with metadata
    - 📊 Generates comprehensive metadata for RAG pipelines
    """)


def render_upload_section():
    """Render video upload section."""
    st.markdown('<p class="subheader">📤 Upload Video/Audio</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Choose a video or audio file",
            type=["mp4", "avi", "mov", "mkv", "wav", "mp3", "m4a"],
            help="Supported formats: MP4, AVI, MOV, MKV (video) and WAV, MP3, M4A (audio)"
        )
    
    with col2:
        enable_llm = st.checkbox(
            "Use LLM for descriptions",
            value=True,
            help="Generate AI descriptions for transcript chunks"
        )
    
    return uploaded_file, enable_llm


def render_config_section():
    """Render configuration section."""
    st.markdown('<p class="subheader">⚙️ Processing Configuration</p>', unsafe_allow_html=True)
    
    with st.expander("Advanced Settings", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            extract_frames = st.checkbox("Extract Frames", value=True)
            deduplicate_frames = st.checkbox("Deduplicate Frames", value=True)
            frame_interval = st.slider("Frame Interval", 1, 100, 30)
        
        with col2:
            max_chunk_tokens = st.slider("Max Chunk Tokens", 50, 300, 100)
            chunk_overlap = st.slider("Chunk Overlap Tokens", 0, 50, 10)
            noise_reduction = st.checkbox("Apply Noise Reduction", value=True)
        
        return {
            "extract_frames": extract_frames,
            "remove_duplicate_frames": deduplicate_frames,
            "frame_interval": frame_interval,
            "max_chunk_tokens": max_chunk_tokens,
            "chunk_overlap_tokens": chunk_overlap,
            "apply_noise_reduction": noise_reduction
        }
    
    return None


def process_video(
    video_path: Path,
    filename: str,
    enable_llm: bool = True,
    config_overrides: Optional[Dict[str, Any]] = None
):
    """
    Process uploaded video through the pipeline.
    
    Args:
        video_path: Path to uploaded video
        filename: Original filename
        enable_llm: Whether to use LLM for descriptions
        config_overrides: Configuration overrides
    """
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    metrics_placeholder = st.empty()
    
    def update_progress(msg: str, progress: float = None):
        with progress_placeholder.container():
            if progress is not None:
                st.progress(min(progress, 1.0), text=msg)
            else:
                st.info(msg)
    
    try:
        st.session_state.processing_in_progress = True
        
        # Create config
        update_progress("Preparing pipeline...", 0.05)
        config_dict = {
            "extract_audio": True,
            "audio_sample_rate": 16000,
            "enable_transcription": True,
            "asr_model": "base",
            "asr_language": None,
            "use_word_timestamps": True,
            "export_json": True,
            "export_txt": True,
            "export_srt": True,
            "export_vtt": True
        }
        
        if config_overrides:
            config_dict.update(config_overrides)
        
        config = MediaProcessorConfig(**config_dict)
        
        # Create processor
        update_progress("Initializing processor...", 0.1)
        output_dir = PipelineState.OUTPUT_DIR / filename.replace(".", "_")
        input_dir = video_path.parent
        processor = MediaProcessor(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            config=config
        )
        
        # Process video
        update_progress("Processing media...", 0.2)
        result = processor.process_file(str(video_path))
        
        if not result:
            st.error("❌ Failed to process video")
            return None
        
        # Extract counts from results
        if result.get("transcript_path") and Path(result["transcript_path"]).exists():
            with open(result["transcript_path"], 'r') as f:
                transcript_data = json.load(f)
                result["segments_count"] = len(transcript_data.get("segments", []))
        
        if result.get("chunks_path") and Path(result["chunks_path"]).exists():
            with open(result["chunks_path"], 'r') as f:
                chunks_data = json.load(f)
                result["chunks_count"] = len(chunks_data.get("chunks", []))
        
        result["frames_count"] = len(result.get("frame_paths", []))
        
        # Extract duration from metadata
        metadata_path = output_dir / "media_metadata" / f"{Path(video_path).stem}_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    result["duration"] = metadata.get("duration", result.get("duration", 0))
            except Exception as e:
                logger.warning(f"Could not extract duration from metadata: {e}")
                result["duration"] = result.get("duration", 0)
        else:
            result["duration"] = result.get("duration", 0)
        
        update_progress("Enhancing chunks with descriptions...", 0.6)
        
        # Enhance chunks with LLM descriptions
        chunks_path = output_dir / "transcript_chunks" / f"{Path(video_path).stem}_chunks.json"
        frame_meta_path = output_dir / "media_metadata" / f"{Path(video_path).stem}_frame_metadata.json"
        frames_dir = output_dir / "extracted_frames"
        
        enhanced_chunks_path = None
        if chunks_path.exists() and enable_llm:
            try:
                enhancer = EnhancedChunkProcessor(
                    chunks_json_path=str(chunks_path),
                    frame_metadata_json_path=str(frame_meta_path),
                    frames_dir=str(frames_dir),
                    video_path=str(video_path),
                    video_duration=result.get("duration", 0),
                    video_fps=result.get("fps", 29.97),
                    use_llm=enable_llm
                )
                
                enhanced_chunks, enhanced_frames, chunks_out, frames_out = enhancer.process_all(
                    context=f"Video: {filename}",
                    output_chunks_path=str(output_dir / "transcript_chunks" / f"{Path(video_path).stem}_enhanced_chunks.json"),
                    output_frames_path=str(output_dir / "media_metadata" / f"{Path(video_path).stem}_enhanced_frame_metadata.json")
                )
                
                result["enhanced_chunks"] = enhanced_chunks
                result["enhanced_frames"] = enhanced_frames
                enhanced_chunks_path = chunks_out
                
            except Exception as e:
                logger.warning(f"Could not enhance chunks: {str(e)}")
        
        # ========================= STEP 3: RAG INDEXING =========================
        # Use enhanced chunks if available, otherwise use regular chunks
        chunks_for_indexing = enhanced_chunks_path if enhanced_chunks_path and Path(enhanced_chunks_path).exists() else None
        
        if not chunks_for_indexing:
            # Fallback to regular chunks
            regular_chunks_path = output_dir / "transcript_chunks" / f"{Path(video_path).stem}_chunks.json"
            if regular_chunks_path.exists():
                chunks_for_indexing = regular_chunks_path
        
        if chunks_for_indexing and Path(chunks_for_indexing).exists():
            try:
                update_progress("Indexing chunks for RAG retrieval...", 0.85)
                
                # Initialize RAG pipeline with hybrid retrieval
                rag_pipeline = VideoRAGPipeline(
                    retrieval_method="hybrid",
                    use_frames=True
                )
                
                # Load chunks (works with both enhanced and regular chunks)
                chunks = rag_pipeline.load_enhanced_chunks(chunks_for_indexing)
                
                if chunks:
                    # Prepare video metadata
                    video_metadata = {
                        "filename": filename,
                        "duration": result.get("duration", 0),
                        "fps": result.get("fps", 29.97),
                        "total_chunks": len(chunks),
                        "chunks_type": "enhanced" if "enhanced" in str(chunks_for_indexing) else "regular"
                    }
                    
                    # Index chunks for RAG retrieval
                    success = rag_pipeline.index_video_chunks(chunks, video_metadata)
                    
                    if success:
                        # Save RAG index to disk
                        index_path = output_dir / "rag_index"
                        index_path.mkdir(parents=True, exist_ok=True)
                        
                        # Save BM25 index
                        if hasattr(rag_pipeline.retriever, 'bm25'):
                            bm25_file = index_path / "bm25_index.pkl"
                            with open(bm25_file, 'wb') as f:
                                pickle.dump({
                                    'bm25': rag_pipeline.retriever.bm25,
                                    'tokenized_docs': getattr(rag_pipeline.retriever, 'tokenized_docs', []),
                                    'documents': getattr(rag_pipeline.retriever, 'documents', [])
                                }, f)
                        
                        # Save indexed chunks metadata
                        metadata_file = index_path / "indexed_chunks.json"
                        with open(metadata_file, 'w') as f:
                            json.dump({
                                "total_chunks": len(chunks),
                                "retrieval_method": "hybrid",
                                "indexed_at": datetime.now().isoformat(),
                                "video_metadata": video_metadata,
                                "chunk_indices": [c.get("chunk_index", i) for i, c in enumerate(chunks)]
                            }, f, indent=2)
                        
                        result["rag_index_path"] = str(index_path)
                        result["chunks_indexed"] = len(chunks)
                        result["retrieval_ready"] = True
                        logger.info(f"✓ Indexed {len(chunks)} {video_metadata['chunks_type']} chunks with hybrid retrieval")
                    else:
                        logger.warning("RAG indexing returned False")
                        result["retrieval_ready"] = False
                else:
                    logger.warning("No chunks found for RAG indexing")
                    result["retrieval_ready"] = False
            
            except Exception as e:
                logger.warning(f"Could not index chunks for RAG: {str(e)}")
                result["retrieval_ready"] = False
        
        update_progress("Pipeline complete!", 1.0)
        
        update_progress("Pipeline complete!", 1.0)
        
        # Register processed video
        st.session_state.pipeline_state.register_processed_video(
            filename,
            {
                "output_dir": str(output_dir),
                "transcripts": str(output_dir / "transcripts"),
                "chunks": str(output_dir / "transcript_chunks"),
                "frames": str(output_dir / "extracted_frames"),
                "metadata": str(output_dir / "media_metadata")
            }
        )
        
        return result
    
    except Exception as e:
        st.error(f"❌ Pipeline error: {str(e)}")
        logger.exception("Pipeline error")
        return None
    
    finally:
        st.session_state.processing_in_progress = False


def render_results(result: Dict[str, Any], filename: str, enable_llm: bool = True):
    """Render processing results."""
    if not result:
        return
    
    st.markdown('<p class="subheader">✅ Processing Results</p>', unsafe_allow_html=True)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📝 Segments", result.get("segments_count", 0))
    with col2:
        st.metric("📦 Chunks", result.get("chunks_count", 0))
    with col3:
        st.metric("🎞️ Frames", result.get("frames_count", 0))
    with col4:
        st.metric("⏱️ Duration", f"{result.get('duration', 0):.1f}s")
    
    # RAG Status
    if result.get("chunks_indexed", 0) > 0:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🔍 Indexed Chunks", result.get("chunks_indexed", 0))
        with col2:
            if result.get("retrieval_ready"):
                st.success("✅ Hybrid Retrieval Ready")
            else:
                st.warning("⚠️ Retrieval Not Ready")
    else:
        st.info("⏳ **RAG indexing in progress or not available.** The search feature will appear here once chunks are indexed.")
    
    st.markdown("---")
    
    # RAG Search Section - PRIORITIZED before transcripts
    if result.get("retrieval_ready"):
        st.markdown("#### 🔍 RAG Semantic Search")
        st.info("💡 Ask questions about the video content and get AI-powered answers!")
        
        search_query = st.text_input(
            "Enter search query:",
            placeholder="e.g., What is Naive Bayes classifier?"
        )
        
        if search_query:
            try:
                # Initialize RAG pipeline for search
                from rag_retrievers import SimpleHybridRetriever
                
                output_dir = PipelineState.OUTPUT_DIR / filename.replace(".", "_")
                
                # Try enhanced chunks first, fall back to regular chunks
                enhanced_chunks_path = output_dir / "transcript_chunks" / f"{Path(filename).stem}_enhanced_chunks.json"
                regular_chunks_path = output_dir / "transcript_chunks" / f"{Path(filename).stem}_chunks.json"
                chunks_path = enhanced_chunks_path if enhanced_chunks_path.exists() else regular_chunks_path
                
                frame_meta_path = output_dir / "media_metadata" / f"{Path(filename).stem}_enhanced_frame_metadata.json"
                regular_frame_meta_path = output_dir / "media_metadata" / f"{Path(filename).stem}_frame_metadata.json"
                frame_meta = frame_meta_path if frame_meta_path.exists() else regular_frame_meta_path
                
                if Path(chunks_path).exists():
                    # Load chunks
                    with open(chunks_path, 'r') as f:
                        chunks_data = json.load(f)
                    
                    chunks = chunks_data.get("chunks", [])
                    
                    # Store chunks in session for metadata lookup
                    st.session_state.rag_chunks = {chunk.get('chunk_index', i): chunk for i, chunk in enumerate(chunks)}
                    
                    # Load and store frame metadata for frame lookup
                    frame_metadata_dict = {}
                    if Path(frame_meta).exists():
                        try:
                            with open(frame_meta, 'r') as f:
                                frame_meta_data = json.load(f)
                            # Create lookup dict by frame index and chunk index
                            for frame in frame_meta_data.get("frames", []):
                                frame_idx = frame.get("frame_index")
                                if frame_idx is not None:
                                    frame_metadata_dict[frame_idx] = frame
                            st.session_state.frame_metadata = frame_metadata_dict
                            st.session_state.frame_meta_config = frame_meta_data.get("metadata", {})
                        except Exception as e:
                            logger.debug(f"Could not load frame metadata: {str(e)}")
                    
                    # Prepare documents
                    documents = []
                    for i, chunk in enumerate(chunks):
                        doc = {
                            "id": f"chunk_{chunk.get('chunk_index', i)}",
                            "text": f"{chunk.get('text', '')} {chunk.get('text_description', '')}",
                            "source": "video",
                            "metadata": {
                                "chunk_index": chunk.get("chunk_index", i),
                                "start_time": chunk.get("start_time", 0),
                                "end_time": chunk.get("end_time", 0),
                                "description": chunk.get("text_description", ""),
                                "frames": len(chunk.get("associated_frames", []))
                            }
                        }
                        documents.append(doc)
                    
                    # Initialize hybrid retriever
                    retriever = SimpleHybridRetriever()
                    retriever.index_documents(documents)
                    
                    # Search
                    results = retriever.search(search_query, top_k=3)
                    
                    if results:
                        st.write(f"**Found {len(results)} relevant chunks:**")
                        
                        # Generate AI response based on retrieved chunks
                        if enable_llm:
                            try:
                                import os
                                from openai import OpenAI
                                
                                api_key = os.getenv("OPENAI_API_KEY")
                                if api_key:
                                    context_text = "\n\n".join([
                                        f"Chunk {i+1} (Time: {r.get('metadata', {}).get('start_time', 0):.1f}s):\n{r.get('text', '')[:500]}"
                                        for i, r in enumerate(results[:3])
                                    ])
                                    
                                    client = OpenAI(api_key=api_key)
                                    response = client.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=[
                                            {
                                                "role": "system",
                                                "content": "You are a helpful assistant answering questions based on video transcript content. Be concise and accurate."
                                            },
                                            {
                                                "role": "user",
                                                "content": f"Based on this transcript content:\n\n{context_text}\n\nAnswer this question: {search_query}"
                                            }
                                        ],
                                        max_tokens=300
                                    )
                                    
                                    answer = response.choices[0].message.content
                                    st.success(f"**🤖 AI Response:** {answer}")
                            except Exception as e:
                                logger.warning(f"Could not generate AI response: {str(e)}")
                        
                        st.markdown("---")
                        
                        # Display detailed results
                        for i, result_item in enumerate(results, 1):
                            score = result_item.get('score', 0)
                            meta = result_item.get("metadata", {})
                            
                            # The metadata should now be correctly preserved from the retriever
                            # chunk_index, start_time, end_time, description are all included
                            chunk_index = meta.get('chunk_index')
                            
                            # Try to get additional chunk data for frames
                            full_chunk = None
                            if chunk_index is not None and hasattr(st.session_state, 'rag_chunks'):
                                if chunk_index in st.session_state.rag_chunks:
                                    full_chunk = st.session_state.rag_chunks[chunk_index]
                            
                            # Ensure metadata has all required fields (now should come from retriever)
                            if not meta.get('chunk_index'):
                                meta['chunk_index'] = chunk_index
                            
                            with st.expander(f"📌 Result {i} - Relevance: {score:.1%}"):
                                # Metadata columns
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("⏱️ Start Time", f"{meta.get('start_time', 0):.1f}s")
                                with col2:
                                    st.metric("⏱️ End Time", f"{meta.get('end_time', 0):.1f}s")
                                with col3:
                                    st.metric("📍 Chunk Index", f"{meta.get('chunk_index', 'N/A')}")
                                with col4:
                                    # Count frames from the chunk if available
                                    frame_count = len(full_chunk.get('associated_frames', [])) if full_chunk else meta.get('frames', 0)
                                    st.metric("🎞️ Frames", frame_count)
                                
                                st.markdown("**📝 Full Text:**")
                                st.write(result_item.get('text', ''))
                                
                                st.markdown("**💬 LLM Description:**")
                                st.write(meta.get('description', 'No description available'))
                                
                                # Show related frames
                                frames_dir = output_dir / "extracted_frames"
                                # Handle both flat and nested directory structures
                                if not frames_dir.exists():
                                    frames_dir = output_dir / "extracted_frames" / Path(filename).stem
                                
                                frame_files = []
                                fps = 29.97  # Default FPS
                                
                                # Strategy 1: Use associated_frames from chunk if available
                                if full_chunk and full_chunk.get('associated_frames'):
                                    for frame_ref in full_chunk.get('associated_frames', []):
                                        if isinstance(frame_ref, dict):
                                            # Frame reference is a dict with frame_path and metadata
                                            frame_path = Path(frame_ref.get('frame_path', ''))
                                        else:
                                            # Frame reference is a string (filename)
                                            frame_path = Path(frame_ref)
                                        
                                        # Make absolute path if needed
                                        if not frame_path.is_absolute():
                                            frame_path = frames_dir / frame_path.name
                                        
                                        if frame_path.exists():
                                            frame_files.append(frame_path)
                                
                                # Strategy 2: Fallback - find by timestamp range using frame metadata
                                if not frame_files:
                                    try:
                                        # Try enhanced frame metadata first, then regular frame metadata
                                        frame_meta_path = output_dir / "media_metadata" / f"{Path(filename).stem}_enhanced_frame_metadata.json"
                                        if not frame_meta_path.exists():
                                            frame_meta_path = output_dir / "media_metadata" / f"{Path(filename).stem}_frame_metadata.json"
                                        
                                        if frame_meta_path.exists():
                                            with open(frame_meta_path, 'r') as f:
                                                frame_meta_data = json.load(f)
                                            
                                            fps = frame_meta_data.get("metadata", {}).get("fps", 29.97)
                                            start_time = meta.get('start_time', 0)
                                            end_time = meta.get('end_time', 0)
                                            chunk_idx = meta.get('chunk_index')
                                            
                                            for frame in frame_meta_data.get("frames", []):
                                                # Match frames that belong to this chunk
                                                if frame.get("associated_chunk_index") == chunk_idx:
                                                    frame_path = Path(frame.get('frame_path', ''))
                                                    if not frame_path.is_absolute():
                                                        frame_path = frames_dir / frame_path.name
                                                    if frame_path.exists():
                                                        frame_files.append(frame_path)
                                    except Exception as e:
                                        logger.debug(f"Frame metadata lookup failed: {str(e)}")
                                
                                # Strategy 3: Fallback - find by timestamp range (frames directory scan)
                                if not frame_files and frames_dir.exists():
                                    start_time = meta.get('start_time', 0)
                                    end_time = meta.get('end_time', 0)
                                    
                                    # Search in both direct directory and subdirectories
                                    search_paths = [
                                        frames_dir.glob("*.jpg"),
                                        frames_dir.glob("**/*.jpg")  # Recursive search
                                    ]
                                    
                                    for pattern_frames in search_paths:
                                        for frame_path in sorted(pattern_frames):
                                            try:
                                                # Try to extract frame number from filename
                                                stem = frame_path.stem
                                                # Pattern: video_name_framenum or just framenum
                                                if '_' in stem:
                                                    frame_num = int(stem.split('_')[-1])
                                                else:
                                                    frame_num = int(stem)
                                                
                                                frame_time = frame_num / fps
                                                if start_time <= frame_time <= end_time:
                                                    frame_files.append(frame_path)
                                            except (ValueError, IndexError):
                                                pass
                                        
                                        # Stop searching if we found frames
                                        if frame_files:
                                            break
                                
                                if frame_files:
                                    st.markdown(f"**🎬 Related Frames ({len(frame_files)} found):**")
                                    frame_cols = st.columns(min(3, len(frame_files)))
                                    
                                    for idx, frame_path in enumerate(frame_files[:3]):
                                        with frame_cols[idx % 3]:
                                            try:
                                                from PIL import Image
                                                img = Image.open(frame_path)
                                                st.image(img)
                                                st.caption(f"Frame {frame_path.stem}")
                                            except Exception as e:
                                                logger.warning(f"Could not load frame {frame_path}: {str(e)}")
                                else:
                                    st.info("ℹ️ No frames available for this chunk (audio-only content or frames not extracted)")
                                    # Debug info
                                    if logger.getEffectiveLevel() <= logging.DEBUG:
                                        st.caption(f"Debug: frames_dir={frames_dir}, exists={frames_dir.exists()}")
                    else:
                        st.warning("No relevant chunks found")
                else:
                    st.error("❌ Could not find chunks file. Please ensure the video has been processed.")
            
            except Exception as e:
                st.error(f"Search error: {str(e)}")
        
        st.markdown("---")
    
    # Transcripts
    output_dir = PipelineState.OUTPUT_DIR / filename.replace(".", "_")
    transcripts_dir = output_dir / "transcripts"
    
    if transcripts_dir.exists():
        st.markdown("#### 📄 Transcripts")
        transcript_files = list(transcripts_dir.glob(f"{Path(filename).stem}.*"))
        
        col1, col2, col3, col4 = st.columns(4)
        
        for idx, tf in enumerate(sorted(transcript_files)):
            col = [col1, col2, col3, col4][idx % 4]
            with col:
                with open(tf, 'r') as f:
                    content = f.read()
                st.download_button(
                    f"📥 {tf.suffix[1:].upper()}",
                    content,
                    file_name=tf.name,
                    mime="text/plain"
                )
        
        # Show preview
        with st.expander("Preview Transcript", expanded=True):
            txt_file = transcripts_dir / f"{Path(filename).stem}.txt"
            if txt_file.exists():
                with open(txt_file, 'r') as f:
                    content = f.read()
                st.text_area("Transcript Content", content, height=150, disabled=True)
    
    st.markdown("---")
    
    # Chunks
    chunks_dir = output_dir / "transcript_chunks"
    if chunks_dir.exists():
        st.markdown("#### 📑 Transcript Chunks")
        
        chunk_file = chunks_dir / f"{Path(filename).stem}_enhanced_chunks.json"
        if not chunk_file.exists():
            chunk_file = chunks_dir / f"{Path(filename).stem}_chunks.json"
        
        if chunk_file.exists():
            with open(chunk_file, 'r') as f:
                chunks_data = json.load(f)
            
            chunks = chunks_data.get("chunks", [])
            st.write(f"**Total Chunks:** {len(chunks)}")
            
            # Display first 3 chunks
            for i, chunk in enumerate(chunks[:3]):
                with st.expander(f"Chunk {i+1} ({chunk.get('start_time', 0):.1f}s - {chunk.get('end_time', 0):.1f}s)"):
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.write("**Transcript:**")
                        st.write(chunk.get("text", "")[:200] + "...")
                    
                    with col2:
                        st.write("**Description:**")
                        st.write(chunk.get("text_description", "N/A")[:200] + "...")
                    
                    st.write(f"**Tokens:** {chunk.get('token_count', 0)}")
                    if chunk.get("associated_frames"):
                        st.write(f"**Associated Frames:** {len(chunk.get('associated_frames', []))}")
    
    st.markdown("---")
    
    # Frames
    frames_dir = output_dir / "extracted_frames"
    if frames_dir.exists():
        st.markdown("#### 🎞️ Extracted Frames")
        
        frames_list = list(frames_dir.glob(f"{Path(filename).stem}/*.jpg"))
        st.write(f"**Total Frames:** {len(frames_list)}")
        
        # Show frame grid
        if frames_list:
            cols = st.columns(5)
            for idx, frame_path in enumerate(sorted(frames_list)[:10]):
                col = cols[idx % 5]
                with col:
                    from PIL import Image
                    try:
                        img = Image.open(frame_path)
                        st.image(img)
                        st.caption(f"Frame {idx}")
                    except Exception as e:
                        st.warning(f"Could not load frame: {str(e)}")
    
    st.markdown("---")
    
    # Download outputs
    st.markdown("#### 📥 Download Results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if (output_dir / "media_metadata" / f"{Path(filename).stem}_metadata.json").exists():
            with open(output_dir / "media_metadata" / f"{Path(filename).stem}_metadata.json", 'r') as f:
                metadata = json.dumps(json.load(f), indent=2)
            st.download_button(
                "📥 Metadata JSON",
                metadata,
                file_name="metadata.json",
                mime="application/json"
            )
    
    with col2:
        if chunk_file.exists():
            with open(chunk_file, 'r') as f:
                chunks_json = f.read()
            st.download_button(
                "📥 Enhanced Chunks",
                chunks_json,
                file_name="chunks.json",
                mime="application/json"
            )
    
    with col3:
        frame_meta = output_dir / "media_metadata" / f"{Path(filename).stem}_frame_metadata.json"
        if frame_meta.exists():
            with open(frame_meta, 'r') as f:
                frame_json = f.read()
            st.download_button(
                "📥 Frame Metadata",
                frame_json,
                file_name="frame_metadata.json",
                mime="application/json"
            )


def load_existing_results(filename: str) -> Dict[str, Any]:
    """Load results from existing processed video."""
    output_dir = PipelineState.OUTPUT_DIR / filename.replace(".", "_")
    result = {
        "filename": filename,
        "segments_count": 0,
        "chunks_count": 0,
        "frames_count": 0,
        "duration": 0,
        "chunks_indexed": 0,
        "retrieval_ready": False
    }
    
    # Load segment count
    transcript_path = output_dir / "transcripts" / f"{Path(filename).stem}.json"
    if transcript_path.exists():
        with open(transcript_path, 'r') as f:
            transcript_data = json.load(f)
            result["segments_count"] = len(transcript_data.get("segments", []))
    
    # Load chunk count
    chunks_path = output_dir / "transcript_chunks" / f"{Path(filename).stem}_chunks.json"
    if chunks_path.exists():
        with open(chunks_path, 'r') as f:
            chunks_data = json.load(f)
            result["chunks_count"] = len(chunks_data.get("chunks", []))
    
    # Count frames
    frames_dir = output_dir / "extracted_frames"
    if frames_dir.exists():
        result["frames_count"] = len(list(frames_dir.glob("*.jpg")))
    
    # Check for RAG index
    rag_index_path = output_dir / "rag_index" / "indexed_chunks.json"
    if rag_index_path.exists():
        with open(rag_index_path, 'r') as f:
            index_data = json.load(f)
            result["chunks_indexed"] = index_data.get("total_chunks", 0)
            result["retrieval_ready"] = result["chunks_indexed"] > 0
    
    return result


def render_history_section():
    """Render processing history with clickable selection."""
    if st.session_state.pipeline_state.processed_videos:
        st.markdown('<p class="subheader">📋 Processing History</p>', unsafe_allow_html=True)
        
        history_data = []
        filenames = []
        for filename, info in st.session_state.pipeline_state.processed_videos.items():
            history_data.append({
                "Filename": filename,
                "Processed": info.get("processed_at", "N/A")[:10]
            })
            filenames.append(filename)
        
        df = pd.DataFrame(history_data)
        st.dataframe(df, width="stretch")
        
        # Selection buttons
        st.write("**Select a video to view its results:**")
        cols = st.columns(min(3, len(filenames)))
        
        for idx, filename in enumerate(filenames):
            with cols[idx % 3]:
                if st.button(f"📽️ {Path(filename).stem}", key=f"select_{filename}"):
                    st.session_state.selected_video = filename
                    st.rerun()


def main():
    """Main application."""
    render_header()
    
    if not IMPORTS_AVAILABLE:
        st.error(f"❌ Import Error: {IMPORT_ERROR}")
        st.info("Please ensure all dependencies are installed: pip install -r requirements.txt")
        return
    
    # Sidebar
    with st.sidebar:
        st.markdown("### Settings")
        
        debug_mode = st.checkbox("Debug Mode", value=False)
        
        # Enable debug logging if debug mode is on
        if debug_mode:
            logger.setLevel(logging.DEBUG)
            st.caption("🐛 Debug mode enabled - verbose logging active")
        else:
            logger.setLevel(logging.INFO)
        
        if st.button("🗑️ Clear Cache"):
            st.cache_resource.clear()
            st.success("Cache cleared")
    
    # Main content
    tab1, tab2 = st.tabs(["🚀 Process Video", "📊 Results"])
    
    with tab1:
        uploaded_file, enable_llm = render_upload_section()
        config_overrides = render_config_section()
        
        if uploaded_file:
            col1, col2 = st.columns(2)
            
            with col1:
                process_button = st.button(
                    "▶️ Start Processing",
                    disabled=st.session_state.processing_in_progress,
                    type="primary"
                )
            
            with col2:
                st.write("")  # Spacing
            
            if process_button:
                # Save uploaded file
                upload_path = PipelineState.UPLOAD_DIR / uploaded_file.name
                with open(upload_path, 'wb') as f:
                    f.write(uploaded_file.getbuffer())
                
                # Process
                with st.spinner("Processing video..."):
                    result = process_video(
                        upload_path,
                        uploaded_file.name,
                        enable_llm=enable_llm,
                        config_overrides=config_overrides
                    )
                
                if result:
                    st.success("✅ Processing complete!")
                    st.session_state.last_result = result
                    st.session_state.last_filename = uploaded_file.name
                    st.session_state.last_enable_llm = enable_llm
    
    with tab2:
        # Check if user selected a video from history
        if hasattr(st.session_state, "selected_video") and st.session_state.selected_video:
            filename = st.session_state.selected_video
            existing_result = load_existing_results(filename)
            st.write(f"**Loaded results for: {filename}**")
            render_results(existing_result, filename, enable_llm=True)
        elif hasattr(st.session_state, "last_result") and st.session_state.last_result:
            enable_llm_last = getattr(st.session_state, "last_enable_llm", True)
            render_results(st.session_state.last_result, st.session_state.last_filename, enable_llm=enable_llm_last)
        else:
            st.info("📌 Select a video from history below to view its results.")
        
        st.markdown("---")
        render_history_section()


if __name__ == "__main__":
    main()
