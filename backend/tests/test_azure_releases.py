"""Release rows on Azure (§22.11, MC4-9): the classifier, rows of a generated project, and what-if results. What-if
cannot show a replacement, so changing a resource that holds data is medium risk."""

import pytest

from app.providers.azure.provider import AzureProvider
from app.providers.azure.releases import AzureResourceClassifier, WhatIfReader
from app.releases.plan import ChangeSpec
from app.releases.risk import ChangeRiskClassifier
from tests.azure_helpers import azure_request, synthesize

JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}
GROUP = "/subscriptions/0b1f6d5e-1234-4c3a-9a7b-2f6e8d9c0a11/resourceGroups/rg-invoice-ingest-stage"
ACCOUNT = f"{GROUP}/providers/Microsoft.Storage/storageAccounts/stuploadsabc"
ROLE = f"{ACCOUNT}/providers/Microsoft.Authorization/roleAssignments/1f0c"


@pytest.mark.parametrize("type_name", [
    "Microsoft.Storage/storageAccounts", "Microsoft.Storage/storageAccounts/blobServices/containers",
    "Microsoft.DocumentDB/databaseAccounts", "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers",
    "Microsoft.Sql/servers/databases", "Microsoft.DBforPostgreSQL/flexibleServers",
    "Microsoft.DBforMySQL/flexibleServers", "Microsoft.ServiceBus/namespaces/queues", "Microsoft.KeyVault/vaults",
    "microsoft.storage/storageaccounts",
])
def test_data_holding_types_are_stateful(type_name):
    assert AzureResourceClassifier().is_stateful(type_name) is True


def test_compute_holds_no_data():
    classifier = AzureResourceClassifier()
    assert (classifier.is_stateful("Microsoft.Web/sites"), classifier.is_stateful("Microsoft.Web/serverfarms"),
            classifier.is_stateful("Microsoft.EventGrid/systemTopics")) == (False, False, False)


@pytest.mark.parametrize("type_name, permission", [
    ("Microsoft.Authorization/roleAssignments", True), ("Microsoft.Authorization/policyAssignments", True),
    ("Microsoft.ManagedIdentity/userAssignedIdentities", True),
    ("Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments", True),
    ("Microsoft.Web/sites", False),
])
def test_permission_types(type_name, permission):
    assert AzureResourceClassifier().is_permission(type_name) is permission


def test_a_documents_rows_name_the_stack_type_and_service():
    rows = AzureResourceClassifier().rows(synthesize(azure_request(
        resources=[{"id": "processor", "type": "compute.function"}, {"id": "jobs", "type": "messaging.queue"}],
        connections=[{"kind": "access.grant", "source": "processor", "target": "jobs", "access": "readwrite"}])))
    assert {"data/Microsoft.Storage/storageAccounts/code", "shared/Microsoft.ServiceBus/namespaces/jobs",
            "shared/Microsoft.Authorization/roleAssignments/processor → jobs",
            "shared/Microsoft.Authorization/roleAssignments/processor → jobs #2",
            "app/Microsoft.Web/sites/processor"} <= {address for address, _ in rows}


def test_every_row_is_unique():
    rows = AzureResourceClassifier().rows(synthesize(azure_request()))
    assert len(rows) == len({address for address, _ in rows})


# ---- what-if ----

def what_if(*changes) -> dict:
    return {"status": "Succeeded", "changes": [{"resourceId": resource_id, "changeType": change_type}
                                               for resource_id, change_type in changes]}


def test_what_if_changes_become_release_rows():
    function = f"{GROUP}/providers/Microsoft.Web/sites/func-a"
    rows = WhatIfReader().changes(what_if((ACCOUNT, "Create"), (ROLE, "Modify"), (function, "Deploy"),
                                          (f"{GROUP}/providers/Microsoft.Web/serverfarms/plan-a", "NoChange"),
                                          (f"{GROUP}/providers/Microsoft.Web/sites/func-b", "Ignore")))
    assert rows == [ChangeSpec(action="Add", logical_id=ACCOUNT, resource_type="Microsoft.Storage/storageAccounts"),
                    ChangeSpec(action="Modify", logical_id=ROLE, resource_type="Microsoft.Authorization/roleAssignments"),
                    ChangeSpec(action="Modify", logical_id=function, resource_type="Microsoft.Web/sites")]


def test_child_resource_types_come_from_the_resource_id():
    [row] = WhatIfReader().changes(what_if((f"{ACCOUNT}/blobServices/default/containers/data", "Create")))
    assert row.resource_type == "Microsoft.Storage/storageAccounts/blobServices/containers"


def test_deletes_count_only_for_resources_the_stack_manages():
    """Complete-mode what-if lists the other stacks' resources as deletes; only the stack's own are removed."""
    other = f"{GROUP}/providers/Microsoft.Web/sites/func-other"
    rows = WhatIfReader().changes(what_if((ROLE, "Delete"), (other, "Delete")), managed={ROLE.upper()})
    assert rows == [ChangeSpec(action="Remove", logical_id=ROLE, resource_type="Microsoft.Authorization/roleAssignments")]


def test_the_data_stack_never_deletes():
    assert WhatIfReader().changes(what_if((ACCOUNT, "Delete"))) == []


def test_changing_data_is_medium_risk_because_what_if_hides_replacements():
    classifier = ChangeRiskClassifier.for_resources(AzureResourceClassifier())
    [modified] = WhatIfReader().changes(what_if((ACCOUNT, "Modify")))
    [function] = WhatIfReader().changes(what_if((f"{GROUP}/providers/Microsoft.Web/sites/func-a", "Modify")))
    assert (classifier.risk_of(modified), classifier.risk_of(function)) == ("medium", "low")


def test_other_providers_add_no_rules():
    from app.providers.gcp.releases import TerraformResourceClassifier

    assert TerraformResourceClassifier().rules() == []


def test_the_provider_gives_its_classifier():
    assert isinstance(AzureProvider().resources(), AzureResourceClassifier)


# ---- releases through the API ----

@pytest.fixture
def project(client):
    client.post("/v1/projects", json=azure_request(), headers={"Idempotency-Key": "k1"})


def simulate(client, high_risk=False) -> dict:
    return client.post("/v1/projects/invoice-ingest/releases:simulate",
                       json={"environment": "stage", "high_risk": high_risk}, headers=JORDAN).json()


def test_a_release_lists_the_template_resources(client, project):
    rows = {change["logical_id"]: change["risk"] for change in simulate(client)["changes"]}
    assert (rows["data/Microsoft.Storage/storageAccounts/uploads"],
            rows["shared/Microsoft.Authorization/roleAssignments/uploads → processor"],
            rows["app/Microsoft.Web/sites/processor"]) == ("low", "medium", "low")


def test_replacing_a_storage_account_is_high_risk(client, project):
    release = simulate(client, high_risk=True)
    replaced = [change for change in release["changes"] if change["replacement"]]
    assert (release["risk"], [change["logical_id"] for change in replaced]) == (
        "high", ["data/Microsoft.Storage/storageAccounts/uploads"])
