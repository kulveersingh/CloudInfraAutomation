import json

from app.projects.tags import MANAGED_BY
from app.providers.gcp.labels import LabelPolicy
from app.providers.gcp.project.capabilities import GcpBlock
from app.providers.gcp.project.document import PRIMARY_ONLY, TerraformDocument, generator, label
from app.synth.blocks.base import Block
from app.synth.synthesizer import IacDialect

STRING = {"type": "string"}
FOUNDATION_VARIABLES = {
    "project_id": {**STRING, "description": "The environment's Google Cloud project"},
    "project_name": STRING,
    "environment_name": STRING,
    "resilience_mode": {**STRING, "default": "single"},
    "region": STRING,
    "region_role": {**STRING, "default": "primary"},
    "activation_state": {**STRING, "default": "active"},
}
NETWORK_VARIABLES = {
    "network": {**STRING, "description": "Shared VPC network self-link"},
    "subnetwork": {**STRING, "description": "Shared VPC subnetwork in this region"},
    "network_tags": {"type": "list(string)", "default": []},
}
CONTRACT = "contract"


class TerraformJsonDialect(IacDialect):
    """Google Cloud documents are Terraform configurations in JSON syntax, applied by Infrastructure Manager once per
    environment project and region. Project-wide resources are created by the primary region's deployment."""

    def start(self, request):
        document = TerraformDocument()
        for name, body in FOUNDATION_VARIABLES.items():
            document.add_variable(name, body)
        # The cost center comes from the registry at deploy time (a repository variable), so it can change alone.
        document.add_variable("org_cost_center", STRING)
        document.set_local("labels", self._labels(request))
        document.set_local("is_primary", '${var.region_role == "primary"}')
        document.set_local("is_active", '${var.activation_state == "active"}')
        document.set_local("generator", generator())
        return document

    def _labels(self, request) -> dict[str, str]:
        ownership, policy = request.ownership, LabelPolicy()
        fixed = {"org_portfolio": ownership.portfolio_id, "org_product": ownership.product_id,
                 "org_data_classification": ownership.data_classification, "org_resilience": request.resilience.mode}
        return {"org_project": "${var.project_name}", "org_environment": "${var.environment_name}",
                "org_cost_center": label("org_cost_center"),
                **{key: policy.value(value) for key, value in fixed.items()}, "managed_by": MANAGED_BY}

    def add_block(self, document, block: GcpBlock):
        for name, body in block.required_variables().items():
            document.add_variable(name, body)
        block.emit(document)

    def finish(self, document, request, blocks: dict[str, Block]):
        if any(block.uses_network for block in blocks.values()):
            for name, body in NETWORK_VARIABLES.items():
                document.add_variable(name, body)
        self._publish_contract(document, request, blocks)
        return document.to_dict()

    def _publish_contract(self, document: TerraformDocument, request, blocks: dict[str, Block]) -> None:
        """The infrastructure contract, in Secret Manager so application repos can discover resources."""
        resources = {resource_id: {"type": block.type_name, **block.contract_entry()}
                     for resource_id, block in blocks.items()}
        contract = {"contractVersion": "1", "project": "${var.project_name}", "environment": "${var.environment_name}",
                    "resilienceMode": "${var.resilience_mode}", "resources": resources}
        primary_only = {"count": PRIMARY_ONLY} if request.resilience.is_multi_region else {}
        document.add_resource("google_secret_manager_secret", CONTRACT, {
            **primary_only, "secret_id": f"{request.project_name}-contract", "replication": {"auto": {}}})
        secret = f"google_secret_manager_secret.{CONTRACT}{'[0]' if primary_only else ''}.id"
        document.add_resource("google_secret_manager_secret_version", CONTRACT, {
            **primary_only, "secret": f"${{{secret}}}", "secret_data": json.dumps(contract, sort_keys=True)})
