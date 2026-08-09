-- ============================================================================
-- LAKEBASE PERMISSIONS FIX FOR WEATHER INTELLIGENCE APP
-- Run these commands in: Lakebase → weather-intelligence → production → SQL Editor
-- ============================================================================

-- STEP 1: Find the app's PostgreSQL role
-- ============================================================================
SELECT rolname 
FROM pg_roles 
WHERE rolname LIKE '%app%' 
   OR rolname LIKE '%weather%'
   OR rolname LIKE '%1526wj%'
ORDER BY rolname;

-- Note the role name, then replace <APP_ROLE_NAME> below with it

-- STEP 2: Check current table ownership
-- ============================================================================
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE schemaname = 'public' 
  AND tablename IN ('weather_documents', 'weather_embeddings')
ORDER BY tablename;

-- STEP 3: Grant permissions to the app role
-- ============================================================================
-- Replace <APP_ROLE_NAME> with the actual role from Step 1

GRANT SELECT, INSERT, UPDATE ON public.weather_documents TO <APP_ROLE_NAME>;
GRANT SELECT, INSERT, UPDATE ON public.weather_embeddings TO <APP_ROLE_NAME>;
GRANT USAGE ON SCHEMA public TO <APP_ROLE_NAME>;

-- ALTERNATIVE: If role name has special characters, use quotes:
-- GRANT SELECT, INSERT, UPDATE ON public.weather_documents TO "app-1526wj weather-intelligence";
-- GRANT SELECT, INSERT, UPDATE ON public.weather_embeddings TO "app-1526wj weather-intelligence";
-- GRANT USAGE ON SCHEMA public TO "app-1526wj weather-intelligence";

-- ALTERNATIVE: If you found sp_* role:
-- GRANT SELECT, INSERT, UPDATE ON public.weather_documents TO sp_74896113208105;
-- GRANT SELECT, INSERT, UPDATE ON public.weather_embeddings TO sp_74896113208105;
-- GRANT USAGE ON SCHEMA public TO sp_74896113208105;

-- LAST RESORT: Grant to PUBLIC (less secure but works)
-- GRANT SELECT, INSERT, UPDATE ON public.weather_documents TO PUBLIC;
-- GRANT SELECT, INSERT, UPDATE ON public.weather_embeddings TO PUBLIC;
-- GRANT USAGE ON SCHEMA public TO PUBLIC;

-- STEP 4: Verify the grants
-- ============================================================================
SELECT 
    table_name,
    grantee,
    privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public'
  AND table_name IN ('weather_documents', 'weather_embeddings')
ORDER BY table_name, grantee, privilege_type;

-- You should see your app role with SELECT, INSERT, UPDATE on both tables

-- STEP 5: Test data (after running curl command)
-- ============================================================================
SELECT COUNT(*) as total_docs
FROM public.weather_documents;

SELECT 
    location,
    COUNT(*) as count
FROM public.weather_documents
GROUP BY location
ORDER BY count DESC
LIMIT 10;
