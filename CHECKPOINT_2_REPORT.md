# CHECKPOINT 2 REPORT: Weather Embeddings Database Schema

## ✅ CHANGES MADE

### File Modified: `setup_weather_embeddings.py`

**Change**: Added `model_name` column to weather_embeddings table schema

**Line 19 - Added:**
```sql
model_name VARCHAR(255) NOT NULL DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
```

**Complete Table Schema:**
```sql
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
```

## 📋 DATABASE OBJECTS DEFINED

### 1. pgvector Extension
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. weather_embeddings Table
- **Columns:**
  - `id`: SERIAL PRIMARY KEY (auto-increment)
  - `document_id`: VARCHAR(255) NOT NULL with FK to weather_documents(id) ON DELETE CASCADE
  - `chunk_index`: INTEGER NOT NULL (chunk position within document)
  - `chunk_text`: TEXT NOT NULL (actual text chunk)
  - `embedding`: vector(384) NOT NULL (384-dimensional embedding)
  - `model_name`: VARCHAR(255) NOT NULL (embedding model identifier)
  - `created_at`: TIMESTAMP DEFAULT CURRENT_TIMESTAMP

- **Constraints:**
  - PRIMARY KEY on `id`
  - FOREIGN KEY `document_id` → `weather_documents(id)` with CASCADE DELETE
  - UNIQUE constraint on (`document_id`, `chunk_index`) - prevents duplicate chunks

### 3. HNSW Index (Cosine Similarity)
```sql
CREATE INDEX IF NOT EXISTS weather_embeddings_hnsw_idx 
    ON weather_embeddings 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

**Parameters:**
- `m = 16`: Max connections per layer (good default for accuracy/speed balance)
- `ef_construction = 64`: Dynamic candidate list size during index build
- `vector_cosine_ops`: Cosine distance operator (<=> in queries)

### 4. Supporting Indexes
```sql
-- Fast document lookups
CREATE INDEX IF NOT EXISTS idx_weather_embeddings_document_id 
    ON weather_embeddings(document_id);

-- Temporal queries
CREATE INDEX IF NOT EXISTS idx_weather_embeddings_created_at 
    ON weather_embeddings(created_at);
```

## 🔍 VALIDATION REQUIREMENTS

The schema must satisfy:
1. ✅ pgvector extension installed
2. ✅ weather_embeddings table exists
3. ✅ embedding column is vector(384)
4. ✅ model_name column exists (VARCHAR 255)
5. ✅ Foreign key to weather_documents(id) with CASCADE DELETE
6. ✅ UNIQUE constraint on (document_id, chunk_index)
7. ✅ HNSW index using vector_cosine_ops

## 🚀 MANUAL STEPS REQUIRED

### Step 1: Run setup script in App environment
The setup script requires Lakebase environment variables (PGHOST, PGDATABASE, PGUSER, ENDPOINT_NAME) which are only available in the Databricks App context.

**From the App terminal or a script with App env vars:**
```bash
cd /Workspace/Users/ysaisreekar@gmail.com/weather-intelligence
python setup_weather_embeddings.py
```

**Expected output:**
```
Creating weather_embeddings table with pgvector...
✅ Successfully created weather_embeddings table and HNSW index

✅ pgvector extension: v0.x.x

Table schema (7 columns):
  - id: int4
  - document_id: varchar
  - chunk_index: int4
  - chunk_text: text
  - embedding: vector
  - model_name: varchar
  - created_at: timestamp

✅ HNSW index created: weather_embeddings_hnsw_idx
```

### Step 2: Validate schema
```bash
python validate_schema.py
```

This will verify:
- Table structure
- Embedding dimension (384)
- Foreign key constraint
- UNIQUE constraint
- HNSW index
- pgvector extension

## 📊 VALIDATION QUERIES

If you prefer manual SQL validation:

### Check table exists
```sql
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_name = 'weather_embeddings'
) as table_exists;
```

### Check embedding dimension
```sql
SELECT atttypmod - 4 as vector_dim
FROM pg_attribute
WHERE attrelid = 'weather_embeddings'::regclass
AND attname = 'embedding';
-- Should return: 384
```

### Check schema
```sql
SELECT column_name, data_type, udt_name
FROM information_schema.columns 
WHERE table_name = 'weather_embeddings'
ORDER BY ordinal_position;
```

### Check HNSW index
```sql
SELECT indexname, indexdef
FROM pg_indexes 
WHERE tablename = 'weather_embeddings'
AND indexname LIKE '%hnsw%';
```

### Check foreign key
```sql
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
AND tc.table_name = 'weather_embeddings';
```

### Check UNIQUE constraint
```sql
SELECT
    tc.constraint_name,
    string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'UNIQUE'
AND tc.table_name = 'weather_embeddings'
GROUP BY tc.constraint_name;
-- Should show: UNIQUE (document_id, chunk_index)
```

## 📁 FILES STATUS

### Modified Files:
- ✅ `setup_weather_embeddings.py` - Added model_name column

### Created Files:
- ✅ `validate_schema.py` - Validation script

### Unchanged Files:
- ✅ `lakebase.py` - No changes (reuses existing connection pattern)
- ✅ `app.py` - No changes (Part 3 ready)
- ✅ `weather_client.py` - No changes
- ✅ `requirements.txt` - No changes (all dependencies present)
- ✅ `ingest_weather_embeddings.py` - Already created correctly (from summary)

## 🎯 CHECKPOINT 2 STATUS

**STATUS**: ✅ **COMPLETE** (Code changes ready, manual execution required)

**What was done:**
1. ✅ Added `model_name` column to setup_weather_embeddings.py
2. ✅ Verified schema includes all requirements:
   - pgvector extension
   - vector(384) embedding column
   - Foreign key to weather_documents
   - UNIQUE constraint on (document_id, chunk_index)
   - HNSW cosine index
3. ✅ Created validation script

**What needs manual execution:**
1. ⏳ Run `python setup_weather_embeddings.py` in App environment
2. ⏳ Run `python validate_schema.py` to verify creation

**Next Checkpoint:**
- CHECKPOINT 3: Create embedding ingestion script (already exists per summary)

---
Generated: 2026-08-09
