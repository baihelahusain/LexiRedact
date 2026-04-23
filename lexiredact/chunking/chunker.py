"""
Core document chunking logic.
Splits large documents into smaller chunks with overlap.
"""

from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass
import uuid
from enum import Enum
import re


class ChunkingStrategy(str, Enum):
    """Chunking strategies."""
    FIXED_SIZE = "fixed_size"          # Fixed token/char chunks
    SENTENCE = "sentence"               # Split by sentences
    PARAGRAPH = "paragraph"             # Split by paragraphs
    HYBRID = "hybrid"                   # Sentences grouped into chunks


@dataclass
class Chunk:
    """Single chunk of text."""
    id: str
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]


class DocumentChunker:
    """
    Convert large documents into LexiRedact-compatible chunks.

    Support for:
    - Fixed-size chunking (tokens or characters)
    - Sentence-based chunking
    - Paragraph-based chunking
    - Overlap between chunks
    """

    def __init__(
        self,
        chunk_size: int = 512,              # Max characters per chunk
        overlap: int = 100,                 # Overlap between chunks (chars)
        strategy: ChunkingStrategy = ChunkingStrategy.FIXED_SIZE,
        preserve_sentences: bool = True,    # Don't split mid-sentence
    ):
        """
        Initialize chunker.

        Args:
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks (to preserve context)
            strategy: Chunking strategy to use
            preserve_sentences: Don't split in middle of sentence
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if overlap < 0:
            raise ValueError("overlap must be greater than or equal to 0")
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.strategy = strategy
        self.preserve_sentences = preserve_sentences

    def chunk_text(
        self,
        text: str,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        """
        Chunk a document.

        Args:
            text: Document text to chunk
            doc_id: Original document ID (source)
            metadata: Optional metadata to attach to chunks

        Returns:
            List of Chunk objects
        """
        metadata = metadata or {}

        if self.strategy == ChunkingStrategy.FIXED_SIZE:
            return self._chunk_fixed_size(text, doc_id, metadata)
        elif self.strategy == ChunkingStrategy.SENTENCE:
            return self._chunk_by_sentence(text, doc_id, metadata)
        elif self.strategy == ChunkingStrategy.PARAGRAPH:
            return self._chunk_by_paragraph(text, doc_id, metadata)
        elif self.strategy == ChunkingStrategy.HYBRID:
            return self._chunk_hybrid(text, doc_id, metadata)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

    def _chunk_fixed_size(
        self,
        text: str,
        doc_id: str,
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """Split into fixed-size chunks with overlap."""
        chunks = []
        chunk_index = 0
        start = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            # If preserve_sentences, adjust end to not split mid-sentence
            if self.preserve_sentences and end < len(text):
                window = text[start:end]
                boundaries = list(re.finditer(r"[.!?](?=\s|$)|\n", window))
                if boundaries:
                    end = start + boundaries[-1].end()

            chunk_text = text[start:end].strip()

            if chunk_text:  # Skip empty chunks
                chunk = Chunk(
                    id=f"{doc_id}_chunk_{chunk_index}",
                    text=chunk_text,
                    chunk_index=chunk_index,
                    start_char=start,
                    end_char=end,
                    metadata={
                        **metadata,
                        "source_doc_id": doc_id,
                        "chunk_number": chunk_index,
                        "strategy": self.strategy.value,
                    }
                )
                chunks.append(chunk)
                chunk_index += 1

            if end >= len(text):
                break

            # Move start position (with overlap)
            start = end - self.overlap

        return chunks

    def _chunk_by_sentence(
        self,
        text: str,
        doc_id: str,
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """Split by sentences while preserving punctuation-heavy tokens."""
        sentences = self._split_sentences(text)
        chunks = []
        chunk_index = 0

        current_chunk = []
        current_size = 0
        start_char = 0

        for sentence in sentences:
            sentence_size = len(sentence)

            # If adding this sentence exceeds chunk_size, save current chunk
            if current_size + sentence_size > self.chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk).strip()
                if chunk_text:
                    chunk = Chunk(
                        id=f"{doc_id}_chunk_{chunk_index}",
                        text=chunk_text,
                        chunk_index=chunk_index,
                        start_char=start_char,
                        end_char=start_char + len(chunk_text),
                        metadata={
                            **metadata,
                            "source_doc_id": doc_id,
                            "chunk_number": chunk_index,
                            "strategy": self.strategy.value,
                        }
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                start_char += len(chunk_text) + 1
                current_chunk = [sentence]
                current_size = sentence_size
            else:
                current_chunk.append(sentence)
                current_size += sentence_size

        # Add remaining chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk).strip()
            chunk = Chunk(
                id=f"{doc_id}_chunk_{chunk_index}",
                text=chunk_text,
                chunk_index=chunk_index,
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                metadata={
                    **metadata,
                    "source_doc_id": doc_id,
                    "chunk_number": chunk_index,
                    "strategy": self.strategy.value,
                }
            )
            chunks.append(chunk)

        return chunks

    def _chunk_by_paragraph(
        self,
        text: str,
        doc_id: str,
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """Split by paragraphs (double newline)."""
        paragraphs = text.split('\n\n')
        chunks = []
        chunk_index = 0
        start_char = 0

        for para in paragraphs:
            para = para.strip()
            if para:
                chunk = Chunk(
                    id=f"{doc_id}_chunk_{chunk_index}",
                    text=para,
                    chunk_index=chunk_index,
                    start_char=start_char,
                    end_char=start_char + len(para),
                    metadata={
                        **metadata,
                        "source_doc_id": doc_id,
                        "chunk_number": chunk_index,
                        "strategy": self.strategy.value,
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
                start_char += len(para) + 2  # +2 for '\n\n'

        return chunks

    def _chunk_hybrid(
        self,
        text: str,
        doc_id: str,
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """
        Hybrid: Group sentences into chunks of target size.
        Better than fixed_size because sentences stay together.
        """
        sentences = self._split_sentences(text)
        chunks = []
        chunk_index = 0
        start_char = 0

        current_chunk = []
        current_size = 0

        for sentence in sentences:
            # If adding sentence exceeds size and we have content, save chunk
            if current_size + len(sentence) > self.chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk).strip()
                chunk = Chunk(
                    id=f"{doc_id}_chunk_{chunk_index}",
                    text=chunk_text,
                    chunk_index=chunk_index,
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    metadata={
                        **metadata,
                        "source_doc_id": doc_id,
                        "chunk_number": chunk_index,
                        "strategy": self.strategy.value,
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
                start_char += len(chunk_text) + 1
                current_chunk = [sentence]
                current_size = len(sentence)
            else:
                current_chunk.append(sentence)
                current_size += len(sentence)

        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk).strip()
            chunk = Chunk(
                id=f"{doc_id}_chunk_{chunk_index}",
                text=chunk_text,
                chunk_index=chunk_index,
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                metadata={
                    **metadata,
                    "source_doc_id": doc_id,
                    "chunk_number": chunk_index,
                    "strategy": self.strategy.value,
                }
            )
            chunks.append(chunk)

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text on sentence boundaries without breaking emails or domains.
        """
        normalized = text.strip()
        if not normalized:
            return []

        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", normalized)
        return [part.strip() for part in parts if part.strip()]
