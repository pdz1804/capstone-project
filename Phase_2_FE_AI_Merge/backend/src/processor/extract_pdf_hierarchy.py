#!/usr/bin/env python3
"""
PyMuPDF Document Hierarchy Extractor
Extracts table of contents, bookmarks, and structural information from PDF
"""

import fitz  # PyMuPDF
import json
from pathlib import Path


def extract_toc(pdf_path):
    """Extract Table of Contents (bookmarks/outline) from PDF"""
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    doc.close()
    return toc


def print_toc_hierarchy(toc, indent=0):
    """Pretty print TOC with indentation showing hierarchy"""
    for item in toc:
        level, title, page = item[0], item[1], item[2]
        print("  " * (level - 1) + f"├─ {title} (page {page})")


def extract_text_with_structure(pdf_path, max_pages=None):
    """Extract text with block information and structure"""
    doc = fitz.open(pdf_path)
    structure = []

    pages_to_process = min(max_pages or doc.page_count, doc.page_count)

    for page_num in range(pages_to_process):
        page = doc[page_num]
        blocks = page.get_text("blocks")

        page_data = {
            "page": page_num + 1,
            "blocks": []
        }

        for block in blocks:
            if block[4] != "":  # Skip empty blocks
                page_data["blocks"].append({
                    "text": block[4][:100],  # First 100 chars
                    "bbox": block[:4],
                    "is_text": block[6] == 0
                })

        structure.append(page_data)

    doc.close()
    return structure


def extract_metadata(pdf_path):
    """Extract PDF metadata"""
    doc = fitz.open(pdf_path)
    metadata = {
        "title": doc.metadata.get("title", "N/A"),
        "author": doc.metadata.get("author", "N/A"),
        "subject": doc.metadata.get("subject", "N/A"),
        "keywords": doc.metadata.get("keywords", "N/A"),
        "creator": doc.metadata.get("creator", "N/A"),
        "producer": doc.metadata.get("producer", "N/A"),
        "page_count": doc.page_count,
        "is_pdf": doc.is_pdf,
        "has_toc": bool(doc.get_toc())
    }
    doc.close()
    return metadata


def main():
    pdf_path = "/Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project/Phase_2_FE_AI_Merge/backend/2412.19437v2.pdf"

    print("=" * 60)
    print("PDF HIERARCHY EXTRACTION - PyMuPDF Analysis")
    print("=" * 60)

    # Extract and display metadata
    print("\n📄 PDF METADATA:")
    print("-" * 60)
    metadata = extract_metadata(pdf_path)
    for key, value in metadata.items():
        print(f"  {key:20}: {value}")

    # Extract and display TOC
    print("\n📚 TABLE OF CONTENTS (OUTLINE/BOOKMARKS):")
    print("-" * 60)
    toc = extract_toc(pdf_path)

    if toc:
        print_toc_hierarchy(toc)
        # Save TOC to JSON
        toc_json = [{"level": item[0], "title": item[1], "page": item[2]} for item in toc]
        with open("pdf_toc.json", "w") as f:
            json.dump(toc_json, f, indent=2)
        print(f"\n  ✓ TOC saved to pdf_toc.json")
    else:
        print("  ⚠ No table of contents found in PDF")

    # Extract text structure from first few pages
    print("\n📖 TEXT STRUCTURE (First 3 pages):")
    print("-" * 60)
    structure = extract_text_with_structure(pdf_path, max_pages=3)
    for page_data in structure:
        print(f"\n  Page {page_data['page']} ({len(page_data['blocks'])} blocks):")
        for i, block in enumerate(page_data['blocks'][:3]):  # Show first 3 blocks
            print(f"    Block {i+1}: {block['text'][:60]}...")


if __name__ == "__main__":
    main()
