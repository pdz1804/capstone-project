# Multimodal Document Processor for RAG Pipeline

This project provides a comprehensive document processing solution using Docling's advanced capabilities, specifically designed for educational content processing at HCMUT (Ho Chi Minh City University of Technology).

## 🚀 Features

### Advanced Document Understanding
- **PDF Processing**: Advanced layout analysis, reading order detection, table structure recognition
- **OCR Support**: Multiple OCR engines (Tesseract, EasyOCR, RapidOCR) for scanned documents
- **Visual Language Models**: Integration with GraniteDocling for enhanced visual understanding
- **Audio Processing**: Automatic Speech Recognition (ASR) for lecture recordings
- **Multimodal Export**: Structured output in Markdown, HTML, JSON formats

### Educational Content Optimization
- **Lecture Materials**: Optimized for slides, documents, and presentation materials
- **Audio Transcription**: Support for lecture recordings and educational audio content
- **Visual Elements**: Extraction of diagrams, equations, charts, and tables
- **Metadata Enrichment**: Comprehensive document metadata for better organization

### Technical Capabilities
- **GPU Acceleration**: Leverages GPU for faster processing when available
- **Batch Processing**: Efficient handling of large document collections
- **Format Support**: PDF, DOCX, PPTX, XLSX, images, audio files, and more
- **Error Handling**: Robust error handling and detailed logging

## 📁 Project Structure

```
Week0506/
├── src/
│   └── document_processor.py     # Main DocumentProcessor class
├── input/                        # Place your documents here
├── output/                       # Processed documents output
│   ├── markdown/                # Primary output for GenAI consumption
│   ├── images/                  # Extracted images and diagrams
│   ├── tables/                  # Extracted tables in various formats
│   ├── metadata/                # Document metadata and statistics
│   └── logs/                    # Processing logs and summaries
├── test_processor.py            # Comprehensive test script
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## 🛠️ Installation

1. **Create a virtual environment** (recommended):
```bash
python -m venv docling_env
# On Windows:
docling_env\\Scripts\\activate
# On macOS/Linux:
source docling_env/bin/activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Verify installation**:
```bash
python test_processor.py --test-type basic
```

## 🚀 Quick Start

### Basic Usage

```python
from src.document_processor import DocumentProcessor, ProcessingConfig

# Create configuration
config = ProcessingConfig(
    use_gpu=True,           # Enable GPU acceleration
    enable_ocr=True,        # Enable OCR for scanned documents
    enable_vlm=True,        # Enable Visual Language Model
    enable_asr=True,        # Enable Audio Speech Recognition
    export_markdown=True,   # Export to Markdown (recommended for GenAI)
    export_images=True,     # Extract images and diagrams
    export_tables=True      # Extract tables separately
)

# Initialize processor
processor = DocumentProcessor(
    input_dir="input",
    output_dir="output", 
    config=config
)

# Process all documents in input directory
results = processor.process_batch()

print(f"Processed {results['processed_files']} files successfully")
```

### Context Manager Usage (Recommended)

```python
# Using context manager for automatic cleanup
with DocumentProcessor("input", "output", config) as processor:
    results = processor.process_batch()
    stats = processor.get_processing_stats()
    print(f"File types processed: {stats['file_types']}")
```

### Single File Processing

```python
from pathlib import Path

# Process a specific file
file_path = Path("input/lecture_slides.pdf")
processing_info = processor.process_single_file(file_path)

if processing_info['success']:
    # Export the processed document
    exported_files = processor.export_processed_document(processing_info)
    print(f"Exported to: {list(exported_files.keys())}")
```

## 🔧 Configuration Options

The `ProcessingConfig` class allows fine-tuning of processing behavior:

```python
config = ProcessingConfig(
    # Hardware settings
    use_gpu=True,                    # Use GPU acceleration if available
    
    # Processing features
    enable_ocr=True,                 # OCR for scanned documents
    enable_vlm=True,                 # Visual Language Model understanding
    enable_asr=True,                 # Audio Speech Recognition
    
    # OCR configuration
    ocr_engine="tesseract",          # Options: tesseract, easyocr, rapidocr
    ocr_languages=["eng", "vie"],    # Language codes for OCR
    
    # Export settings
    export_markdown=True,            # Primary format for GenAI
    export_images=True,              # Extract images separately
    export_tables=True,              # Extract tables in CSV/MD format
    export_metadata=True,            # Comprehensive metadata
    
    # Output organization
    create_subfolder_per_doc=True,   # Organize by document
    preserve_structure=True          # Maintain input folder structure
)
```

## 📊 Supported Formats

| Category | Extensions | Processing Features |
|----------|------------|-------------------|
| **PDF** | `.pdf` | Layout analysis, OCR, table extraction, image extraction |
| **Office** | `.docx`, `.pptx`, `.xlsx` | Structure preservation, media extraction |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.tiff` | OCR, visual analysis, content extraction |
| **Audio** | `.wav`, `.mp3`, `.m4a` | Speech recognition, transcription |
| **Web** | `.html`, `.htm` | Structure parsing, content extraction |
| **Text** | `.txt`, `.md` | Direct processing, format conversion |

## 🎯 Use Cases for HCMUT Educational Context

### 1. Lecture Material Processing
```python
# Process lecture slides and handouts
config = ProcessingConfig(
    enable_ocr=True,     # For scanned slides
    enable_vlm=True,     # Understanding diagrams and equations
    export_images=True   # Extract important visuals
)
```

### 2. Audio Lecture Processing
```python
# Process recorded lectures
config = ProcessingConfig(
    enable_asr=True,           # Transcribe audio content
    asr_model="whisper",       # High-quality transcription
    export_metadata=True       # Track lecture metadata
)
```

### 3. Research Paper Processing
```python
# Process academic papers and documents
config = ProcessingConfig(
    enable_ocr=True,           # Handle scanned papers
    enable_vlm=True,           # Understand figures and tables
    export_tables=True,        # Extract research data
    create_subfolder_per_doc=True  # Organize by paper
)
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Basic test with sample files
python test_processor.py --test-type basic

# Advanced test with multiple configurations
python test_processor.py --test-type advanced

# Both tests with verbose output
python test_processor.py --test-type both --verbose
```

### Test Script Features
- **Automatic Sample Generation**: Creates test files if none exist
- **Multiple Configurations**: Tests different processing setups
- **Performance Metrics**: Measures processing speed and success rates
- **Output Visualization**: Shows processed file structure
- **Error Analysis**: Detailed error reporting

## 📈 Output Structure

After processing, your output directory will contain:

```
output/
├── markdown/              # Primary GenAI-ready content
│   ├── document1.md
│   └── document2.md
├── images/                # Extracted images and diagrams
│   ├── document1/
│   │   ├── image_001.png
│   │   └── image_002.png
│   └── document2/
├── tables/                # Extracted tables
│   ├── document1/
│   │   ├── table_001.csv
│   │   └── table_001.md
│   └── document2/
├── metadata/              # Document metadata and statistics
│   ├── document1_metadata.json
│   └── document2_metadata.json
└── logs/                  # Processing logs and batch summaries
    ├── processing_20241022_143022.log
    └── batch_summary_20241022_143022.json
```

## 🔍 Integration with RAG Pipeline

The processed documents are optimized for RAG (Retrieval-Augmented Generation) pipelines:

### Text Embeddings
- **Markdown Output**: Clean, structured text perfect for text embeddings
- **Chunking-Ready**: Proper heading structure for semantic chunking
- **Metadata Rich**: Comprehensive metadata for filtering and routing

### Multimodal Embeddings
- **Extracted Images**: Individual images for visual embeddings
- **Layout Images**: Page-level layout understanding
- **Table Data**: Structured data for specialized retrieval

### Example Integration
```python
# After processing documents
from pathlib import Path

# Get processed markdown for text embeddings
markdown_files = list(Path("output/markdown").glob("*.md"))

# Get extracted images for visual embeddings  
image_dirs = list(Path("output/images").iterdir())

# Get metadata for enhanced retrieval
metadata_files = list(Path("output/metadata").glob("*_metadata.json"))
```

## ⚡ Performance Optimization

### GPU Acceleration
- Automatically uses GPU when available
- Significant speed improvement for VLM and OCR processing
- Falls back gracefully to CPU processing

### Batch Processing
- Efficient memory management for large document sets
- Progress tracking and error recovery
- Parallel processing where possible

### Memory Management
- Streams large files to avoid memory issues
- Automatic cleanup of temporary files
- Resource monitoring and reporting

## 🔧 Troubleshooting

### Common Issues

1. **Import Errors**: Ensure Docling is properly installed with all dependencies
2. **GPU Issues**: Check CUDA installation for GPU acceleration
3. **OCR Problems**: Verify Tesseract installation and language packs
4. **Memory Issues**: Reduce batch size or disable certain features

### Debug Mode
Enable detailed logging for troubleshooting:

```python
python test_processor.py --verbose
```

### Performance Monitoring
Check processing statistics:

```python
stats = processor.get_processing_stats()
print(f"Processing time: {stats['processing_time']:.2f}s")
print(f"Success rate: {stats['processed_files']/stats['total_files']*100:.1f}%")
```

## 🚀 Future Enhancements

- **Chart Understanding**: Enhanced support for educational charts and graphs
- **Chemical Formulas**: Specialized processing for chemistry content
- **Language Detection**: Automatic language detection and processing
- **Custom VLM Models**: Integration with domain-specific vision models
- **Advanced Chunking**: Semantic chunking strategies for better RAG performance

## 📝 License

This project is part of the HCMUT educational research initiative. Please refer to your institution's guidelines for usage and distribution.

## 🤝 Contributing

This is an educational research project. For improvements or bug reports, please follow your institution's collaboration guidelines.

---

**Note**: This document processor is specifically designed for the HCMUT multimodal RAG pipeline project. The configuration and features are optimized for educational content processing and GenAI integration.