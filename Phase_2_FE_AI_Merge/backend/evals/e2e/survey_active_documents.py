"""Survey active documents to check sections and text content."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.paths import merged_runtime_settings, sanitize_storage_user_id, workspace_paths_for_user
from app.services.document_lineage_service import DocumentLineageService
from app.services.processed_documents_service import build_processed_documents_snapshot
from app.services.processed_markdown_service import gather_processed_markdown_context
import re


def _doc_matches_active(lineage: DocumentLineageService, doc_id: str) -> bool:
    row = lineage.lineage_for_source(doc_id)
    if row is None:
        return True
    return bool(row.get("active_for_retrieval", True))


def _flatten_sections_from_markdown(markdown_text: str, doc_id: str) -> list:
    """Flatten sections from stage1_normalized markdown."""
    sections = []
    lines = markdown_text.split('\n')
    heading_re = re.compile(r'^(#{1,6})\s+(.+)$')
    
    current_section = None
    current_content = []
    breadcrumbs = []
    section_index = 0
    
    for line in lines:
        match = heading_re.match(line)
        if match:
            # Save previous section
            if current_section and current_content:
                current_section["source_text"] = '\n'.join(current_content).strip()
                sections.append(current_section)
                section_index += 1
            
            # Start new section
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            
            # Update breadcrumbs
            if level == 1:
                breadcrumbs = [heading_text]
            else:
                while len(breadcrumbs) >= level:
                    breadcrumbs.pop()
                breadcrumbs.append(heading_text)
            
            current_section = {
                "doc_id": doc_id,
                "section_id": f"{doc_id}:section:{section_index:04d}",
                "section_index": section_index,
                "heading_text": heading_text,
                "heading_level": level,
                "heading_breadcrumb": list(breadcrumbs),
            }
            current_content = []
        elif current_section is not None:
            current_content.append(line)
    
    # Save last section
    if current_section and current_content:
        current_section["source_text"] = '\n'.join(current_content).strip()
        sections.append(current_section)
    
    # If no sections found, create a default one
    if not sections:
        sections.append({
            "doc_id": doc_id,
            "section_id": f"{doc_id}:section:0000",
            "section_index": 0,
            "heading_text": "Document",
            "heading_level": 1,
            "heading_breadcrumb": ["Document"],
            "source_text": markdown_text.strip(),
        })
    
    return sections


def survey_documents(user_id: str, max_context_chars: int = 80_000):
    """Survey active documents and report sections."""
    sanitized_user_id = sanitize_storage_user_id(user_id)
    paths = workspace_paths_for_user(sanitized_user_id)
    lineage = DocumentLineageService(sanitized_user_id)
    
    print(f"{'=' * 80}")
    print(f"SURVEY DOCUMENTS FOR USER: {user_id}")
    print(f"{'=' * 80}\n")
    
    # Get active documents
    snapshot = build_processed_documents_snapshot(sanitized_user_id, include_preview=False)
    docs = []
    
    for doc in snapshot.get("documents") or []:
        doc_id = str(doc.get("id") or "").strip()
        if not doc_id or doc_id.startswith("__"):
            continue
        if not _doc_matches_active(lineage, doc_id):
            continue
        
        # Get stage1_normalized markdown
        ctx = gather_processed_markdown_context(sanitized_user_id, doc_id, max_context_chars)
        if not ctx.strip():
            continue
        
        docs.append({
            "doc_id": doc_id,
            "display_name": str(doc.get("display_name") or doc_id),
            "total_files": int(doc.get("total_files") or 0),
            "context": ctx,
        })
    
    print(f"Total ACTIVE documents: {len(docs)}\n")
    
    if not docs:
        print("No active documents found!")
        return
    
    # Process each document
    for doc_idx, doc in enumerate(docs, 1):
        doc_id = doc["doc_id"]
        display_name = doc["display_name"]
        
        print(f"\n{'=' * 80}")
        print(f"DOCUMENT {doc_idx}/{len(docs)}: {display_name}")
        print(f"ID: {doc_id}")
        print(f"Total files: {doc['total_files']}")
        print(f"{'=' * 80}\n")
        
        # Flatten sections
        sections = _flatten_sections_from_markdown(doc["context"], doc_id)
        print(f"Total sections: {len(sections)}\n")
        
        # Analyze each section
        short_sections = []
        
        for section_idx, section in enumerate(sections, 1):
            source_text = section.get("source_text", "")
            text_length = len(source_text)
            heading = section.get("heading_text", "Untitled")
            
            print(f"  Section {section_idx}: {heading}")
            print(f"    ID: {section['section_id']}")
            print(f"    Level: {section.get('heading_level', 1)}")
            print(f"    Text length: {text_length} chars")
            print(f"    Breadcrumb: {' > '.join(section.get('heading_breadcrumb', []))}")
            
            # Check if section is too short
            if text_length < 100:
                print(f"    ⚠️  WARNING: Very short section (< 100 chars)!")
                short_sections.append(section)
            elif text_length < 500:
                print(f"    ⚠️  WARNING: Short section (< 500 chars) - may not contain enough content")
                short_sections.append(section)
            else:
                print(f"    ✓ OK")
            
            # Show preview
            if source_text:
                preview = source_text[:200].replace('\n', ' ')
                print(f"    Preview: {preview}{'...' if len(source_text) > 200 else ''}")
            
            print()
        
        # Summary for this document
        if short_sections:
            print(f"\n⚠️  Document Summary: {len(short_sections)} short/empty sections found")
            for idx, sec in enumerate(short_sections, 1):
                print(f"  {idx}. {sec.get('heading_text', 'Untitled')} - {len(sec.get('source_text', ''))} chars")
        else:
            print(f"\n✓ All sections have sufficient content")
    
    # Overall summary
    print(f"\n{'=' * 80}")
    print("OVERALL SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total documents: {len(docs)}")
    total_sections = sum(len(_flatten_sections_from_markdown(doc["context"], doc["doc_id"])) for doc in docs)
    print(f"Total sections: {total_sections}")
    
    # Find all short sections across all documents
    all_short = []
    for doc in docs:
        sections = _flatten_sections_from_markdown(doc["context"], doc["doc_id"])
        for section in sections:
            if len(section.get("source_text", "")) < 500:
                all_short.append({
                    "doc_id": doc["doc_id"],
                    "doc_name": doc["display_name"],
                    "section": section.get("heading_text", "Untitled"),
                    "length": len(section.get("source_text", ""))
                })
    
    if all_short:
        print(f"\n⚠️  SECTIONS WITH LOW CONTENT (< 500 chars): {len(all_short)}")
        for idx, item in enumerate(all_short, 1):
            print(f"  {idx}. [{item['doc_name']}] {item['section']} - {item['length']} chars")
    else:
        print(f"\n✓ All sections have sufficient content (≥ 500 chars)")


if __name__ == "__main__":

    import argparse
    
    parser = argparse.ArgumentParser(description="Survey active documents for document intelligence evaluation")
    parser.add_argument("--user-id", required=True, help="User ID to survey")
    
    args = parser.parse_args()
    survey_documents(args.user_id)
