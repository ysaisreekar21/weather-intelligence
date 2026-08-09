# Lakebase Connection Diagnostic Plan

## ✅ RESOURCE VERIFICATION COMPLETE

**App Resource Configuration:**
```json
"resources": [
  {
    "name": "postgres",
    "postgres": {
      "branch": "projects/weather-intelligence/branches/production",
      "database": "projects/weather-intelligence/branches/production/databases/databricks-postgres",
      "permission": "CAN_CONNECT_AND_CREATE"
    }
  }
]
```

✅ Resource key: `postgres` (correct)  
✅ Lakebase Autoscaling: Yes  
✅ Project: `weather-intelligence`  
✅ Branch: `production`  
✅ Database: `databricks-postgres`  
✅ Permission: `CAN_CONNECT_AND_CREATE`  

---

## 🔧 DIAGNOSTIC CODE ADDED

I've added two diagnostic features to `app.py`:

### 1. New Endpoint: `/diagnostics/env`
Reports which environment variables are **present** or **missing** (never prints actual values):
- `ENDPOINT_NAME`
- `PGHOST`
- `PGDATABASE`
- `PGUSER`
- `PGPORT`
- `PGSSLMODE`

### 2. Enhanced: `/api/weather/status`
Now includes:
- `lakebase_error`: The exact error message
- `lakebase_error_type`: The exception type (e.g., ValueError, psycopg2.OperationalError)

### 3. Enhanced: `/db-test`
Now includes:
- `error_type`: The exception class name
- Detailed error message

---

## 🚀 DEPLOYMENT & TESTING STEPS

### Step 1: Deploy the Updated App
```bash
databricks apps deploy weather-intelligence
```

Wait for deployment to complete (check status):
```bash
databricks apps get weather-intelligence
```

Look for:
```json
"app_status": {
  "state": "RUNNING"
}
```

### Step 2: Check Environment Variables

Get your app URL:
```bash
databricks apps get weather-intelligence | grep '"url"'
```

Then test the diagnostics endpoint:
```bash
curl https://weather-intelligence-7474659239402355.aws.databricksapps.com/diagnostics/env
```

**Expected Output (if working):**
```json
{
  "status": "success",
  "environment_variables": {
    "ENDPOINT_NAME": "present",
    "PGHOST": "present",
    "PGDATABASE": "present",
    "PGUSER": "present",
    "PGPORT": "present",
    "PGSSLMODE": "present"
  }
}
```

**Expected Output (if NOT working):**
```json
{
  "status": "success",
  "environment_variables": {
    "ENDPOINT_NAME": "present",
    "PGHOST": "missing",
    "PGDATABASE": "missing",
    "PGUSER": "missing",
    "PGPORT": "missing",
    "PGSSLMODE": "missing"
  }
}
```

### Step 3: Check Connection Error Details

```bash
curl https://weather-intelligence-7474659239402355.aws.databricksapps.com/api/weather/status
```

**Expected Output (if connection fails):**
```json
{
  "status": "success",
  "lakebase_connected": false,
  "lakebase_error": "Missing required Lakebase environment variables. Expected PGHOST, PGDATABASE, and PGUSER.",
  "lakebase_error_type": "ValueError",
  "weather_documents_count": 0,
  "weather_embeddings_count": 0,
  "unembedded_count": 0,
  "weather_available": false,
  "embeddings_available": false
}
```

OR:

```json
{
  "status": "success",
  "lakebase_connected": false,
  "lakebase_error": "could not connect to server: Connection refused",
  "lakebase_error_type": "OperationalError",
  ...
}
```

### Step 4: Test Direct Connection

```bash
curl https://weather-intelligence-7474659239402355.aws.databricksapps.com/db-test
```

This will show the full exception stack trace.

---

## 📋 DIAGNOSTIC CHECKLIST

After running the tests above, fill in these findings:

### Environment Variables Status

- [ ] `ENDPOINT_NAME`: ___________
- [ ] `PGHOST`: ___________
- [ ] `PGDATABASE`: ___________
- [ ] `PGUSER`: ___________
- [ ] `PGPORT`: ___________
- [ ] `PGSSLMODE`: ___________

### Connection Error Details

- [ ] **Error Type:** ___________
- [ ] **Error Message:** ___________

### Expected Outcomes

**Scenario A: Environment Variables Missing**
- `PGHOST`, `PGDATABASE`, `PGUSER` are "missing"
- Error: `ValueError: Missing required Lakebase environment variables`
- **Cause:** App resource binding not injecting Postgres connection parameters
- **Fix:** Need to verify app.yaml configuration or Databricks Apps documentation

**Scenario B: Environment Variables Present, Connection Fails**
- All env vars are "present"
- Error: `psycopg2.OperationalError` or similar
- **Cause:** Connection parameters are wrong, network issue, or OAuth token issue
- **Fix:** Need to verify connection parameters or OAuth credential generation

**Scenario C: OAuth Token Generation Fails**
- All env vars are "present"
- Error: Related to `WorkspaceClient` or `generate_database_credential`
- **Cause:** App permissions or SDK authentication issue
- **Fix:** Verify app service principal has correct permissions

**Scenario D: Everything Works**
- All env vars are "present"
- No errors in `/api/weather/status`
- `lakebase_connected: true`
- **Result:** Connection is working! Problem might be elsewhere.

---

## 🎯 NEXT STEPS

1. **Deploy the app** with diagnostic code
2. **Run all three diagnostic endpoints**
3. **Record the findings** in the checklist above
4. **Report back** with:
   - Which env vars are present/missing
   - The exact error type and message
   - Any other relevant output

**DO NOT:**
- Print actual credential values
- Change the resource configuration
- Modify app.yaml yet
- Run notebooks or install packages

Once we have the runtime evidence, we'll know exactly what's wrong and what minimal fix is needed.

---

## 📝 THEORY vs. REALITY

**According to Databricks Documentation:**
> When a Lakebase database is added as an App resource, Databricks automatically provides PGDATABASE, PGHOST, PGPORT, PGSSLMODE and PGUSER to the deployed app.

**Our Hypothesis:**
The environment variables SHOULD be automatically injected, but we need to verify this is actually happening in the deployed runtime.

**Possible Issues:**
1. Documentation is correct, but there's a version/feature mismatch
2. Resource binding syntax in app.yaml needs adjustment
3. Resource is configured but injection isn't working
4. Environment variables ARE injected but lakebase.py has a different issue
5. OAuth credential generation is failing

**The diagnostic will tell us which scenario is real.**

---

Generated: 2026-08-09
