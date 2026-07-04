# Git History Rewrite Runbook

Use this only after the working tree cleanup is reviewed, committed, and data is safely uploaded to Drive. Do not run history rewrite with uncommitted or staged cleanup work.

## Prerequisites

Install `git-filter-repo`:

```bash
python -m pip install git-filter-repo
```

Make a backup clone or archive before continuing. History rewrite changes commit hashes and requires force-push.

## Rewrite Command

Run from the repository root:

```bash
git filter-repo \
  --path Phase_1/data/ \
  --path Phase_2/data/ \
  --path Phase_2_AI_SERVICE_FOLDER/ \
  --path Phase_2_FE_AI_Merge/ \
  --path Phase_2_FE_IMPLEMENT/ \
  --path Phase_2_PDZ_001_Test_Media_RAG/ \
  --path Phase_2_PDZ_003_Test_Qdrant_Cloud/ \
  --path-glob '*/input/*' \
  --path-glob '*/output/*' \
  --path-glob '*/outputs/*' \
  --path-glob '*/results/*' \
  --path-glob '*/.work/*' \
  --path-glob '*/test_parsing/*' \
  --path-glob '*.pkl' \
  --path-glob '*.pickle' \
  --path-glob '*.bin' \
  --path-glob '*.faiss' \
  --path-glob '*.index' \
  --path-glob '*.onnx' \
  --path-glob '*.pt' \
  --path-glob '*.pth' \
  --path-glob '*.safetensors' \
  --path-glob '*.npy' \
  --path-glob '*.npz' \
  --path-glob '*.parquet' \
  --path-glob '*.jsonl' \
  --invert-paths
```

Then repack:

```bash
git gc --prune=now --aggressive
```

## Verification

```bash
git ls-files | grep -E '(^|/)(input|output|outputs|results|data|\.work|test_parsing)/'
git ls-files | grep -E '\.(pkl|pickle|bin|faiss|index|onnx|pt|pth|safetensors|npy|npz|parquet|jsonl)$'
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize:disk) %(rest)' | sort -nr -k3 | head -50
du -sh .git Phase_1 Phase_2 docs
```

After the rewritten branch is validated, force-push intentionally and have collaborators reclone or reset to the new history.
