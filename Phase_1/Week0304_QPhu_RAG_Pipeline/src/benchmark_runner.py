"""
Benchmark runner for all RAG implementations
"""
import os
import time
import json
import asyncio
from typing import List, Dict, Any
from pathlib import Path
import sys
import argparse

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from shared.config import Config
from shared.utils import DocumentProcessor, setup_logging

# Import RAG implementations
try:
    from langchain_rag.rag_system import LangChainRAG
except ImportError:
    LangChainRAG = None

try:
    from llamaindex_rag.rag_system import LlamaIndexRAG
except ImportError:
    LlamaIndexRAG = None

from manual_rag.rag_system import ManualRAG

class RAGBenchmark:
    """Comprehensive RAG benchmark runner"""
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.results_dir = Path(Config.RESULTS_DIR)
        self.results_dir.mkdir(exist_ok=True)
        self.logger = setup_logging("benchmark")
        
        # Available implementations
        self.implementations = {
            "manual": ManualRAG,
            "langchain": LangChainRAG if LangChainRAG else None,
            "llamaindex": LlamaIndexRAG if LlamaIndexRAG else None
        }
        
        # Filter out unavailable implementations
        self.implementations = {k: v for k, v in self.implementations.items() if v is not None}
        
        self.logger.info(f"Available implementations: {list(self.implementations.keys())}")
    
    def prepare_test_data(self):
        """Prepare test data"""
        self.logger.info("Preparing test data")
        
        # Load documents
        documents = DocumentProcessor.load_documents_from_directory(self.data_dir)
        
        if not documents:
            # Create sample documents if none exist
            self.logger.warning("No documents found, creating sample documents")
            self._create_sample_documents()
            documents = DocumentProcessor.load_documents_from_directory(self.data_dir)
        
        return documents
    
    def _create_sample_documents(self):
        """Create sample documents for testing"""
        sample_docs = [
            {
                "filename": "ai_overview.txt",
                "content": """
Artificial Intelligence (AI) Overview

Artificial Intelligence is a rapidly evolving field that focuses on creating intelligent machines capable of performing tasks that typically require human intelligence. These tasks include learning, reasoning, problem-solving, perception, and language understanding.

Key Areas of AI:
1. Machine Learning: Algorithms that improve automatically through experience
2. Natural Language Processing: Enabling computers to understand and interpret human language
3. Computer Vision: Teaching machines to interpret and understand visual information
4. Robotics: Designing and programming robots to perform complex tasks
5. Expert Systems: Computer systems that emulate decision-making abilities of human experts

Applications:
- Healthcare: Diagnosis assistance, drug discovery, personalized treatment
- Finance: Fraud detection, algorithmic trading, risk assessment
- Transportation: Autonomous vehicles, traffic optimization
- Education: Personalized learning, intelligent tutoring systems
- Entertainment: Game AI, content recommendation systems

Challenges:
- Ethical considerations and bias in AI systems
- Data privacy and security concerns
- Explainability and transparency of AI decisions
- Job displacement and economic impacts
- Technical limitations and computational requirements

The future of AI holds great promise for solving complex global challenges while requiring careful consideration of its societal implications.
                """
            },
            {
                "filename": "machine_learning_basics.txt",
                "content": """
Machine Learning Fundamentals

Machine Learning (ML) is a subset of artificial intelligence that enables systems to automatically learn and improve from experience without being explicitly programmed. It focuses on developing algorithms that can access data and use it to learn patterns and make predictions.

Types of Machine Learning:

1. Supervised Learning:
   - Uses labeled training data
   - Goal is to learn a mapping from inputs to outputs
   - Examples: Classification, regression
   - Algorithms: Linear regression, decision trees, neural networks

2. Unsupervised Learning:
   - Works with unlabeled data
   - Finds hidden patterns or structures
   - Examples: Clustering, dimensionality reduction
   - Algorithms: K-means, hierarchical clustering, PCA

3. Reinforcement Learning:
   - Learns through interaction with environment
   - Uses reward/punishment feedback
   - Examples: Game playing, robotics
   - Algorithms: Q-learning, policy gradients

Key Concepts:
- Training Data: Dataset used to teach the algorithm
- Features: Individual measurable properties of observed phenomena
- Model: Mathematical representation learned from data
- Overfitting: Model performs well on training data but poorly on new data
- Cross-validation: Technique to assess model performance

Popular ML Libraries:
- Python: scikit-learn, TensorFlow, PyTorch, Keras
- R: caret, randomForest, glmnet
- Java: Weka, Apache Spark MLlib
- JavaScript: TensorFlow.js, ML5.js

Best Practices:
1. Data quality is crucial - clean, relevant, and sufficient data
2. Feature engineering can significantly impact performance
3. Regular model evaluation and validation
4. Consider computational costs and deployment requirements
5. Monitor for bias and fairness in model predictions
                """
            },
            {
                "filename": "deep_learning_guide.txt",
                "content": """
Deep Learning Comprehensive Guide

Deep Learning is a specialized subset of machine learning that uses artificial neural networks with multiple layers to model and understand complex patterns in data. It has revolutionized many fields including computer vision, natural language processing, and speech recognition.

Neural Network Architecture:

1. Perceptron: Basic building block
   - Input layer, weights, bias, activation function
   - Single layer can only solve linearly separable problems

2. Multi-layer Perceptron (MLP):
   - Multiple hidden layers
   - Can approximate any continuous function
   - Backpropagation for training

3. Convolutional Neural Networks (CNNs):
   - Specialized for image processing
   - Convolution layers, pooling layers
   - Applications: Image classification, object detection

4. Recurrent Neural Networks (RNNs):
   - Designed for sequential data
   - Memory capabilities through hidden states
   - Variants: LSTM, GRU
   - Applications: Language modeling, time series

5. Transformer Architecture:
   - Attention mechanisms
   - Parallel processing capabilities
   - State-of-the-art in NLP
   - Applications: GPT, BERT, machine translation

Training Deep Networks:

Challenges:
- Vanishing/exploding gradients
- Overfitting with large parameter spaces
- Computational requirements
- Data requirements

Solutions:
- Proper weight initialization
- Batch normalization
- Dropout and regularization
- Learning rate scheduling
- Transfer learning

Popular Frameworks:
- TensorFlow/Keras: Google's comprehensive platform
- PyTorch: Facebook's research-friendly framework
- JAX: Google's high-performance computing
- Caffe: Berkeley's CNN framework

Applications:
1. Computer Vision: Image classification, object detection, facial recognition
2. Natural Language Processing: Translation, sentiment analysis, chatbots
3. Speech Processing: Speech recognition, text-to-speech
4. Healthcare: Medical imaging, drug discovery
5. Autonomous Systems: Self-driving cars, drones
6. Gaming: AlphaGo, game AI

Future Directions:
- Efficient architectures (MobileNets, EfficientNets)
- Few-shot and zero-shot learning
- Federated learning
- Neuromorphic computing
- Quantum machine learning
                """
            }
        ]
        
        # Create data directory
        data_path = Path(self.data_dir)
        data_path.mkdir(parents=True, exist_ok=True)
        
        # Write sample documents
        for doc in sample_docs:
            file_path = data_path / doc["filename"]
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(doc["content"])
        
        self.logger.info(f"Created {len(sample_docs)} sample documents")
    
    def run_implementation_benchmark(self, implementation_name: str, vector_store: str, llm_provider: str, documents: List[Dict[str, str]], rebuild: bool = True, num_queries: int = None, force_delete: bool = False) -> Dict[str, Any]:
        """Run benchmark for a specific implementation"""
        self.logger.info(f"Benchmarking {implementation_name} with {vector_store} and {llm_provider}")
        
        try:
            # Initialize implementation
            implementation_class = self.implementations[implementation_name]
            rag_system = implementation_class(
                vector_store_type=vector_store,
                llm_provider=llm_provider
            )
            
            start_time = time.time()
            
            if rebuild:
                if force_delete:
                    # Destructive cleanup - actually delete files on disk
                    self.logger.warning(f"Force deleting vector stores for {implementation_name}")
                    if hasattr(rag_system, 'cleanup_storage_destructive'):
                        rag_system.cleanup_storage_destructive()
                    else:
                        # Fallback to regular cleanup for implementations that don't have destructive method
                        rag_system.cleanup_storage()
                
                # NOTE: For regular rebuild (not force_delete), we intentionally do not delete 
                # persistent vector store files on disk (to avoid file-lock issues on Windows). 
                # The implementations' cleanup_storage() methods are now non-destructive
                # and we rely on create_* methods to overwrite/persist new data.

                # Process documents and create index (rebuild by overwriting)
                if implementation_name == "manual":
                    rag_system.process_documents(documents)
                    rag_system.create_vector_index()
                elif implementation_name == "langchain":
                    processed_docs = rag_system.process_documents(documents)
                    rag_system.create_vector_store(processed_docs)
                    rag_system.setup_retrieval_chain()
                elif implementation_name == "llamaindex":
                    processed_docs = rag_system.process_documents(documents)
                    rag_system.create_index(processed_docs)
                    rag_system.setup_query_engine()
            else:
                # Load existing index
                if implementation_name == "manual":
                    rag_system.load_existing_index()
                elif implementation_name == "langchain":
                    rag_system.load_existing_vector_store()
                    rag_system.setup_retrieval_chain()
                elif implementation_name == "llamaindex":
                    rag_system.load_existing_index()
                    rag_system.setup_query_engine()
            
            setup_time = time.time() - start_time
            
            # Run benchmark with specified number of queries
            test_queries = Config.TEST_QUERIES
            if num_queries is not None:
                test_queries = test_queries[:num_queries]
                
            results = rag_system.run_benchmark(test_queries, save_results=True, num_queries=num_queries)
            results["setup_time"] = setup_time
            
            self.logger.info(f"Completed benchmark for {implementation_name}")
            return results
            
        except Exception as e:
            self.logger.error(f"Error benchmarking {implementation_name}: {e}")
            return {
                "method": implementation_name,
                "vector_store": vector_store,
                "llm_provider": llm_provider,
                "error": str(e),
                "queries": [],
                "performance": {}
            }
    
    def run_comprehensive_benchmark(self, vector_stores: List[str] = None, llm_providers: List[str] = None, rebuild: bool = True, num_queries: int = None, force_delete: bool = False) -> Dict[str, Any]:
        """Run comprehensive benchmark across all implementations"""
        self.logger.info("Starting comprehensive benchmark")
        
        if vector_stores is None:
            vector_stores = ["faiss", "chroma"]
        if llm_providers is None:
            llm_providers = ["openai"]  # Start with OpenAI only for stability
            
        # Use specified number of queries or default
        if num_queries is None:
            num_queries = Config.DEFAULT_NUM_QUERIES
            llm_providers = ["openai"]  # Start with OpenAI only for stability
        
        # Prepare test data
        documents = self.prepare_test_data()
        
        all_results = {
            "benchmark_timestamp": time.time(),
            "test_queries": Config.TEST_QUERIES[:num_queries],
            "num_queries": num_queries,
            "configurations": [],
            "summary": {}
        }
        
        # Run benchmarks for each combination
        for impl_name in self.implementations.keys():
            for vector_store in vector_stores:
                for llm_provider in llm_providers:
                    config_name = f"{impl_name}_{vector_store}_{llm_provider}"
                    self.logger.info(f"Running configuration: {config_name}")
                    
                    result = self.run_implementation_benchmark(
                        impl_name, vector_store, llm_provider, documents, rebuild, num_queries, force_delete
                    )
                    
                    all_results["configurations"].append(result)
        
        # Save comprehensive results
        results_path = f"{Config.RESULTS_DIR}/comprehensive_benchmark.json"
        Path(results_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(results_path, 'w') as f:
            json.dump(all_results, f, indent=2)
        
        self.logger.info("Comprehensive benchmark completed")
        return all_results
    
    def generate_comparison_report(self, results: Dict[str, Any] = None) -> str:
        """Generate comprehensive comparison report"""
        if results is None:
            # Load latest results
            results_path = f"{Config.RESULTS_DIR}/comprehensive_benchmark.json"
            if Path(results_path).exists():
                with open(results_path, 'r') as f:
                    results = json.load(f)
            else:
                raise FileNotFoundError("No benchmark results found")
        
        report = []
        
        # Header and metadata
        report.append("# 🔍 Comprehensive RAG Pipeline Comparison Report\n")
        report.append(f"**Generated on**: {time.ctime()}\n")
        report.append(f"**Version**: 1.0\n")
        report.append(f"**Document Corpus**: {len(results.get('metadata', {}).get('documents', []))} documents\n")
        report.append(f"**Test Queries**: {len(results.get('metadata', {}).get('test_queries', []))} queries\n\n")
        
        # Table of Contents
        report.append("## 📋 Table of Contents\n")
        report.append("1. [Executive Summary](#executive-summary)\n")
        report.append("2. [Performance Overview](#performance-overview)\n")
        report.append("3. [Quality Metrics Analysis](#quality-metrics-analysis)\n")
        report.append("4. [Technical Architecture Comparison](#technical-architecture-comparison)\n")
        report.append("5. [Detailed Performance Breakdown](#detailed-performance-breakdown)\n")
        report.append("6. [Query-by-Query Analysis](#query-by-query-analysis)\n")
        report.append("7. [Resource Utilization](#resource-utilization)\n")
        report.append("8. [Error Analysis](#error-analysis)\n")
        report.append("9. [Cost Analysis](#cost-analysis)\n")
        report.append("10. [Recommendations Matrix](#recommendations-matrix)\n")
        report.append("11. [Implementation Guide](#implementation-guide)\n\n")
        
        # Executive Summary with insights
        report.append("## 📊 Executive Summary\n")
        report.append("This comprehensive report analyzes three distinct approaches to building RAG (Retrieval-Augmented Generation) pipelines:\n\n")
        
        # Analyze configurations to provide insights
        configs = results.get("configurations", [])
        successful_configs = [c for c in configs if "error" not in c]
        
        if successful_configs:
            # Find best performers
            best_memory = min(successful_configs, key=lambda x: x.get("performance", {}).get("memory_usage", float('inf')))
            best_relevance = max(successful_configs, key=lambda x: x.get("performance", {}).get("relevance", 0))
            best_answer_quality = max(successful_configs, key=lambda x: x.get("performance", {}).get("answer_quality", 0))
            
            report.append("### 🏆 Key Findings\n")
            report.append(f"- **Most Memory Efficient**: {best_memory['method'].title()} ({best_memory['vector_store']}) - {best_memory.get('performance', {}).get('memory_usage', 0):.0f}MB\n")
            report.append(f"- **Best Relevance (LLM)**: {best_relevance['method'].title()} ({best_relevance['vector_store']}) - {best_relevance.get('performance', {}).get('relevance', 0):.3f}\n")
            report.append(f"- **Best Answer Quality**: {best_answer_quality['method'].title()} ({best_answer_quality['vector_store']}) - {best_answer_quality.get('performance', {}).get('answer_quality', 0):.3f}\n\n")
        
        report.append("### 🎯 Implementation Approaches\n")
        report.append("| Approach | Philosophy | Strengths | Best Use Cases |\n")
        report.append("|----------|------------|-----------|----------------|\n")
        report.append("| **LangChain** | High-level abstraction | Rapid development, extensive integrations | Prototyping, complex workflows |\n")
        report.append("| **LlamaIndex** | Data-centric design | Advanced indexing, Python-native | Data applications, custom indexing |\n")
        report.append("| **Manual** | Full control | Performance optimization, minimal deps | Production systems, educational |\n\n")
        
        # Performance Overview with detailed table
        report.append("## ⚡ Performance Overview\n")
        report.append("### Performance Metrics\n")
        report.append("| Implementation | Vector Store | Setup (s) | Vector Processing (s) | Retrieval (s) | Generation (s) | Process Memory (MB) |\n")
        report.append("|---------------|--------------|-----------|----------------------|---------------|----------------|-----------------|\n")
        
        for config in successful_configs:
            perf = config.get("performance", {})
            # Fix missing values with proper fallbacks
            memory_usage = perf.get('memory_usage', 0) or 0
            setup_time = config.get('setup_time', 0) or 0
            vector_processing_time = perf.get('vector_processing_time', 0) or 0
            retrieval_time = perf.get('retrieval_time', 0) or 0
            generation_time = perf.get('generation_time', 0) or 0
            
            # Mark missing or zero values as 'X' for clarity
            memory_usage_str = f"{memory_usage:.0f}" if memory_usage > 0 else "X"
            setup_time_str = f"{setup_time:.2f}" if setup_time > 0 else "X"
            vector_processing_time_str = f"{vector_processing_time:.3f}" if vector_processing_time > 0 else "X"
            retrieval_time_str = f"{retrieval_time:.3f}" if retrieval_time > 0 else "X"
            generation_time_str = f"{generation_time:.3f}" if generation_time > 0 else "X"
            
            report.append(f"| **{config['method'].title()}** | {config['vector_store']} | "
                         f"{setup_time_str} | {vector_processing_time_str} | "
                         f"{retrieval_time_str} | {generation_time_str} | {memory_usage_str} |\n")
        
        report.append("\n")
        report.append("**Metrics Explanation:**\n")
        report.append("- **Setup**: Time to initialize components and load models\n")
        report.append("- **Vector Processing**: Combined embedding generation + vector index creation time\n")
        report.append("- **Retrieval**: Time to query vector store and retrieve relevant documents\n")
        report.append("- **Generation**: Time for LLM to generate the final answer\n")
        report.append("- **Process Memory**: Total Python process memory (RSS) including models, data, and runtime\n\n")
        
        # Quality Metrics Analysis
        report.append("## 🎯 Quality Metrics Analysis\n")
        
        # Add detailed quality tables for each implementation
        report.append("### Detailed Quality Results by Implementation\n")
        
        # Group configurations by implementation
        impl_configs = {}
        for config in successful_configs:
            impl_name = config['method']
            if impl_name not in impl_configs:
                impl_configs[impl_name] = []
            impl_configs[impl_name].append(config)
        
        # Generate detailed tables for each implementation
        for impl_name, configs in impl_configs.items():
            report.append(f"#### {impl_name.title()} Implementation Results\n")
            report.append("| Vector Store | Query | Relevance (LLM) | Answer Quality | Response Time (s) |\n")
            report.append("|--------------|-------|-----------------|----------------|------------------|\n")
            
            for config in configs:
                vector_store = config['vector_store']
                queries = config.get('queries', [])
                
                for i, query_result in enumerate(queries[:10]):  # Show first 10 queries
                    query_text = query_result.get('query', f'Query {i+1}')[:50] + "..." if len(query_result.get('query', '')) > 50 else query_result.get('query', f'Query {i+1}')
                    evaluation = query_result.get('evaluation', {})
                    relevance = evaluation.get('relevance', 0)
                    answer_qual = evaluation.get('answer_quality', 0)
                    query_time = query_result.get('query_time', 0)
                    
                    # Mark missing values as 'X'
                    relevance_str = f"{relevance:.3f}" if relevance > 0 else "X"
                    answer_qual_str = f"{answer_qual:.3f}" if answer_qual > 0 else "X"
                    query_time_str = f"{query_time:.3f}" if query_time > 0 else "X"
                    
                    report.append(f"| {vector_store} | {query_text} | {relevance_str} | {answer_qual_str} | {query_time_str} |\n")
            
            report.append("\n")
        
        # Summary quality table
        report.append("### Overall Quality Summary\n")
        report.append("| Implementation | Vector Store | Relevance (LLM) | Answer Quality | Combined Score |\n")
        report.append("|---------------|--------------|-----------------|----------------|----------------|\n")

        for config in successful_configs:
            perf = config.get("performance", {})
            # Handle both old and new field names for backward compatibility
            relevance = perf.get("relevance", perf.get("retrieval_accuracy", 0))
            answer_qual = perf.get("answer_quality", 0)
            combined = (relevance + answer_qual) / 2 if relevance > 0 and answer_qual > 0 else 0

            # Mark missing values as 'X'
            relevance_str = f"{relevance:.3f}" if relevance > 0 else "X"
            answer_qual_str = f"{answer_qual:.3f}" if answer_qual > 0 else "X"
            combined_str = f"{combined:.3f}" if combined > 0 else "X"

            report.append(f"| **{config['method'].title()}** | {config['vector_store']} | "
                         f"{relevance_str} | {answer_qual_str} | {combined_str} |\n")
        
        report.append("\n### Quality Insights\n")
        
        # Analyze quality patterns
        quality_analysis = {}
        for config in successful_configs:
            method = config['method']
            if method not in quality_analysis:
                quality_analysis[method] = {'relevance': [], 'answer': []}
            perf = config.get("performance", {})
            # Handle both old and new field names for backward compatibility
            quality_analysis[method]['relevance'].append(perf.get("relevance", perf.get("retrieval_accuracy", 0)))
            quality_analysis[method]['answer'].append(perf.get("answer_quality", 0))

        for method, scores in quality_analysis.items():
            avg_relevance = sum(scores['relevance']) / len(scores['relevance']) if scores['relevance'] else 0
            avg_answer = sum(scores['answer']) / len(scores['answer']) if scores['answer'] else 0
            report.append(f"- **{method.title()}**: Avg Relevance = {avg_relevance:.3f}, Avg Answer Quality = {avg_answer:.3f}\n")
        
        report.append("\n")
        
        # Technical Architecture Comparison
        report.append("## 🏗️ Technical Architecture Comparison\n")
        report.append("### Framework Dependencies and Complexity\n")
        report.append("| Aspect | LangChain | LlamaIndex | Manual |\n")
        report.append("|--------|-----------|------------|--------|\n")
        report.append("| **Dependencies** | High (langchain-community, etc.) | Medium (llama-index-core) | Low (sentence-transformers, faiss) |\n")
        report.append("| **Setup Complexity** | Medium | Medium | High |\n")
        report.append("| **Customization** | High | High | Maximum |\n")
        report.append("| **Learning Curve** | Medium | Medium | High |\n")
        report.append("| **Production Ready** | Yes | Yes | Requires work |\n")
        report.append("| **Documentation** | Extensive | Good | N/A |\n")
        report.append("| **Community Support** | Large | Growing | N/A |\n\n")
        
        # Detailed Performance Breakdown
        report.append("## 📈 Detailed Performance Breakdown\n")
        
        for config in successful_configs:
            method = config['method']
            vs = config['vector_store']
            llm = config['llm_provider']
            perf = config.get("performance", {})
            
            report.append(f"### {method.title()} + {vs.upper()} + {llm.upper()}\n")
            
            # Performance metrics
            report.append("#### ⏱️ Timing Breakdown\n")
            total_time = perf.get('total_time', 0)
            setup_time = config.get('setup_time', 0)
            embedding_time = perf.get('embedding_time', 0)
            indexing_time = perf.get('indexing_time', 0)
            retrieval_time = perf.get('retrieval_time', 0)
            generation_time = perf.get('generation_time', 0)
            
            # Calculate percentages
            if total_time > 0:
                setup_pct = (setup_time / total_time) * 100
                embedding_pct = (embedding_time / total_time) * 100
                indexing_pct = (indexing_time / total_time) * 100
                retrieval_pct = (retrieval_time / total_time) * 100
                generation_pct = (generation_time / total_time) * 100
                
                report.append(f"- **Setup**: {setup_time:.3f}s ({setup_pct:.1f}%)\n")
                report.append(f"- **Embedding**: {embedding_time:.3f}s ({embedding_pct:.1f}%)\n")
                report.append(f"- **Indexing**: {indexing_time:.3f}s ({indexing_pct:.1f}%)\n")
                report.append(f"- **Retrieval**: {retrieval_time:.3f}s ({retrieval_pct:.1f}%)\n")
                report.append(f"- **Generation**: {generation_time:.3f}s ({generation_pct:.1f}%)\n")
            
            report.append(f"\n#### 💾 Resource Utilization\n")
            report.append(f"- **Peak Memory**: {perf.get('memory_usage', 0):.2f} MB\n")
            report.append(f"- **Memory Efficiency**: {(perf.get('memory_usage', 0)/1024):.2f} GB\n")
            
            # Quality metrics
            report.append(f"\n#### 🎯 Quality Assessment\n")
            # Handle both old and new field names for backward compatibility
            relevance = perf.get('relevance', perf.get('retrieval_accuracy', 0))
            answer_quality = perf.get('answer_quality', 0)
            overall_score = (relevance + answer_quality) / 2
            report.append(f"- **Relevance (LLM)**: {relevance:.3f}\n")
            report.append(f"- **Answer Quality**: {answer_quality:.3f}\n")
            report.append(f"- **Overall Score**: {overall_score:.3f}\n")
            
            report.append("\n")
        
        # Query-by-Query Analysis
        report.append("## 🔍 Query-by-Query Analysis\n")
        
        test_queries = results.get('metadata', {}).get('test_queries', [])
        if test_queries:
            report.append("### Individual Query Performance\n")
            
            for i, query in enumerate(test_queries):
                report.append(f"#### Query {i+1}: \"{query}\"\n")
                report.append("| Implementation | Vector Store | Response Time (s) | Answer Length | Quality Score |\n")
                report.append("|---------------|--------------|-------------------|---------------|---------------|\n")
                
                for config in successful_configs:
                    queries = config.get("queries", [])
                    if i < len(queries):
                        query_result = queries[i]
                        answer_length = len(query_result.get('response', {}).get('answer', ''))
                        quality = "N/A"  # Could be calculated if we have per-query quality scores
                        
                        report.append(f"| {config['method'].title()} | {config['vector_store']} | "
                                     f"{query_result.get('query_time', 0):.3f} | {answer_length} chars | {quality} |\n")
                
                report.append("\n")
        
        # Resource Utilization
        report.append("## 💻 Resource Utilization\n")
        report.append("### Memory Usage Patterns\n")
        
        memory_data = {}
        for config in successful_configs:
            key = f"{config['method']}-{config['vector_store']}"
            memory_data[key] = config.get("performance", {}).get("memory_usage", 0)
        
        sorted_memory = sorted(memory_data.items(), key=lambda x: x[1])
        
        report.append("| Rank | Configuration | Memory Usage (MB) | Efficiency Rating |\n")
        report.append("|------|---------------|-------------------|-------------------|\n")
        
        for i, (config, memory) in enumerate(sorted_memory):
            efficiency = "🟢 Excellent" if memory < 1200 else "🟡 Good" if memory < 1400 else "🔴 High"
            report.append(f"| {i+1} | {config} | {memory:.2f} | {efficiency} |\n")
        
        report.append("\n")
        
        # Error Analysis
        error_configs = [c for c in configs if "error" in c]
        if error_configs:
            report.append("## ⚠️ Error Analysis\n")
            report.append("### Failed Configurations\n")
            
            for config in error_configs:
                report.append(f"#### {config['method'].title()} - {config.get('vector_store', 'N/A')} - {config.get('llm_provider', 'N/A')}\n")
                report.append(f"**Error**: {config['error']}\n")
                report.append("**Potential Solutions**:\n")
                
                # Provide specific solutions based on error patterns
                error_msg = str(config['error']).lower()
                if "import" in error_msg or "module" in error_msg:
                    report.append("- Install missing dependencies\n")
                    report.append("- Check package versions compatibility\n")
                elif "api" in error_msg or "key" in error_msg:
                    report.append("- Verify API keys are set correctly\n")
                    report.append("- Check network connectivity\n")
                elif "memory" in error_msg or "out of" in error_msg:
                    report.append("- Reduce batch sizes\n")
                    report.append("- Use lighter embedding models\n")
                else:
                    report.append("- Check configuration parameters\n")
                    report.append("- Review system requirements\n")
                
                report.append("\n")
        
        # Cost Analysis
        report.append("## 💰 Cost Analysis\n")
        report.append("### Development and Operational Costs\n")
        report.append("| Factor | LangChain | LlamaIndex | Manual |\n")
        report.append("|--------|-----------|------------|--------|\n")
        report.append("| **Development Time** | Low (1-2 days) | Low (1-2 days) | High (1-2 weeks) |\n")
        report.append("| **Learning Curve** | Medium | Medium | High |\n")
        report.append("| **Maintenance** | Low | Low | High |\n")
        report.append("| **Performance Tuning** | Medium | Medium | High Control |\n")
        report.append("| **Debugging Complexity** | Medium | Medium | High |\n")
        report.append("| **Team Onboarding** | Easy | Easy | Difficult |\n\n")
        
        # Recommendations Matrix
        report.append("## 🎯 Recommendations Matrix\n")
        report.append("### Use Case Recommendations\n")
        report.append("| Scenario | Recommended Approach | Reasoning |\n")
        report.append("|----------|---------------------|----------|\n")
        report.append("| **Rapid Prototyping** | LangChain | Quick setup, extensive docs |\n")
        report.append("| **Production System** | Manual/LlamaIndex | Better performance control |\n")
        report.append("| **Research/Education** | Manual | Understanding internals |\n")
        report.append("| **Enterprise Integration** | LangChain | Mature ecosystem |\n")
        report.append("| **Data-Heavy Applications** | LlamaIndex | Advanced indexing features |\n")
        report.append("| **Performance Critical** | Manual | Maximum optimization |\n")
        report.append("| **Limited Resources** | Manual | Minimal dependencies |\n")
        report.append("| **Complex Workflows** | LangChain | Rich integration options |\n\n")
        
        # Implementation Guide
        report.append("## 🛠️ Implementation Guide\n")
        report.append("### Quick Start Complexity Assessment\n")
        report.append("#### LangChain Implementation\n")
        report.append("**Complexity**: ⭐⭐⭐ (Medium)\n")
        report.append("```python\n")
        report.append("# Typical setup - ~20 lines of code\n")
        report.append("from langchain.vectorstores import FAISS\n")
        report.append("from langchain.embeddings import HuggingFaceEmbeddings\n")
        report.append("# ... implementation\n")
        report.append("```\n\n")
        
        report.append("#### LlamaIndex Implementation\n")
        report.append("**Complexity**: ⭐⭐⭐ (Medium)\n")
        report.append("```python\n")
        report.append("# Typical setup - ~25 lines of code\n")
        report.append("from llama_index.core import VectorStoreIndex\n")
        report.append("from llama_index.core import Settings\n")
        report.append("# ... implementation\n")
        report.append("```\n\n")
        
        report.append("#### Manual Implementation\n")
        report.append("**Complexity**: ⭐⭐⭐⭐⭐ (High)\n")
        report.append("```python\n")
        report.append("# Typical setup - ~100+ lines of code\n")
        report.append("# Full control over embedding, chunking, retrieval\n")
        report.append("# Custom similarity functions, reranking, etc.\n")
        report.append("```\n\n")
        
        # Performance Summary
        if successful_configs:
            report.append("## 📊 Performance Summary\n")
            
            # Calculate averages by method
            method_stats = {}
            for config in successful_configs:
                method = config['method']
                if method not in method_stats:
                    method_stats[method] = {'times': [], 'memory': [], 'relevance': [], 'quality': []}
                
                perf = config.get("performance", {})
                method_stats[method]['times'].append(perf.get('total_time', 0))
                method_stats[method]['memory'].append(perf.get('memory_usage', 0))
                method_stats[method]['relevance'].append(perf.get('relevance', 0))
                method_stats[method]['quality'].append(perf.get('answer_quality', 0))
            
            report.append("### Average Performance by Method\n")
            report.append("| Method | Avg Time (s) | Avg Memory (MB) | Avg Relevance (LLM) | Avg Answer Quality |\n")
            report.append("|--------|--------------|-----------------|---------------------|--------------------|\n")
            
            for method, stats in method_stats.items():
                avg_time = sum(stats['times']) / len(stats['times']) if stats['times'] else 0
                avg_memory = sum(stats['memory']) / len(stats['memory']) if stats['memory'] else 0
                avg_relevance = sum(stats['relevance']) / len(stats['relevance']) if stats['relevance'] else 0
                avg_quality = sum(stats['quality']) / len(stats['quality']) if stats['quality'] else 0
                
                report.append(f"| **{method.title()}** | {avg_time:.2f} | {avg_memory:.1f} | {avg_relevance:.3f} | {avg_quality:.3f} |\n")
            
            report.append("\n")
        
        # Conclusion
        report.append("## 🏁 Conclusion\n")
        report.append("This comprehensive analysis provides detailed insights into three different RAG implementation approaches. ")
        report.append("The choice between them should be based on your specific requirements:\n\n")
        report.append("- **For rapid development**: Choose LangChain\n")
        report.append("- **For data-centric applications**: Choose LlamaIndex\n")
        report.append("- **For maximum control and performance**: Choose Manual implementation\n\n")
        report.append("Each approach has its trade-offs between development speed, performance, and complexity. ")
        report.append("Consider your team's expertise, project timeline, and performance requirements when making your decision.\n\n")
        
        # Footer
        report.append("---\n")
        report.append("*This report was automatically generated by the RAG Benchmark Runner. ")
        report.append("For questions or improvements, please check the project documentation.*\n")
        
        # Save report
        report_text = "".join(report)
        report_path = f"{Config.RESULTS_DIR}/comparison_report.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        self.logger.info(f"Enhanced comparison report saved to {report_path}")
        return report_text
    
    def _collect_analysis_data(self) -> Dict[str, Any]:
        """Collect all available data for LLM analysis"""
        data = {
            "benchmark_results": {},
            "detailed_results": {},
            "logs": {},
            "metrics": {},
            "configurations": {},
            "errors": []
        }
        
        # Collect benchmark results
        try:
            results_file = self.results_dir / "comprehensive_benchmark.json"
            if results_file.exists():
                with open(results_file, 'r') as f:
                    data["benchmark_results"] = json.load(f)
        except Exception as e:
            data["errors"].append(f"Error loading benchmark results: {e}")
        
        # Collect detailed results for each method
        methods_found = []
        for method in ["manual", "langchain", "llamaindex"]:
            method_data_found = False
            try:
                # Look for any results files for this method
                for vector_store in ["faiss", "chroma"]:
                    for llm in ["openai", "azure", "gemini", "ollama"]:
                        results_file = self.results_dir / f"{method}_{vector_store}_{llm}_results.json"
                        if results_file.exists():
                            with open(results_file, 'r') as f:
                                result_data = json.load(f)
                                
                                # Store detailed results
                                if method not in data["detailed_results"]:
                                    data["detailed_results"][method] = {}
                                data["detailed_results"][method][f"{vector_store}_{llm}"] = result_data
                                
                                # Extract metrics if available
                                if "performance" in result_data:
                                    if method not in data["metrics"]:
                                        data["metrics"][method] = {}
                                    data["metrics"][method][f"{vector_store}_{llm}"] = {
                                        "method": method,
                                        "metrics": result_data["performance"]
                                    }
                                
                                method_data_found = True
                        
                        # Check for log files
                        log_file = self.results_dir / f"{method}_{vector_store}_{llm}.log"
                        if log_file.exists():
                            try:
                                with open(log_file, 'r', encoding='utf-8') as f:
                                    if method not in data["logs"]:
                                        data["logs"][method] = {}
                                    data["logs"][method][f"{vector_store}_{llm}"] = f.read()
                            except Exception as log_error:
                                data["errors"].append(f"Error reading {method} log: {log_error}")
                
                if method_data_found:
                    methods_found.append(method)
                    
            except Exception as e:
                data["errors"].append(f"Error loading {method} data: {e}")
        
        # Log what we found
        self.logger.info(f"Found data for methods: {methods_found}")
        self.logger.info(f"Detailed results keys: {list(data['detailed_results'].keys())}")
        self.logger.info(f"Metrics keys: {list(data['metrics'].keys())}")
        
        return data
    
    def _generate_llm_analysis(self, data: Dict[str, Any]) -> str:
        """Generate comprehensive analysis using LLM"""
        try:
            # Import OpenAI or other LLM provider
            from openai import OpenAI
            
            # Initialize client with API key from config
            client = OpenAI(api_key=Config.LLM_CONFIGS["openai"].api_key)
            
            # Prepare the analysis prompt
            prompt = self._create_analysis_prompt(data)
            
            # Generate analysis
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Use a cost-effective model for analysis
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a senior AI/ML engineer with expertise in RAG systems, Vector Databases, and performance analysis. Provide detailed, technical analysis with actionable insights."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=4000,
                temperature=0
            )
            
            analysis = response.choices[0].message.content
            
            # Format the final report
            report = self._format_llm_report(analysis, data)
            return report
            
        except Exception as e:
            # Fallback to template-based report if LLM fails
            self.logger.error(f"LLM analysis failed: {e}")
            return self._generate_fallback_report(data)
    
    def _create_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Create comprehensive analysis prompt for LLM"""
        prompt_parts = []
        
        prompt_parts.append("""
# RAG Pipeline Benchmark Analysis Task

You are analyzing the performance of three different RAG (Retrieval-Augmented Generation) implementations:
1. **Manual RAG**: Custom implementation with full control
2. **LangChain**: High-level framework with abstractions  
3. **LlamaIndex**: Data-centric framework with advanced indexing

## Data Provided:
""")
        
        # Add benchmark results summary
        if data.get("benchmark_results"):
            prompt_parts.append("### Benchmark Results Summary:")
            prompt_parts.append(json.dumps(data["benchmark_results"], indent=2))
            prompt_parts.append("\n")
        
        # Add performance metrics
        if data.get("metrics"):
            prompt_parts.append("### Performance Metrics by Method:")
            for method, metrics in data["metrics"].items():
                prompt_parts.append(f"\n**{method.upper()}:**")
                prompt_parts.append(json.dumps(metrics, indent=2))
            prompt_parts.append("\n")
        
        # Add detailed results sample
        if data.get("detailed_results"):
            prompt_parts.append("### Sample Query Results:")
            for method, results in data["detailed_results"].items():
                if "queries" in results and results["queries"]:
                    sample_query = results["queries"][0]
                    prompt_parts.append(f"\n**{method.upper()} Sample:**")
                    prompt_parts.append(json.dumps(sample_query, indent=2))
            prompt_parts.append("\n")
        
        # Add error information
        if data.get("errors"):
            prompt_parts.append("### Errors Encountered:")
            for error in data["errors"]:
                prompt_parts.append(f"- {error}")
            prompt_parts.append("\n")
        
        # Add analysis requirements
        prompt_parts.append("""
## Analysis Requirements:

Please provide a comprehensive analysis covering:

### 1. Executive Summary (2-3 paragraphs)
- Overall performance comparison
- Key findings and surprising results
- Recommended use cases for each approach

### 2. Performance Analysis
- Speed comparison (setup, embedding, indexing, retrieval, generation)
- Memory usage analysis
- Scalability considerations
- Identify performance bottlenecks

### 3. Quality Assessment
- Retrieval accuracy comparison
- Answer quality evaluation
- Consistency across queries
- Failure modes and edge cases

### 4. Technical Implementation Analysis
- Code complexity and maintainability
- Dependency management
- Configuration flexibility
- Error handling and debugging

### 5. Resource Efficiency
- Memory usage patterns
- CPU utilization
- Disk I/O and storage requirements
- Cost implications

### 6. Practical Recommendations
- When to use each approach
- Performance optimization suggestions
- Common pitfalls to avoid
- Migration strategies

### 7. Future Considerations
- Scalability to larger datasets
- Integration with different LLM providers
- Monitoring and observability
- Maintenance overhead

Please be specific with numbers from the data and provide actionable insights. Format your response in Markdown with clear sections and subsections.
""")
        
        return "\n".join(prompt_parts)
    
    def _format_llm_report(self, analysis: str, data: Dict[str, Any]) -> str:
        """Format the LLM analysis into a complete report"""
        report_parts = []
        
        # Header
        report_parts.append("# 🤖 AI-Powered RAG Pipeline Analysis Report\n")
        report_parts.append(f"**Generated on**: {time.ctime()}\n")
        report_parts.append(f"**Analysis Engine**: GPT-4o-mini\n")
        report_parts.append(f"**Data Sources**: {len(data.get('metrics', {}))} implementations analyzed\n\n")
        
        # Add disclaimer
        report_parts.append("> 🔬 **Note**: This report was generated using AI analysis of benchmark results. ")
        report_parts.append("The insights combine quantitative metrics with qualitative assessment patterns.\n\n")
        
        # Add the LLM analysis
        report_parts.append(analysis)
        
        # Add appendix with raw data
        report_parts.append("\n\n---\n")
        report_parts.append("## 📊 Appendix: Raw Performance Data\n\n")
        
        if data.get("metrics"):
            report_parts.append("### Performance Metrics\n")
            report_parts.append("```json\n")
            report_parts.append(json.dumps(data["metrics"], indent=2))
            report_parts.append("\n```\n\n")
        
        if data.get("errors"):
            report_parts.append("### Errors Encountered\n")
            for error in data["errors"]:
                report_parts.append(f"- {error}\n")
            report_parts.append("\n")
        
        # Footer
        report_parts.append("---\n")
        report_parts.append("*This AI-powered analysis was generated by the RAG Benchmark Runner. ")
        report_parts.append("For questions or to reproduce results, please check the project documentation.*\n")
        
        return "".join(report_parts)
    
    def _generate_fallback_report(self, data: Dict[str, Any]) -> str:
        """Generate fallback report if LLM analysis fails"""
        report = []
        
        report.append("# 📊 RAG Pipeline Comparison Report (Fallback)\n")
        report.append(f"**Generated on**: {time.ctime()}\n")
        report.append("**Note**: LLM analysis unavailable, using template-based report\n\n")
        
        # Add basic metrics comparison
        if data.get("metrics"):
            report.append("## Performance Metrics Summary\n\n")
            report.append("| Method | Total Time (s) | Memory (MB) | Relevance (LLM) | Answer Quality |\n")
            report.append("|--------|---------------|-------------|-----------------|----------------|\n")
            
            for method, metrics in data["metrics"].items():
                perf = metrics.get("metrics", {})
                report.append(f"| {method.title()} | {perf.get('total_time', 0):.2f} | ")
                report.append(f"{perf.get('memory_usage', 0):.2f} | ")
                report.append(f"{perf.get('relevance', 0):.3f} | ")
                report.append(f"{perf.get('answer_quality', 0):.3f} |\n")
            
            report.append("\n")
        
        # Add error summary
        if data.get("errors"):
            report.append("## Issues Encountered\n\n")
            for error in data["errors"]:
                report.append(f"- {error}\n")
            report.append("\n")
        
        report.append("For detailed analysis, please resolve LLM configuration issues and regenerate the report.\n")
        
        return "".join(report)
    
    def generate_llm_powered_report(self):
        """Generate comprehensive LLM-powered analysis report"""
        self.logger.info("Generating LLM-powered analysis report")
        
        # Collect all available data
        analysis_data = self._collect_analysis_data()
        
        if not analysis_data.get("metrics") and not analysis_data.get("detailed_results") and not analysis_data.get("benchmark_results"):
            self.logger.error("No benchmark data found for analysis")
            print("❌ No benchmark data found. Please run benchmarks first.")
            return None
        
        # Generate LLM analysis
        try:
            report = self._generate_llm_analysis(analysis_data)
            
            # Save report
            report_file = self.results_dir / "ai_analysis_report.md"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            self.logger.info(f"AI analysis report saved to {report_file}")
            print(f"🤖 AI-powered analysis report generated: {report_file}")
            
            return str(report_file)
            
        except Exception as e:
            self.logger.error(f"Failed to generate LLM report: {e}")
            print(f"❌ Failed to generate AI report: {e}")
            return None

def main():
    """Main function for benchmark runner"""
    parser = argparse.ArgumentParser(description="RAG Benchmark Runner")
    parser.add_argument("--vector-stores", nargs="+", choices=["faiss", "chroma"], default=["faiss"])
    parser.add_argument("--llm-providers", nargs="+", choices=["openai", "azure", "gemini", "ollama"], default=["openai"])
    parser.add_argument("--data-dir", default="./data")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild all vector stores")
    parser.add_argument("--force-delete", action="store_true", help="Force destructive cleanup of vector stores (WARNING: deletes files on disk)")
    parser.add_argument("--report-only", action="store_true", help="Generate report from existing results")
    parser.add_argument("--ai-report", action="store_true", help="Generate AI-powered analysis report")
    parser.add_argument("--both-reports", action="store_true", help="Generate both template and AI reports")
    parser.add_argument("--num-queries", type=int, default=Config.DEFAULT_NUM_QUERIES, 
                        help=f"Number of test queries to run (default: {Config.DEFAULT_NUM_QUERIES})")
    
    args = parser.parse_args()
    
    # Safety check for force-delete on Windows
    if args.force_delete:
        import platform
        if platform.system() == "Windows":
            print("⚠️  WARNING: --force-delete will delete vector store files on disk.")
            print("   This may cause file lock errors on Windows if files are in use.")
            print("   Consider using regular --rebuild instead (non-destructive).")
            
        print("\n🚨 DESTRUCTIVE OPERATION CONFIRMED:")
        print("   This will permanently delete existing vector store files.")
        confirmation = input("   Type 'DELETE' to confirm: ")
        
        if confirmation != "DELETE":
            print("❌ Operation cancelled. Use --rebuild for safe non-destructive rebuilding.")
            return
        
        print("✅ Destructive cleanup confirmed. Proceeding...")
    
    # Initialize benchmark runner
    benchmark = RAGBenchmark(data_dir=args.data_dir)
    
    if args.report_only or (args.ai_report and not args.rebuild) or (args.both_reports and not args.rebuild):
        # Generate reports only (when not rebuilding)
        if args.ai_report:
            # Generate AI-powered report
            ai_report = benchmark.generate_llm_powered_report()
            if ai_report:
                print("🤖 AI-powered analysis report generated successfully!")
                print(f"AI Report saved to: {ai_report}")
            
        elif args.both_reports:
            # Generate both reports
            template_report = benchmark.generate_comparison_report()
            ai_report = benchmark.generate_llm_powered_report()
            
            print("📊 Both reports generated successfully!")
            print(f"Template report: {Config.RESULTS_DIR}/comparison_report.md")
            if ai_report:
                print(f"AI analysis report: {ai_report}")
            
        else:
            # Generate template report (default)
            report = benchmark.generate_comparison_report()
            print("📊 Template comparison report generated successfully!")
            print(f"Report saved to: {Config.RESULTS_DIR}/comparison_report.md")
    
    else:
        # Run comprehensive benchmark
        results = benchmark.run_comprehensive_benchmark(
            vector_stores=args.vector_stores,
            llm_providers=args.llm_providers,
            rebuild=args.rebuild,
            num_queries=args.num_queries,
            force_delete=args.force_delete
        )
        
        # Generate comparison report (template by default)
        report = benchmark.generate_comparison_report(results)
        
        print("✅ Benchmark completed successfully!")
        print(f"Results saved to: {Config.RESULTS_DIR}/comprehensive_benchmark.json")
        print(f"Template report: {Config.RESULTS_DIR}/comparison_report.md")
        
        # Optionally generate AI report if requested
        if args.ai_report or args.both_reports:
            ai_report = benchmark.generate_llm_powered_report()
            if ai_report:
                print(f"🤖 AI analysis report: {ai_report}")

if __name__ == "__main__":
    main()