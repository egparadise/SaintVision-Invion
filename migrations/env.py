"""Alembic environment.

The database URL is read from ``INV_DATABASE_URL`` or ``INV_MIGRATION_DSN`` and
never from the ini file, so no connection string — and no credential — is committed.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CP_SRC = ROOT / "services" / "control-plane" / "src"

for p in (SRC, CP_SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from saintvision.db.base import Base
    from saintvision.db import models  # noqa: F401  (registers tables)
    target_metadata = Base.metadata
except ImportError:
    target_metadata = None

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    url = os.environ.get("INV_DATABASE_URL") or os.environ.get("INV_MIGRATION_DSN")
    if not url:
        raise RuntimeError("Neither INV_DATABASE_URL nor INV_MIGRATION_DSN is set")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            transactional_ddl=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
