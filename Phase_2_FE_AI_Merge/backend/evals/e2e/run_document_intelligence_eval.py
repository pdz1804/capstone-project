"""CLI for Document Intelligence Evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.paths import load_yaml_config, merged_runtime_settings, workspace_paths_for_user
from src.evaluation.document_intelligence import (
    DocumentIntelligenceEvalConfig,
    run_document_intelligence_eval,
)
from app.services.document_intelligence_eval_service import DocumentIntelligenceEvalService


def build_parser() -> argparse.ArgumentParser:
    paths = workspace_paths_for_user()
    parser = argparse.ArgumentParser(description="Run document intelligence evaluation phases.")
    parser.add_argument("--input", default=str(paths.rag_ready_dir))
    parser.add_argument(
        "--parsed-root",
        default=str(paths.processing_dir / "stage1_normalized"),
        help="Path to stage1_normalized or a direct parsed JSON root.",
    )
    parser.add_argument(
        "--output-dir",
        default="output/evaluation/document_intelligence_eval",
    )
    parser.add_argument(
        "--phase",
        choices=["e2e_qa", "all"],
        default="all",
    )
    parser.add_argument("--questions-per-section", type=int, default=10)
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--max-sections-per-document", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--retriever-type", default="hybrid")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--user-id", default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    runtime = merged_runtime_settings(load_yaml_config())
    generation = runtime.get("generation", {}) or {}
    provider = (args.provider or generation.get("provider") or "openai").strip().lower()
    model = (args.model or generation.get("model") or "").strip() or None

    # Use database-based service if user_id is provided
    if args.user_id:
        print(f"Running evaluation for user_id: {args.user_id} (database mode)")
        service = DocumentIntelligenceEvalService(yaml_config=runtime, user_id=args.user_id)
        run = service.create_run(
            questions_per_section=args.questions_per_section,
            max_documents=args.max_documents,
            max_sections_per_document=args.max_sections_per_document,
            top_k=args.top_k,
            retriever_type=args.retriever_type,
            provider=provider,
            model=model,
        )
        print(
            json.dumps(
                {
                    "run_id": run.get("run_id"),
                    "user_id": run.get("user_id"),
                    "status": run.get("status"),
                    "phase": args.phase,
                    "output_dir": run.get("artifact_path"),
                    "summary": run.get("summary"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    # Original file-based mode
    print("Running evaluation in file-based mode")
    config = DocumentIntelligenceEvalConfig(
        input_path=str(Path(args.input).resolve()),
        parsed_root=str(Path(args.parsed_root).resolve()),
        output_dir=str(Path(args.output_dir).resolve()),
        phase=args.phase,
        questions_per_section=args.questions_per_section,
        max_documents=args.max_documents,
        max_sections_per_document=args.max_sections_per_document,
        top_k=args.top_k,
        retriever_type=args.retriever_type,
        provider=provider,
        model=model,
        user_id=args.user_id,
    )
    written = run_document_intelligence_eval(config)
    print(
        json.dumps(
            {
                "phase": args.phase,
                "output_dir": config.output_dir,
                "reports": sorted(written.keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
