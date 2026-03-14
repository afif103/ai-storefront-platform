-- ==========================================================================
-- init-db.sql — Run as RDS master/admin user (bootstrap only).
-- Creates app_migrator (DDL + DML for schema migrations) and
-- app_user (DML only for runtime, RLS enforced).
--
-- WARNING: Passwords below are placeholders (CHANGE_ME_*).
-- The bootstrap ECS task MUST substitute real passwords before execution.
-- Do NOT run this file in production with literal CHANGE_ME_* values.
-- ==========================================================================

-- ---------------------------------------------------------------------------
-- 1. app_migrator — used by Alembic migration ECS task
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_migrator') THEN
        CREATE ROLE app_migrator LOGIN PASSWORD 'CHANGE_ME_MIGRATOR';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE saas_db TO app_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO app_migrator;

-- app_migrator gets full DDL + DML on all current and future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO app_migrator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO app_migrator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON FUNCTIONS TO app_migrator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TYPES TO app_migrator;

-- ---------------------------------------------------------------------------
-- 2. app_user — used by FastAPI + Celery at runtime (RLS enforced)
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN PASSWORD 'CHANGE_ME_APP';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE saas_db TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

-- app_user gets DML only on all current and future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;
