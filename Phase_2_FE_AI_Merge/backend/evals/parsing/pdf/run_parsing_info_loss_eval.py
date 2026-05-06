"""CLI for parsing information-loss evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.evaluation.parsing_info_loss import load_eval_config, run_parsing_info_loss_eval


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate parsed JSON against original-file or OmniDocBench GT.")
    parser.add_argument("--config", default=str(BACKEND_ROOT / "config" / "parsing_info_loss_eval.yaml"))
    parser.add_argument("--original-root", default=str(BACKEND_ROOT / "output" / "processing" / "stage1_normalized" / "original_files"))
    parser.add_argument("--parsed-root", default=str(BACKEND_ROOT / "output" / "processing" / "stage1_normalized"))
    parser.add_argument("--output-dir", default=str(BACKEND_ROOT / "output" / "evaluation" / "parsing_info_loss"))
    parser.add_argument("--doc-id", default=None)
    parser.add_argument("--modalities", default=None, help="Comma-separated modalities, e.g. docx,xlsx,pptx,pdf")
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--pdf-reference", choices=["weak", "omnidocbench"], default=None)
    parser.add_argument("--omnidocbench-gt", default=None)
    parser.add_argument("--omnidocbench-image-root", default=None)
    parser.add_argument("--disable", action="append", default=[], help="Disable a score group. Can be repeated.")
    parser.add_argument("--weight", action="append", default=[], help="Override group weight as name=value. Can be repeated.")
    return parser


def _parse_weights(items: list[str]) -> dict[str, float]:
    out = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --weight value: {item!r}; expected name=value")
        name, value = item.split("=", 1)
        out[name.strip()] = float(value)
    return out


def main() -> int:
    args = build_parser().parse_args()
    modalities = [m.strip() for m in args.modalities.split(",") if m.strip()] if args.modalities else None
    config = load_eval_config(
        config_path=args.config,
        original_root=str(Path(args.original_root).resolve()),
        parsed_root=str(Path(args.parsed_root).resolve()),
        output_dir=str(Path(args.output_dir).resolve()),
        doc_id=args.doc_id,
        modalities=modalities,
        max_documents=args.max_documents,
        pdf_reference=args.pdf_reference,
        omnidocbench_gt=args.omnidocbench_gt,
        omnidocbench_image_root=args.omnidocbench_image_root,
        weights=_parse_weights(args.weight),
        disabled_groups=args.disable,
    )
    written = run_parsing_info_loss_eval(config)
    print(json.dumps({name: str(path) for name, path in written.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
