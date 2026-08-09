"""Validation script for PART 2: Weather Embeddings Infrastructure

This script validates:
A. weather_embeddings table exists
B. embedding column is vector(384)
C. Document counts
D. Embedding counts
E. Vector dimensions
F. No duplicate document chunks
G. HNSW index exists
"""

import lakebase


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def validate_table_exists():
    """A. Verify weather_embeddings table exists."""
    print_section("A. Table Existence")
    
    result = lakebase.run_query("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'weather_embeddings'
        ) as table_exists
    """)
    
    exists = result[0]['table_exists']
    
    if exists:
        print("✅ weather_embeddings table exists")
    else:
        print("❌ weather_embeddings table NOT found")
        return False
    
    return True


def validate_schema():
    """B. Verify embedding column is vector(384)."""
    print_section("B. Schema Validation")
    
    # Get all columns
    result = lakebase.run_query("""
        SELECT 
            column_name, 
            data_type,
            udt_name,
            character_maximum_length
        FROM information_schema.columns 
        WHERE table_name = 'weather_embeddings'
        ORDER BY ordinal_position
    """)
    
    print(f"\nTable has {len(result)} columns:")
    for row in result:
        col_name = row['column_name']
        col_type = row['udt_name'] if row['data_type'] == 'USER-DEFINED' else row['data_type']
        print(f"  - {col_name}: {col_type}")
    
    # Check embedding column specifically
    embedding_cols = [r for r in result if r['column_name'] == 'embedding']
    
    if not embedding_cols:
        print("\n❌ embedding column NOT found")
        return False
    
    embedding_col = embedding_cols[0]
    
    if embedding_col['udt_name'] == 'vector':
        print("\n✅ embedding column is type 'vector'")
        
        # Check dimension
        dim_result = lakebase.run_query("""
            SELECT 
                atttypmod - 4 as vector_dim
            FROM pg_attribute
            WHERE attrelid = 'weather_embeddings'::regclass
            AND attname = 'embedding'
        """)
        
        if dim_result and dim_result[0]['vector_dim'] == 384:
            print("✅ embedding dimension is 384")
            return True
        else:
            actual_dim = dim_result[0]['vector_dim'] if dim_result else 'unknown'
            print(f"❌ embedding dimension is {actual_dim}, expected 384")
            return False
    else:
        print(f"\n❌ embedding column is {embedding_col['udt_name']}, expected 'vector'")
        return False


def validate_document_counts():
    """C. Check weather_documents count."""
    print_section("C. Document Count")
    
    result = lakebase.run_query("""
        SELECT COUNT(*) as total_docs
        FROM weather_documents
    """)
    
    count = result[0]['total_docs']
    print(f"Total documents in weather_documents: {count}")
    
    if count > 0:
        print("✅ Documents found")
        return True
    else:
        print("⚠️  No documents found in weather_documents")
        return False


def validate_embedding_counts():
    """D. Check weather_embeddings count."""
    print_section("D. Embedding Count")
    
    result = lakebase.run_query("""
        SELECT 
            COUNT(*) as total_embeddings,
            COUNT(DISTINCT document_id) as unique_documents
        FROM weather_embeddings
    """)
    
    if result:
        total = result[0]['total_embeddings']
        unique = result[0]['unique_documents']
        print(f"Total embeddings: {total}")
        print(f"Unique documents embedded: {unique}")
        
        if total > 0:
            print("✅ Embeddings found")
            return True
        else:
            print("⚠️  No embeddings found yet (run ingest_weather_embeddings.py)")
            return False
    else:
        print("❌ Could not query embeddings")
        return False


def validate_dimensions():
    """E. Verify vector_dims() function works on embeddings."""
    print_section("E. Dimension Validation")
    
    result = lakebase.run_query("""
        SELECT 
            document_id,
            chunk_index,
            vector_dims(embedding) as dims
        FROM weather_embeddings
        LIMIT 5
    """)
    
    if not result:
        print("⚠️  No embeddings to validate dimensions")
        return False
    
    print(f"\nChecking dimensions on {len(result)} sample embeddings:")
    all_correct = True
    for row in result:
        doc_id = row['document_id']
        chunk_idx = row['chunk_index']
        dims = row['dims']
        status = "✅" if dims == 384 else "❌"
        print(f"  {status} Doc {doc_id} chunk {chunk_idx}: {dims} dimensions")
        if dims != 384:
            all_correct = False
    
    if all_correct:
        print("\n✅ All embeddings have correct dimensions (384)")
        return True
    else:
        print("\n❌ Some embeddings have incorrect dimensions")
        return False


def validate_no_duplicates():
    """F. Check for duplicate document chunks."""
    print_section("F. Duplicate Check")
    
    result = lakebase.run_query("""
        SELECT 
            document_id, 
            chunk_index, 
            COUNT(*) as count
        FROM weather_embeddings
        GROUP BY document_id, chunk_index
        HAVING COUNT(*) > 1
    """)
    
    if not result or len(result) == 0:
        print("✅ No duplicate document chunks found")
        return True
    else:
        print(f"❌ Found {len(result)} duplicate document chunk combinations:")
        for row in result[:5]:  # Show first 5
            print(f"  - Doc {row['document_id']}, chunk {row['chunk_index']}: {row['count']} copies")
        return False


def validate_hnsw_index():
    """G. Verify HNSW index exists."""
    print_section("G. HNSW Index Validation")
    
    result = lakebase.run_query("""
        SELECT 
            indexname,
            indexdef
        FROM pg_indexes 
        WHERE tablename = 'weather_embeddings'
        AND indexname LIKE '%hnsw%'
    """)
    
    if result:
        for row in result:
            print(f"✅ Index found: {row['indexname']}")
            print(f"   Definition: {row['indexdef'][:100]}...")
        return True
    else:
        print("❌ No HNSW index found on weather_embeddings")
        return False


def validate_pgvector_extension():
    """Verify pgvector extension is installed."""
    print_section("pgvector Extension")
    
    result = lakebase.run_query("""
        SELECT extname, extversion 
        FROM pg_extension 
        WHERE extname = 'vector'
    """)
    
    if result:
        version = result[0]['extversion']
        print(f"✅ pgvector extension installed (version {version})")
        return True
    else:
        print("❌ pgvector extension NOT installed")
        return False


def validate_model_name():
    """Check model_name column exists and has correct values."""
    print_section("Model Name Validation")
    
    result = lakebase.run_query("""
        SELECT DISTINCT model_name, COUNT(*) as count
        FROM weather_embeddings
        GROUP BY model_name
    """)
    
    if not result:
        print("⚠️  No embeddings to check model_name")
        return False
    
    print("\nModel names in use:")
    all_correct = True
    for row in result:
        model = row['model_name']
        count = row['count']
        expected = "sentence-transformers/all-MiniLM-L6-v2"
        status = "✅" if model == expected else "❌"
        print(f"  {status} {model}: {count} embeddings")
        if model != expected:
            all_correct = False
    
    return all_correct


def main():
    """Run all validations."""
    print("\n" + "█"*60)
    print("  PART 2 VALIDATION: Weather Embeddings Infrastructure")
    print("█"*60)
    
    results = {}
    
    # Run validations
    results['pgvector'] = validate_pgvector_extension()
    results['table_exists'] = validate_table_exists()
    
    if results['table_exists']:
        results['schema'] = validate_schema()
        results['document_count'] = validate_document_counts()
        results['embedding_count'] = validate_embedding_counts()
        
        if results['embedding_count']:
            results['dimensions'] = validate_dimensions()
            results['no_duplicates'] = validate_no_duplicates()
            results['model_name'] = validate_model_name()
        
        results['hnsw_index'] = validate_hnsw_index()
    
    # Summary
    print("\n" + "="*60)
    print("  VALIDATION SUMMARY")
    print("="*60)
    
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL VALIDATIONS PASSED")
        print("PART 2 is complete and ready to use!")
    else:
        print("⚠️  SOME VALIDATIONS FAILED")
        print("Review errors above and fix issues.")
    print("="*60 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
