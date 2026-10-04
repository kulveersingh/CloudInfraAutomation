import uuid

from sqlalchemy.orm import Session

from app.adapters.ports import GitHubPort
from app.db import models
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.cloudformation.bundle import LandingZoneBundle
from app.landing_zone.cloudformation.guardrails import GuardrailPlan, ScpQuotaRule
from app.landing_zone.design import AccountPlan, LandingZoneDesign, OrgCatalog, OuNode
from app.landing_zone.designer import LandingZoneDesigner
from app.landing_zone.diagram import OuDiagramRenderer
from app.landing_zone.edits import EditPermissions, TreeEdit, TreeEditor
from app.landing_zone.executor import LandingZoneExecutor, LandingZoneOutputs
from app.landing_zone.repository import LandingZoneRepository
from app.landing_zone.request import LandingZoneRequest
from app.landing_zone.states import DesignStatus
from app.landing_zone.validation import DesignValidator
from app.networks.models import NetworkInput
from app.networks.service import NetworkService
from app.registry.service import RegistryService, require
from app.releases.policy import Actor, Role

REPOSITORY_NAME = "landing-zone-infra"
REPOSITORY_MARKER = "landing-zone"


class LandingZonePolicy:
    """Only platform admins design the landing zone; a different admin approves or rejects."""

    def require_admin(self, actor: Actor) -> None:
        if not actor.has_role(Role.PLATFORM_ADMIN):
            raise ForbiddenError("Only platform admins can manage the landing zone.")

    def require_second_admin(self, actor: Actor, record: models.LandingZoneDesignRecord) -> None:
        self.require_admin(actor)
        if actor.name == record.submitted_by:
            raise ForbiddenError("You submitted this design, so a different platform admin must decide on it.")


class LandingZoneService:
    """The landing zone workflow: propose → draft → submit → approve (commit + apply + register networks) or reject."""

    def __init__(self, repository: LandingZoneRepository, registry: RegistryService, networks: NetworkService,
                 github: GitHubPort, executor: LandingZoneExecutor, owner: str):
        self._repository = repository
        self._registry = registry
        self._networks = networks
        self._github = github
        self._executor = executor
        self._owner = owner
        self._policy = LandingZonePolicy()
        self._designer = LandingZoneDesigner.default()

    @classmethod
    def for_session(cls, session: Session, github: GitHubPort, executor: LandingZoneExecutor,
                    owner: str) -> "LandingZoneService":
        return cls(LandingZoneRepository(session), RegistryService.for_session(session),
                   NetworkService.for_session(session), github, executor, owner)

    def propose(self, request: LandingZoneRequest, actor: Actor) -> dict:
        self._policy.require_admin(actor)
        design = self._design(request.answers, request.edits)
        return {**self._explain(design), "files": LandingZoneBundle.default().render(design, self._catalog())}

    def create(self, request: LandingZoneRequest, actor: Actor) -> dict:
        self._policy.require_admin(actor)
        record = models.LandingZoneDesignRecord(version=self._repository.next_version(),
                                                answers=request.answers.model_dump(mode="json"),
                                                edits=TreeEditor.dump(request.edits),
                                                status=DesignStatus.DRAFT, created_by=actor.name)
        self._repository.add(record)
        self._repository.commit()
        return self._describe(record)

    def designs(self, actor: Actor) -> list[dict]:
        self._policy.require_admin(actor)
        return [self._describe(record) for record in self._repository.all()]

    def get(self, design_id: uuid.UUID, actor: Actor) -> dict:
        self._policy.require_admin(actor)
        record = self._record(design_id)
        return {**self._describe(record), **self._explain(self._design_of(record))}

    def diagram(self, design_id: uuid.UUID, actor: Actor) -> str:
        self._policy.require_admin(actor)
        return OuDiagramRenderer().svg(self._design_of(self._record(design_id)))

    def submit(self, design_id: uuid.UUID, actor: Actor) -> dict:
        self._policy.require_admin(actor)
        record = self._in_status(design_id, DesignStatus.DRAFT)
        problems = self._problems(self._design_of(record))
        if problems:
            raise ValidationFailedError(" ".join(problems))
        record.status, record.submitted_by = DesignStatus.PENDING_APPROVAL, actor.name
        self._repository.commit()
        return self._describe(record)

    def approve(self, design_id: uuid.UUID, actor: Actor, comment: str) -> dict:
        record = self._in_status(design_id, DesignStatus.PENDING_APPROVAL)
        self._policy.require_second_admin(actor, record)
        design = self._design_of(record)
        record.commit_sha = self._commit(design, record.version, actor)
        outputs = self._executor.apply(design)
        self._register_networks(design, outputs)
        record.status, record.decided_by, record.decision_comment = DesignStatus.APPLIED, actor.name, comment
        record.repository, record.accounts = f"{self._owner}/{REPOSITORY_NAME}", outputs.accounts
        self._repository.commit()
        return self._describe(record)

    def reject(self, design_id: uuid.UUID, actor: Actor, comment: str) -> dict:
        record = self._in_status(design_id, DesignStatus.PENDING_APPROVAL)
        self._policy.require_second_admin(actor, record)
        record.status, record.decided_by, record.decision_comment = DesignStatus.REJECTED, actor.name, comment
        self._repository.commit()
        return self._describe(record)

    # ---- helpers ----

    def _catalog(self) -> OrgCatalog:
        portfolios = self._registry.org_registry()
        return OrgCatalog(portfolios=[portfolio["id"] for portfolio in portfolios],
                          products=[product["id"] for portfolio in portfolios for product in portfolio["products"]])

    def _design(self, answers: LandingZoneAnswers, edits: list[TreeEdit]) -> LandingZoneDesign:
        design = self._designer.design(answers, self._catalog())
        design.edit_problems = TreeEditor().apply(design, edits)
        return design

    def _design_of(self, record: models.LandingZoneDesignRecord) -> LandingZoneDesign:
        return self._design(LandingZoneAnswers.model_validate(record.answers), TreeEditor.parse(record.edits))

    def _problems(self, design: LandingZoneDesign) -> list[str]:
        return [*design.edit_problems, *DesignValidator.default().problems(design),
                *ScpQuotaRule().problems(GuardrailPlan.for_design(design))]

    def _explain(self, design: LandingZoneDesign) -> dict:
        renderer = OuDiagramRenderer()
        return {"ous": [_ou_json(ou) for ou in design.root_ous], "problems": self._problems(design),
                "diagram": {"svg": renderer.svg(design), "mermaid": renderer.mermaid(design)}}

    def _record(self, design_id: uuid.UUID) -> models.LandingZoneDesignRecord:
        return require(self._repository.get(design_id), NotFoundError(f"Unknown landing zone design '{design_id}'."))

    def _in_status(self, design_id: uuid.UUID, status: str) -> models.LandingZoneDesignRecord:
        record = self._record(design_id)
        if record.status != status:
            raise ConflictError(f"Design v{record.version} is {record.status}, not {status}.")
        return record

    def _commit(self, design: LandingZoneDesign, version: int, actor: Actor) -> str:
        self._github.create_repository(self._owner, REPOSITORY_NAME, marker=REPOSITORY_MARKER)
        files = LandingZoneBundle.default().render(design, self._catalog())
        return self._github.commit_files(self._owner, REPOSITORY_NAME, files,
                                         f"Landing zone design v{version} approved by {actor.name}")

    def _register_networks(self, design: LandingZoneDesign, outputs: LandingZoneOutputs) -> None:
        organization = design.answers.organization_name
        for network in outputs.networks:
            for account_name in network.account_names:
                account_id = outputs.accounts[account_name]
                self._networks.register(f"lz-{account_id}-{network.region}", NetworkInput(
                    name=f"{organization} {network.label} shared VPC", account_id=account_id, region=network.region,
                    vpc_id=network.vpc_id, cidr=network.cidr, private_subnet_ids=network.subnet_ids,
                    security_group_ids=[network.security_group_id], is_default=True))

    def _describe(self, record: models.LandingZoneDesignRecord) -> dict:
        return {"id": str(record.id), "version": record.version, "status": record.status,
                "organization_name": record.answers["organization_name"], "answers": record.answers,
                "edits": record.edits,
                "created_by": record.created_by, "submitted_by": record.submitted_by,
                "decided_by": record.decided_by, "decision_comment": record.decision_comment,
                "repository": record.repository, "commit_sha": record.commit_sha, "accounts": record.accounts or {},
                "created_at": record.created_at.isoformat()}


def _ou_json(ou: OuNode) -> dict:
    permissions = EditPermissions()
    return {"key": ou.key, "name": ou.name, "kind": ou.kind, "environment": ou.environment, "tier": ou.tier,
            "created_by_control_tower": ou.created_by_control_tower, "custom": ou.custom,
            "domain": ou.isolation_domain, "allowed_edits": permissions.for_ou(ou),
            "blocked_edits": permissions.blocked_for_ou(ou), "accounts": [_account_json(account) for account in ou.accounts],
            "children": [_ou_json(child) for child in ou.children]}


def _account_json(account: AccountPlan) -> dict:
    return {"name": account.name, "enabled": account.enabled, "added": account.added,
            "allowed_edits": EditPermissions().for_account(account)}
