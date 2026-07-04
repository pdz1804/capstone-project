# Stage 2: Media Processing - Detailed Documentation

## Table of Contents
1. [Overview](#overview)
2. [Module: media_processor.py](#module-media_processorpy)
3. [Processing Workflows](#processing-workflows)
4. [Function Reference](#function-reference)
5. [Whisper Models](#whisper-models)
6. [Examples](#examples)

---

## Overview

**Stage 2: Media Processing** extracts audio from videos, transcribes audio to text using Whisper ASR, and optionally extracts video frames for image-based retrieval.

### Purpose
- **Video → Audio**: Extract audio tracks from video files
- **Audio → Text**: Transcribe speech using OpenAI Whisper
- **Video → Frames**: Extract frames for image-based RAG (optional)
- **Generate Multiple Formats**: TXT, JSON, SRT, VTT for different use cases

### Supported Media Formats

| **Type** | **Extensions** | **Processing** |
|---------|---------------|---------------|
| **Video** | `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm` | Audio extraction → Transcription → Frame extraction |
| **Audio** | `.wav`, `.mp3`, `.m4a`, `.flac`, `.ogg` | Transcription |

---

## Module: media_processor.py

### Key Classes

#### 1. `MediaProcessorConfig`
Configuration dataclass for media processing behavior.

**Attributes**:
```python
@dataclass
class MediaProcessorConfig:
    # Audio extraction
    extract_audio: bool = True              # Extract audio from video
    audio_format: str = 'wav'               # Output format
    audio_sample_rate: int = 16000          # Whisper optimal rate
    audio_channels: int = 1                 # Mono (required by Whisper)
    
    # Transcription
    enable_transcription: bool = True       # Transcribe audio
    asr_model: str = "base"                 # tiny/base/small/medium/large/large-v3
    asr_language: str = None                # Auto-detect if None
    use_gpu: bool = True                    # GPU acceleration
    
    # Chunked processing
    chunk_duration: int = 30                # Seconds per chunk
    chunk_overlap: float = 1.0              # Overlap between chunks
    
    # Frame extraction
    extract_frames: bool = False            # Extract video frames
    frame_interval: int = 100               # Extract every N frames
    frame_format: str = 'jpg'               # Image format
    frame_quality: int = 85                 # JPEG quality
    
    # Output formats
    export_txt: bool = True                 # Plain text transcript
    export_json: bool = True                # JSON with timestamps
    export_srt: bool = True                 # SRT subtitles
    export_vtt: bool = True                 # WebVTT subtitles
    
    # Frame filtering
    min_frame_quality: float = 0.5          # Skip blurry frames (0-1)
```

#### 2. `MediaProcessor`
Main orchestrator for media processing pipeline.

**Initialization**:
```python
def __init__(
    self,
    input_dir: Union[str, Path],           # Source media directory
    output_dir: Union[str, Path],          # Output directory
    config: Optional[MediaProcessorConfig] = None
):
```

**Key Attributes**:
- `self.audio_dir`: Extracted audio files
- `self.transcripts_dir`: Transcript files (TXT, JSON, SRT, VTT)
- `self.frames_dir`: Extracted video frames
- `self.metadata_dir`: Processing statistics

#### 3. `AudioExtractor`
Extract audio from video files using MoviePy.

**Key Methods**:
```python
def extract_audio(self, video_path: Path) -> Optional[Path]:
    """Extract audio from video and save as WAV."""
```

#### 4. `AudioTranscriber`
Transcribe audio using OpenAI Whisper.

**Key Methods**:
```python
def transcribe(self, audio_path: Path) -> Optional[Dict]:
    """Transcribe audio file using Whisper."""

def transcribe_chunked(self, audio_path: Path) -> Optional[Dict]:
    """Transcribe long audio in chunks (for >30 minute files)."""
```

#### 5. `FrameExtractor`
Extract frames from video files using OpenCV.

**Key Methods**:
```python
def extract_frames(self, video_path: Path) -> int:
    """Extract frames at specified interval."""

def _is_frame_quality_sufficient(self, frame) -> bool:
    """Check if frame is not too blurry (Laplacian variance)."""
```

---

## Processing Workflows

### Workflow 1: Video → Audio → Text

**Complete Pipeline**:
```
Video File (MP4)
  │
  ├→ Stage 1: Audio Extraction (MoviePy)
  │   ├→ Extract audio track
  │   ├→ Convert to WAV format
  │   ├→ Resample to 16kHz (Whisper optimal)
  │   └→ Convert to mono (required by Whisper)
  │
  ├→ Stage 2: Transcription (Whisper)
  │   ├→ Load Whisper model (tiny/base/small/medium/large)
  │   ├→ GPU acceleration (if available)
  │   ├→ Auto-detect language
  │   └→ Generate transcript with timestamps
  │
  ├→ Stage 3: Export Multiple Formats
  │   ├→ Plain text (.txt)
  │   ├→ JSON with timestamps (.json)
  │   ├→ SRT subtitles (.srt)
  │   └→ WebVTT subtitles (.vtt)
  │
  └→ Optional: Frame Extraction (OpenCV)
      ├→ Extract every N frames
      ├→ Filter blurry frames
      └→ Save as JPG images
```

**Example**:
```
Input:  lecture_video.mp4 (100MB, 10 minutes)
Output:
  - extracted_audio/lecture_video.wav (10MB)
  - transcripts/lecture_video.txt (5KB)
  - transcripts/lecture_video.json (15KB with timestamps)
  - transcripts/lecture_video.srt (10KB)
  - transcripts/lecture_video.vtt (10KB)
  - extracted_frames/lecture_video/ (optional, 100 frames)
```

### Workflow 2: Audio → Text

**Direct Audio Processing**:
```
Audio File (WAV/MP3)
  │
  ├→ Convert to WAV 16kHz Mono (if needed)
  │
  ├→ Transcribe with Whisper
  │   ├→ Load audio with librosa
  │   ├→ Process with Whisper model
  │   └→ Get transcript with timestamps
  │
  └→ Export Multiple Formats
      ├→ TXT (plain text)
      ├→ JSON (with timestamps)
      ├→ SRT (subtitles)
      └→ VTT (web subtitles)
```

### Workflow 3: Frame Extraction (Optional)

**Video → Image Frames**:
```
Video File
  │
  ├→ Open with OpenCV
  │
  ├→ Extract Every N Frames
  │   ├→ Frame 100: Check quality
  │   ├→ Frame 200: Check quality
  │   └→ Frame 300: Check quality
  │
  ├→ Quality Filtering
  │   ├→ Calculate Laplacian variance (sharpness)
  │   ├→ Keep if > min_frame_quality threshold
  │   └→ Skip blurry/duplicate frames
  │
  └→ Save as JPG Images
      └→ frame_0001.jpg, frame_0002.jpg, ...
```

**Why Extract Frames?**
- Enable image-based RAG on video content
- Find visual information (diagrams, code, presentations)
- Support multimodal retrieval (text + images)

---

## Function Reference

### Main Processing Functions

#### `MediaProcessor.process_batch() -> Dict`
Process all media files in input directory.

**Returns**:
```python
{
    "total_files": 10,
    "processed_files": 9,
    "failed_files": 1,
    "audio_extracted": 8,       # Number of audio files extracted
    "transcribed": 9,            # Number of transcriptions
    "frames_extracted": 5,       # Videos with frames extracted
    "errors": [...]
}
```

**Usage**:
```python
processor = MediaProcessor(
    input_dir="./input",
    output_dir="./output/stage2"
)
stats = processor.process_batch()
```

#### `MediaProcessor._process_video(video_path: Path)`
Process a single video file (audio + transcription + frames).

**Steps**:
1. Extract audio with `AudioExtractor`
2. Transcribe audio with `AudioTranscriber`
3. Export transcripts (TXT, JSON, SRT, VTT)
4. Optionally extract frames with `FrameExtractor`

#### `MediaProcessor._process_audio(audio_path: Path)`
Process a single audio file (transcription only).

**Steps**:
1. Transcribe with `AudioTranscriber`
2. Export transcripts (TXT, JSON, SRT, VTT)

### Audio Extraction Functions

#### `AudioExtractor.extract_audio(video_path) -> Optional[Path]`
Extract audio from video using MoviePy.

**Parameters**:
- `video_path`: Path to video file

**Returns**:
- Path to extracted WAV file, or `None` if failed

**Technical Details**:
- Uses MoviePy's `VideoFileClip` and `audio.write_audiofile()`
- Output format: WAV, 16kHz, mono, 16-bit PCM
- Skips if audio already extracted

**Error Handling**:
- Returns `None` if video has no audio stream
- Returns `None` if extraction fails
- Logs detailed error messages

**Example**:
```python
extractor = AudioExtractor(
    output_dir="./audio",
    config=MediaProcessorConfig()
)
audio_path = extractor.extract_audio("lecture.mp4")
# Returns: Path("./audio/lecture.wav")
```

### Transcription Functions

#### `AudioTranscriber.transcribe(audio_path) -> Optional[Dict]`
Transcribe audio using Whisper (for files < 30 minutes).

**Parameters**:
- `audio_path`: Path to audio file (WAV recommended)

**Returns**:
```python
{
    "text": "Full transcript text",
    "language": "en",
    "segments": [
        {
            "start": 0.0,
            "end": 5.2,
            "text": "Welcome to the lecture."
        },
        {
            "start": 5.2,
            "end": 10.5,
            "text": "Today we'll discuss AI."
        }
    ]
}
```

**Process**:
1. Load audio with `librosa` (resample to 16kHz, convert to mono)
2. Pass to Whisper model
3. Get transcript with word-level timestamps
4. Return structured result

**GPU Acceleration**:
- Automatically uses CUDA if available
- Falls back to CPU if GPU unavailable
- ~10x faster on GPU

**Example**:
```python
transcriber = AudioTranscriber(config=MediaProcessorConfig(asr_model="base"))
result = transcriber.transcribe("audio.wav")
print(result["text"])
print(f"Language: {result['language']}")
```

#### `AudioTranscriber.transcribe_chunked(audio_path) -> Optional[Dict]`
Transcribe long audio files in chunks (for files > 30 minutes).

**Why Chunked Processing?**
- Whisper has memory limits for very long audio
- Chunking prevents OOM errors
- Enables processing of hours-long lectures

**Parameters**:
- `audio_path`: Path to long audio file

**Process**:
1. Load full audio
2. Split into 30-second chunks with 1-second overlap
3. Transcribe each chunk independently
4. Adjust timestamps for each chunk
5. Combine all segments into final transcript

**Overlap Strategy**:
```
Chunk 1: [0s -------- 30s]
Chunk 2:           [29s -------- 59s]
Chunk 3:                      [58s -------- 88s]
         ↑ 1-second overlap prevents word cuts
```

**Returns**: Same format as `transcribe()` but combines all chunks.

**Example**:
```python
# For 2-hour lecture
result = transcriber.transcribe_chunked("long_lecture.wav")
# Returns combined transcript with adjusted timestamps
```

### Frame Extraction Functions

#### `FrameExtractor.extract_frames(video_path) -> int`
Extract frames from video at specified interval.

**Parameters**:
- `video_path`: Path to video file

**Returns**:
- Number of frames extracted

**Process**:
1. Open video with OpenCV
2. Iterate through frames at `frame_interval`
3. Check frame quality (skip blurry frames)
4. Save as JPG images

**Frame Quality Check**:
Uses Laplacian variance to detect blurry frames:
```python
def _is_frame_quality_sufficient(self, frame) -> bool:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance >= self.config.min_frame_quality * 100
```

**Example**:
```python
extractor = FrameExtractor(
    output_dir="./frames",
    config=MediaProcessorConfig(frame_interval=100)
)
num_frames = extractor.extract_frames("lecture.mp4")
print(f"Extracted {num_frames} frames")
```

### Export Functions

#### `_export_transcript_formats(result, stem, output_dir)`
Export transcript in multiple formats (TXT, JSON, SRT, VTT).

**TXT Format** (Plain text):
```
Welcome to the lecture. Today we'll discuss AI and machine learning concepts.
```

**JSON Format** (With timestamps):
```json
{
  "text": "Full transcript...",
  "language": "en",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Welcome to the lecture."
    }
  ]
}
```

**SRT Format** (Standard subtitles):
```
1
00:00:00,000 --> 00:00:05,200
Welcome to the lecture.

2
00:00:05,200 --> 00:00:10,500
Today we'll discuss AI.
```

**VTT Format** (Web subtitles):
```
WEBVTT

00:00:00.000 --> 00:00:05.200
Welcome to the lecture.

00:00:05.200 --> 00:00:10.500
Today we'll discuss AI.
```

---

## Whisper Models

### Available Models

| **Model** | **Parameters** | **Speed** | **Accuracy** | **VRAM** | **Use Case** |
|----------|---------------|----------|-------------|----------|-------------|
| **tiny** | 39M | Fastest | Lowest | 1GB | Quick tests, demos |
| **base** | 74M | Very Fast | Good | 1GB | **Recommended default** |
| **small** | 244M | Fast | Better | 2GB | Production, English |
| **medium** | 769M | Medium | High | 5GB | Multi-language |
| **large** | 1550M | Slow | Highest | 10GB | Best accuracy |
| **large-v3** | 1550M | Slow | Highest | 10GB | Latest version |

### Model Selection Guide

**Quick Processing** (Speed > Accuracy):
```python
config = MediaProcessorConfig(asr_model="tiny")
```

**Balanced** (Default):
```python
config = MediaProcessorConfig(asr_model="base")  # Recommended
```

**High Accuracy** (Accuracy > Speed):
```python
config = MediaProcessorConfig(asr_model="large-v3")
```

**Multi-Language**:
```python
config = MediaProcessorConfig(
    asr_model="medium",      # Better for non-English
    asr_language=None        # Auto-detect language
)
```

### Performance Comparison

**10-minute video transcription**:
- **tiny** (GPU): ~30 seconds
- **base** (GPU): ~60 seconds ⭐ Recommended
- **small** (GPU): ~120 seconds
- **medium** (GPU): ~300 seconds (5 minutes)
- **large** (GPU): ~600 seconds (10 minutes)

**Note**: CPU processing is ~10x slower than GPU.

---

## Configuration Options

### Production Configuration (Default)
```python
config = MediaProcessorConfig(
    extract_audio=True,
    enable_transcription=True,
    asr_model="base",               # Good balance
    asr_language=None,              # Auto-detect
    use_gpu=True,                   # Enable GPU
    extract_frames=False,           # Skip frames by default
    export_txt=True,
    export_json=True,
    export_srt=True,
    export_vtt=True
)
```

### Fast Configuration (Quick Testing)
```python
config = MediaProcessorConfig(
    asr_model="tiny",               # Fastest model
    extract_frames=False,           # Skip frames
    export_srt=False,               # Skip subtitles
    export_vtt=False
)
```

### High Accuracy Configuration
```python
config = MediaProcessorConfig(
    asr_model="large-v3",           # Best accuracy
    use_gpu=True,                   # Required for large model
    chunk_duration=30,              # Standard chunking
    extract_frames=True,            # Include frame extraction
    frame_interval=50               # More frames
)
```

### Frame Extraction Configuration
```python
config = MediaProcessorConfig(
    extract_frames=True,
    frame_interval=100,             # Every 100 frames (~4 sec at 25fps)
    frame_quality=90,               # High quality JPGs
    min_frame_quality=0.7           # Skip very blurry frames
)
```

---

## Examples

### Example 1: Basic Video Processing
```python
from media_processor import MediaProcessor, MediaProcessorConfig

# Initialize
processor = MediaProcessor(
    input_dir="./videos",
    output_dir="./output/stage2"
)

# Process all videos
stats = processor.process_batch()

print(f"Processed: {stats['processed_files']}")
print(f"Transcribed: {stats['transcribed']}")
```

### Example 2: Custom Whisper Model
```python
# Use large model for best accuracy
config = MediaProcessorConfig(
    asr_model="large-v3",
    use_gpu=True
)

processor = MediaProcessor(
    input_dir="./lectures",
    output_dir="./output",
    config=config
)

stats = processor.process_batch()
```

### Example 3: Extract Frames from Videos
```python
config = MediaProcessorConfig(
    extract_frames=True,            # Enable frame extraction
    frame_interval=100,             # Every 100 frames
    frame_quality=85,               # Good quality
    min_frame_quality=0.6           # Filter blurry frames
)

processor = MediaProcessor(
    input_dir="./videos",
    output_dir="./output",
    config=config
)

stats = processor.process_batch()
print(f"Frames extracted: {stats['frames_extracted']}")
```

### Example 4: Audio-Only Processing
```python
# Process audio files (no video)
processor = MediaProcessor(
    input_dir="./audio_files",     # Contains .wav, .mp3
    output_dir="./output"
)

stats = processor.process_batch()
# Automatically detects audio files and transcribes
```

### Example 5: Chunked Processing for Long Videos
```python
config = MediaProcessorConfig(
    asr_model="base",
    chunk_duration=30,              # 30-second chunks
    chunk_overlap=1.0               # 1-second overlap
)

processor = MediaProcessor(
    input_dir="./long_lectures",   # 2-hour videos
    output_dir="./output",
    config=config
)

stats = processor.process_batch()
# Automatically uses chunked processing for long audio
```

---

## Output Structure

### Directory Layout
```
output/stage2_media_processed/
├── extracted_audio/                  # WAV audio files
│   ├── lecture1.wav
│   └── lecture2.wav
├── transcripts/                      # Transcript files
│   ├── lecture1.txt                 # Plain text
│   ├── lecture1.json                # JSON with timestamps
│   ├── lecture1.srt                 # SRT subtitles
│   ├── lecture1.vtt                 # WebVTT subtitles
│   └── lecture2.*
├── extracted_frames/                 # Video frames (if enabled)
│   ├── lecture1/
│   │   ├── frame_0001.jpg
│   │   ├── frame_0002.jpg
│   │   └── ...
│   └── lecture2/
└── media_metadata/
    └── media_processing_stats.json  # Statistics
```

### Transcript JSON Format
```json
{
  "text": "Welcome to the lecture on artificial intelligence. Today we will discuss machine learning fundamentals...",
  "language": "en",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 5.2,
      "text": "Welcome to the lecture on artificial intelligence."
    },
    {
      "id": 1,
      "start": 5.2,
      "end": 10.8,
      "text": "Today we will discuss machine learning fundamentals."
    }
  ]
}
```

---

## Dependencies

### Required Libraries
```bash
# Core dependencies
pip install torch                   # PyTorch (CUDA support)
pip install openai-whisper          # Whisper ASR
pip install moviepy                 # Video processing
pip install librosa                 # Audio processing
pip install soundfile               # Audio I/O
pip install opencv-python           # Frame extraction
pip install numpy                   # Numerical operations
pip install Pillow                  # Image processing

# Utilities
pip install tqdm                    # Progress bars
```

### GPU Setup (Optional but Recommended)
```bash
# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify GPU
python -c "import torch; print(torch.cuda.is_available())"
# Should print: True
```

---

## Performance Tips

### 1. Use GPU for Transcription
GPU provides ~10x speedup over CPU for Whisper models.

### 2. Choose Appropriate Model
- **Quick tests**: Use `tiny` or `base`
- **Production**: Use `base` or `small`
- **Best quality**: Use `large-v3` (requires 10GB VRAM)

### 3. Skip Frame Extraction
Frame extraction is slow. Only enable if needed for image-based RAG.

### 4. Chunked Processing
For videos > 30 minutes, chunked processing prevents memory issues.

### 5. Batch Processing
Process multiple files in one run for better efficiency.

---

## Next Steps

- **Stage 3**: See [STAGE3_DOCUMENT.md](STAGE3_DOCUMENT.md) for Docling processing
- **API Reference**: See [API_REFERENCE.md](API_REFERENCE.md) for complete API
