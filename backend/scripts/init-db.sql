-- Create app_user role (used by FastAPI, RLS enforced)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN PASSWORD 'app_user';
    END IF;
END
$$;

-- Grant connect and schema usage
GRANT CONNECT ON DATABASE saas_db TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

-- app_user gets DML on all current and future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;
