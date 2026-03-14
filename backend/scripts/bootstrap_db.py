"""Bootstrap database roles for multi-tenant SaaS platform.

Run as a one-off ECS task via the saas-bootstrap task definition.
Connects as the RDS master/admin user and creates app_migrator (DDL + DML)
and app_user (DML only, RLS-enforced).

This is bootstrap-only setup for task 8.5. No runtime services are consuming
/prod/database-url at this point, so it is safe to create/update secrets
before the roles exist in the database.

Environment variables (injected by ECS task-definition secrets):
  MASTER_PASSWORD         Raw master/admin password (/prod/rds-master-password)
  MIGRATOR_DATABASE_URL   Full connection string (/prod/database-url-migrator)
  APP_USER_DATABASE_URL   Full connection string (/prod/database-url)

Environment variables (plain, from task definition):
  RDS_MASTER_USER         Master username (default: saas_admin)
  RDS_DB_NAME             Database name (default: saas_db)
"""

import os
import sys
from urllib.parse import urlparse

import psycopg2
from psycopg2 import sql


def parse_password(database_url: str) -> str:
    """Extract password from a database connection URL."""
    parsed = urlparse(database_url)
    if not parsed.password:
        raise ValueError(f"No password in URL (scheme={parsed.scheme}, user={parsed.username})")
    return parsed.password


def parse_host_port(database_url: str) -> tuple[str, int]:
    """Extract host and port from a database connection URL."""
    parsed = urlparse(database_url)
    host = parsed.hostname
    port = parsed.port or 5432
    if not host:
        raise ValueError(f"No host in URL (scheme={parsed.scheme})")
    return host, port


def main() -> None:
    master_password = os.environ["MASTER_PASSWORD"]
    migrator_url = os.environ["MIGRATOR_DATABASE_URL"]
    app_user_url = os.environ["APP_USER_DATABASE_URL"]
    master_user = os.environ.get("RDS_MASTER_USER", "saas_admin")
    db_name = os.environ.get("RDS_DB_NAME", "saas_db")

    migrator_password = parse_password(migrator_url)
    app_user_password = parse_password(app_user_url)
    host, port = parse_host_port(migrator_url)

    print(f"Connecting to {host}:{port}/{db_name} as {master_user}")

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=db_name,
        user=master_user,
        password=master_password,
        sslmode="require",
    )
    conn.autocommit = True

    db_id = sql.Identifier(db_name)

    with conn.cursor() as cur:
        # -- app_migrator (DDL + DML, used by alembic migrations) ----------
        print("Creating/updating app_migrator role...")
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'app_migrator'")
        if cur.fetchone() is None:
            cur.execute(
                "CREATE ROLE app_migrator LOGIN PASSWORD %s",
                (migrator_password,),
            )
            print("  Created role")
        else:
            cur.execute(
                "ALTER ROLE app_migrator WITH PASSWORD %s",
                (migrator_password,),
            )
            print("  Updated password")

        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO app_migrator").format(db_id))
        cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO app_migrator")
        cur.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT ALL PRIVILEGES ON TABLES TO app_migrator"
        )
        cur.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT ALL PRIVILEGES ON SEQUENCES TO app_migrator"
        )
        cur.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT ALL PRIVILEGES ON FUNCTIONS TO app_migrator"
        )
        cur.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT ALL PRIVILEGES ON TYPES TO app_migrator"
        )
        print("  Grants applied")

        # -- app_user (DML only, RLS-enforced, used at runtime) ------------
        print("Creating/updating app_user role...")
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'app_user'")
        if cur.fetchone() is None:
            cur.execute(
                "CREATE ROLE app_user LOGIN PASSWORD %s",
                (app_user_password,),
            )
            print("  Created role")
        else:
            cur.execute(
                "ALTER ROLE app_user WITH PASSWORD %s",
                (app_user_password,),
            )
            print("  Updated password")

        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO app_user").format(db_id))
        cur.execute("GRANT USAGE ON SCHEMA public TO app_user")
        cur.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user"
        )
        cur.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT USAGE, SELECT ON SEQUENCES TO app_user"
        )

        # Tables/sequences are created by app_migrator (via alembic), not
        # by the admin user. ALTER DEFAULT PRIVILEGES without FOR ROLE only
        # covers objects the current user creates. This FOR ROLE clause
        # ensures app_user can access objects created by app_migrator.
        cur.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user"
        )
        cur.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public "
            "GRANT USAGE, SELECT ON SEQUENCES TO app_user"
        )

        # Grant on existing objects so reruns are safe if migrations
        # have already created tables before bootstrap runs.
        cur.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES " "IN SCHEMA public TO app_user"
        )
        cur.execute("GRANT USAGE, SELECT ON ALL SEQUENCES " "IN SCHEMA public TO app_user")
        print("  Grants applied (including FOR ROLE app_migrator defaults)")

    conn.close()
    print("Bootstrap complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
