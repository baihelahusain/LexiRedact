"""
Core ingestion pipeline for VectorShield.

Orchestrates PII detection, redaction, embedding, and storage.
This is the heart of the system.
"""
from typing import List, Dict, Any, Optional, Callable
import asyncio
import time
import uuid
from ..interfaces import CacheBackend, Embedder, VectorStore, Tracker
from ..privacy import PIIDetector, PIIRedactor, PIIPolicy
from ..metrics import MetricsCollector, IngestionMetrics
from ..utils import generate_cache_key, Timer
from ..config import load_config
from ..registry import ComponentLoader
from ..implementations.tracker import NoOpTracker  # ← ADD THIS IMPORT


class Document:
    """Input document for ingestion."""
    
    def __init__(self, id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Create a document.
        
        Args:
            id: Unique document identifier
            text: Document text content
            metadata: Optional metadata dictionary
        """
        self.id = id
        self.text = text
        self.metadata = metadata or {}


class ProcessedDocument:
    """Output document after ingestion."""
    
    def __init__(
        self,
        id: str,
        original_preview: str,
        clean_text: str,
        pii_entities: List[str],
        embedding_preview: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "success"
    ):
        """
        Create a processed document result.
        
        Args:
            id: Document ID
            original_preview: First 100 chars of original text
            clean_text: Sanitized text with PII redacted
            pii_entities: List of PII types found
            embedding_preview: First 5 values of embedding
            metadata: Document metadata
            status: Processing status ("success" or "failed")
        """
        self.id = id
        self.original_preview = original_preview
        self.clean_text = clean_text
        self.pii_entities = pii_entities
        self.embedding_preview = embedding_preview
        self.metadata = metadata or {}
        self.status = status
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for output."""
        return {
            "id": self.id,
            "status": self.status,
            "original_preview": self.original_preview,
            "clean_text": self.clean_text,
            "pii_found": self.pii_entities,
            "vector_preview": self.embedding_preview,
            "metadata": self.metadata
        }


class IngestionPipeline:
    """
    VectorShield ingestion pipeline.
    
    Architecture:
    1. Check cache for PII detection result (using text hash)
    2. If cache miss: Run PII detection + embedding IN PARALLEL
    3. Apply redaction to create clean text
    4. Store clean text + embedding in vector database
    5. Track metrics
    
    The key insight: Embeddings are generated from ORIGINAL text
    (before redaction) to preserve semantic quality, while only
    the REDACTED text is stored.
    """
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache: Optional[CacheBackend] = None,
        embedder: Optional[Embedder] = None,
        vectorstore: Optional[VectorStore] = None,
        tracker: Optional[Tracker] = None,
        pii_policy: Optional[PIIPolicy] = None,  # ← ADD THIS PARAMETER
        # Custom functions
        cache_get_func: Optional[Callable] = None,
        cache_set_func: Optional[Callable] = None,
        cache_connect_func: Optional[Callable] = None,
        cache_disconnect_func: Optional[Callable] = None,
        cache_delete_func: Optional[Callable] = None,
        cache_clear_func: Optional[Callable] = None,
        embed_func: Optional[Callable] = None,
        embed_batch_func: Optional[Callable] = None,
        add_vectors_func: Optional[Callable] = None,
        search_func: Optional[Callable] = None,
        vectorstore_connect_func: Optional[Callable] = None,
        vectorstore_disconnect_func: Optional[Callable] = None,
        vectorstore_delete_func: Optional[Callable] = None,
        vectorstore_update_func: Optional[Callable] = None,
    ):
        """Initialize ingestion pipeline."""
        
        self.config = config or {}
        
        # Load default config if not provided
        if not self.config:
            self.config = load_config()
        
        self.initialized = False
        
        # If components provided directly, use them
        if cache is not None and embedder is not None and vectorstore is not None:
            self.cache = cache
            self.embedder = embedder
            self.vectorstore = vectorstore
            self.tracker = tracker or NoOpTracker()  # ← Now imported!
        else:
            # Load components using ComponentLoader
            components = ComponentLoader.load_all(
                self.config,
                custom_cache=cache,
                custom_embedder=embedder,
                custom_vectorstore=vectorstore,
                custom_tracker=tracker,
                # Cache functions with "cache_" prefix
                cache_get_func=cache_get_func,
                cache_set_func=cache_set_func,
                cache_connect_func=cache_connect_func,
                cache_disconnect_func=cache_disconnect_func,
                cache_delete_func=cache_delete_func,
                cache_clear_func=cache_clear_func,
                # Embedder functions
                embed_func=embed_func,
                embed_batch_func=embed_batch_func,
                # VectorStore functions with "vectorstore_" prefix
                add_vectors_func=add_vectors_func,
                search_func=search_func,
                vectorstore_connect_func=vectorstore_connect_func,
                vectorstore_disconnect_func=vectorstore_disconnect_func,
                vectorstore_delete_func=vectorstore_delete_func,
                vectorstore_update_func=vectorstore_update_func,
            )
            
            self.cache = components["cache"]
            self.embedder = components["embedder"]
            self.vectorstore = components["vectorstore"]
            self.tracker = components["tracker"]
        
        # Initialize privacy components
        self.pii_policy = pii_policy or PIIPolicy.create_standard()  # ← Now defined!
        self.pii_detector = PIIDetector(entities=self.pii_policy.get_entity_list())
        self.redactor = PIIRedactor()
        
        # Initialize metrics
        self.metrics = MetricsCollector()
        
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        Initialize all components.
        
        Must be called before processing documents.
        """
        if self._initialized:
            return
        
        print("🚀 Initializing VectorShield pipeline...")
        
        # Connect all components concurrently
        await asyncio.gather(
            self.cache.connect(),
            self.vectorstore.connect(),
            self.tracker.connect()
        )
        
        # Log configuration to tracker
        await self.tracker.log_param("embedding_model", self.config.get("embedding_model", "BAAI/bge-small-en-v1.5"))
        await self.tracker.log_param("cache_backend", self.config.get("cache_backend", "memory"))
        await self.tracker.log_param("pii_entities", self.pii_policy.get_entity_list())
        
        self._initialized = True
        print("✅ VectorShield pipeline ready")
    
    async def shutdown(self) -> None:
        """Cleanup and close all connections."""
        if not self._initialized:
            return
        
        print("👋 Shutting down VectorShield pipeline...")
        
        await asyncio.gather(
            self.cache.close(),
            self.vectorstore.close(),
            self.tracker.close()
        )
        
        self._initialized = False
        print("✅ Shutdown complete")
    
    async def process_document(self, document: Document) -> ProcessedDocument:
        """
        Process a single document through the pipeline.
        
        Args:
            document: Input document
            
        Returns:
            Processed document with sanitized text and embedding
            
        Example:
            >>> doc = Document(id="1", text="Call John at 555-0123")
            >>> result = await pipeline.process_document(doc)
            >>> print(result.clean_text)  # "Call <PERSON> at <PHONE_NUMBER>"
        """
        if not self._initialized:
            raise RuntimeError("Pipeline not initialized. Call await pipeline.initialize()")
        
        start_time = time.perf_counter()
        
        # Timing for each stage
        pii_time = 0.0
        embedding_time = 0.0
        storage_time = 0.0
        cache_hit = False
        
        try:
            text = document.text
            cache_key = generate_cache_key(text)
            
            # STAGE 1: Check cache
            cached_result = await self.cache.get(cache_key)
            
            if cached_result:
                # Cache hit - reuse PII detection result
                cache_hit = True
                clean_text = cached_result["clean_text"]
                pii_entities = cached_result["pii_found"]
                
                # Still generate embedding from ORIGINAL text (Shadow Mode)
                with Timer() as t:
                    embedding = await self.embedder.embed_text(text)
                embedding_time = t.elapsed_ms
            else:
                # Cache miss - parallel processing
                if self.config.get("parallel_processing", True):
                    # STAGE 2: Parallel execution (CRITICAL FOR PERFORMANCE)
                    # Path A: Detect PII in original text
                    # Path B: Generate embedding from original text
                    with Timer() as t_parallel:
                        pii_task = self.pii_detector.detect(text)
                        embedding_task = self.embedder.embed_text(text)
                        
                        detection_results, embedding = await asyncio.gather(
                            pii_task,
                            embedding_task
                        )
                    
                    # Split timing proportionally (simplified)
                    pii_time = t_parallel.elapsed_ms / 2
                    embedding_time = t_parallel.elapsed_ms / 2
                    
                    # STAGE 3: Apply redaction
                    clean_text, pii_entities = await self.redactor.redact(text, detection_results)
                else:
                    # Sequential processing (for debugging)
                    with Timer() as t:
                        detection_results = await self.pii_detector.detect(text)
                    pii_time = t.elapsed_ms
                    
                    clean_text, pii_entities = await self.redactor.redact(text, detection_results)
                    
                    with Timer() as t:
                        embedding = await self.embedder.embed_text(text)
                    embedding_time = t.elapsed_ms
                
                # Cache the PII result for future use
                await self.cache.set(
                    cache_key,
                    {"clean_text": clean_text, "pii_found": pii_entities},
                    ttl=self.config.get("cache_ttl", 3600)
                )
            
            # STAGE 4: Store in vector database
            with Timer() as t:
                await self.vectorstore.add_vectors(
                    ids=[document.id],
                    embeddings=[embedding],
                    documents=[clean_text],
                    metadata=[document.metadata]
                )
            storage_time = t.elapsed_ms
            
            # Calculate total time
            total_time = (time.perf_counter() - start_time) * 1000
            
            # Record metrics
            metric = IngestionMetrics(
                document_id=document.id,
                status="success",
                total_time_ms=total_time,
                pii_detection_time_ms=pii_time,
                embedding_time_ms=embedding_time,
                storage_time_ms=storage_time,
                pii_entities_found=pii_entities,
                cache_hit=cache_hit
            )
            self.metrics.record(metric)
            
            # Log to tracker (async, non-blocking)
            await self.tracker.log_metrics({
                "latency_ms": total_time,
                "pii_entities_found": len(pii_entities),
                "cache_hit": 1 if cache_hit else 0
            })
            
            # Return result
            return ProcessedDocument(
                id=document.id,
                original_preview=text[:100],
                clean_text=clean_text,
                pii_entities=pii_entities,
                embedding_preview=embedding[:5],
                metadata=document.metadata,
                status="success"
            )
        
        except Exception as e:
            # Handle failure
            total_time = (time.perf_counter() - start_time) * 1000
            
            metric = IngestionMetrics(
                document_id=document.id,
                status="failed",
                total_time_ms=total_time,
                pii_detection_time_ms=pii_time,
                embedding_time_ms=embedding_time,
                storage_time_ms=storage_time,
                cache_hit=cache_hit
            )
            self.metrics.record(metric)
            
            print(f"❌ Failed to process document {document.id}: {e}")
            import traceback
            traceback.print_exc()
            
            return ProcessedDocument(
                id=document.id,
                original_preview=document.text[:100],
                clean_text="",
                pii_entities=[],
                embedding_preview=[],
                metadata=document.metadata,
                status="failed"
            )
    
    async def process_batch(self, documents: List[Document]) -> Dict[str, Any]:
        """
        Process multiple documents concurrently.
        
        Args:
            documents: List of documents to process
            
        Returns:
            JSON-serializable result dictionary with batch summary
            
        Example:
            >>> docs = [
            ...     Document(id="1", text="Call John"),
            ...     Document(id="2", text="Email alice@example.com")
            ... ]
            >>> result = await pipeline.process_batch(docs)
            >>> print(result["total_processed"])
        """
        if not self._initialized:
            raise RuntimeError("Pipeline not initialized. Call await pipeline.initialize()")
        
        # Enforce batch size limit
        max_batch = self.config.get("max_batch_size", 505)
        if len(documents) > max_batch:
            raise ValueError(f"Batch size {len(documents)} exceeds maximum {max_batch}")
        
        # Generate batch ID
        batch_id = str(uuid.uuid4())
        batch_start = time.perf_counter()
        
        # Process all documents concurrently
        tasks = [self.process_document(doc) for doc in documents]
        results = await asyncio.gather(*tasks)
        
        batch_time = time.perf_counter() - batch_start
        
        # Build output
        return {
            "batch_id": batch_id,
            "total_processed": len(results),
            "total_time_seconds": round(batch_time, 3),
            "results": [r.to_dict() for r in results]
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics summary.
        
        Returns:
            Metrics summary dictionary
        """
        return self.metrics.export_summary()
    
    def reset_metrics(self) -> None:
        """Reset metrics counters."""
        self.metrics.reset()