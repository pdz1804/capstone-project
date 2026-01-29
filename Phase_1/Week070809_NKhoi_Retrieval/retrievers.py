import time
import numpy as np
import random
import math
import json
import os
import gc
import argparse
import torch
import torch.nn.functional as F
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModelForCausalLM
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from datasets import load_dataset
from ragatouille import RAGPretrainedModel

# --- 0. DEVICE SELECTION ---
def get_device():
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        print("MPS device found. Using 'mps'.")
        return "mps"
    return "cpu"

DEVICE = get_device()
print(f"Using device: {DEVICE}")

# --- 1. UTILITY FUNCTIONS ---
base_path = "./ms_marco_val"  # Thay thế bằng đường dẫn thực tế của bạn

def load_jsonl(path):
    data = []
    print(f"Attempting to load JSONL file: {path}")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                try:
                    processed_line = line.strip()
                    if processed_line:
                        data.append(json.loads(processed_line))
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON on line {i+1} in {path}: {e}")
                    print(f"Problematic line content (first 100 chars): {line[:100]}...")
                    print("Skipping this problematic line.")
    except FileNotFoundError:
        print(f"ERROR: File not found at {path}")
        # Không raise nếu chạy local, giả định file sẽ được tạo ở bước convert_ms_marco hoặc đã có
    except Exception as e:
        print(f"An unexpected error occurred while loading {path}: {e}")
        raise
    print(f"Successfully loaded {len(data)} records from {path}")
    return data

def load_qrels(path):
    qrels = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                # MS MARCO format: qid iter docid rel
                parts = line.strip().split()
                if len(parts) < 4: continue # Bỏ qua dòng không hợp lệ
                qid, _, docid, rel = parts
                qrels.setdefault(qid, {})[docid] = int(rel)
    except FileNotFoundError:
        print(f"ERROR: Qrels file not found at {path}")
        # Không raise nếu chạy local
    return qrels

def save_jsonl(items, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for d in items:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

def save_qrels(qrels_list, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for qid, docid, rel in qrels_list:
            f.write(f"{qid}\t0\t{docid}\t{rel}\n")

def convert_ms_marco(split="validation", out_dir=os.path.join(base_path, "data/ms_marco_val")):
    ds = load_dataset("microsoft/ms_marco", 'v2.1', split=split)
    os.makedirs(out_dir, exist_ok=True)

    # Queries
    queries = [{"id": str(rec["query_id"]), "text": rec["query"]} for rec in ds]

    # Corpus & Qrels
    corpus_map = {}
    qrels = []

    for rec in ds:
        qid = str(rec["query_id"])
        passages = rec["passages"]
        texts = passages["passage_text"]
        selected = passages["is_selected"]

        for idx, text in enumerate(texts):
            if not text:
                continue
            doc_id = f"{qid}_{idx}"
            corpus_map[doc_id] = text
            if selected[idx] == 1:
                qrels.append((qid, doc_id, 1))

    corpus = [{"id": did, "text": txt} for did, txt in corpus_map.items()]

    # Save
    save_jsonl(corpus, os.path.join(out_dir, "corpus.jsonl"))
    save_jsonl(queries, os.path.join(out_dir, "queries.jsonl"))
    save_qrels(qrels, os.path.join(out_dir, "qrels.tsv"))

    print("Done convert MS MARCO split:", split)

# if exists the folder, skip
if not os.path.exists(os.path.join(base_path, "corpus.jsonl")):
    convert_ms_marco(split="validation", out_dir=base_path)

# --- 2. METRICS FUNCTIONS ---
def recall_at_k(run, qrels, k):
    relevant = {d for d, rel in qrels.items() if rel > 0}
    retrieved = {d for d, _ in run[:k]}
    if not relevant:
        return 0.0
    return len(relevant & retrieved) / len(relevant)

def dcg_at_k(run, qrels, k):
    return sum(
        (2**qrels.get(doc, 0) - 1) / math.log2(idx + 2)
        for idx, (doc, _) in enumerate(run[:k])
    )

def ndcg_at_k(run, qrels, k):
    ideal = sorted(qrels.values(), reverse=True)[:k]
    idcg = sum((2**rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(ideal))
    if idcg == 0:
        return 0.0
    return dcg_at_k(run, qrels, k) / idcg

def normalize_scores(scores_dict):
    if not scores_dict: return {}
    vals = list(scores_dict.values())
    min_v, max_v = min(vals), max(vals)
    range_v = max_v - min_v
    if range_v == 0:
        return {k: 0.5 for k in scores_dict}
    return {k: (v - min_v) / range_v for k, v in scores_dict.items()}

# --- 3. EVALUATION FRAMEWORK ---

def evaluate(retriever, queries, qrels, corpus_map,
             reranker=None, k=10, retrieval_k=50, batch_size=64, save_path=None,
             initial_runs_data=None):
    """
    Đánh giá retriever hoặc reranker trên dữ liệu có sẵn.
    Nếu initial_runs_data được cung cấp, sẽ bỏ qua bước retrieval.
    """
    ndcgs, recalls = [], []
    all_final_outputs = []

    q_texts = [q["text"] for q in queries]
    q_ids = [q["id"] for q in queries]

    eval_name = ""
    if initial_runs_data is None:
        eval_name = f"{retriever.__class__.__name__}"
    else:
        base_retriever_name = "Precomputed"
        if initial_runs_data and isinstance(initial_runs_data, list) and initial_runs_data[0].get('retriever_info'):
            base_retriever_name = initial_runs_data[0]['retriever_info'].split('+')[0].strip() # Lấy tên retriever gốc
        eval_name = f"{base_retriever_name}"

    if reranker:
        reranker_model_name = reranker.model_name.split('/')[-1]
        if reranker.__class__.__name__ == 'RagatouilleRetriever':
             reranker_model_name = "ColBERTv2"
             eval_name = "RAGatouilleRetriever"
        else:
             eval_name += f" + {reranker_model_name}"

    print(f"--- Starting Evaluation for: {eval_name} (Queries: {len(queries)}, k={k}) ---")

    all_initial_runs_tuples = []
    raw_outputs_to_save = []

    # === Bước 1: Initial Retrieval (HOẶC Load dữ liệu có sẵn) ===
    start_retrieval_time = time.time()
    if initial_runs_data is None:
        # --- Chạy retrieval ---
        current_retrieval_k = retrieval_k if reranker else k
        print(f"Step 1: Retrieving top {current_retrieval_k} candidates for {len(queries)} queries using {retriever.__class__.__name__}...")

        if isinstance(retriever, BM25Retriever):
            for qtext in tqdm(q_texts, desc=f"BM25 Search (k={current_retrieval_k})"):
                all_initial_runs_tuples.append(retriever.search(qtext, k=current_retrieval_k))
        elif hasattr(retriever, "search_batch"):
            all_initial_runs_tuples = retriever.search_batch(q_texts, k=current_retrieval_k, batch_size=batch_size)
        else:
            raise TypeError("Unsupported retriever type")

        retrieval_time = time.time() - start_retrieval_time
        print(f"Initial retrieval completed in {retrieval_time:.2f} seconds.")

        # Lưu thông tin retriever vào output
        for i in range(len(queries)):
            retriever_info = retriever.__class__.__name__
            if retriever.__class__.__name__ == 'RAGatouilleRetriever':
                retriever_info = "RAGatouille_ColBERTv2"
            
            raw_outputs_to_save.append({
                "query_id": q_ids[i],
                "query_text": q_texts[i],
                "retriever_info": retriever_info,
                "results": [
                    {"doc_id": docid, "score": float(score)}
                    for docid, score in all_initial_runs_tuples[i]
                ]
            })
        initial_runs_data = raw_outputs_to_save # Gán cho bước sau

    else:
        # --- Load dữ liệu có sẵn ---
        print(f"Step 1: Loading pre-computed initial runs for {len(queries)} queries...")
        all_initial_runs_tuples = []
        # Cập nhật retrieval_k để lấy chính xác số lượng từ dữ liệu thô
        final_retrieval_k = retrieval_k if reranker else k
        for run_data in initial_runs_data:
             results_list = run_data.get("results", [])[:final_retrieval_k]
             all_initial_runs_tuples.append([(res["doc_id"], float(res.get("score", 0.0))) for res in results_list])
        retrieval_time = 0
        print("Pre-computed runs loaded.")
        raw_outputs_to_save = initial_runs_data

    # === Bước 2: Reranking (Nếu có) ===
    start_rerank_time = time.time()
    if reranker and not isinstance(reranker, RAGPretrainedModel): # Loại trừ ColBERT/RAGatouille
        print(f"Step 2: Reranking top {retrieval_k} candidates for each query using {reranker.model_name}...")
        all_final_runs_tuples = []
        num_queries = len(queries)

        for i in tqdm(range(num_queries), desc=f"Reranking ({reranker.model_name.split('/')[-1]})"):
            qid = q_ids[i]
            qtext = q_texts[i]
            initial_run_tuples = all_initial_runs_tuples[i]

            docs_to_rerank = [
                {"doc_id": docid, "text": corpus_map.get(docid, ""), "initial_score": score}
                for docid, score in initial_run_tuples
            ]

            if not docs_to_rerank:
                all_final_runs_tuples.append([])
                all_final_outputs.append({
                    "query_id": qid, "query_text": qtext, "results": []
                })
                continue

            reranked_run_full = reranker.rerank(qtext, docs_to_rerank, k=k)

            final_run_tuples = [(doc['doc_id'], doc['rerank_score']) for doc in reranked_run_full]
            all_final_runs_tuples.append(final_run_tuples)

            all_final_outputs.append({
                "query_id": qid,
                "query_text": qtext,
                "retriever_info": raw_outputs_to_save[i].get('retriever_info', 'Precomputed'),
                "results": reranked_run_full
            })

        rerank_time = time.time() - start_rerank_time
        avg_latency_ms = (rerank_time / num_queries) * 1000 if num_queries > 0 else 0
        print(f"--- Reranking Performance ({reranker.model_name}) ---")
        print(f"Total time for reranking {num_queries} queries: {rerank_time:.2f} seconds")
        print(f"Average reranking latency: {avg_latency_ms:.2f} ms/query")

    else:
        # Không rerank, kết quả cuối cùng là initial run (đã cắt k) hoặc là ColBERT
        print("Step 2: No sequential reranker specified. Using initial retrieval results (or ColBERT).")
        all_final_runs_tuples = [run[:k] for run in all_initial_runs_tuples]
        rerank_time = 0
        # Nếu là ColBERT, outputs là raw_outputs_to_save
        all_final_outputs = raw_outputs_to_save

    # === Bước 3: Tính toán Metrics ===
    print("Step 3: Calculating metrics...")
    for i in range(len(queries)):
        qid = q_ids[i]
        final_run_tuples = all_final_runs_tuples[i]
        qrel = qrels.get(qid, {})
        ndcgs.append(ndcg_at_k(final_run_tuples, qrel, k))
        recalls.append(recall_at_k(final_run_tuples, qrel, k))

    # === Bước 4: Lưu kết quả ===
    if save_path:
        print(f"Saving {len(all_final_outputs)} final results to {save_path}...")
        try:
            save_jsonl(all_final_outputs, save_path)
            print("Saved successfully.")
        except Exception as e:
            print(f"Error saving results to {save_path}: {e}")

    mean_ndcg = float(np.mean(ndcgs)) if ndcgs else 0.0
    mean_recall = float(np.mean(recalls)) if recalls else 0.0

    print(f"--- Final Metrics for {eval_name} (k={k}) ---")
    print(f"Average nDCG@{k}: {mean_ndcg:.4f}")
    print(f"Average Recall@{k}: {mean_recall:.4f}")
    print("-" * 30)

    # Trả về raw_outputs_to_save nếu không rerank, hoặc all_final_outputs nếu có rerank
    return mean_ndcg, mean_recall, all_final_outputs if reranker and not isinstance(reranker, RAGPretrainedModel) else raw_outputs_to_save


# --- 4. RERANKER CLASS (hợp nhất từ notebook 2) ---

class Reranker:
    def __init__(self, model_name, model_type="cross-encoder", device=DEVICE, batch_size=32):
        self.device = device
        self.model_name = model_name
        self.model_type = model_type.lower()
        self.batch_size = batch_size

        print(f"Loading tokenizer for {model_name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

        print(f"Loading model {model_name} ({self.model_type})...")
        if self.model_type == 'qwen-reranker':
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32,
                attn_implementation="sdpa",
                trust_remote_code=True
            ).to(self.device).eval()
            self._qwen_prepare()
        elif self.model_type == 'cross-encoder':
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if self.device != 'cpu' else torch.float32
            ).to(self.device).eval()
            self.num_labels = self.model.config.num_labels
            print(f"Cross-encoder loaded with {self.num_labels} output labels.")
        else:
            raise ValueError("Unsupported model_type. Choose 'cross-encoder' or 'qwen-reranker'.")

        print(f"Reranker ({model_name}) initialized successfully on {self.device}.")

    def _qwen_prepare(self):
        self.token_false_id = self.tokenizer.convert_tokens_to_ids("no")
        self.token_true_id = self.tokenizer.convert_tokens_to_ids("yes")
        self.prefix = ("<|im_start|>system\\n"
                       "Judge whether the Document meets the requirements based on the Query and the Instruct provided. "
                       "Note that the answer can only be \\\"yes\\\" or \\\"no\\\".<|im_end|>\\n"
                       "<|im_start|>user\\n")
        self.suffix = "<|im_end|>\\n<|im_start|>assistant\\n<think>\\n\\n</think>\\n\\n"
        self.prefix_tokens = self.tokenizer.encode(self.prefix, add_special_tokens=False)
        self.suffix_tokens = self.tokenizer.encode(self.suffix, add_special_tokens=False)
        self.max_length = getattr(self.model.config, 'max_position_embeddings', 8192)
        print(f"Qwen reranker max sequence length: {self.max_length}")

    def _format_qwen_input(self, instruction, query, doc):
        return f"<Instruct>: {instruction}\\n<Query>: {query}\\n<Document>: {doc}"

    @torch.no_grad()
    def rerank(self, query, docs, k=10):
        if not docs: return []

        doc_map = {}
        input_pairs = []

        for idx, doc in enumerate(docs):
            doc_id = doc.get("doc_id")
            doc_text = doc.get("text", "")
            if not doc_id or not doc_text: continue

            if self.model_type == 'qwen-reranker':
                 instruction = 'Given a web search query, retrieve relevant passages that answer the query'
                 input_pairs.append(self._format_qwen_input(instruction, query, doc_text))
            elif self.model_type == 'cross-encoder':
                 input_pairs.append((query, doc_text))

            doc_map[idx] = doc

        all_scores = []
        for i in range(0, len(input_pairs), self.batch_size):
            batch_input = input_pairs[i : i + self.batch_size]

            if self.model_type == 'qwen-reranker':
                max_len_val = self.max_length - len(self.prefix_tokens) - len(self.suffix_tokens)
                inputs = self.tokenizer(
                    batch_input, padding=False, truncation='longest_first',
                    return_attention_mask=False,
                    max_length=max_len_val
                )
                for j in range(len(inputs['input_ids'])):
                    inputs['input_ids'][j] = self.prefix_tokens + inputs['input_ids'][j] + self.suffix_tokens

                inputs = self.tokenizer.pad(inputs, padding=True, return_tensors="pt", max_length=self.max_length)
                inputs = {key: val.to(self.device) for key, val in inputs.items()}

                logits = self.model(**inputs).logits[:, -1, :]
                true_logits = logits[:, self.token_true_id]
                false_logits = logits[:, self.token_false_id]
                batch_scores_tensor = torch.stack([false_logits, true_logits], dim=1)
                batch_scores_tensor = F.log_softmax(batch_scores_tensor, dim=1)
                scores = batch_scores_tensor[:, 1].exp().cpu().tolist()
            elif self.model_type == 'cross-encoder':
                ce_max_length = getattr(self.tokenizer, 'model_max_length', 512)
                inputs = self.tokenizer(
                    batch_input, padding=True, truncation=True,
                    return_tensors="pt", max_length=ce_max_length
                ).to(self.device)

                outputs = self.model(**inputs)
                logits = outputs.logits

                if self.num_labels == 1:
                    scores = logits.squeeze(-1).cpu().tolist()
                elif self.num_labels >= 2:
                     probabilities = torch.softmax(logits, dim=-1)
                     scores = probabilities[:, 1].cpu().tolist()
                else:
                    scores = [0.0] * len(batch_input)

            else:
                scores = [0.0] * len(batch_input)

            all_scores.extend(scores)

            # Cleanup
            del inputs
            if 'outputs' in locals(): del outputs
            if 'logits' in locals(): del logits
            if self.device in ['cuda', 'mps']:
                if self.device == 'cuda': torch.cuda.empty_cache()
                elif self.device == 'mps': torch.mps.empty_cache()
            gc.collect()

        scored_docs = []
        for idx, score in enumerate(all_scores):
            if idx in doc_map:
                doc = doc_map[idx]
                doc['rerank_score'] = float(score)
                scored_docs.append(doc)

        reranked_docs = sorted(scored_docs, key=lambda x: x.get('rerank_score', 0.0), reverse=True)

        return reranked_docs[:k]

# --- 5. RETRIEVER CLASSES (hợp nhất từ notebook 1 và 2) ---

class BM25Retriever:
    def __init__(self, corpus):
        self.doc_ids = [doc["id"] for doc in corpus]
        tokenized_corpus = [doc["text"].split() for doc in tqdm(corpus, desc="Tokenizing corpus for BM25")]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query, k=10):
        tokenized_query = query.split()
        scores = self.bm25.get_scores(tokenized_query)
        # Sắp xếp và lấy top k hiệu quả hơn
        top_k_indices = np.argpartition(scores, -k)[-k:]
        top_k_sorted_indices = top_k_indices[np.argsort(scores[top_k_indices])][::-1]
        return [(self.doc_ids[i], float(scores[i])) for i in top_k_sorted_indices]


class DenseRetriever:
    def __init__(self, corpus, model_name="sentence-transformers/all-MiniLM-L6-v2", device=DEVICE, embeddings_dir=None):
        self.device = device
        self.model_name = model_name
        print(f"Initializing DenseRetriever with model: {self.model_name} on device: {self.device}")
        self.model = SentenceTransformer(model_name, device=self.device)
        self.doc_ids = [doc["id"] for doc in corpus]

        safe_model_name = model_name.replace('/', '_')
        self.embeddings_path = os.path.join(embeddings_dir, f"corpus_embeddings_{safe_model_name}_small.npy")
        os.makedirs(embeddings_dir, exist_ok=True)

        if os.path.exists(self.embeddings_path):
            print(f"Loading pre-computed embeddings from {self.embeddings_path}...")
            self.doc_vecs = np.load(self.embeddings_path)
            print("Embeddings loaded successfully.")
        else:
            print(f"No pre-computed embeddings found at {self.embeddings_path}. Encoding corpus...")
            texts = [doc["text"] for doc in corpus]
            encode_batch_size = 128 if self.device in ['cuda', 'mps'] else 32
            self.doc_vecs = self.model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=True,
                convert_to_numpy=True,
                batch_size=encode_batch_size
            )
            print(f"Saving embeddings to {self.embeddings_path} for future use...")
            np.save(self.embeddings_path, self.doc_vecs)
            print(f"New embeddings saved.")

        self.doc_vecs_gpu = None
        if self.device in ["cuda", "mps"]:
            try:
                # self.doc_vecs_gpu = torch.from_numpy(self.doc_vecs).to(self.device)
                self.doc_vecs_gpu = torch.from_numpy(self.doc_vecs).to(self.device).to(torch.float32)
                print(f"Document embeddings moved to {self.device}.")
            except Exception as e:
                print(f"Failed to move embeddings to {self.device}: {e}. Calculations will use CPU numpy.")
                self.doc_vecs_gpu = None

    def search_batch(self, queries, k=10, batch_size=64):
        results = []
        for i in tqdm(range(0, len(queries), batch_size), desc=f"Dense Batch Search ({self.model_name})"):
            queries_chunk = queries[i:i+batch_size]
            q_vecs_chunk = self.model.encode(
                queries_chunk,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_tensor=True,
                device=self.device
            ).to(torch.float32)

            if self.doc_vecs_gpu is not None:
                sims_chunk = torch.matmul(q_vecs_chunk, self.doc_vecs_gpu.T)
                sims_chunk_cpu = sims_chunk.cpu().numpy()
            else:
                q_vecs_chunk_np = q_vecs_chunk.cpu().numpy()
                sims_chunk_cpu = np.dot(q_vecs_chunk_np, self.doc_vecs.T)

            for row in sims_chunk_cpu:
                if k < len(row):
                    top_idx = np.argpartition(row, -k)[-k:]
                    top_k_sorted_indices = top_idx[np.argsort(row[top_idx])][::-1]
                else:
                    top_k_sorted_indices = np.argsort(row)[::-1]
                results.append([(self.doc_ids[j], float(row[j])) for j in top_k_sorted_indices])

            del q_vecs_chunk
            if self.device == 'cuda': torch.cuda.empty_cache()
            elif self.device == 'mps': torch.mps.empty_cache()
            gc.collect()

        return results


class RagatouilleRetriever:
    # Class này chỉ là một wrapper mỏng để sử dụng RAGPretrainedModel trong hàm evaluate
    def __init__(self, collection_texts, collection_ids, index_root,
                 checkpoint='colbert-ir/colbertv2.0',
                 nbits=2, doc_maxlen=100, overwrite=False):

        self.index_root = index_root
        self.checkpoint = checkpoint
        self.index_name = f'colbert_index_full_{nbits}bits'
        self.device = DEVICE # Sử dụng global DEVICE

        print(f"Initializing RAGatouille with checkpoint: {checkpoint} on device: {self.device}")
        self.retriever = RAGPretrainedModel.from_pretrained(
            checkpoint,
            index_root=self.index_root,
            n_gpu=-1 if self.device == 'cuda' else 0, # -1 cho auto cuda, 0 cho CPU/MPS
            # device=self.device # RAGatouille xử lý device/n_gpu hơi khác, dùng n_gpu cho cuda
        )


    def index_collection(self, collection_texts, collection_ids, doc_maxlen, overwrite):
        print(f"Indexing full collection... (Index: {self.index_name}, Overwrite: {overwrite})")
        # RAGatouille sẽ tự xử lý device dựa trên config lúc from_pretrained
        self.retriever.index(
            collection=collection_texts,
            document_ids=collection_ids,
            index_name=self.index_name,
            max_document_length=doc_maxlen,
            overwrite_index=overwrite,
            use_faiss=True
        )
        print("Indexing complete.")

    def search_batch(self, queries, k=3, batch_size=64):
        print(f"RAGatouille searching {len(queries)} queries (k={k})...")

        # RAGatouille's .search() natively supports batch queries!
        batch_results = self.retriever.search(
            query=queries,
            k=k,
            index_name=self.index_name
        )

        all_results_tuples = []
        for q_results in tqdm(batch_results, desc="Mapping results"):
            current_q_results = [
                (res['document_id'], res['score']) for res in q_results
            ]
            all_results_tuples.append(current_q_results)

        return all_results_tuples


# --- 6. HYBRID FUSION FUNCTION (giữ nguyên) ---

def combine_and_evaluate_hybrid(bm25_results_path, dense_results_path, qrels, corpus_map, k=10, save_path=None, method='rrf', alpha=0.5, rrf_k=60):
    print(f"\n--- Combining BM25 ({os.path.basename(bm25_results_path)}) and Dense ({os.path.basename(dense_results_path)}) using '{method}' ---")

    try:
        bm25_outputs = load_jsonl(bm25_results_path)
        dense_outputs = load_jsonl(dense_results_path)
    except Exception as e:
        print(f"Error loading results file: {e}. Cannot proceed with hybrid combination.")
        return None, None, []

    if len(bm25_outputs) != len(dense_outputs):
         print("Number of queries in BM25 and Dense outputs do not match! Skipping.")
         return None, None, []

    ndcgs, recalls = [], []
    hybrid_outputs_raw = []

    dense_model_name_inferred = "UnknownDense"
    if dense_outputs and dense_outputs[0].get('retriever_info'):
        dense_model_name_inferred = dense_outputs[0]['retriever_info'].replace('DenseRetriever', '').replace('Raw', '').strip()

    hybrid_retriever_name = f"Hybrid_{dense_model_name_inferred}_{method}"

    for i in tqdm(range(len(bm25_outputs)), desc=f"Combining Hybrid ({method})"):
        bm_res = bm25_outputs[i]
        dn_res = dense_outputs[i]

        qid = bm_res["query_id"]
        qtext = bm_res["query_text"]
        qrel = qrels.get(qid, {})

        run_tuples = []
        bm_results_list = bm_res.get('results', [])
        dn_results_list = dn_res.get('results', [])

        if method == 'weighted_sum':
            bm_dict = {r['doc_id']: r['score'] for r in bm_results_list}
            dn_dict = {r['doc_id']: r['score'] for r in dn_results_list}
            bm_norm = normalize_scores(bm_dict)
            dn_norm = normalize_scores(dn_dict)
            all_ids = set(bm_norm.keys()) | set(dn_norm.keys())
            scores = {
                doc_id: alpha * dn_norm.get(doc_id, 0) + (1 - alpha) * bm_norm.get(doc_id, 0)
                for doc_id in all_ids
            }
            run_tuples = sorted(scores.items(), key=lambda item: item[1], reverse=True)

        elif method == 'rrf':
            bm_ranks = {r['doc_id']: i + 1 for i, r in enumerate(bm_results_list)}
            dn_ranks = {r['doc_id']: i + 1 for i, r in enumerate(dn_results_list)}
            all_ids = set(bm_ranks.keys()) | set(dn_ranks.keys())
            rrf_scores = {}
            for doc_id in all_ids:
                score = 0.0
                if doc_id in bm_ranks: score += 1.0 / (rrf_k + bm_ranks[doc_id])
                if doc_id in dn_ranks: score += 1.0 / (rrf_k + dn_ranks[doc_id])
                rrf_scores[doc_id] = score
            run_tuples = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
        else:
            raise ValueError("Method must be 'weighted_sum' or 'rrf'")

        run_tuples_k = run_tuples[:k]

        ndcgs.append(ndcg_at_k(run_tuples_k, qrel, k))
        recalls.append(recall_at_k(run_tuples_k, qrel, k))

        hybrid_outputs_raw.append({
            "query_id": qid,
            "query_text": qtext,
            "retriever_info": hybrid_retriever_name,
            "results": [
                 {"doc_id": docid, "score": float(score)}
                 for docid, score in run_tuples
            ]
        })

    mean_ndcg = float(np.mean(ndcgs)) if ndcgs else 0.0
    mean_recall = float(np.mean(recalls)) if recalls else 0.0

    print(f"--- Hybrid Raw Metrics ({method}, k={k}) ---")
    print(f"Average nDCG@{k}: {mean_ndcg:.4f}")
    print(f"Average Recall@{k}: {mean_recall:.4f}")

    if save_path:
        print(f"Saving {len(hybrid_outputs_raw)} raw hybrid results to {save_path}...")
        try:
             save_jsonl(hybrid_outputs_raw, save_path)
             print(f"Saved raw hybrid results successfully.")
        except Exception as e:
             print(f"Error saving raw hybrid results to {save_path}: {e}")

    return mean_ndcg, mean_recall, hybrid_outputs_raw

def parse_args():
    parser = argparse.ArgumentParser(description="Run IR evaluation pipelines on MS MARCO validation set.")
    
    # Arguments cho các retriever/pipeline cơ bản
    parser.add_argument('--colbert', action='store_true', help='Run RAGatouille (ColBERTv2) evaluation.')
    parser.add_argument('--bm25', action='store_true', help='Run BM25 retrieval and save raw results.')
    parser.add_argument('--minilm', action='store_true', help='Run Dense MiniLM-L6 retrieval and save raw results.')
    parser.add_argument('--bgesmall', action='store_true', help='Run Dense BGE-small-en-v1.5 retrieval and save raw results.')
    parser.add_argument('--hybrid', action='store_true', help='Run Hybrid Fusion (RRF) for both MiniLM and BGE-Small (requires BM25/MiniLM/BGE raw outputs).')
    
    # Arguments cho reranker
    parser.add_argument('--rerank_bge', action='store_true', help='Run all available retrievers/fusion results through BGE-Large reranker.')
    parser.add_argument('--rerank_minilm_ce', action='store_true', help='Run all available retrievers/fusion results through MiniLM-L12 cross-encoder.')
    
    # Argument cấu hình chung (có thể set mặc định nếu không muốn thay đổi)
    parser.add_argument('--num_corpus', type=int, default=50000, help='Target size for the subset corpus.')
    parser.add_argument('--num_query', type=int, default=1000, help='Number of queries to sample for evaluation.')
    parser.add_argument('--k_metric', type=int, default=3, help='Top-K for final metrics (nDCG@K, Recall@K).')
    parser.add_argument('--k_retrieval', type=int, default=30, help='Top-K for initial retrieval (for reranking/fusion).')
    
    args = parser.parse_args()
    return args

def main():
    args = parse_args()
    
    # Cấu hình chung từ arguments
    NUM_CORPUS_TARGET = 50000 # cố định không đổi
    NUM_QUERY = 1000 # cố định không đổi (thực tế chỉ có 556 query trong tập val có relevant doc)
    K_METRIC = args.k_metric
    K_RETRIEVAL = args.k_retrieval
    BATCH_SIZE = 128 # Giữ nguyên

    global base_path
    base_path = os.getenv("BASE_PATH", "ms_marco_val")
    results_dir = os.path.join(base_path, "results_optimized_2")
    os.makedirs(results_dir, exist_ok=True)
    results = {}
    
    # Định nghĩa các tên file đầu ra thô
    bm25_raw_path = os.path.join(results_dir, f"bm25_raw_k{K_RETRIEVAL}_numdoc{NUM_CORPUS_TARGET}.jsonl")
    minilm_raw_path = os.path.join(results_dir, f"dense_minilm_raw_k{K_RETRIEVAL}_numdoc{NUM_CORPUS_TARGET}.jsonl")
    bge_small_raw_path = os.path.join(results_dir, f"dense_bge_small_raw_k{K_RETRIEVAL}_numdoc{NUM_CORPUS_TARGET}.jsonl")
    hybrid_minilm_path = os.path.join(results_dir, f"hybrid_minilm_rrf_raw_k{K_RETRIEVAL}_numdoc{NUM_CORPUS_TARGET}.jsonl")
    hybrid_bge_path = os.path.join(results_dir, f"hybrid_bge_small_rrf_raw_k{K_RETRIEVAL}_numdoc{NUM_CORPUS_TARGET}.jsonl")

    # --- PHASE 0: PREPARATION (giữ nguyên logic chọn tập con) ---
    print(f"Base Path: {base_path}")
    print(f"Results Dir: {results_dir}")
    print(f"K_METRIC: {K_METRIC}, K_RETRIEVAL: {K_RETRIEVAL}")
    print("--------------------------------------------------")

    corpus = load_jsonl(os.path.join(base_path, "corpus.jsonl"))
    queries_full = load_jsonl(os.path.join(base_path, "queries.jsonl"))
    qrels_full = load_qrels(os.path.join(base_path, "qrels.tsv"))

    random.seed(42)
    queries_eval = random.sample(queries_full, NUM_QUERY) if len(queries_full) > NUM_QUERY else queries_full

    qids_eval = {q['id'] for q in queries_eval}
    qrels_eval = {qid: docs for qid, docs in qrels_full.items() if qid in qids_eval}

    relevant_doc_ids = set().union(*[{docid for docid, rel in docs.items() if rel > 0} for docs in qrels_eval.values()])
    qids_with_relevant_doc = {qid for qid, docs in qrels_eval.items() if docs}
    queries_eval = [q for q in queries_eval if q['id'] in qids_with_relevant_doc]

    corpus_map_full = {doc['id']: doc for doc in corpus}
    all_doc_ids = set(corpus_map_full.keys())
    noise_candidate_ids = all_doc_ids - relevant_doc_ids

    num_relevant_docs = len(relevant_doc_ids)
    required_noise = max(0, NUM_CORPUS_TARGET - num_relevant_docs)
    num_noise_to_take = min(required_noise, len(noise_candidate_ids))

    random.seed(42)
    noise_doc_ids = random.sample(list(noise_candidate_ids), num_noise_to_take) if num_noise_to_take > 0 else []

    final_corpus_ids = relevant_doc_ids.union(set(noise_doc_ids))

    # corpus_subset = [corpus_map_full[doc_id] for doc_id in final_corpus_ids]

    final_corpus_ids_list = list(final_corpus_ids)
    final_corpus_ids_list.sort()
    corpus_subset = [corpus_map_full[doc_id] for doc_id in final_corpus_ids_list]


    queries = queries_eval
    qrels = qrels_eval
    corpus = corpus_subset
    corpus_texts = [doc['text'] for doc in corpus]
    corpus_ids = [doc['id'] for doc in corpus]
    corpus_map = {doc['id']: doc['text'] for doc in corpus}

    print(f"Final Corpus size: {len(corpus):,} documents (Relevant: {num_relevant_docs:,}, Noise: {len(noise_doc_ids):,})")
    print(f"Final Queries size: {len(queries):,} queries")
    print("--------------------------------------------------")
    
    # Khởi tạo các biến chứa output thô (dùng cho rerank/fusion sau này)
    colbert_outputs = None
    bm25_raw_outputs = None
    minilm_raw_outputs = None
    bge_small_raw_outputs = None
    hybrid_minilm_rrf_outputs = None
    hybrid_bge_small_rrf_outputs = None


    # --- PHASE 1: INDIVIDUAL MODELS ---

    # 1. ColBERTv2 (RAGatouille)
    if args.colbert:
        print("\n" + "="*50)
        print("BẮT ĐẦU ĐÁNH GIÁ RAGATOUILLE (COLBERTV2)")
        colbert_retriever_root = "ms_marco_val"
        index_name = "colbert_index_full_2bits"
        index_dir = os.path.join(colbert_retriever_root, "colbert", "indexes", index_name)

        colbert_retriever = RagatouilleRetriever(
            collection_texts=corpus_texts,
            collection_ids=corpus_ids,
            index_root=colbert_retriever_root,
            checkpoint='colbert-ir/colbertv2.0',
            nbits=2,
            doc_maxlen=80,
            overwrite=False
        )
        
        if os.path.exists(index_dir):
            try:
                index_full_path = os.path.join(colbert_retriever_root, "colbert", "indexes", index_name)
                colbert_retriever.retriever = RAGPretrainedModel.from_index(index_full_path)
                print("RAGPretrainedModel loaded successfully from index path.")
            except Exception as e:
                print(f"!!! LỖI KHÔNG TẢI ĐƯỢC INDEX BẰNG from_index: {e}. Thử xây lại index.")
                colbert_retriever.index_collection(corpus_texts, corpus_ids, 80, True)
        else:
            print(f"No index found at {index_dir}. Building new index...")
            colbert_retriever.index_collection(corpus_texts, corpus_ids, 80, True)

        colbert_ndcg, colbert_recall, colbert_outputs = evaluate(
            retriever=colbert_retriever,
            queries=queries,
            qrels=qrels,
            corpus_map=corpus_map,
            k=K_METRIC,
            retrieval_k=K_RETRIEVAL,
            batch_size=BATCH_SIZE,
            save_path=os.path.join(results_dir, f"colbert_evaluation_results_k{K_METRIC}.jsonl")
        )
        results['RAGatouille_ColBERTv2'] = {f"nDCG@{K_METRIC}": colbert_ndcg, f"Recall@{K_METRIC}": colbert_recall}
        del colbert_retriever
        gc.collect()
        if DEVICE == 'cuda': torch.cuda.empty_cache()
        elif DEVICE == 'mps': torch.mps.empty_cache()
    else:
         # Tải output đã lưu nếu có (cần thiết cho rerank/summary)
         if os.path.exists(os.path.join(results_dir, f"colbert_evaluation_results_k{K_METRIC}.jsonl")):
              colbert_outputs = load_jsonl(os.path.join(results_dir, f"colbert_evaluation_results_k{K_METRIC}.jsonl"))


    # 2. BM25
    if args.bm25:
        bm25_retriever = BM25Retriever(corpus)
        print(f"\n--- Evaluating BM25 Raw ---")
        bm25_ndcg, bm25_recall, bm25_raw_outputs = evaluate(
            bm25_retriever, queries, qrels, corpus_map, k=K_RETRIEVAL, retrieval_k=K_RETRIEVAL, # Lưu top K_RETRIEVAL
            save_path=bm25_raw_path
        )
        # Tính lại metrics cho K_METRIC (để đưa vào summary)
        final_ndcgs, final_recalls = [], []
        for record in bm25_raw_outputs:
            q_id = record["query_id"]
            q_rel = qrels.get(q_id, {})
            final_run = [(d['doc_id'], d.get('score', 0.0)) for d in record['results']]
            final_ndcgs.append(ndcg_at_k(final_run, q_rel, K_METRIC))
            final_recalls.append(recall_at_k(final_run, q_rel, K_METRIC))
        results[f"BM25 Raw (k={K_METRIC})"] = {f"nDCG@{K_METRIC}": np.mean(final_ndcgs), f"Recall@{K_METRIC}": np.mean(final_recalls)}
        del bm25_retriever
        gc.collect()
    else:
        # Tải output đã lưu nếu cần cho Hybrid/Rerank
        if os.path.exists(bm25_raw_path):
             bm25_raw_outputs = load_jsonl(bm25_raw_path)


    # 3. Dense MiniLM-L6
    if args.minilm:
        minilm_model_name = "sentence-transformers/all-MiniLM-L6-v2"
        print(f"\n--- Evaluating Dense {minilm_model_name.split('/')[-1]} Raw ---")
        dense_minilm = DenseRetriever(corpus, model_name=minilm_model_name, device=DEVICE, embeddings_dir=base_path)
        minilm_ndcg, minilm_recall, minilm_raw_outputs = evaluate(
            dense_minilm, queries, qrels, corpus_map, k=K_RETRIEVAL, retrieval_k=K_RETRIEVAL,
            batch_size=BATCH_SIZE, save_path=minilm_raw_path
        )
        # Tính lại metrics cho K_METRIC
        final_ndcgs, final_recalls = [], []
        for record in minilm_raw_outputs:
            q_id = record["query_id"]
            q_rel = qrels.get(q_id, {})
            final_run = [(d['doc_id'], d.get('score', 0.0)) for d in record['results']]
            final_ndcgs.append(ndcg_at_k(final_run, q_rel, K_METRIC))
            final_recalls.append(recall_at_k(final_run, q_rel, K_METRIC))
        results[f"Dense MiniLM Raw (k={K_METRIC})"] = {f"nDCG@{K_METRIC}": np.mean(final_ndcgs), f"Recall@{K_METRIC}": np.mean(final_recalls)}
        del dense_minilm
        gc.collect()
        if DEVICE == 'cuda': torch.cuda.empty_cache()
        elif DEVICE == 'mps': torch.mps.empty_cache()
    else:
        if os.path.exists(minilm_raw_path):
             minilm_raw_outputs = load_jsonl(minilm_raw_path)


    # 4. Dense BGE-small-en-v1.5
    if args.bgesmall:
        bge_model_name = "BAAI/bge-small-en-v1.5"
        print(f"\n--- Evaluating Dense {bge_model_name.split('/')[-1]} Raw ---")
        dense_bge = DenseRetriever(corpus, model_name=bge_model_name, device=DEVICE, embeddings_dir=base_path)
        bge_ndcg, bge_recall, bge_small_raw_outputs = evaluate(
            dense_bge, queries, qrels, corpus_map, k=K_RETRIEVAL, retrieval_k=K_RETRIEVAL,
            batch_size=BATCH_SIZE, save_path=bge_small_raw_path
        )
        # Tính lại metrics cho K_METRIC
        final_ndcgs, final_recalls = [], []
        for record in bge_small_raw_outputs:
            q_id = record["query_id"]
            q_rel = qrels.get(q_id, {})
            final_run = [(d['doc_id'], d.get('score', 0.0)) for d in record['results']]
            final_ndcgs.append(ndcg_at_k(final_run, q_rel, K_METRIC))
            final_recalls.append(recall_at_k(final_run, q_rel, K_METRIC))
        results[f"Dense BGE-Small Raw (k={K_METRIC})"] = {f"nDCG@{K_METRIC}": np.mean(final_ndcgs), f"Recall@{K_METRIC}": np.mean(final_recalls)}
        del dense_bge
        gc.collect()
        if DEVICE == 'cuda': torch.cuda.empty_cache()
        elif DEVICE == 'mps': torch.mps.empty_cache()
    else:
        if os.path.exists(bge_small_raw_path):
             bge_small_raw_outputs = load_jsonl(bge_small_raw_path)


    # --- PHASE 2: HYBRID FUSION ---

    if args.hybrid:
        # 5. Hybrid BM25 + MiniLM (RRF)
        if bm25_raw_outputs is not None and minilm_raw_outputs is not None:
            print(f"\n--- Running Hybrid BM25 + MiniLM (RRF) ---")
            h_minilm_ndcg, h_minilm_recall, hybrid_minilm_rrf_outputs, error = combine_and_evaluate_hybrid(
                bm25_raw_path, minilm_raw_path, qrels, corpus_map, k=K_METRIC,
                save_path=hybrid_minilm_path, method='rrf', rrf_k=60
            )
            if not error:
                 results[f"Hybrid MiniLM RRF Raw (k={K_METRIC})"] = {f"nDCG@{K_METRIC}": h_minilm_ndcg, f"Recall@{K_METRIC}": h_minilm_recall}
        else:
             print(f"\n--- Skipping Hybrid BM25 + MiniLM (RRF): Missing BM25/MiniLM raw data. ---")
             if os.path.exists(hybrid_minilm_path):
                 hybrid_minilm_rrf_outputs = load_jsonl(hybrid_minilm_path)


        # 6. Hybrid BM25 + BGE-Small (RRF)
        if bm25_raw_outputs is not None and bge_small_raw_outputs is not None:
            print(f"\n--- Running Hybrid BM25 + BGE-Small (RRF) ---")
            h_bge_ndcg, h_bge_recall, hybrid_bge_small_rrf_outputs, error = combine_and_evaluate_hybrid(
                bm25_raw_path, bge_small_raw_path, qrels, corpus_map, k=K_METRIC,
                save_path=hybrid_bge_path, method='rrf', rrf_k=60
            )
            if not error:
                results[f"Hybrid BGE-Small RRF Raw (k={K_METRIC})"] = {f"nDCG@{K_METRIC}": h_bge_ndcg, f"Recall@{K_METRIC}": h_bge_recall}
        else:
            print(f"\n--- Skipping Hybrid BM25 + BGE-Small (RRF): Missing BM25/BGE-Small raw data. ---")
            if os.path.exists(hybrid_bge_path):
                hybrid_bge_small_rrf_outputs = load_jsonl(hybrid_bge_path)
        
    else:
        # Tải output đã lưu nếu cần cho Rerank
        if os.path.exists(hybrid_minilm_path):
                 hybrid_minilm_rrf_outputs = load_jsonl(hybrid_minilm_path)
        if os.path.exists(hybrid_bge_path):
                 hybrid_bge_small_rrf_outputs = load_jsonl(hybrid_bge_path)


    print("\n--- Retrieval and Fusion Phase Complete. VRAM should be clear. ---")

    # --- PHASE 3: SEQUENTIAL RERANKINGS ---

    datasets_to_rerank = {
        "BM25_Raw": bm25_raw_outputs,
        "Dense_MiniLM_Raw": minilm_raw_outputs,
        "Dense_BGE-Small_Raw": bge_small_raw_outputs,
        "Hybrid_MiniLM_RRF_Raw": hybrid_minilm_rrf_outputs,
        "Hybrid_BGE-Small_RRF_Raw": hybrid_bge_small_rrf_outputs,
        "ColBERTv2_Raw": colbert_outputs # Có thể rerank cả ColBERT (dù ít phổ biến)
    }

    RERANKER_CONFIGS = []
    if args.rerank_bge:
         RERANKER_CONFIGS.append({"name": "BGE-Large", "model_name": "BAAI/bge-reranker-large", "model_type": "cross-encoder", "batch_size": 64})
    if args.rerank_minilm_ce:
         RERANKER_CONFIGS.append({"name": "MiniLM-L12", "model_name": "cross-encoder/ms-marco-MiniLM-L-12-v2", "model_type": "cross-encoder", "batch_size": 64})

    for reranker_cfg in RERANKER_CONFIGS:
        reranker_name = reranker_cfg['name']
        print(f"\n===== PROCESSING RERANKER: {reranker_name} =====")
        reranker_obj = None

        try:
            print(f"Loading {reranker_name}...")
            reranker_obj = Reranker(
                model_name=reranker_cfg['model_name'],
                model_type=reranker_cfg['model_type'],
                batch_size=reranker_cfg.get('batch_size', 4),
                device=DEVICE
            )

            for data_key_prefix, initial_data in datasets_to_rerank.items():

                if initial_data is None:
                    print(f"Skipping reranking for **{data_key_prefix}** with {reranker_name} - Initial data is not available (run the prerequisite retriever/hybrid step first).")
                    continue

                if not initial_data or not isinstance(initial_data, list) or len(initial_data) == 0:
                    print(f"Skipping reranking for **{data_key_prefix}** with {reranker_name} - Initial data is empty.")
                    continue

                reranked_key = f"{data_key_prefix.replace('_Raw', '')} + {reranker_name}"
                print(f"\n--- Reranking: {reranked_key} ---")

                ndcg, recall, _ = evaluate(
                    retriever=None,
                    queries=queries,
                    qrels=qrels,
                    corpus_map=corpus_map,
                    reranker=reranker_obj,
                    k=K_METRIC,
                    retrieval_k=K_RETRIEVAL,
                    initial_runs_data=initial_data,
                    save_path=os.path.join(results_dir, f"{reranked_key.replace(' ', '_').replace('+', '_')}_k{K_METRIC}.jsonl")
                )
                results[reranked_key] = {f"nDCG@{K_METRIC}": ndcg, f"Recall@{K_METRIC}": recall}

        except Exception as e:
            print(f"!! FAILED during processing with Reranker {reranker_name}: {e}")
            for data_key_prefix in datasets_to_rerank.keys():
                 if datasets_to_rerank[data_key_prefix] is not None:
                     failed_key = f"{data_key_prefix.replace('_Raw', '')} + {reranker_name}"
                     if failed_key not in results:
                         results[failed_key] = {f"nDCG@{K_METRIC}": "LOAD/RUN ERROR", f"Recall@{K_METRIC}": "LOAD/RUN ERROR"}

        finally:
            if reranker_obj and hasattr(reranker_obj, 'model'):
                print(f"\nUnloading {reranker_name}...")
                del reranker_obj.model
                del reranker_obj.tokenizer
                del reranker_obj
            gc.collect()
            if DEVICE == 'cuda': torch.cuda.empty_cache()
            elif DEVICE == 'mps': torch.mps.empty_cache()
            print(f"Cleanup for {reranker_name} complete.")
            print("="*50)

    # --- FINAL SUMMARY ---
    print("\n" + "="*50)
    print(f"FINAL RESULTS SUMMARY (k={K_METRIC}):")
    
    # Chỉ hiển thị các kết quả đã được tính toán thành công
    filtered_results = {k: v for k, v in results.items() if isinstance(v.get(f"nDCG@{K_METRIC}"), (float, np.float32, np.float64))}
    
    # Sắp xếp theo nDCG@K giảm dần
    sorted_results = dict(sorted(filtered_results.items(), key=lambda item: item[1].get(f"nDCG@{K_METRIC}", 0.0), reverse=True))
    
    # Thêm các lỗi vào cuối
    error_results = {k: v for k, v in results.items() if not isinstance(v.get(f"nDCG@{K_METRIC}"), (float, np.float32, np.float64))}
    sorted_results.update(error_results)
    
    print(json.dumps(sorted_results, indent=4))
    print("="*50)

    with open(os.path.join(results_dir, f'results_final_k{K_METRIC}.json'), 'w') as f:
        json.dump(sorted_results, f, indent=4)

if __name__ == '__main__':
    main()