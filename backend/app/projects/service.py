from sqlalchemy.orm import Session

from app.db import models
from app.errors import ConflictError, ValidationFailedError
from app.projects.repository import ProjectRepository
from app.projects.tags import TagSet
from app.provisioning.queue import JobQueue
from app.provisioning.states import ProjectStatus
from app.provisioning.topology import TopologyFactory
from app.registry.service import RegistryService
from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.lint import LintError, TemplateLinter
from app.synth.render import RepositoryBundle
from app.synth.request import ProjectRequest
from app.synth.synthesizer import TemplateSynthesizer
from app.synth.validation import RequestValidationError, RequestValidator


class ProjectService:
    """Project use cases: preview what will be created, and start provisioning."""

    def __init__(self, registry: RegistryService, synthesizer: TemplateSynthesizer, validator: RequestValidator,
                 linter: TemplateLinter, bundle: RepositoryBundle, topologies: TopologyFactory, queue: JobQueue,
                 projects: ProjectRepository):
        self._registry = registry
        self._synthesizer = synthesizer
        self._validator = validator
        self._linter = linter
        self._bundle = bundle
        self._topologies = topologies
        self._queue = queue
        self._projects = projects

    @classmethod
    def for_session(cls, session: Session) -> "ProjectService":
        blocks, binders = BlockRegistry.default(), BinderRegistry.default()
        return cls(RegistryService.for_session(session), TemplateSynthesizer(blocks, binders),
                   RequestValidator.default(blocks, binders), TemplateLinter.default(), RepositoryBundle.default(),
                   TopologyFactory.default(), JobQueue(session), ProjectRepository(session))

    def preview(self, request: ProjectRequest) -> dict:
        self._validate(request)
        template = self._synthesizer.synthesize(request)
        ownership = request.ownership
        cost_center = self._registry.resolve_cost_center(ownership.portfolio_id, ownership.product_id,
                                                         request.project_name)
        return {"files": self._bundle.render(request, template), "tags": TagSet(request, cost_center).as_dict(),
                "targets": self._targets(request), "lint": self._linter.lint(template)}

    def create(self, request: ProjectRequest, idempotency_key: str) -> models.Job:
        self._validate(request)
        self._reject_lint_findings(self._synthesizer.synthesize(request))
        if self._queue.by_request_id(idempotency_key) is None:
            self._register(request)
        return self._queue.enqueue(request.project_name, idempotency_key, request.model_dump(mode="json"))

    def projects(self) -> list[dict]:
        return [{"name": project.name, "portfolio_id": project.portfolio_id, "product_id": project.product_id,
                 "resilience_mode": project.resilience_mode, "status": project.status}
                for project in self._projects.all()]

    def _validate(self, request: ProjectRequest) -> None:
        try:
            self._validator.validate(request)
        except RequestValidationError as error:
            raise ValidationFailedError(str(error)) from error
        self._registry.validate_ownership(request.ownership.portfolio_id, request.ownership.product_id)
        self._registry.validate_environments(request.environments)
        self._registry.validate_regions(request.resilience)

    def _reject_lint_findings(self, template: dict) -> None:
        try:
            self._linter.assert_clean(template)
        except LintError as error:
            raise ValidationFailedError(str(error)) from error

    def _targets(self, request: ProjectRequest) -> dict:
        accounts = self._registry.target_accounts(request.ownership.portfolio_id, request.environments)
        topology = self._topologies.for_resilience(request.resilience)
        return {environment: {"account_id": account, "regions": topology.regions_for(environment)}
                for environment, account in accounts.items()}

    def _register(self, request: ProjectRequest) -> None:
        if self._projects.get(request.project_name) is not None:
            raise ConflictError(f"Project '{request.project_name}' already exists.")
        self._projects.add(models.Project(
            name=request.project_name, portfolio_id=request.ownership.portfolio_id,
            product_id=request.ownership.product_id, resilience_mode=request.resilience.mode,
            status=ProjectStatus.PROVISIONING, request=request.model_dump(mode="json")))
