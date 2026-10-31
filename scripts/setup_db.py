"""
Database setup script for Campus OS.

Run this ONCE to create the campus_os user and databases.
You need to supply the postgres superuser password.

Usage:
    python scripts/setup_db.py --pg-password YOUR_POSTGRES_PASSWORD

This script:
    1. Creates the 'campus_os' role/user with password 'campus_os'
    2. Creates the 'campus_os' database owned by campus_os
    3. Creates the 'campus_os_test' database for running tests
"""
import argparse
import sys

import psycopg2


def setup(pg_password: str) -> None:
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password=pg_password,
            dbname="postgres",
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Create user
        cur.execute("SELECT 1 FROM pg_user WHERE usename = 'campus_os'")
        if not cur.fetchone():
            cur.execute("CREATE USER campus_os WITH PASSWORD 'campus_os'")
            print("Created user: campus_os")
        else:
            print("User campus_os already exists — skipping")

        # Create main DB
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'campus_os'")
        if not cur.fetchone():
            cur.execute("CREATE DATABASE campus_os OWNER campus_os")
            print("Created database: campus_os")
        else:
            print("Database campus_os already exists — skipping")

        # Create test DB
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'campus_os_test'")
        if not cur.fetchone():
            cur.execute("CREATE DATABASE campus_os_test OWNER campus_os")
            print("Created database: campus_os_test")
        else:
            print("Database campus_os_test already exists — skipping")

        conn.close()
        print("\n[OK] Database setup complete.")
        print("  Next steps:")
        print("    cd backend")
        print("    alembic upgrade head")
        print("    python -m app.db.seed")
        print("    uvicorn app.main:app --reload")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus OS database setup")
    parser.add_argument(
        "--pg-password",
        required=True,
        help="PostgreSQL superuser (postgres) password",
    )
    args = parser.parse_args()
    setup(args.pg_password)

