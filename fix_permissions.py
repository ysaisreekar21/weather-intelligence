#!/usr/bin/env python3
"""Fix Lakebase permissions for the weather-intelligence app.

This script grants the app's Service Principal the required permissions
on existing tables that were created during local development.
"""
import os
import sys
from databricks.sdk import WorkspaceClient
import psycopg2

# App Service Principal client ID
APP_SP_CLIENT_ID = "18a23a65-c311-49b8-90c5-e9ecfd1d8d4b"

def main():
    print("=" * 70)
    print("Lakebase Permission Fix for weather-intelligence App")
    print("=" * 70)
    
    # Initialize Databricks client
    w = WorkspaceClient()
    
    # Get endpoint information
    endpoint_name = "projects/weather-intelligence/branches/production/endpoints/primary"
    print(f"\n1. Getting endpoint: {endpoint_name}")
    
    try:
        endpoint = w.postgres.get_endpoint(name=endpoint_name)
        host = endpoint.status.hosts.host
        print(f"   ✓ Host: {host}")
    except Exception as e:
        print(f"   ✗ Error getting endpoint: {e}")
        sys.exit(1)
    
    # Generate OAuth token
    print("\n2. Generating OAuth token...")
    try:
        token = w.postgres.generate_database_credential(endpoint=endpoint_name).token
        username = w.current_user.me().user_name
        print(f"   ✓ Token generated for user: {username}")
    except Exception as e:
        print(f"   ✗ Error generating token: {e}")
        sys.exit(1)
    
    # Connect to database
    print("\n3. Connecting to Lakebase database...")
    try:
        conn = psycopg2.connect(
            host=host,
            port=5432,
            dbname="databricks-postgres",
            user=username,
            password=token,
            sslmode="require"
        )
        conn.autocommit = True
        cursor = conn.cursor()
        print("   ✓ Connected")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        sys.exit(1)
    
    # Check current ownership
    print("\n4. Checking current table ownership...")
    try:
        cursor.execute("""
            SELECT tableowner 
            FROM pg_tables 
            WHERE schemaname = 'public' 
              AND tablename = 'weather_embeddings'
        """)
        result = cursor.fetchone()
        if result:
            owner = result[0]
            print(f"   ✓ weather_embeddings owner: {owner}")
        else:
            print("   ✗ weather_embeddings table not found!")
            conn.close()
            sys.exit(1)
    except Exception as e:
        print(f"   ✗ Error checking ownership: {e}")
        conn.close()
        sys.exit(1)
    
    # Check if Service Principal role exists
    print(f"\n5. Checking if Service Principal role exists...")
    sp_role = APP_SP_CLIENT_ID
    try:
        cursor.execute("""
            SELECT 1 FROM pg_roles WHERE rolname = %s
        """, (sp_role,))
        exists = cursor.fetchone()
        if exists:
            print(f"   ✓ Role '{sp_role}' exists")
        else:
            print(f"   ! Role '{sp_role}' not found")
            print(f"     The Service Principal should auto-create a role when it first connects.")
            print(f"     The app may be using a different role format.")
            print(f"\n   Checking for alternative role formats...")
            
            # Try sp_<service_principal_id> format
            alt_role = "sp_74896113208105"
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (alt_role,))
            if cursor.fetchone():
                sp_role = alt_role
                print(f"   ✓ Found role: {sp_role}")
            else:
                print(f"   ! Role not found in any format")
                print(f"\n   Listing all non-system roles:")
                cursor.execute("""
                    SELECT rolname 
                    FROM pg_roles 
                    WHERE rolname NOT LIKE 'pg_%' 
                      AND rolname NOT IN ('postgres', 'databricks_superuser', 'authenticator')
                    ORDER BY rolname
                """)
                roles = cursor.fetchall()
                for role in roles:
                    print(f"     - {role[0]}")
                
                print(f"\n   ! Cannot proceed without knowing the correct role name.")
                conn.close()
                sys.exit(1)
    except Exception as e:
        print(f"   ✗ Error checking role: {e}")
        conn.close()
        sys.exit(1)
    
    # Grant permissions
    print(f"\n6. Granting permissions to Service Principal role '{sp_role}'...")
    
    grant_statements = [
        f'GRANT USAGE ON SCHEMA public TO "{sp_role}"',
        f'GRANT SELECT, INSERT, UPDATE ON TABLE public.weather_documents TO "{sp_role}"',
        f'GRANT SELECT, INSERT, UPDATE ON TABLE public.weather_embeddings TO "{sp_role}"',
    ]
    
    for sql in grant_statements:
        try:
            print(f"   Executing: {sql[:60]}...")
            cursor.execute(sql)
            print(f"   ✓ Success")
        except Exception as e:
            print(f"   ✗ Error: {e}")
            conn.close()
            sys.exit(1)
    
    # Verify permissions
    print("\n7. Verifying permissions...")
    try:
        cursor.execute("""
            SELECT 
                grantee,
                string_agg(privilege_type, ', ' ORDER BY privilege_type) as privileges
            FROM information_schema.table_privileges
            WHERE table_schema = 'public'
              AND table_name = 'weather_embeddings'
              AND grantee = %s
            GROUP BY grantee
        """, (sp_role,))
        result = cursor.fetchone()
        if result:
            print(f"   ✓ Role '{result[0]}' has: {result[1]}")
        else:
            print(f"   ! No permissions found for '{sp_role}' (this may be okay if grants just completed)")
    except Exception as e:
        print(f"   ! Could not verify: {e}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ PERMISSIONS GRANTED SUCCESSFULLY")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Test the embedding endpoint:")
    print("   curl -X POST https://weather-intelligence-7474659239402355.aws.databricksapps.com/weather/embed \\")
    print('        -H "Content-Type: application/json" \\')
    print('        -d \'{"batch_size": 50}\'')
    print("\n2. Expected response:")
    print('   {"status": "success", "documents_processed": N, "embeddings_inserted": M}')
    print()

if __name__ == "__main__":
    main()
