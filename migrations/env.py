"""Migration URL is obtained from the environment, never committed."""

import os
from alembic import context
from sqlalchemy import create_engine

url = os.environ["INV_MIGRATION_DSN"]
# Caller supplies postgresql+psycopg:// for SQLAlchemy. Do not render the URL.
engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection, transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()
