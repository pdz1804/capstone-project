"""
Video/Audio RAG Integration Module

Integrates video/audio processing pipeline with RAG retrieval systems
for end-to-end video-to-RAG workflows.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from rag_retrievers import SimpleBM25Retriever, SimpleDenseRetriever, SimpleHybridRetriever
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class VideoRAGPipeline:
    """
    End-to-end RAG pipeline for video/audio content.
    
    Processes video → extracts chunks → indexes for retrieval
    """
    
    def __init__(
        self,
        retrieval_method: str = "hybrid",
        use_frames: bool = True
    ):
        """
        Initialize Video RAG Pipeline.
        
        Args:
            retrieval_method: "bm25", "dense", or "hybrid"
            use_frames: Whether to include frame metadata in retrieval
        """
        # Always initialize base attributes
        self.use_frames = use_frames
        self.indexed_chunks = []
        self.chunk_index_map = {}  # Map chunk index to metadata
        
        if not RAG_AVAILABLE:
            logger.warning("RAG retrievers not available")
            self.retriever = None
            return
        
        self.retriever = self._init_retriever(retrieval_method)
    
    def _init_retriever(self, method: str):
        """Initialize the appropriate retriever."""
        if method == "bm25":
            return SimpleBM25Retriever()
        elif method == "dense":
            return SimpleDenseRetriever()
        elif method == "hybrid":
            return SimpleHybridRetriever()
        else:
            logger.warning(f"Unknown method {method}, using BM25")
            return SimpleBM25Retriever()
    
    def load_enhanced_chunks(self, chunks_json_path: str) -> List[Dict[str, Any]]:
        """
        Load enhanced chunks from the processing pipeline output.
        
        Args:
            chunks_json_path: Path to enhanced_chunks.json
        
        Returns:
            List of chunk dictionaries
        """
        try:
            with open(chunks_json_path, 'r') as f:
                data = json.load(f)
            
            chunks = data.get("chunks", [])
            logger.info(f"Loaded {len(chunks)} enhanced chunks")
            
            return chunks
        
        except Exception as e:
            logger.error(f"Error loading chunks: {str(e)}")
            return []
    
    def index_video_chunks(
        self,
        chunks: List[Dict[str, Any]],
        video_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Index enhanced video chunks for RAG retrieval.
        
        Args:
            chunks: List of chunk dictionaries from processing pipeline
            video_metadata: Optional metadata about the source video
        
        Returns:
            True if indexing successful
        """
        if not self.retriever or not RAG_AVAILABLE:
            logger.warning("Retriever not available")
            return False
        
        try:
            logger.info(f"Indexing {len(chunks)} chunks for RAG...")
            
            # Convert chunks to retriever format
            documents = []
            for i, chunk in enumerate(chunks):
                doc = {
                    "id": f"chunk_{chunk.get('chunk_index', i)}",
                    "text": chunk.get("text", ""),
                    "source": video_metadata.get("filename", "unknown") if video_metadata else "unknown",
                    "metadata": {
                        "chunk_index": chunk.get("chunk_index", i),
                        "start_time": chunk.get("start_time", 0),
                        "end_time": chunk.get("end_time", 0),
                        "duration": chunk.get("duration", 0),
                        "description": chunk.get("text_description", ""),
                        "associated_frames": chunk.get("associated_frames", []),
                        "token_count": chunk.get("token_count", 0),
                        "segment_indices": chunk.get("segment_indices", [])
                    }
                }
                documents.append(doc)
                self.chunk_index_map[chunk.get("chunk_index", i)] = doc
            
            # Index documents
            self.retriever.index_documents(documents)
            self.indexed_chunks = chunks
            
            logger.info(f"✓ Successfully indexed {len(documents)} chunks")
            return True
        
        except Exception as e:
            logger.error(f"Error indexing chunks: {str(e)}")
            return False
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        include_frames: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: Search query
            top_k: Number of top results to return
            include_frames: Whether to include associated frames
        
        Returns:
            List of relevant chunks with metadata
        """
        if not self.retriever or not self.indexed_chunks:
            logger.warning("Retriever not ready or no indexed chunks")
            return []
        
        try:
            logger.info(f"Retrieving top {top_k} chunks for query: {query}")
            
            # Retrieve from RAG
            results = self.retriever.search(query, top_k=top_k)
            
            # Enrich results with original chunk data
            enriched_results = []
            for result in results:
                chunk_idx = int(result.get("id", "chunk_0").split("_")[-1])
                
                # Find original chunk
                original_chunk = None
                for chunk in self.indexed_chunks:
                    if chunk.get("chunk_index") == chunk_idx:
                        original_chunk = chunk
                        break
                
                if original_chunk:
                    enriched_result = {
                        "rank": len(enriched_results) + 1,
                        "score": result.get("score", 0),
                        "chunk_index": chunk_idx,
                        "text": original_chunk.get("text", ""),
                        "description": original_chunk.get("text_description", ""),
                        "start_time": original_chunk.get("start_time", 0),
                        "end_time": original_chunk.get("end_time", 0),
                        "duration": original_chunk.get("duration", 0),
                        "associated_frames": (
                            original_chunk.get("associated_frames", [])
                            if include_frames else []
                        ),
                        "source": result.get("source", "unknown"),
                        "metadata": result.get("metadata", {})
                    }
                    enriched_results.append(enriched_result)
            
            logger.info(f"Retrieved {len(enriched_results)} relevant chunks")
            return enriched_results
        
        except Exception as e:
            logger.error(f"Error retrieving results: {str(e)}")
            return []
    
    def save_index(self, output_path: str) -> bool:
        """
        Save the indexed retriever to disk.
        
        Args:
            output_path: Path to save the index
        
        Returns:
            True if save successful
        """
        if not self.retriever:
            logger.warning("No retriever to save")
            return False
        
        try:
            self.retriever.save_index(output_path)
            logger.info(f"✓ Index saved to {output_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving index: {str(e)}")
            return False
    
    def load_index(self, index_path: str) -> bool:
        """
        Load a previously saved index.
        
        Args:
            index_path: Path to the saved index
        
        Returns:
            True if load successful
        """
        if not self.retriever:
            logger.warning("No retriever to load index to")
            return False
        
        try:
            self.retriever.load_index(index_path)
            logger.info(f"✓ Index loaded from {index_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error loading index: {str(e)}")
            return False


class VideoFrameRetriever:
    """
    Retrieve frames associated with query results.
    
    Links text chunks to their visual representations in the video.
    """
    
    def __init__(self, frames_dir: str, frame_metadata_path: str):
        """
        Initialize frame retriever.
        
        Args:
            frames_dir: Directory containing extracted frames
            frame_metadata_path: Path to frame metadata JSON
        """
        self.frames_dir = Path(frames_dir)
        self.frame_metadata = self._load_frame_metadata(frame_metadata_path)
    
    def _load_frame_metadata(self, path: str) -> Dict[str, Any]:
        """Load frame metadata."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading frame metadata: {str(e)}")
            return {}
    
    def get_frames_for_chunk(self, chunk_index: int) -> List[Dict[str, Any]]:
        """
        Get frames associated with a specific chunk.
        
        Args:
            chunk_index: Index of the chunk
        
        Returns:
            List of frame metadata and paths
        """
        frames_data = self.frame_metadata.get("frames", [])
        associated_frames = []
        
        for frame in frames_data:
            if frame.get("associated_chunk_index") == chunk_index:
                frame_path = self.frames_dir / frame.get("frame_path", "")
                
                if frame_path.exists():
                    associated_frames.append({
                        "frame_path": str(frame_path),
                        "frame_index": frame.get("frame_index"),
                        "video_timestamp": frame.get("video_timestamp"),
                        "hash": frame.get("frame_hash"),
                        "is_duplicate": frame.get("is_duplicate", False)
                    })
        
        return associated_frames
    
    def get_frames_by_timestamp(
        self,
        start_time: float,
        end_time: float
    ) -> List[Dict[str, Any]]:
        """
        Get frames within a time range.
        
        Args:
            start_time: Start timestamp in seconds
            end_time: End timestamp in seconds
        
        Returns:
            List of frames in the time range
        """
        frames_data = self.frame_metadata.get("frames", [])
        frames_in_range = []
        
        for frame in frames_data:
            frame_ts = frame.get("video_timestamp", 0)
            
            if start_time <= frame_ts <= end_time:
                frame_path = self.frames_dir / frame.get("frame_path", "")
                
                if frame_path.exists():
                    frames_in_range.append({
                        "frame_path": str(frame_path),
                        "frame_index": frame.get("frame_index"),
                        "video_timestamp": frame_ts
                    })
        
        return frames_in_range


class VideoRAGEvaluator:
    """Evaluate RAG retrieval quality on video chunks."""
    
    @staticmethod
    def evaluate_retrieval(
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        relevant_indices: List[int]
    ) -> Dict[str, float]:
        """
        Evaluate retrieval quality.
        
        Args:
            query: The search query
            retrieved_chunks: Retrieved chunks from RAG
            relevant_indices: Ground truth relevant chunk indices
        
        Returns:
            Evaluation metrics (precision, recall, MRR, etc.)
        """
        retrieved_indices = [
            chunk.get("chunk_index") for chunk in retrieved_chunks
        ]
        
        # Calculate metrics
        tp = len(set(retrieved_indices) & set(relevant_indices))
        fp = len(set(retrieved_indices) - set(relevant_indices))
        fn = len(set(relevant_indices) - set(retrieved_indices))
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # MRR (Mean Reciprocal Rank)
        mrr = 0.0
        for i, idx in enumerate(retrieved_indices):
            if idx in relevant_indices:
                mrr = 1.0 / (i + 1)
                break
        
        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "mrr": mrr,
            "relevant_count": len(relevant_indices),
            "retrieved_count": len(retrieved_chunks),
            "true_positives": tp
        }


# Example usage
if __name__ == "__main__":
    # Initialize pipeline
    rag_pipeline = VideoRAGPipeline(retrieval_method="hybrid", use_frames=True)
    
    # Load enhanced chunks
    chunks = rag_pipeline.load_enhanced_chunks(
        "output/transcript_chunks/video_enhanced_chunks.json"
    )
    
    # Index for RAG
    video_meta = {
        "filename": "lecture.mp4",
        "duration": 210.60,
        "fps": 29.97
    }
    rag_pipeline.index_video_chunks(chunks, video_meta)
    
    # Retrieve results
    query = "What is natural language processing?"
    results = rag_pipeline.retrieve(query, top_k=5)
    
    # Print results
    for result in results:
        print(f"\n[Rank {result['rank']}] Score: {result['score']:.3f}")
        print(f"Time: {result['start_time']:.1f}s - {result['end_time']:.1f}s")
        print(f"Description: {result['description']}")
        print(f"Text: {result['text'][:100]}...")
        if result['associated_frames']:
            print(f"Associated Frames: {len(result['associated_frames'])}")
    
    # Save index
    rag_pipeline.save_index("output/rag_index")
