"""
Evaluate retrieval quality across candidate embedding configurations.

This example keeps the evaluation logic outside the main ingestion pipeline so
LexiRedact remains focused on PII-safe processing while still helping users
compare retrieval quality.
"""

from pprint import pprint

from _bootstrap import ensure_project_root

ensure_project_root()

from lexiredact.metrics import RetrievalMetricsEvaluator


def main() -> None:
    queries = [
        {
            "query_id": "employee-contact",
            "expected_ids": ["doc-1"],
            "retrieved_ids": ["doc-3", "doc-1", "doc-5", "doc-8"],
        },
        {
            "query_id": "medical-policy",
            "expected_ids": ["doc-2"],
            "retrieved_ids": ["doc-2", "doc-7", "doc-4", "doc-9"],
        },
        {
            "query_id": "legal-retention",
            "expected_ids": ["doc-4", "doc-6"],
            "retrieved_ids": ["doc-10", "doc-6", "doc-1", "doc-4"],
        },
    ]

    model_a = RetrievalMetricsEvaluator.evaluate_queries(queries, k=3)

    queries_model_b = [
        {
            "query_id": "employee-contact",
            "expected_ids": ["doc-1"],
            "retrieved_ids": ["doc-1", "doc-5", "doc-8", "doc-3"],
        },
        {
            "query_id": "medical-policy",
            "expected_ids": ["doc-2"],
            "retrieved_ids": ["doc-7", "doc-2", "doc-4", "doc-9"],
        },
        {
            "query_id": "legal-retention",
            "expected_ids": ["doc-4", "doc-6"],
            "retrieved_ids": ["doc-6", "doc-4", "doc-10", "doc-1"],
        },
    ]
    model_b = RetrievalMetricsEvaluator.evaluate_queries(queries_model_b, k=3)

    print("Model A summary")
    pprint(model_a["summary"])
    print()

    print("Model B summary")
    pprint(model_b["summary"])
    print()

    better_model = (
        "Model B"
        if model_b["summary"]["mean_reciprocal_rank"] >= model_a["summary"]["mean_reciprocal_rank"]
        else "Model A"
    )
    print(f"Preferred by MRR: {better_model}")


if __name__ == "__main__":
    main()
