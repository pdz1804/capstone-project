#!/usr/bin/env python3
"""
ColPali vs OCR Retrieval System
Compares three retrieval pipelines:
- Pipeline A: OCR + BM25
- Pipeline B: ColQwen (Multi-modal, image-based)
- Pipeline C: OCR + MiniLM-L6 (Dense retrieval)
"""

import sys
import os
import json
import re
import logging
import tempfile
import shutil
import pickle
import argparse
import base64
import io
from pathlib import Path
from typing import List, Dict, Any, Optional

# PDF and Image processing
from PIL import Image
from pdf2image import convert_from_path
import pytesseract

# ML and Retrieval
from rank_bm25 import BM25Okapi
import torch
from transformers import AutoModel, AutoTokenizer, AutoImageProcessor
from sentence_transformers import SentenceTransformer, util as st_util
from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor

# OpenAI for LLM
from openai import OpenAI

# Progress bar
from tqdm import tqdm

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration for the retrieval system"""
    def __init__(self, pdf_dir: str, output_dir: str, openai_api_key: Optional[str] = None):
        self.PDF_DIR = Path(pdf_dir)
        self.OUTPUT_DIR = Path(output_dir)
        
        # Create directories if they don't exist
        self.PDF_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Index paths
        self.OCR_DATA_PATH = self.OUTPUT_DIR / "ocr_data.json"
        self.BM25_INDEX_PATH = self.OUTPUT_DIR / "bm25_index.pkl"
        self.COLQWEN_INDEX_PATH = self.OUTPUT_DIR / "colqwen_index.pkl"
        self.MINILM_INDEX_PATH = self.OUTPUT_DIR / "minilm_index.pkl"
        
        # Device configuration
        self.DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # OpenAI API Key
        self.OPENAI_API_KEY = openai_api_key or os.getenv("OPENAI_API_KEY")
        
        logging.info(f"PDF Directory: {self.PDF_DIR}")
        logging.info(f"Output Directory: {self.OUTPUT_DIR}")
        logging.info(f"Device: {self.DEVICE}")


# ============================================================================
# OCR PROCESSOR
# ============================================================================

class SlideOCR:
    """Converts PDF -> Images -> Text (OCR)"""
    
    def __init__(self):
        logging.info("SlideOCR initialized.")
    
    def pdf_to_images(self, pdf_path: Path, temp_dir: Path) -> List[Path]:
        """Convert PDF to images"""
        try:
            images = convert_from_path(
                pdf_path,
                dpi=200,
                output_folder=str(temp_dir),
                fmt="png",
                thread_count=4,
            )
            return [Path(img.filename) for img in images]
        except Exception as e:
            logging.error(f"[SlideOCR] Error converting PDF {pdf_path}: {e}")
            return []
    
    def ocr_image(self, image_path: Path) -> str:
        """Perform OCR on an image"""
        try:
            img = Image.open(image_path)
            # Use both Vietnamese and English
            text = pytesseract.image_to_string(img, lang='vie+eng')
            return text
        except Exception as e:
            logging.error(f"[SlideOCR] Error OCR image {image_path}: {e}")
            return ""
    
    def process_slides(self, pdf_files: List[Path]) -> List[Dict[str, Any]]:
        """Process all PDF files and extract text via OCR"""
        all_ocr_data = []
        
        for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
            if not pdf_path.exists():
                logging.warning(f"[SlideOCR] File not found: {pdf_path}")
                continue
            
            with tempfile.TemporaryDirectory() as temp_dir:
                image_paths = self.pdf_to_images(pdf_path, Path(temp_dir))
                
                for i, img_path in enumerate(tqdm(image_paths, desc=f"OCR {pdf_path.name}", leave=False)):
                    page_num = i + 1
                    ocr_text = self.ocr_image(img_path)
                    
                    # Clean text
                    clean_text = re.sub(r'\n+', '\n', ocr_text).strip()
                    clean_text = re.sub(r'[ \t]+', ' ', clean_text)
                    
                    if clean_text:
                        all_ocr_data.append({
                            "source": pdf_path.name,
                            "page": page_num,
                            "text": clean_text
                        })
        
        return all_ocr_data


# ============================================================================
# PIPELINE A: BM25
# ============================================================================

class PipelineA_BM25:
    """OCR + BM25 retrieval"""
    
    def __init__(self, index_path: Path):
        self.bm25_index = None
        self.ocr_data = []
        self.index_path = index_path
    
    def _tokenize(self, text: str) -> List[str]:
        return text.lower().split()
    
    def build_index(self, ocr_data: List[Dict[str, Any]], force_rebuild: bool = False):
        """Build or load BM25 index"""
        if not force_rebuild and self.index_path.exists():
            logging.info(f"Pipeline A: Loading index from {self.index_path}...")
            with open(self.index_path, 'rb') as f:
                self.bm25_index, self.ocr_data = pickle.load(f)
            logging.info("Pipeline A: BM25 index loaded successfully.")
            return
        
        logging.info("Pipeline A: Building BM25 index...")
        self.ocr_data = ocr_data
        if not self.ocr_data:
            logging.error("Error (BM25): No OCR data to build index.")
            return
        
        tokenized_corpus = [self._tokenize(doc['text']) for doc in self.ocr_data]
        self.bm25_index = BM25Okapi(tokenized_corpus)
        
        with open(self.index_path, 'wb') as f:
            pickle.dump((self.bm25_index, self.ocr_data), f)
        logging.info(f"Pipeline A: BM25 index built and saved to {self.index_path}")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search using BM25"""
        if not self.bm25_index:
            if self.index_path.exists():
                with open(self.index_path, 'rb') as f:
                    self.bm25_index, self.ocr_data = pickle.load(f)
            else:
                logging.error("Error (BM25): Index not built. Please run build_index() first.")
                return []
        
        tokenized_query = self._tokenize(query)
        scores = self.bm25_index.get_scores(tokenized_query)
        top_n_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        results = []
        for i in top_n_indices:
            if scores[i] > 0:
                doc = self.ocr_data[i]
                results.append({
                    "source": doc['source'],
                    "page": doc['page'],
                    "score": scores[i],
                    "text_snippet": doc['text']
                })
        return results


# ============================================================================
# PIPELINE C: MiniLM
# ============================================================================

class PipelineC_MiniLM:
    """OCR + MiniLM-L6 dense retrieval"""
    
    def __init__(self, index_path: Path, device: torch.device):
        self.model = None
        self.index_path = index_path
        self.corpus_embeddings = None
        self.ocr_data = []
        self.device = device
    
    def _get_model(self):
        if self.model is None:
            logging.info("Pipeline C: Loading MiniLM-L6 model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2', device=self.device)
            logging.info("Pipeline C: MiniLM-L6 model loaded successfully.")
    
    def build_index(self, ocr_data: List[Dict[str, Any]], force_rebuild: bool = False):
        """Build or load MiniLM index"""
        if not force_rebuild and self.index_path.exists():
            logging.info(f"Pipeline C: Loading index from {self.index_path}...")
            with open(self.index_path, 'rb') as f:
                self.corpus_embeddings, self.ocr_data = pickle.load(f)
            self.corpus_embeddings = self.corpus_embeddings.to(self.device)
            logging.info("Pipeline C: MiniLM index loaded successfully.")
            return
        
        self._get_model()
        logging.info("Pipeline C: Building MiniLM index...")
        self.ocr_data = ocr_data
        if not self.ocr_data:
            logging.error("Error (MiniLM): No OCR data to build index.")
            return
        
        corpus = [doc['text'] for doc in self.ocr_data]
        logging.info(f"Embedding {len(corpus)} text pages...")
        self.corpus_embeddings = self.model.encode(
            corpus, convert_to_tensor=True, device=self.device, show_progress_bar=True
        )
        
        with open(self.index_path, 'wb') as f:
            pickle.dump((self.corpus_embeddings.cpu(), self.ocr_data), f)
        logging.info(f"Pipeline C: MiniLM index built and saved to {self.index_path}")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search using MiniLM"""
        self._get_model()
        if self.corpus_embeddings is None:
            if self.index_path.exists():
                with open(self.index_path, 'rb') as f:
                    self.corpus_embeddings, self.ocr_data = pickle.load(f)
                self.corpus_embeddings = self.corpus_embeddings.to(self.device)
            else:
                logging.error("Error (MiniLM): Index not built. Please run build_index() first.")
                return []
        
        query_embedding = self.model.encode(query, convert_to_tensor=True, device=self.device)
        cos_scores = st_util.pytorch_cos_sim(query_embedding, self.corpus_embeddings)[0]
        top_results = torch.topk(cos_scores, k=min(top_k, len(cos_scores)))
        
        results = []
        for score, idx in zip(top_results[0].cpu().tolist(), top_results[1].cpu().tolist()):
            if score > 0.1:
                doc = self.ocr_data[idx]
                results.append({
                    "source": doc['source'],
                    "page": doc['page'],
                    "score": score,
                    "text_snippet": doc['text']
                })
        return results


# ============================================================================
# PIPELINE B: ColQwen (Multi-modal)
# ============================================================================

class PipelineB_ColQwen:
    """ColQwen multi-modal retrieval (image-based)"""
    
    def __init__(self, index_path: Path, device: torch.device):
        self.processor = None
        self.model = None
        self.index_path = index_path
        self.colqwen_index = []
        self.device = device
    
    def _get_model(self):
        if self.model is None:
            logging.info("Pipeline B: Loading ColQwen 2.5 model...")
            model_name = 'vidore/colqwen2.5-v0.2'
            
            self.processor = ColQwen2_5_Processor.from_pretrained(model_name)
            self.model = ColQwen2_5.from_pretrained(
                model_name,
                torch_dtype=torch.bfloat16 if self.device.type == 'cuda' else torch.float32,
                device_map=self.device.type
            ).eval()
            logging.info("Pipeline B: ColQwen 2.5 model loaded successfully.")
    
    def build_index(self, pdf_dir: Path, force_rebuild: bool = False):
        """Build or load ColQwen index"""
        if not force_rebuild and self.index_path.exists():
            logging.info(f"Pipeline B: Loading index from {self.index_path}...")
            with open(self.index_path, 'rb') as f:
                self.colqwen_index = pickle.load(f)
            logging.info("Pipeline B: ColQwen index loaded successfully.")
            return
        
        self._get_model()
        logging.info("Pipeline B: Building ColQwen index...")
        
        pdf_files = list(pdf_dir.rglob("*.pdf"))
        if not pdf_files:
            logging.error("Error (ColQwen): No PDF files found.")
            return
        
        self.colqwen_index = []
        
        with torch.no_grad():
            for pdf_path in tqdm(pdf_files, desc="Processing PDFs (ColQwen)"):
                try:
                    images = convert_from_path(pdf_path, dpi=200)
                    for i, page_image in enumerate(tqdm(images, desc=f"Embed {pdf_path.name}", leave=False)):
                        page_num = i + 1
                        
                        # Process image
                        image_inputs = self.processor.process_images([page_image]).to(self.model.device)
                        
                        # Get embeddings
                        doc_outputs = self.model(**image_inputs)
                        
                        self.colqwen_index.append({
                            'source': pdf_path.name,
                            'page': page_num,
                            'embeddings': doc_outputs.cpu()
                        })
                
                except Exception as e:
                    logging.error(f"[ColQwen] Error processing {pdf_path}: {e}")
        
        if self.colqwen_index:
            with open(self.index_path, 'wb') as f:
                pickle.dump(self.colqwen_index, f)
            logging.info(f"Pipeline B: ColQwen index built and saved to {self.index_path}")
        else:
            logging.error("Pipeline B: No documents were embedded.")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search using ColQwen"""
        self._get_model()
        if not self.colqwen_index:
            if self.index_path.exists():
                with open(self.index_path, 'rb') as f:
                    self.colqwen_index = pickle.load(f)
            else:
                logging.error("Error (ColQwen): Index not built. Please run build_index() first.")
                return []
        
        # Embed query
        query_inputs = self.processor.process_queries([query]).to(self.model.device)
        with torch.no_grad():
            query_embeds = self.model(**query_inputs)
        
        page_scores = []
        
        # Score using ColBERT-style multi-vector scoring
        for doc in self.colqwen_index:
            doc_embeds = doc['embeddings'].to(self.model.device)
            score = self.processor.score_multi_vector(query_embeds, doc_embeds).item()
            page_scores.append(score)
        
        # Get top results
        top_n_indices = sorted(range(len(page_scores)), key=lambda i: page_scores[i], reverse=True)[:top_k]
        
        results = []
        for i in top_n_indices:
            doc_info = self.colqwen_index[i]
            results.append({
                "source": doc_info['source'],
                "page": doc_info['page'],
                "score": page_scores[i],
                "text_snippet": f"[ColQwen does not return text, only image page {doc_info['page']}]"
            })
        return results


# ============================================================================
# LLM INTEGRATION
# ============================================================================

def get_image_base64_from_pdf(pdf_dir: Path, pdf_filename: str, page_num: int) -> Optional[str]:
    """Load and convert a specific PDF page to Base64"""
    full_pdf_path = pdf_dir / pdf_filename
    if not full_pdf_path.exists():
        # Try to find it recursively
        candidates = list(pdf_dir.rglob(pdf_filename))
        if candidates:
            full_pdf_path = candidates[0]
        else:
            logging.error(f"PDF file not found: {full_pdf_path}")
            return None
    
    try:
        images = convert_from_path(
            str(full_pdf_path),
            first_page=page_num,
            last_page=page_num,
            dpi=150
        )
        if not images:
            return None
        
        img = images[0]
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    except Exception as e:
        logging.error(f"Error rendering page {page_num} of {pdf_filename}: {e}")
        return None


def get_llm_answer(
    query: str,
    retrieved_contexts: List[Dict[str, Any]],
    pipeline_type: str,
    client: Optional[OpenAI],
    pdf_dir: Path
) -> str:
    """
    Call GPT-4o Mini to generate answer, supports multi-modal for Pipeline B.
    pipeline_type: 'A', 'B', or 'C'
    """
    if client is None:
        return "(Error: OpenAI API Key not configured)"
    
    if not retrieved_contexts:
        return "(No context found to answer)"
    
    prompt_messages = [
        {
            "role": "system",
            "content": "You are a helpful AI assistant. Your task is to answer the user's question *only* based on the provided context (which may include text and/or images). The response must be written in the **same language** as the user's query. If the context does not contain the information, state clearly: 'Based on the context provided, I cannot find the information'. **IMPORTANT**: ONLY INFER FROM THE GIVEN RETRIEVED CONTEXTS REGARDLESS OF HOW NONSENSE IT IS FROM THE REAL LIFE OR KNOWLEDGE YOU HAVE KNOWN. DO NOT COME UP WITH EXTERNAL FACTS OR INFORMATION."
        }
    ]
    user_content = []
    text_context_for_llm = ""
    
    for i, ctx in enumerate(retrieved_contexts):
        source_info = f"Source: {ctx['source']}, Page: {ctx['page']}, Score: {ctx['score']:.4f}"
        
        if pipeline_type in ['A', 'C']:
            # Text-only pipelines
            snippet = ctx['text_snippet'][:1000] + "..."
            text_context_for_llm += f"--- Context {i+1} ({source_info}) ---\n"
            text_context_for_llm += f"Text Snippet:\n{snippet}\n\n"
        
        elif pipeline_type == 'B':
            # Multi-modal pipeline
            base64_image = get_image_base64_from_pdf(pdf_dir, ctx['source'], ctx['page'])
            if base64_image:
                user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})
                text_context_for_llm += f"Context {i+1}: Image is provided above. ({source_info})\n\n"
    
    # Final text prompt
    final_prompt = f"**Contexts from Retriever:**\n{text_context_for_llm}\n\n**Question:**\n{query}"
    
    # Insert text prompt at the beginning
    user_content.insert(0, {"type": "text", "text": final_prompt})
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": user_content}],
            temperature=0.1,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"(Error calling LLM: {str(e)})"


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def sanitize_filename(query: str) -> str:
    """Convert query to safe filename"""
    filename = re.sub(r'[^a-zA-Z0-9\s-]', '', query).lower()
    filename = re.sub(r'[_\s-]+', '_', filename).strip('_')
    return filename[:50]


def main():
    parser = argparse.ArgumentParser(description="ColPali vs OCR Retrieval System")
    parser.add_argument('--pdf_dir', type=str, required=True, help='Directory containing PDF files')
    parser.add_argument('--output_dir', type=str, required=True, help='Directory to save outputs and indexes')
    parser.add_argument('--openai_api_key', type=str, help='OpenAI API Key (or set OPENAI_API_KEY env var)')
    parser.add_argument('--force_rebuild_ocr', action='store_true', help='Force rebuild OCR data')
    parser.add_argument('--force_rebuild_indexes', action='store_true', help='Force rebuild all indexes')
    parser.add_argument('--query', type=str, action='append', help='Query to run (can specify multiple times)')
    parser.add_argument('--top_k', type=int, default=5, help='Number of results to retrieve')
    
    args = parser.parse_args()
    
    # Initialize configuration
    config = Config(args.pdf_dir, args.output_dir, args.openai_api_key)
    
    # Initialize OpenAI client
    client = None
    if config.OPENAI_API_KEY:
        client = OpenAI(api_key=config.OPENAI_API_KEY)
    else:
        logging.warning("OpenAI API Key not provided. LLM step will be skipped.")
    
    # ========================================================================
    # STEP 1: OCR Processing
    # ========================================================================
    
    ocr_data = []
    if not args.force_rebuild_ocr and config.OCR_DATA_PATH.exists():
        logging.info(f"Loading OCR data from {config.OCR_DATA_PATH}...")
        with open(config.OCR_DATA_PATH, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        logging.info(f"Loaded {len(ocr_data)} pages from OCR file.")
    else:
        logging.info("Starting OCR process (this may take time)...")
        ocr_processor = SlideOCR()
        pdf_files = list(config.PDF_DIR.rglob("*.pdf"))
        
        if not pdf_files:
            logging.error(f"No PDF files found in {config.PDF_DIR}")
            sys.exit(1)
        
        logging.info(f"Found {len(pdf_files)} PDF files. Starting processing...")
        ocr_data = ocr_processor.process_slides(pdf_files)
        
        # Save OCR data
        with open(config.OCR_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(ocr_data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"OCR complete! Processed {len(ocr_data)} pages with text.")
        logging.info(f"OCR data saved to {config.OCR_DATA_PATH}")
    
    if not ocr_data:
        logging.error("No OCR data available. Exiting.")
        sys.exit(1)
    
    # ========================================================================
    # STEP 2: Build/Load Indexes
    # ========================================================================
    
    logging.info("--- Building/Loading Indexes ---")
    
    p_a = PipelineA_BM25(config.BM25_INDEX_PATH)
    p_b = PipelineB_ColQwen(config.COLQWEN_INDEX_PATH, config.DEVICE)
    p_c = PipelineC_MiniLM(config.MINILM_INDEX_PATH, config.DEVICE)
    
    p_a.build_index(ocr_data, force_rebuild=args.force_rebuild_indexes)
    p_b.build_index(config.PDF_DIR, force_rebuild=args.force_rebuild_indexes)
    p_c.build_index(ocr_data, force_rebuild=args.force_rebuild_indexes)
    
    logging.info("ALL 3 INDEXES BUILT/LOADED SUCCESSFULLY.")
    
    # ========================================================================
    # STEP 3: Run Queries
    # ========================================================================
    
    if not args.query:
        logging.info("No queries specified. Use --query to run retrieval.")
        return
    
    for query in args.query:
        logging.info(f"\n{'='*80}")
        logging.info(f"Running query: '{query}'")
        logging.info(f"{'='*80}\n")
        
        # Create output file
        filename = sanitize_filename(query)
        output_path = config.OUTPUT_DIR / f"{filename}.md"
        markdown_content = f"# RAG Comparison Results for: '{query}'\n\n"
        
        # --- Pipeline A ---
        markdown_content += "\n# Pipeline A (OCR + BM25)\n"
        results_a = p_a.search(query, top_k=args.top_k)
        
        markdown_content += "## 🔍 Retrieved Contexts\n"
        for res in results_a:
            info = f"Source: {res['source']}, Page: {res['page']} (Score: {res['score']:.2f})\n"
            logging.info(info.strip())
            markdown_content += f"* {info} \n"
        
        llm_answer_a = get_llm_answer(query, results_a, 'A', client, config.PDF_DIR)
        markdown_content += "\n## 🤖 LLM Summary (Text-only):\n"
        markdown_content += f"> {llm_answer_a}\n"
        logging.info("Pipeline A complete.\n")
        
        # --- Pipeline B ---
        markdown_content += "\n# Pipeline B (ColQwen - Multi-modal)\n"
        results_b = p_b.search(query, top_k=args.top_k)
        
        markdown_content += "## 🔍 Retrieved Contexts\n"
        for res in results_b:
            info = f"Source: {res['source']}, Page: {res['page']} (Score: {res['score']:.4f})"
            logging.info(info)
            markdown_content += f"* {info} (Image sent to LLM)\n"
        
        llm_answer_b = get_llm_answer(query, results_b, 'B', client, config.PDF_DIR)
        markdown_content += "\n## 🤖 LLM Summary (Multi-modal):\n"
        markdown_content += f"> {llm_answer_b}\n"
        logging.info("Pipeline B complete.\n")
        
        # --- Pipeline C ---
        markdown_content += "\n# Pipeline C (OCR + MiniLM-L6)\n"
        results_c = p_c.search(query, top_k=args.top_k)
        
        markdown_content += "## 🔍 Retrieved Contexts\n"
        for res in results_c:
            info = f"Source: {res['source']}, Page: {res['page']} (Score: {res['score']:.4f})"
            logging.info(info)
            markdown_content += f"* {info} \n"
        
        llm_answer_c = get_llm_answer(query, results_c, 'C', client, config.PDF_DIR)
        markdown_content += "\n## 🤖 LLM Summary (Text-only):\n"
        markdown_content += f"> {llm_answer_c}\n"
        logging.info("Pipeline C complete.\n")
        
        # Save results
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logging.info(f"✨ Results saved to: {output_path}")
        logging.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()
