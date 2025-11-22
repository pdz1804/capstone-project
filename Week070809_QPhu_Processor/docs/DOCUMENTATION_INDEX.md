# Document Processing Pipeline - Complete Documentation Index

## Welcome

This directory contains comprehensive documentation for the **Unified Document Processing Pipeline**, a production-ready system for preparing multimodal documents for RAG (Retrieval-Augmented Generation) systems.

---

## 📚 Documentation Files

### 1. [PIPELINE_ARCHITECTURE.md](PIPELINE_ARCHITECTURE.md)
**Overview of the complete three-stage pipeline**

- Three-stage architecture explanation
- Data flow diagrams
- Design rationale and decisions
- Configuration system
- Performance characteristics
- Output structure

**Read this first** to understand the overall system design.

---

### 2. [STAGE1_NORMALIZATION.md](STAGE1_NORMALIZATION.md)
**Detailed documentation for Stage 1: Document Normalization**

- Module: `normalizer.py`
- Convert diverse formats → PDF + Markdown
- LibreOffice integration for high-quality conversion
- Function reference and API
- Configuration options
- Examples and best practices

**Key Topics**:
- DOCX/PPTX → PDF conversion
- HTML/Excel → Markdown conversion
- Image → PDF conversion
- Safe filename handling

---

### 3. [STAGE2_MEDIA.md](STAGE2_MEDIA.md)
**Detailed documentation for Stage 2: Media Processing**

- Module: `media_processor.py`
- Video → Audio → Text transcription
- Whisper ASR integration
- Frame extraction from videos
- Multiple output formats (TXT, JSON, SRT, VTT)

**Key Topics**:
- Audio extraction with MoviePy
- Transcription with OpenAI Whisper
- Chunked processing for long videos
- Whisper model selection guide
- GPU acceleration

---

### 4. [STAGE3_DOCUMENT.md](STAGE3_DOCUMENT.md)
**Detailed documentation for Stage 3: Document Processing**

- Module: `document_processor.py`
- Deep document analysis with Docling
- OCR, VLM, and table extraction
- Image filtering and quality control
- Structured export (Markdown, images, tables)

**Key Topics**:
- Docling integration
- OCR engines (RapidOCR, Tesseract, EasyOCR)
- Visual Language Models (SmolVLM)
- Advanced image filtering
- GPU acceleration

---

## 🚀 Quick Start

### Installation

```bash
# Create virtual environment
python -m venv myenv
source myenv/bin/activate  # On Windows: myenv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install LibreOffice for best DOCX/PPTX conversion
# Download from: https://www.libreoffice.org/download/
```

### Basic Usage

```python
from src.pipeline import DocumentProcessingPipeline

# Initialize pipeline
pipeline = DocumentProcessingPipeline(
    input_dir="./input",
    output_dir="./output"
)

# Run all three stages
stats = pipeline.run()

print(f"Total files processed: {stats['total_output_files']}")
```

### Command-Line Usage

```bash
# Process all files in input directory
python pipeline.py --input ./input --output ./output

# Custom configuration
python pipeline.py --input ./input --output ./output \
    --whisper-model base \
    --enable-vlm \
    --gpu
```

---

## 📁 Project Structure

```
Week070809_QPhu_Processor/
├── README.md                        # Quick start guide
├── PIPELINE_ARCHITECTURE.md         # 📘 Overall architecture
├── STAGE1_NORMALIZATION.md          # 📗 Stage 1 details
├── STAGE2_MEDIA.md                  # 📙 Stage 2 details
├── STAGE3_DOCUMENT.md               # 📕 Stage 3 details
├── DOCUMENTATION_INDEX.md           # 📚 This file
├── pipeline.py                      # Main entry point
├── requirements.txt                 # Dependencies
├── src/
│   ├── __init__.py
│   ├── pipeline.py                  # Pipeline orchestrator
│   ├── normalizer.py                # Stage 1: Normalization
│   ├── media_processor.py           # Stage 2: Media processing
│   ├── document_processor.py        # Stage 3: Document processing
│   └── utils.py                     # Utility functions
├── input/                           # Input files
└── output/                          # Output directory
    ├── pipeline_stats.json
    ├── stage1_normalized/
    ├── stage2_media_processed/
    └── stage3_document_processed/
```

---

## 🎯 Use Cases

### 1. Educational Content Processing
**Scenario**: Process lecture videos, slides, and papers for an AI-powered learning assistant.

**Configuration**:
```python
from src.pipeline import DocumentProcessingPipeline, PipelineConfig
from src.media_processor import MediaProcessorConfig

config = PipelineConfig(
    media_config=MediaProcessorConfig(
        asr_model="base",           # Good balance
        extract_frames=True,        # Extract slides from video
        frame_interval=100
    )
)

pipeline = DocumentProcessingPipeline(
    input_dir="./lectures",
    output_dir="./processed",
    config=config
)
```

**Input**: 
- Lecture videos (MP4)
- PowerPoint slides (PPTX)
- Research papers (PDF)

**Output**:
- Transcribed lectures (Markdown)
- Processed slides (Markdown + images)
- Analyzed papers (Markdown + extracted figures)

---

### 2. Enterprise Document Management
**Scenario**: Convert legacy documents to searchable format.

**Configuration**:
```python
config = PipelineConfig(
    enable_media_processing=False,   # No videos
    document_config=ProcessingConfig(
        enable_ocr=True,             # Scan old documents
        enable_vlm=True,             # Describe diagrams
        export_tables=True           # Extract data tables
    )
)
```

**Input**:
- Scanned PDFs
- Word documents (DOCX)
- Spreadsheets (XLSX)

**Output**:
- OCR-processed documents (Markdown)
- Extracted tables (CSV)
- Searchable text for RAG

---

### 3. Multimodal RAG System
**Scenario**: Build a RAG system that retrieves both text and images.

**Configuration**:
```python
config = PipelineConfig(
    normalizer_config=NormalizerConfig(
        generate_pdf=True,           # PDFs for image RAG
        generate_markdown=True       # Markdown for text RAG
    ),
    document_config=ProcessingConfig(
        export_images=True,          # Extract all images
        min_image_area=5000          # Keep smaller images
    )
)
```

**Output Structure**:
- **Text-based RAG**: Use `stage3_document_processed/*.md`
- **Image-based RAG**: Use `stage1_normalized/normalized_pdfs/*.pdf`
- **Hybrid RAG**: Combine both approaches

---

## ⚙️ Configuration Guide

### Quick Configuration Presets

#### Fastest (Quick Testing)
```python
from src.pipeline import PipelineConfig
from src.media_processor import MediaProcessorConfig
from src.document_processor import ProcessingConfig

config = PipelineConfig(
    normalizer_config=NormalizerConfig(generate_pdf=False),
    media_config=MediaProcessorConfig(asr_model="tiny"),
    document_config=ProcessingConfig(enable_vlm=False)
)
```

#### Balanced (Recommended)
```python
config = PipelineConfig()  # Uses all defaults
# - Normalization: PDF + Markdown
# - Media: Whisper base model
# - Document: OCR + VLM with GPU
```

#### Maximum Quality (Slowest)
```python
config = PipelineConfig(
    normalizer_config=NormalizerConfig(image_quality=100),
    media_config=MediaProcessorConfig(asr_model="large-v3"),
    document_config=ProcessingConfig(
        enable_vlm=True,
        ocr_engine="easyocr",
        use_gpu=True
    )
)
```

---

## 🔧 Module Reference

### Stage 1: Normalization (`normalizer.py`)

**Classes**:
- `NormalizerConfig`: Configuration dataclass
- `DocumentNormalizer`: Main normalization engine

**Key Functions**:
- `normalize_batch()`: Process all files
- `_normalize_docx()`: DOCX → PDF + Markdown
- `_normalize_pptx()`: PPTX → PDF + Markdown
- `_normalize_html()`: HTML → Markdown
- `_normalize_excel()`: XLSX → Markdown tables
- `_normalize_image()`: Image → PDF

**Supported Formats**: DOCX, PPTX, HTML, XLSX, CSV, Images, PDF, MD, TXT

---

### Stage 2: Media (`media_processor.py`)

**Classes**:
- `MediaProcessorConfig`: Configuration dataclass
- `MediaProcessor`: Main orchestrator
- `AudioExtractor`: Video → Audio extraction
- `AudioTranscriber`: Audio → Text (Whisper)
- `FrameExtractor`: Video → Frame extraction

**Key Functions**:
- `process_batch()`: Process all media files
- `extract_audio()`: Extract audio from video
- `transcribe()`: Transcribe audio with Whisper
- `transcribe_chunked()`: Chunked processing for long audio
- `extract_frames()`: Extract frames from video

**Supported Formats**: MP4, AVI, MOV, WAV, MP3, M4A

---

### Stage 3: Document (`document_processor.py`)

**Classes**:
- `ProcessingConfig`: Configuration dataclass
- `MultimodalDocumentProcessor`: Main Docling orchestrator

**Key Functions**:
- `process_batch()`: Process all files
- `process_single_file()`: Process one file
- `_export_markdown()`: Export to Markdown
- `_export_images()`: Export images (filtered)
- `_export_tables()`: Export tables (CSV + MD)
- `_export_metadata()`: Save processing metadata

**Supported Formats**: PDF, DOCX, PPTX, XLSX, Images, HTML, MD, TXT

---

## 📊 Output Formats

### Text Outputs
- **Markdown (`.md`)**: Main text-based output for RAG
- **Plain Text (`.txt`)**: Transcripts from media
- **JSON (`.json`)**: Structured data with timestamps

### Image Outputs
- **PDF (`.pdf`)**: Normalized PDFs for image-based RAG
- **PNG/JPG**: Extracted images from documents
- **Video frames**: Extracted frames from videos

### Data Outputs
- **CSV (`.csv`)**: Extracted tables (machine-readable)
- **Markdown Tables**: Human-readable tables
- **Metadata JSON**: Processing statistics

### Subtitle Formats
- **SRT (`.srt`)**: Standard subtitle format
- **WebVTT (`.vtt`)**: Web subtitle format

---

## 🐛 Troubleshooting

### Issue 1: LibreOffice Not Found
**Error**: "LibreOffice not found in system"

**Solution**:
1. Install LibreOffice from https://www.libreoffice.org/download/
2. Or accept ReportLab fallback (text-only PDFs)

**Impact**: Stage 1 PDFs will be text-only without LibreOffice

---

### Issue 2: Whisper Model Download Slow
**Error**: "Downloading Whisper model..."

**Solution**: Models are cached after first download
- `tiny`: 39MB (fast download)
- `base`: 74MB (recommended)
- `large`: 1.5GB (slow download)

**Tip**: Start with `tiny` for testing, upgrade to `base` for production

---

### Issue 3: CUDA Out of Memory
**Error**: "CUDA out of memory"

**Solutions**:
1. Use smaller Whisper model (`base` instead of `large`)
2. Disable VLM: `enable_vlm=False`
3. Process fewer files at once
4. Reduce batch size in VLM config

**VRAM Requirements**:
- Minimal (no GPU): CPU-only
- Basic (4GB): Whisper base + VLM
- Recommended (8GB): Whisper medium + VLM
- Advanced (16GB): Whisper large + VLM

---

### Issue 4: Slow Processing
**Symptoms**: Very slow document processing

**Solutions**:
1. Enable GPU: `use_gpu=True`
2. Use smaller Whisper model
3. Disable VLM if not needed
4. Skip frame extraction: `extract_frames=False`

**Performance Comparison**:
- CPU-only: ~50 pages/minute
- GPU (CUDA): ~200 pages/minute (4x faster)

---

## 🔗 Dependencies

### Core Libraries
```txt
# Document processing
python-docx>=0.8.11
python-pptx>=0.6.21
pandas>=1.5.0
beautifulsoup4>=4.11.0
reportlab>=3.6.12
img2pdf>=0.4.4
Pillow>=9.4.0

# Media processing
torch>=2.0.0
openai-whisper>=20231117
moviepy>=1.0.3
librosa>=0.10.0
soundfile>=0.12.1
opencv-python>=4.7.0

# Document understanding
docling[all]>=1.0.0

# Utilities
tqdm>=4.65.0
loguru>=0.7.0
```

### Optional Dependencies
```txt
# OCR engines
rapidocr-onnxruntime  # Recommended
pytesseract           # Requires Tesseract installation
easyocr               # GPU-accelerated OCR

# Advanced features
transformers          # For VLM
```

---

## 📈 Performance Benchmarks

### Processing Speed (Approximate)

| **File Type** | **Size** | **Stage 1** | **Stage 2** | **Stage 3** | **Total** |
|--------------|---------|------------|------------|------------|-----------|
| DOCX (10 pages) | 500KB | 5s | — | 15s | **20s** |
| PPTX (20 slides) | 5MB | 10s | — | 30s | **40s** |
| PDF (50 pages) | 10MB | 1s | — | 60s | **61s** |
| Image (high-res) | 5MB | 2s | — | 10s | **12s** |
| Video (10 min) | 100MB | — | 120s | 5s | **125s** |

**Hardware**: Intel i7, 16GB RAM, NVIDIA RTX 3060 (6GB VRAM)

---

## 📝 Changelog

### Version 1.0.0 (2025-11-21)
- ✅ Initial release
- ✅ Three-stage pipeline implementation
- ✅ Comprehensive documentation
- ✅ Production-ready configuration

---

## 🤝 Contributing

### Documentation Improvements
If you find errors or have suggestions for improving the documentation:
1. Note the specific file and section
2. Describe the issue or improvement
3. Submit a pull request or issue

### Code Contributions
See the main [README.md](README.md) for contribution guidelines.

---

## 📞 Support

### Getting Help
1. **Read the Docs**: Start with [PIPELINE_ARCHITECTURE.md](PIPELINE_ARCHITECTURE.md)
2. **Check Examples**: Each stage doc has detailed examples
3. **Review Troubleshooting**: Common issues listed above
4. **Check Source Code**: Inline comments in `src/` directory

### Common Questions

**Q: Which Whisper model should I use?**
A: Start with `base` (good balance), upgrade to `small` or `medium` for better accuracy.

**Q: Do I need LibreOffice?**
A: Highly recommended for DOCX/PPTX conversion. ReportLab fallback works but loses images.

**Q: Should I enable VLM?**
A: Yes, if you need image descriptions for RAG. Disable if processing speed is critical.

**Q: What's the difference between Stage 1 PDFs and Stage 3 Markdown?**
A: Stage 1 PDFs are for image-based RAG (visual similarity). Stage 3 Markdown is for text-based RAG (semantic search).

---

## 📚 Additional Resources

### Related Documentation
- Docling Documentation: https://github.com/DS4SD/docling
- OpenAI Whisper: https://github.com/openai/whisper
- MoviePy: https://zulko.github.io/moviepy/

### Research Papers
- Docling: IBM Research's Document Understanding Framework
- Whisper: Robust Speech Recognition via Large-Scale Weak Supervision
- ColPali: Vision Language Models for Document Retrieval

---

## 📄 License

See [LICENSE](LICENSE) file for details.

---

## 🎓 Citation

If you use this pipeline in your research or project:

```bibtex
@software{document_processing_pipeline,
  title={Unified Document Processing Pipeline for RAG Systems},
  author={Your Name},
  year={2025},
  url={https://github.com/yourusername/Week070809_QPhu_Processor}
}
```

---

## ✨ Acknowledgments

This pipeline integrates several open-source projects:
- **Docling** by IBM Research
- **Whisper** by OpenAI
- **MoviePy**, **LibreOffice**, **Pandas**, and many others

Special thanks to the open-source community!

---

**Last Updated**: 2025-11-21
**Version**: 1.0.0
