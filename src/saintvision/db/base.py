"""Declarative base and the column types shared by every table."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from sqlalchemy import CHAR, BigInteger, DateTime, Integer, MetaData, String, text
from sqlalchemy.dialects.postgresql import JSONB, NUMERIC, UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column

# Explicit naming so Alembic autogenerate produces stable constraint names and a
# migration diff is a real diff rather than a rename storm.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


#: prefix + ULID is 4 + 26 characters; the column is fixed width so a malformed
#: ID cannot be stored even if application validation is bypassed.
InvId = Annotated[str, mapped_column(CHAR(30))]
TenantId = Annotated[uuid.UUID, mapped_column(UUID(as_uuid=True))]
Sha256 = Annotated[str, mapped_column(CHAR(64))]
TraceId = Annotated[str, mapped_column(CHAR(32))]
Utc = Annotated[dt.datetime, mapped_column(DateTime(timezone=True))]
Quantity = Annotated[float, mapped_column(NUMERIC(20, 4))]

__all__ = [
    "Base",
    "BigInteger",
    "InvId",
    "Integer",
    "JSONB",
    "NAMING_CONVENTION",
    "Quantity",
    "Sha256",
    "String",
    "TenantId",
    "TraceId",
    "Utc",
    "text",
]
