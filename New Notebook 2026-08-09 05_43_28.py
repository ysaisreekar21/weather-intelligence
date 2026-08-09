# Databricks notebook source
import psycopg2
print("PSYCOPG2 OK")

# COMMAND ----------

import psycopg2

conn = psycopg2.connect(
    host="ep-nameless-queen-d8s7qam4.database.us-east-2.cloud.databricks.com",
    dbname="databricks_postgres",
    user="ysaisreekar@gmail.com",
    password="eyJraWQiOiJqblJxRmciLCJhbGciOiJSUzI1NiIsInR5cCI6ImF0K2p3dCJ9.eyJpc3MiOiJodHRwczovL2RiYy1mODkyNjEzZi1lMjBkLmNsb3VkLmRhdGFicmlja3MuY29tL29pZGMiLCJzdWIiOiJ5c2Fpc3JlZWthckBnbWFpbC5jb20iLCJhdWQiOlsiNzQ3NDY1MzIyMjQxNTM3MCJdLCJpYXQiOjE3ODYyMzQ2MTIsImV4cCI6MTc4NjIzODIxMiwianRpIjoiOTYxZGE1ZWUtNzI4ZS00MDExLWE5NmEtNWYwZjIzNjcwMDAwIiwiY2xpZW50X2lkIjoiZGItZGF0YWJhc2UtY3JlZGVudGlhbCIsInNjb3BlIjoiaWFtLmN1cnJlbnQtdXNlcjpyZWFkIGlhbS5ncm91cHM6cmVhZCBpYW0uc2VydmljZS1wcmluY2lwYWxzOnJlYWQgaWFtLnVzZXJzOnJlYWQiLCJwY3R4IjoiQ29FRUNoUUlBUm9HQ05hTjM5TUdJZ1lJdFA3ZjB3WW9BaEtaQXdHb05xWThDME1zTFdnUFFNNkpGNnlydk9kN2pMajZpOVQyZy1vb21zOURiVmh6bUhLTE8yNXFlaEdXZi00M2JGY21pRkdQYU5jUlJxb29pMXEyU2V0OFVzV0FCd19Hb2h1b0psTkx6dmwwOHdLeHk4TjI2b1lvV0tvN3pJaGFaWDdWYkxjY2VnTk9yaF9lbnZmM3BYbEszSTJoMlBHYW1USldoTF9pb1dUd3AzX3JabjJJd0lFZVgyLVRQcl80eUt6UHJfYVZBS3p6bURONXRQY016M01UOFU1MU5NV3FDZndEX18wOEQyQTNxN0dTQmVlYVI5MW03QThqbkgtRWNTak9NUnBuNkMyQVY0X2lGa0dTUU5ObFN6N0hyVWF6U1B2QVdtQ0NwNTBCV29IbjFNMkF6UlRNaERSQktORExQcUVKZ2JxZGF0LXZsTXNNMXZKLXN5cURVblpZOUNDUUNycmxkT2dtQ1oxMTBQQ2hjY0lPU00tQklTc1pYRV95dmVGLWhpeExZOFVLeHFlc0JHZVV5X0J5OGwzSUJoYTJubENVb3NXSHo3VTF3NDlITndUMlRtenlKOHRyNW5aMUFXazYyQXpQZjFSNmZRYXhaYTdKTmgxaDhMeHlLNWJVVF9UYWI3M3UwcjVjWnVjeE5tZ3FGbXh5TmJBcjNJVl80cmVOT3ZpWE9VTTZXLVIxZjdOQS0zdFc4UzA4RlNBenRtVWFUUUdPZjh2Vk1FWUNJUUNFR1RLaV9Bd2Z1Y1loSHBRWXRUOGZPNk1KYjFHV2hrd1ZEeHZYQTQyYm9nSWhBUHp0MzBGN1hWTFZiQTl0TmVUSjdtUm5KblZzakRSX3ZZNlJsZks0bW1lMCJ9.VkbdimSUnG6bxZRC9dFwoOUBHUajcE1gxJa4NhzsippQGAkXOrOq14Hl0WWc49G8WVG48RM2ekpz1cLrm__Y_LTJQ8Q5-NrVOZ-jYjEH_Jm07cLRLFe4YUFHdr3r_TUtMWC2PYM-Vj1gXY8xC50U3Vuq-52oGVmriSyAEGnmPXQkUZacXzradOufpP9KQIn59ytstvhFwI2hY6xx_JNU8ZS2lGRqh7_ZKaJDOpBYiBGv6Mb8uzbsa0eR-1DkvepIrnsQjEZcA9AJ8OZqUOk-NRTxncC-h5_bfqDe60tZTH-himuUN0plHB4HhGBYnY64luwvMPgRqzmWCc0cfWNxDg",
    sslmode="require"
)

print("LAKEBASE CONNECTION OK")

# COMMAND ----------

cur = conn.cursor()

cur.execute("SELECT 1;")
print(cur.fetchone())

cur.close()

# COMMAND ----------

cur = conn.cursor()

cur.execute("""
SELECT COUNT(*)
FROM weather_embeddings;
""")

print("Embeddings rows:", cur.fetchone()[0])

cur.close()

# COMMAND ----------

cur = conn.cursor()

cur.execute("""
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT document_id) AS unique_documents,
    COUNT(DISTINCT embedding) AS unique_embeddings
FROM weather_embeddings;
""")

print(cur.fetchone())

cur.close()

# COMMAND ----------

cur = conn.cursor()

cur.execute("""
SELECT
    document_id,
    chunk_index,
    LEFT(chunk_text, 100) AS text_preview
FROM weather_embeddings
ORDER BY id
LIMIT 5;
""")

for row in cur.fetchall():
    print(row)

cur.close()

# COMMAND ----------



# COMMAND ----------

from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

query = "showers and thunderstorms"
query_embedding = model.encode(query).tolist()

cur = conn.cursor()

cur.execute("""
SELECT
    document_id,
    chunk_index,
    LEFT(chunk_text, 150) AS text_preview,
    embedding <=> %s::vector AS distance
FROM weather_embeddings
ORDER BY embedding <=> %s::vector
LIMIT 5;
""", (query_embedding, query_embedding))

for row in cur.fetchall():
    print(row)

cur.close()

# COMMAND ----------

import psycopg2

conn = psycopg2.connect(
    host="ep-nameless-queen-d8s7qam4.database.us-east-2.cloud.databricks.com",
    dbname="databricks_postgres",
    user="ysaisreekar@gmail.com",
    password=credential.token,
    sslmode="require"
)

print("Reconnected to Lakebase")

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

credential = w.postgres.generate_database_credential(
    endpoint="projects/weather-intelligence/branches/production/endpoints/primary"
)

print("Credential generated")

# COMMAND ----------

import psycopg2

conn = psycopg2.connect(
    host="ep-nameless-queen-d8s7qam4.database.us-east-2.cloud.databricks.com",
    dbname="databricks_postgres",
    user="ysaisreekar@gmail.com",
    password="eyJraWQiOiJqblJxRmciLCJhbGciOiJSUzI1NiIsInR5cCI6ImF0K2p3dCJ9.eyJpc3MiOiJodHRwczovL2RiYy1mODkyNjEzZi1lMjBkLmNsb3VkLmRhdGFicmlja3MuY29tL29pZGMiLCJzdWIiOiJ5c2Fpc3JlZWthckBnbWFpbC5jb20iLCJhdWQiOlsiNzQ3NDY1MzIyMjQxNTM3MCJdLCJpYXQiOjE3ODYyMzU4NTcsImV4cCI6MTc4NjIzOTQ1NywianRpIjoiODMxYWNkZGQtMzdhOS00OGMwLWIzODgtOWMxODc2NzdmYzEyIiwiY2xpZW50X2lkIjoiZGItZGF0YWJhc2UtY3JlZGVudGlhbCIsInNjb3BlIjoiaWFtLmN1cnJlbnQtdXNlcjpyZWFkIGlhbS5ncm91cHM6cmVhZCBpYW0uc2VydmljZS1wcmluY2lwYWxzOnJlYWQgaWFtLnVzZXJzOnJlYWQiLCJwY3R4IjoiQ29FRUNoUUlBUm9HQ0xPWDM5TUdJZ1lJa1lqZzB3WW9BaEtaQXdHb05xWThyeHJwSURXMG5FNUZYbW92allrSDFfZ0JPQWVkSEp4Y0NpeDJuTi1senZ2REk4c3VFeHBQcUhlMmh6WTFqNHlqaUFqTXlTQnphQTlMOXpJQnVRcDRtWV95OFZOeW1OWUlsTWJYOU9FYzg2U0FsSXRpTmgxWWtlM1JMQWtXY2pXVTVjR2pXNkJWUnhJRk5ra0trRnM0S1c3RFFTUnRTS05mdGpTZnM1YXQ1VV93NjNQQXJvd21hbFJvX3JUa2FpMWxiV2N6c2ZXLWtLdWl3c0dsZU9sLWpkaHdqVjBia3MzMjBwc1JHNmNFQjNJM1RrZko2aXhtLXFFRllXSDdVOC1iZlVpeVQ0YUhHTlhMaHFKV2dGQnNONm81ZFUyeVBGZk1acjl5MHRURmR6WTNZRHlER29VQmlMaGFVSnY5eEptOUFtREUwVUlMNzJKVF9qRVp5dlRRTzZIM0EzbGhGSk5FTVRpU0tZc0lPaEpRaTFXQzRYZEJhYm1tTFFmc3RLXzZhOFc3UnhNNjdCdU80aEczMXFLZVNfcE84WGkwWklfbXJOVTRLOGhXSnRFcHdTV0JoTXhBMVlQZXRmUXpTc29fRTdFbnlxNnVFbVJxY19oY1ZXbHdwRG5rdFZ2YzZ3NjlKbnNFV3Q2SWdHSlh2cU13SjBJakgzcmxfM05XWDhGRTFDN0ZlMVliRm1VS1NRRXJzeGdwT3o4ZlYwQWFUUUdPZjh2Vk1FWUNJUURtMU50aEo5ZjQxSDc3VTQ2UlhNcmpja1BNTkhwcV9wX1R3MTdaRkxZa2FRSWhBTXQxV1dnbG9wVVQ5NFFIWWJESVA1NWRyU09lNVZGQVRBa2hyamk4cjFWTiJ9.d3wTSqJnKNuRQ9u1nVspvet_VBTK0flUl0iIDDafr9RYIrlqxwrh5_8QaM7EdYzrEWuy_j0vk03sgH2lrhbz9R7qf1tokRkP9gHmqM6Omn2-dSv6mIuMlnudhR83a8binkL81IcNE7WNg2__RcqksrJSUpvfGE61Mo4LylATeEw8XaWSH07jkrHLSu-Vfsu1HXJ33sGHmMp99MfVjxQzY-p-1OEEHRMCHnTD8C6eSQjE2-6DoqXxHOU2pp6KAgi7yMFrm29JSfUkmmAS_aSW9qUwMOz8pMCkZYZHyYPL_mSvC30qT8CTMz4ZUgzdoDVw7jOdPJG1m8c28Y_hkTE9pg",
    sslmode="require"
)

print("Lakebase reconnected")

# COMMAND ----------

from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

query = "showers and thunderstorms"
query_embedding = model.encode(query).tolist()

cur = conn.cursor()

cur.execute("""
SELECT
    document_id,
    chunk_index,
    LEFT(chunk_text, 150) AS text_preview,
    embedding <=> %s::vector AS distance
FROM weather_embeddings
ORDER BY embedding <=> %s::vector
LIMIT 5;
""", (query_embedding, query_embedding))

for row in cur.fetchall():
    print(row)

cur.close()

# COMMAND ----------

cur = conn.cursor()

cur.execute("""
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'weather_embeddings'
ORDER BY ordinal_position;
""")

print("COLUMNS:")
for row in cur.fetchall():
    print(row)

print("\nINDEXES:")

cur.execute("""
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'weather_embeddings';
""")

for row in cur.fetchall():
    print(row)

cur.close()

# COMMAND ----------

import psycopg2

conn = psycopg2.connect(
    host="ep-nameless-queen-d8s7qam4.database.us-east-2.cloud.databricks.com",
    dbname="databricks_postgres",
    user="ysaisreekar@gmail.com",
    password="eyJraWQiOiJqblJxRmciLCJhbGciOiJSUzI1NiIsInR5cCI6ImF0K2p3dCJ9.eyJpc3MiOiJodHRwczovL2RiYy1mODkyNjEzZi1lMjBkLmNsb3VkLmRhdGFicmlja3MuY29tL29pZGMiLCJzdWIiOiJ5c2Fpc3JlZWthckBnbWFpbC5jb20iLCJhdWQiOlsiNzQ3NDY1MzIyMjQxNTM3MCJdLCJpYXQiOjE3ODYyMzY1NTQsImV4cCI6MTc4NjI0MDE1NCwianRpIjoiN2Q3NTM5ODAtOTc2NC00YjkyLWJkZmEtMzQ1NWRlYjY1NmQ3IiwiY2xpZW50X2lkIjoiZGItZGF0YWJhc2UtY3JlZGVudGlhbCIsInNjb3BlIjoiaWFtLmN1cnJlbnQtdXNlcjpyZWFkIGlhbS5ncm91cHM6cmVhZCBpYW0uc2VydmljZS1wcmluY2lwYWxzOnJlYWQgaWFtLnVzZXJzOnJlYWQiLCJwY3R4IjoiQ3YwRENoUUlBUm9HQ095YzM5TUdJZ1lJeW8zZzB3WW9BaEtYQXdHb05xWThKbzRUM3RoS3dEbXFad29Zc0J1Wjdqb01iVkhtNXo2NFRqRUUyWWR2WVBFUllDeEYxNFRnUFk3eTd0QXd2UU5RUzFnaVpMSERvSkpob3JybWZDZXphakt6Vm42YllSNWNGUDJZenRFYnE0akd3TTBMY2V2Y3BPNjhXZXo3QTBIY3BncE93eUNDYUcyUU1EQldkWkZWVDRSdDFXYl9KT0lMOTFwQ1R4OTktTjJnTWtFaFBHQ2ZQNHN1ZVJzNU5tVVo3R0NmMWNEX0sxdGZxU0dnU3R0cGM2WGNveXFFa1o1eDhrWFk5ak5ZMmt2dTMyR0VnZmVIM0ZFMjE4blZ5WGoweTI3eWxaTFhiRDlDS3JJeGdEb3JacGFxcXJCUjdibEozdzc1dXJpM3dLMG4tZHQ3ektOal9UY25rNDNaa2ZTMmFfWHJIYlVrQk9IZkMzWlNIZXhkRjU1N19fcVhHYThScG1rTU1ETEJwamZDOHh1NWxHYkRDYWRaTC1BQi11dXhZbHlNYmppSG5EQ1R5bEhWbG83a3J5d0ZRa3JpMnRhMjBvTWd1enJrZXhiLWU1S21kQmhiekFfNTdMM1YxSEU1V3RDQjBSbTNxa2JDclNYRUZvYlJyNW1wTFcxMDhPSVFUQzRhbnVZZXE3OUNpaHdidWpQOE9rWnVySngtZWZub2dLdTZJdThHRnQ5aEZVZzc2T2ZMNjhRNkdrc0Jqbl9MMVRCRUFpQkZiM3hNUm1UZzlBRHFxbzZjNF80Zng3cGVxV0JSUnJyTDBscm55c2VaR1FJZ0tHdEhFYlNTdFlLZXQtbFExMEJFWXFya3BtWEhDQzJ1QnJMb2VlNWdVSmc9In0.VYTrCO_oDGvVBg4CtRNsEfpu8euSxPB2ym3HBfrax3Y65hOvlkFeamFwk87uDTXS-l3r7P-jYjj18k_e7_AnPqOxXP6s_g-Kzr53VzgjM-PSZCwrZrjWQODEBQDwuWwHi_JYebix8CwW0I1OuCO9WCXXgQCUUsSvl2Gi8w7xXaq8VUCm7p2FswSEMUz7SS14EcRFGeRP-_n0Wix1SrB6wGUhFWUpmZkzRNQ9wvEY3kv8NT2UffpEibcX8AuOzpZlAbCV1eTlMcdOhlWPYxOZI2LNuV_S9Z1sfVhnwVu8lX9q59AVwhbGBYjTYPZZzRlCLqvA234MIKY58KW1qI6j5Q",
    sslmode="require"
)

print("Lakebase reconnected")

# COMMAND ----------

cur = conn.cursor()

cur.execute("""
ALTER TABLE weather_embeddings
ADD COLUMN IF NOT EXISTS model_name VARCHAR(255);
""")

cur.execute("""
UPDATE weather_embeddings
SET model_name = 'sentence-transformers/all-MiniLM-L6-v2'
WHERE model_name IS NULL;
""")

conn.commit()

print("model_name added and populated")

cur.close()

# COMMAND ----------

cur = conn.cursor()

cur.execute("""
SELECT model_name, COUNT(*)
FROM weather_embeddings
GROUP BY model_name;
""")

print(cur.fetchall())

cur.close()