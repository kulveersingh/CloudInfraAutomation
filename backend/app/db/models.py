import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonDocument = JSON().with_variant(JSONB(), "postgresql")


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class OrganizationSettings(Base):
    __tablename__ = "organization_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    default_cost_center: Mapped[str] = mapped_column(String(32))
    cost_center_pattern: Mapped[str] = mapped_column(String(128))
    attach_compute_to_vpc: Mapped[bool] = mapped_column(default=True, server_default=true())


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    cost_center: Mapped[str | None] = mapped_column(String(32))
    products: Mapped[list["Product"]] = relationship(order_by="Product.id", lazy="selectin")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id"))
    name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))
    cost_center: Mapped[str | None] = mapped_column(String(32))
    classification_ceiling: Mapped[str] = mapped_column(String(16))


class CostCenterOverride(Base):
    __tablename__ = "cost_center_overrides"

    project_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    cost_center: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    approved_by: Mapped[str] = mapped_column(String(128))


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    tier: Mapped[str] = mapped_column(String(16))
    position: Mapped[int]
    requires_approval: Mapped[bool]


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool]


class AccountBinding(Base):
    __tablename__ = "account_bindings"
    __table_args__ = (UniqueConstraint("environment_id", "portfolio_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"))
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id"))
    account_id: Mapped[str] = mapped_column(String(12), unique=True)


class Project(Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64))
    product_id: Mapped[str] = mapped_column(String(64))
    resilience_mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32))
    request: Mapped[dict] = mapped_column(JsonDocument)
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class ProjectChange(Base):
    """A "Change infrastructure" request: the new request, its pull request and where it is (§21.8)."""

    __tablename__ = "project_changes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_name: Mapped[str] = mapped_column(ForeignKey("projects.name"), index=True)
    revision: Mapped[int]
    request: Mapped[dict] = mapped_column(JsonDocument)
    summary: Mapped[dict] = mapped_column(JsonDocument)
    base_commit: Mapped[str] = mapped_column(String(64))
    branch: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(16))
    pull_request_number: Mapped[int | None]
    pull_request_url: Mapped[str | None] = mapped_column(String(512))
    merge_commit: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_name: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(128), unique=True)
    payload: Mapped[dict] = mapped_column(JsonDocument)
    kind: Mapped[str] = mapped_column(String(16), default="provision", server_default="provision")
    change_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project_changes.id"))
    state: Mapped[str] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class JobStep(Base):
    __tablename__ = "job_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"))
    sequence: Mapped[int]
    name: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128))
    details: Mapped[dict] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class Release(Base):
    __tablename__ = "releases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_name: Mapped[str] = mapped_column(String(64), index=True)
    environment_id: Mapped[str] = mapped_column(String(16))
    commit_sha: Mapped[str] = mapped_column(String(64))
    artifact_digest: Mapped[str] = mapped_column(String(128))
    changes: Mapped[list] = mapped_column(JsonDocument)
    evidence: Mapped[dict] = mapped_column(JsonDocument)
    risk: Mapped[str] = mapped_column(String(16))
    gate_findings: Mapped[list] = mapped_column(JsonDocument)
    state: Mapped[str] = mapped_column(String(32))
    requested_by: Mapped[str] = mapped_column(String(128))
    execution_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class ReleaseDecision(Base):
    __tablename__ = "release_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    release_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("releases.id"))
    actor: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class Network(Base):
    """An organization network a platform engineer registered for one account and region."""

    __tablename__ = "networks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    account_id: Mapped[str] = mapped_column(String(12), index=True)
    region: Mapped[str] = mapped_column(String(32))
    vpc_id: Mapped[str] = mapped_column(String(32))
    cidr: Mapped[str] = mapped_column(String(43))
    private_subnet_ids: Mapped[list] = mapped_column(JsonDocument)
    security_group_ids: Mapped[list] = mapped_column(JsonDocument)
    is_default: Mapped[bool] = mapped_column(default=False)


class LandingZoneDesignRecord(Base):
    """One version of the landing zone questionnaire answers and where it is in the approval workflow."""

    __tablename__ = "landing_zone_designs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(unique=True)
    answers: Mapped[dict] = mapped_column(JsonDocument)
    edits: Mapped[list] = mapped_column(JsonDocument, default=list)
    status: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[str] = mapped_column(String(128))
    submitted_by: Mapped[str | None] = mapped_column(String(128))
    decided_by: Mapped[str | None] = mapped_column(String(128))
    decision_comment: Mapped[str | None] = mapped_column(Text)
    repository: Mapped[str | None] = mapped_column(String(256))
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    accounts: Mapped[dict | None] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class Teardown(Base):
    """Removing an environment or decommissioning a project, backup-first, with what it needs for a restore (§21.9)."""

    __tablename__ = "teardowns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_name: Mapped[str] = mapped_column(ForeignKey("projects.name"), index=True)
    scope: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(32))
    requested_by: Mapped[str] = mapped_column(String(128))
    base_revision: Mapped[int]
    base_request: Mapped[dict] = mapped_column(JsonDocument)
    base_commit: Mapped[str | None] = mapped_column(String(64))
    backup_account_id: Mapped[str] = mapped_column(String(12))
    restore_state: Mapped[str | None] = mapped_column(String(16))
    restore_requested_by: Mapped[str | None] = mapped_column(String(128))
    restore_decided_by: Mapped[str | None] = mapped_column(String(128))
    restore_job_id: Mapped[uuid.UUID | None]
    restore_steps: Mapped[list] = mapped_column(JsonDocument, default=list)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class TeardownEnvironment(Base):
    """One environment of a teardown: its own approval, job and checkpoints."""

    __tablename__ = "teardown_environments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    teardown_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teardowns.id"), index=True)
    environment: Mapped[str] = mapped_column(String(16))
    position: Mapped[int]
    approver_role: Mapped[str] = mapped_column(String(32))
    account_id: Mapped[str] = mapped_column(String(12))
    regions: Mapped[list] = mapped_column(JsonDocument)
    state: Mapped[str] = mapped_column(String(32))
    decided_by: Mapped[str | None] = mapped_column(String(128))
    decision_comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None]
    revision: Mapped[int | None]
    error: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[uuid.UUID | None]
    completed_steps: Mapped[list] = mapped_column(JsonDocument, default=list)


class TeardownRecoveryPoint(Base):
    """A backup in the central locked vault, taken before the environment's data store was deleted."""

    __tablename__ = "teardown_recovery_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    teardown_environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teardown_environments.id"), index=True)
    service_id: Mapped[str] = mapped_column(String(64))
    logical_id: Mapped[str] = mapped_column(String(255))
    resource_type: Mapped[str] = mapped_column(String(128))
    physical_name: Mapped[str] = mapped_column(String(255))
    region: Mapped[str] = mapped_column(String(32))
    account_id: Mapped[str] = mapped_column(String(12))
    recovery_point_arn: Mapped[str] = mapped_column(String(512))
    vault: Mapped[str] = mapped_column(String(128))
    completed_at: Mapped[datetime]
    locked_until: Mapped[datetime]

