from sqlalchemy.orm import Session

from app.db import models
from app.errors import ConflictError, NotFoundError, ValidationFailedError
from app.networks.service import NetworkService
from app.projects.change_repository import ProjectChangeRepository
from app.projects.files import ProjectFiles
from app.projects.readback import ProjectSubject
from app.projects.repository import ProjectRepository
from app.projects.tags import TagSet
from app.providers.base import ProviderRegistry, unknown_provider
from app.provisioning.queue import JobQueue
from app.provisioning.states import ProjectStatus
from app.provisioning.topology import TopologyFactory
from app.registry.service import RegistryService, require
from app.synth.lint import LintError
from app.synth.request import ProjectRequest
from app.synth.toolkit import ProjectToolkit
from app.synth.validation import RequestValidationError


class ProjectService:
    """Project use cases: preview what will be created, and start provisioning."""

    def __init__(self, registry: RegistryService, providers: ProviderRegistry, topologies: TopologyFactory,
                 queue: JobQueue, projects: ProjectRepository, networks: NetworkService,
                 changes: ProjectChangeRepository, files: ProjectFiles):
        self._registry = registry
        self._providers = providers
        self._topologies = topologies
        self._queue = queue
        self._projects = projects
        self._networks = networks
        self._changes = changes
        self._files = files

    @classmethod
    def for_session(cls, session: Session) -> "ProjectService":
        return cls(RegistryService.for_session(session), ProviderRegistry.default(), TopologyFactory.default(), JobQueue(session), ProjectRepository(session),
                   NetworkService.for_session(session), ProjectChangeRepository(session),
                   ProjectFiles.for_session(session))

    def preview(self, request: ProjectRequest) -> dict:
        toolkit = self._validate(request)
        template = toolkit.synthesizer.synthesize(request)
        ownership = request.ownership
        cost_center = self._registry.resolve_cost_center(ownership.portfolio_id, ownership.product_id,
                                                         request.project_name)
        return {"files": toolkit.bundle.render(request, template), "tags": TagSet(request, cost_center).as_dict(),
                "targets": self._targets(request), "lint": toolkit.linter.lint(template)}

    def check(self, request: ProjectRequest) -> None:
        """Everything that must hold before the platform provisions or changes a project."""
        toolkit = self._validate(request)
        self._targets(request)
        self._reject_lint_findings(toolkit, toolkit.synthesizer.synthesize(request))

    def create(self, request: ProjectRequest, idempotency_key: str) -> models.Job:
        self.check(request)
        if self._queue.by_request_id(idempotency_key) is None:
            self._register(request)
        return self._queue.enqueue(request.project_name, idempotency_key, request.model_dump(mode="json"))

    def projects(self) -> list[dict]:
        return [{"name": project.name, "portfolio_id": project.portfolio_id, "product_id": project.product_id,
                 "resilience_mode": project.resilience_mode, "status": project.status, "revision": project.revision,
                 "environments": project.request["environments"],
                 "open_change": self._open_change(project.name), "provider": project.provider}
                for project in self._projects.all()]

    def _open_change(self, project_name: str) -> dict | None:
        change = self._changes.active(project_name)
        if change is None:
            return None
        return {"id": str(change.id), "revision": change.revision, "state": change.state,
                "pull_request": pull_request_json(change)}

    def repository_subject(self, project_name: str) -> ProjectSubject:
        """The project to read back from its infrastructure repository (§21)."""
        project = require(self._projects.get(project_name), NotFoundError(f"Unknown project '{project_name}'."))
        return ProjectSubject(project, self.render)

    def render(self, request: ProjectRequest) -> dict[str, str]:
        return self._files.render(request)

    def toolkit(self, provider: str) -> ProjectToolkit:
        """The provider's project toolkit; an unknown provider is an invalid request."""
        if not self._providers.has(provider):
            raise ValidationFailedError(unknown_provider(provider))
        return self._providers.get(provider).project()

    def _validate(self, request: ProjectRequest) -> ProjectToolkit:
        toolkit = self.toolkit(request.provider)
        try:
            toolkit.validator.validate(request)
        except RequestValidationError as error:
            raise ValidationFailedError(str(error)) from error
        self._registry.validate_ownership(request.ownership.portfolio_id, request.ownership.product_id)
        self._registry.validate_environments(request.environments)
        self._registry.validate_regions(request.provider, request.resilience)
        return toolkit

    def _reject_lint_findings(self, toolkit: ProjectToolkit, template: dict) -> None:
        try:
            toolkit.linter.assert_clean(template)
        except LintError as error:
            raise ValidationFailedError(str(error)) from error

    def _targets(self, request: ProjectRequest) -> dict:
        accounts = self._registry.target_accounts(request.provider, request.ownership.portfolio_id,
                                                  request.environments)
        topology = self._topologies.for_resilience(request.resilience)
        networks = self._networks.resolve(request, topology, accounts)
        return {environment: {"account_id": account, "regions": topology.regions_for(environment),
                              "networks": self._networks_for(environment, networks)}
                for environment, account in accounts.items()}

    def _networks_for(self, environment: str, networks: dict[tuple[str, str], dict]) -> dict:
        return {region: {"network_id": network["id"], "vpc_id": network["vpc_id"],
                         "subnet_ids": network["private_subnet_ids"]}
                for (network_environment, region), network in networks.items() if network_environment == environment}

    def _register(self, request: ProjectRequest) -> None:
        if self._projects.get(request.project_name) is not None:
            raise ConflictError(f"Project '{request.project_name}' already exists.")
        self._projects.add(models.Project(
            name=request.project_name, provider=request.provider, portfolio_id=request.ownership.portfolio_id,
            product_id=request.ownership.product_id, resilience_mode=request.resilience.mode,
            status=ProjectStatus.PROVISIONING, request=request.model_dump(mode="json")))


def pull_request_json(change: models.ProjectChange) -> dict | None:
    if change.pull_request_number is None:
        return None
    return {"number": change.pull_request_number, "url": change.pull_request_url}
