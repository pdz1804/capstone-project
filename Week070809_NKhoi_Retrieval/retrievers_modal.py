import modal
import os
import sys
import shutil
from pathlib import Path

# Define the app
app = modal.App("retriever-evaluation")

# Define the image with dependencies
image = (
    modal.Image.from_registry("nvidia/cuda:12.2.0-devel-ubuntu22.04", add_python="3.11")
    .apt_install("build-essential", "git")
    .pip_install(
        "torch",
        "transformers",
        "sentence-transformers",
        "rank_bm25",
        "datasets",
        "RAGatouille[langchain]==0.0.9.post2",
        "langchain<0.2",
        "langchain-core<0.2",
        "tqdm",
        "numpy",
        "scikit-learn",
        "psutil"
    )
    .env({"CUDA_HOME": "/usr/local/cuda"})
    # Add the retriever script
    .add_local_file("retrieval/0506/retriever.py", "/root/retriever.py")
)

# Define the volume for persistent storage
# We use a volume to store the MS MARCO dataset and results
volume = modal.Volume.from_name("ms-marco-data", create_if_missing=True)

# Paths
VOLUME_MOUNT_PATH = "/data"
DATA_PATH = "/data/data"  # The actual path to data inside the volume
SCRIPT_PATH = "/root/retriever.py"

@app.function(
    image=image,
    gpu="T4",
    volumes={VOLUME_MOUNT_PATH: volume},
    timeout=7200, # 2 hours
    env={"BASE_PATH": DATA_PATH}
)
def run_evaluation(
    colbert: bool = False,
    bm25: bool = False,
    minilm: bool = False,
    bgesmall: bool = False,
    hybrid: bool = False,
    rerank_bge: bool = False,
    rerank_minilm_ce: bool = False,
    num_corpus: int = 50000,
    num_query: int = 1000,
    k_metric: int = 3,
    k_retrieval: int = 30
):
    """
    Run the retrieval evaluation on Modal GPU.
    """
    import subprocess
    
    print(f"Checking data in {DATA_PATH}...")
    # Debug: List all files in the mount path to find where data actually is
    print(f"--- Directory structure of {VOLUME_MOUNT_PATH} ---")
    for root, dirs, files in os.walk(VOLUME_MOUNT_PATH):
        level = root.replace(VOLUME_MOUNT_PATH, '').count(os.sep)
        indent = ' ' * 4 * (level)
        print(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            print(f'{subindent}{f}')
    print("------------------------------------------------")

    if not os.path.exists(os.path.join(DATA_PATH, "corpus.jsonl")):
        # Try to find where corpus.jsonl is
        found_path = None
        for root, dirs, files in os.walk(DATA_PATH):
            if "corpus.jsonl" in files:
                found_path = root
                break
        
        if found_path:
            print(f"FOUND corpus.jsonl in {found_path}. Please update DATA_MOUNT_PATH or volume structure.")
            # We can try to temporarily set BASE_PATH to this found path for this run
            os.environ["BASE_PATH"] = found_path
            print(f"Temporarily setting BASE_PATH to {found_path}")
        else:
            print(f"WARNING: corpus.jsonl not found anywhere in {DATA_MOUNT_PATH}.")
            print("Please run the following command locally to upload data:")
            print(f"  modal volume put ms-marco-data retrieval/0506/ms_marco_val /")
    
    # Construct command
    cmd = ["python", SCRIPT_PATH]
    
    if colbert: cmd.append("--colbert")
    if bm25: cmd.append("--bm25")
    if minilm: cmd.append("--minilm")
    if bgesmall: cmd.append("--bgesmall")
    if hybrid: cmd.append("--hybrid")
    if rerank_bge: cmd.append("--rerank_bge")
    if rerank_minilm_ce: cmd.append("--rerank_minilm_ce")
    
    cmd.extend(["--num_corpus", str(num_corpus)])
    cmd.extend(["--num_query", str(num_query)])
    cmd.extend(["--k_metric", str(k_metric)])
    cmd.extend(["--k_retrieval", str(k_retrieval)])
    
    print(f"Running command: {' '.join(cmd)}")
    
    # Stream output
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    for line in process.stdout:
        print(line, end="")
    
    return_code = process.wait()
    if return_code != 0:
        raise Exception(f"Command failed with return code {return_code}")
        
    # Commit volume to save results
    volume.commit()
    print("Results saved to volume.")

@app.local_entrypoint()
def main(
    colbert: bool = False,
    bm25: bool = False,
    minilm: bool = False,
    bgesmall: bool = False,
    hybrid: bool = False,
    rerank_bge: bool = False,
    rerank_minilm_ce: bool = False,
    all: bool = False
):
    """
    CLI entrypoint.
    
    Usage:
      # 1. Upload data first (run locally)
      modal volume put ms-marco-data retrieval/0506/ms_marco_val /data/ms_marco_val
      
      # 2. Run evaluations
      modal run retrieval/0506/retriever_modal.py --bm25 --minilm
      
      # Run everything
      modal run retrieval/0506/retriever_modal.py --all
    """
    if all:
        colbert = True
        bm25 = True
        minilm = True
        bgesmall = True
        hybrid = True
        rerank_bge = True
        rerank_minilm_ce = True
    
    if not any([colbert, bm25, minilm, bgesmall, hybrid, rerank_bge, rerank_minilm_ce]):
        print("❌ No evaluation flags provided.")
        print("Usage:")
        print("  modal volume put ms-marco-data retrieval/0506/ms_marco_val /data/ms_marco_val  # Upload data")
        print("  modal run retrieval/0506/retriever_modal.py --all               # Run all evals")
        return

    print("🚀 Starting evaluation on GPU...")
    run_evaluation.remote(
        colbert=colbert,
        bm25=bm25,
        minilm=minilm,
        bgesmall=bgesmall,
        hybrid=hybrid,
        rerank_bge=rerank_bge,
        rerank_minilm_ce=rerank_minilm_ce
    )
