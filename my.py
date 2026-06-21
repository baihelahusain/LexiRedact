from lexiredact import LexiredactPipeline, load_config

config = load_config("lexiredact_config.yaml")
pipeline = LexiredactPipeline(config)

my_chunks = [
    {"id": "doc_001", "text": "Alice Johnson called support at alice@acme.com about billing"},
    {"id": "doc_002", "text": "The server at 192.168.1.1 triggered a security alert"}
]

results = pipeline.ingest(my_chunks)

for r in results:
    print(r.chunk_id, "|", r.sanitized_text, "|", r.latency_ms, "ms")