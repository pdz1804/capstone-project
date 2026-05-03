# RAG Pipeline Comparison Project

This project provides a comprehensive comparison of three different approaches to building RAG (Retrieval-Augmented Generation) pipelines:

1. **LangChain**: High-level framework with extensive integrations
2. **LlamaIndex**: Pythonic alternative focused on data connectivity
3. **Manual**: From-scratch implementation for maximum control

## Features

- 🔍 **Multiple Vector Stores**: Support for FAISS and Chroma
- 🤖 **Multiple LLM Providers**: OpenAI GPT-4o-mini, Azure OpenAI, Google Gemini, and Ollama
- ⚡ **Performance Benchmarking**: Comprehensive metrics collection
- 📊 **Detailed Comparison**: Automated report generation
- 🧪 **Test Suite**: Unit and integration tests
- 🏗️ **Microservice Architecture**: Modular and extensible design

## Project Structure

```
Week0304/
├── src/                          # Source code
│   ├── shared/                   # Shared utilities and configuration
│   │   ├── config.py            # Configuration management
│   │   └── utils.py             # Utility functions
│   ├── langchain_rag/           # LangChain implementation
│   │   └── rag_system.py
│   ├── llamaindex_rag/          # LlamaIndex implementation
│   │   └── rag_system.py
│   ├── manual_rag/              # Manual implementation
│   │   └── rag_system.py
│   └── benchmark_runner.py      # Benchmark orchestrator
├── data/                        # Document storage
├── logs/                        # Performance logs
├── results/                     # Benchmark results
├── tests/                       # Test suite
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
└── README.md                    # This file
```

## Quick Start

### 1. Environment Setup

```bash
# Clone or navigate to the project directory
cd Week0304

# Create and activate virtual environment (if not already done)
# python -m venv venv
# venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
copy .env.example .env
# Edit .env file with your API keys
```

### 2. Configure API Keys

Edit the `.env` file with your API keys:

```env
OPENAI_API_KEY=your_openai_api_key_here
AZURE_OPENAI_API_KEY=your_azure_openai_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
GOOGLE_API_KEY=your_google_api_key_here
```

### 3. Prepare Data

Place your text documents in the `data/` directory, or let the system create sample documents automatically.

### 4. Run Individual Implementations

#### Manual RAG

```bash
cd src
python manual_rag/rag_system.py --vector-store faiss --llm openai --rebuild
```

#### LangChain RAG

```bash
cd src
python langchain_rag/rag_system.py --vector-store faiss --llm openai --rebuild
```

#### LlamaIndex RAG

```bash
cd src
python llamaindex_rag/rag_system.py --vector-store faiss --llm openai --rebuild
```

### 5. Run Comprehensive Benchmark

```bash
cd src
python benchmark_runner.py --vector-stores faiss chroma --llm-providers openai --rebuild
```

### 6. Generate Comparison Report Only

```bash
cd src
python benchmark_runner.py --report-only

python benchmark_runner.py --ai-report

python benchmark_runner.py --rebuild --both-reports --vector-stores faiss chroma --llm-providers openai
```

## Detailed Usage

### Command Line Options

Each RAG implementation supports these options:

- `--vector-store`: Choose between `faiss` or `chroma`
- `--llm`: Choose between `openai`, `azure`, `gemini`, or `ollama`
- `--data-dir`: Path to document directory (default: `./data`)
- `--rebuild`: Force rebuild of vector store

### Benchmark Runner Options

- `--vector-stores`: List of vector stores to test
- `--llm-providers`: List of LLM providers to test
- `--data-dir`: Path to document directory
- `--rebuild`: Rebuild all vector stores
- `--report-only`: Generate report from existing results

### Output Files

The system generates several types of output:

1. **Performance Logs**: `logs/[method]_[vectorstore]_[llm]_metrics.json`
2. **Detailed Results**: `results/[method]_[vectorstore]_[llm]_results.json`
3. **Comprehensive Results**: `results/comprehensive_benchmark.json`
4. **Comparison Report**: `results/comparison_report.md`

## Performance Metrics

The benchmark tracks:

- **Embedding Time**: Time to generate embeddings
- **Indexing Time**: Time to build vector index
- **Retrieval Time**: Time to retrieve relevant chunks
- **Generation Time**: Time to generate answers
- **Total Time**: Complete pipeline time
- **Memory Usage**: Peak memory consumption
- **Retrieval Accuracy**: Quality of retrieved documents
- **Answer Quality**: Heuristic-based answer evaluation

## Testing

Run the test suite:

```bash
# Run all tests
cd tests
python -m pytest test_rag_systems.py -v

# Run only unit tests (skip integration tests)
python -m pytest test_rag_systems.py -v -m "not integration"
```

## Architecture Details

### Shared Components

- **Config**: Centralized configuration management
- **Utils**: Performance tracking, document processing, embedding generation
- **Logging**: Structured logging with different levels

### Implementation-Specific Features

#### Manual RAG

- Direct control over all components
- Custom chunking and embedding logic
- Minimal dependencies
- Maximum performance optimization potential

#### LangChain RAG

- Rich ecosystem integration
- Pre-built chains and retrievers
- Easy LLM provider switching
- Extensive documentation and community

#### LlamaIndex RAG

- Data-centric design
- Advanced indexing strategies
- Python-first approach
- Strong integration capabilities

### Vector Store Comparison

#### FAISS

- **Pros**: Fast similarity search, local storage, no external dependencies
- **Cons**: Limited metadata support, manual persistence management

#### Chroma

- **Pros**: Rich metadata support, automatic persistence, better filtering
- **Cons**: Additional dependency, potential network overhead

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed (`pip install -r requirements.txt`)
2. **API Key Errors**: Verify your `.env` file is properly configured
3. **Memory Issues**: Reduce batch size in config or use smaller documents
4. **Ollama Connection**: Ensure Ollama is running locally on port 11434

### Debug Mode

Enable debug logging by setting `LOG_LEVEL=DEBUG` in your `.env` file.

### Performance Optimization

- Use FAISS for faster retrieval
- Reduce chunk size for memory efficiency
- Use smaller embedding models for speed
- Implement batch processing for large document sets

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for GPT models and APIs
- Hugging Face for embedding models
- LangChain and LlamaIndex communities
- FAISS and Chroma Vector Database projects

## Future Enhancements

- Additional vector store support (Pinecone, Weaviate)
- More LLM providers (Anthropic Claude, local models)
- Advanced evaluation metrics
- GUI interface for easier comparison
- Docker containerization
- Cloud deployment scripts
