import hashlib
import secrets

from app.providers.aws.project.toolkit import aws_project
from app.releases.plan import ChangeSpec, Evidence, PlanSubmission
from app.releases.risk import STATEFUL_TYPES
from app.synth.request import ProjectRequest
from app.synth.synthesizer import TemplateSynthesizer

COMMIT_BYTES = 6


class LocalPipelineSimulator:
    """Produces the plan a project's pipeline would send, so approvals can be exercised locally."""

    def __init__(self, synthesizer: TemplateSynthesizer):
        self._synthesizer = synthesizer

    @classmethod
    def default(cls) -> "LocalPipelineSimulator":
        return cls(aws_project().synthesizer)

    def plan(self, request: ProjectRequest, environment: str, requested_by: str, high_risk: bool = False) -> PlanSubmission:
        resources = self._synthesizer.synthesize(request)["Resources"]
        replaced = self._replaced_resource(resources) if high_risk else None
        changes = [self._change(logical_id, body["Type"], logical_id == replaced) for logical_id, body in resources.items()]
        return PlanSubmission(project_name=request.project_name, environment=environment,
                              commit_sha=secrets.token_hex(COMMIT_BYTES), artifact_digest=self._artifact(request),
                              changes=changes, evidence=Evidence(tests_passed=True, signed=True),
                              requested_by=requested_by)

    def _replaced_resource(self, resources: dict) -> str | None:
        return next((logical_id for logical_id, body in resources.items() if body["Type"] in STATEFUL_TYPES), None)

    def _change(self, logical_id: str, resource_type: str, replaced: bool) -> ChangeSpec:
        action = "Modify" if replaced else "Add"
        return ChangeSpec(action=action, logical_id=logical_id, resource_type=resource_type, replacement=replaced)

    def _artifact(self, request: ProjectRequest) -> str:
        return "sha256:" + hashlib.sha256(request.project_name.encode()).hexdigest()
