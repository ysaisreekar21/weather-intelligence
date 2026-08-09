"""Embedding ingestion script for weather documents.

This script:
1. Reads unembedded documents from weather_documents table
2. Chunks text using CHUNK_SIZE=800 and CHUNK_OVERLAP=100
3. Generates 384-dimensional embeddings using sentence-transformers/all-MiniLM-L6-v2
4. Inserts embeddings into weather_embeddings table via psycopg2
5. Safe to rerun - uses ON CONFLICT to avoid duplicates
"""

import logging
import time
import os
from typing import List, Tuple

# Prevent tokenizer parallelism warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from sentence_transformers import SentenceTransformer
from psycopg2.extras import execute_values
import lakebase

# Chunking configuration
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# Model configuration
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Batch processing configuration
BATCH_SIZE = 50  # Process documents in batches
EMBEDDING_BATCH_SIZE = 32  # Embed chunks in batches for efficiency

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
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


def get_unembedded_documents(limit: int = BATCH_SIZE) -> List[dict]:
    """Fetch documents from weather_documents that don't have embeddings yet.

    Args:
        limit: Maximum number of documents to fetch

    Returns:
        List of document dictionaries with id, headline, and narrative_text
    """
    query = """
        SELECT 
            wd.id,
            wd.headline,
            wd.narrative_text
        FROM weather_documents wd
        LEFT JOIN weather_embeddings we ON wd.id = we.document_id
        WHERE we.document_id IS NULL
        AND (wd.headline IS NOT NULL OR wd.narrative_text IS NOT NULL)
        ORDER BY wd.created_at DESC
        LIMIT %s
    """

    with lakebase.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()

    return [
        {
            "id": row["id"],
            "headline": row["headline"],
            "narrative_text": row["narrative_text"]
        }
        for row in rows
    ]


def insert_embeddings_batch(document_id: str, chunks_with_embeddings: List[Tuple[int, str, List[float]]]):
    """Insert embeddings into weather_embeddings table using batch insert.
    
    Args:
        document_id: The weather document ID
        chunks_with_embeddings: List of (chunk_index, chunk_text, embedding) tuples
    """
    if not chunks_with_embeddings:
        return
    
    insert_sql = """
        INSERT INTO weather_embeddings (
            document_id, 
            chunk_index, 
            chunk_text, 
            embedding,
            model_name
        )
        VALUES %s
        ON CONFLICT (document_id, chunk_index) DO UPDATE SET
            chunk_text = EXCLUDED.chunk_text,
            embedding = EXCLUDED.embedding,
            model_name = EXCLUDED.model_name,
            created_at = CURRENT_TIMESTAMP
    """
    
    # Prepare values for batch insert
    # Each tuple: (document_id, chunk_index, chunk_text, embedding_str, model_name)
    values = []
    for chunk_index, chunk_text, embedding in chunks_with_embeddings:
        # Convert embedding list to PostgreSQL vector format string
        embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
        values.append((document_id, chunk_index, chunk_text, embedding_str, MODEL_NAME))
    
    with lakebase.get_connection() as conn:
        with conn.cursor() as cursor:
            # Use execute_values for efficient batch insert
            # Template uses %s::vector to cast the string to vector type
            execute_values(
                cursor,
                insert_sql,
                values,
                template="(%s, %s, %s, %s::vector, %s)"
            )
            conn.commit()


def process_document(doc: dict, model: SentenceTransformer) -> int:
    """Process a single document: chunk, embed, and store.
    
    Args:
        doc: Document dictionary with id, headline, narrative_text
        model: Loaded SentenceTransformer model
    
    Returns:
        Number of chunks processed
    """
    document_id = doc['id']
    
    # Combine headline and narrative text
    text_parts = []
    if doc.get('headline') and doc['headline']:
        text_parts.append(f"Headline: {doc['headline']}")
    if doc.get('narrative_text') and doc['narrative_text']:
        text_parts.append(doc['narrative_text'])
    
    full_text = '\n\n'.join(text_parts)
    
    if not full_text.strip():
        logger.warning(f"Document {document_id} has no text content, skipping")
        return 0
    
    # Chunk the text
    chunks = chunk_text(full_text)
    
    if not chunks:
        logger.warning(f"Document {document_id} produced no chunks, skipping")
        return 0
    
    logger.info(f"Processing document {document_id}: {len(chunks)} chunks")
    
    # Generate embeddings for all chunks in batches
    all_embeddings = []
    for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch = chunks[i:i + EMBEDDING_BATCH_SIZE]
        batch_embeddings = model.encode(batch, show_progress_bar=False)
        all_embeddings.extend(batch_embeddings)
    
    # Prepare chunks with their embeddings
    chunks_with_embeddings = [
        (idx, chunk, embedding.tolist())
        for idx, (chunk, embedding) in enumerate(zip(chunks, all_embeddings))
    ]
    
    # Insert into database using batch insert
    insert_embeddings_batch(document_id, chunks_with_embeddings)
    
    return len(chunks)


def ingest_embeddings(batch_limit: int = BATCH_SIZE):
    """Main ingestion process.
    
    Args:
        batch_limit: Number of documents to process in this run
    """
    logger.info("="*60)
    logger.info("Starting embedding ingestion process")
    logger.info(f"Configuration: CHUNK_SIZE={CHUNK_SIZE}, CHUNK_OVERLAP={CHUNK_OVERLAP}")
    logger.info(f"Model: {MODEL_NAME} (dimension: {EMBEDDING_DIM})")
    logger.info("="*60)
    
    # Load the sentence transformer model
    logger.info("Loading model...")
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    actual_dim = model.get_sentence_embedding_dimension()
    
    if actual_dim != EMBEDDING_DIM:
        raise ValueError(f"Model dimension mismatch: expected {EMBEDDING_DIM}, got {actual_dim}")
    
    logger.info(f"✅ Model loaded successfully (dimension: {actual_dim})")
    
    # Get unembedded documents
    logger.info(f"\nFetching up to {batch_limit} unembedded documents...")
    documents = get_unembedded_documents(limit=batch_limit)
    
    if not documents:
        logger.info("\n✅ No unembedded documents found. All documents are up to date.")
        return
    
    logger.info(f"Found {len(documents)} unembedded documents to process\n")
    
    # Process each document
    total_chunks = 0
    total_embeddings = 0
    successful_docs = 0
    failed_docs = 0
    
    start_time = time.time()
    
    for idx, doc in enumerate(documents, 1):
        try:
            chunks_processed = process_document(doc, model)
            total_chunks += chunks_processed
            total_embeddings += chunks_processed
            successful_docs += 1
            
            if idx % 10 == 0:
                elapsed = time.time() - start_time
                rate = idx / elapsed
                logger.info(f"Progress: {idx}/{len(documents)} docs ({rate:.1f} docs/sec)")
        
        except Exception as e:
            logger.error(f"Failed to process document {doc['id']}: {str(e)}")
            failed_docs += 1
            continue
    
    elapsed_time = time.time() - start_time
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("✅ Embedding ingestion complete")
    logger.info(f"  Documents found: {len(documents)}")
    logger.info(f"  Documents processed successfully: {successful_docs}")
    logger.info(f"  Documents failed: {failed_docs}")
    logger.info(f"  Total chunks created: {total_chunks}")
    logger.info(f"  Total embeddings generated: {total_embeddings}")
    logger.info(f"  Rows inserted: {total_embeddings}")
    logger.info(f"  Time elapsed: {elapsed_time:.1f}s")
    if successful_docs > 0:
        logger.info(f"  Average rate: {successful_docs/elapsed_time:.1f} docs/sec")
    logger.info("="*60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Ingest weather document embeddings into Lakebase'
    )
    parser.add_argument(
        '--batch-limit',
        type=int,
        default=BATCH_SIZE,
        help=f'Number of documents to process (default: {BATCH_SIZE})'
    )
    
    args = parser.parse_args()
    
    ingest_embeddings(batch_limit=args.batch_limit)
