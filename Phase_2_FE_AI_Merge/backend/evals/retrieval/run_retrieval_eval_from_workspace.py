"""Run retrieval evaluation against a real user workspace."""

import argparse
import json
import os
import sys
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_root))

from app.core.paths import merged_runtime_settings
from app.services.retrieval_eval_service import RetrievalEvalService


def _load_backend_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(backend_root / ".env")
    except Exception:
        return


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retrieval eval against the same per-user workspace used by the API.")
    parser.add_argument(
        "--user-id",
        default=os.getenv("DEFAULT_STORAGE_USER_ID", "default"),
        help="Storage/Firebase user id. Must match the frontend X-User-Id header.",
    )
    parser.add_argument("--max-documents", type=int, default=5)
    parser.add_argument("--questions-per-category", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--retriever-type", choices=["bm25", "dense", "hybrid", "all"], default="all")
    parser.add_argument(
        "--summary-output",
        default=str(backend_root / "output" / "evaluation" / "retrieval_eval_workspace_summary.json"),
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
    print("RETRIEVAL EVALUATION")
    print("=" * 80)
    print(f"User/workspace: {user_id}")

    # Create service
    service = RetrievalEvalService(yaml_config=cfg, user_id=user_id)

    # Check if there are active documents (skip knowledge lookup for speed)
    docs = service._active_documents(max_documents=args.max_documents, skip_knowledge_lookup=True)
    print(f"\nFound {len(docs)} active documents:")
    for doc in docs:
        kg = doc.get("knowledge") or {}
        kg_label = f" | knowledge={kg.get('knowledge_id') or kg.get('title')}" if kg else ""
        print(f"  - {doc['doc_id']}: {doc['display_name']} ({doc['total_files']} files){kg_label}")

    if not docs:
        print("\n❌ No active documents found for this user.")
        print("   Pass --user-id with the same uid sent by the frontend X-User-Id header.")
        return

    # Run evaluation with different retriever types (each runs both text and image search)
    retriever_types = ["bm25", "dense", "hybrid"] if args.retriever_type == "all" else [args.retriever_type]
    results_summary = {}

    for retriever_type in retriever_types:
        print("\n" + "=" * 80)
        print(f"Running evaluation with {retriever_type.upper()} retriever...")
        print("=" * 80)

        try:
            run = service.create_run(
                top_k=args.top_k,
                k_values=[1, 3, 5, 10],
                retriever_type=retriever_type,
                questions_per_category=args.questions_per_category,
                max_documents=args.max_documents,
                skip_knowledge_lookup=True,
            )

            print(f"\n✅ Run completed: {run['run_id']}")
            print(f"   Status: {run['status']}")
            print(f"   Questions generated: {len(run.get('questions', []))}")
            print(f"   Results: {len(run.get('results', []))}")

            # Print metrics
            metrics = run.get('metrics', {})
            print(f"\n📊 Metrics for {retriever_type.upper()}:")

            llm_metrics = metrics.get('llm', {})
            if llm_metrics:
                print("\n   LLM Judgments:")
                for modality in ['text', 'image']:
                    mod_metrics = llm_metrics.get(modality, {})
                    aggregate = mod_metrics.get('aggregate', {})
                    if aggregate:
                        print(f"\n   {modality.upper()} Modality:")
                        for metric_name, metric_data in aggregate.items():
                            if isinstance(metric_data, dict) and 'mean' in metric_data:
                                print(f"      {metric_name}: {metric_data['mean']:.4f} (±{metric_data['std']:.4f})")

            # Print timing
            timings = run.get('timings_ms', {})
            if timings:
                retrieval_timing = timings.get('retrieval', {})
                if retrieval_timing:
                    print(f"\n   ⏱️  Timing:")
                    print(f"      Total queries: {retrieval_timing.get('query_count', 0)}")
                    print(f"      Total wall time: {retrieval_timing.get('wall_total_ms', 0):.2f} ms")
                    print(f"      Avg per query: {retrieval_timing.get('wall_total_ms', 0) / max(1, retrieval_timing.get('query_count', 1)):.2f} ms")

                    text_timing = retrieval_timing.get('text', {})
                    if text_timing:
                        print(f"\n      Text Retrieval:")
                        print(f"         Total: {text_timing.get('total_ms', 0):.2f} ms")
                        print(f"         Embed: {text_timing.get('embed_ms', 0):.2f} ms")
                        print(f"         BM25: {text_timing.get('bm25_ms', 0):.2f} ms")
                        print(f"         Qdrant: {text_timing.get('dense_qdrant_ms', 0):.2f} ms")

            results_summary[retriever_type] = {
                'run_id': run['run_id'],
                'user_id': user_id,
                'metrics': metrics,
                'timings': timings
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
    print(f"{'Retriever':<12} {'Recall@1':<10} {'Recall@3':<10} {'Recall@5':<10} {'Recall@10':<11} {'nDCG@1':<10} {'nDCG@3':<10} {'nDCG@5':<10} {'nDCG@10':<11}")

    for retriever_type in retriever_types:
        if retriever_type not in results_summary:
            continue

        metrics = results_summary[retriever_type]['metrics'].get('llm', {}).get('text', {}).get('aggregate', {})

        recall_1 = metrics.get('recall@1', {}).get('mean', 0)
        recall_3 = metrics.get('recall@3', {}).get('mean', 0)
        recall_5 = metrics.get('recall@5', {}).get('mean', 0)
        recall_10 = metrics.get('recall@10', {}).get('mean', 0)

        ndcg_1 = metrics.get('ndcg@1', {}).get('mean', 0)
        ndcg_3 = metrics.get('ndcg@3', {}).get('mean', 0)
        ndcg_5 = metrics.get('ndcg@5', {}).get('mean', 0)
        ndcg_10 = metrics.get('ndcg@10', {}).get('mean', 0)

        print(f"{retriever_type:<12} {recall_1:<10.4f} {recall_3:<10.4f} {recall_5:<10.4f} {recall_10:<11.4f} {ndcg_1:<10.4f} {ndcg_3:<10.4f} {ndcg_5:<10.4f} {ndcg_10:<11.4f}")

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
