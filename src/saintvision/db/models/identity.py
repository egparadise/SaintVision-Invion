"""Tenant, user, role and project tables (S02-DB).

Cross-tenant FK linkage is blocked structurally: every child carries
``tenant_id`` and points at its parent through a composite FK that includes it,
so a row can only reference a parent inside its own tenant (ADR-008).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, TenantId, Utc

USER_STATUSES = ("active", "suspended", "retired")
PROJECT_STATUSES = ("active", "archived")


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    version: Mapped[int] = mapped_column(default=1)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # The IdP subject is the identity key. It is unique per tenant, not
        # globally: two tenants may federate the same directory.
        UniqueConstraint("tenant_id", "external_subject"),
        UniqueConstraint("tenant_id", "user_id", name="uq_users_tenant_id_user_id"),
        CheckConstraint(
            "status IN ('active','suspended','retired')", name="status_allowed"
        ),
    )

    user_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column(ForeignKey("tenants.tenant_id"))
    #: OIDC ``sub``. The issuer is an S01 decision; the column stores whatever
    #: subject the configured issuer asserts and does not parse it.
    external_subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    version: Mapped[int] = mapped_column(default=1)


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        UniqueConstraint("tenant_id", "role_id", name="uq_roles_tenant_id_role_id"),
    )

    role_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column(ForeignKey("tenants.tenant_id"))
    code: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.user_id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "role_id"], ["roles.tenant_id", "roles.role_id"]
        ),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    user_id: Mapped[InvId] = mapped_column(primary_key=True)
    role_id: Mapped[InvId] = mapped_column(primary_key=True)
    granted_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        UniqueConstraint("tenant_id", "project_id", name="uq_projects_tenant_id_project_id"),
        CheckConstraint("status IN ('active','archived')", name="status_allowed"),
    )

    project_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column(ForeignKey("tenants.tenant_id"))
    code: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    version: Mapped[int] = mapped_column(default=1)


class ProjectMember(Base):
    """Project membership is checked at the service boundary as well as here.

    RLS gives tenant isolation; it does not give project isolation, because a
    user is a member of some projects and not others inside one tenant
    (PLAN-DB-001).
    """

    __tablename__ = "project_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.user_id"]
        ),
        Index("ix_project_members_tenant_id_user_id", "tenant_id", "user_id"),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    project_id: Mapped[InvId] = mapped_column(primary_key=True)
    user_id: Mapped[InvId] = mapped_column(primary_key=True)
    role_code: Mapped[str] = mapped_column(String(64))
    granted_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
