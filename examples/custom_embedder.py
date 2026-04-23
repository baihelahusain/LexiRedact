"""
Custom Embedder Example

Reference example for swapping LexiRedact's default FastEmbed model with a
SentenceTransformers model through the Embedder interface.

Use this when you want one custom model in production.
Use `embedding_model_comparision.py` when you want to compare multiple models
before choosing one.
"""

import asyncio
from pathlib import Path

from _bootstrap import ensure_project_root

ensure_project_root()

import lexiredact as vs
from _embedding_reference import (
    DOCUMENTS,
    QUERIES,
    SentenceTransformerLexiRedactEmbedder,
)


async def main() -> None:
    print("=" * 60)
    print("LexiRedact - Custom SentenceTransformers Embedder")
    print("=" * 60)
    print()

    try:
        embedder = SentenceTransformerLexiRedactEmbedder(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            local_files_only=True,
        )
    except ImportError as exc:
        print(exc)
        return
    except Exception as exc:
        print(f"Model load failed: {exc}")
        print("If the model is not cached locally, install it or rerun a comparison with downloads enabled.")
        return

    config = vs.load_config(
        config_dict={
            "vectorstore_path": str(Path(".tmp-build") / "custom_embedder_data"),
            "vectorstore_collection": "custom_embedder_reference",
            "mlflow_log_artifacts": False,
        }
    )

    pipeline = vs.IngestionPipeline(config=config, embedder=embedder)
    await pipeline.initialize()

    print(f"Model: {embedder.model_name}")
    print(f"Embedding dimension: {embedder.get_embedding_dimension()}")
    print("Processing reference documents...")
    print()

    batch_result = await pipeline.process_batch(list(DOCUMENTS))

    print("Stored documents:")
    for item in batch_result["results"]:
        print(f"   {item['id']}: {item['clean_text']}")
    print()

    sample_query = QUERIES[0].query
    query_embedding = await embedder.embed_query(sample_query)
    results = await pipeline.vectorstore.query(query_embedding=query_embedding, top_k=3)

    print(f"Sample query: {sample_query}")
    for index, item in enumerate(results, start=1):
        print(f"   {index}. {item['id']} score={item['score']:.4f}")
        print(f"      {item['document']}")
    print()

    print("Reference pattern:")
    print("   1. Implement `embed_text`, `embed_batch`, and `get_embedding_dimension`.")
    print("   2. Pass the embedder into `vs.IngestionPipeline(embedder=your_embedder)`.")
    print("   3. Keep query embedding logic next to the model if it needs query prefixes.")

    await pipeline.shutdown()
    print()
    print("See `embedding_model_comparision.py` for side-by-side model comparison.")


if __name__ == "__main__":
    asyncio.run(main())
