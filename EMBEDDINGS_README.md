# Part 2B: Weather Vectorization

This implementation creates a vector search capability for weather documents using pgvector in Lakebase Postgres.

## Architecture

### Database Schema

**weather_embeddings table:**
- `id`: Serial primary key
- `document_id`: Foreign key to weather_documents(id)
- `chunk_index`: Index of the chunk within the document
- `chunk_text`: The actual text chunk (max 800 chars with 100 char overlap)
- `embedding`: pgvector vector(384) - 384-dimensional embedding from all-MiniLM-L6-v2
- `created_at`: Timestamp

**Indexes:**
- HNSW index on `embedding` using cosine distance for fast similarity search
- B-tree index on `document_id` for efficient document lookups
- B-tree index on `created_at` for temporal queries

### Embedding Model

**Model:** `sentence-transformers/all-MiniLM-L6-v2`
- Embedding dimension: 384
- Fast inference speed
- Good balance between quality and performance
- Optimized for semantic similarity tasks

### Chunking Strategy

- **CHUNK_SIZE:** 800 characters
- **CHUNK_OVERLAP:** 100 characters
- **Boundary detection:** Attempts to break at sentence boundaries (`.!?`) or word boundaries to maintain semantic coherence
- **Text preparation:** Combines headline and narrative_text with clear labels

## Setup Instructions

### 1. Update Dependencies

The `requirements.txt` has been updated with:
```
sentence-transformers>=2.2.2
torch>=2.0.0
```

If running locally or in a notebook, install with:
```bash
pip install -r requirements.txt
```

### 2. Create the Embeddings Table

Run the setup script to create the `weather_embeddings` table with pgvector support:

```bash
python setup_weather_embeddings.py
```

This will:
- Enable the pgvector extension
- Create the weather_embeddings table
- Create the HNSW cosine similarity index
- Create supporting indexes
- Verify the installation

### 3. Ingest Embeddings

Run the ingestion script to process weather documents:

```bash
# Process default batch (50 documents)
python ingest_embeddings.py

# Process custom batch size
python ingest_embeddings.py --batch-limit 100
```

The script will:
1. Find documents in `weather_documents` that don't have embeddings yet
2. Chunk each document's text (headline + narrative)
3. Generate 384-dim embeddings using sentence-transformers
4. Insert embeddings into `weather_embeddings` via psycopg2
5. Report progress and statistics

## Usage

### Check Embedding Status

```python
import lakebase

# Count total documents and embedded documents
stats = lakebase.run_query("""
    SELECT 
        COUNT(DISTINCT wd.id) as total_documents,
        COUNT(DISTINCT we.document_id) as embedded_documents,
        COUNT(we.id) as total_chunks
    FROM weather_documents wd
    LEFT JOIN weather_embeddings we ON wd.id = we.document_id
""")

print(stats)
```

### View Sample Embeddings

```python
import lakebase

# Get sample embeddings
samples = lakebase.run_query("""
    SELECT 
        we.document_id,
        we.chunk_index,
        LEFT(we.chunk_text, 100) as chunk_preview,
        array_length(we.embedding::float[], 1) as embedding_dim
    FROM weather_embeddings we
    LIMIT 5
""")

for sample in samples:
    print(f"Doc: {sample['document_id']}, Chunk: {sample['chunk_index']}")
    print(f"Preview: {sample['chunk_preview']}...")
    print(f"Embedding dim: {sample['embedding_dim']}")
    print()
```

### Find Similar Documents (Vector Search)

```python
from sentence_transformers import SentenceTransformer
import lakebase

# Load model
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Create query embedding
query = "What is the weather forecast for tomorrow?"
query_embedding = model.encode(query).tolist()
embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

# Search for similar chunks
results = lakebase.run_query("""
    SELECT 
        we.document_id,
        we.chunk_text,
        wd.headline,
        wd.location,
        1 - (we.embedding <=> %s::vector) as similarity
    FROM weather_embeddings we
    JOIN weather_documents wd ON we.document_id = wd.id
    ORDER BY we.embedding <=> %s::vector
    LIMIT 5
""", (embedding_str, embedding_str))

for result in results:
    print(f"Similarity: {result['similarity']:.3f}")
    print(f"Location: {result['location']}")
    print(f"Headline: {result['headline']}")
    print(f"Text: {result['chunk_text'][:200]}...")
    print()
```

## Performance Notes

### HNSW Index Parameters

- **m=16**: Max connections per layer (default, good for most use cases)
- **ef_construction=64**: Size of dynamic candidate list during index build (higher = better quality, slower build)

For production, you may tune:
- Increase `m` (e.g., 32) for better recall at the cost of memory
- Increase `ef_construction` (e.g., 128) for higher quality index

### Query Performance

Set `ef_search` at query time for speed/accuracy tradeoff:

```sql
SET hnsw.ef_search = 100;  -- Higher = more accurate, slower
```

### Batch Processing

- Default batch: 50 documents per run
- Embedding batch: 32 chunks at a time for efficiency
- Run incrementally as new documents are synced

## Next Steps

- ✅ Part 2B Complete: Vector embeddings infrastructure
- ⏳ Part 2C: Implement `/api/weather/search` endpoint for semantic search
- ⏳ Add search UI to the dashboard
- ⏳ Implement hybrid search (vector + keyword)
