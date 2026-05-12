#!/usr/bin/env python3
"""Parse Stanford/CS PDF and PPTX files with DocumentProcessorV2.

PDFs are forced through the custom PDF reader path. PPTX files use the custom
PptxParser path when available. Results are exported as markdown/parsed JSON and
a manifest maps original source paths to parser outputs for evaluation.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_ROOTS = [
    "backend/input/CS131_notes_zh-CN-master",
    "backend/input/CS193P-Fall-2017-DEMO-master",
    "backend/input/CS228_PGM-master",
    "backend/input/CS231n-2017-master",
    "backend/input/Stanford-University-Algorithms-Design-and-Analysis-master",
    "backend/input/Stanford-University-Statistical-Learning-master",
    "backend/input/cs229-2018-autumn-main",
    "backend/input/stanford-cs161-master",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roots", nargs="*", default=DEFAULT_ROOTS)
    parser.add_argument(
        "--output-dir",
        default=str(BACKEND_ROOT / "output" / "evaluation" / "stanford_pdf_pptx_v2_processing"),
    )
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Re-parse files already marked successful in manifest.")
    parser.add_argument(
        "--pdf-content-source",
        choices=["pymupdf", "docling", "hybrid", "hybrid_batched"],
        default="hybrid",
        help="CustomPdfReader content source for PDFs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roots = [Path(root).resolve() for root in args.roots]
    out_dir = Path(args.output_dir)
    parsed_root = out_dir / "parsed"
    parsed_root.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "processing_manifest.json"
    manifest = load_manifest(manifest_path)

    files = list(discover_files(roots))
    if args.max_files:
        files = files[: args.max_files]

    DocumentProcessorV2, ProcessingConfigV2 = load_document_processor_v2()
    config = ProcessingConfigV2(
        prefer_custom_readers=True,
        pdf_content_source=args.pdf_content_source,
        docling_config=SimpleNamespace(
            enable_ocr=True,
            enable_vlm=False,
            export_images=False,
            export_tables=True,
            ocr_languages=["eng"],
        ),
        runtime_yaml={
            "inference": {"use_aws_sagemaker_docling": False},
            "processing": {"document": {"docling_backend": "local", "docling_remote": "0"}},
        },
    )

    stats = {"total_files": len(files), "processed": 0, "skipped": 0, "failed": 0}
    for idx, path in enumerate(files, 1):
        source = str(path)
        existing = manifest["documents"].get(source)
        if existing and existing.get("success") and not args.force:
            stats["skipped"] += 1
            if idx % 25 == 0:
                print_status(idx, len(files), stats)
            continue

        doc_id = stable_doc_id(path)
        doc_output_dir = parsed_root / doc_id
        doc_output_dir.mkdir(parents=True, exist_ok=True)
        processor = StanfordDocumentProcessorV2(
            input_dir=path.parent,
            output_dir=doc_output_dir,
            config=config,
        )
        processor.force_pdf_reader = path.suffix.lower() == ".pdf"
        try:
            info = processor.process_single_file(path)
            exported = processor.export_processed_document(info) if info.get("success") else {}
            record = build_manifest_record(path, doc_id, info, exported)
            manifest["documents"][source] = record
            if record["success"]:
                stats["processed"] += 1
            else:
                stats["failed"] += 1
        except Exception as exc:
            manifest["documents"][source] = {
                "source_path": source,
                "doc_id": doc_id,
                "file_type": path.suffix.lower().lstrip("."),
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "updated_at": datetime.now().isoformat(),
            }
            stats["failed"] += 1

        save_manifest(manifest_path, manifest, roots, args)
        if idx % 10 == 0 or idx == len(files):
            print_status(idx, len(files), stats)

    save_manifest(manifest_path, manifest, roots, args)
    summary_path = out_dir / "summary.json"
    summary = summarize_manifest(manifest, roots, args)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "summary": str(summary_path)}, indent=2))
    return 0


class StanfordDocumentProcessorV2:
    """Thin wrapper around DocumentProcessorV2 that can force PDFs to pdf_reader."""

    force_pdf_reader: bool = False

    def __init__(self, input_dir: Path, output_dir: Path, config: Any) -> None:
        DocumentProcessorV2, _ = load_document_processor_v2()

        class _Processor(DocumentProcessorV2):
            def __init__(self, *inner_args, **inner_kwargs):
                super().__init__(*inner_args, **inner_kwargs)
                self.force_pdf_reader = False

            def _route_pdf(self, file_path: Path) -> str:
                if self.force_pdf_reader:
                    return "pdf_reader"
                return super()._route_pdf(file_path)

        self._processor = _Processor(input_dir=input_dir, output_dir=output_dir, config=config)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._processor, name)

    @property
    def force_pdf_reader(self) -> bool:
        return bool(getattr(self._processor, "force_pdf_reader", False))

    @force_pdf_reader.setter
    def force_pdf_reader(self, value: bool) -> None:
        setattr(self._processor, "force_pdf_reader", value)


def discover_files(roots: Sequence[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        candidates = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".pdf", ".pptx"}]
        for path in sorted(candidates, key=lambda p: str(p).lower()):
            if path.name.startswith("~$"):
                continue
            yield path


def build_manifest_record(path: Path, doc_id: str, info: Dict[str, Any], exported: Dict[str, str]) -> Dict[str, Any]:
    return {
        "source_path": str(path),
        "doc_id": doc_id,
        "file_type": path.suffix.lower().lstrip("."),
        "success": bool(info.get("success")),
        "error": info.get("error"),
        "processor_used": info.get("processor_used"),
        "processing_time": info.get("processing_time"),
        "pages": info.get("pages"),
        "file_size": info.get("file_size"),
        "exported": exported,
        "markdown": exported.get("markdown"),
        "parsed_json": exported.get("parsed_json"),
        "metadata": exported.get("metadata") or exported.get("metadata_json"),
        "updated_at": datetime.now().isoformat(),
    }


def load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"metadata": {}, "documents": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("documents"), dict):
            return payload
    except Exception:
        pass
    return {"metadata": {}, "documents": {}}


def save_manifest(path: Path, manifest: Dict[str, Any], roots: Sequence[Path], args: argparse.Namespace) -> None:
    manifest["metadata"] = {
        "schema": "stanford_pdf_pptx_v2_processing_manifest",
        "version": "1.0",
        "roots": [str(root) for root in roots],
        "pdf_content_source": args.pdf_content_source,
        "updated_at": datetime.now().isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_manifest(manifest: Dict[str, Any], roots: Sequence[Path], args: argparse.Namespace) -> Dict[str, Any]:
    docs = list((manifest.get("documents") or {}).values())
    by_type: Dict[str, int] = {}
    by_processor: Dict[str, int] = {}
    success = 0
    for record in docs:
        by_type[record.get("file_type", "")] = by_type.get(record.get("file_type", ""), 0) + 1
        by_processor[str(record.get("processor_used") or "none")] = by_processor.get(str(record.get("processor_used") or "none"), 0) + 1
        if record.get("success"):
            success += 1
    failures = [record for record in docs if not record.get("success")]
    return {
        "document_count": len(docs),
        "success_count": success,
        "failure_count": len(failures),
        "by_type": by_type,
        "by_processor": by_processor,
        "pdf_content_source": args.pdf_content_source,
        "failures_preview": failures[:20],
    }


def print_status(idx: int, total: int, stats: Dict[str, int]) -> None:
    print(
        f"processed {idx}/{total}; parsed={stats['processed']} skipped={stats['skipped']} failed={stats['failed']}",
        flush=True,
    )


def stable_doc_id(path: Path) -> str:
    import hashlib

    return hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:16]


def load_document_processor_v2():
    package_name = "src.processor"
    if package_name not in sys.modules:
        pkg = types.ModuleType(package_name)
        pkg.__path__ = [str(BACKEND_ROOT / "src" / "processor")]
        sys.modules[package_name] = pkg
    module_name = "src.processor.document_processor_v2"
    if module_name in sys.modules:
        module = sys.modules[module_name]
    else:
        module_path = BACKEND_ROOT / "src" / "processor" / "document_processor_v2.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return module.DocumentProcessorV2, module.ProcessingConfigV2


if __name__ == "__main__":
    os.environ.setdefault("USE_AWS_SAGEMAKER_DOCLING", "0")
    raise SystemExit(main())
