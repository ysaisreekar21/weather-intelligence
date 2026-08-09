"""Setup script to create weather_documents table in Lakebase.

Run this once to initialize the database schema.
"""

import lakebase

# SQL DDL for weather_documents table
CREATE_TABLE_SQL = """
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


def create_weather_table():
    """Create the weather_documents table and indexes."""
    print("Creating weather_documents table...")
    
    try:
        lakebase.run_write(CREATE_TABLE_SQL)
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
        print(f"❌ Error creating table: {str(e)}")
        raise


if __name__ == "__main__":
    create_weather_table()
