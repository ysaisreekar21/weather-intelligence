# Fix Lakebase Permissions - Weather Intelligence App

## 🔒 ISSUE

**Error:** `permission denied for table weather_documents`

**Status:** Lakebase connection works, but the app's PostgreSQL role lacks INSERT/UPDATE permissions on the tables.

---

## 🔍 STEP 1: IDENTIFY THE APP'S POSTGRESQL ROLE

### Run in Lakebase SQL Editor

Go to: **Lakebase** → **weather-intelligence** → **production branch** → **SQL Editor**

Run this query to check what role the current admin user has:

```sql
SELECT current_user, session_user;
```

Then find the app's service principal role:

```sql
SELECT rolname 
FROM pg_roles 
WHERE rolname LIKE '%app%' 
   OR rolname LIKE '%weather%'
   OR rolname LIKE '%1526wj%'
ORDER BY rolname;
```

**Expected role name patterns:**
- `app_1526wj_weather_intelligence`
- `sp_74896113208105` (service principal ID)
- Or another Databricks-generated format

**Note the exact role name** - you'll need it for Step 3.

---

## 🔍 STEP 2: CHECK CURRENT TABLE OWNERSHIP & PRIVILEGES

### Check Table Ownership

```sql
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE schemaname = 'public' 
  AND tablename IN ('weather_documents', 'weather_embeddings')
ORDER BY tablename;
```

**Expected output:**
```
schemaname | tablename           | tableowner
public     | weather_documents   | admin (or your user)
public     | weather_embeddings  | admin (or your user)
```

### Check Current Privileges

```sql
SELECT 
    table_name,
    grantee,
    privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public'
  AND table_name IN ('weather_documents', 'weather_embeddings')
ORDER BY table_name, grantee, privilege_type;
```

This will show you who currently has permissions on these tables.

---

## ✅ STEP 3: GRANT PERMISSIONS TO THE APP ROLE

**IMPORTANT:** Replace `<APP_ROLE_NAME>` below with the exact role name you found in Step 1.

### Option A: If you found a specific app role name

Run these commands in the **Lakebase SQL Editor**:

```sql
-- Grant permissions on weather_documents
GRANT SELECT, INSERT, UPDATE ON public.weather_documents TO <APP_ROLE_NAME>;

-- Grant permissions on weather_embeddings
GRANT SELECT, INSERT, UPDATE ON public.weather_embeddings TO <APP_ROLE_NAME>;

-- Grant usage on the public schema
GRANT USAGE ON SCHEMA public TO <APP_ROLE_NAME>;

-- Verify the grants
SELECT 
    table_name,
    grantee,
    privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public'
  AND table_name IN ('weather_documents', 'weather_embeddings')
  AND grantee = '<APP_ROLE_NAME>'
ORDER BY table_name, privilege_type;
```

### Option B: If the app uses a service principal role

The Databricks App service principal is:
- **Name:** `app-1526wj weather-intelligence`
- **ID:** `74896113208105`

The PostgreSQL role might be formatted as:
```sql
-- Try these if the app role wasn't obvious in Step 1:
GRANT SELECT, INSERT, UPDATE ON public.weather_documents TO "app-1526wj weather-intelligence";
GRANT SELECT, INSERT, UPDATE ON public.weather_embeddings TO "app-1526wj weather-intelligence";
GRANT USAGE ON SCHEMA public TO "app-1526wj weather-intelligence";
```

Or:
```sql
GRANT SELECT, INSERT, UPDATE ON public.weather_documents TO sp_74896113208105;
GRANT SELECT, INSERT, UPDATE ON public.weather_embeddings TO sp_74896113208105;
GRANT USAGE ON SCHEMA public TO sp_74896113208105;
```

### Option C: Grant to all app roles (broad but safe)

If the specific role is hard to identify:

```sql
-- Find all roles that look like app roles
DO $
DECLARE
    role_name TEXT;
BEGIN
    FOR role_name IN 
        SELECT rolname 
        FROM pg_roles 
        WHERE rolname LIKE 'app%' OR rolname LIKE 'sp_%'
    LOOP
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON public.weather_documents TO %I', role_name);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON public.weather_embeddings TO %I', role_name);
        EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', role_name);
        RAISE NOTICE 'Granted permissions to role: %', role_name;
    END LOOP;
END $;
```

### Option D: Make tables accessible to PUBLIC (simplest, less secure)

**Only if other options don't work:**

```sql
GRANT SELECT, INSERT, UPDATE ON public.weather_documents TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON public.weather_embeddings TO PUBLIC;
GRANT USAGE ON SCHEMA public TO PUBLIC;
```

---

## 🔍 STEP 4: VERIFY THE FIX

### Check that permissions were granted:

```sql
SELECT 
    table_name,
    grantee,
    privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public'
  AND table_name IN ('weather_documents', 'weather_embeddings')
ORDER BY table_name, grantee, privilege_type;
```

You should now see your app role with SELECT, INSERT, and UPDATE privileges on both tables.

---

## 🚀 STEP 5: TEST THE APP

### No app restart needed - permissions are effective immediately

### Test 1: Verify Lakebase Connection

```bash
curl https://weather-intelligence-7474659239402355.aws.databricksapps.com/api/weather/status
```

**Expected:**
```json
{
  "lakebase_connected": true,
  ...
}
```

### Test 2: Sync Weather Data

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

**NOT:**
```json
{
  "status": "error",
  "error": "permission denied for table weather_documents"
}
```

### Test 3: Verify Data Was Inserted

In Lakebase SQL Editor:

```sql
SELECT COUNT(*) as total_docs
FROM public.weather_documents;

SELECT 
    location,
    COUNT(*) as count
FROM public.weather_documents
GROUP BY location
ORDER BY count DESC;
```

You should see rows!

---

## 🔍 ALTERNATIVE: RUN DIAGNOSTIC FROM APP CONTEXT

If you want to see exactly what role the **app** uses when connecting, temporarily add this diagnostic endpoint to app.py:

```python
@app.route("/diagnostics/db-role")
def diagnostics_db_role():
    """Check what PostgreSQL role the app is using."""
    try:
        result = lakebase.run_query(
            "SELECT current_user, session_user, current_database()"
        )
        return jsonify({
            "status": "success",
            "current_user": result[0]["current_user"],
            "session_user": result[0]["session_user"],
            "database": result[0]["current_database"]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
```

Then:
1. Deploy the app
2. Call: `curl https://<app-url>/diagnostics/db-role`
3. Use the returned `current_user` as the role name in Step 3

---

## ✅ SUMMARY

**What you need to do:**

1. **Open Lakebase SQL Editor:**
   - Navigate to: Lakebase → weather-intelligence → production → SQL Editor

2. **Find the app's role name:**
   - Run: `SELECT rolname FROM pg_roles WHERE rolname LIKE '%app%' ORDER BY rolname;`

3. **Grant permissions:**
   - Run: `GRANT SELECT, INSERT, UPDATE ON public.weather_documents TO <APP_ROLE_NAME>;`
   - Run: `GRANT SELECT, INSERT, UPDATE ON public.weather_embeddings TO <APP_ROLE_NAME>;`
   - Run: `GRANT USAGE ON SCHEMA public TO <APP_ROLE_NAME>;`

4. **Test immediately** (no restart needed):
   - `curl -X POST https://<app-url>/api/weather/sync ...`

5. **Verify data:**
   - `SELECT COUNT(*) FROM public.weather_documents;`

**Common role name patterns to try:**
- `app_1526wj_weather_intelligence`
- `"app-1526wj weather-intelligence"` (with quotes)
- `sp_74896113208105`
- Or use Option C (grant to all app roles)
- Or use Option D (grant to PUBLIC) as last resort

---

## 🎯 EXPECTED OUTCOME

✅ Lakebase connection: Working  
✅ POST /api/weather/sync: Returns 200 with `documents_synced: 100`  
✅ weather_documents table: Contains rows  
✅ No more "permission denied" errors  

---

Generated: 2026-08-09
