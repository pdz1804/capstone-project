"""Run document intelligence evaluation against a real user workspace."""

import argparse
import json
import os
import sys
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_root))

from app.services.document_intelligence_eval_service import DocumentIntelligenceEvalService
from app.core.paths import merged_runtime_settings


def _load_backend_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(backend_root / ".env")
    except Exception:
        return


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run document intelligence evaluation against the same per-user workspace used by the API.",
    )
    parser.add_argument("--user-id", default=os.getenv("DEFAULT_STORAGE_USER_ID", "default"))
    parser.add_argument("--max-documents", type=int, default=5)
    parser.add_argument("--max-sections-per-document", type=int, default=5)
    parser.add_argument("--questions-per-section", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--retriever-type", choices=["bm25", "dense", "hybrid", "all"], default="all")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--summary-output",
        default=str(backend_root / "output" / "evaluation" / "document_intelligence_workspace_summary.json"),
        help="Path for the compact comparison summary.",
    )
    return parser.parse_args()

def main():
    _load_backend_env()
    args = _parse_args()

    # Load config
    cfg = merged_runtime_settings()
    user_id = str(args.user_id or "default").strip()

    print("=" * 80)
    print("DOCUMENT INTELLIGENCE EVALUATION")
    print("=" * 80)
    print(f"User/workspace: {user_id}")

    # Create service
    service = DocumentIntelligenceEvalService(yaml_config=cfg, user_id=user_id)

    # Check if there are active documents
    docs = service._active_documents(max_documents=args.max_documents)
    print(f"\nFound {len(docs)} active documents:")
    for doc in docs:
        print(f"  - {doc['doc_id']}: {doc['display_name']} ({doc['total_files']} files)")

    if not docs:
        print("\n❌ No active documents found. Please process some documents first.")
        return

    # Run evaluation with different retriever types
    retriever_types = ["bm25", "dense", "hybrid"] if args.retriever_type == "all" else [args.retriever_type]
    results_summary = {}

    for retriever_type in retriever_types:
        print("\n" + "=" * 80)
        print(f"Running evaluation with {retriever_type.upper()} retriever...")
        print("=" * 80)

        try:
            run = service.create_run(
                top_k=args.top_k,
                questions_per_section=args.questions_per_section,
                max_documents=args.max_documents,
                max_sections_per_document=args.max_sections_per_document,
                retriever_type=retriever_type,
                provider=args.provider,
                model=args.model,
            )

            print(f"\n✅ Run completed: {run['run_id']}")
            print(f"   Status: {run['status']}")
            print(f"   User ID: {run.get('user_id', 'N/A')}")
            
            summary = run.get('summary', {})
            print(f"\n📊 Summary:")
            print(f"   Total questions: {summary.get('total_questions', 0)}")
            print(f"   Total documents: {summary.get('total_documents', 0)}")
            print(f"   Total sections: {summary.get('total_sections', 0)}")

            # Print distributions
            distributions = summary.get('distributions', {})
            if distributions:
                print("\n   Distributions:")
                for metric_name, metric_dist in distributions.items():
                    print(f"\n   {metric_name.upper()}:")
                    for label, count in metric_dist.items():
                        print(f"      {label}: {count}")

            results_summary[retriever_type] = {
                'run_id': run['run_id'],
                'summary': summary,
            }

        except Exception as e:
            print(f"\n❌ Error running {retriever_type} evaluation: {e}")
            import traceback
            traceback.print_exc()

    # Print comparison table
    print("\n" + "=" * 80)
    print("COMPARISON TABLE")
    print("=" * 80)

    # Header
    print(f"{'Retriever':<12} {'Total Qs':<10} {'Correct':<10} {'Partially Correct':<18} {'Incorrect':<10} {'Faithful':<10} {'Hallucinated':<15} {'Fully Supported':<16}")

    for retriever_type in retriever_types:
        if retriever_type not in results_summary:
            continue

        summary = results_summary[retriever_type]['summary'].get('distributions', {})
        
        total_questions = summary.get('total_questions', 0)
        correctness = summary.get('correctness', {})
        faithfulness = summary.get('faithfulness', {})
        answer_support = summary.get('answer_support', {})

        correct = correctness.get('correct', 0)
        partially_correct = correctness.get('partially_correct', 0)
        incorrect = correctness.get('incorrect', 0)
        faithful = faithfulness.get('faithful', 0)
        hallucinated = faithfulness.get('hallucinated', 0)
        fully_supported = answer_support.get('fully_supported', 0)

        print(f"{retriever_type:<12} {total_questions:<10} {correct:<10} {partially_correct:<18} {incorrect:<10} {faithful:<10} {hallucinated:<15} {fully_supported:<16}")

    print("\n" + "=" * 80)
    print("✅ Evaluation complete!")
    print("=" * 80)

    # Save summary
    output_path = Path(args.summary_output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results_summary, f, indent=2, default=str)
    print(f"\n📁 Results saved to: {output_path.absolute()}")

if __name__ == "__main__":
    main()
