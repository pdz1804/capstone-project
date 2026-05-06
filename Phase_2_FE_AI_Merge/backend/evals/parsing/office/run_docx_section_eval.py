"""CLI for DOCX parsing/chunking section coverage evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.paths import load_yaml_config, merged_runtime_settings, workspace_paths_for_user
from src.evaluation.docx_section_coverage import (
    DocxSectionCoverageConfig,
    run_docx_section_coverage,
)


def _default_input_path() -> Path:
    return workspace_paths_for_user().rag_ready_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate DOCX parsing/chunking quality via section coverage.",
    )
    parser.add_argument(
        "--input",
        default=str(_default_input_path()),
        help="Path to a stage4 DOCX doc dir, a docx_chunks.json file, or a corpus root.",
    )
    parser.add_argument(
        "--output-dir",
        default="output/evaluation/docx_section_eval",
        help="Directory for JSON/CSV evaluation outputs.",
    )
    parser.add_argument(
        "--parsed-root",
        default=None,
        help="Optional override for the parsed DOCX JSON root directory.",
    )
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--max-sections-per-document", type=int, default=None)
    parser.add_argument("--questions-per-section", type=int, default=20)
    parser.add_argument("--min-section-chars", type=int, default=120)
    parser.add_argument("--section-pass-threshold", type=float, default=0.8)
    parser.add_argument("--provider", default=None, help="Judge provider, e.g. openai or bedrock.")
    parser.add_argument("--model", default=None, help="Judge model override.")
    parser.add_argument(
        "--calibration-sample-size",
        type=int,
        default=0,
        help="Sample this many sections for human verification artifacts.",
    )
    parser.add_argument(
        "--human-labels-path",
        default=None,
        help="Optional JSON file with human labels for calibration comparison.",
    )
    parser.add_argument("--random-seed", type=int, default=7)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    runtime = merged_runtime_settings(load_yaml_config())
    generation = runtime.get("generation", {}) or {}

    provider = (args.provider or generation.get("provider") or "openai").strip().lower()
    model = (args.model or generation.get("model") or "").strip() or None

    config = DocxSectionCoverageConfig(
        input_path=str(Path(args.input).resolve()),
        output_dir=str(Path(args.output_dir).resolve()),
        parsed_root=str(Path(args.parsed_root).resolve()) if args.parsed_root else None,
        max_documents=args.max_documents,
        max_sections_per_document=args.max_sections_per_document,
        questions_per_section=args.questions_per_section,
        min_section_chars=args.min_section_chars,
        section_pass_threshold=args.section_pass_threshold,
        provider=provider,
        model=model,
        calibration_sample_size=args.calibration_sample_size,
        human_labels_path=str(Path(args.human_labels_path).resolve()) if args.human_labels_path else None,
        random_seed=args.random_seed,
    )

    results, calibration = run_docx_section_coverage(config)
    summary = {
        "document_count": len(results),
        "documents": [result.document_id for result in results],
        "output_dir": config.output_dir,
        "calibration_status": calibration.status,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
