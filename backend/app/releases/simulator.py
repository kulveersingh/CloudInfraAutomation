import hashlib
import secrets

from app.releases.plan import ChangeSpec, Evidence, PlanSubmission
from app.releases.risk import ResourceClassifier
from app.synth.request import ProjectRequest
from app.synth.synthesizer import TemplateSynthesizer

COMMIT_BYTES = 6


class LocalPipelineSimulator:
    """Produces the plan a project's pipeline would send, so approvals can be exercised locally."""

    def __init__(self, synthesizer: TemplateSynthesizer, resources: ResourceClassifier):
        self._synthesizer = synthesizer
        self._resources = resources

    def plan(self, request: ProjectRequest, environment: str, requested_by: str, high_risk: bool = False) -> PlanSubmission:
        rows = self._resources.rows(self._synthesizer.synthesize(request))
        replaced = self._replaced_resource(rows) if high_risk else None
        changes = [self._change(address, resource_type, address == replaced) for address, resource_type in rows]
        return PlanSubmission(project_name=request.project_name, environment=environment,
                              commit_sha=secrets.token_hex(COMMIT_BYTES), artifact_digest=self._artifact(request),
                              changes=changes, evidence=Evidence(tests_passed=True, signed=True),
                              requested_by=requested_by)

    def _replaced_resource(self, rows: list[tuple[str, str]]) -> str | None:
        return next((address for address, resource_type in rows if self._resources.is_stateful(resource_type)), None)

    def _change(self, logical_id: str, resource_type: str, replaced: bool) -> ChangeSpec:
        action = "Modify" if replaced else "Add"
        return ChangeSpec(action=action, logical_id=logical_id, resource_type=resource_type, replacement=replaced)

    def _artifact(self, request: ProjectRequest) -> str:
        return "sha256:" + hashlib.sha256(request.project_name.encode()).hexdigest()
