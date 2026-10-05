from functools import partial

from sqlalchemy.orm import Session

from app.adapters.ports import AwsPort, GitHubPort
from app.db import models
from app.networks.service import NetworkService
from app.projects.files import ProjectFiles
from app.projects.readback import GENERATOR, INPUT_FILE, KIND, REVISION
from app.projects.repository import ProjectRepository
from app.projects.tags import TagSet
from app.provisioning.queue import JobQueue
from app.provisioning.saga import Saga
from app.provisioning.states import ProjectStatus
from app.provisioning.steps import ProvisioningContext, ProvisioningPlanner
from app.provisioning.topology import TopologyFactory
from app.readback.manifest import ManifestSealer, ManifestSigner
from app.registry.service import RegistryService
from app.synth.request import ProjectRequest


class JobRunner:
    """Runs one provisioning job: build the files, plan the steps, run them as a saga, record the result."""

    def __init__(self, queue: JobQueue, projects: ProjectRepository, registry: RegistryService,
                 files: ProjectFiles, topologies: TopologyFactory,
                 planner: ProvisioningPlanner, networks: NetworkService, github: GitHubPort, aws: AwsPort,
                 owner: str, sealer: ManifestSealer):
        self._queue = queue
        self._projects = projects
        self._registry = registry
        self._project_files = files
        self._topologies = topologies
        self._planner = planner
        self._networks = networks
        self._github = github
        self._aws = aws
        self._owner = owner
        self._sealer = sealer

    @classmethod
    def for_session(cls, session: Session, github: GitHubPort, aws: AwsPort, owner: str,
                    signer: ManifestSigner) -> "JobRunner":
        return cls(JobQueue(session), ProjectRepository(session), RegistryService.for_session(session),
                   ProjectFiles.for_session(session),
                   TopologyFactory.default(), ProvisioningPlanner(), NetworkService.for_session(session), github, aws,
                   owner, ManifestSealer(signer))

    def run(self, job: models.Job) -> None:
        request = ProjectRequest.model_validate(job.payload)
        context = self.context(job.request_id, request, REVISION)
        outcome = Saga(self._planner.steps_for(context), partial(self._queue.record_step, job)).run(context)
        self._queue.finish(job, outcome.state, outcome.error)
        self._projects.set_status(request.project_name, ProjectStatus.for_job_state(outcome.state), context.commit_sha)

    @property
    def queue(self) -> JobQueue:
        return self._queue

    @property
    def projects(self) -> ProjectRepository:
        return self._projects

    def context(self, request_id: str, request: ProjectRequest, revision: int) -> ProvisioningContext:
        ownership = request.ownership
        cost_center = self._registry.resolve_cost_center(ownership.portfolio_id, ownership.product_id,
                                                         request.project_name)
        accounts = self._registry.target_accounts(request.provider, ownership.portfolio_id, request.environments)
        topology = self._topologies.for_resilience(request.resilience)
        return ProvisioningContext(
            request_id=request_id, request=request, owner=self._owner,
            files=self._files(request, revision), accounts=accounts,
            topology=topology, tags=TagSet(request, cost_center).as_dict(), github=self._github, aws=self._aws,
            networks=self._networks.resolve(request, topology, accounts))

    def _files(self, request: ProjectRequest, revision: int) -> dict[str, str]:
        files = self._project_files.render(request)
        return self._sealer.seal(kind=KIND, id=request.project_name, revision=revision, generator=GENERATOR,
                                 input=INPUT_FILE, files=files)
