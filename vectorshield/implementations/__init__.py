# """
# Default implementations for VectorShield components.

# These can be replaced with custom implementations via dependency injection.
# """

# from .cache import MemoryCache, RedisCache, NoOpCache
# from .embedding import FastEmbedEmbedder
# from .vectorstore import ChromaVectorStore
# from .tracking import MLflowTracker, NoOpTracker

# __all__ = [
#     "MemoryCache",
#     "RedisCache",
#     "NoOpCache",
#     "FastEmbedEmbedder",
#     "ChromaVectorStore",
#     "MLflowTracker",
#     "NoOpTracker",
# ]
from .embedding import FastEmbedEmbedder, GenericEmbedder  # ← Add GenericEmbedder
from .cache import MemoryCache, RedisCache, NoOpCache, GenericCache  # ← Add GenericCache
from .vectorstore import ChromaVectorStore, GenericVectorStore  # ← Add GenericVectorStore
from .tracker import MLflowTracker, NoOpTracker

__all__ = [
    # Embedders
    "FastEmbedEmbedder",
    "GenericEmbedder",  # ← Add
    # Caches
    "MemoryCache",
    "RedisCache",
    "NoOpCache",
    "GenericCache",  # ← Add
    # VectorStores
    "ChromaVectorStore",
    "GenericVectorStore",  # ← Add
    # Trackers
    "MLflowTracker",
    "NoOpTracker",
]
