import logging
import os

from flask import Flask, jsonify, request, send_from_directory
import json
import lakebase
import weather_client
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weather-app")

# Load embedding model once at application startup
try:
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    embedding_model_loaded = True
    embedding_model_error = None
    logger.info(f"Embedding model loaded successfully. Dimension: {embedding_model.get_sentence_embedding_dimension()}")
except Exception as e:
    embedding_model = None
    embedding_model_loaded = False
    embedding_model_error = str(e)
    logger.error(f"Failed to load embedding model: {e}")

app = Flask(__name__)


@app.route("/healthz")
def healthz():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "weather-intelligence",
        "embedding_model_loaded": embedding_model_loaded,
        "embedding_model_error": embedding_model_error
    })


@app.errorhandler(Exception)
def handle_exception(err):
    """Ensure all unhandled errors return JSON."""
    logger.exception("Unhandled exception while processing request")

    status_code = getattr(err, "code", 500)
    if not isinstance(status_code, int):
        status_code = 500

    return jsonify({"error": str(err)}), status_code


@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Weather Intelligence</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #f4f7fb;
                margin: 0;
                padding: 40px;
            }

            .container {
                max-width: 900px;
                margin: auto;
            }

            h1 {
                color: #1f2937;
            }

            .card {
                background: white;
                padding: 25px;
                border-radius: 12px;
                margin-top: 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            }

            .status {
                color: green;
                font-weight: bold;
            }

            button {
                padding: 10px 18px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
            }
        </style>
    </head>

    <body>
        <div class="container">
            <h1>🌤️ Weather Intelligence</h1>

            <div class="card">
                <h2>System Status</h2>
                <p>Status: <span class="status">Running</span></p>
                <p>Lakebase: Connected</p>
                <p>Weather data: Available</p>
            </div>

            <div class="card">
                <h2>Weather Intelligence</h2>
                <p><strong>Status:</strong> <span class="status" id="systemStatus">Loading...</span></p>
                <p><strong>Weather Documents:</strong> <span id="docCount">-</span></p>
                <p><strong>Embeddings:</strong> <span id="embCount">-</span></p>
                <p><strong>Unembedded:</strong> <span id="unembeddedCount">-</span></p>
                <button onclick="runEmbed()" style="background: #2563eb; color: white; margin-top: 10px;">Generate Embeddings</button>
                <button onclick="testSearch()" style="background: #059669; color: white; margin-top: 10px; margin-left: 10px;">Test Search</button>
            </div>

            <div class="card" id="searchResults" style="display: none;">
                <h3>Search Results</h3>
                <div id="resultsContent"></div>
            </div>
        </div>

        <script>
            async function loadStatus() {
                try {
                    const response = await fetch('/api/weather/status');
                    const data = await response.json();
                    document.getElementById('systemStatus').textContent = data.status === 'success' ? 'Active' : 'Error';
                    document.getElementById('docCount').textContent = data.weather_documents_count || 0;
                    document.getElementById('embCount').textContent = data.weather_embeddings_count || 0;
                    document.getElementById('unembeddedCount').textContent = data.unembedded_count || 0;
                } catch (e) {
                    document.getElementById('systemStatus').textContent = 'Error';
                }
            }

            async function runEmbed() {
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = 'Generating...';
                try {
                    const response = await fetch('/weather/embed', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({batch_size: 50})
                    });
                    const data = await response.json();
                    alert(`Processed: ${data.documents_processed} docs, Inserted: ${data.embeddings_inserted} embeddings`);
                    loadStatus();
                } catch (e) {
                    alert('Error: ' + e.message);
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Generate Embeddings';
                }
            }

            async function testSearch() {
                const query = prompt('Enter search query:', 'severe weather warnings');
                if (!query) return;
                try {
                    const response = await fetch('/weather/search', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({query, top_k: 5})
                    });
                    const data = await response.json();
                    
                    // Check for backend errors
                    if (data.status === 'error') {
                        alert('Search failed: ' + data.error);
                        return;
                    }
                    
                    const resultsDiv = document.getElementById('searchResults');
                    const contentDiv = document.getElementById('resultsContent');
                    
                    console.log('Search response:', data);
                    console.log('Results count:', data.results ? data.results.length : 0);
                    
                    if (data.results && data.results.length > 0) {
                        contentDiv.innerHTML = data.results.map(r => 
                            `<div style="border-left: 3px solid #2563eb; padding-left: 12px; margin: 10px 0;">
                                <strong>${r.location}</strong> (similarity: ${r.similarity.toFixed(3)})<br>
                                ${r.headline || r.narrative_text?.substring(0, 150) + '...'}
                            </div>`
                        ).join('');
                        resultsDiv.style.display = 'block';
                    } else {
                        contentDiv.innerHTML = '<p>No results found. (Backend returned 0 results)</p>';
                        resultsDiv.style.display = 'block';
                    }
                } catch (e) {
                    alert('Search error: ' + e.message);
                    console.error('Search exception:', e);
                }
            }

            loadStatus();
        </script>
    </body>
    </html>
        </div>
    </body>
    </html>
    """


@app.route("/diagnostics/env")
def diagnostics_env():
    """TEMPORARY: Report which environment variables are present (not their values)."""
    env_vars = [
        "ENDPOINT_NAME",
        "PGHOST",
        "PGDATABASE",
        "PGUSER",
        "PGPORT",
        "PGSSLMODE"
    ]
    
    env_status = {}
    for var in env_vars:
        env_status[var] = "present" if os.environ.get(var) else "missing"
    
    return jsonify({
        "status": "success",
        "environment_variables": env_status
    })


@app.route("/diagnostics/embedding-query")
def diagnostics_embedding_query():
    """TEMPORARY: Debug why get_unembedded_documents returns 0 rows.
    
    This endpoint runs the exact same query and diagnostic checks to show:
    - Total documents in weather_documents
    - Total embeddings in weather_embeddings
    - Documents that would be returned by get_unembedded_documents
    - Sample data from weather_documents
    """
    diagnostics = {
        "status": "success",
        "total_documents": 0,
        "total_embeddings": 0,
        "unembedded_count": 0,
        "unembedded_sample": [],
        "sample_documents": [],
        "tables_exist": {},
        "error": None
    }
    
    try:
        # Check if tables exist
        table_check_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('weather_documents', 'weather_embeddings')
        """
        existing_tables = lakebase.run_query(table_check_query)
        diagnostics["tables_exist"] = {
            "weather_documents": any(t["table_name"] == "weather_documents" for t in existing_tables),
            "weather_embeddings": any(t["table_name"] == "weather_embeddings" for t in existing_tables)
        }
        
        # Count total documents
        if diagnostics["tables_exist"]["weather_documents"]:
            count_docs = lakebase.run_query("SELECT COUNT(*) as count FROM weather_documents")
            diagnostics["total_documents"] = count_docs[0]["count"]
            
            # Get sample documents with field status
            sample_query = """
                SELECT 
                    id,
                    location,
                    headline IS NOT NULL AND TRIM(headline) <> '' as has_headline,
                    narrative_text IS NOT NULL AND TRIM(narrative_text) <> '' as has_narrative,
                    LENGTH(headline) as headline_len,
                    LENGTH(narrative_text) as narrative_len
                FROM weather_documents
                LIMIT 5
            """
            diagnostics["sample_documents"] = lakebase.run_query(sample_query)
        
        # Count total embeddings
        if diagnostics["tables_exist"]["weather_embeddings"]:
            count_emb = lakebase.run_query("SELECT COUNT(*) as count FROM weather_embeddings")
            diagnostics["total_embeddings"] = count_emb[0]["count"]
        
        # Run the exact query from get_unembedded_documents
        if diagnostics["tables_exist"]["weather_documents"]:
            unembedded_query = """
                SELECT 
                    wd.id,
                    wd.headline,
                    wd.narrative_text,
                    we.document_id as has_embedding
                FROM weather_documents wd
                LEFT JOIN weather_embeddings we ON wd.id = we.document_id
                WHERE we.document_id IS NULL
                AND (
                    (wd.headline IS NOT NULL AND TRIM(wd.headline) <> '')
                    OR (wd.narrative_text IS NOT NULL AND TRIM(wd.narrative_text) <> '')
                )
                ORDER BY wd.created_at DESC
                LIMIT 5
            """
            
            if diagnostics["tables_exist"]["weather_embeddings"]:
                unembedded_results = lakebase.run_query(unembedded_query)
                diagnostics["unembedded_count"] = len(unembedded_results)
                diagnostics["unembedded_sample"] = [
                    {
                        "id": r["id"],
                        "has_headline": bool(r["headline"]),
                        "has_narrative": bool(r["narrative_text"]),
                        "headline_preview": r["headline"][:50] if r["headline"] else None,
                        "narrative_preview": r["narrative_text"][:50] if r["narrative_text"] else None
                    }
                    for r in unembedded_results
                ]
            else:
                # If weather_embeddings doesn't exist, all documents are unembedded
                diagnostics["unembedded_count"] = "N/A - weather_embeddings table does not exist"
        
    except Exception as e:
        diagnostics["error"] = str(e)
        diagnostics["error_type"] = type(e).__name__
        logger.exception("Embedding query diagnostic failed")
    
    return jsonify(diagnostics)


@app.route("/diagnostics/db-role")
def diagnostics_db_role():
    """TEMPORARY: Safe database diagnostics for permission troubleshooting.
    
    Returns ONLY safe information:
    - PGUSER environment variable
    - PGDATABASE environment variable
    - Connection status
    - current_user (PostgreSQL role)
    - current_database()
    
    Does NOT return: passwords, tokens, PGHOST, PGPORT, connection strings
    """
    diagnostics = {
        "status": "success",
        "env_pguser": os.environ.get("PGUSER", "not set"),
        "env_pgdatabase": os.environ.get("PGDATABASE", "not set"),
        "connection_successful": False,
        "current_user": None,
        "current_database": None,
        "error": None
    }
    
    try:
        # Attempt connection and get PostgreSQL role information
        result = lakebase.run_query(
            "SELECT current_user, current_database()"
        )
        
        diagnostics["connection_successful"] = True
        diagnostics["current_user"] = result[0]["current_user"]
        diagnostics["current_database"] = result[0]["current_database"]
        
    except Exception as e:
        diagnostics["connection_successful"] = False
        diagnostics["error"] = str(e)
        diagnostics["error_type"] = type(e).__name__
        logger.exception("Database role check failed")
    
    return jsonify(diagnostics)


@app.route("/db-test")
def db_test():
    """Test Lakebase database connection with detailed error reporting."""
    try:
        result = lakebase.run_query("SELECT 1 AS connected")
        return jsonify({
            "status": "success",
            "message": "Lakebase connection successful",
            "result": result
        })
    except Exception as e:
        logger.exception("Database connection test failed")
        return jsonify({
            "status": "error",
            "message": "Lakebase connection failed",
            "error": str(e),
            "error_type": type(e).__name__
        }), 500


@app.route("/weather/sync", methods=["POST"])
@app.route("/api/weather/sync", methods=["POST"])
def weather_sync():
    """Sync weather data for specified locations.
    
    Request body:
        {
            "locations": ["Chicago, IL", "Austin, TX"],
            "limit": 50
        }
    
    Returns:
        {
            "status": "success",
            "documents_synced": 42,
            "locations_processed": 2
        }
    """
    try:
        if not request.is_json:
            return jsonify({
                "status": "error",
                "error": "Request must be JSON"
            }), 400
        
        data = request.get_json()
        
        locations = data.get("locations")
        if not locations:
            return jsonify({
                "status": "error",
                "error": "Missing required field: locations"
            }), 400
        
        if not isinstance(locations, list):
            return jsonify({
                "status": "error",
                "error": "locations must be a list"
            }), 400
        
        if not locations:
            return jsonify({
                "status": "error",
                "error": "locations list cannot be empty"
            }), 400
        
        limit = data.get("limit")
        if limit is not None:
            if not isinstance(limit, int) or limit <= 0:
                return jsonify({
                    "status": "error",
                    "error": "limit must be a positive integer"
                }), 400
        
        logger.info(f"Starting weather sync for {len(locations)} locations (limit: {limit})")
        
        documents = weather_client.fetch_weather_documents(locations, limit)
        
        if not documents:
            return jsonify({
                "status": "success",
                "documents_synced": 0,
                "locations_processed": len(locations),
                "message": "No documents found for the specified locations"
            })
        
        synced_count = _upsert_weather_documents(documents)
        
        logger.info(f"Successfully synced {synced_count} weather documents")
        
        return jsonify({
            "status": "success",
            "documents_synced": synced_count,
            "locations_processed": len(locations)
        })
    
    except weather_client.LocationResolutionError as e:
        logger.error(f"Location resolution failed: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Location resolution failed: {str(e)}"
        }), 400
    
    except weather_client.NWSAPIError as e:
        logger.error(f"NWS API error: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Weather service error: {str(e)}"
        }), 502
    
    except Exception as e:
        logger.exception("Unexpected error during weather sync")
        return jsonify({
            "status": "error",
            "error": f"Internal server error: {str(e)}"
        }), 500


@app.route("/api/weather/status", methods=["GET"])
def weather_status():
    """Get real-time status of weather data and embeddings.
    
    Returns:
        {
            "status": "success",
            "lakebase_connected": bool,
            "weather_documents_count": int,
            "weather_embeddings_count": int,
            "unembedded_count": int,
            "weather_available": bool,
            "embeddings_available": bool
        }
    """
    try:
        # Test Lakebase connection
        lakebase_connected = True
        try:
            lakebase.run_query("SELECT 1")
        except Exception:
            lakebase_connected = False
        
        # Get counts from database
        if lakebase_connected:
            # Count weather documents
            doc_count_result = lakebase.run_query(
                "SELECT COUNT(*) as count FROM weather_documents"
            )
            weather_docs_count = doc_count_result[0]["count"] if doc_count_result else 0
            
            # Count embeddings
            emb_count_result = lakebase.run_query(
                "SELECT COUNT(*) as count FROM weather_embeddings"
            )
            embeddings_count = emb_count_result[0]["count"] if emb_count_result else 0
            
            # Count unembedded documents
            unembedded_result = lakebase.run_query("""
                SELECT COUNT(DISTINCT wd.id) as count
                FROM weather_documents wd
                LEFT JOIN weather_embeddings we ON wd.id = we.document_id
                WHERE we.document_id IS NULL
                AND (wd.headline IS NOT NULL OR wd.narrative_text IS NOT NULL)
            """)
            unembedded_count = unembedded_result[0]["count"] if unembedded_result else 0
        else:
            weather_docs_count = 0
            embeddings_count = 0
            unembedded_count = 0
        
        return jsonify({
            "status": "success",
            "lakebase_connected": lakebase_connected,
            "weather_documents_count": weather_docs_count,
            "weather_embeddings_count": embeddings_count,
            "unembedded_count": unembedded_count,
            "weather_available": weather_docs_count > 0,
            "embeddings_available": embeddings_count > 0
        })
    
    except Exception as e:
        logger.exception("Status check failed")
        return jsonify({
            "status": "error",
            "error": str(e),
            "lakebase_connected": False,
            "weather_documents_count": 0,
            "weather_embeddings_count": 0,
            "unembedded_count": 0,
            "weather_available": False,
            "embeddings_available": False
        }), 500


@app.route("/weather/search", methods=["POST"])
def weather_search():
    """Semantic search over weather documents using pgvector."""
    try:
        logger.info("=== SEARCH REQUEST RECEIVED ===")
        logger.info(f"Request content type: {request.content_type}")
        logger.info(f"Is JSON: {request.is_json}")
        
        if not request.is_json:
            logger.error("Request is not JSON")
            return jsonify({
                "status": "error",
                "error": "Request must be JSON"
            }), 400

        data = request.get_json()
        logger.info(f"Request data: {data}")

        query = data.get("query")
        logger.info(f"Query: {query}")
        if not isinstance(query, str) or not query.strip():
            logger.error("Query validation failed")
            return jsonify({
                "status": "error",
                "error": "query must be a non-empty string"
            }), 400

        top_k = data.get("top_k", 5)

        if not isinstance(top_k, int):
            return jsonify({
                "status": "error",
                "error": "top_k must be an integer"
            }), 400

        # Clamp top_k to 1-20
        top_k = max(1, min(top_k, 20))

        # Check if embedding model is loaded
        logger.info(f"Embedding model loaded: {embedding_model_loaded}")
        logger.info(f"Embedding model error: {embedding_model_error}")
        if not embedding_model_loaded or embedding_model is None:
            logger.error("Embedding model not loaded, returning error")
            return jsonify({
                "status": "error",
                "error": f"Embedding model not loaded: {embedding_model_error}"
            }), 500

        # Generate the query embedding
        logger.info("Generating query embedding...")
        query_embedding = embedding_model.encode(
            query.strip()
        )
        logger.info(f"Query embedding generated, shape: {query_embedding.shape}")

        # Convert embedding to pgvector format
        embedding_vector = "[" + ",".join(
            str(float(value)) for value in query_embedding
        ) + "]"
        logger.info(f"Embedding vector length: {len(embedding_vector)} chars")

        search_sql = """
            SELECT
                d.id,
                d.location,
                d.headline,
                d.narrative_text,
                e.chunk_text,
                1 - (e.embedding <=> %s::vector) AS similarity
            FROM weather_embeddings e
            JOIN weather_documents d
                ON d.id = e.document_id
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
        """

        logger.info("Executing vector similarity search...")
        with lakebase.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    search_sql,
                    (
                        embedding_vector,
                        embedding_vector,
                        top_k
                    )
                )

                rows = cursor.fetchall()
                logger.info(f"Database returned {len(rows)} rows")

        results = []

        for row in rows:
            results.append({
                "id": row["id"],
                "location": row["location"],
                "headline": row["headline"],
                "narrative_text": row["narrative_text"],
                "chunk_text": row["chunk_text"],
                "similarity": float(row["similarity"])
            })

        logger.info(f"Returning {len(results)} results")
        response_data = {
            "status": "success",
            "query": query,
            "top_k": top_k,
            "results": results
        }
        logger.info(f"Response: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        # Comprehensive exception diagnostics
        import traceback
        import sys
        
        exc_type, exc_value, exc_traceback = sys.exc_info()
        
        error_details = {
            "exception_type": exc_type.__name__ if exc_type else "Unknown",
            "exception_message": str(e),
            "exception_repr": repr(e),
            "exception_args": str(e.args) if hasattr(e, 'args') else "No args",
            "exception_code": getattr(e, 'pgcode', 'N/A'),
            "traceback": traceback.format_exc()
        }
        
        logger.error(f"=== SEARCH EXCEPTION DETAILS ===")
        logger.error(f"Type: {error_details['exception_type']}")
        logger.error(f"Message: {error_details['exception_message']}")
        logger.error(f"Repr: {error_details['exception_repr']}")
        logger.error(f"Args: {error_details['exception_args']}")
        logger.error(f"PG Code: {error_details['exception_code']}")
        logger.error(f"Traceback:\n{error_details['traceback']}")
        
        return jsonify({
            "status": "error",
            "error": error_details['exception_message'],
            "error_type": error_details['exception_type'],
            "error_details": error_details,
            "debug_info": {
                "query_received": query if 'query' in locals() else "NOT_SET",
                "top_k": top_k if 'top_k' in locals() else "NOT_SET",
                "embedding_model_loaded": embedding_model_loaded
            }
        }), 500

def _upsert_weather_documents(documents):
    """Upsert weather documents into Lakebase.
    
    Args:
        documents: List of normalized weather documents
    
    Returns:
        Number of documents upserted
    """
    if not documents:
        return 0
    
    upsert_sql = """
        INSERT INTO weather_documents (
            id, location, source_type, headline, narrative_text,
            issued_at, effective_at, payload, synced_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            location = EXCLUDED.location,
            source_type = EXCLUDED.source_type,
            headline = EXCLUDED.headline,
            narrative_text = EXCLUDED.narrative_text,
            issued_at = EXCLUDED.issued_at,
            effective_at = EXCLUDED.effective_at,
            payload = EXCLUDED.payload,
            synced_at = EXCLUDED.synced_at
    """
    
    with lakebase.get_connection() as conn:
        with conn.cursor() as cursor:
            for doc in documents:
                payload_json = json.dumps(doc.get("payload"))
                
                cursor.execute(upsert_sql, (
                    doc["id"],
                    doc["location"],
                    doc["source_type"],
                    doc.get("headline"),
                    doc.get("narrative_text"),
                    doc.get("issued_at"),
                    doc.get("effective_at"),
                    payload_json,
                    doc["synced_at"]
                ))
            
            conn.commit()
    
    return len(documents)


# ============================================================================
# EMBEDDING ENDPOINTS
# ============================================================================

# Chunking configuration
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
EMBEDDING_DIM = 384
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def ensure_embeddings_table():
    """Ensure weather_embeddings table exists with pgvector support.
    
    Creates the table and indexes if they don't exist.
    Safe to call multiple times (idempotent).
    """
    sql_statements = [
        # Enable pgvector extension
        "CREATE EXTENSION IF NOT EXISTS vector",
        
        # Create weather_embeddings table with 384-dimensional vectors
        """
        CREATE TABLE IF NOT EXISTS weather_embeddings (
            id SERIAL PRIMARY KEY,
            document_id VARCHAR(255) NOT NULL REFERENCES weather_documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector(384) NOT NULL,
            model_name VARCHAR(255) NOT NULL DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(document_id, chunk_index)
        )
        """,
        
        # Create HNSW index for fast cosine similarity search
        """
        CREATE INDEX IF NOT EXISTS weather_embeddings_hnsw_idx 
            ON weather_embeddings 
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """,
        
        # Create index on document_id for efficient lookups
        "CREATE INDEX IF NOT EXISTS idx_weather_embeddings_document_id ON weather_embeddings(document_id)",
        
        # Create index on created_at for temporal queries
        "CREATE INDEX IF NOT EXISTS idx_weather_embeddings_created_at ON weather_embeddings(created_at)"
    ]
    
    try:
        with lakebase.get_connection() as conn:
            with conn.cursor() as cursor:
                for i, sql in enumerate(sql_statements):
                    logger.info(f"Executing DDL statement {i+1}/{len(sql_statements)}")
                    cursor.execute(sql)
                conn.commit()
        logger.info("Embeddings table verified/created successfully")
    except Exception as e:
        logger.error(f"Error ensuring embeddings table exists: {str(e)}")
        raise
DOCUMENT_BATCH_SIZE = 50


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        chunk_size: Maximum characters per chunk
        overlap: Number of overlapping characters between chunks
    
    Returns:
        List of text chunks
    """
    if not text or len(text.strip()) == 0:
        return []
    
    text = text.strip()
    
    # If text is shorter than chunk size, return as single chunk
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        # Get chunk from start to start + chunk_size
        end = start + chunk_size
        
        # If this is not the last chunk, try to break at sentence or word boundary
        if end < len(text):
            # Look for sentence boundary (. ! ?) within last 100 chars of chunk
            search_start = max(start, end - 100)
            sentence_breaks = []
            for i in range(search_start, end):
                if text[i] in '.!?' and i + 1 < len(text) and text[i + 1] == ' ':
                    sentence_breaks.append(i + 1)
            
            if sentence_breaks:
                end = sentence_breaks[-1]
            else:
                # Look for word boundary (space) within last 50 chars
                search_start = max(start, end - 50)
                for i in range(end - 1, search_start - 1, -1):
                    if text[i] == ' ':
                        end = i + 1
                        break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start forward by (chunk_size - overlap) to create overlap
        start = end - overlap
        
        # Ensure we're making progress
        if start <= 0 or start >= len(text):
            break
    
    return chunks


def get_unembedded_documents(limit):
    """Fetch documents that don't have embeddings yet.
    
    Args:
        limit: Maximum number of documents to fetch
    
    Returns:
        List of document dictionaries
    """
    try:
        # First check if weather_embeddings table exists
        table_check_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'weather_embeddings'
        """
        
        with lakebase.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(table_check_query)
                table_exists = len(cursor.fetchall()) > 0
        
        logger.info(f"Embeddings table exists: {table_exists}")
        
        # Build query based on whether embeddings table exists
        if table_exists:
            # Table exists - filter out already embedded documents
            query = """
                SELECT 
                    wd.id,
                    wd.headline,
                    wd.narrative_text
                FROM weather_documents wd
                LEFT JOIN weather_embeddings we ON wd.id = we.document_id
                WHERE we.document_id IS NULL
                AND (
                    (wd.headline IS NOT NULL AND TRIM(wd.headline) <> '')
                    OR (wd.narrative_text IS NOT NULL AND TRIM(wd.narrative_text) <> '')
                )
                ORDER BY wd.created_at DESC
                LIMIT %s
            """
        else:
            # Table doesn't exist - return all documents with content
            query = """
                SELECT 
                    id,
                    headline,
                    narrative_text
                FROM weather_documents
                WHERE (
                    (headline IS NOT NULL AND TRIM(headline) <> '')
                    OR (narrative_text IS NOT NULL AND TRIM(narrative_text) <> '')
                )
                ORDER BY created_at DESC
                LIMIT %s
            """

        logger.info(f"Executing query with limit={limit}")
        with lakebase.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (limit,))
                rows = cursor.fetchall()
        
        logger.info(f"Query returned {len(rows)} rows")

        result = [
            {
                "id": row["id"],
                "headline": row["headline"],
                "narrative_text": row["narrative_text"]
            }
            for row in rows
        ]
        
        logger.info(f"Returning {len(result)} documents")
        return result
        
    except Exception as e:
        logger.exception(f"Error in get_unembedded_documents: {str(e)}")
        raise


def insert_embeddings_batch(document_id, chunks_with_embeddings):
    """Insert embeddings using psycopg2 with ON CONFLICT DO NOTHING.
    
    Args:
        document_id: The weather document ID
        chunks_with_embeddings: List of (chunk_index, chunk_text, embedding) tuples
    """
    import uuid
    
    if not chunks_with_embeddings:
        return 0
    
    insert_sql = """
        INSERT INTO weather_embeddings (
            id,
            document_id, 
            chunk_index, 
            chunk_text, 
            embedding,
            model_name
        )
        VALUES (%s, %s, %s, %s, %s::vector, %s)
    """
    
    inserted = 0
    with lakebase.get_connection() as conn:
        with conn.cursor() as cursor:
            for chunk_index, chunk_text, embedding in chunks_with_embeddings:
                # Generate unique ID for this embedding
                embedding_id = str(uuid.uuid4())
                
                # Convert embedding to pgvector format string
                embedding_str = '[' + ','.join(str(float(x)) for x in embedding) + ']'
                
                cursor.execute(
                    insert_sql,
                    (embedding_id, document_id, chunk_index, chunk_text, embedding_str, MODEL_NAME)
                )
                inserted += cursor.rowcount
            
            conn.commit()
    
    return inserted


@app.route("/weather/embed", methods=["POST"])
def weather_embed():
    """Generate and store embeddings for weather documents.
    
    This endpoint processes unembedded documents in batches, chunks the text,
    generates embeddings, and stores them in weather_embeddings.
    
    Optional request body:
        {
            "batch_size": 50  (max documents to process, default 50)
        }
    
    Returns:
        {
            "status": "success",
            "documents_processed": int,
            "chunks_created": int,
            "embeddings_inserted": int
        }
    """
    try:
        # Parse batch_size parameter
        batch_size = DOCUMENT_BATCH_SIZE
        if request.is_json:
            data = request.get_json()
            if "batch_size" in data:
                batch_size = data["batch_size"]
                if not isinstance(batch_size, int) or batch_size <= 0:
                    return jsonify({
                        "status": "error",
                        "error": "batch_size must be a positive integer"
                    }), 400
                # Cap at reasonable limit
                batch_size = min(batch_size, 200)
        
        logger.info(f"Starting embedding generation for up to {batch_size} documents")
        
        # Get unembedded documents
        # Note: Table setup (CREATE TABLE, CREATE INDEX) should be done during initial
        # deployment, not on every request. The endpoint only needs INSERT/SELECT permissions.
        documents = get_unembedded_documents(batch_size)
        
        if not documents:
            return jsonify({
                "status": "success",
                "message": "No unembedded documents found",
                "documents_processed": 0,
                "chunks_created": 0,
                "embeddings_inserted": 0
            })
        
        logger.info(f"Found {len(documents)} unembedded documents")
        
        # Process documents
        total_chunks = 0
        total_embeddings = 0
        successful_docs = 0
        
        for doc in documents:
            try:
                document_id = doc['id']
                
                # Combine headline and narrative text
                text_parts = []
                if doc.get('headline') and doc['headline']:
                    text_parts.append(f"Headline: {doc['headline']}")
                if doc.get('narrative_text') and doc['narrative_text']:
                    text_parts.append(doc['narrative_text'])
                
                full_text = '\n\n'.join(text_parts)
                
                if not full_text.strip():
                    logger.warning(f"Document {document_id} has no text, skipping")
                    continue
                
                # Chunk the text
                chunks = chunk_text(full_text)
                
                if not chunks:
                    logger.warning(f"Document {document_id} produced no chunks, skipping")
                    continue
                
                # Generate embeddings for all chunks
                embeddings = embedding_model.encode(chunks, show_progress_bar=False)
                
                # Prepare chunks with embeddings
                chunks_with_embeddings = [
                    (idx, chunk, embedding.tolist())
                    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
                ]
                
                # Insert into database
                inserted = insert_embeddings_batch(document_id, chunks_with_embeddings)
                
                total_chunks += len(chunks)
                total_embeddings += inserted
                successful_docs += 1
                
                logger.info(f"Processed document {document_id}: {len(chunks)} chunks, {inserted} inserted")
                
            except Exception as doc_err:
                logger.error(f"Error processing document {doc.get('id', 'unknown')}: {str(doc_err)}")
                # Continue with next document
                continue
        
        logger.info(f"Embedding generation complete: {successful_docs} docs, {total_chunks} chunks, {total_embeddings} inserted")
        
        return jsonify({
            "status": "success",
            "documents_processed": successful_docs,
            "chunks_created": total_chunks,
            "embeddings_inserted": total_embeddings
        })
    
    except Exception as e:
        logger.exception("Embedding generation failed")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================================
# ADMIN ENDPOINTS - Part 2 Embedding Pipeline Test
# ============================================================================

@app.route("/admin/weather/embedding-test", methods=["POST"])
def admin_embedding_test():
    """Administrative endpoint for controlled embedding ingestion test.
    
    This endpoint runs a small batch test (max 3 documents) to validate
    the embedding pipeline before full production ingestion.
    
    Request body:
        {
            "limit": 1-3  (default: 1, max: 3)
        }
    
    Returns:
        {
            "status": "success" | "error",
            "documents_processed": int,
            "chunks_created": int,
            "embeddings_generated": int,
            "rows_inserted": int,
            "embedding_dimension": int,
            "errors": [str]
        }
    """
    try:
        # Parse and validate limit parameter
        limit = 1  # Default
        if request.is_json and "limit" in request.json:
            limit = request.json["limit"]
            if not isinstance(limit, int):
                return jsonify({
                    "status": "error",
                    "error": "limit must be an integer"
                }), 400
            if limit < 1 or limit > 3:
                return jsonify({
                    "status": "error",
                    "error": "limit must be between 1 and 3 for this test endpoint"
                }), 400
        
        logger.info(f"Starting embedding test with limit={limit}")
        
        # Step 1: Ensure weather_embeddings table exists
        try:
            from setup_weather_tables import create_weather_embeddings_table
            logger.info("Setting up weather_embeddings table...")
            create_weather_embeddings_table()
        except Exception as setup_err:
            logger.error(f"Setup error: {setup_err}")
            return jsonify({
                "status": "error",
                "error": f"Failed to create embeddings table: {str(setup_err)}"
            }), 500
        
        # Step 2: Get initial count for validation
        initial_count_result = lakebase.run_query(
            "SELECT COUNT(*) as count FROM weather_embeddings"
        )
        initial_count = initial_count_result[0]["count"] if initial_count_result else 0
        
        # Step 3: Run controlled ingestion
        # Import ingestion logic but capture metrics
        from ingest_weather_embeddings import (
            get_unembedded_documents,
            process_document,
            MODEL_NAME,
            EMBEDDING_DIM
        )
        from sentence_transformers import SentenceTransformer
        
        logger.info(f"Fetching up to {limit} unembedded documents...")
        documents = get_unembedded_documents(limit=limit)
        
        if not documents:
            return jsonify({
                "status": "success",
                "message": "No unembedded documents found",
                "documents_processed": 0,
                "chunks_created": 0,
                "embeddings_generated": 0,
                "rows_inserted": 0,
                "embedding_dimension": EMBEDDING_DIM,
                "errors": []
            })
        
        logger.info(f"Found {len(documents)} unembedded documents")
        logger.info(f"Loading model: {MODEL_NAME}...")
        
        # Load model for this test (isolated from app's main model)
        model = SentenceTransformer(MODEL_NAME, device="cpu")
        actual_dim = model.get_sentence_embedding_dimension()
        
        if actual_dim != EMBEDDING_DIM:
            return jsonify({
                "status": "error",
                "error": f"Model dimension mismatch: expected {EMBEDDING_DIM}, got {actual_dim}"
            }), 500
        
        logger.info(f"Model loaded successfully (dimension: {actual_dim})")
        
        # Process documents and track metrics
        total_chunks = 0
        successful_docs = 0
        errors = []
        
        for doc in documents:
            try:
                chunks_created = process_document(doc, model)
                total_chunks += chunks_created
                successful_docs += 1
                logger.info(f"Processed document {doc['id']}: {chunks_created} chunks")
            except Exception as doc_err:
                error_msg = f"Document {doc['id']}: {str(doc_err)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        # Step 4: Get final count to calculate rows inserted
        final_count_result = lakebase.run_query(
            "SELECT COUNT(*) as count FROM weather_embeddings"
        )
        final_count = final_count_result[0]["count"] if final_count_result else 0
        rows_inserted = final_count - initial_count
        
        # Step 5: Validate embeddings
        if rows_inserted > 0:
            validation_result = lakebase.run_query("""
                SELECT 
                    vector_dims(embedding) as dimensions,
                    model_name
                FROM weather_embeddings
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            if validation_result:
                validated_dim = validation_result[0]["dimensions"]
                validated_model = validation_result[0]["model_name"]
                logger.info(f"Validation: dimension={validated_dim}, model={validated_model}")
        
        # Return success response
        response = {
            "status": "success",
            "documents_processed": successful_docs,
            "chunks_created": total_chunks,
            "embeddings_generated": total_chunks,  # 1 embedding per chunk
            "rows_inserted": rows_inserted,
            "embedding_dimension": actual_dim,
            "errors": errors
        }
        
        logger.info(f"Test complete: {response}")
        return jsonify(response)
        
    except Exception as e:
        logger.exception("Embedding test failed")
        # Return error without exposing credentials
        return jsonify({
            "status": "error",
            "error": str(e),
            "documents_processed": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
            "rows_inserted": 0,
            "embedding_dimension": 0,
            "errors": [str(e)]
        }), 500


@app.route("/diagnostics/permissions", methods=["GET"])
def diagnostics_permissions():
    """Diagnostic endpoint to verify table structure and permissions.
    
    This endpoint tests:
    1. weather_embeddings table exists with correct structure
    2. App has SELECT/INSERT permissions
    3. Can query for unembedded documents
    
    Returns:
        JSON with detailed diagnostic information
    """
    results = {
        "status": "running",
        "checks": {},
        "errors": []
    }
    
    try:
        # Check 1: Table structure
        try:
            table_result = lakebase.run_query("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('weather_documents', 'weather_embeddings')
            """)
            tables = {row['table_name'] for row in table_result}
            
            results["checks"]["weather_documents_exists"] = 'weather_documents' in tables
            results["checks"]["weather_embeddings_exists"] = 'weather_embeddings' in tables
            
            if 'weather_embeddings' in tables:
                # Check columns
                cols = lakebase.run_query("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'weather_embeddings'
                """)
                column_names = {col['column_name'] for col in cols}
                required = {'id', 'document_id', 'chunk_index', 'chunk_text', 'embedding', 'model_name'}
                results["checks"]["all_columns_present"] = required.issubset(column_names)
                results["checks"]["columns"] = list(column_names)
        except Exception as e:
            results["errors"].append(f"Table structure check failed: {str(e)}")
        
        # Check 2: SELECT permissions
        try:
            lakebase.run_query("SELECT COUNT(*) as cnt FROM weather_documents")
            results["checks"]["can_select_documents"] = True
        except Exception as e:
            results["checks"]["can_select_documents"] = False
            results["errors"].append(f"SELECT on weather_documents failed: {str(e)}")
        
        try:
            lakebase.run_query("SELECT COUNT(*) as cnt FROM weather_embeddings")
            results["checks"]["can_select_embeddings"] = True
        except Exception as e:
            results["checks"]["can_select_embeddings"] = False
            results["errors"].append(f"SELECT on weather_embeddings failed: {str(e)}")
        
        # Check 3: Can query for unembedded documents
        try:
            docs = get_unembedded_documents(limit=5)
            results["checks"]["can_query_unembedded"] = True
            results["checks"]["unembedded_count"] = len(docs)
            if docs:
                results["checks"]["sample_document_id"] = docs[0].get('id')
        except Exception as e:
            results["checks"]["can_query_unembedded"] = False
            results["errors"].append(f"Query unembedded documents failed: {str(e)}")
        
        # Check 4: Row counts
        try:
            doc_count = lakebase.run_query("SELECT COUNT(*) as cnt FROM weather_documents")
            results["checks"]["total_documents"] = doc_count[0]['cnt'] if doc_count else 0
            
            emb_count = lakebase.run_query("SELECT COUNT(*) as cnt FROM weather_embeddings")
            results["checks"]["total_embeddings"] = emb_count[0]['cnt'] if emb_count else 0
        except Exception as e:
            results["errors"].append(f"Count query failed: {str(e)}")
        
        # Set overall status
        if results["errors"]:
            results["status"] = "warning"
        else:
            results["status"] = "success"
        
        return jsonify(results)
        
    except Exception as e:
        logger.exception("Diagnostics failed")
        return jsonify({
            "status": "error",
            "error": str(e),
            "checks": results.get("checks", {}),
            "errors": results.get("errors", [])
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
