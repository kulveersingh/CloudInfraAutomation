import uuid

from sqlalchemy.orm import Session

from app.db import models
from app.errors import NotFoundError, ValidationFailedError
from app.projects.repository import ProjectRepository
from app.registry.repository import RegistryRepository
from app.registry.service import require
from app.releases.executor import ReleaseExecutor
from app.releases.gate import GateContext, GateEvaluator
from app.releases.plan import PlanSubmission
from app.releases.policy import Actor, ApprovalPolicy, Role
from app.releases.repository import ReleaseRepository
from app.releases.risk import ChangeRiskClassifier, RiskLevel
from app.releases.simulator import LocalPipelineSimulator
from app.releases.state import InvalidTransitionError, ReleaseState, ReleaseStateMachine
from app.synth.request import ProjectRequest

STAGE = "stage"
INBOX_STATES = {Role.REVIEWER: ReleaseState.AWAITING_APPROVAL, Role.PLATFORM_ADMIN: ReleaseState.OVERRIDE_REQUESTED}


class ReleaseService:
    """Release workflow: plan intake, automated gate, overrides, reviewer approval, execution."""

    def __init__(self, releases: ReleaseRepository, projects: ProjectRepository, registry: RegistryRepository,
                 classifier: ChangeRiskClassifier, gate: GateEvaluator, machine: ReleaseStateMachine,
                 policy: ApprovalPolicy, executor: ReleaseExecutor, simulator: LocalPipelineSimulator):
        self._releases = releases
        self._projects = projects
        self._registry = registry
        self._classifier = classifier
        self._gate = gate
        self._machine = machine
        self._policy = policy
        self._executor = executor
        self._simulator = simulator

    @classmethod
    def for_session(cls, session: Session, executor: ReleaseExecutor) -> "ReleaseService":
        return cls(ReleaseRepository(session), ProjectRepository(session), RegistryRepository(session),
                   ChangeRiskClassifier.default(), GateEvaluator.default(), ReleaseStateMachine(), ApprovalPolicy(),
                   executor, LocalPipelineSimulator.default())

    # ---- intake ----

    def submit_plan(self, submission: PlanSubmission) -> dict:
        project = self._project(submission.project_name)
        environment = self._enabled_environment(project, submission.environment)
        self._supersede_pending(project.name, environment.id)
        release = models.Release(
            project_name=project.name, environment_id=environment.id, commit_sha=submission.commit_sha,
            artifact_digest=submission.artifact_digest, changes=self._classifier.classify(submission.changes),
            evidence=submission.evidence.model_dump(), risk=self._classifier.overall(submission.changes),
            gate_findings=[], state=ReleaseState.PLANNED, requested_by=submission.requested_by)
        self._releases.add(release)
        release.gate_findings = self._gate.findings(GateContext(
            environment=environment.id, artifact_digest=release.artifact_digest, evidence=submission.evidence,
            last_stage_artifact=self._releases.last_deployed_artifact(project.name, STAGE)))
        self._advance(release, environment)
        return self.describe(release)

    def simulate(self, project_name: str, environment_id: str, actor: Actor, high_risk: bool) -> dict:
        project = self._project(project_name)
        request = ProjectRequest.model_validate(project.request)
        return self.submit_plan(self._simulator.plan(request, environment_id, actor.name, high_risk))

    # ---- decisions ----

    def approve(self, release_id: uuid.UUID, actor: Actor, comment: str) -> dict:
        release = self._release(release_id)
        self._policy.check_reviewer(actor, release)
        self._require_state(release, {ReleaseState.AWAITING_APPROVAL})
        self._record_decision(release, actor, "approve", comment)
        self._execute(release)
        return self.describe(release)

    def reject(self, release_id: uuid.UUID, actor: Actor, comment: str) -> dict:
        release = self._release(release_id)
        self._policy.check_reviewer(actor, release)
        self._require_state(release, ReleaseState.PENDING)
        self._record_decision(release, actor, "reject", comment)
        self._move(release, ReleaseState.REJECTED)
        return self.describe(release)

    def approve_override(self, release_id: uuid.UUID, actor: Actor, comment: str) -> dict:
        release = self._release(release_id)
        self._policy.check_override(actor, release)
        self._require_state(release, {ReleaseState.OVERRIDE_REQUESTED})
        self._record_decision(release, actor, "override", comment)
        self._release_or_wait(release, self._registry.environment(release.environment_id))
        return self.describe(release)

    # ---- views ----

    def get(self, release_id: uuid.UUID) -> dict:
        return self.describe(self._release(release_id))

    def releases(self, project_name: str | None) -> list[dict]:
        return [self.describe(release) for release in self._releases.for_project(project_name)]

    def inbox(self, actor: Actor) -> list[dict]:
        states = [state for role, state in INBOX_STATES.items() if actor.has_role(role)]
        return [self.describe(release) for release in self._releases.in_states(states)]

    def pipeline(self, project_name: str) -> list[dict]:
        project = self._project(project_name)
        enabled = set(project.request["environments"])
        return [self._pipeline_stage(project.name, environment) for environment in self._registry.environments()
                if environment.id in enabled]

    def describe(self, release: models.Release) -> dict:
        decisions = [{"actor": decision.actor, "kind": decision.kind, "comment": decision.comment,
                      "created_at": decision.created_at.isoformat()} for decision in self._releases.decisions(release)]
        return {"id": str(release.id), "project_name": release.project_name, "environment": release.environment_id,
                "commit_sha": release.commit_sha, "artifact_digest": release.artifact_digest, "risk": release.risk,
                "changes": release.changes, "evidence": release.evidence, "gate_findings": release.gate_findings,
                "state": release.state, "requested_by": release.requested_by,
                "execution_detail": release.execution_detail, "created_at": release.created_at.isoformat(),
                "decisions": decisions}

    # ---- workflow ----

    def _advance(self, release: models.Release, environment: models.Environment) -> None:
        if release.gate_findings:
            self._move(release, ReleaseState.GATE_FAILED)
        elif release.risk == RiskLevel.HIGH:
            self._move(release, ReleaseState.OVERRIDE_REQUESTED)
        else:
            self._release_or_wait(release, environment)

    def _release_or_wait(self, release: models.Release, environment: models.Environment) -> None:
        if environment.requires_approval:
            self._move(release, ReleaseState.AWAITING_APPROVAL)
        else:
            self._execute(release)

    def _execute(self, release: models.Release) -> None:
        self._move(release, ReleaseState.DEPLOYING)
        result = self._executor.execute(release)
        release.execution_detail = result.detail
        self._move(release, ReleaseState.DEPLOYED if result.succeeded else ReleaseState.ROLLED_BACK)

    def _move(self, release: models.Release, target: str) -> None:
        self._machine.check(release.state, target)
        release.state = target
        self._releases.commit()

    def _supersede_pending(self, project_name: str, environment_id: str) -> None:
        for release in self._releases.pending_for(project_name, environment_id):
            self._move(release, ReleaseState.SUPERSEDED)

    def _record_decision(self, release: models.Release, actor: Actor, kind: str, comment: str) -> None:
        self._releases.add_decision(models.ReleaseDecision(release_id=release.id, actor=actor.name, kind=kind,
                                                           comment=comment))
        self._registry.add_audit(actor.name, f"release.{kind}", {"release": str(release.id), "comment": comment})

    def _require_state(self, release: models.Release, allowed: set[str] | frozenset[str]) -> None:
        if release.state not in allowed:
            raise InvalidTransitionError(f"The release is {release.state}; this decision is not possible.")

    def _pipeline_stage(self, project_name: str, environment: models.Environment) -> dict:
        latest = self._releases.latest_for(project_name, environment.id)
        return {"environment": environment.id, "name": environment.name,
                "requires_approval": environment.requires_approval,
                "release": self.describe(latest) if latest else None}

    def _project(self, project_name: str) -> models.Project:
        return require(self._projects.get(project_name), NotFoundError(f"Unknown project '{project_name}'."))

    def _release(self, release_id: uuid.UUID) -> models.Release:
        return require(self._releases.get(release_id), NotFoundError(f"Unknown release '{release_id}'."))

    def _enabled_environment(self, project: models.Project, environment_id: str) -> models.Environment:
        if environment_id not in project.request["environments"]:
            raise ValidationFailedError(f"{environment_id} is not enabled for {project.name}.")
        return self._registry.environment(environment_id)
