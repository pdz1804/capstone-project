
# Capstone Project - 251

## Overview

A small, robust Python script to batch‑download research PDFs and auto‑name them using site‑specific rules (arXiv, ACL Anthology, CVF/OpenAccess, ACM DL, AAAI OJS). It verifies real PDFs, retries on network hiccups, and writes a CSV log + end‑of‑run stats.

## Features

- Deduplicates input URLs.
- Smart, human‑readable filenames via domain heuristics (+ PDF metadata fallback).
- PDF validation (signature check).
- Automatic retries with exponential backoff.
- Clear summary & `download_log.csv` (success/failure + reasons).
- Collision‑safe filenames (`(2)`, `(3)`, …).

## Requirements

Create `requirements.txt`:

```
requests>=2.32.3
tqdm>=4.66.4
beautifulsoup4>=4.12.3
lxml>=5.3.0
python-slugify>=8.0.4
pypdf>=4.2.0
tenacity>=9.0.0
```

## Install

```bash
# (optional) create venv
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
# .\.venv\Scripts\activate

pip install -r requirements.txt
```

## Usage

```bash
python download_papers.py --out downloads
```

- PDFs saved to `downloads/`.
- A CSV log appears at `downloads/download_log.csv`.

> The script uses the `RAW_URLS` list embedded at the top of `download_papers.py`. Add/remove URLs there.

## Output & Naming

- **Naming order**: site heuristic → PDF `/Title` metadata → `Content-Disposition` filename → URL tail.
- Examples:
  - `2024-title-arxiv-2407.12345v1.pdf`
  - `2023-title-aclanthology-2023.emnlp-main.825.pdf`
  - `transform-retrieve-generate-cvpr2022.pdf`

## Troubleshooting

- **`not-pdf-content`**: The URL responded with HTML or a gated page (cookies/paywall). Open it in a browser or use an alternative PDF link.
- **Network errors**: The script auto‑retries. Persistent failures will be listed in the summary and CSV with reasons.
- **Duplicate names**: The script appends `(2)`, `(3)`, etc.

## Customize

- Read URLs from a file, add concurrency, or route outputs by venue/year—happy to extend the script if you want.
