# Weather Intelligence

A Databricks-based weather intelligence pipeline that harvests unstructured weather data from the National Weather Service (NWS), stores it in Lakebase PostgreSQL, generates vector embeddings, and provides semantic search through a Flask REST API.

## 1. Data Source

This project uses the National Weather Service (NWS) API:

https://api.weather.gov

NWS was selected because it is a public API that does not require an API key and provides useful unstructured weather text, including active weather alerts and narrative forecasts.

The application resolves locations to NWS grid points and retrieves weather information for the requested locations.

## 2. Schema and Embedding Design

### weather_documents

Raw and normalized weather documents are stored in the `weather_documents` table.

The table includes:

- `id` - Stable document identifier used for deduplication
- `location` - Weather location
- `source_type` - Alert or forecast
- `headline` - Weather event or forecast headline
- `narrative_text` - Free-text weather information used for embedding
- `issued_at` - Document issue time
- `effective_at` - Effective time
- `payload` - Original NWS API response stored as JSON
- `synced_at` - Time the document was synchronized
- `created_at` - Record creation time

### weather_embeddings

Vectorized weather text is stored in the `weather_embeddings` table.

The project uses:

- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Embedding dimension: `384`
- Chunk size: `800`
- Chunk overlap: `100`
- Vector type: `vector(384)`
- Similarity search: pgvector cosine distance using the `<=>` operator
- Vector index: HNSW with `vector_cosine_ops`

Weather documents are divided into chunks when necessary before generating embeddings.

The embedding pipeline uses `psycopg2` to write directly to Lakebase rather than Spark JDBC.

## 3. End-to-End Pipeline

The pipeline follows:

NWS API → Weather Documents → Embeddings → Lakebase → Semantic Search API

### Step 1: Sync weather data

Send a POST request to:

`POST /weather/sync`

Example request:

```json
{
  "locations": ["Chicago, IL", "Austin, TX"],
  "limit": 50
}

This retrieves weather data from NWS, normalizes the responses, and upserts the resulting documents into weather_documents.

### Step 2: Generate embeddings

Run:

python ingest_weather_embeddings.py

The ingestion script:

Reads weather documents that do not yet have embeddings.
Chunks the narrative text.
Generates 384-dimensional embeddings using all-MiniLM-L6-v2.
Writes the vectors to weather_embeddings using psycopg2.

Step 3: Semantic search

Send a POST request to:

POST /weather/search

Example:

{
  "query": "flash flood risk this weekend",
  "top_k": 5
}

## 4. Known Limitations and Future Improvements
The current implementation focuses on NWS weather alerts and forecast information.

Search quality depends on the available weather documents and embedding model.

The system currently uses a single embedding model, all-MiniLM-L6-v2.

Additional weather sources could be added in the future.
Retrieval could be improved with metadata filtering, such as location or source type.

A scheduled job could be added to periodically synchronize new weather information.

The search results could be extended into a full RAG workflow that generates natural-language weather summaries.