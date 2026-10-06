"""An Azure project through the same flows as on AWS and Google Cloud: provisioning, read-back and Change
infrastructure (§22.11). Removal follows MC4-2: data is kept, everything else (access included) is deleted."""

import json
import re

import pytest

from app.adapters.factory import AdapterFactory
from app.adapters.local_azure import LocalAzure
from app.adapters.local_github import LocalGitHub
from app.providers.azure.expressions import unique_string
from app.provisioning.worker import Worker
from app.readback.manifest import MANIFEST_PATH, ManifestSigner
from tests.azure_helpers import DR, HA, azure_request, resources, synthesize

OWNER = "acme-platform"
REPOSITORY = "invoice-ingest-infra"
PROJECT = "/v1/projects/invoice-ingest"
JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}
ROLE = "Microsoft.Authorization/roleAssignments"
# Access and wiring: never kept when the service or connection that needs it goes.
ACCESS_AND_WIRING = {ROLE, "Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments",
                     "Microsoft.ManagedIdentity/userAssignedIdentities", "Microsoft.EventGrid/systemTopics",
                     "Microsoft.Network/privateEndpoints"}
EVERYTHING = azure_request(
    resources=[{"id": "uploads", "type": "storage.bucket"}, {"id": "processor", "type": "compute.function"},
               {"id": "orders", "type": "database.table"}, {"id": "jobs", "type": "messaging.queue"},
               {"id": "cache", "type": "Microsoft.Cache/redis"}],
    connections=[{"kind": "event.notify", "source": "uploads", "target": "processor", "prefix": "in/"},
                 {"kind": "access.grant", "source": "processor", "target": "orders", "access": "readwrite"},
                 {"kind": "access.grant", "source": "processor", "target": "jobs", "access": "write"},
                 {"kind": "access.grant", "source": "processor", "target": "uploads", "access": "read",
                  "prefix": "in/"}],
    resilience=DR, attach=True)
SHAPES = {
    "default": azure_request(),
    "everything, DR and attached": EVERYTHING,
    "HA": azure_request(resilience=HA),
    "attached storage without functions": azure_request(resources=[{"id": "uploads", "type": "storage.bucket"}],
                                                        attach=True),
    "attached database without functions": azure_request(resources=[{"id": "orders", "type": "database.table"}],
                                                         attach=True),
}


def github(settings) -> LocalGitHub:
    return LocalGitHub(settings.local_state_dir)


def run_worker(settings, session_factory) -> None:
    factory = AdapterFactory()
    Worker(session_factory, factory.github(settings), factory.clouds(settings), settings.github_owner,
           ManifestSigner.from_settings(settings)).process_one()


def provision(client, settings, session_factory, payload: dict) -> dict:
    client.post("/v1/projects", json=payload, headers={"Idempotency-Key": "k1"})
    run_worker(settings, session_factory)
    return client.get(f"{PROJECT}/repository:read-back").json()


@pytest.fixture
def provisioned(client, settings, session_factory) -> dict:
    return provision(client, settings, session_factory, azure_request(resilience=DR, attach=True))


def files(settings) -> dict[str, str]:
    return github(settings).read_files(OWNER, REPOSITORY).files


# ---- the stacks: data kept, everything else deleted (MC4-2) ----

@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_the_data_stack_holds_only_what_is_kept(shape):
    payload = SHAPES[shape]
    kept = {item["id"] for item in payload["resources"] if item["type"] in {"storage.bucket", "database.table"}
            or item["type"].startswith("Microsoft.")}
    data = synthesize(payload)["data"]
    assert [(item["type"], item["comments"]) for item in data["resources"]
            if item["type"] in ACCESS_AND_WIRING or item["comments"] not in kept | {"contract", "code"}] == []


def test_access_identities_and_wiring_are_in_the_shared_stack():
    shared = synthesize(EVERYTHING)["shared"]
    assert ({item["type"] for item in shared["resources"]} >= ACCESS_AND_WIRING,
            {item["comments"] for item in resources(shared, ROLE)}) == (
        True, {"processor host", "uploads → processor", "processor → jobs", "processor → uploads"})


def test_queues_are_deleted_with_their_service_like_on_other_clouds():
    shared = synthesize(EVERYTHING)["shared"]
    assert [item["comments"] for item in resources(shared, "Microsoft.ServiceBus/namespaces/queues")] == ["jobs"]


def test_function_code_containers_go_but_the_shared_code_account_stays():
    document = synthesize(EVERYTHING)
    assert ([item["comments"] for item in resources(document["data"], "Microsoft.Storage/storageAccounts")],
            [item["comments"] for item in resources(document["shared"],
                                                    "Microsoft.Storage/storageAccounts/blobServices/containers")]) == (
        ["uploads", "code"], ["processor"])


def defined_types(template: dict) -> set[str]:
    return {item["type"].lower() for item in template["resources"]}


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_every_template_depends_only_on_its_own_resources(shape):
    """ARM refuses a dependsOn on a resource the template does not define; other stacks deploy first."""
    for name, template in synthesize(SHAPES[shape]).items():
        foreign = [(name, item["comments"], entry) for item in template["resources"] for entry in item.get("dependsOn", [])
                   if re.match(r"\[resourceId\('([^']+)'", entry).group(1).lower() not in defined_types(template)]
        assert foreign == []


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_every_template_declares_the_parameters_it_uses(shape):
    for name, template in synthesize(SHAPES[shape]).items():
        used = set(re.findall(r"parameters\('(\w+)'\)", json.dumps(template)))
        assert (name, used - set(template["parameters"])) == (name, set())


# ---- provisioning ----

def test_provisioning_creates_a_sealed_repository_with_three_stacks(client, settings, provisioned):
    assert ({"main.json", "shared.json", "app.json", "parameters/prod.json", MANIFEST_PATH} <= set(files(settings)),
            client.get("/v1/projects").json()[0]["status"]) == (True, "active")


def test_every_environment_gets_a_federated_deploy_identity_in_its_resource_group(settings, provisioned):
    stacks = [stack for stack in LocalAzure(settings.local_state_dir).stacks() if stack["environment"] == "prod"]
    assert ({stack["deployer_identity"].split("/resourceGroups/")[1] for stack in stacks},
            {stack["region"] for stack in stacks}) == (
        {"rg-invoice-ingest-prod/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-invoice-ingest-prod-deploy"},
        {"eastus2", "centralus"})


def test_environment_variables_point_the_workflow_at_the_environment_subscription(settings, provisioned):
    variables = github(settings).environment(OWNER, REPOSITORY, "prod")
    assert (variables["AZURE_RESOURCE_GROUP"], variables["AZURE_SECONDARY_REGION"],
            variables["ACTIVATION_STATE_SECONDARY"], variables["SUBNET_ID_SECONDARY"].split("/virtualNetworks/")[1]) == (
        "rg-invoice-ingest-prod", "centralus", "standby", "vnet-centralus/subnets/functions")


def test_workflow_deploys_data_then_shared_then_each_region(settings, provisioned):
    workflow = files(settings)[".github/workflows/deploy.yml"]
    order = [workflow.index(f'--name "invoice-ingest-{name}"') for name in
             ("data", "shared", "${{ vars.AZURE_PRIMARY_REGION }}", "${{ vars.AZURE_SECONDARY_REGION }}")]
    shared = workflow[order[1]:order[2]]
    assert (order == sorted(order), "--template-file shared.json" in shared,
            "--action-on-unmanage deleteResources" in shared, "endpointSubnetId=${{ vars.ENDPOINT_SUBNET_ID }}" in shared,
            github(settings).repository_variables(OWNER, REPOSITORY)["ORG_COST_CENTER"]) == (
        True, True, True, True, "CC-4410")


def test_the_contract_vault_is_named_for_the_environment_so_the_workflow_can_recover_it(settings, provisioned):
    variables = github(settings).environment(OWNER, REPOSITORY, "prod")
    group = f"/subscriptions/{variables['AZURE_SUBSCRIPTION_ID']}/resourceGroups/rg-invoice-ingest-prod"
    assert variables["CONTRACT_VAULT"] == f"kv{unique_string(group)}"


def test_workflow_recovers_a_soft_deleted_contract_vault_before_the_data_stack(settings, provisioned):
    """After a teardown the purge-protected vault stays soft-deleted for 90 days under the same name (§22.11.6)."""
    workflow = files(settings)[".github/workflows/deploy.yml"]
    recover = workflow.index('az keyvault recover --name "${{ vars.CONTRACT_VAULT }}" --resource-group "$RG" '
                             '--location "${{ vars.AZURE_PRIMARY_REGION }}"')
    assert recover < workflow.index('--name "invoice-ingest-data"')


def test_preview_shows_the_ownership_tags(client):
    tags = client.post("/v1/projects:preview", json=azure_request()).json()["tags"]
    assert (tags["org:portfolio"], tags["org:cost-center"], tags["org:managed-by"]) == (
        "pf-payments", "CC-4410", "cloudinfra")


# ---- read-back ----

def test_read_back_returns_the_request(provisioned):
    assert (provisioned["verified"], provisioned["findings"], provisioned["request"]["provider"],
            provisioned["design"]["revision"]) == (True, [], "azure", 1)


def test_hand_edited_shared_stack_blocks_read_back(client, settings, provisioned):
    github(settings).commit_files(OWNER, REPOSITORY, {"shared.json": "{}\n"}, "hand edit")
    result = client.get(f"{PROJECT}/repository:read-back").json()
    assert (result["verified"], result["findings"][0]["check"], result["findings"][0]["files"][0]["path"]) == (
        False, "integrity", "shared.json")


# ---- Change infrastructure ----

def change(provisioned: dict, resources: list[dict], connections: list[dict] | None = None) -> dict:
    request = {**provisioned["request"], "resources": resources,
               "connections": provisioned["request"]["connections"] if connections is None else connections}
    return {"request": request, "base_commit": provisioned["commit_sha"]}


def preview(client, body: dict) -> dict:
    return client.post(f"{PROJECT}/changes:preview", json=body).json()


def test_adding_a_database_puts_it_in_the_data_stack_and_its_endpoint_in_the_shared_stack(client, provisioned):
    body = change(provisioned, [*provisioned["request"]["resources"], {"id": "orders", "type": "database.table",
                                                                       "config": {}}])
    result = preview(client, body)
    data, shared = json.loads(result["files"]["main.json"]), json.loads(result["files"]["shared.json"])
    assert (result["summary"]["added_services"], result["summary"]["changed_files"],
            [item["comments"] for item in resources(data, "Microsoft.DocumentDB/databaseAccounts")],
            sorted(item["comments"] for item in resources(shared, "Microsoft.Network/privateEndpoints"))) == (
        ["orders"], ["app.json", "infra.json", "main.json", "shared.json"], ["orders"], ["orders", "uploads"])


def test_removing_a_connection_leaves_the_data_stack_alone_so_its_access_is_deleted(client, provisioned):
    result = preview(client, change(provisioned, provisioned["request"]["resources"], []))
    shared = json.loads(result["files"]["shared.json"])
    assert (result["summary"]["changed_files"], resources(shared, ROLE, "uploads → processor"),
            resources(shared, "Microsoft.EventGrid/systemTopics")) == (
        ["app.json", "infra.json", "shared.json"], [], [])


def test_removing_a_function_deletes_its_identity(client, provisioned):
    result = preview(client, change(provisioned, [{"id": "uploads", "type": "storage.bucket", "config": {}}], []))
    shared = json.loads(result["files"]["shared.json"])
    assert (result["summary"]["removed_services"],
            resources(shared, "Microsoft.ManagedIdentity/userAssignedIdentities")) == (
        [{"id": "processor", "type": "compute.function", "retained": False, "removal": "deleted"}], [])


def test_removing_a_storage_account_keeps_it_out_of_every_stack(client, provisioned):
    result = preview(client, change(provisioned, [{"id": "processor", "type": "compute.function", "config": {}}], []))
    [removed] = result["summary"]["removed_services"]
    assert (removed, "uploads" in {item["comments"] for item in json.loads(result["files"]["main.json"])["resources"]}) == (
        {"id": "uploads", "type": "storage.bucket", "retained": True,
         "removal": "kept: detached from the data stack, delete it by hand"}, False)


def test_change_opens_a_pull_request_that_says_what_happens_to_removed_services(client, settings, session_factory,
                                                                               provisioned):
    body = change(provisioned, [{"id": "processor", "type": "compute.function", "config": {}}], [])
    created = client.post(f"{PROJECT}/changes", json={**body, "confirm_removals": True}, headers=JORDAN).json()
    run_worker(settings, session_factory)
    pull_request = github(settings).pull_request(OWNER, REPOSITORY, 1)
    assert (client.get(f"{PROJECT}/changes/{created['id']}").json()["state"],
            "uploads (kept: detached from the data stack, delete it by hand)" in pull_request["body"]) == ("open", True)
