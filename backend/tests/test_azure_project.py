"""Azure projects as ARM templates (§22.11, MC-4b): a data stack and an app stack per region, the curated services,
exact-resource role assignments, Event Grid with native filters, lint and the resource-type snapshot."""

import json

import pytest

from app.providers.azure.provider import AzureProvider
from app.synth.request import ProjectRequest
from app.synth.validation import RequestValidationError
from tests.azure_helpers import DR, HA, azure_request, resource, resources, synthesize

STORAGE = "Microsoft.Storage/storageAccounts"
SITES = "Microsoft.Web/sites"
COSMOS = "Microsoft.DocumentDB/databaseAccounts"
ROLE = "Microsoft.Authorization/roleAssignments"
BLOB_READER = "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1"
BLOB_CONTRIBUTOR = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"


def toolkit():
    return AzureProvider().project()


def validate(payload: dict) -> list[str]:
    try:
        toolkit().validator.validate(ProjectRequest.model_validate(payload))
    except RequestValidationError as error:
        return error.messages
    return []


def role(document: dict, role_id: str) -> dict:
    [found] = [item for item in resources(document["data"], ROLE) if role_id in item["properties"]["roleDefinitionId"]]
    return found


# ---- the two stacks ----

def test_a_project_is_a_data_stack_and_an_app_stack():
    document = synthesize(azure_request())
    assert ({stack["$schema"] for stack in document.values()}, set(document)) == (
        {"https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"}, {"data", "app"})


def test_stacks_share_the_project_parameters():
    document = synthesize(azure_request())
    assert {"projectName", "environmentName", "location", "costCenter"} <= set(document["data"]["parameters"]) & set(
        document["app"]["parameters"])


def test_the_app_stack_knows_its_region_role():
    parameters = synthesize(azure_request())["app"]["parameters"]
    assert (parameters["regionRole"]["defaultValue"], parameters["activationState"]["allowedValues"]) == (
        "primary", ["active", "standby"])


def test_every_resource_carries_the_ownership_tags():
    document = synthesize(azure_request())
    tags = document["data"]["variables"]["tags"]
    assert ((tags["org:project"], tags["org:cost-center"], tags["org:managed-by"]),
            {item.get("tags") for stack in document.values() for item in stack["resources"]
             if item["type"] not in (ROLE, "Microsoft.Storage/storageAccounts/blobServices",
                                     "Microsoft.Storage/storageAccounts/blobServices/containers",
                                     "Microsoft.Storage/storageAccounts/managementPolicies",
                                     "Microsoft.EventGrid/systemTopics/eventSubscriptions",
                                     "Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments",
                                     "Microsoft.KeyVault/vaults/secrets")}) == (
        ("[parameters('projectName')]", "[parameters('costCenter')]", "cloudinfra"), {"[variables('tags')]"})


def test_generation_is_deterministic():
    assert json.dumps(synthesize(azure_request())) == json.dumps(synthesize(azure_request()))


# ---- storage.bucket ----

def test_storage_accounts_are_locked_down():
    account = resource(synthesize(azure_request())["data"], STORAGE, "uploads")
    properties = account["properties"]
    assert (account["name"], account["kind"], account["sku"], properties["allowSharedKeyAccess"],
            properties["allowBlobPublicAccess"], properties["minimumTlsVersion"], properties["supportsHttpsTrafficOnly"]) == (
        "[variables('uploadsName')]", "StorageV2", {"name": "Standard_ZRS"}, False, False, "TLS1_2", True)


def test_storage_account_names_fit_azure_limits():
    variables = synthesize(azure_request())["data"]["variables"]
    assert variables["uploadsName"] == "[concat('st', take('uploads', 9), uniqueString(resourceGroup().id))]"


def test_blobs_keep_versions_and_expire_old_ones():
    data = synthesize(azure_request())["data"]
    service = resource(data, "Microsoft.Storage/storageAccounts/blobServices", "uploads")
    policy = resource(data, "Microsoft.Storage/storageAccounts/managementPolicies", "uploads")
    assert (service["properties"]["isVersioningEnabled"], service["properties"]["deleteRetentionPolicy"],
            policy["properties"]["policy"]["rules"][0]["definition"]["actions"]["version"]) == (
        True, {"enabled": True, "days": 7}, {"delete": {"daysAfterCreationGreaterThan": 30}})


@pytest.mark.parametrize("resilience, sku", [(DR, "Standard_GZRS"), (HA, "Standard_RAGZRS")])
def test_multi_region_storage_is_geo_redundant(resilience, sku):
    assert resource(synthesize(azure_request(resilience=resilience))["data"], STORAGE, "uploads")["sku"] == {"name": sku}


def test_geo_redundant_storage_needs_the_regions_pair():
    payload = azure_request(resilience={"mode": "dr", "primary_region": "eastus2", "secondary_region": "westus"})
    assert validate(payload) == [("Azure geo-redundant storage replicates to the primary region's pair: choose centralus "
                                 "as the secondary region for eastus2.")]


def test_a_region_without_a_pair_cannot_replicate_storage():
    payload = azure_request(resilience={"mode": "dr", "primary_region": "qatarcentral", "secondary_region": "eastus2"})
    assert validate(payload) == ["Azure geo-redundant storage needs a paired primary region; qatarcentral has none."]


def test_projects_without_storage_may_use_any_secondary():
    payload = azure_request(resources=[{"id": "processor", "type": "compute.function"}],
                            resilience={"mode": "dr", "primary_region": "eastus2", "secondary_region": "westus"})
    assert validate(payload) == []


# ---- compute.function ----

def test_functions_run_on_flex_consumption_with_their_own_identity():
    document = synthesize(azure_request())
    site = resource(document["app"], SITES, "processor")
    identity = resource(document["data"], "Microsoft.ManagedIdentity/userAssignedIdentities", "processor")
    assert (site["kind"], identity["name"], list(site["identity"]["userAssignedIdentities"]),
            site["properties"]["functionAppConfig"]["runtime"],
            site["properties"]["functionAppConfig"]["scaleAndConcurrency"]) == (
        "functionapp,linux", "id-processor",
        ["[resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', 'id-processor')]"],
        {"name": "python", "version": "3.12"}, {"maximumInstanceCount": 100, "instanceMemoryMB": 2048})


def test_function_code_comes_from_its_deployment_container():
    storage = resource(synthesize(azure_request())["app"], SITES, "processor")["properties"]["functionAppConfig"][
        "deployment"]["storage"]
    assert (storage["type"], storage["value"], storage["authentication"]["type"]) == (
        "blobContainer",
        "[format('https://{0}.blob.{1}/app-processor', variables('codeName'), environment().suffixes.storage)]",
        "UserAssignedIdentity")


def test_function_settings_reach_the_app():
    payload = azure_request(resources=[{"id": "processor", "type": "compute.function", "config": {
        "runtime": "node", "memory_mb": 4096, "max_instances": 40}}])
    config = resource(synthesize(payload)["app"], SITES, "processor")["properties"]["functionAppConfig"]
    assert (config["runtime"], config["scaleAndConcurrency"]) == (
        {"name": "node", "version": "22"}, {"maximumInstanceCount": 40, "instanceMemoryMB": 4096})


def test_attached_functions_join_the_subnet_and_take_no_public_traffic():
    properties = resource(synthesize(azure_request(attach=True))["app"], SITES, "processor")["properties"]
    assert (properties["virtualNetworkSubnetId"], properties["publicNetworkAccess"]) == (
        "[parameters('subnetId')]", "Disabled")


def test_functions_deploy_in_every_region_with_regional_names():
    variables = synthesize(azure_request(resilience=DR))["app"]["variables"]
    assert variables["processorApp"] == (
        "[concat('func-', take('invoice-ingest-processor', 33), '-', uniqueString(resourceGroup().id, "
        "parameters('location')))]")


# ---- database.table ----

def database(**config) -> dict:
    return synthesize(azure_request(resources=[{"id": "orders", "type": "database.table", "config": config}]))


def test_cosmos_uses_entra_only_and_continuous_backup():
    properties = resource(database()["data"], COSMOS, "orders")["properties"]
    assert (properties["disableLocalAuth"], properties["backupPolicy"], properties["locations"]) == (
        True, {"type": "Continuous", "continuousModeProperties": {"tier": "Continuous30Days"}},
        [{"locationName": "[parameters('location')]", "failoverPriority": 0, "isZoneRedundant": True}])


def test_the_partition_key_is_a_setting():
    container = resource(database(partition_key="tenantId")["data"],
                         "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers", "orders")
    assert container["properties"]["resource"]["partitionKey"] == {"paths": ["/tenantId"], "kind": "Hash"}


def test_dr_cosmos_adds_a_read_region_and_ha_writes_everywhere():
    dr = resource(synthesize(azure_request(resources=[{"id": "orders", "type": "database.table"}], resilience=DR))["data"],
                  COSMOS, "orders")["properties"]
    ha = resource(synthesize(azure_request(resources=[{"id": "orders", "type": "database.table"}], resilience=HA))["data"],
                  COSMOS, "orders")["properties"]
    assert ([location["locationName"] for location in dr["locations"]], dr["enableMultipleWriteLocations"],
            ha["enableMultipleWriteLocations"]) == (
        ["[parameters('location')]", "[parameters('secondaryLocation')]"], False, True)


# ---- messaging.queue ----

def test_queues_dead_letter_and_use_entra_only():
    data = synthesize(azure_request(resources=[{"id": "jobs", "type": "messaging.queue"}]))["data"]
    namespace = resource(data, "Microsoft.ServiceBus/namespaces", "jobs")
    queue = resource(data, "Microsoft.ServiceBus/namespaces/queues", "jobs")
    assert (namespace["sku"], namespace["properties"]["disableLocalAuth"], queue["properties"]["maxDeliveryCount"],
            queue["properties"]["deadLetteringOnMessageExpiration"]) == ({"name": "Standard", "tier": "Standard"},
                                                                         True, 5, True)


def test_multi_region_queues_are_premium():
    data = synthesize(azure_request(resources=[{"id": "jobs", "type": "messaging.queue"}], resilience=DR))["data"]
    assert resource(data, "Microsoft.ServiceBus/namespaces", "jobs")["sku"]["name"] == "Premium"


# ---- access.grant ----

def grant(target: dict, access: str, prefix: str = "") -> dict:
    return synthesize(azure_request(resources=[{"id": "processor", "type": "compute.function"}, target],
                                    connections=[{"kind": "access.grant", "source": "processor", "target": target["id"],
                                                  "access": access, "prefix": prefix}]))


def test_bucket_access_is_a_role_on_the_container():
    assignment = role(grant({"id": "reports", "type": "storage.bucket"}, "write"), BLOB_CONTRIBUTOR)
    assert (assignment["scope"], assignment["properties"]["principalType"], "condition" in assignment["properties"]) == (
        "[format('Microsoft.Storage/storageAccounts/{0}/blobServices/default/containers/data', variables('reportsName'))]",
        "ServicePrincipal", False)


def test_bucket_access_to_a_prefix_is_an_abac_condition():
    properties = role(grant({"id": "reports", "type": "storage.bucket"}, "read", "monthly/"), BLOB_READER)["properties"]
    assert (properties["conditionVersion"], "StringStartsWith 'monthly/'" in properties["condition"]) == ("2.0", True)


def test_cosmos_access_is_a_data_plane_role_on_the_container():
    [assignment] = resources(grant({"id": "orders", "type": "database.table"}, "readwrite")["data"],
                             "Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments")
    assert (assignment["properties"]["roleDefinitionId"].endswith("'00000000-0000-0000-0000-000000000002')]"),
            assignment["properties"]["scope"]) == (
        True, ("[format('{0}/dbs/data/colls/data', resourceId('Microsoft.DocumentDB/databaseAccounts', "
              "variables('ordersName')))]"))


def test_queue_access_sends_and_receives_on_the_queue():
    document = grant({"id": "jobs", "type": "messaging.queue"}, "readwrite")
    scopes = {item["scope"] for item in resources(document["data"], ROLE) if item.get("comments") == "processor → jobs"}
    assert scopes == {"[format('Microsoft.ServiceBus/namespaces/{0}/queues/jobs', variables('jobsName'))]"}


def test_access_puts_the_target_in_the_app_settings():
    settings = {item["name"]: item["value"] for item in resource(
        grant({"id": "jobs", "type": "messaging.queue"}, "read")["app"], SITES, "processor")["properties"]["siteConfig"][
        "appSettings"]}
    assert (settings["JOBS_NAMESPACE"], settings["JOBS_QUEUE"]) == ("[variables('jobsName')]", "jobs")


# ---- event.notify ----

def test_bucket_events_reach_the_function_through_event_grid_with_native_filters():
    document = synthesize(azure_request())
    topic = resource(document["data"], "Microsoft.EventGrid/systemTopics", "uploads")
    subscription = resource(document["app"], "Microsoft.EventGrid/systemTopics/eventSubscriptions", "uploads → processor")
    assert (topic["properties"]["topicType"], subscription["condition"], subscription["properties"]["filter"]) == (
        "Microsoft.Storage.StorageAccounts", "[equals(parameters('activationState'), 'active')]",
        {"includedEventTypes": ["Microsoft.Storage.BlobCreated"],
         "subjectBeginsWith": "/blobServices/default/containers/data/blobs/incoming/", "subjectEndsWith": ".csv"})


def test_the_triggered_function_can_read_the_bucket():
    assert role(synthesize(azure_request()), BLOB_READER)["comments"] == "uploads → processor"


def test_no_notes_are_needed_because_filters_are_native():
    assert toolkit().notes(ProjectRequest.model_validate(azure_request())) == []


# ---- contract ----

def test_the_contract_is_a_key_vault_secret():
    data = synthesize(azure_request())["data"]
    vault = resource(data, "Microsoft.KeyVault/vaults", "contract")
    secret = resource(data, "Microsoft.KeyVault/vaults/secrets", "contract")
    assert (vault["properties"]["enableRbacAuthorization"], vault["properties"]["enablePurgeProtection"],
            secret["properties"]["value"]) == (True, True, "[string(variables('contract'))]")


# ---- lint ----

def test_generated_templates_have_no_lint_findings():
    for payload in (azure_request(), azure_request(resilience=DR, attach=True),
                    azure_request(resources=[{"id": "processor", "type": "compute.function"},
                                             {"id": "orders", "type": "database.table"},
                                             {"id": "jobs", "type": "messaging.queue"}],
                                  connections=[{"kind": "access.grant", "source": "processor", "target": "orders",
                                                "access": "readwrite"},
                                               {"kind": "access.grant", "source": "processor", "target": "jobs",
                                                "access": "read"}])):
        assert toolkit().linter.lint(synthesize(payload)) == []


def stack(*items) -> dict:
    return {"data": {"resources": list(items)}, "app": {"resources": []}}


@pytest.mark.parametrize("item, finding", [
    ({"type": ROLE, "apiVersion": "2022-04-01", "name": "x", "comments": "x", "properties": {
        "principalId": "p", "roleDefinitionId": "[subscriptionResourceId('Microsoft.Authorization/roleDefinitions', "
                                                "'b24988ac-6180-42a0-ab88-20f7382dd24c')]"}},
     "Microsoft.Authorization/roleAssignments x: broad role Contributor."),
    ({"type": ROLE, "apiVersion": "2022-04-01", "name": "x", "comments": "x", "scope": "[subscription().id]",
      "properties": {"principalId": "p", "roleDefinitionId": f"[{BLOB_READER}]"}},
     "Microsoft.Authorization/roleAssignments x: role assignment above the resource group."),
    ({"type": STORAGE, "apiVersion": "2023-05-01", "name": "x", "location": "l", "kind": "StorageV2", "comments": "x",
      "sku": {"name": "Standard_ZRS"}, "properties": {"allowSharedKeyAccess": True, "allowBlobPublicAccess": False}},
     "Microsoft.Storage/storageAccounts x: shared key access is on."),
    ({"type": COSMOS, "apiVersion": "2024-11-15", "name": "x", "location": "l", "comments": "x",
      "properties": {"databaseAccountOfferType": "Standard", "locations": []}},
     "Microsoft.DocumentDB/databaseAccounts x: local authentication is on."),
])
def test_lint_findings(item, finding):
    assert toolkit().linter.lint(stack(item)) == [finding]


def test_schema_check_finds_unknown_types_versions_and_properties():
    findings = toolkit().linter.lint(stack(
        {"type": "Microsoft.Nope/things", "apiVersion": "2024-01-01", "name": "a", "comments": "a"},
        {"type": STORAGE, "apiVersion": "1999-01-01", "name": "b", "comments": "b", "location": "l", "kind": "StorageV2",
         "sku": {"name": "Standard_ZRS"}, "properties": {"allowSharedKeyAccess": False, "allowBlobPublicAccess": False}},
        {"type": "Microsoft.KeyVault/vaults", "apiVersion": "2023-07-01", "name": "c", "comments": "c", "location": "l",
         "properties": {"tenantId": "t", "sku": {"family": "A", "name": "standard"}, "enableRbacAuthorisation": True}}))
    assert findings == ["Microsoft.Nope/things a: unknown resource type.",
                        "Microsoft.Storage/storageAccounts b: unknown API version 1999-01-01.",
                        "Microsoft.KeyVault/vaults c: unknown property 'properties.enableRbacAuthorisation'."]


# ---- raw types (Tier 2) ----

def test_raw_azure_types_are_searchable():
    assert "Microsoft.Cache/redis" in [entry["type"] for entry in toolkit().types.search("microsoft.cache/redis")]


def test_raw_types_take_the_latest_stable_api_version_and_their_properties():
    payload = azure_request(resources=[{"id": "cache", "type": "Microsoft.Cache/redis",
                                        "config": {"properties": {"sku": {"name": "Basic", "family": "C", "capacity": 0}}}}])
    [cache] = resources(synthesize(payload)["data"], "Microsoft.Cache/redis")
    assert (cache["apiVersion"] >= "2024-11-01", "preview" in cache["apiVersion"], cache["properties"]["sku"]["name"],
            cache["location"]) == (True, False, "Basic", "[parameters('location')]")


@pytest.mark.parametrize("type_name", ["Microsoft.Authorization/policyAssignments",
                                       "Microsoft.ManagedIdentity/userAssignedIdentities",
                                       "Microsoft.Network/virtualNetworks"])
def test_platform_managed_types_cannot_be_requested(type_name):
    payload = azure_request(resources=[{"id": "x", "type": type_name, "config": {"properties": {}}}])
    assert validate(payload) == [f"'{type_name}' for 'x' is managed by the platform and cannot be requested."]


def test_curated_resource_types_point_to_the_curated_service():
    payload = azure_request(resources=[{"id": "raw", "type": STORAGE, "config": {"properties": {}}}])
    assert validate(payload) == [f"Use the curated service 'storage.bucket' instead of '{STORAGE}' for 'raw'."]


def test_unknown_azure_types_are_refused():
    payload = azure_request(resources=[{"id": "x", "type": "Microsoft.Nope/things", "config": {"properties": {}}}])
    assert validate(payload) == ["Unknown resource type 'Microsoft.Nope/things' for 'x'."]


def test_catalog_lists_azure_settings():
    entries = {entry["type"]: entry for entry in toolkit().catalog()}
    assert ([setting["name"] for setting in entries["compute.function"]["settings"]],
            [setting["name"] for setting in entries["database.table"]["settings"]]) == (
        ["runtime", "memory_mb", "max_instances", "function_name"], ["partition_key"])


# ---- the resource-type snapshot ----

def test_the_snapshot_pins_the_curated_api_versions():
    from app.providers.azure.project.schema import AzureResourceTypes

    types = AzureResourceTypes.bundled()
    assert (types.schema(SITES, "2024-04-01")["required"], "2024-04-01" in types.versions("microsoft.web/sites")) == (
        ["location", "name"], True)


def test_the_refresh_reads_the_index_and_the_pinned_types(tmp_path):
    from app.providers.azure.project.refresh import main
    from app.providers.azure.project.schema import AzureResourceTypes, BicepTypesReader

    files = {"index.json": {"resources": {"Microsoft.X/things@2024-01-01": {"$ref": "x/types.json#/1"},
                                          "Microsoft.X/things@2025-01-01-preview": {"$ref": "x/types.json#/1"}}},
             "x/types.json": [{"$type": "StringType"},
                              {"$type": "ResourceType", "name": "Microsoft.X/things@2024-01-01", "body": {"$ref": "#/2"}},
                              {"$type": "ObjectType", "name": "things", "properties": {
                                  "name": {"type": {"$ref": "#/0"}, "flags": 9},
                                  "id": {"type": {"$ref": "#/0"}, "flags": 10},
                                  "properties": {"type": {"$ref": "#/3"}, "flags": 0}}},
                              {"$type": "DiscriminatedObjectType", "discriminator": "kind", "baseProperties": {},
                               "elements": {"a": {"$ref": "#/4"}}},
                              {"$type": "ObjectType", "name": "a", "properties": {"size": {"type": {"$ref": "#/5"}}}},
                              {"$type": "ArrayType", "itemType": {"$ref": "#/6"}},
                              {"$type": "ObjectType", "name": "tags", "additionalProperties": {"$ref": "#/0"}}]}
    main([], BicepTypesReader(files.__getitem__), tmp_path / "types.json.gz", ["Microsoft.X/things@2024-01-01"])
    types = AzureResourceTypes.read(tmp_path / "types.json.gz")
    assert (types.latest_stable("microsoft.x/things"), types.schema("Microsoft.X/things", "2024-01-01")) == (
        "2024-01-01", {"required": ["name"], "properties": {"name": None, "properties": {
            "required": [], "properties": {"kind": None, "size": None}}}})


# ---- more shapes ----

def test_paired_dr_storage_is_fine():
    assert validate(azure_request(resilience=DR)) == []


def test_access_needs_a_level_and_a_workload():
    no_level = azure_request(resources=[{"id": "processor", "type": "compute.function"},
                                        {"id": "jobs", "type": "messaging.queue"}],
                             connections=[{"kind": "iam.access", "source": "processor", "target": "jobs"}])
    from_bucket = azure_request(resources=[{"id": "uploads", "type": "storage.bucket"},
                                           {"id": "jobs", "type": "messaging.queue"}],
                                connections=[{"kind": "access.grant", "source": "uploads", "target": "jobs",
                                              "access": "read"}])
    assert (validate(no_level), validate(from_bucket)) == (
        ["iam.access from 'processor' to 'jobs' needs an access level."],
        ["access.grant cannot connect storage.bucket to messaging.queue."])


def test_two_functions_share_the_code_account_and_a_bucket_topic():
    document = synthesize(azure_request(
        resources=[{"id": "uploads", "type": "storage.bucket"}, {"id": "first", "type": "compute.function"},
                   {"id": "second", "type": "compute.function"}],
        connections=[{"kind": "event.notify", "source": "uploads", "target": name} for name in ("first", "second")]))
    assert (len(resources(document["data"], STORAGE, "code")),
            len(resources(document["data"], "Microsoft.EventGrid/systemTopics")),
            len(resources(document["app"], "Microsoft.EventGrid/systemTopics/eventSubscriptions"))) == (1, 1, 2)


def test_attached_data_stores_get_private_endpoints():
    payload = azure_request(resources=[{"id": "processor", "type": "compute.function"},
                                       {"id": "orders", "type": "database.table"}, {"id": "jobs", "type": "messaging.queue"}],
                            resilience=DR, attach=True)
    endpoints = resources(synthesize(payload)["data"], "Microsoft.Network/privateEndpoints")
    assert sorted(endpoint["comments"] for endpoint in endpoints) == ["jobs", "orders"]


def test_raw_types_without_properties():
    [cache] = resources(synthesize(azure_request(resources=[{"id": "cache", "type": "Microsoft.Cache/redis"}]))["data"],
                        "Microsoft.Cache/redis")
    assert "properties" not in cache


@pytest.mark.parametrize("config, message", [
    ({"properties": []}, "Microsoft.Cache/redis 'cache' properties must be a JSON object."),
    ({"properties": {}, "extra": 1}, "Microsoft.Cache/redis 'cache' accepts only 'properties' in config, not 'extra'."),
])
def test_raw_type_config_is_checked(config, message):
    assert validate(azure_request(resources=[{"id": "cache", "type": "Microsoft.Cache/redis", "config": config}])) == [
        message]


def test_lint_finds_functions_without_their_own_identity_and_missing_properties():
    findings = toolkit().linter.lint(stack(
        {"type": SITES, "apiVersion": "2024-04-01", "name": "f", "comments": "f", "location": "l", "kind": "functionapp"},
        {"type": "Microsoft.KeyVault/vaults", "apiVersion": "2023-07-01", "name": "v", "comments": "v", "location": "l",
         "properties": {"sku": {"family": "A", "name": "standard"}}}))
    assert findings == ["Microsoft.Web/sites f: function app has no identity of its own.",
                        "Microsoft.KeyVault/vaults v: missing required property 'properties.tenantId'."]


def test_the_trimmer_stops_at_its_depth_and_reuses_shared_types():
    from app.providers.azure.project.schema import MAX_DEPTH, Trimmer

    nodes = [{"$type": "ObjectType", "name": "node", "properties": {"a": {"type": {"$ref": "#/0"}},
                                                                    "b": {"type": {"$ref": "#/0"}}}}]
    tree = Trimmer(nodes).resource({"body": {"$ref": "#/0"}})
    for _ in range(MAX_DEPTH - 1):
        assert tree["properties"]["a"] is tree["properties"]["b"]
        tree = tree["properties"]["a"]
    assert tree["properties"]["a"] is None


def test_the_refresh_fetches_from_the_type_repository(monkeypatch):
    from app.providers.azure.project import refresh

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *details):
            return False

        def read(self):
            return b'{"resources": {}}'

    seen = []
    monkeypatch.setattr(refresh.urllib.request, "urlopen", lambda url, timeout: seen.append((url, timeout)) or Response())
    refresh.fetch.cache_clear()
    assert (refresh.fetch("index.json"), seen) == ({"resources": {}}, [(refresh.SOURCE + "index.json", 60)])


def test_types_at_unpinned_versions_are_checked_for_type_and_version_only():
    assert toolkit().linter.lint(stack({"type": "Microsoft.Cache/redis", "apiVersion": "2024-11-01", "name": "c",
                                        "comments": "c", "location": "l", "anything": True})) == []
