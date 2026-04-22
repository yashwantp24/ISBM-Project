# connection.py
"""
Single source of truth for PostgreSQL connections.

All modules should import `get_conn` from here. Credentials come from
environment variables; the fallbacks match the previous hardcoded values
so existing local setups keep working:

    PGHOST      default "localhost"
    PGPORT      default 5432
    PGDATABASE  default "postgres"
    PGUSER      default "postgres"
    PGPASSWORD  default "admin"
"""

from __future__ import annotations

import os
import psycopg2


def get_conn():
    """Return a new psycopg2 connection using env-driven credentials."""
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        dbname=os.environ.get("PGDATABASE", "postgres"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", "admin"),
        port=int(os.environ.get("PGPORT", "5432")),
    )
