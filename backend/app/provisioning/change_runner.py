from functools import partial

from sqlalchemy.orm import Session

from app.adapters.ports import GitHubPort, ProviderPort
from app.db import models
from app.projects.change_repository import ChangeState, ProjectChangeRepository
from app.provisioning.runner import JobRunner
from app.provisioning.saga import Saga
from app.provisioning.states import JobState
from app.provisioning.steps import ChangePlanner
from app.readback.manifest import ManifestSigner
from app.synth.request import ProjectRequest


class ChangeJobRunner:
    """Runs a change job (§21.8): regenerate at the new revision, then branch and pull request, as a saga."""

    def __init__(self, provisioning: JobRunner, changes: ProjectChangeRepository, planner: ChangePlanner):
        self._provisioning = provisioning
        self._changes = changes
        self._planner = planner

    @classmethod
    def for_session(cls, session: Session, github: GitHubPort, cloud: ProviderPort, owner: str,
                    signer: ManifestSigner) -> "ChangeJobRunner":
        return cls(JobRunner.for_session(session, github, cloud, owner, signer), ProjectChangeRepository(session),
                   ChangePlanner())

    def run(self, job: models.Job) -> None:
        change = self._changes.get(job.change_id)
        current = ProjectRequest.model_validate(self._provisioning.projects.get(change.project_name).request)
        context = self._provisioning.context(job.request_id, ProjectRequest.model_validate(change.request),
                                             change.revision)
        context.branch, context.title, context.body = change.branch, title(change), body(change)
        queue = self._provisioning.queue
        outcome = Saga(self._planner.steps_for(context, current), partial(queue.record_step, job)).run(context)
        queue.finish(job, outcome.state, outcome.error)
        if outcome.state == JobState.SUCCEEDED:
            change.state = ChangeState.OPEN
            change.pull_request_number, change.pull_request_url = context.pull_request.number, context.pull_request.url
        else:
            change.state = ChangeState.FAILED
        self._changes.commit()


def title(change: models.ProjectChange) -> str:
    return f"Change infrastructure: revision {change.revision}"


def body(change: models.ProjectChange) -> str:
    summary = change.summary
    removed = [f"{service['id']} ({service['removal']})" for service in summary["removed_services"]]
    lines = [("Added services", summary["added_services"]), ("Removed services", removed),
             ("Changed services", summary["changed_services"]), ("Added environments", summary["added_environments"]),
             ("Files", summary["changed_files"])]
    return "\n".join([f"Requested by {change.created_by} through the CloudInfra platform (revision {change.revision}).",
                      "", *[f"- {label}: {', '.join(values)}" for label, values in lines if values], ""])
