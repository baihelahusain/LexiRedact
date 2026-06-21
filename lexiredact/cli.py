"""
cli.py — Enhanced Click-based CLI for lexiredact.

Commands:
  LexiRedact ingest    --config PATH --input PATH [--mode ...] [--output ...]
  LexiRedact inspect   --config PATH [--limit 10] [--output ...]
  LexiRedact validate  --config PATH [--input PATH]
  LexiRedact export    --config PATH [--output PATH]
  LexiRedact stats     --config PATH [--output PATH]
  LexiRedact info      --config PATH
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any
from datetime import datetime
from collections import defaultdict

import click

from lexiredact import __version__, load_config
from lexiredact.config.schema import LexiredactConfig
from lexiredact.exceptions import LexiredactError, LexiredactInputError
from lexiredact.app_logging import configure_logging, get_logger

logger = get_logger("cli")


def _format_size(bytes_: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_ < 1024:
            return f"{bytes_:.1f}{unit}"
        bytes_ /= 1024
    return f"{bytes_:.1f}TB"


def _write_output(data: dict[str, Any] | list, output_path: str | None) -> None:
    """Write data to file or stdout."""
    content = json.dumps(data, indent=2, default=str)
    if output_path:
        Path(output_path).write_text(content)
        click.echo(f"✓ Written to {output_path}")
    else:
        click.echo(content)


@click.group()
@click.version_option(__version__, prog_name="lexiredact")
def cli() -> None:
    """LexiRedact — privacy-preserving RAG ingestion middleware.
    
    For detailed help on any command: LexiRedact COMMAND --help
    """


# ── ingest ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True),
              help="Path to lexiredact_config.yaml")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True),
              help="Path to JSON file: list of raw chunk dicts")
@click.option("--mode", "pipeline_mode",
              type=click.Choice(["raw", "preredacted", "dual"]), default=None,
              help="Override pipeline_mode from config")
@click.option("--batch-size", "batch_size", type=int, default=None,
              help="Override embedder.batch_size from config")
@click.option("--output", "output_path", type=click.Path(), default=None,
              help="Save results to JSON file (optional)")
@click.option("--verbose", is_flag=True, default=False,
              help="Print per-chunk result summary")
def ingest(
    config_path: str,
    input_path: str,
    pipeline_mode: str | None,
    batch_size: int | None,
    output_path: str | None,
    verbose: bool,
) -> None:
    """Ingest pre-chunked text through the LexiRedact pipeline.
    
    Input JSON must be a list of dicts: [{"id": "...", "text": "..."}, ...]
    """
    configure_logging("INFO")

    try:
        config = load_config(config_path)

        # Apply CLI overrides
        overrides: dict[str, Any] = {}
        if pipeline_mode is not None:
            overrides["pipeline_mode"] = pipeline_mode
        if batch_size is not None:
            overrides["embedder"] = config.embedder.model_copy(
                update={"batch_size": batch_size}
            )
        if overrides:
            config = config.model_copy(update=overrides)

        with open(input_path, encoding="utf-8") as fh:
            raw_chunks: list[dict[str, Any]] = json.load(fh)

        if not isinstance(raw_chunks, list):
            raise LexiredactInputError("Input file must contain a JSON array")

        from lexiredact import LexiredactPipeline

        t_start = time.perf_counter()
        pipeline = LexiredactPipeline(config)
        results = pipeline.ingest(raw_chunks)
        elapsed = time.perf_counter() - t_start

        # ── Summary ───────────────────────────────────────────────────────────
        n = len(results)
        mode_used = config.pipeline_mode
        avg_lat = sum(r.latency_ms for r in results) / max(n, 1)
        cache_hits = sum(1 for r in results if r.cache_hit)
        total_entities = sum(len(r.entities_detected) for r in results)
        chunks_with_pii = sum(1 for r in results if r.entities_detected)
        errors = [r for r in results if r.error]

        click.echo(
            f"\n✓  Processed {n} chunks in {elapsed:.2f}s  |  mode={mode_used}  |"
            f"  avg latency={avg_lat:.1f}ms  |  cache hits={cache_hits}/{n}"
        )
        if mode_used != "raw":
            click.echo(
                f"   PII detected: {total_entities} entities across {chunks_with_pii} chunks"
            )
        click.echo(
            f"   Stored to: {config.store.persist_directory}"
            f"  (collection: {config.store.collection_name})"
        )

        if verbose:
            click.echo("\nPer-chunk summary:")
            for r in results:
                ent_count = len(r.entities_detected)
                hit = "cache" if r.cache_hit else "model"
                entities = ", ".join(e.entity_type for e in r.entities_detected[:3])
                click.echo(
                    f"  {r.chunk_id:<20}  {ent_count:>2} entities  "
                    f"{r.latency_ms:>7.1f}ms  [{hit}]"
                    + (f"  {entities}" if entities else "")
                )

        if errors:
            click.echo(f"\n⚠  {len(errors)} chunk(s) had errors:", err=True)
            for r in errors:
                click.echo(f"   {r.chunk_id}: {r.error}", err=True)

        if output_path:
            results_data = [r.to_dict() for r in results]
            _write_output(results_data, output_path)

    except LexiredactError as exc:
        click.echo(f"\nERROR: {exc}", err=True)
        sys.exit(1)


# ── inspect ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True),
              help="Path to lexiredact_config.yaml")
@click.option("--limit", "limit", type=int, default=10, show_default=True,
              help="Number of chunks to sample")
@click.option("--output", "output_path", type=click.Path(), default=None,
              help="Save to JSON file")
def inspect(config_path: str, limit: int, output_path: str | None) -> None:
    """Inspect persisted vector store contents.
    
    Samples stored chunks with their metadata and embedding dimension info.
    """
    configure_logging("WARNING")

    try:
        config = load_config(config_path)

        from lexiredact.pipeline.embedder.registry import create_embedder
        from lexiredact.pipeline.store.chroma import ChromaStore

        embedder = create_embedder(config.embedder)
        store = ChromaStore(config.store, embedder.get_dimension())

        # Get collection stats
        collection = store._collection
        count = collection.count()
        
        # Sample records
        results = collection.get(limit=limit)

        payload = {
            "store": {
                "provider": config.store.provider,
                "collection": config.store.collection_name,
                "persist_directory": config.store.persist_directory,
                "total_chunks": count,
                "embedding_dimension": embedder.get_dimension(),
            },
            "sample": {
                "limit": limit,
                "returned": len(results["ids"]) if results else 0,
                "chunks": [
                    {
                        "id": chunk_id,
                        "text_preview": metadata.get("text", "")[:200],
                        "metadata": metadata,
                    }
                    for chunk_id, metadata in zip(
                        results["ids"],
                        results["metadatas"],
                    )
                ]
                if results
                else [],
            },
        }

        if output_path:
            _write_output(payload, output_path)
        else:
            click.echo(json.dumps(payload, indent=2))

    except LexiredactError as exc:
        click.echo(f"\nERROR: {exc}", err=True)
        sys.exit(1)


# ── validate ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True),
              help="Path to lexiredact_config.yaml")
@click.option("--input", "input_path", type=click.Path(exists=True), default=None,
              help="Optional: validate input JSON file")
def validate(config_path: str, input_path: str | None) -> None:
    """Validate configuration and optional input file.
    
    Checks config syntax, required fields, and input JSON structure.
    """
    configure_logging("WARNING")

    errors = []
    warnings = []

    # Validate config
    try:
        config = load_config(config_path)
        click.echo("✓ Config file is valid")
        click.echo(f"  Pipeline mode: {config.pipeline_mode}")
        click.echo(f"  Embedder: {config.embedder.backend} ({config.embedder.model_name})")
        click.echo(f"  Store: {config.store.provider} at {config.store.persist_directory}")
    except Exception as e:
        errors.append(f"Config validation failed: {e}")

    # Validate input (if provided)
    if input_path:
        try:
            with open(input_path, encoding="utf-8") as fh:
                data = json.load(fh)

            if not isinstance(data, list):
                errors.append("Input must be JSON array")
            else:
                click.echo(f"✓ Input file contains {len(data)} records")

                # Check required fields
                text_field = config.input_schema.text_field
                id_field = config.input_schema.id_field

                for i, record in enumerate(data):
                    if text_field not in record:
                        errors.append(f"Record {i}: missing field '{text_field}'")
                    if id_field not in record:
                        errors.append(f"Record {i}: missing field '{id_field}'")
                    if record.get(text_field) == "":
                        warnings.append(f"Record {i}: empty text field")

                if not errors:
                    click.echo(f"✓ All {len(data)} records have required fields")

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")
        except FileNotFoundError:
            errors.append(f"Input file not found: {input_path}")

    # Report
    if errors:
        click.echo("\n✗ Validation failed:", err=True)
        for err in errors:
            click.echo(f"  {err}", err=True)
        sys.exit(1)

    if warnings:
        click.echo("\n⚠ Warnings:", err=True)
        for warn in warnings:
            click.echo(f"  {warn}", err=True)

    if not errors:
        click.echo("\n✓ All validations passed!")


# ── export ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True),
              help="Path to lexiredact_config.yaml")
@click.option("--output", "output_path", required=True, type=click.Path(),
              help="Output JSON file path")
@click.option("--limit", "limit", type=int, default=None,
              help="Limit exported records (None = all)")
def export(config_path: str, output_path: str, limit: int | None) -> None:
    """Export all stored chunks from the vector database.
    
    Exports chunk IDs, text, and metadata in JSON format.
    """
    configure_logging("WARNING")

    try:
        config = load_config(config_path)

        from lexiredact.pipeline.embedder.registry import create_embedder
        from lexiredact.pipeline.store.chroma import ChromaStore

        embedder = create_embedder(config.embedder)
        store = ChromaStore(config.store, embedder.get_dimension())

        collection = store._collection
        total = collection.count()

        click.echo(f"Exporting {total} chunks...")

        # Fetch all records
        results = collection.get(limit=limit or total)

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "config": {
                "collection": config.store.collection_name,
                "embedder": config.embedder.model_name,
            },
            "records": [
                {
                    "id": chunk_id,
                    "text": metadata.get("text", ""),
                    "metadata": metadata,
                }
                for chunk_id, metadata in zip(results["ids"], results["metadatas"])
            ]
            if results
            else [],
        }

        _write_output(export_data, output_path)

    except LexiredactError as exc:
        click.echo(f"\nERROR: {exc}", err=True)
        sys.exit(1)


# ── stats ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True),
              help="Path to lexiredact_config.yaml")
@click.option("--output", "output_path", type=click.Path(), default=None,
              help="Save stats to JSON file")
def stats(config_path: str, output_path: str | None) -> None:
    """Display detailed statistics about stored data.
    
    Shows distribution of PII entities, chunk sizes, and collection health.
    """
    configure_logging("WARNING")

    try:
        config = load_config(config_path)

        from lexiredact.pipeline.embedder.registry import create_embedder
        from lexiredact.pipeline.store.chroma import ChromaStore

        embedder = create_embedder(config.embedder)
        store = ChromaStore(config.store, embedder.get_dimension())

        collection = store._collection
        total_chunks = collection.count()

        # Fetch all for analysis
        results = collection.get(limit=10000)

        if not results or not results["ids"]:
            click.echo("No chunks in collection yet.")
            return

        # Analyze metadata
        text_lengths = []
        entity_types = defaultdict(int)

        for metadata in results["metadatas"]:
            text = metadata.get("text", "")
            text_lengths.append(len(text))

        stats_data = {
            "collection": config.store.collection_name,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_chunks": total_chunks,
                "sampled_chunks": len(results["ids"]),
                "embedding_dim": embedder.get_dimension(),
            },
            "text_statistics": {
                "min_length": min(text_lengths),
                "max_length": max(text_lengths),
                "avg_length": sum(text_lengths) / len(text_lengths),
                "median_length": sorted(text_lengths)[len(text_lengths) // 2],
            },
            "pii_entities": dict(entity_types),
        }

        if output_path:
            _write_output(stats_data, output_path)
        else:
            click.echo(json.dumps(stats_data, indent=2))

    except LexiredactError as exc:
        click.echo(f"\nERROR: {exc}", err=True)
        sys.exit(1)


# ── info ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True),
              help="Path to lexiredact_config.yaml")
def info(config_path: str) -> None:
    """Display active configuration.
    
    No ML model is loaded — this is instantaneous.
    """
    try:
        config = load_config(config_path)
        entities_str = ", ".join(config.pii.entities)
        cache_str = "enabled" if config.cache.enabled else "disabled"
        sep = "─" * 60

        click.echo(f"\nLexiRedact v{__version__}")
        click.echo(sep)
        click.echo(f"Pipeline mode        : {config.pipeline_mode}")
        click.echo(f"Input schema         : id='{config.input_schema.id_field}', text='{config.input_schema.text_field}'")
        click.echo(sep)
        click.echo(f"Embedder backend     : {config.embedder.backend}")
        click.echo(f"Embedding model      : {config.embedder.model_name}")
        click.echo(f"Embedding dimension  : {config.embedder.dimension or 'auto-detect'}")
        click.echo(f"Document prefix      : {config.embedder.document_prefix!r}")
        click.echo(f"Query prefix         : {config.embedder.query_prefix!r}")
        click.echo(f"Batch size           : {config.embedder.batch_size}")
        click.echo(f"Device               : {config.embedder.device}")
        click.echo(sep)
        click.echo(f"PII entities         : {entities_str}")
        click.echo(f"NLP engine           : {config.pii.nlp_engine}")
        click.echo(f"NLP model            : {config.pii.nlp_model}")
        click.echo(f"Score threshold      : {config.pii.score_threshold}")
        click.echo(sep)
        click.echo(f"Cache                : {cache_str}")
        if config.cache.enabled:
            click.echo(f"Cache URL            : {config.cache.redis_url}")
            click.echo(f"Cache TTL            : {config.cache.ttl_seconds}s")
        click.echo(sep)
        click.echo(f"Vector store         : {config.store.provider}")
        click.echo(f"Store path           : {config.store.persist_directory}")
        click.echo(f"Collection name      : {config.store.collection_name}")
        click.echo(sep + "\n")

    except LexiredactError as exc:
        click.echo(f"\nERROR: {exc}", err=True)
        sys.exit(1)

def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()