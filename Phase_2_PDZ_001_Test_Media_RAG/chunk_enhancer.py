"""
Enhanced Chunk Processing with LLM Descriptions and Frame Metadata.

Adds text descriptions and frame metadata to video/audio chunks before embedding.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import time

from dotenv import load_dotenv, find_dotenv
import os

load_dotenv(find_dotenv())  # Load environment variables from .env file

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@dataclass
class ChunkEnhancement:
    """Enhanced chunk with LLM description and metadata."""
    chunk_index: int
    text: str
    text_description: str  # NEW: LLM-generated description
    token_count: int
    segment_indices: List[int]
    start_time: float
    end_time: float
    duration: float  # NEW: Chunk duration
    associated_frames: List[Dict[str, Any]]  # NEW: Frame metadata


@dataclass
class FrameMetadata:
    """Complete metadata for extracted frame."""
    frame_path: str
    frame_index: int
    video_timestamp: float  # When in video this frame appears
    extraction_timestamp: str  # When it was extracted (ISO format)
    frame_hash: Optional[str] = None
    is_duplicate: bool = False
    similarity_score: Optional[float] = None
    associated_chunk_index: Optional[int] = None  # Which chunk contains this frame's timestamp


class ChunkDescriptionGenerator:
    """Generate LLM descriptions for transcript chunks."""
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        """
        Initialize the description generator.
        
        Args:
            model: LLM model to use (OpenAI by default)
            api_key: OpenAI API key (reads from OPENAI_API_KEY env var if not provided)
        """
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI library not installed. Descriptions will be skipped.")
            self.client = None
            return
        
        self.model = model
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        # Use provided api_key or read from environment
        # If api_key is None, OpenAI client reads OPENAI_API_KEY automatically
        try:
            self.client = OpenAI(api_key=api_key)
            logger.info(f"Initialized description generator with model: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            self.client = None
    
    def generate_description(self, chunk_text: str, context: Optional[str] = None) -> str:
        """
        Generate a concise description of what's being said in the chunk.
        
        Args:
            chunk_text: The transcript chunk text
            context: Optional context (e.g., video title, module name)
        
        Returns:
            Generated description
        """
        if not self.client:
            logger.warning("OpenAI client not available, returning empty description")
            return ""
        
        try:
            context_str = f"\nContext: {context}" if context else ""
            
            prompt = f"""Provide a brief, informative one-sentence summary of the main topic or concept being discussed in the following transcript excerpt. Focus on the key information being conveyed.

Transcript:
{chunk_text}
{context_str}

Summary:"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.3  # More deterministic
            )
            
            description = response.choices[0].message.content.strip()
            logger.debug(f"Generated description: {description[:80]}...")
            return description
            
        except Exception as e:
            logger.error(f"Error generating description: {str(e)}")
            return ""
    
    def generate_batch_descriptions(
        self, 
        chunks: List[Dict[str, Any]], 
        context: Optional[str] = None
    ) -> List[str]:
        """
        Generate descriptions for multiple chunks.
        
        Args:
            chunks: List of chunk dictionaries with 'text' field
            context: Optional context for all chunks
        
        Returns:
            List of descriptions
        """
        descriptions = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Generating description for chunk {i+1}/{len(chunks)}...")
            desc = self.generate_description(chunk.get("text", ""), context)
            descriptions.append(desc)
            time.sleep(0.1)  # Small delay to avoid rate limiting
        
        return descriptions


class FrameMetadataBuilder:
    """Build comprehensive metadata for extracted frames."""
    
    def __init__(self, video_path: str, video_duration: float, fps: float):
        """
        Initialize frame metadata builder.
        
        Args:
            video_path: Path to the original video
            video_duration: Duration of the video in seconds
            fps: Frames per second of the video
        """
        self.video_path = video_path
        self.video_duration = video_duration
        self.fps = fps
        self.extraction_time = datetime.now().isoformat()
    
    def build_frame_metadata(
        self,
        frame_path: str,
        frame_index: int,
        frame_hash: Optional[str] = None,
        is_duplicate: bool = False,
        similarity_score: Optional[float] = None
    ) -> FrameMetadata:
        """
        Build metadata for a single frame.
        
        Args:
            frame_path: Path to the frame file
            frame_index: Index of the frame in the video
            frame_hash: Optional perceptual hash of the frame
            is_duplicate: Whether this is a duplicate frame
            similarity_score: Similarity score to previous frame
        
        Returns:
            FrameMetadata object
        """
        # Calculate timestamp: frame_index / fps = timestamp in seconds
        video_timestamp = (frame_index / self.fps) if self.fps > 0 else 0
        
        # Clamp to video duration
        video_timestamp = min(video_timestamp, self.video_duration)
        
        return FrameMetadata(
            frame_path=str(frame_path),
            frame_index=frame_index,
            video_timestamp=video_timestamp,
            extraction_timestamp=self.extraction_time,
            frame_hash=frame_hash,
            is_duplicate=is_duplicate,
            similarity_score=similarity_score
        )
    
    def associate_frames_with_chunks(
        self,
        frame_metadata_list: List[FrameMetadata],
        chunks: List[Dict[str, Any]]
    ) -> List[FrameMetadata]:
        """
        Associate each frame with the chunk that contains its timestamp.
        
        Args:
            frame_metadata_list: List of frame metadata objects
            chunks: List of chunk dictionaries with start_time/end_time
        
        Returns:
            Updated frame metadata with chunk associations
        """
        for frame_meta in frame_metadata_list:
            for chunk in chunks:
                start = chunk.get("start_time", 0)
                end = chunk.get("end_time", 0)
                
                if start <= frame_meta.video_timestamp <= end:
                    frame_meta.associated_chunk_index = chunk.get("chunk_index")
                    break
        
        return frame_metadata_list


class EnhancedChunkProcessor:
    """Process chunks with LLM descriptions and frame metadata."""
    
    def __init__(
        self,
        chunks_json_path: str,
        frame_metadata_json_path: str,
        frames_dir: str,
        video_path: str,
        video_duration: float,
        video_fps: float,
        use_llm: bool = True
    ):
        """
        Initialize enhanced chunk processor.
        
        Args:
            chunks_json_path: Path to chunks JSON file
            frame_metadata_json_path: Path to frame metadata JSON file
            frames_dir: Directory containing extracted frames
            video_path: Path to original video
            video_duration: Duration of video in seconds
            video_fps: Frames per second of video
            use_llm: Whether to use LLM for descriptions
        """
        self.chunks_path = Path(chunks_json_path)
        self.frame_meta_path = Path(frame_metadata_json_path)
        self.frames_dir = Path(frames_dir)
        self.video_path = video_path
        self.video_duration = video_duration
        self.video_fps = video_fps
        self.use_llm = use_llm
        
        self.desc_generator = ChunkDescriptionGenerator() if use_llm else None
        self.frame_builder = FrameMetadataBuilder(video_path, video_duration, video_fps)
        
        self.chunks_data = None
        self.frame_data = None
    
    def load_chunks(self) -> Dict[str, Any]:
        """Load chunks from JSON file."""
        try:
            with open(self.chunks_path, 'r') as f:
                self.chunks_data = json.load(f)
            logger.info(f"Loaded {len(self.chunks_data.get('chunks', []))} chunks")
            return self.chunks_data
        except Exception as e:
            logger.error(f"Error loading chunks: {str(e)}")
            return {}
    
    def load_frame_metadata(self) -> Dict[str, Any]:
        """Load frame metadata from JSON file."""
        try:
            with open(self.frame_meta_path, 'r') as f:
                data = json.load(f)
            
            # Handle both list and dict formats
            if isinstance(data, list):
                # If it's a list, wrap it in a dict
                self.frame_data = {'frames': data}
            else:
                # If it's already a dict, use as-is
                self.frame_data = data
            
            frames_count = len(self.frame_data.get('frames', []))
            logger.info(f"Loaded {frames_count} frame metadata entries")
            return self.frame_data
        except Exception as e:
            logger.error(f"Error loading frame metadata: {str(e)}")
            return {}
    
    def enhance_chunks(self, context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Add LLM descriptions to chunks.
        
        Args:
            context: Optional context for LLM (e.g., video title)
        
        Returns:
            Enhanced chunks with descriptions
        """
        if not self.chunks_data:
            self.load_chunks()
        
        chunks = self.chunks_data.get('chunks', [])
        logger.info(f"Enhancing {len(chunks)} chunks with descriptions...")
        
        for chunk in chunks:
            if self.use_llm and self.desc_generator and self.desc_generator.client:
                description = self.desc_generator.generate_description(
                    chunk.get("text", ""),
                    context
                )
            else:
                description = ""
            
            chunk["text_description"] = description
            chunk["duration"] = chunk.get("end_time", 0) - chunk.get("start_time", 0)
        
        logger.info("Chunk enhancement complete")
        return chunks
    
    def enhance_frame_metadata(self) -> List[Dict[str, Any]]:
        """
        Enhance frame metadata with complete information.
        
        Args:
            (Loads from instance variables)
        
        Returns:
            Enhanced frame metadata
        """
        if not self.frame_data:
            self.load_frame_metadata()
        
        frames = self.frame_data.get('frames', [])
        logger.info(f"Enhancing {len(frames)} frame metadata entries...")
        
        # Rebuild frame metadata with timestamps
        enhanced_frames = []
        for frame_entry in frames:
            try:
                frame_path = frame_entry.get("frame_path", "")
                
                # Extract frame index from filename (frame_XXXXXX.jpg)
                frame_idx = int(Path(frame_path).stem.split('_')[-1])
                
                frame_meta = self.frame_builder.build_frame_metadata(
                    frame_path=frame_path,
                    frame_index=frame_idx,
                    frame_hash=frame_entry.get("hash"),
                    is_duplicate=frame_entry.get("is_duplicate", False),
                    similarity_score=frame_entry.get("similarity_to_previous")
                )
                
                enhanced_frames.append(asdict(frame_meta))
            
            except Exception as e:
                logger.error(f"Error processing frame {frame_entry}: {str(e)}")
                continue
        
        logger.info(f"Enhanced {len(enhanced_frames)} frame entries with metadata")
        return enhanced_frames
    
    def associate_frames_to_chunks(
        self,
        enhanced_chunks: List[Dict[str, Any]],
        enhanced_frames: List[Dict[str, Any]]
    ) -> tuple:
        """
        Associate frames with chunks based on timestamps.
        Updates both chunks (with associated_frames) and frames (with associated_chunk_index).
        
        Args:
            enhanced_chunks: Enhanced chunk list
            enhanced_frames: Enhanced frame metadata list
        
        Returns:
            Tuple of (updated_chunks, updated_frames)
        """
        logger.info("Associating frames with chunks by timestamp...")
        
        # Initialize associated_frames for all chunks
        for chunk in enhanced_chunks:
            chunk["associated_frames"] = []
        
        # Associate each frame with its chunk and update both
        for frame in enhanced_frames:
            frame_ts = frame.get("video_timestamp", 0)
            frame["associated_chunk_index"] = None  # Default to None
            
            for chunk in enhanced_chunks:
                start = chunk.get("start_time", 0)
                end = chunk.get("end_time", 0)
                
                if start <= frame_ts <= end:
                    # Update frame with chunk index
                    frame["associated_chunk_index"] = chunk.get("chunk_index")
                    
                    # Add frame reference to chunk
                    chunk["associated_frames"].append({
                        "frame_path": frame.get("frame_path"),
                        "frame_index": frame.get("frame_index"),
                        "video_timestamp": frame_ts
                    })
                    break
        
        frames_with_chunks = sum(1 for f in enhanced_frames if f.get("associated_chunk_index") is not None)
        chunks_with_frames = sum(1 for c in enhanced_chunks if len(c.get("associated_frames", [])) > 0)
        logger.info(f"Frame-to-chunk association complete:")
        logger.info(f"  • Frames with chunks: {frames_with_chunks}/{len(enhanced_frames)}")
        logger.info(f"  • Chunks with frames: {chunks_with_frames}/{len(enhanced_chunks)}")
        
        return enhanced_chunks, enhanced_frames
    
    def save_enhanced_chunks(self, output_path: str) -> str:
        """Save enhanced chunks to JSON."""
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            output_data = {
                "metadata": self.chunks_data.get("metadata", {}),
                "chunks": self.chunks_data.get("chunks", [])
            }
            
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            logger.info(f"Saved enhanced chunks to {output_path}")
            return str(output_file)
        
        except Exception as e:
            logger.error(f"Error saving enhanced chunks: {str(e)}")
            return ""
    
    def save_enhanced_frame_metadata(self, frames: List[Dict[str, Any]], output_path: str) -> str:
        """Save enhanced frame metadata to JSON.
        
        Args:
            frames: The enhanced frames list to save
            output_path: Output file path
        
        Returns:
            Path to saved file
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            output_data = {
                "metadata": {
                    "video_path": self.video_path,
                    "video_duration": self.video_duration,
                    "fps": self.video_fps,
                    "total_frames": len(frames),
                    "enhanced_at": datetime.now().isoformat()
                },
                "frames": frames
            }
            
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            logger.info(f"Saved enhanced frame metadata to {output_path}")
            return str(output_file)
        
        except Exception as e:
            logger.error(f"Error saving enhanced frame metadata: {str(e)}")
            return ""
    
    def process_all(
        self,
        context: Optional[str] = None,
        output_chunks_path: Optional[str] = None,
        output_frames_path: Optional[str] = None
    ) -> tuple:
        """
        Run complete enhancement pipeline.
        
        Args:
            context: Optional context for LLM descriptions
            output_chunks_path: Where to save enhanced chunks
            output_frames_path: Where to save enhanced frame metadata
        
        Returns:
            Tuple of (enhanced_chunks, enhanced_frames, chunks_output_path, frames_output_path)
        """
        logger.info("=" * 80)
        logger.info("STARTING ENHANCED CHUNK PROCESSING")
        logger.info("=" * 80)
        
        # Step 1: Load existing data
        self.load_chunks()
        self.load_frame_metadata()
        
        # Step 2: Enhance chunks with descriptions
        enhanced_chunks = self.enhance_chunks(context)
        
        # Step 3: Enhance frame metadata
        enhanced_frames = self.enhance_frame_metadata()
        
        # Step 4: Associate frames with chunks (updates both lists)
        enhanced_chunks, enhanced_frames = self.associate_frames_to_chunks(
            enhanced_chunks,
            enhanced_frames
        )
        
        # Step 5: Update internal state
        self.chunks_data["chunks"] = enhanced_chunks
        self.frame_data["frames"] = enhanced_frames
        
        # Step 6: Save results
        chunks_out = output_chunks_path or str(self.chunks_path.parent / "enhanced_chunks.json")
        frames_out = output_frames_path or str(self.chunks_path.parent / "enhanced_frame_metadata.json")
        
        chunks_saved = self.save_enhanced_chunks(chunks_out)
        frames_saved = self.save_enhanced_frame_metadata(enhanced_frames, frames_out)
        
        logger.info("=" * 80)
        logger.info("ENHANCEMENT COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Enhanced chunks: {chunks_saved}")
        logger.info(f"Enhanced frame metadata: {frames_saved}")
        
        return enhanced_chunks, enhanced_frames, chunks_saved, frames_saved


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python chunk_enhancer.py <chunks_json_path> <frame_metadata_path> [frames_dir] [video_path] [duration] [fps]")
        sys.exit(1)
    
    chunks_path = sys.argv[1]
    frame_meta_path = sys.argv[2]
    frames_dir = sys.argv[3] if len(sys.argv) > 3 else "output/extracted_frames"
    video_path = sys.argv[4] if len(sys.argv) > 4 else "input/video.mp4"
    duration = float(sys.argv[5]) if len(sys.argv) > 5 else 210.0
    fps = float(sys.argv[6]) if len(sys.argv) > 6 else 29.97
    
    processor = EnhancedChunkProcessor(
        chunks_json_path=chunks_path,
        frame_metadata_json_path=frame_meta_path,
        frames_dir=frames_dir,
        video_path=video_path,
        video_duration=duration,
        video_fps=fps,
        use_llm=True
    )
    
    processor.process_all(context="NLP Basics Lecture")
