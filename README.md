# Lecture Processing Pipeline

A comprehensive tool for processing educational content, featuring automatic speech recognition (ASR) for lecture videos and optical character recognition (OCR) for lecture slides. Built with Python and optimized for academic use cases.

## Features

- High-accuracy speech-to-text conversion using PhoWhisper
- OCR for extracting text from lecture slides and PDFs
- Video processing with audio extraction capabilities
- Structured output in multiple formats (TXT, CSV, JSON)
- Optimized for batch processing of multiple files

## Getting Started

### Prerequisites

- Python 3.9+
- Tesseract OCR (for slide processing)
- FFmpeg (for audio/video processing)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/lecture-processing-pipeline.git
   cd lecture-processing-pipeline
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install system dependencies:
   - **Windows**: 
     - Download and install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
     - Download and install [FFmpeg](https://ffmpeg.org/download.html)
     - Add both to your system PATH
   
   - **Linux**:
     ```bash
     sudo apt update
     sudo apt install tesseract-ocr tesseract-ocr-vie ffmpeg
     ```
   
   - **macOS**:
     ```bash
     brew install tesseract tesseract-lang ffmpeg
     ```

## Usage

The application has two main modes: `asr` for speech recognition and `ocr` for slide processing. Use the appropriate mode based on your needs.

### 1. Speech Recognition (ASR) Mode

Process lecture videos or audio files to extract text transcripts:

```bash
python main.py asr [options] <input_files>

Options:
  --model {tiny,base,small,medium,large}  Whisper model size (default: small)
  --language LANG                        Language code (e.g., vi, en, ja)
  --output-dir DIR                       Output directory (default: results/asr/)
  --format {txt,json,csv}               Output format (default: txt)
  --device {cpu,cuda}                    Device to use for inference
```

Example:
```bash
# Process a single video file
python main.py asr --model large --language vi --format json data/videos/lecture1.mp4

# Process multiple files
python main.py asr data/videos/lecture1.mp4 data/videos/lecture2.mp4
```

### 2. Slide Processing (OCR) Mode

Extract text from lecture slides or PDFs:

```bash
python main.py ocr [options] <input_files>

Options:
  --output-dir DIR      Output directory (default: results/ocr/)
  --lang LANG           Language for OCR (default: vie+eng)
  --preprocess {none,adaptive,otsu}  Image preprocessing method (default: adaptive)
  --output-format {txt,json}  Output format (default: txt)
```

Example:
```bash
# Process all PDF files in a directory
python main.py ocr --lang vie+eng --preprocess adaptive data/slides/*.pdf

# Process specific image files
python main.py ocr slide1.jpg slide2.png
```

## 📁 Project Structure

```
.
├── data/                   # Input/output data
│   ├── audio/             # Extracted audio files
│   ├── slides/            # Lecture slides (PDF/Images)
│   └── videos/            # Lecture videos
├── models/                # Pretrained models
├── results/               # Processing results
│   ├── asr/              # Speech recognition outputs
│   └── ocr/              # OCR outputs
├── main.py                # Main entry point for the application
├── audio_processor.py     # Audio processing and ASR (imported by main.py)
├── slide_processor.py     # Slide processing and OCR (imported by main.py)
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI Whisper for the speech recognition model
- Tesseract OCR for text extraction
- All contributors who helped improve this project
  - `videos/`: Input lecture videos
  - `slides/`: Input lecture slides
- `results/`: Output directory for transcripts and OCR results

## Notes

- For best OCR results, ensure slides are high-contrast and well-lit
- PhoWhisper works best with clear audio and minimal background noise
- Processing time depends on video/slide length and hardware capabilities
