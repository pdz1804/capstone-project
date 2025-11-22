"""
Media Processor Module

This module handles video and audio processing for the RAG pipeline.
- Extracts audio from video files
- Transcribes audio using Whisper/Gemini
- Optionally extracts frames for image-based retrieval

Based on Week0506_Mkhoi_OCR_ASR implementation with enhancements.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime
from tqdm import tqdm
import tempfile

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
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

try:
    # MoviePy 2.x uses direct import, not .editor submodule
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



@dataclass
class MediaProcessorConfig:
    """Configuration for media processing."""
    
    # Audio extraction
    extract_audio: bool = True
    audio_format: str = 'wav'
    audio_sample_rate: int = 16000
    audio_channels: int = 1  # Mono
    
    # Transcription
    enable_transcription: bool = True
    asr_model: str = "base"  # tiny, base, small, medium, large, large-v3
    asr_language: str = None  # Auto-detect if None
    use_gpu: bool = True
    
    # Chunked processing for long audio
    chunk_duration: int = 30  # seconds
    chunk_overlap: float = 1.0  # seconds
    
    # Frame extraction
    extract_frames: bool = False  # Optional: for image-based retrieval
    frame_interval: int = 100  # Extract every N frames
    frame_format: str = 'jpg'
    frame_quality: int = 85
    
    # Output formats
    export_txt: bool = True
    export_json: bool = True
    export_srt: bool = True  # Subtitle format
    export_vtt: bool = True  # WebVTT format
    
    # Frame processing
    min_frame_quality: float = 0.5  # Skip blurry frames (0-1)


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
    
    def extract_audio(self, video_path: Union[str, Path]) -> Optional[Path]:
        """
        Extract audio from video file.
        
        Args:
            video_path: Path to video file
        
        Returns:
            Path to extracted audio file, or None if failed
        """
        if not MOVIEPY_AVAILABLE:
            print("ERROR: moviepy not available. Install with: pip install moviepy")
            return None
        
        video_path = Path(video_path)
        output_path = self.output_dir / f"{video_path.stem}.{self.config.audio_format}"
        
        # Skip if already extracted
        if output_path.exists():
            print(f"Audio already extracted: {output_path}")
            return output_path
        
        try:
            print(f"Extracting audio from: {video_path}")
            
            # Load video
            video = VideoFileClip(str(video_path))
            
            # Extract audio
            audio = video.audio
            
            if audio is None:
                print(f"ERROR: No audio stream found in: {video_path}")
                video.close()
                return None
            
            # Write audio file
            audio.write_audiofile(
                str(output_path),
                fps=self.config.audio_sample_rate,
                nbytes=2,
                codec='pcm_s16le',
                logger=None
            )
            
            # Close resources
            video.close()
            
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise Exception("Failed to create audio file")
            
            print(f"Successfully extracted audio: {output_path}")
            return output_path
        
        except Exception as e:
            print(f"ERROR: Error extracting audio from {video_path}: {str(e)}")
            if 'video' in locals():
                video.close()
            return None


class AudioTranscriber:
    """Transcribe audio using Whisper ASR."""
    
    def __init__(self, config: MediaProcessorConfig):
        """
        Initialize audio transcriber.
        
        Args:
            config: Processing configuration
        """
        self.config = config
        self.device = None
        self.model = None
        
        if WHISPER_AVAILABLE and config.enable_transcription:
            self._load_model()
    
    def _load_model(self):
        """Load Whisper model."""
        if not TORCH_AVAILABLE or not WHISPER_AVAILABLE:
            print("ERROR: torch and whisper required for transcription")
            return
        
        self.device = "cuda" if self.config.use_gpu and torch.cuda.is_available() else "cpu"
        print(f"Loading Whisper model '{self.config.asr_model}' on {self.device}")
        
        try:
            self.model = whisper.load_model(self.config.asr_model, device=self.device)
            print(f"Model loaded successfully")
        except Exception as e:
            print(f"ERROR: Error loading Whisper model: {str(e)}")
            print(f"Available models: {whisper.available_models()}")
            raise
    
    def transcribe(self, audio_path: Union[str, Path]) -> Optional[Dict]:
        """
        Transcribe audio file.
        
        Args:
            audio_path: Path to audio file
        
        Returns:
            Dictionary with transcription results, or None if failed
        """
        if self.model is None:
            print("ERROR: Model not loaded")
            return None
        
        if not LIBROSA_AVAILABLE:
            print("ERROR: librosa required for audio processing")
            return None
        
        audio_path = Path(audio_path)
        print(f"Transcribing: {audio_path}")
        
        try:
            # Check file exists
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            # Load audio
            audio, sr = librosa.load(
                str(audio_path),
                sr=self.config.audio_sample_rate,
                mono=True
            )
            
            # Transcribe with Whisper
            result = self.model.transcribe(
                audio,
                language=self.config.asr_language,
                verbose=False
            )
            
            print(f"Transcription complete. Detected language: {result.get('language', 'unknown')}")
            
            return result
        
        except Exception as e:
            print(f"ERROR: Error transcribing {audio_path}: {str(e)}")
            return None
    
    def transcribe_chunked(self, audio_path: Union[str, Path]) -> Optional[Dict]:
        """
        Transcribe long audio file in chunks.
        
        Args:
            audio_path: Path to audio file
        
        Returns:
            Dictionary with combined transcription results
        """
        if not LIBROSA_AVAILABLE or not NUMPY_AVAILABLE:
            print("ERROR: librosa and numpy required for chunked processing")
            return None
        
        audio_path = Path(audio_path)
        print(f"Transcribing in chunks: {audio_path}")
        
        try:
            # Load full audio
            audio, sr = librosa.load(
                str(audio_path),
                sr=self.config.audio_sample_rate,
                mono=True
            )
            
            duration = len(audio) / sr
            chunk_samples = int(self.config.chunk_duration * sr)
            overlap_samples = int(self.config.chunk_overlap * sr)
            
            print(f"Audio duration: {duration:.1f}s, processing in {self.config.chunk_duration}s chunks")
            
            # Process chunks
            all_segments = []
            current_time = 0
            chunk_idx = 0
            
            while current_time < duration:
                start_sample = chunk_idx * (chunk_samples - overlap_samples)
                end_sample = start_sample + chunk_samples
                
                # Extract chunk
                chunk = audio[start_sample:end_sample]
                
                # Transcribe chunk
                result = self.model.transcribe(
                    chunk,
                    language=self.config.asr_language,
                    verbose=False
                )
                
                # Adjust timestamps
                for segment in result.get('segments', []):
                    segment['start'] += current_time
                    segment['end'] += current_time
                    all_segments.append(segment)
                
                current_time = end_sample / sr
                chunk_idx += 1
            
            # Combine results
            combined_text = " ".join([seg['text'].strip() for seg in all_segments])
            
            return {
                'text': combined_text,
                'segments': all_segments,
                'language': all_segments[0].get('language') if all_segments else 'unknown'
            }
        
        except Exception as e:
            print(f"ERROR: Error in chunked transcription: {str(e)}")
            return None


class FrameExtractor:
    """Extract frames from video for image-based retrieval."""
    
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
    
    def extract_frames(self, video_path: Union[str, Path]) -> List[Path]:
        """
        Extract frames from video at regular intervals.
        
        Args:
            video_path: Path to video file
        
        Returns:
            List of paths to extracted frame images
        """
        if not CV2_AVAILABLE:
            print("ERROR: opencv-python required for frame extraction")
            return []
        
        video_path = Path(video_path)
        video_name = video_path.stem
        frame_dir = self.output_dir / video_name
        frame_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Extracting frames from: {video_path}")
        
        extracted_frames = []
        
        try:
            # Open video
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                raise Exception(f"Cannot open video: {video_path}")
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            print(f"Video: {total_frames} frames, {fps:.2f} fps")
            
            frame_idx = 0
            saved_count = 0
            
            with tqdm(total=total_frames // self.config.frame_interval, desc="Extracting frames") as pbar:
                while True:
                    ret, frame = cap.read()
                    
                    if not ret:
                        break
                    
                    # Extract every Nth frame
                    if frame_idx % self.config.frame_interval == 0:
                        # Check frame quality (skip blurry frames)
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
            
            print(f"Extracted {saved_count} quality frames from {total_frames} total frames")
            return extracted_frames
        
        except Exception as e:
            print(f"ERROR: Error extracting frames: {str(e)}")
            if 'cap' in locals():
                cap.release()
            return []
    
    def _is_quality_frame(self, frame) -> bool:
        """
        Check if frame meets quality threshold (not blurry).
        
        Args:
            frame: OpenCV frame
        
        Returns:
            True if frame quality is acceptable
        """
        if not NUMPY_AVAILABLE:
            return True
        
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate Laplacian variance (measure of blur)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Normalize to 0-1 range (rough approximation)
            quality_score = min(laplacian_var / 1000.0, 1.0)
            
            return quality_score >= self.config.min_frame_quality
        except:
            return True


class MediaProcessor:
    """
    Main media processor coordinating audio extraction, transcription, and frame extraction.
    """
    
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
        
        for dir_path in [self.audio_dir, self.transcript_dir, self.frames_dir, self.metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.audio_extractor = AudioExtractor(self.audio_dir, self.config)
        self.transcriber = AudioTranscriber(self.config) if self.config.enable_transcription else None
        self.frame_extractor = FrameExtractor(self.frames_dir, self.config) if self.config.extract_frames else None
        
        # Setup logging
        self._setup_logging()
        
        # Statistics
        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "audio_extracted": 0,
            "transcribed": 0,
            "frames_extracted": 0,
            "errors": []
        }
    
    def _setup_logging(self):
        """Setup logging configuration."""
        log_file = self.output_dir / "media_processing.log"
        
    
    def process_batch(self) -> Dict:
        """
        Process all video/audio files in input directory.
        
        Returns:
            Dictionary with processing statistics
        """
        print(f"Starting batch media processing from: {self.input_dir}")
        
        # Find media files
        media_files = self._find_media_files()
        self.stats["total_files"] = len(media_files)
        
        print(f"Found {len(media_files)} media files to process")
        
        # Process each file
        for file_path in tqdm(media_files, desc="Processing media"):
            try:
                self.process_file(file_path)
                self.stats["processed_files"] += 1
            except Exception as e:
                print(f"ERROR: Failed to process {file_path}: {str(e)}")
                self.stats["failed_files"] += 1
                self.stats["errors"].append({
                    "file": str(file_path),
                    "error": str(e)
                })
        
        # Save statistics
        self._save_statistics()
        
        print(f"Processing complete. {self.stats['processed_files']}/{self.stats['total_files']} files processed")
        
        return self.stats
    
    def process_file(self, file_path: Union[str, Path]) -> Dict:
        """
        Process a single video or audio file.
        
        Args:
            file_path: Path to media file
        
        Returns:
            Dictionary with processing results
        """
        file_path = Path(file_path)
        print(f"Processing: {file_path}")
        
        results = {
            "file": str(file_path),
            "audio_path": None,
            "transcript_path": None,
            "frame_paths": [],
            "transcript_text": None
        }
        
        # Determine if video or audio
        is_video = file_path.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
        is_audio = file_path.suffix.lower() in ['.wav', '.mp3', '.m4a', '.flac', '.ogg']
        
        audio_path = file_path
        
        # Extract audio from video
        if is_video and self.config.extract_audio:
            audio_path = self.audio_extractor.extract_audio(file_path)
            if audio_path:
                results["audio_path"] = str(audio_path)
                self.stats["audio_extracted"] += 1
        
        # Transcribe audio
        if audio_path and self.config.enable_transcription and self.transcriber:
            transcript = self.transcriber.transcribe(audio_path)
            
            if transcript:
                # Save transcripts in various formats
                transcript_paths = self._save_transcripts(file_path.stem, transcript)
                results["transcript_path"] = transcript_paths.get('txt')
                results["transcript_text"] = transcript.get('text')
                self.stats["transcribed"] += 1
        
        # Extract frames from video
        if is_video and self.config.extract_frames and self.frame_extractor:
            frame_paths = self.frame_extractor.extract_frames(file_path)
            results["frame_paths"] = [str(p) for p in frame_paths]
            self.stats["frames_extracted"] += len(frame_paths)
        
        return results
    
    def _find_media_files(self) -> List[Path]:
        """Find all supported media files in input directory."""
        extensions = {
            # Video
            '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm',
            # Audio
            '.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac'
        }
        
        files = []
        for ext in extensions:
            files.extend(self.input_dir.rglob(f"*{ext}"))
        
        return sorted(files)
    
    def _save_transcripts(self, stem: str, transcript: Dict) -> Dict[str, Path]:
        """
        Save transcript in multiple formats.
        
        Args:
            stem: Base filename
            transcript: Transcript data from Whisper
        
        Returns:
            Dictionary mapping format to saved path
        """
        paths = {}
        
        # Plain text
        if self.config.export_txt:
            txt_path = self.transcript_dir / f"{stem}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(transcript.get('text', ''))
            paths['txt'] = txt_path
        
        # JSON with full metadata
        if self.config.export_json:
            json_path = self.transcript_dir / f"{stem}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(transcript, f, indent=2, ensure_ascii=False)
            paths['json'] = json_path
        
        # SRT subtitle format
        if self.config.export_srt and 'segments' in transcript:
            srt_path = self.transcript_dir / f"{stem}.srt"
            with open(srt_path, 'w', encoding='utf-8') as f:
                for idx, segment in enumerate(transcript['segments'], 1):
                    f.write(f"{idx}\n")
                    f.write(f"{self._format_timestamp(segment['start'])} --> {self._format_timestamp(segment['end'])}\n")
                    f.write(f"{segment['text'].strip()}\n\n")
            paths['srt'] = srt_path
        
        # WebVTT format
        if self.config.export_vtt and 'segments' in transcript:
            vtt_path = self.transcript_dir / f"{stem}.vtt"
            with open(vtt_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                for segment in transcript['segments']:
                    f.write(f"{self._format_timestamp(segment['start'])} --> {self._format_timestamp(segment['end'])}\n")
                    f.write(f"{segment['text'].strip()}\n\n")
            paths['vtt'] = vtt_path
        
        return paths
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as SRT/VTT timestamp."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _save_statistics(self):
        """Save processing statistics."""
        stats_path = self.metadata_dir / "media_processing_stats.json"
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)
        print(f"Saved statistics to: {stats_path}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is not None:
            print(f"ERROR: Error during processing: {exc_val}")
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
    with MediaProcessor(input_dir, output_dir, config) as processor:
        return processor.process_batch()


if __name__ == "__main__":
    # Example usage
    config = MediaProcessorConfig(
        extract_audio=True,
        enable_transcription=True,
        asr_model="base",
        extract_frames=True,
        frame_interval=100,
        export_txt=True,
        export_json=True,
        export_srt=True
    )
    
    stats = process_media(
        input_dir="input/videos",
        output_dir="output/media_processed",
        config=config
    )
    
    print(f"\nMedia Processing Summary:")
    print(f"Total files: {stats['total_files']}")
    print(f"Processed: {stats['processed_files']}")
    print(f"Audio extracted: {stats['audio_extracted']}")
    print(f"Transcribed: {stats['transcribed']}")
    print(f"Frames extracted: {stats['frames_extracted']}")
