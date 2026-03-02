"""
Component registry and loader for VectorShield.

Dynamically loads implementations based on configuration.
Supports both built-in and custom user-provided components.
"""
from typing import Dict, Any, Optional, Type, Callable, List
from ..interfaces import CacheBackend, Embedder, VectorStore, Tracker
from ..implementations import (
    MemoryCache, RedisCache, NoOpCache, GenericCache,
    FastEmbedEmbedder, GenericEmbedder,
    ChromaVectorStore, GenericVectorStore,
    MLflowTracker, NoOpTracker
)


class ComponentLoader:
    """
    Loads VectorShield components based on configuration.
    
    Supports three ways to load each component:
    1. Custom instance (direct injection)
    2. Custom functions/object (via Generic wrappers)
    3. Built-in implementations (via registry)
    """
    
    # Built-in implementations registry
    CACHE_BACKENDS: Dict[str, Type[CacheBackend]] = {
        "memory": MemoryCache,
        "redis": RedisCache,
        "none": NoOpCache,
    }
    
    EMBEDDERS: Dict[str, Type[Embedder]] = {
        "fastembed": FastEmbedEmbedder,
    }
    
    VECTORSTORES: Dict[str, Type[VectorStore]] = {
        "chroma": ChromaVectorStore,
    }
    
    TRACKERS: Dict[str, Type[Tracker]] = {
        "mlflow": MLflowTracker,
        "none": NoOpTracker,
    }
    
    @classmethod
    def load_cache(
        cls,
        config: Dict[str, Any],
        custom_instance: Optional[CacheBackend] = None,
        get_func: Optional[Callable[[str], Any]] = None,
        set_func: Optional[Callable[[str, Dict[str, Any], Optional[int]], None]] = None,
        connect_func: Optional[Callable[[], None]] = None,
        disconnect_func: Optional[Callable[[], None]] = None,
        delete_func: Optional[Callable[[str], None]] = None,
        clear_func: Optional[Callable[[], None]] = None
    ) -> CacheBackend:
        """
        Load cache backend - supports built-in and generic caches.
        
        Args:
            config: Configuration dictionary with keys:
                - cache_backend: "memory", "redis", or "none" (default: "memory")
                - redis_host: Redis host (default: "localhost")
                - redis_port: Redis port (default: 6379)
                - redis_db: Redis database (default: 0)
                - cache_name: Custom cache name (default: "custom")
            custom_instance: Optional custom cache implementation
            get_func: Custom get function (key: str) -> Any
            set_func: Custom set function (key: str, value: Any, ttl: Optional[int]) -> None
            connect_func: Optional connect function
            disconnect_func: Optional disconnect function
            delete_func: Optional delete function (key: str) -> None
            clear_func: Optional clear function () -> None
            
        Returns:
            CacheBackend instance
            
        Raises:
            ValueError: If unknown cache backend specified
            
        Examples:
            # Built-in Memory cache
            >>> config = {"cache_backend": "memory"}
            >>> cache = ComponentLoader.load_cache(config)
            
            # Built-in Redis cache
            >>> config = {
            ...     "cache_backend": "redis",
            ...     "redis_host": "localhost",
            ...     "redis_port": 6379
            ... }
            >>> cache = ComponentLoader.load_cache(config)
            
            # Custom Redis client (GenericCache)
            >>> import redis
            >>> client = redis.Redis(host='localhost', port=6379)
            >>> cache = ComponentLoader.load_cache(
            ...     config={"cache_name": "redis-custom"},
            ...     get_func=lambda key: client.get(key),
            ...     set_func=lambda key, val, ttl: client.setex(key, ttl or 3600, val),
            ...     connect_func=lambda: client.ping(),
            ...     disconnect_func=lambda: client.close()
            ... )
            
            # Custom Memcached
            >>> import memcache
            >>> mc = memcache.Client(['127.0.0.1:11211'])
            >>> cache = ComponentLoader.load_cache(
            ...     config={"cache_name": "memcached-custom"},
            ...     get_func=mc.get,
            ...     set_func=lambda key, val, ttl: mc.set(key, val, time=ttl or 0)
            ... )
        """
        # Priority 1: Direct custom instance
        if custom_instance is not None:
            return custom_instance
        
        # Priority 2: Custom functions → use GenericCache
        if get_func is not None and set_func is not None:
            cache_name = config.get("cache_name", "custom")
            return GenericCache(
                get_func=get_func,
                set_func=set_func,
                connect_func=connect_func,
                disconnect_func=disconnect_func,
                delete_func=delete_func,
                clear_func=clear_func,
                name=cache_name
            )
        
        # Priority 3: Built-in cache backends
        backend_type = config.get("cache_backend", "memory")
        
        if backend_type not in cls.CACHE_BACKENDS:
            raise ValueError(
                f"Unknown cache backend: {backend_type}. "
                f"Available: {list(cls.CACHE_BACKENDS.keys())}. "
                f"Or provide get_func and set_func for custom caches."
            )
        
        backend_class = cls.CACHE_BACKENDS[backend_type]
        
        # Instantiate with appropriate parameters
        if backend_type == "redis":
            return backend_class(
                host=config.get("redis_host", "localhost"),
                port=config.get("redis_port", 6379),
                db=config.get("redis_db", 0)
            )
        else:
            return backend_class()
    
    @classmethod
    def load_embedder(
        cls,
        config: Dict[str, Any],
        custom_instance: Optional[Embedder] = None,
        embed_func: Optional[Callable[[str], List[float]]] = None,
        embed_batch_func: Optional[Callable[[List[str]], List[List[float]]]] = None
    ) -> Embedder:
        """
        Load embedder - supports built-in and custom embedders.
        
        Args:
            config: Configuration dictionary with keys:
                - embedder_backend: "fastembed" (default)
                - embedder_name: Custom name for embedder (default: "custom")
                - embedding_model: Model name (default: "BAAI/bge-small-en-v1.5")
            custom_instance: Optional custom embedder instance
            embed_func: Custom embedding function (str → List[float])
            embed_batch_func: Custom batch embedding function (List[str] → List[List[float]])
            
        Returns:
            Embedder instance
            
        Raises:
            ValueError: If unknown embedder backend specified
            TypeError: If embed_func is not callable
            
        Examples:
            # Built-in FastEmbed
            >>> config = {"embedding_model": "BAAI/bge-small-en-v1.5"}
            >>> embedder = ComponentLoader.load_embedder(config)
            
            # Custom OpenAI
            >>> from openai import OpenAI
            >>> client = OpenAI(api_key="sk-...")
            >>> embedder = ComponentLoader.load_embedder(
            ...     config={"embedder_name": "openai"},
            ...     embed_func=lambda text: client.embeddings.create(
            ...         input=text, 
            ...         model="text-embedding-3-small"
            ...     ).data[0].embedding
            ... )
            
            # Custom SentenceTransformers
            >>> from sentence_transformers import SentenceTransformer
            >>> model = SentenceTransformer('all-MiniLM-L6-v2')
            >>> embedder = ComponentLoader.load_embedder(
            ...     config={"embedder_name": "sentence-transformers"},
            ...     embed_func=lambda text: model.encode(text).tolist(),
            ...     embed_batch_func=lambda texts: model.encode(texts).tolist()
            ... )
        """
        # Priority 1: Direct custom instance
        if custom_instance is not None:
            return custom_instance
        
        # Priority 2: Custom functions → use GenericEmbedder
        if embed_func is not None:
            embedder_name = config.get("embedder_name", "custom")
            return GenericEmbedder(
                embed_func=embed_func,
                embed_batch_func=embed_batch_func,
                name=embedder_name
            )
        
        # Priority 3: Built-in embedders
        backend_type = config.get("embedder_backend", "fastembed")
        
        if backend_type not in cls.EMBEDDERS:
            raise ValueError(
                f"Unknown embedder: {backend_type}. "
                f"Available: {list(cls.EMBEDDERS.keys())}. "
                f"Or provide embed_func parameter for custom embedders."
            )
        
        backend_class = cls.EMBEDDERS[backend_type]
        
        # Instantiate with appropriate parameters
        if backend_type == "fastembed":
            return backend_class(
                model_name=config.get("embedding_model", "BAAI/bge-small-en-v1.5")
            )
        else:
            return backend_class()
    
    @classmethod
    def load_vectorstore(
        cls,
        config: Dict[str, Any],
        custom_instance: Optional[VectorStore] = None,
        add_vectors_func: Optional[Callable[[List[str], List[List[float]], List[str], Optional[List[Dict]]], None]] = None,
        search_func: Optional[Callable[[List[float], int, Optional[Dict]], List[Dict[str, Any]]]] = None,
        connect_func: Optional[Callable[[], None]] = None,
        disconnect_func: Optional[Callable[[], None]] = None,
        delete_func: Optional[Callable[[List[str]], None]] = None,
        update_func: Optional[Callable[[List[str], List[List[float]]], None]] = None
    ) -> VectorStore:
        """
        Load vector store - supports built-in and custom vector stores.
        
        Args:
            config: Configuration dictionary with keys:
                - vectorstore_backend: "chroma" (default)
                - vectorstore_name: Custom name for vectorstore (default: "custom")
                - vectorstore_path: Path to persist data (default: "./vectorshield_data")
                - vectorstore_collection: Collection name (default: "documents")
            custom_instance: Optional custom vector store instance
            add_vectors_func: Custom function to add vectors
            search_func: Custom function to search vectors
            connect_func: Optional connect function
            disconnect_func: Optional disconnect function
            delete_func: Optional delete function
            update_func: Optional update function
            
        Returns:
            VectorStore instance
            
        Raises:
            ValueError: If unknown vectorstore backend specified
            
        Examples:
            # Built-in Chroma
            >>> config = {"vectorstore_backend": "chroma"}
            >>> vectorstore = ComponentLoader.load_vectorstore(config)
            
            # Custom Pinecone
            >>> import pinecone
            >>> pinecone.init(api_key="xxx")
            >>> index = pinecone.Index("my-index")
            >>> vectorstore = ComponentLoader.load_vectorstore(
            ...     config={"vectorstore_name": "pinecone-custom"},
            ...     add_vectors_func=lambda ids, embeddings, docs, meta: index.upsert([
            ...         (id_, emb, {**m, "document": doc})
            ...         for id_, emb, doc, m in zip(ids, embeddings, docs, meta or [{}]*len(ids))
            ...     ]),
            ...     search_func=lambda query, top_k, filters: [
            ...         {"id": m["id"], "score": m["score"], "document": m["metadata"].get("document")}
            ...         for m in index.query(query, top_k=top_k, filter=filters)["matches"]
            ...     ]
            ... )
            
            # Custom Weaviate
            >>> import weaviate
            >>> client = weaviate.Client("http://localhost:8080")
            >>> vectorstore = ComponentLoader.load_vectorstore(
            ...     config={"vectorstore_name": "weaviate-custom"},
            ...     add_vectors_func=lambda ids, embeddings, docs, meta: [
            ...         client.data_object.create(
            ...             class_name="Document",
            ...             data_object={"text": doc, **(m or {})},
            ...             vector=emb
            ...         )
            ...         for id_, emb, doc, m in zip(ids, embeddings, docs, meta or [{}]*len(ids))
            ...     ],
            ...     search_func=lambda query, top_k, filters: client.query.get("Document")
            ...         .with_near_vector({"vector": query}).with_limit(top_k).do()
            ...         .get("data", {}).get("Get", {}).get("Document", [])
            ... )
        """
        # Priority 1: Direct custom instance
        if custom_instance is not None:
            return custom_instance
        
        # Priority 2: Custom functions → use GenericVectorStore
        if add_vectors_func is not None and search_func is not None:
            vectorstore_name = config.get("vectorstore_name", "custom")
            return GenericVectorStore(
                add_vectors_func=add_vectors_func,
                search_func=search_func,
                connect_func=connect_func,
                disconnect_func=disconnect_func,
                delete_func=delete_func,
                update_func=update_func,
                name=vectorstore_name
            )
        
        # Priority 3: Built-in vector stores
        backend_type = config.get("vectorstore_backend", "chroma")
        
        if backend_type not in cls.VECTORSTORES:
            raise ValueError(
                f"Unknown vectorstore backend: {backend_type}. "
                f"Available: {list(cls.VECTORSTORES.keys())}. "
                f"Or provide add_vectors_func and search_func for custom stores."
            )
        
        backend_class = cls.VECTORSTORES[backend_type]
        
        # Instantiate with appropriate parameters
        if backend_type == "chroma":
            return backend_class(
                persist_directory=config.get("vectorstore_path", "./vectorshield_data"),
                collection_name=config.get("vectorstore_collection", "documents")
            )
        else:
            return backend_class()
    
    @classmethod
    def load_tracker(
        cls,
        config: Dict[str, Any],
        custom_instance: Optional[Tracker] = None
    ) -> Tracker:
        """
        Load tracker for monitoring and experiment tracking.
        
        Args:
            config: Configuration dictionary with keys:
                - tracking_enabled: Enable tracking (default: False)
                - tracking_backend: "mlflow" or "none" (default: "none")
                - mlflow_tracking_uri: MLflow server URI (default: "http://localhost:5000")
                - mlflow_experiment_name: Experiment name (default: "vectorshield")
            custom_instance: Optional custom tracker instance
            
        Returns:
            Tracker instance (NoOpTracker if tracking disabled)
            
        Raises:
            ValueError: If unknown tracker backend specified
            
        Examples:
            # Disable tracking (default)
            >>> config = {"tracking_enabled": False}
            >>> tracker = ComponentLoader.load_tracker(config)
            
            # Enable MLflow tracking
            >>> config = {
            ...     "tracking_enabled": True,
            ...     "tracking_backend": "mlflow",
            ...     "mlflow_tracking_uri": "http://localhost:5000",
            ...     "mlflow_experiment_name": "my_experiment"
            ... }
            >>> tracker = ComponentLoader.load_tracker(config)
        """
        if custom_instance is not None:
            return custom_instance
        
        # If tracking disabled, use NoOpTracker
        if not config.get("tracking_enabled", False):
            return NoOpTracker()
        
        backend_type = config.get("tracking_backend", "none")
        
        if backend_type not in cls.TRACKERS:
            raise ValueError(
                f"Unknown tracker backend: {backend_type}. "
                f"Available: {list(cls.TRACKERS.keys())}"
            )
        
        backend_class = cls.TRACKERS[backend_type]
        
        # Instantiate with appropriate parameters
        if backend_type == "mlflow":
            return backend_class(
                tracking_uri=config.get("mlflow_tracking_uri", "http://localhost:5000"),
                experiment_name=config.get("mlflow_experiment_name", "vectorshield")
            )
        else:
            return backend_class()
    
    @classmethod
    def load_all(
        cls,
        config: Dict[str, Any],
        custom_cache: Optional[CacheBackend] = None,
        custom_embedder: Optional[Embedder] = None,
        custom_vectorstore: Optional[VectorStore] = None,
        custom_tracker: Optional[Tracker] = None,
        # Cache functions
        cache_get_func: Optional[Callable[[str], Any]] = None,
        cache_set_func: Optional[Callable[[str, Any, Optional[int]], None]] = None,
        cache_connect_func: Optional[Callable[[], None]] = None,
        cache_disconnect_func: Optional[Callable[[], None]] = None,
        cache_delete_func: Optional[Callable[[str], None]] = None,
        cache_clear_func: Optional[Callable[[], None]] = None,
        # Embedder functions
        embed_func: Optional[Callable[[str], List[float]]] = None,
        embed_batch_func: Optional[Callable[[List[str]], List[List[float]]]] = None,
        # VectorStore functions
        add_vectors_func: Optional[Callable[[List[str], List[List[float]], List[str], Optional[List[Dict]]], None]] = None,
        search_func: Optional[Callable[[List[float], int, Optional[Dict]], List[Dict[str, Any]]]] = None,
        vectorstore_connect_func: Optional[Callable[[], None]] = None,
        vectorstore_disconnect_func: Optional[Callable[[], None]] = None,
        vectorstore_delete_func: Optional[Callable[[List[str]], None]] = None,
        vectorstore_update_func: Optional[Callable[[List[str], List[List[float]]], None]] = None
    ) -> Dict[str, Any]:
        """
        Load all components at once.
        
        Convenience method that loads cache, embedder, vectorstore, and tracker.
        
        Args:
            config: Configuration dictionary
            custom_cache: Optional custom cache
            custom_embedder: Optional custom embedder
            custom_vectorstore: Optional custom vector store
            custom_tracker: Optional custom tracker
            cache_get_func: Optional custom cache get function
            cache_set_func: Optional custom cache set function
            cache_connect_func: Optional custom cache connect function
            cache_disconnect_func: Optional custom cache disconnect function
            cache_delete_func: Optional custom cache delete function
            cache_clear_func: Optional custom cache clear function
            embed_func: Optional custom embed function
            embed_batch_func: Optional custom batch embed function
            add_vectors_func: Optional custom add vectors function
            search_func: Optional custom search function
            vectorstore_connect_func: Optional custom vectorstore connect function
            vectorstore_disconnect_func: Optional custom vectorstore disconnect function
            vectorstore_delete_func: Optional custom vectorstore delete function
            vectorstore_update_func: Optional custom vectorstore update function
            
        Returns:
            Dictionary with keys: "cache", "embedder", "vectorstore", "tracker"
            
        Examples:
            # Load all with defaults
            >>> components = ComponentLoader.load_all({})
            
            # Load all with custom Redis and Pinecone
            >>> import redis
            >>> import pinecone
            >>> client = redis.Redis()
            >>> pinecone.init(api_key="xxx")
            >>> index = pinecone.Index("my-index")
            >>> 
            >>> components = ComponentLoader.load_all(
            ...     config={
            ...         "cache_name": "redis-prod",
            ...         "vectorstore_name": "pinecone-prod"
            ...     },
            ...     cache_get_func=lambda key: client.get(key),
            ...     cache_set_func=lambda key, val, ttl: client.setex(key, ttl or 3600, val),
            ...     add_vectors_func=lambda ids, embs, docs, meta: index.upsert(...),
            ...     search_func=lambda query, top_k, filters: index.query(...)
            ... )
        """
        return {
            "cache": cls.load_cache(
                config,
                custom_cache,
                get_func=cache_get_func,
                set_func=cache_set_func,
                connect_func=cache_connect_func,
                disconnect_func=cache_disconnect_func,
                delete_func=cache_delete_func,
                clear_func=cache_clear_func
            ),
            "embedder": cls.load_embedder(
                config,
                custom_embedder,
                embed_func=embed_func,
                embed_batch_func=embed_batch_func
            ),
            "vectorstore": cls.load_vectorstore(
                config,
                custom_vectorstore,
                add_vectors_func=add_vectors_func,
                search_func=search_func,
                connect_func=vectorstore_connect_func,
                disconnect_func=vectorstore_disconnect_func,
                delete_func=vectorstore_delete_func,
                update_func=vectorstore_update_func
            ),
            "tracker": cls.load_tracker(config, custom_tracker),
        }