import uuid
from collections import Counter

from sqlalchemy.orm import Session

from app.adapters.ports import GitHubPort
from app.db import models
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.catalog.controls import CatalogError, ControlCatalogSnapshot
from app.landing_zone.catalog.packs import PROFILE_PACKS, PackRegistry
from app.landing_zone.catalog.resolver import EnabledControl, PackResolver
from app.landing_zone.catalog.templates import IndustryTemplate, TemplateRegistry
from app.landing_zone.cloudformation.bundle import LandingZoneBundle, StackSizeRule
from app.landing_zone.cloudformation.guardrails import GuardrailPlan, ScpQuotaRule
from app.landing_zone.design import AccountPlan, LandingZoneDesign, OrgCatalog, OuNode
from app.landing_zone.designer import LandingZoneDesigner
from app.landing_zone.diagram import OuDiagramRenderer
from app.landing_zone.edits import EditPermissions, TreeEdit, TreeEditor
from app.landing_zone.executor import LandingZoneExecutor, LandingZoneOutputs
from app.landing_zone.readback import GENERATOR, INPUT_FILE, KIND, REPOSITORY_NAME, LandingZoneSubject
from app.landing_zone.repository import LandingZoneRepository
from app.landing_zone.request import LandingZoneRequest
from app.landing_zone.states import DesignStatus
from app.landing_zone.validation import DesignAdvisor, DesignValidator
from app.networks.models import NetworkInput
from app.networks.service import NetworkService
from app.readback.manifest import ManifestSealer, ManifestSigner
from app.readback.subjects import ownership_properties
from app.registry.service import RegistryService, require
from app.releases.policy import Actor, Role

REPOSITORY_MARKER = "landing-zone"
BEHAVIORS = ("PREVENTIVE", "DETECTIVE", "PROACTIVE")
# Placeholder identity used only to preview a template's structure before the customer names the organization.
PREVIEW_ORGANIZATION = {"organization_name": "example", "management_email": "aws@example.com",
                        "home_region": "us-east-1", "governed_regions": ["us-east-1", "us-east-2"]}


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
                 github: GitHubPort, executor: LandingZoneExecutor, owner: str, signer: ManifestSigner):
        self._repository = repository
        self._registry = registry
        self._networks = networks
        self._github = github
        self._executor = executor
        self._owner = owner
        self._sealer = ManifestSealer(signer)
        self._policy = LandingZonePolicy()
        self._designer = LandingZoneDesigner.default()

    @classmethod
    def for_session(cls, session: Session, github: GitHubPort, executor: LandingZoneExecutor, owner: str,
                    signer: ManifestSigner) -> "LandingZoneService":
        return cls(LandingZoneRepository(session), RegistryService.for_session(session),
                   NetworkService.for_session(session), github, executor, owner, signer)

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

    def templates(self, actor: Actor) -> list[dict]:
        self._policy.require_admin(actor)
        return [self._template_summary(template) for template in TemplateRegistry.default().all()]

    def template(self, template_id: str, actor: Actor) -> dict:
        self._policy.require_admin(actor)
        try:
            template = TemplateRegistry.default().get(template_id)
        except CatalogError as error:
            raise NotFoundError(str(error)) from error
        return {**self._template_summary(template), "answers": template.answers, "edits": template.edits}

    def control_packs(self, actor: Actor) -> dict:
        self._policy.require_admin(actor)
        snapshot = ControlCatalogSnapshot.default()
        return {"mappings_refreshed": snapshot.mappings_refreshed, "profiles": PROFILE_PACKS,
                "packs": [{"id": pack.id, "version": pack.version, "name": pack.name, "description": pack.description,
                           "selectors": list(pack.selectors), "optional": pack.optional,
                           "controls": [_control_json(snapshot.get(control_id)) for control_id in pack.control_ids]}
                          for pack in PackRegistry.default().all()]}

    def repository_subject(self, actor: Actor) -> LandingZoneSubject:
        """The applied design to read back from landing-zone-infra (§21)."""
        self._policy.require_admin(actor)
        record = require(self._repository.latest_applied(), NotFoundError("No landing zone has been applied yet."))
        return LandingZoneSubject(record, self._render)

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
        record.commit_sha = self._commit(design, record, actor)
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
        design.edits = list(edits)
        return design

    def _render(self, request: LandingZoneRequest) -> dict[str, str]:
        return LandingZoneBundle.default().render(self._design(request.answers, request.edits), self._catalog())

    def _design_of(self, record: models.LandingZoneDesignRecord) -> LandingZoneDesign:
        return self._design(LandingZoneAnswers.model_validate(record.answers), TreeEditor.parse(record.edits))

    def _problems(self, design: LandingZoneDesign) -> list[str]:
        return [*design.edit_problems, *DesignValidator.default().problems(design),
                *ScpQuotaRule().problems(GuardrailPlan.for_design(design)),
                *StackSizeRule().problems(design, self._catalog())]

    def _template_summary(self, template: IndustryTemplate) -> dict:
        answers = LandingZoneAnswers.model_validate({**PREVIEW_ORGANIZATION, **template.answers})
        design = self._design(answers, TreeEditor.parse(template.edits))
        enabled = [item for items in PackResolver.default().resolve(design).controls.values() for item in items]
        distinct = {item.control.id: item.control.behavior for item in enabled}
        behaviors = Counter(distinct.values())
        return {"id": template.id, "version": template.version, "name": template.name, "industry": template.industry,
                "description": template.description, "frameworks": list(template.frameworks),
                "frameworks_verified": ControlCatalogSnapshot.default().mappings_refreshed is not None,
                "environments": [environment.name for environment in answers.environments()],
                "packs": answers.packs(), "ou_count": len(list(design.walk())),
                "control_counts": {behavior: behaviors[behavior] for behavior in BEHAVIORS},
                "enabled_controls": len(enabled)}

    def _explain(self, design: LandingZoneDesign) -> dict:
        renderer = OuDiagramRenderer()
        controls = PackResolver.default().resolve(design).controls
        return {"ous": [_ou_json(ou, controls) for ou in design.root_ous], "problems": self._problems(design),
                "warnings": DesignAdvisor.default().warnings(design),
                "diagram": {"svg": renderer.svg(design), "mermaid": renderer.mermaid(design)}}

    def _record(self, design_id: uuid.UUID) -> models.LandingZoneDesignRecord:
        return require(self._repository.get(design_id), NotFoundError(f"Unknown landing zone design '{design_id}'."))

    def _in_status(self, design_id: uuid.UUID, status: str) -> models.LandingZoneDesignRecord:
        record = self._record(design_id)
        if record.status != status:
            raise ConflictError(f"Design v{record.version} is {record.status}, not {status}.")
        return record

    def _commit(self, design: LandingZoneDesign, record: models.LandingZoneDesignRecord, actor: Actor) -> str:
        design_id = str(record.id)
        self._github.create_repository(self._owner, REPOSITORY_NAME, marker=REPOSITORY_MARKER)
        self._github.set_repository_properties(self._owner, REPOSITORY_NAME, ownership_properties(KIND, design_id))
        files = self._sealer.seal(kind=KIND, id=design_id, revision=record.version, generator=GENERATOR,
                                  input=INPUT_FILE, files=LandingZoneBundle.default().render(design, self._catalog()))
        return self._github.commit_files(self._owner, REPOSITORY_NAME, files,
                                         f"Landing zone design v{record.version} approved by {actor.name}")

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


def _ou_json(ou: OuNode, controls: dict[str, list[EnabledControl]]) -> dict:
    permissions = EditPermissions()
    return {"key": ou.key, "name": ou.name, "kind": ou.kind, "environment": ou.environment, "tier": ou.tier,
            "created_by_control_tower": ou.created_by_control_tower, "custom": ou.custom,
            "domain": ou.isolation_domain, "allowed_edits": permissions.for_ou(ou),
            "blocked_edits": permissions.blocked_for_ou(ou), "accounts": [_account_json(account) for account in ou.accounts],
            "controls": [{"id": enabled.control.id, "name": enabled.control.name, "behavior": enabled.control.behavior,
                          "severity": enabled.control.severity, "packs": list(enabled.packs)}
                         for enabled in controls.get(ou.key, [])],
            "children": [_ou_json(child, controls) for child in ou.children]}


def _control_json(control) -> dict:
    return {"id": control.id, "name": control.name, "behavior": control.behavior, "severity": control.severity,
            "implementation": control.implementation, "frameworks": list(control.frameworks)}


def _account_json(account: AccountPlan) -> dict:
    return {"name": account.name, "enabled": account.enabled, "added": account.added,
            "allowed_edits": EditPermissions().for_account(account)}
