import logging
import os

from flask import Flask, jsonify, request
import json
import lakebase
import weather_client
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weather-app")

# Load embedding model once at application startup
embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

app = Flask(__name__)


@app.route("/healthz")
def healthz():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "weather-intelligence"
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
                <h2>Weather Dashboard</h2>
                <p>Weather search and intelligence features will be available in Part 2.</p>
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/db-test")
def db_test():
    """Test Lakebase database connection."""
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
            "error": str(e)
        }), 500


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


@app.route("/weather/search", methods=["POST"])
def weather_search():
    """Semantic search over weather documents using pgvector."""
    try:
        if not request.is_json:
            return jsonify({
                "status": "error",
                "error": "Request must be JSON"
            }), 400

        data = request.get_json()

        query = data.get("query")
        if not isinstance(query, str) or not query.strip():
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

        # Generate the query embedding
        query_embedding = embedding_model.encode(
            query.strip()
        )

        # Convert embedding to pgvector format
        embedding_vector = "[" + ",".join(
            str(float(value)) for value in query_embedding
        ) + "]"

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

        results = []

        for row in rows:
            results.append({
                "id": row[0],
                "location": row[1],
                "headline": row[2],
                "narrative_text": row[3],
                "chunk_text": row[4],
                "similarity": float(row[5])
            })

        return jsonify({
            "status": "success",
            "query": query,
            "top_k": top_k,
            "results": results
        })

    except Exception as e:
        logger.exception("Weather semantic search failed")

        return jsonify({
            "status": "error",
            "error": str(e)
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
            synced_at = EXCLUDED.synced_at,
            updated_at = CURRENT_TIMESTAMP
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
            from setup_weather_embeddings import create_embeddings_table
            logger.info("Setting up weather_embeddings table...")
            create_embeddings_table()
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
