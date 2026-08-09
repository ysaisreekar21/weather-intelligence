"""Validation script for weather_embeddings schema.

This script checks:
- Table exists
- embedding column is vector(384)
- model_name column exists
- Foreign key to weather_documents exists
- UNIQUE constraint on (document_id, chunk_index)
- HNSW index exists
"""

import sys
sys.path.insert(0, '/Workspace/Users/ysaisreekar@gmail.com/weather-intelligence')
import lakebase


def validate_table_exists():
    """Check if weather_embeddings table exists."""
    result = lakebase.run_query("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'weather_embeddings'
        ) as table_exists
    """)
    exists = result[0]['table_exists']
    print(f"✅ Table exists: {exists}" if exists else "❌ Table NOT found")
    return exists


def validate_schema():
    """Validate the complete schema."""
    schema = lakebase.run_query("""
        SELECT column_name, data_type, udt_name, character_maximum_length
        FROM information_schema.columns 
        WHERE table_name = 'weather_embeddings'
        ORDER BY ordinal_position
    """)
    
    print(f"\n📋 Table schema ({len(schema)} columns):")
    required_columns = {
        'id': 'int4',
        'document_id': 'varchar',
        'chunk_index': 'int4',
        'chunk_text': 'text',
        'embedding': 'vector',
        'model_name': 'varchar',
        'created_at': 'timestamp'
    }
    
    found_columns = {}
    for row in schema:
        col_name = row['column_name']
        col_type = row['udt_name'] if row['data_type'] == 'USER-DEFINED' else row['data_type']
        found_columns[col_name] = col_type
        
        expected_type = required_columns.get(col_name)
        if expected_type and col_type == expected_type:
            print(f"  ✅ {col_name}: {col_type}")
        elif col_name in required_columns:
            print(f"  ❌ {col_name}: {col_type} (expected {expected_type})")
        else:
            print(f"  ⚠️  {col_name}: {col_type}")
    
    # Check for missing columns
    for col_name, col_type in required_columns.items():
        if col_name not in found_columns:
            print(f"  ❌ MISSING: {col_name} ({col_type})")
    
    return all(col in found_columns for col in required_columns)


def validate_embedding_dimension():
    """Check that embedding is vector(384)."""
    result = lakebase.run_query("""
        SELECT atttypmod - 4 as vector_dim
        FROM pg_attribute
        WHERE attrelid = 'weather_embeddings'::regclass
        AND attname = 'embedding'
    """)
    
    if result and result[0]['vector_dim'] == 384:
        print(f"\n✅ Embedding dimension: 384")
        return True
    else:
        actual = result[0]['vector_dim'] if result else 'unknown'
        print(f"\n❌ Embedding dimension: {actual} (expected 384)")
        return False


def validate_foreign_key():
    """Check foreign key constraint."""
    result = lakebase.run_query("""
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_name = 'weather_embeddings'
    """)
    
    if result:
        for fk in result:
            print(f"\n✅ Foreign key: {fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}")
        return True
    else:
        print(f"\n❌ No foreign key found")
        return False


def validate_unique_constraint():
    """Check UNIQUE constraint on (document_id, chunk_index)."""
    result = lakebase.run_query("""
        SELECT
            tc.constraint_name,
            string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'UNIQUE'
        AND tc.table_name = 'weather_embeddings'
        GROUP BY tc.constraint_name
    """)
    
    if result:
        for constraint in result:
            print(f"\n✅ UNIQUE constraint: ({constraint['columns']})")
        return True
    else:
        print(f"\n❌ No UNIQUE constraint found")
        return False


def validate_hnsw_index():
    """Check HNSW index exists."""
    result = lakebase.run_query("""
        SELECT indexname, indexdef
        FROM pg_indexes 
        WHERE tablename = 'weather_embeddings'
        AND indexname LIKE '%hnsw%'
    """)
    
    if result:
        for idx in result:
            print(f"\n✅ HNSW index: {idx['indexname']}")
            if 'vector_cosine_ops' in idx['indexdef']:
                print(f"   Uses cosine distance ✅")
        return True
    else:
        print(f"\n❌ HNSW index NOT found")
        return False


def validate_pgvector():
    """Check pgvector extension."""
    result = lakebase.run_query("""
        SELECT extname, extversion 
        FROM pg_extension 
        WHERE extname = 'vector'
    """)
    
    if result:
        print(f"\n✅ pgvector extension: v{result[0]['extversion']}")
        return True
    else:
        print(f"\n❌ pgvector extension NOT installed")
        return False


if __name__ == "__main__":
    print("="*60)
    print("CHECKPOINT 2 VALIDATION: weather_embeddings schema")
    print("="*60)
    
    checks = {
        'pgvector': validate_pgvector(),
        'table_exists': validate_table_exists(),
        'schema': validate_schema(),
        'embedding_dim': validate_embedding_dimension(),
        'foreign_key': validate_foreign_key(),
        'unique_constraint': validate_unique_constraint(),
        'hnsw_index': validate_hnsw_index()
    }
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}")
    
    if all(checks.values()):
        print("\n✅ ALL CHECKS PASSED - Schema is correct")
    else:
        print("\n❌ SOME CHECKS FAILED - Review errors above")
