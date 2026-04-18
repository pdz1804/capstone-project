"""
Enhanced Media Processor Module

This module handles advanced video and audio processing for the RAG pipeline.
- Extracts audio from video files with noise reduction
- Transcribes audio using Whisper with full parameters and word-level timestamps
- Performs intelligent transcript chunking (max 100 tokens per chunk)
- Extracts frames with duplicate removal and frame-level metadata
- Tracks complete provenance metadata for all outputs

Based on Week0506_Mkhoi_OCR_ASR implementation with comprehensive enhancements.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, Any
from dataclasses import dataclass, asdict
import logging
from datetime import datetime
import time
from tqdm import tqdm
import tempfile
import hashlib
from collections import Counter
import subprocess

from .whisper_remote import invoke_sagemaker_whisper, should_use_sagemaker_whisper

# Audio/Video processing
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    import librosa
    import librosa.effects
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

try:
    from moviepy import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import scipy.signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False


# ======================== Logging Setup ========================

def setup_logging(log_path: Optional[Path] = None):
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

logger = setup_logging()


# ======================== Configuration ========================

@dataclass
class MediaProcessorConfig:
    """Configuration for media processing."""
    
    # Audio extraction
    extract_audio: bool = True
    audio_sample_rate: int = 16000
    audio_format: str = "wav"
    
    # Audio noise reduction
    apply_noise_reduction: bool = True
    noise_reduction_threshold: float = 40  # Librosa trim top_db parameter (dB, not ratio)
    
    # Transcription
    enable_transcription: bool = True
    asr_model: str = "base"  # tiny, base, small, medium, large
    asr_language: Optional[str] = None  # Auto-detect language (None = auto)
    
    # Whisper advanced parameters
    use_word_timestamps: bool = True
    temperature_schedule: Tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    compression_ratio_threshold: float = 2.4
    logprob_threshold: float = -1.0
    no_speech_threshold: float = 0.1  # Very permissive to capture all speech
    condition_on_previous_text: bool = True
    
    # Transcript chunking
    max_chunk_tokens: int = 100
    chunk_overlap_tokens: int = 10
    
    # Frame extraction
    extract_frames: bool = True
    frame_interval: int = 30  # Extract every Nth frame
    frame_format: str = "jpg"
    frame_quality: int = 85  # JPEG quality 0-100
    min_frame_quality: float = 0.1  # Minimum Laplacian variance
    
    # Frame deduplication
    remove_duplicate_frames: bool = True
    frame_similarity_threshold: float = 0.95  # 0-1 range, similarity score
    
    # Export options
    export_txt: bool = True
    export_json: bool = True
    export_srt: bool = True
    export_vtt: bool = True
    export_md: bool = True   # Markdown export for Stage 3 Docling compatibility
    export_metadata: bool = True
    
    # Backward-compatible fields (used by pipeline.py CLI)
    use_gpu: bool = True
    audio_channels: int = 1  # Mono (hardcoded in librosa.load)
    chunk_duration: int = 30  # Legacy chunked processing duration
    chunk_overlap: float = 1.0  # Legacy chunked overlap
    
    # Device
    device: str = "cuda" if TORCH_AVAILABLE and torch.cuda.is_available() else "cpu"
    compute_dtype: str = "float16" if device == "cuda" else "float32"

    # Optional remote ASR (single shared SageMaker endpoint can host Whisper op)
    use_aws_sagemaker_whisper: bool = False
    sagemaker_whisper_endpoint_name: str = ""
    aws_region: str = "us-west-2"
    
    def __post_init__(self):
        """Sync device with use_gpu flag for backward compatibility."""
        if not self.use_gpu:
            self.device = "cpu"
            self.compute_dtype = "float32"


# ======================== Audio Noise Reduction ========================

class AudioNoiseReducer:
    """Reduce noise from extracted audio."""
    
    def __init__(self, config: MediaProcessorConfig):
        """Initialize noise reducer."""
        self.config = config
    
    def reduce_noise(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Reduce noise from audio using high-pass filter only.
        Skip aggressive silence trimming that destroys the signal.
        
        Args:
            audio: Audio signal as numpy array
            sr: Sample rate
        
        Returns:
            Denoised audio signal
        """
        if not NUMPY_AVAILABLE:
            logger.warning("numpy not available, skipping noise reduction")
            return audio
        
        try:
            original_length = len(audio)
            logger.info(f"Original audio length: {original_length} samples")
            
            # Apply high-pass filter to remove rumble and low-frequency noise
            if SCIPY_AVAILABLE:
                # High-pass filter at 80 Hz to remove rumble and DC bias
                sos = scipy.signal.butter(4, 80, 'hp', fs=sr, output='sos')
                audio_filtered = scipy.signal.sosfilt(sos, audio)
                logger.info(f"Applied high-pass filter (80 Hz) for rumble removal")
                return audio_filtered
            else:
                logger.warning("scipy not available, returning audio as-is")
                return audio
        
        except Exception as e:
            logger.error(f"Error reducing noise: {str(e)}")
            return audio


# ======================== Frame Deduplication ========================

class FrameDeduplicator:
    """Remove duplicate frames from extracted frame set."""
    
    def __init__(self, config: MediaProcessorConfig):
        """Initialize deduplicator."""
        self.config = config
    
    def compute_frame_hash(self, frame_path: Path) -> Optional[str]:
        """
        Compute perceptual hash for frame using PIL and imagehash.
        Falls back to histogram-based comparison if imagehash unavailable.
        
        Args:
            frame_path: Path to frame image
        
        Returns:
            Hash string or None if error
        """
        try:
            if IMAGEHASH_AVAILABLE and PIL_AVAILABLE:
                img = Image.open(frame_path)
                # Use average hash (fast and effective)
                img_hash = imagehash.average_hash(img)
                return str(img_hash)
            elif PIL_AVAILABLE:
                # Fallback: histogram-based hash
                img = Image.open(frame_path)
                hist = img.histogram()
                return hashlib.md5(str(hist).encode()).hexdigest()
            return None
        except Exception as e:
            logger.error(f"Error hashing frame {frame_path}: {str(e)}")
            return None
    
    def compute_similarity(self, hash1: str, hash2: str) -> float:
        """
        Compute similarity between two hashes (0-1, higher = more similar).
        
        Args:
            hash1: First hash string
            hash2: Second hash string
        
        Returns:
            Similarity score 0-1
        """
        if IMAGEHASH_AVAILABLE:
            # If using imagehash format (hexadecimal string)
            if len(hash1) == 16 and len(hash2) == 16:  # Average hash produces 16 char hex
                try:
                    # Hamming distance normalized
                    distance = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
                    # Max distance is 64 (16 * 4 bits)
                    similarity = 1.0 - (distance / 64.0)
                    return similarity
                except:
                    pass
        
        # Fallback: simple string similarity
        if hash1 == hash2:
            return 1.0
        return 0.0
    
    def deduplicate_frames(self, frame_paths: List[Path]) -> Dict[str, Any]:
        """
        Remove duplicate frames and return metadata.
        
        Args:
            frame_paths: List of paths to extracted frames
        
        Returns:
            Dictionary with unique_frames list and metadata
        """
        if not frame_paths:
            return {
                "unique_frames": [],
                "removed_duplicates": 0,
                "frame_metadata": []
            }
        
        logger.info(f"Deduplicating {len(frame_paths)} frames...")
        
        frame_metadata = []
        unique_frames = []
        prev_hash = None
        prev_path = None
        duplicates_removed = 0
        
        for idx, frame_path in enumerate(sorted(frame_paths)):
            try:
                current_hash = self.compute_frame_hash(frame_path)
                
                # Extract frame index from filename (frame_XXXXXX.jpg)
                frame_idx = int(frame_path.stem.split('_')[-1])
                
                # Calculate timestamp from frame index if possible
                # (would need video FPS info, storing as placeholder)
                
                is_duplicate = False
                if prev_hash and current_hash:
                    similarity = self.compute_similarity(prev_hash, current_hash)
                    if similarity >= self.config.frame_similarity_threshold:
                        is_duplicate = True
                        duplicates_removed += 1
                        logger.debug(f"Removed duplicate: {frame_path.name} (similarity: {similarity:.3f})")
                
                if not is_duplicate:
                    unique_frames.append(frame_path)
                    frame_metadata.append({
                        "frame_path": str(frame_path),
                        "frame_index": frame_idx,
                        "hash": current_hash,
                        "is_duplicate": False,
                        "similarity_to_previous": None
                    })
                    prev_hash = current_hash
                    prev_path = frame_path
                else:
                    frame_metadata.append({
                        "frame_path": str(frame_path),
                        "frame_index": frame_idx,
                        "hash": current_hash,
                        "is_duplicate": True,
                        "similarity_to_previous": similarity
                    })
            
            except Exception as e:
                logger.error(f"Error processing frame {frame_path}: {str(e)}")
        
        logger.info(f"Deduplication complete: {len(unique_frames)}/{len(frame_paths)} unique frames")
        
        return {
            "unique_frames": unique_frames,
            "removed_duplicates": duplicates_removed,
            "frame_metadata": frame_metadata
        }


# ======================== Transcript Chunking ========================

class TranscriptChunker:
    """Chunk transcript into segments based on token count."""
    
    def __init__(self, config: MediaProcessorConfig):
        """Initialize chunker."""
        self.config = config
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).
        Whisper uses BPE tokens, but we approximate: ~1 token per 4 characters.
        
        Args:
            text: Text to count tokens for
        
        Returns:
            Estimated token count
        """
        # Rough approximation: split by whitespace and punctuation
        words = text.split()
        # Each word ~1.3 tokens on average
        return int(len(words) * 1.3)
    
    def chunk_transcript(self, transcript: Dict) -> Dict[str, Any]:
        """
        Chunk transcript based on token count using JSON segment data.
        
        Args:
            transcript: Whisper output dictionary with segments
        
        Returns:
            Dictionary with chunks and metadata
        """
        if 'segments' not in transcript or not transcript['segments']:
            return {
                "chunks": [],
                "chunk_metadata": [],
                "total_chunks": 0
            }
        
        logger.info(f"Chunking transcript with max {self.config.max_chunk_tokens} tokens per chunk...")
        
        segments = transcript['segments']
        chunks = []
        chunk_metadata = []
        
        current_chunk_text = []
        current_chunk_tokens = 0
        current_chunk_segment_indices = []
        chunk_start_time = None
        chunk_end_time = None
        
        for seg_idx, segment in enumerate(segments):
            seg_text = segment.get('text', '').strip()
            seg_tokens_raw = segment.get('tokens', [])
            
            # Handle both list of token IDs and token count
            if isinstance(seg_tokens_raw, list):
                seg_tokens = len(seg_tokens_raw)  # Count the token IDs
            else:
                seg_tokens = seg_tokens_raw if isinstance(seg_tokens_raw, int) else 0
            
            # If segment has no token info, estimate
            if seg_tokens == 0:
                seg_tokens = self.estimate_tokens(seg_text)
            
            # Check if adding this segment would exceed token limit
            if (current_chunk_tokens + seg_tokens > self.config.max_chunk_tokens and 
                current_chunk_text):
                # Save current chunk and start new one
                chunk_text = ' '.join(current_chunk_text)
                chunks.append(chunk_text)
                
                chunk_metadata.append({
                    "chunk_index": len(chunks) - 1,
                    "text": chunk_text,
                    "token_count": current_chunk_tokens,
                    "segment_indices": current_chunk_segment_indices,
                    "start_time": chunk_start_time,
                    "end_time": chunk_end_time
                })
                
                logger.debug(f"Chunk {len(chunks)-1}: {current_chunk_tokens} tokens, "
                           f"{len(current_chunk_segment_indices)} segments")
                
                # Reset for next chunk
                current_chunk_text = []
                current_chunk_tokens = 0
                current_chunk_segment_indices = []
                chunk_start_time = None
                chunk_end_time = None
            
            # Add segment to current chunk
            current_chunk_text.append(seg_text)
            current_chunk_tokens += seg_tokens
            current_chunk_segment_indices.append(seg_idx)
            
            if chunk_start_time is None:
                chunk_start_time = segment.get('start', 0)
            chunk_end_time = segment.get('end', 0)
        
        # Save final chunk
        if current_chunk_text:
            chunk_text = ' '.join(current_chunk_text)
            chunks.append(chunk_text)
            
            chunk_metadata.append({
                "chunk_index": len(chunks),
                "text": chunk_text,
                "token_count": current_chunk_tokens,
                "segment_indices": current_chunk_segment_indices,
                "start_time": chunk_start_time,
                "end_time": chunk_end_time
            })
            
            logger.debug(f"Chunk {len(chunks)-1}: {current_chunk_tokens} tokens, "
                       f"{len(current_chunk_segment_indices)} segments")
        
        logger.info(f"Created {len(chunks)} chunks from {len(segments)} segments")
        
        return {
            "chunks": chunks,
            "chunk_metadata": chunk_metadata,
            "total_chunks": len(chunks)
        }
    
    def chunk_transcript_with_uniform_metadata(
        self, transcript: Dict, original_file: str, original_file_format: str
    ) -> Dict[str, Any]:
        """
        Chunk transcript and add uniform metadata to each chunk.
        
        Args:
            transcript: Whisper output dictionary with segments
            original_file: Path to the original media file
            original_file_format: Format of the original file (e.g., 'mp4')
        
        Returns:
            Dictionary with uniformly-metadata'd chunks
        """
        base_result = self.chunk_transcript(transcript)
        
        if not base_result.get('chunk_metadata'):
            return base_result
        
        now_iso = datetime.now().isoformat()
        stem = Path(original_file).stem
        
        for chunk in base_result['chunk_metadata']:
            idx = chunk.get('chunk_index', 0)
            chunk.update({
                'chunk_name': f"{stem}_transcript_chunk_{idx}",
                'original_file': original_file,
                'original_file_format': original_file_format,
                'current_format': 'json',
                'uploaded_timestamp': now_iso,
                'content_type': 'transcript_text',
                'duration': chunk.get('end_time', 0) - chunk.get('start_time', 0),
                'associated_frames': [],  # Populated later by frame-chunk association
            })
        
        return base_result


# ======================== Audio Extraction ========================

class AudioExtractor:
    """Extract audio from video files."""
    
    def __init__(self, output_dir: Union[str, Path], config: MediaProcessorConfig):
        """
        Initialize audio extractor.
        
        Args:
            output_dir: Directory to save extracted audio
            config: Processing configuration
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.noise_reducer = AudioNoiseReducer(config)
    
    def extract_audio(self, video_path: Union[str, Path]) -> Optional[Path]:
        """
        Extract audio from video and optionally reduce noise.
        
        Args:
            video_path: Path to video file
        
        Returns:
            Path to extracted audio file or None if error
        """
        if not MOVIEPY_AVAILABLE or not LIBROSA_AVAILABLE:
            logger.error("MoviePy or librosa required for audio extraction")
            return None
        
        video_path = Path(video_path)
        logger.info(f"Extracting audio from: {video_path}")
        
        try:
            if not video_path.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Load video
            logger.info("Loading video with MoviePy...")
            start_time = time.time()
            video = VideoFileClip(str(video_path))
            load_time = time.time() - start_time
            logger.info(f"✓ Video loaded in {load_time:.2f}s")
            logger.info(f"  - Duration: {video.duration:.2f}s")
            logger.info(f"  - FPS: {video.fps}")
            
            # Extract audio stream
            if video.audio is None:
                raise ValueError("Video has no audio stream")
            
            logger.info(f"Audio stream info:")
            logger.info(f"  - Duration: {video.audio.duration:.2f}s")
            logger.info(f"  - Sample rate: {video.audio.fps} Hz")
            logger.info(f"  - Channels: {video.audio.nchannels}")
            
            # Save audio file directly using MoviePy (preserves quality)
            audio_path = self.output_dir / f"{video_path.stem}.{self.config.audio_format}"
            logger.info(f"Saving audio to: {audio_path}")
            
            # Use MoviePy's write_audiofile for best quality
            video.audio.write_audiofile(
                str(audio_path),
                fps=self.config.audio_sample_rate,
                nbytes=2,
                codec='pcm_s16le',
                logger=None
            )
            
            file_size = audio_path.stat().st_size
            logger.info(f"✓ Audio extracted and saved")
            logger.info(f"  - File size: {file_size / (1024*1024):.2f} MB")
            
            # Clean up
            video.close()
            
            return audio_path
        
        except Exception as e:
            logger.error(f"Error extracting audio: {str(e)}")
            if 'video' in locals():
                video.close()
            return None


# ======================== Audio Transcription ========================

class AudioTranscriber:
    """Transcribe audio using Whisper with full parameters."""
    
    def __init__(self, config: MediaProcessorConfig):
        """
        Initialize transcriber.
        
        Args:
            config: Processing configuration
        """
        self.config = config
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load Whisper model with appropriate device."""
        if should_use_sagemaker_whisper(media_config=self.config):
            logger.info(
                "Whisper ASR configured for SageMaker endpoint mode (region=%s, endpoint=%s)",
                self.config.aws_region,
                self.config.sagemaker_whisper_endpoint_name or os.getenv("SAGEMAKER_ENDPOINT_NAME", ""),
            )
            self.model = "sagemaker-runtime"
            return

        if not WHISPER_AVAILABLE:
            logger.error("Whisper required for transcription")
            return
        
        try:
            logger.info(f"Loading Whisper {self.config.asr_model} model on {self.config.device}...")
            start_time = time.time()
            
            self.model = whisper.load_model(
                self.config.asr_model,
                device=self.config.device
            )
            
            load_time = time.time() - start_time
            logger.info(f"✓ Model loaded in {load_time:.2f}s")
        
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            self.model = None

    def _prepare_audio_for_whisper(self, audio_path: Path) -> Tuple[Path, bool]:
        """
        Normalize media inputs to mono 16k WAV via ffmpeg before librosa load.

        Returns:
            (prepared_audio_path, should_cleanup)
        """
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin is None:
            return audio_path, False

        # Keep native WAV inputs on the fast path.
        if audio_path.suffix.lower() == ".wav":
            return audio_path, False

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            prepared_audio = Path(tmp.name)

        cmd = [
            ffmpeg_bin,
            "-nostdin",
            "-y",
            "-i",
            str(audio_path),
            "-ac",
            str(self.config.audio_channels),
            "-ar",
            str(self.config.audio_sample_rate),
            "-vn",
            str(prepared_audio),
        ]

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            logger.info(
                "Prepared audio with ffmpeg: %s -> %s (%s Hz, %s channel)",
                audio_path.name,
                prepared_audio.name,
                self.config.audio_sample_rate,
                self.config.audio_channels,
            )
            return prepared_audio, True
        except subprocess.CalledProcessError as exc:
            prepared_audio.unlink(missing_ok=True)
            err_preview = (exc.stderr or "").strip().splitlines()
            logger.warning(
                "ffmpeg pre-conversion failed, falling back to direct librosa load: %s",
                err_preview[-1] if err_preview else str(exc),
            )
            return audio_path, False
    
    def transcribe(self, audio_path: Union[str, Path]) -> Optional[Dict]:
        """
        Transcribe audio with full Whisper parameters and word-level timestamps.
        
        Args:
            audio_path: Path to audio file
        
        Returns:
            Dictionary with transcription results or None if error
        """
        if should_use_sagemaker_whisper(media_config=self.config):
            try:
                data = invoke_sagemaker_whisper(
                    Path(audio_path),
                    language=self.config.asr_language,
                    word_timestamps=self.config.use_word_timestamps,
                    media_config=self.config,
                )
                if not isinstance(data, dict):
                    logger.error("Invalid SageMaker Whisper response type: %s", type(data))
                    return None
                return data
            except Exception as e:
                logger.error(f"SageMaker Whisper invocation failed: {str(e)}")
                return None

        if self.model is None:
            logger.error("Model not loaded")
            return None
        
        if not LIBROSA_AVAILABLE:
            logger.error("Librosa required for audio processing")
            return None
        
        audio_path = Path(audio_path)
        logger.info(f"Transcribing audio: {audio_path}")
        logger.info(f"File size: {audio_path.stat().st_size / (1024*1024):.2f} MB")

        prepared_audio_path = audio_path
        cleanup_prepared = False
        
        try:
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            prepared_audio_path, cleanup_prepared = self._prepare_audio_for_whisper(audio_path)
            
            # Load audio with librosa
            logger.info("Loading audio with librosa from: %s", prepared_audio_path)
            start_time = time.time()
            audio, sr = librosa.load(
                str(prepared_audio_path),
                sr=self.config.audio_sample_rate,
                mono=True
            )
            load_time = time.time() - start_time
            logger.info(f"✓ Audio loaded in {load_time:.2f}s")
            logger.info(f"  - Duration: {len(audio) / sr:.2f}s")
            logger.info(f"  - Sample rate: {sr} Hz")
            
            # Transcribe with full Whisper parameters
            logger.info("Starting Whisper transcription with full parameters...")
            logger.info("Whisper parameters:")
            logger.info(f"  - language: {self.config.asr_language}")
            logger.info(f"  - temperature: {self.config.temperature_schedule}")
            logger.info(f"  - compression_ratio_threshold: {self.config.compression_ratio_threshold}")
            logger.info(f"  - logprob_threshold: {self.config.logprob_threshold}")
            logger.info(f"  - no_speech_threshold: {self.config.no_speech_threshold}")
            logger.info(f"  - condition_on_previous_text: {self.config.condition_on_previous_text}")
            logger.info(f"  - word_timestamps: {self.config.use_word_timestamps}")
            
            start_time = time.time()
            result = self.model.transcribe(
                audio,
                language=self.config.asr_language,
                task="transcribe",
                # Temperature sampling
                temperature=self.config.temperature_schedule,
                # Quality thresholds for hallucination detection
                compression_ratio_threshold=self.config.compression_ratio_threshold,
                logprob_threshold=self.config.logprob_threshold,
                no_speech_threshold=self.config.no_speech_threshold,
                # Context handling
                condition_on_previous_text=self.config.condition_on_previous_text,
                # Word-level timestamps
                word_timestamps=self.config.use_word_timestamps,
                # Verbose off for performance
                verbose=False
            )
            transcribe_time = time.time() - start_time
            logger.info(f"✓ Transcription completed in {transcribe_time:.2f}s")

            if not isinstance(result, dict):
                logger.error("Unexpected Whisper result type: %s", type(result))
                return None

            if result.get("text") is None:
                result["text"] = ""
            segments = result.get("segments")
            if not isinstance(segments, list):
                segments = []
                result["segments"] = segments
            
            language = result.get('language', 'unknown')
            text_length = len(result.get('text', ''))
            segment_count = len(segments)
            logger.info(f"  - Detected language: {language}")
            logger.info(f"  - Text length: {text_length} characters")
            logger.info(f"  - Segments: {segment_count}")
            
            # Check for word timestamps
            first_segment = segments[0] if segments else {}
            has_word_timestamps = isinstance(first_segment, dict) and ('words' in first_segment)
            logger.info(f"  - Word-level timestamps: {'✓ Yes' if has_word_timestamps else '✗ No'}")
            
            # Log sample segments
            logger.info("Sample segments (first 3):")
            for idx, seg in enumerate(segments[:3]):
                start_sec = float(seg.get('start', 0.0)) if isinstance(seg, dict) else 0.0
                end_sec = float(seg.get('end', 0.0)) if isinstance(seg, dict) else 0.0
                seg_text = str(seg.get('text', '')) if isinstance(seg, dict) else ""
                token_val = seg.get('tokens', 0) if isinstance(seg, dict) else 0
                token_count = len(token_val) if isinstance(token_val, list) else token_val
                logger.info(
                    f"  [{idx}] {start_sec:.2f}s - {end_sec:.2f}s | "
                    f"Tokens: {token_count} | Text: {seg_text[:50]}..."
                )
            
            return result
        
        except Exception as e:
            logger.error(f"Error transcribing: {str(e)}")
            return None
        finally:
            if cleanup_prepared:
                prepared_audio_path.unlink(missing_ok=True)


# ======================== Frame Extraction ========================

class FrameExtractor:
    """Extract frames from video with deduplication."""
    
    def __init__(self, output_dir: Union[str, Path], config: MediaProcessorConfig):
        """
        Initialize frame extractor.
        
        Args:
            output_dir: Directory to save extracted frames
            config: Processing configuration
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.deduplicator = FrameDeduplicator(config)
    
    def extract_frames(self, video_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Extract frames from video with optional deduplication.
        
        Args:
            video_path: Path to video file
        
        Returns:
            Dictionary with extracted_frames list and metadata
        """
        if not CV2_AVAILABLE:
            logger.error("OpenCV (cv2) required for frame extraction")
            return {"extracted_frames": [], "frame_metadata": [], "total_frames": 0}
        
        video_path = Path(video_path)
        video_name = video_path.stem
        frame_dir = self.output_dir / video_name
        frame_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Extracting frames from: {video_path}")
        
        extracted_frames = []
        
        try:
            # Open video
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                raise Exception(f"Cannot open video: {video_path}")
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"Video properties:")
            logger.info(f"  - Total frames: {total_frames}")
            logger.info(f"  - FPS: {fps:.2f}")
            logger.info(f"  - Duration: {total_frames/fps:.2f}s")
            logger.info(f"  - Frame interval: {self.config.frame_interval}")
            
            frame_idx = 0
            saved_count = 0
            
            pbar_total = total_frames // self.config.frame_interval
            with tqdm(total=pbar_total, desc="Extracting frames") as pbar:
                while True:
                    ret, frame = cap.read()
                    
                    if not ret:
                        break
                    
                    # Extract every Nth frame
                    if frame_idx % self.config.frame_interval == 0:
                        # Check frame quality
                        if self._is_quality_frame(frame):
                            frame_path = frame_dir / f"frame_{frame_idx:06d}.{self.config.frame_format}"
                            
                            # Save frame
                            cv2.imwrite(
                                str(frame_path),
                                frame,
                                [cv2.IMWRITE_JPEG_QUALITY, self.config.frame_quality]
                            )
                            
                            extracted_frames.append(frame_path)
                            saved_count += 1
                            pbar.update(1)
                    
                    frame_idx += 1
            
            cap.release()
            logger.info(f"✓ Extracted {saved_count}/{pbar_total} quality frames")
            
            # Apply deduplication if enabled
            if self.config.remove_duplicate_frames:
                logger.info("Applying frame deduplication...")
                dedup_result = self.deduplicator.deduplicate_frames(extracted_frames)
                extracted_frames = dedup_result["unique_frames"]
                frame_metadata = dedup_result["frame_metadata"]
                logger.info(f"  - Removed {dedup_result['removed_duplicates']} duplicates")
            else:
                # Create basic frame metadata
                frame_metadata = [
                    {
                        "frame_path": str(fp),
                        "frame_index": int(fp.stem.split('_')[-1]),
                        "is_duplicate": False
                    }
                    for fp in extracted_frames
                ]
            
            # Enrich frame metadata with uniform fields
            now_iso = datetime.now().isoformat()
            for fm in frame_metadata:
                frame_idx = fm.get("frame_index", 0)
                video_ts = (frame_idx / fps) if fps > 0 else 0.0
                fm.update({
                    "frame_name": f"{video_name}_frame_{frame_idx:06d}",
                    "original_file": str(video_path),
                    "original_file_format": video_path.suffix.lstrip('.').lower(),
                    "current_format": self.config.frame_format,
                    "uploaded_timestamp": now_iso,
                    "video_timestamp": video_ts,
                    "content_type": "extracted_frame",
                    "associated_chunk_index": None,  # Populated later
                })
            
            return {
                "extracted_frames": extracted_frames,
                "frame_metadata": frame_metadata,
                "total_frames": len(extracted_frames),
                "fps": float(fps),
                "duration": float(total_frames / fps) if fps > 0 else 0.0
            }
        
        except Exception as e:
            logger.error(f"Error extracting frames: {str(e)}")
            if 'cap' in locals():
                cap.release()
            return {"extracted_frames": [], "frame_metadata": [], "total_frames": 0}
    
    def _is_quality_frame(self, frame) -> bool:
        """
        Check if frame meets quality threshold (not blurry).
        
        Args:
            frame: OpenCV frame
        
        Returns:
            True if frame quality is acceptable
        """
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            return True
        
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            quality_score = min(laplacian_var / 1000.0, 1.0)
            return quality_score >= self.config.min_frame_quality
        except:
            return True


# ======================== Main Media Processor ========================

class MediaProcessor:
    """Main orchestrator for media processing pipeline."""
    
    def __init__(
        self,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path],
        config: Optional[MediaProcessorConfig] = None
    ):
        """
        Initialize media processor.
        
        Args:
            input_dir: Directory containing video/audio files
            output_dir: Directory for processed outputs
            config: Processing configuration
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.config = config or MediaProcessorConfig()
        
        # Create output directories
        self.audio_dir = self.output_dir / "extracted_audio"
        self.transcript_dir = self.output_dir / "transcripts"
        self.frames_dir = self.output_dir / "extracted_frames"
        self.metadata_dir = self.output_dir / "media_metadata"
        self.chunks_dir = self.output_dir / "transcript_chunks"
        
        for dir_path in [self.audio_dir, self.transcript_dir, self.frames_dir, 
                        self.metadata_dir, self.chunks_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.audio_extractor = AudioExtractor(self.audio_dir, self.config)
        self.transcriber = AudioTranscriber(self.config) if self.config.enable_transcription else None
        self.frame_extractor = FrameExtractor(self.frames_dir, self.config) if self.config.extract_frames else None
        self.transcript_chunker = TranscriptChunker(self.config) if self.config.enable_transcription else None
        
        # Statistics
        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "audio_extracted": 0,
            "transcribed": 0,
            "frames_extracted": 0,
            "chunks_created": 0,
            "errors": []
        }
    
    def process_batch(self) -> Dict:
        """
        Process all video/audio files in input directory.
        
        Returns:
            Dictionary with processing statistics
        """
        logger.info(f"Starting batch media processing from: {self.input_dir}")
        
        # Find media files
        media_files = self._find_media_files()
        self.stats["total_files"] = len(media_files)
        
        logger.info(f"Found {len(media_files)} media files to process")
        
        # Process each file
        for file_path in tqdm(media_files, desc="Processing media"):
            try:
                self.process_file(file_path)
                self.stats["processed_files"] += 1
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {str(e)}")
                self.stats["failed_files"] += 1
                self.stats["errors"].append({
                    "file": str(file_path),
                    "error": str(e)
                })
        
        # Save statistics
        self._save_statistics()
        
        logger.info(f"Processing complete. {self.stats['processed_files']}/{self.stats['total_files']} files processed")
        
        return self.stats
    
    def process_file(self, file_path: Union[str, Path]) -> Dict:
        """
        Process a single video or audio file with full pipeline.
        
        Args:
            file_path: Path to media file
        
        Returns:
            Dictionary with processing results
        """
        file_path = Path(file_path)
        logger.info(f"Processing: {file_path}")
        
        results = {
            "file": str(file_path),
            "original_type": None,
            "current_type": None,
            "audio_path": None,
            "transcript_path": None,
            "transcript_text": None,
            "chunks_path": None,
            "frame_paths": [],
            "metadata_path": None,
            "timestamps": {
                "start": datetime.now().isoformat(),
                "end": None
            }
        }
        
        # Determine file type
        is_video = file_path.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']
        is_audio = file_path.suffix.lower() in ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac']
        
        if is_video:
            results["original_type"] = "video"
        elif is_audio:
            results["original_type"] = "audio"
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
        
        audio_path = file_path
        
        # Step 1: Extract audio from video
        if is_video and self.config.extract_audio:
            audio_path = self.audio_extractor.extract_audio(file_path)
            if audio_path:
                results["audio_path"] = str(audio_path)
                results["current_type"] = "audio"
                self.stats["audio_extracted"] += 1
        else:
            results["current_type"] = "audio"
        
        # Step 2: Transcribe audio
        if audio_path and self.config.enable_transcription and self.transcriber:
            transcript = self.transcriber.transcribe(audio_path)
            
            if transcript:
                # Save full transcript (JSON, TXT, SRT, VTT, MD)
                transcript_paths = self._save_transcripts(file_path.stem, transcript)
                _tp = transcript_paths.get('md') or transcript_paths.get('json')
                results["transcript_path"] = str(_tp) if _tp else None
                results["transcript_text"] = transcript.get('text')
                self.stats["transcribed"] += 1
                
                # Step 3: Chunk transcript with uniform metadata
                if self.transcript_chunker:
                    chunked = self.transcript_chunker.chunk_transcript_with_uniform_metadata(
                        transcript,
                        original_file=str(file_path),
                        original_file_format=file_path.suffix.lstrip('.').lower()
                    )
                    chunks_path = self._save_chunks(file_path.stem, chunked, transcript)
                    results["chunks_path"] = str(chunks_path)
                    results["_chunk_metadata"] = chunked.get("chunk_metadata", [])
                    self.stats["chunks_created"] += len(chunked.get('chunks', []))
        
        # Step 4: Extract frames from video
        if is_video and self.config.extract_frames and self.frame_extractor:
            frame_result = self.frame_extractor.extract_frames(file_path)
            results["frame_paths"] = [str(p) for p in frame_result.get("extracted_frames", [])]
            self.stats["frames_extracted"] += frame_result.get("total_frames", 0)
            
            # Capture video properties for metadata
            results["fps"] = frame_result.get("fps", 29.97)
            results["duration"] = frame_result.get("duration", 0.0)
            
            # Associate frames with transcript chunks (bidirectional)
            frame_metadata_list = frame_result.get("frame_metadata", [])
            chunk_metadata_list = results.get("_chunk_metadata", [])
            
            if frame_metadata_list and chunk_metadata_list:
                frame_metadata_list, chunk_metadata_list = self._associate_frames_with_chunks(
                    frame_metadata_list, chunk_metadata_list
                )
                results["_chunk_metadata"] = chunk_metadata_list
                
                # Re-save chunks with updated associated_frames
                if results.get("chunks_path"):
                    self._resave_chunks_with_frames(
                        results["chunks_path"], chunk_metadata_list
                    )
            
            # Save frame metadata
            if frame_metadata_list:
                frame_metadata_path = self.metadata_dir / f"{file_path.stem}_frame_metadata.json"
                with open(frame_metadata_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        "metadata": {
                            "original_file": str(file_path),
                            "total_frames": len(frame_metadata_list),
                            "fps": results.get("fps", 29.97),
                            "duration": results.get("duration", 0.0),
                            "created_at": datetime.now().isoformat()
                        },
                        "frames": frame_metadata_list
                    }, f, indent=2)
                logger.info(f"Saved frame metadata to: {frame_metadata_path}")
        
        # Clean up internal metadata from results
        results.pop("_chunk_metadata", None)
        
        # Step 5: Save comprehensive metadata
        results["timestamps"]["end"] = datetime.now().isoformat()
        metadata_path = self._save_media_metadata(file_path, results)
        results["metadata_path"] = str(metadata_path)
        
        return results
    
    def _find_media_files(self) -> List[Path]:
        """Find all supported media files."""
        extensions = {
            '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm',  # Video
            '.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac'  # Audio
        }
        
        files = []
        for ext in extensions:
            files.extend(self.input_dir.rglob(f"*{ext}"))
        
        return sorted(files)
    
    def _save_transcripts(self, stem: str, transcript: Dict) -> Dict[str, Path]:
        """Save transcript in multiple formats."""
        paths = {}
        
        # JSON with full metadata
        if self.config.export_json:
            json_path = self.transcript_dir / f"{stem}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(transcript, f, indent=2, ensure_ascii=False)
            paths['json'] = json_path
            logger.info(f"Saved JSON transcript to: {json_path}")
        
        # Plain text
        if self.config.export_txt:
            txt_path = self.transcript_dir / f"{stem}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(transcript.get('text', ''))
            paths['txt'] = txt_path
            logger.info(f"Saved TXT transcript to: {txt_path}")
        
        # Markdown format for Stage 3 Docling processing
        if self.config.export_md:
            md_path = self.transcript_dir / f"{stem}.md"
            markdown_content = self._transcript_to_markdown(stem, transcript)
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            paths['md'] = md_path
            logger.info(f"Saved MD transcript to: {md_path}")
        
        # SRT subtitle
        if self.config.export_srt and 'segments' in transcript:
            srt_path = self.transcript_dir / f"{stem}.srt"
            with open(srt_path, 'w', encoding='utf-8') as f:
                for idx, segment in enumerate(transcript['segments'], 1):
                    f.write(f"{idx}\n")
                    f.write(f"{self._format_timestamp(segment['start'])} --> {self._format_timestamp(segment['end'])}\n")
                    f.write(f"{segment['text'].strip()}\n\n")
            paths['srt'] = srt_path
            logger.info(f"Saved SRT transcript to: {srt_path}")
        
        # WebVTT
        if self.config.export_vtt and 'segments' in transcript:
            vtt_path = self.transcript_dir / f"{stem}.vtt"
            with open(vtt_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                for segment in transcript['segments']:
                    f.write(f"{self._format_timestamp(segment['start'])} --> {self._format_timestamp(segment['end'])}\n")
                    f.write(f"{segment['text'].strip()}\n\n")
            paths['vtt'] = vtt_path
            logger.info(f"Saved VTT transcript to: {vtt_path}")
        
        return paths
    
    def _transcript_to_markdown(self, stem: str, transcript: Dict) -> str:
        """
        Convert transcript to structured markdown format for Stage 3 Docling processing.
        
        Format:
        # Transcript: {filename}
        
        **Duration**: {duration}
        **Language**: {language}
        
        ## Transcript Content
        
        **[HH:MM:SS]** Text segment ...
        """
        lines = []
        
        lines.append(f"# Transcript: {stem}\n")
        lines.append(f"**Duration**: {transcript.get('duration', 'N/A')}")
        lines.append(f"**Language**: {transcript.get('language', 'auto')}\n")
        lines.append("## Transcript Content\n")
        
        if 'segments' in transcript:
            for segment in transcript['segments']:
                timestamp = self._format_timestamp_readable(segment['start'])
                text = segment['text'].strip()
                lines.append(f"**[{timestamp}]** {text}\n")
        else:
            lines.append(transcript.get('text', ''))
        
        return '\n'.join(lines)
    
    def _format_timestamp_readable(self, seconds: float) -> str:
        """Format seconds as readable timestamp [HH:MM:SS]."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _associate_frames_with_chunks(
        self,
        frame_metadata: List[Dict],
        chunk_metadata: List[Dict]
    ) -> tuple:
        """
        Associate frames with transcript chunks bidirectionally by timestamp.
        
        Each frame gets associated_chunk_index; each chunk gets associated_frames list.
        
        Args:
            frame_metadata: List of frame metadata dicts with video_timestamp
            chunk_metadata: List of chunk metadata dicts with start_time/end_time
        
        Returns:
            Tuple of (updated_frame_metadata, updated_chunk_metadata)
        """
        logger.info("Associating frames with transcript chunks by timestamp...")
        
        # Initialize associated_frames for chunks that don't have it
        for chunk in chunk_metadata:
            if 'associated_frames' not in chunk:
                chunk['associated_frames'] = []
        
        for frame in frame_metadata:
            frame_ts = frame.get("video_timestamp", 0)
            frame["associated_chunk_index"] = None
            
            for chunk in chunk_metadata:
                start = chunk.get("start_time", 0)
                end = chunk.get("end_time", 0)
                
                if start <= frame_ts <= end:
                    frame["associated_chunk_index"] = chunk.get("chunk_index")
                    chunk["associated_frames"].append({
                        "frame_path": frame.get("frame_path"),
                        "frame_index": frame.get("frame_index"),
                        "frame_name": frame.get("frame_name"),
                        "video_timestamp": frame_ts
                    })
                    break
        
        frames_with_chunks = sum(1 for f in frame_metadata if f.get("associated_chunk_index") is not None)
        chunks_with_frames = sum(1 for c in chunk_metadata if len(c.get("associated_frames", [])) > 0)
        logger.info(f"Frame-chunk association: {frames_with_chunks}/{len(frame_metadata)} frames mapped, "
                     f"{chunks_with_frames}/{len(chunk_metadata)} chunks have frames")
        
        return frame_metadata, chunk_metadata
    
    def _resave_chunks_with_frames(self, chunks_path: str, chunk_metadata: List[Dict]):
        """Re-save chunk JSON with updated associated_frames after frame association."""
        try:
            chunks_file = Path(chunks_path)
            if chunks_file.exists():
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data["chunks"] = chunk_metadata
                with open(chunks_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info(f"Re-saved chunks with frame associations: {chunks_path}")
        except Exception as e:
            logger.error(f"Error re-saving chunks: {str(e)}")
    
    def _save_chunks(self, stem: str, chunked: Dict, original_transcript: Dict) -> Path:
        """
        Save transcript chunks with uniform metadata.
        
        Args:
            stem: Base filename
            chunked: Dictionary with chunks and metadata
            original_transcript: Original Whisper transcript for context
        
        Returns:
            Path to saved chunks file
        """
        chunks_path = self.chunks_dir / f"{stem}_chunks.json"
        
        chunks_output = {
            "metadata": {
                "stem": stem,
                "total_chunks": chunked.get("total_chunks", 0),
                "max_chunk_tokens": self.config.max_chunk_tokens,
                "original_segments": len(original_transcript.get('segments', [])),
                "language": original_transcript.get('language', 'unknown'),
                "created_at": datetime.now().isoformat(),
                "chunk_type": "transcript",
                "uniform_metadata_version": "1.0"
            },
            "chunks": chunked.get("chunk_metadata", [])
        }
        
        with open(chunks_path, 'w', encoding='utf-8') as f:
            json.dump(chunks_output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved chunked transcript to: {chunks_path}")
        return chunks_path
    
    def _save_media_metadata(self, file_path: Path, results: Dict) -> Path:
        """
        Save comprehensive media metadata with provenance.
        
        Args:
            file_path: Original media file path
            results: Processing results dictionary
        
        Returns:
            Path to saved metadata file
        """
        metadata = {
            "provenance": {
                "original_filename": file_path.name,
                "original_type": results.get("original_type"),
                "current_type": results.get("current_type"),
                "original_path": str(file_path.absolute()),
                "file_size_bytes": file_path.stat().st_size,
                "created_at": datetime.fromtimestamp(file_path.stat().st_ctime).isoformat()
            },
            "processing": {
                "processed_at": datetime.now().isoformat(),
                "start_time": results["timestamps"]["start"],
                "end_time": results["timestamps"]["end"],
                "config": {
                    "whisper_model": self.config.asr_model,
                    "language": self.config.asr_language,
                    "max_chunk_tokens": self.config.max_chunk_tokens,
                    "frame_interval": self.config.frame_interval,
                    "remove_duplicate_frames": self.config.remove_duplicate_frames,
                    "apply_noise_reduction": self.config.apply_noise_reduction
                }
            },
            "outputs": {
                "audio_path": results.get("audio_path"),
                "transcript_path": results.get("transcript_path"),
                "chunks_path": results.get("chunks_path"),
                "frame_count": len(results.get("frame_paths", [])),
                "frame_paths": results.get("frame_paths", [])
            },
            "video_properties": {
                "duration": results.get("duration", 0.0),
                "fps": results.get("fps", 29.97)
            }
        }
        
        metadata_path = self.metadata_dir / f"{file_path.stem}_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved metadata to: {metadata_path}")
        return metadata_path
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as SRT/VTT timestamp."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _save_statistics(self):
        """Save processing statistics."""
        stats_path = self.metadata_dir / "processing_statistics.json"
        stats_output = {
            **self.stats,
            "processed_at": datetime.now().isoformat(),
            "config": {
                "whisper_model": self.config.asr_model,
                "device": self.config.device,
                "frame_deduplication": self.config.remove_duplicate_frames,
                "noise_reduction": self.config.apply_noise_reduction
            }
        }
        
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats_output, f, indent=2)
        
        logger.info(f"Saved statistics to: {stats_path}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is not None:
            logger.error(f"Error during processing: {exc_val}")
        return False


# ======================== Utility Functions ========================

def process_media(
    input_dir: Union[str, Path],
    output_dir: Union[str, Path],
    config: Optional[MediaProcessorConfig] = None
) -> Dict:
    """
    Convenience function to process media files.
    
    Args:
        input_dir: Directory containing media files
        output_dir: Directory for outputs
        config: Optional configuration
    
    Returns:
        Dictionary with processing statistics
    """
    processor = MediaProcessor(input_dir, output_dir, config)
    return processor.process_batch()


if __name__ == "__main__":
    # Example usage
    config = MediaProcessorConfig(
        extract_audio=True,
        enable_transcription=True,
        asr_model="base",
        extract_frames=True,
        frame_interval=30,
        remove_duplicate_frames=True,
        apply_noise_reduction=True,
        max_chunk_tokens=100,
        export_json=True,
        export_txt=True,
        export_srt=True,
        export_vtt=True
    )
    
    stats = process_media(
        input_dir="input/videos",
        output_dir="output/media_processed",
        config=config
    )
    
    logger.info("\n" + "="*80)
    logger.info("MEDIA PROCESSING SUMMARY")
    logger.info("="*80)
    logger.info(f"Total files: {stats['total_files']}")
    logger.info(f"Processed: {stats['processed_files']}")
    logger.info(f"Failed: {stats['failed_files']}")
    logger.info(f"Audio extracted: {stats['audio_extracted']}")
    logger.info(f"Transcribed: {stats['transcribed']}")
    logger.info(f"Frames extracted: {stats['frames_extracted']}")
    logger.info(f"Chunks created: {stats['chunks_created']}")
    logger.info("="*80)
