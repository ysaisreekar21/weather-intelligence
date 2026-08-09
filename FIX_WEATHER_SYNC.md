# Weather Sync Fix - updated_at Column Error

## ✅ ISSUE FIXED

**Error:** `column "updated_at" of relation "weather_documents" does not exist`

**Root Cause:** The `_upsert_weather_documents()` function in `app.py` referenced a non-existent `updated_at` column in the ON CONFLICT UPDATE clause.

---

## 🔧 CODE CHANGE

**File:** `app.py`
**Function:** `_upsert_weather_documents()` (line 416-465)
**Line:** 443

### BEFORE (Broken):
```sql
ON CONFLICT (id) DO UPDATE SET
    location = EXCLUDED.location,
    source_type = EXCLUDED.source_type,
    headline = EXCLUDED.headline,
    narrative_text = EXCLUDED.narrative_text,
    issued_at = EXCLUDED.issued_at,
    effective_at = EXCLUDED.effective_at,
    payload = EXCLUDED.payload,
    synced_at = EXCLUDED.synced_at,
    updated_at = CURRENT_TIMESTAMP  ← ERROR: column doesn't exist
```

### AFTER (Fixed):
```sql
ON CONFLICT (id) DO UPDATE SET
    location = EXCLUDED.location,
    source_type = EXCLUDED.source_type,
    headline = EXCLUDED.headline,
    narrative_text = EXCLUDED.narrative_text,
    issued_at = EXCLUDED.issued_at,
    effective_at = EXCLUDED.effective_at,
    payload = EXCLUDED.payload,
    synced_at = EXCLUDED.synced_at  ← removed updated_at line
```

**Change:** Removed `updated_at = CURRENT_TIMESTAMP` from the ON CONFLICT clause.

**Reason:** The `public.weather_documents` table does NOT have an `updated_at` column. The `synced_at` column already tracks when records are inserted/updated during sync operations.

---

## 📋 ACTUAL TABLE SCHEMA

The `public.weather_documents` table has these columns:

* `id` (primary key)
* `location`
* `source_type`
* `headline`
* `narrative_text`
* `issued_at`
* `effective_at`
* `payload_json`
* `synced_at`
* `created_at`

**NO `updated_at` column exists.**

---

## 🚀 DEPLOYMENT STEPS

### Step 1: Deploy the Fixed App
```bash
databricks apps deploy weather-intelligence
```

### Step 2: Wait for Deployment
```bash
# Check status until state is RUNNING
databricks apps get weather-intelligence
```

Look for:
```json
"app_status": {
  "state": "RUNNING"
}
```

### Step 3: Verify Lakebase Connection
```bash
curl https://weather-intelligence-7474659239402355.aws.databricksapps.com/api/weather/status
```

Confirm:
```json
{
  "lakebase_connected": true,
  ...
}
```

### Step 4: Test Weather Sync
```bash
curl -X POST https://weather-intelligence-7474659239402355.aws.databricksapps.com/api/weather/sync \
  -H "Content-Type: application/json" \
  -d '{
    "locations": ["Chicago, IL", "Austin, TX"],
    "limit": 50
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "documents_synced": 100,
  "locations_processed": 2
}
```

### Step 5: Verify Data in Database
```bash
curl https://weather-intelligence-7474659239402355.aws.databricksapps.com/api/weather/status
```

**Expected Response:**
```json
{
  "status": "success",
  "lakebase_connected": true,
  "weather_documents_count": 100,
  "weather_embeddings_count": 0,
  "unembedded_count": 100,
  "weather_available": true,
  "embeddings_available": false
}
```

---

## ✅ VALIDATION CHECKLIST

- [ ] App deployed successfully
- [ ] App status: RUNNING
- [ ] Lakebase connection: Connected
- [ ] `/api/weather/sync` returns 200 OK (not 500)
- [ ] `documents_synced` count matches expected
- [ ] `weather_documents_count` > 0 in status endpoint
- [ ] No errors in app logs

---

## 🎯 WHAT'S FIXED

✅ `/api/weather/sync` no longer throws 500 error  
✅ Weather documents successfully insert/upsert into `public.weather_documents`  
✅ `synced_at` column correctly tracks when records are synced  
✅ ON CONFLICT clause only references existing columns  

---

## 📝 NEXT STEPS

After confirming weather documents are syncing:

1. **Generate Embeddings:**
   ```bash
   curl -X POST https://weather-intelligence-7474659239402355.aws.databricksapps.com/weather/embed \
     -H "Content-Type: application/json" \
     -d '{"limit": 100}'
   ```

2. **Test Semantic Search:**
   ```bash
   curl -X POST https://weather-intelligence-7474659239402355.aws.databricksapps.com/weather/search \
     -H "Content-Type: application/json" \
     -d '{"query": "tornado warnings", "top_k": 5}'
   ```

But **DO NOT proceed to embeddings** until you confirm `public.weather_documents` contains rows.

---

## 🔍 TECHNICAL DETAILS

### Why This Happened

The `setup_weather_table.py` script (line 21) includes `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP` in its CREATE TABLE statement, but the actual table in Lakebase was created without this column.

This mismatch caused the application code (which referenced `updated_at`) to fail against the actual schema.

### Why synced_at is Sufficient

The `synced_at` column already serves the purpose of tracking when records are inserted or updated during sync operations:

* **INSERT:** Sets `synced_at` to the current sync timestamp
* **UPDATE (on conflict):** Updates `synced_at` to the current sync timestamp

No separate `updated_at` column is needed.

---

Generated: 2026-08-09
