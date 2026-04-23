"""
Export chunks as JSON in LexiRedact format.
"""

import json
from typing import List, Dict, Any
from pathlib import Path
from .chunker import Chunk


class JSONExporter:
    """Export chunks to JSON format compatible with LexiRedact."""

    @staticmethod
    def to_lexiredact_format(
        chunks: List[Chunk],
        output_path: str | Path | None = None,
        wrap_documents: bool = False,
    ) -> str | List[Dict[str, Any]] | Dict[str, List[Dict[str, Any]]]:
        """
        Convert chunks to LexiRedact JSON format.

        Args:
            chunks: List of Chunk objects
            output_path: Optional path to save JSON file
            wrap_documents: Export CLI-ready payload as
                {"documents": [...]} when True

        Returns:
            JSON string (if output_path) or payload object (if None)

        Example output format:
            [
              {
                "id": "doc1_chunk_0",
                "text": "First chunk of text...",
                "metadata": {
                  "source_doc_id": "doc1",
                  "chunk_number": 0,
                  "chunk_size": 512
                }
              },
              ...
            ]
        """
        chunk_dicts = [
            {
                "id": chunk.id,
                "text": chunk.text,
                "metadata": chunk.metadata
            }
            for chunk in chunks
        ]
        payload: List[Dict[str, Any]] | Dict[str, List[Dict[str, Any]]]
        payload = {"documents": chunk_dicts} if wrap_documents else chunk_dicts

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            return json.dumps(payload, indent=2, ensure_ascii=False)

        return payload

    @staticmethod
    def to_cli_input(
        chunks: List[Chunk],
        output_path: str | Path | None = None,
    ) -> str | Dict[str, List[Dict[str, Any]]]:
        """Export chunks in the JSON shape expected by `lexiredact process`."""
        return JSONExporter.to_lexiredact_format(
            chunks,
            output_path=output_path,
            wrap_documents=True,
        )

    @staticmethod
    def to_jsonl(
        chunks: List[Chunk],
        output_path: str | Path,
    ) -> None:
        """
        Export chunks as JSONL (one JSON per line).
        Useful for streaming/large datasets.

        Args:
            chunks: List of Chunk objects
            output_path: Path to save JSONL file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                line = {
                    "id": chunk.id,
                    "text": chunk.text,
                    "metadata": chunk.metadata
                }
                f.write(json.dumps(line, ensure_ascii=False) + '\n')
