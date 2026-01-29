
# Week0506_Mkhoi: Multimodal Lecture Processing Pipeline

A comprehensive system for processing educational video lectures using state-of-the-art ASR (Automatic Speech Recognition) and OCR (Optical Character Recognition) technologies. This project supports multiple AI models including OpenAI Whisper, Google Gemini, and DeepSeek for robust multimodal content extraction.

## 🎯 Project Overview

This pipeline processes lecture videos through two parallel streams:
1. **Audio Stream (ASR)**: Extracts and transcribes spoken content using advanced speech recognition models
2. **Visual Stream (OCR)**: Extracts text from presentation slides, PDFs, and visual materials

The system supports multiple AI backends and is optimized for Vietnamese and multilingual educational content.

---

## ✨ Key Features

### Audio Processing (ASR)
- **Multiple Model Support**:
  - OpenAI Whisper (tiny, base, small, medium, large, large-v3)
  - Google Gemini 2.0/2.5 Flash (via API)
  - DeepSeek (on/off variants)
- **Automatic Audio Extraction**: Converts video files to audio (WAV format at 16kHz)
- **Chunked Processing**: Handles long-form content with overlapping chunks
- **Multilingual Support**: Optimized for Vietnamese, English, Japanese, and more
- **GPU Acceleration**: CUDA support for faster inference

### Slide Processing (OCR)
- **Multi-format Support**: PDF, JPG, JPEG, PNG
- **Advanced Preprocessing**: Adaptive thresholding, OTSU binarization, noise reduction
- **Batch Processing**: Process entire directories of slides
- **Text Extraction**: Pytesseract-based OCR with language-specific optimization
- **PDF Handling**: Automatic PDF-to-image conversion with Poppler

### Output & Results
- **Structured Outputs**: TXT, JSON, CSV formats
- **Organized Results**: Separate directories for each processing method
- **Detailed Logging**: Comprehensive logs for debugging and monitoring
- **Benchmarking**: Model comparison files (`asr rank.md`, `ocr rank.md`, `model comparison.md`)

---

## 📁 Project Structure

```
Week0506_Mkhoi/
├── src/                          # Source code modules
│   ├── main.py                   # CLI entry point
│   ├── audio_processor.py        # Audio extraction and ASR processing
│   ├── slide_processor.py        # Slide OCR and preprocessing
│   ├── whisper.py                # OpenAI Whisper implementation
│   ├── gemini.py                 # Google Gemini API integration
│   ├── geminisd.py               # Gemini with special configurations
│   ├── deepseekon.py             # DeepSeek model (enabled)
│   ├── deepseekoff.py            # DeepSeek model (disabled/fallback)
│   └── transcribe.py             # Generic transcription utilities
│
├── data/                         # Input data directories
│   ├── audio/                    # Extracted audio files (.wav)
│   ├── videos/                   # Input lecture videos (.mp4, .avi, etc.)
│   └── slides/                   # Input slides (PDF, images)
│
├── results/                      # Default output directory
│   ├── asr/                      # ASR transcription results
│   └── ocr/                      # OCR extraction results
│
├── results_whisper/              # Whisper-specific outputs
├── results_gemini/               # Gemini-specific outputs
│
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── asr rank.md                   # ASR model performance comparison
├── ocr rank.md                   # OCR method evaluation
├── model comparison.md           # Comprehensive model benchmarks
└── .gitignore                    # Git ignore rules
```

---

## 🚀 Getting Started

### Prerequisites

- **Python**: 3.9+ (tested on 3.9, 3.10, 3.11)
- **System Dependencies**:
  - **Tesseract OCR**: Required for slide text extraction
  - **FFmpeg**: Required for video/audio processing
  - **Poppler**: Required for PDF conversion (optional, bundled in some setups)
- **API Keys** (optional):
  - `GEMINI_API_KEY`: For Google Gemini models
  - `DEEPSEEK_API_KEY`: For DeepSeek models (if using API version)

### Installation

#### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/capstone-project.git
cd Week0506_Mkhoi
```

#### 2. Create Virtual Environment (Recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/macOS)
source venv/bin/activate
```

#### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

**Key Dependencies**:
- `torch==2.1.0` / `torchaudio==2.1.0` - PyTorch for model inference
- `openai-whisper==20231117` - Whisper ASR
- `transformers==4.34.0` - Hugging Face models
- `moviepy==1.0.3` - Video/audio processing
- `pytesseract==0.3.10` - OCR engine
- `opencv-python==4.8.1.78` - Image preprocessing
- `pdf2image` - PDF conversion (install separately if needed)

#### 4. Install System Dependencies

**Windows**:
```powershell
# Download and install from official sources:
# 1. Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
# 2. FFmpeg: https://ffmpeg.org/download.html
# Add both to system PATH environment variable
```

**Linux (Ubuntu/Debian)**:
```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng ffmpeg poppler-utils
```

**macOS**:
```bash
brew install tesseract tesseract-lang ffmpeg poppler
```

#### 5. Configure API Keys (Optional)
Create a `.env` file in the project root:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

---

## 📖 Usage Guide

### Command Structure
```bash
python src/main.py <command> [options] <input_files>
```

Available commands:
- `asr`: Process videos with speech recognition
- `ocr`: Process slides/images with OCR
- `all`: Process both ASR and OCR

---

### 1. ASR (Speech Recognition)

#### Basic Usage
```bash
# Process single video
python src/main.py asr data/videos/lecture1.mp4

# Process multiple videos
python src/main.py asr data/videos/*.mp4
```

#### Advanced Options
```bash
python src/main.py asr \
  --output-dir results/asr_custom \
  data/videos/lecture1.mp4 \
  data/videos/lecture2.mp4
```

**Available Options**:
- `--output-dir DIR`: Custom output directory (default: `results/asr`)

**Audio Processing Details**:
- **Automatic Extraction**: Videos are converted to 16kHz WAV format
- **Storage**: Extracted audio saved to `data/audio/`
- **Chunking**: Long audio split into 30-second chunks with 1-second overlap
- **Model Selection**: Controlled in `audio_processor.py` (default: Whisper small)

#### Model Variants (in code)
Edit `src/audio_processor.py` to switch models:

**Whisper Models**:
```python
asr = PhoWhisperASR(model_name="small")  # Options: tiny, base, small, medium, large
```

**Gemini API** (`src/gemini.py`):
```python
client.chats.create(model="gemini-2.5-flash")  # Or gemini-2.0-flash
```

**DeepSeek** (`src/deepseekon.py`):
- Uses DeepSeek's speech recognition API
- Requires API key configuration

---

### 2. OCR (Slide Processing)

#### Basic Usage
```bash
# Process single PDF
python src/main.py ocr data/slides/lecture1.pdf

# Process all PDFs in directory
python src/main.py ocr data/slides/*.pdf

# Process images
python src/main.py ocr data/slides/slide1.jpg data/slides/slide2.png
```

#### Advanced Options
```bash
python src/main.py ocr \
  --output-dir results/ocr_custom \
  data/slides/*.pdf
```

**Available Options**:
- `--output-dir DIR`: Custom output directory (default: `results/ocr`)

**OCR Processing Details**:
- **Languages**: Configured for Vietnamese + English (`vie+eng`)
- **Preprocessing**:
  - Grayscale conversion
  - OTSU thresholding
  - Morphological operations (dilation/erosion)
  - Noise reduction
- **PDF Handling**: Automatically converts PDF pages to images
- **Output**: Extracted text saved as `.txt` files

#### OCR Configuration (in code)
Edit `src/slide_processor.py`:

```python
# Language settings
pytesseract.image_to_string(image, lang='vie+eng')  # Modify lang parameter

# Preprocessing intensity
kernel = np.ones((1, 1), np.uint8)  # Adjust kernel size
gray = cv2.dilate(gray, kernel, iterations=1)  # Adjust iterations
```

---

### 3. Combined Processing

Process both audio and slides simultaneously:

```bash
python src/main.py all \
  --videos data/videos/lecture1.mp4 \
  --slides data/slides/lecture1.pdf \
  --output-dir results/combined
```

**Output Structure**:
```
results/combined/
├── asr/
│   └── lecture1_transcript.txt
└── ocr/
    └── lecture1_slide_text.txt
```

---

## 📊 Output Formats

### ASR Output
**Text File** (`results/asr/<video_name>.txt`):
```
[00:00:00 - 00:00:30]
Xin chào các bạn, hôm nay chúng ta sẽ học về machine learning...

[00:00:30 - 00:01:00]
Đầu tiên, hãy xem qua các khái niệm cơ bản...
```

### OCR Output
**Text File** (`results/ocr/<slide_name>.txt`):
```
Slide 1: Introduction to Machine Learning

- Supervised Learning
- Unsupervised Learning
- Reinforcement Learning

Key Concepts:
• Training Data
• Model Architecture
• Loss Function
```

---

## ⚙️ Configuration & Customization

### Model Selection

#### Whisper Models (Trade-off: Speed vs Accuracy)
| Model | Size | VRAM | Speed | WER (Vietnamese) |
|-------|------|------|-------|------------------|
| `tiny` | 39M | ~1GB | Fast | Higher error |
| `base` | 74M | ~1GB | Fast | Moderate |
| `small` | 244M | ~2GB | Medium | Good |
| `medium` | 769M | ~5GB | Slow | Better |
| `large` | 1550M | ~10GB | Very Slow | Best |
| `large-v3` | 1550M | ~10GB | Very Slow | Best (latest) |

Edit in `src/audio_processor.py`:
```python
asr = PhoWhisperASR(model_name="large-v3")  # Change model here
```

#### GPU Configuration
```python
# Force CPU
device = "cpu"

# Use GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"
```

### OCR Preprocessing Tuning

Edit `src/slide_processor.py`:

```python
# Adjust preprocessing pipeline
def preprocess_image(self, image_path):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Option 1: OTSU (current)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    
    # Option 2: Adaptive thresholding (for varied lighting)
    # gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
    #                               cv2.THRESH_BINARY, 11, 2)
    
    # Adjust morphological operations
    kernel = np.ones((2, 2), np.uint8)  # Larger kernel for more aggressive filtering
    gray = cv2.dilate(gray, kernel, iterations=2)
    gray = cv2.erode(gray, kernel, iterations=2)
    
    return gray
```

---

## 🔍 Model Comparison & Benchmarks

The project includes detailed performance evaluations:

### ASR Model Rankings (`asr rank.md`)
Compares Whisper variants, Gemini, and DeepSeek on:
- Word Error Rate (WER)
- Real-time factor (processing speed)
- Vietnamese language accuracy
- Resource consumption

### OCR Method Rankings (`ocr rank.md`)
Evaluates preprocessing techniques:
- OTSU vs Adaptive thresholding
- Different kernel sizes
- Language-specific accuracy (Vietnamese + English)

### Overall Model Comparison (`model comparison.md`)
Comprehensive analysis including:
- Cost analysis (API vs local models)
- Latency measurements
- Accuracy metrics
- Use case recommendations

---

## 🛠️ Troubleshooting

### Common Issues

#### 1. Tesseract Not Found
```bash
pytesseract.TesseractNotFoundError: tesseract is not installed
```
**Solution**:
- Install Tesseract OCR (see Installation section)
- Add to PATH (Windows) or verify with `which tesseract` (Linux/macOS)

#### 2. FFmpeg Not Found
```bash
FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```
**Solution**:
- Install FFmpeg (see Installation section)
- Verify with `ffmpeg -version`

#### 3. CUDA Out of Memory
```bash
torch.cuda.OutOfMemoryError: CUDA out of memory
```
**Solution**:
```python
# Switch to smaller model
asr = PhoWhisperASR(model_name="small")  # Instead of "large"

# Or force CPU
device = "cpu"
```

#### 4. PDF Conversion Fails
```bash
PDFInfoNotInstalledError: Unable to get page count
```
**Solution**:
- Install Poppler: `sudo apt install poppler-utils` (Linux)
- Or download Windows binaries and add to PATH

#### 5. API Key Errors (Gemini/DeepSeek)
```bash
google.auth.exceptions.DefaultCredentialsError
```
**Solution**:
- Create `.env` file with API keys
- Or set environment variables:
  ```bash
  export GEMINI_API_KEY="your_key_here"
  ```

---

## 📝 Development Notes

### Code Organization
- **`audio_processor.py`**: Contains `AudioExtractor` (video→audio) and `PhoWhisperASR` (transcription)
- **`slide_processor.py`**: Contains `SlideOCR` with preprocessing and extraction logic
- **`main.py`**: CLI argument parsing and workflow orchestration
- **`gemini.py`**, **`deepseekon.py`**: Alternative ASR backends using APIs
- **`whisper.py`**: Standalone Whisper implementation using Hugging Face transformers

### Extending the Pipeline

#### Adding a New ASR Model
1. Create new file in `src/` (e.g., `my_model.py`)
2. Implement transcription function:
   ```python
   def transcribe(audio_path, language=None):
       # Your model logic
       return {"text": transcript, "timestamps": [...]}
   ```
3. Import and call in `audio_processor.py`

#### Adding a New OCR Engine
1. Edit `src/slide_processor.py`
2. Add new method to `SlideOCR` class:
   ```python
   def ocr_with_new_engine(self, image_path):
       # Your OCR logic
       return extracted_text
   ```
3. Update `process_slides()` to use new method

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Additional language support
- Real-time streaming transcription
- Web interface for easier usage
- Docker containerization
- Automatic language detection
- Subtitle generation (SRT/VTT formats)

**Contribution Steps**:
1. Fork the repository
2. Create feature branch: `git checkout -b feature/YourFeature`
3. Commit changes: `git commit -m 'Add YourFeature'`
4. Push to branch: `git push origin feature/YourFeature`
5. Open Pull Request

---

## 📄 License

[Specify your license here - e.g., MIT, Apache 2.0]

---

## 🙏 Acknowledgments

- **OpenAI Whisper**: State-of-the-art speech recognition
- **Google Gemini**: Multimodal AI capabilities
- **Tesseract OCR**: Open-source OCR engine
- **PyTorch**: Deep learning framework
- **Hugging Face**: Model hosting and transformers library

---

## 📧 Contact & Support

For questions, issues, or collaboration:
- GitHub Issues: [Create an issue](https://github.com/yourusername/capstone-project/issues)
- Email: your.email@example.com

---

**Last Updated**: November 14, 2025  
**Version**: 1.0.0  
**Status**: Active Development


## Notes

#### Core Implementation Files
- `src/main.py` - Main entry point
- `src/audio_processor.py` - Whisper ASR processor
- `src/slide_processor.py` - Tesseract OCR processor
- `src/gemini.py` - Google Gemini ASR processor


#### Additional Files
- `src/whisper.py` - Whisper ASR
- `src/transcribe.py` - Wav2Vec ASR
- `src/geminisd.py` - Google Gemini OCR
- `src/deepseekoff.py` - DeepSeek OCR


#### Statistics Files
- `asr rank.md` - ASR comparison
- `ocr rank.md` - OCR comparison
- `model comparison.md` - Detailed model analysis