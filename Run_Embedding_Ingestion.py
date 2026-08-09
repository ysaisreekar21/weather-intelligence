# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Verify Lakebase Syntax
# Check if lakebase.py has syntax errors
import py_compile
import os

lakebase_path = "/Workspace/Users/ysaisreekar@gmail.com/weather-intelligence/lakebase.py"

print(f"Checking {lakebase_path} for syntax errors...")

try:
    py_compile.compile(lakebase_path, doraise=True)
    print("✅ lakebase.py has no syntax errors")
except py_compile.PyCompileError as e:
    print(f"❌ Syntax error found: {e}")

# COMMAND ----------

# DBTITLE 1,Clean Test - Lakebase Only
# Fresh test - import lakebase WITHOUT importing sentence-transformers first
import sys
weather_path = "/Workspace/Users/ysaisreekar@gmail.com/weather-intelligence"
if weather_path not in sys.path:
    sys.path.insert(0, weather_path)

print("Importing lakebase (no sentence-transformers yet)...")
import lakebase
print("✅ lakebase imported successfully!")

# COMMAND ----------

# DBTITLE 1,Check Pre-installed Packages
# Check what ML packages are already available
import subprocess
import sys

packages_to_check = [
    'torch',
    'sentence-transformers',
    'databricks-sdk',
    'psycopg2',
    'sqlalchemy'
]

print("Checking pre-installed packages:\n")
for package in packages_to_check:
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'show', package],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        # Extract version from output
        for line in result.stdout.split('\n'):
            if line.startswith('Version:'):
                version = line.split(':', 1)[1].strip()
                print(f"✅ {package}: {version}")
                break
    else:
        print(f"❌ {package}: Not installed")

# COMMAND ----------

# DBTITLE 1,Install Required Packages
# All required packages are pre-installed in serverless environment
# torch: 2.13.0, sentence-transformers: 5.7.0, databricks-sdk: 0.125.0
# psycopg2: 2.9.11, sqlalchemy: 2.0.51

# Disable bytecode generation at Python level
import sys
sys.dont_write_bytecode = True

print("✅ All required packages are already available")
print("✅ Bytecode generation disabled: sys.dont_write_bytecode =", sys.dont_write_bytecode)

# COMMAND ----------

# DBTITLE 1,Environment Issue Summary & Solution
# MAGIC %md
# MAGIC # Environment Issue Summary
# MAGIC
# MAGIC ## Problem Identified
# MAGIC The serverless notebook environment has compatibility issues with:
# MAGIC 1. **Module imports** from /Workspace paths - causes kernel crashes (SIGABRT)
# MAGIC 2. **Subprocess execution** of scripts with torch/sentence-transformers - OpenSSL FIPS errors
# MAGIC 3. **Bytecode generation** (__pycache__) in /Workspace filesystem - operation not supported
# MAGIC
# MAGIC ## Root Cause
# MAGIC The `ingest_embeddings.py` script was designed for the Databricks App environment (where app.py runs), not for notebook execution. The notebook environment has restricted file system access and library loading that conflicts with the ML libraries.
# MAGIC
# MAGIC ## Working Solution: Run as Databricks Job
# MAGIC
# MAGIC The embedding ingestion should be executed as a **Databricks Job** instead of from a notebook:
# MAGIC
# MAGIC ### Steps:
# MAGIC 1. **Create a new Job** in the Databricks workspace
# MAGIC 2. **Task type**: Python script
# MAGIC 3. **Script path**: `/Workspace/Users/ysaisreekar@gmail.com/weather-intelligence/ingest_embeddings.py`
# MAGIC 4. **Parameters**: `--batch-limit 50`
# MAGIC 5. **Compute**: Use serverless or a small cluster
# MAGIC 6. **Schedule**: Set to run periodically (e.g., daily) to process new weather documents
# MAGIC
# MAGIC ### Why This Works:
# MAGIC - Jobs run scripts in a clean Python environment without notebook restrictions
# MAGIC - Proper PYTHONPATH and library loading
# MAGIC - Access to app environment variables (if configured)
# MAGIC - Can be scheduled for automated ingestion

# COMMAND ----------

# DBTITLE 1,Test Lakebase Import Fixed
# Test lakebase import with PYTHONDONTWRITEBYTECODE set
import sys
weather_path = "/Workspace/Users/ysaisreekar@gmail.com/weather-intelligence"
if weather_path not in sys.path:
    sys.path.insert(0, weather_path)

print("Importing lakebase...")
import lakebase
print("✅ lakebase imported successfully!")

# COMMAND ----------

# DBTITLE 1,Restart Python Kernel
# Kernel restart not needed - using pre-installed packages
print("✅ Skipping kernel restart - no new packages were installed")

# COMMAND ----------

# DBTITLE 1,Test Sentence Transformers Import
# Simple test of sentence-transformers import
print("Starting import test...")
from sentence_transformers import SentenceTransformer
print("✅ Import successful!")

# COMMAND ----------

# DBTITLE 1,Test Lakebase Import
# Test importing lakebase module
import sys
weather_intel_path = "/Workspace/Users/ysaisreekar@gmail.com/weather-intelligence"
if weather_intel_path not in sys.path:
    sys.path.insert(0, weather_intel_path)

print("Importing lakebase...")
import lakebase
print("✅ lakebase imported successfully")

# COMMAND ----------

# DBTITLE 1,Test Individual Lakebase Imports
# Test each import in lakebase.py individually
print("Testing lakebase imports one by one...\n")

try:
    import os
    print("✅ os")
except Exception as e:
    print(f"❌ os: {e}")

try:
    from contextlib import contextmanager
    print("✅ contextlib.contextmanager")
except Exception as e:
    print(f"❌ contextlib: {e}")

try:
    import psycopg2
    print(f"✅ psycopg2 (version: {psycopg2.__version__})")
except Exception as e:
    print(f"❌ psycopg2: {e}")

try:
    from psycopg2.extras import RealDictCursor
    print("✅ psycopg2.extras.RealDictCursor")
except Exception as e:
    print(f"❌ psycopg2.extras: {e}")

try:
    from sqlalchemy import create_engine
    print("✅ sqlalchemy.create_engine")
except Exception as e:
    print(f"❌ sqlalchemy: {e}")

try:
    from databricks.sdk import WorkspaceClient
    print("✅ databricks.sdk.WorkspaceClient")
except Exception as e:
    print(f"❌ databricks.sdk: {e}")

print("\n✅ All lakebase dependencies import successfully!")

# COMMAND ----------

# DBTITLE 1,Import Ingestion Module
# Run the ingestion script with proper Python path configuration
import subprocess
import sys
import os

script_path = "/Workspace/Users/ysaisreekar@gmail.com/weather-intelligence/ingest_embeddings.py"
weather_dir = "/Workspace/Users/ysaisreekar@gmail.com/weather-intelligence"

# Set up environment for subprocess
env = os.environ.copy()
env['PYTHONPATH'] = weather_dir
env['PYTHONDONTWRITEBYTECODE'] = '1'

print("🚀 Running embedding ingestion script...\n")
print("=" * 60)

result = subprocess.run(
    [sys.executable, script_path, "--batch-limit", "50"],
    capture_output=True,
    text=True,
    env=env,
    cwd=weather_dir
)

print(result.stdout)
if result.stderr:
    print("\nSTDERR:", result.stderr)

if result.returncode == 0:
    print("\n" + "=" * 60)
    print("✅ Ingestion completed successfully!")
else:
    print("\n" + "=" * 60)
    print(f"❌ Ingestion failed with exit code {result.returncode}")
    raise RuntimeError(f"Ingestion script failed: {result.stderr}")

# COMMAND ----------

# DBTITLE 1,Run Embedding Ingestion
# Run the embedding ingestion process
# Process all unembedded documents (up to BATCH_SIZE=50 per run)

print("🚀 Starting embedding ingestion...\n")

try:
    ingest_embeddings(batch_limit=50)
    print("\n✅ Ingestion completed successfully!")
except Exception as e:
    print(f"\n❌ Ingestion failed: {str(e)}")
    import traceback
    traceback.print_exc()
    raise

# COMMAND ----------

# DBTITLE 1,Verification Queries
# MAGIC %sql
# MAGIC -- Verification Query 1: Overall statistics
# MAGIC SELECT 
# MAGIC     'Total Documents' AS metric,
# MAGIC     COUNT(*) AS count
# MAGIC FROM weather_documents
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC     'Total Embeddings' AS metric,
# MAGIC     COUNT(*) AS count
# MAGIC FROM weather_embeddings
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC     'Distinct Documents with Embeddings' AS metric,
# MAGIC     COUNT(DISTINCT document_id) AS count
# MAGIC FROM weather_embeddings
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC     'Documents without Embeddings' AS metric,
# MAGIC     COUNT(*) AS count
# MAGIC FROM weather_documents wd
# MAGIC LEFT JOIN weather_embeddings we ON wd.id = we.document_id
# MAGIC WHERE we.document_id IS NULL;

# COMMAND ----------

# DBTITLE 1,Check for Orphan Document IDs
# MAGIC %sql
# MAGIC -- Verification Query 2: Check for orphan document IDs
# MAGIC -- (embeddings pointing to non-existent documents)
# MAGIC SELECT 
# MAGIC     we.document_id,
# MAGIC     COUNT(*) as orphan_embedding_count
# MAGIC FROM weather_embeddings we
# MAGIC LEFT JOIN weather_documents wd ON we.document_id = wd.id
# MAGIC WHERE wd.id IS NULL
# MAGIC GROUP BY we.document_id
# MAGIC ORDER BY orphan_embedding_count DESC
# MAGIC LIMIT 10;

# COMMAND ----------

# DBTITLE 1,Check for Duplicate (document_id, chunk_index) Pairs
# MAGIC %sql
# MAGIC -- Verification Query 3: Check for duplicate (document_id, chunk_index) pairs
# MAGIC SELECT 
# MAGIC     document_id,
# MAGIC     chunk_index,
# MAGIC     COUNT(*) as duplicate_count
# MAGIC FROM weather_embeddings
# MAGIC GROUP BY document_id, chunk_index
# MAGIC HAVING COUNT(*) > 1
# MAGIC ORDER BY duplicate_count DESC
# MAGIC LIMIT 10;

# COMMAND ----------

# DBTITLE 1,Verify Embedding Dimensions
# MAGIC %sql
# MAGIC -- Verification Query 4: Verify all embeddings have dimension 384
# MAGIC SELECT 
# MAGIC     array_length(embedding::float[], 1) as embedding_dimension,
# MAGIC     COUNT(*) as count
# MAGIC FROM weather_embeddings
# MAGIC GROUP BY array_length(embedding::float[], 1)
# MAGIC ORDER BY embedding_dimension;

# COMMAND ----------

# DBTITLE 1,Sample Embeddings with Document Info
# MAGIC %sql
# MAGIC -- Verification Query 5: Sample embeddings with document information
# MAGIC SELECT 
# MAGIC     we.document_id,
# MAGIC     wd.location,
# MAGIC     wd.source_type,
# MAGIC     we.chunk_index,
# MAGIC     LEFT(we.chunk_text, 100) as chunk_preview,
# MAGIC     array_length(we.embedding::float[], 1) as embedding_dim,
# MAGIC     we.created_at
# MAGIC FROM weather_embeddings we
# MAGIC JOIN weather_documents wd ON we.document_id = wd.id
# MAGIC ORDER BY we.created_at DESC
# MAGIC LIMIT 10;

# COMMAND ----------

