"""Setup script to create weather_documents and weather_embeddings tables in Lakebase.

Run this once to initialize the database schema.
"""

import lakebase

# SQL DDL for weather_documents table
CREATE_DOCUMENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weather_documents (
    id VARCHAR(255) PRIMARY KEY,
    location VARCHAR(500) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    headline TEXT,
    narrative_text TEXT,
    issued_at TIMESTAMP,
    effective_at TIMESTAMP,
    payload JSONB,
    synced_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_weather_location ON weather_documents(location);
CREATE INDEX IF NOT EXISTS idx_weather_source_type ON weather_documents(source_type);
CREATE INDEX IF NOT EXISTS idx_weather_synced_at ON weather_documents(synced_at);
"""

# SQL DDL for pgvector extension and weather_embeddings table
CREATE_EMBEDDINGS_TABLE_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create weather_embeddings table with 384-dimensional vectors
CREATE TABLE IF NOT EXISTS weather_embeddings (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL REFERENCES weather_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    model_name VARCHAR(255) NOT NULL DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, chunk_index)
);

-- Create HNSW index for fast cosine similarity search
-- m: max number of connections per layer (16 is a good default)
-- ef_construction: size of dynamic candidate list (64 is a good default)
CREATE INDEX IF NOT EXISTS weather_embeddings_hnsw_idx 
    ON weather_embeddings 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Create index on document_id for efficient lookups
CREATE INDEX IF NOT EXISTS idx_weather_embeddings_document_id 
    ON weather_embeddings(document_id);

-- Create index on created_at for temporal queries
CREATE INDEX IF NOT EXISTS idx_weather_embeddings_created_at 
    ON weather_embeddings(created_at);
"""


def create_weather_documents_table():
    """Create the weather_documents table and indexes."""
    print("Creating weather_documents table...")
    
    try:
        lakebase.run_write(CREATE_DOCUMENTS_TABLE_SQL)
        print("✅ Successfully created weather_documents table and indexes")
        
        # Verify table exists
        result = lakebase.run_query("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'weather_documents'
            ORDER BY ordinal_position
        """)
        
        print(f"\nTable schema ({len(result)} columns):")
        for row in result:
            print(f"  - {row['column_name']}: {row['data_type']}")
            
    except Exception as e:
        print(f"❌ Error creating weather_documents table: {str(e)}")
        raise


def create_weather_embeddings_table():
    """Create the weather_embeddings table with pgvector support."""
    print("\nCreating weather_embeddings table with pgvector...")
    
    try:
        # Execute DDL statements
        lakebase.run_write(CREATE_EMBEDDINGS_TABLE_SQL)
        print("✅ Successfully created weather_embeddings table and HNSW index")
        
        # Verify pgvector extension
        result = lakebase.run_query("""
            SELECT extname, extversion 
            FROM pg_extension 
            WHERE extname = 'vector'
        """)
        
        if result:
            print(f"\n✅ pgvector extension: v{result[0]['extversion']}")
        else:
            print("\n⚠️  Warning: pgvector extension not found")
        
        # Verify table schema
        schema_result = lakebase.run_query("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns 
            WHERE table_name = 'weather_embeddings'
            ORDER BY ordinal_position
        """)
        
        print(f"\nTable schema ({len(schema_result)} columns):")
        for row in schema_result:
            col_type = row['udt_name'] if row['data_type'] == 'USER-DEFINED' else row['data_type']
            print(f"  - {row['column_name']}: {col_type}")
        
        # Verify HNSW index
        index_result = lakebase.run_query("""
            SELECT 
                indexname, 
                indexdef
            FROM pg_indexes 
            WHERE tablename = 'weather_embeddings'
            AND indexname LIKE '%hnsw%'
        """)
        
        if index_result:
            print(f"\n✅ HNSW index created: {index_result[0]['indexname']}")
        else:
            print("\n⚠️  Warning: HNSW index not found")
            
    except Exception as e:
        print(f"❌ Error creating weather_embeddings table: {str(e)}")
        raise


if __name__ == "__main__":
    print("Setting up Weather Intelligence database tables...\n")
    print("=" * 60)
    
    # Create tables in order (documents first, then embeddings)
    create_weather_documents_table()
    create_weather_embeddings_table()
    
    print("\n" + "=" * 60)
    print("✅ Database setup complete!")
    print("\nNext steps:")
    print("  1. Run: python app.py (start the Flask API)")
    print("  2. POST to /weather/sync to fetch weather data")
    print("  3. Run: python ingest_weather_embeddings.py (generate embeddings)")
    print("  4. POST to /weather/search for semantic search")
