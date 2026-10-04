from functools import partial

from sqlalchemy.orm import Session

from app.adapters.ports import AwsPort, GitHubPort
from app.db import models
from app.projects.repository import ProjectRepository
from app.projects.tags import TagSet
from app.provisioning.queue import JobQueue
from app.provisioning.saga import Saga
from app.provisioning.states import ProjectStatus
from app.provisioning.steps import ProvisioningContext, ProvisioningPlanner
from app.provisioning.topology import TopologyFactory
from app.registry.service import RegistryService
from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.render import RepositoryBundle
from app.synth.request import ProjectRequest
from app.synth.synthesizer import TemplateSynthesizer


class JobRunner:
    """Runs one provisioning job: build the files, plan the steps, run them as a saga, record the result."""

    def __init__(self, queue: JobQueue, projects: ProjectRepository, registry: RegistryService,
                 synthesizer: TemplateSynthesizer, bundle: RepositoryBundle, topologies: TopologyFactory,
                 planner: ProvisioningPlanner, github: GitHubPort, aws: AwsPort, owner: str):
        self._queue = queue
        self._projects = projects
        self._registry = registry
        self._synthesizer = synthesizer
        self._bundle = bundle
        self._topologies = topologies
        self._planner = planner
        self._github = github
        self._aws = aws
        self._owner = owner

    @classmethod
    def for_session(cls, session: Session, github: GitHubPort, aws: AwsPort, owner: str) -> "JobRunner":
        return cls(JobQueue(session), ProjectRepository(session), RegistryService.for_session(session),
                   TemplateSynthesizer(BlockRegistry.default(), BinderRegistry.default()), RepositoryBundle.default(),
                   TopologyFactory.default(), ProvisioningPlanner(), github, aws, owner)

    def run(self, job: models.Job) -> None:
        request = ProjectRequest.model_validate(job.payload)
        context = self._context(job, request)
        outcome = Saga(self._planner.steps_for(context), partial(self._queue.record_step, job)).run(context)
        self._queue.finish(job, outcome.state, outcome.error)
        self._projects.set_status(request.project_name, ProjectStatus.for_job_state(outcome.state))

    def _context(self, job: models.Job, request: ProjectRequest) -> ProvisioningContext:
        ownership = request.ownership
        cost_center = self._registry.resolve_cost_center(ownership.portfolio_id, ownership.product_id,
                                                         request.project_name)
        return ProvisioningContext(
            request_id=job.request_id, request=request, owner=self._owner,
            files=self._bundle.render(request, self._synthesizer.synthesize(request)),
            accounts=self._registry.target_accounts(ownership.portfolio_id, request.environments),
            topology=self._topologies.for_resilience(request.resilience),
            tags=TagSet(request, cost_center).as_dict(), github=self._github, aws=self._aws)
