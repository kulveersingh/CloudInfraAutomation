import gzip
import json

import pytest
from app.providers.gcp.project.lint import gcp_linter
from app.providers.gcp.project.schema import GoogleProviderSchema

from app.providers.gcp.provider import GcpProvider
from app.synth.request import ProjectRequest
from app.synth.validation import RequestValidationError
from tests.gcp_helpers import DR, HA, gcp_request, members, resource, synthesize

BUCKET_NAME = "${var.project_name}-uploads-${substr(sha1(var.project_id), 0, 8)}"
PROCESSOR_SA = "serviceAccount:processor-d9d811df@${var.project_id}.iam.gserviceaccount.com"


def toolkit():
    return GcpProvider().project()


def validate(payload: dict) -> list[str]:
    try:
        toolkit().validator.validate(ProjectRequest.model_validate(payload))
    except RequestValidationError as error:
        return error.messages
    return []


# ---- the document ----

def test_document_pins_terraform_for_infrastructure_manager_and_the_google_provider():
    terraform = synthesize(gcp_request())["terraform"]
    assert terraform == {"required_version": ">= 1.5.0, < 1.6.0", "required_providers": {
        "google": {"source": "hashicorp/google", "version": ">= 7.21.0"}}}


def test_provider_targets_the_environment_project_and_region_with_labels():
    assert synthesize(gcp_request())["provider"]["google"] == {
        "project": "${var.project_id}", "region": "${var.region}", "default_labels": "${local.labels}"}


def test_ownership_tags_become_valid_labels():
    labels = synthesize(gcp_request())["locals"]["labels"]
    assert (labels["org_project"], labels["org_cost_center"], labels["managed_by"]) == (
        "${var.project_name}", '${lower(replace(var.org_cost_center, "/[^a-zA-Z0-9_-]/", "-"))}', "cloudinfra")


def test_generator_is_recorded():
    assert synthesize(gcp_request())["locals"]["generator"] == {"name": "cloudinfra-synth", "version": "0.1.0"}


def test_variables_cover_project_environment_and_region_role():
    variables = synthesize(gcp_request())["variable"]
    assert ({"project_id", "project_name", "environment_name", "region", "region_role", "activation_state",
             "code_bucket", "code_object"} <= set(variables), variables["region_role"]["default"]) == (True, "primary")


def test_generation_is_deterministic():
    assert json.dumps(synthesize(gcp_request())) == json.dumps(synthesize(gcp_request()))


# ---- storage.bucket ----

def test_bucket_is_locked_down_and_versioned():
    bucket = resource(synthesize(gcp_request()), "google_storage_bucket", "uploads")
    assert (bucket["name"], bucket["location"], bucket["uniform_bucket_level_access"], bucket["public_access_prevention"],
            bucket["versioning"], bucket["force_destroy"]) == (
        BUCKET_NAME, "${var.region}", True, "enforced", {"enabled": True}, False)


def test_bucket_expires_old_versions_and_abandoned_uploads():
    rules = resource(synthesize(gcp_request()), "google_storage_bucket", "uploads")["lifecycle_rule"]
    assert rules == [{"condition": {"days_since_noncurrent_time": 30}, "action": {"type": "Delete"}},
                     {"condition": {"age": 7}, "action": {"type": "AbortIncompleteMultipartUpload"}}]


def test_dr_bucket_is_one_dual_region_bucket_created_by_the_primary_deployment():
    bucket = resource(synthesize(gcp_request(resilience=DR)), "google_storage_bucket", "uploads")
    assert (bucket["location"], bucket["custom_placement_config"], bucket["count"], "rpo" in bucket) == (
        "US", {"data_locations": ["US-EAST1", "US-EAST4"]}, "${local.is_primary ? 1 : 0}", False)


def test_ha_bucket_uses_turbo_replication():
    assert resource(synthesize(gcp_request(resilience=HA)), "google_storage_bucket", "uploads")["rpo"] == "ASYNC_TURBO"


def test_dual_region_needs_one_continent():
    payload = gcp_request(resilience={"mode": "dr", "primary_region": "us-east1", "secondary_region": "europe-west1"})
    assert validate(payload) == [
        "Google Cloud dual- and multi-region storage needs both regions on one continent (us-east1, europe-west1)."]


# ---- compute.function ----

def test_function_runs_as_its_own_service_account():
    document = synthesize(gcp_request())
    account = resource(document, "google_service_account", "processor")
    function = resource(document, "google_cloudfunctions2_function", "processor")
    assert (account["account_id"], function["service_config"]["service_account_email"]) == (
        "processor-d9d811df", "processor-d9d811df@${var.project_id}.iam.gserviceaccount.com")


def test_function_defaults():
    function = resource(synthesize(gcp_request()), "google_cloudfunctions2_function", "processor")
    build, service = function["build_config"], function["service_config"]
    assert (function["name"], function["location"], build["runtime"], build["entry_point"],
            build["source"]["storage_source"], service["available_memory"], service["timeout_seconds"],
            service["ingress_settings"]) == (
        "invoice-ingest--processor", "${var.region}", "python313", "main",
        {"bucket": "${var.code_bucket}", "object": "${var.code_object}"}, "256M", 60, "ALLOW_INTERNAL_ONLY")


def test_function_settings_reach_the_function():
    payload = gcp_request(resources=[{"id": "processor", "type": "compute.function", "config": {
        "runtime": "go125", "entry_point": "Handle", "memory_mb": 1024, "timeout_sec": 300}}])
    function = resource(synthesize(payload), "google_cloudfunctions2_function", "processor")
    assert (function["build_config"]["runtime"], function["build_config"]["entry_point"],
            function["service_config"]["available_memory"], function["service_config"]["timeout_seconds"]) == (
        "go125", "Handle", "1024M", 300)


def test_function_joins_the_shared_vpc_with_direct_vpc_egress():
    service = resource(synthesize(gcp_request(attach=True)), "google_cloudfunctions2_function",
                       "processor")["service_config"]
    assert (service["direct_vpc_network_interface"], service["direct_vpc_egress"]) == (
        {"network": "${var.network}", "subnetwork": "${var.subnetwork}", "tags": "${var.network_tags}"},
        "VPC_EGRESS_PRIVATE_RANGES_ONLY")


def test_dr_service_account_is_created_once():
    account = resource(synthesize(gcp_request(resilience=DR)), "google_service_account", "processor")
    assert account["count"] == "${local.is_primary ? 1 : 0}"


def test_functions_deploy_in_every_region():
    function = resource(synthesize(gcp_request(resilience=DR)), "google_cloudfunctions2_function", "processor")
    assert "count" not in function


# ---- database.table ----

def test_firestore_database_is_kept_when_removed_and_protected_in_production():
    database = resource(synthesize(gcp_request(resources=[{"id": "orders", "type": "database.table"}])),
                        "google_firestore_database", "orders")
    assert (database["name"], database["location_id"], database["type"], database["deletion_policy"],
            database["point_in_time_recovery_enablement"], database["delete_protection_state"]) == (
        "invoice-ingest-orders", "${var.region}", "FIRESTORE_NATIVE", "ABANDON", "POINT_IN_TIME_RECOVERY_ENABLED",
        ('${contains(["stage", "prod"], var.environment_name) ? "DELETE_PROTECTION_ENABLED" : '
         '"DELETE_PROTECTION_DISABLED"}'))


@pytest.mark.parametrize("resilience, location", [
    (DR, "nam5"), ({"mode": "ha", "primary_region": "europe-west1", "secondary_region": "europe-west4"}, "eur3")])
def test_multi_region_firestore(resilience, location):
    payload = gcp_request(resources=[{"id": "orders", "type": "database.table"}], resilience=resilience)
    assert resource(synthesize(payload), "google_firestore_database", "orders")["location_id"] == location


def test_firestore_has_no_key_settings():
    payload = gcp_request(resources=[{"id": "orders", "type": "database.table", "config": {"partition_key": "id"}}])
    assert validate(payload) == ["database.table 'orders' does not accept 'partition_key'; it has no settings."]


# ---- messaging.queue ----

def test_queue_is_a_topic_with_a_pull_subscription_and_dead_letters():
    document = synthesize(gcp_request(resources=[{"id": "jobs", "type": "messaging.queue"}]))
    subscription = resource(document, "google_pubsub_subscription", "jobs")
    assert (resource(document, "google_pubsub_topic", "jobs")["name"], subscription["topic"],
            subscription["dead_letter_policy"], subscription["enable_exactly_once_delivery"],
            subscription["message_retention_duration"]) == (
        "invoice-ingest--jobs", "${google_pubsub_topic.jobs.id}",
        {"dead_letter_topic": "${google_pubsub_topic.jobs-dead.id}", "max_delivery_attempts": 5}, True, "604800s")


# ---- access.grant: exact-resource bindings to the function's own service account ----

def grants(target: dict, access: str, prefix: str = "") -> dict:
    payload = gcp_request(resources=[{"id": "processor", "type": "compute.function"}, target],
                          connections=[{"kind": "access.grant", "source": "processor", "target": target["id"],
                                        "access": access, "prefix": prefix}])
    return synthesize(payload)


@pytest.mark.parametrize("access, role", [("read", "roles/storage.objectViewer"),
                                          ("write", "roles/storage.objectCreator"),
                                          ("readwrite", "roles/storage.objectUser")])
def test_bucket_access_is_bound_on_the_bucket(access, role):
    [member] = members(grants({"id": "uploads", "type": "storage.bucket"}, access), "google_storage_bucket_iam_member")
    assert (member["bucket"], member["role"], member["member"]) == (BUCKET_NAME, role, PROCESSOR_SA)


def test_bucket_access_to_a_prefix_is_conditioned():
    [member] = members(grants({"id": "uploads", "type": "storage.bucket"}, "read", "reports/"),
                       "google_storage_bucket_iam_member")
    assert member["condition"]["expression"] == (
        f'resource.name.startsWith("projects/_/buckets/{BUCKET_NAME}/objects/reports/")')


def test_firestore_access_is_conditioned_on_the_database():
    [member] = members(grants({"id": "orders", "type": "database.table"}, "readwrite"), "google_project_iam_member")
    assert (member["role"], member["condition"]["expression"]) == (
        "roles/datastore.user", 'resource.name.startsWith("projects/${var.project_id}/databases/invoice-ingest-orders")')


def test_queue_write_publishes_and_read_subscribes():
    document = grants({"id": "jobs", "type": "messaging.queue"}, "readwrite")
    assert ([member["role"] for member in members(document, "google_pubsub_topic_iam_member")],
            [member["role"] for member in members(document, "google_pubsub_subscription_iam_member")]) == (
        ["roles/pubsub.publisher"], ["roles/pubsub.subscriber"])


def test_access_puts_the_target_name_in_the_environment():
    variables = resource(grants({"id": "jobs", "type": "messaging.queue"}, "read"), "google_cloudfunctions2_function",
                         "processor")["service_config"]["environment_variables"]
    assert (variables["JOBS_TOPIC"], variables["JOBS_SUBSCRIPTION"]) == ("invoice-ingest--jobs", "invoice-ingest--jobs")


# ---- event.notify: an Eventarc trigger; the function filters the prefix ----

def test_bucket_events_trigger_the_function_while_active():
    trigger = resource(synthesize(gcp_request()), "google_cloudfunctions2_function", "processor")["dynamic"][
        "event_trigger"]
    assert (trigger["for_each"], trigger["content"]["event_type"], trigger["content"]["event_filters"],
            trigger["content"]["trigger_region"]) == (
        "${local.is_active ? [1] : []}", "google.cloud.storage.object.v1.finalized",
        {"attribute": "bucket", "value": BUCKET_NAME}, "${var.region}")


def test_the_function_gets_the_prefix_to_filter():
    variables = resource(synthesize(gcp_request()), "google_cloudfunctions2_function", "processor")[
        "service_config"]["environment_variables"]
    assert (variables["CLOUDINFRA_EVENT_PREFIX"], variables["UPLOADS_BUCKET"]) == ("incoming/", BUCKET_NAME)


def test_the_function_can_read_what_triggers_it():
    roles = [member["role"] for member in members(synthesize(gcp_request()), "google_storage_bucket_iam_member")]
    assert roles == ["roles/storage.objectViewer"]


def test_the_storage_service_agent_may_publish_events():
    publisher = resource(synthesize(gcp_request()), "google_project_iam_member", "gcs-events-publisher")
    assert (publisher["role"], publisher["member"]) == (
        "roles/pubsub.publisher", "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}")


def test_prefix_filtering_is_explained():
    assert toolkit().notes(ProjectRequest.model_validate(gcp_request())) == [
        "uploads → processor: Eventarc cannot filter by object prefix, so processor must check CLOUDINFRA_EVENT_PREFIX."]


# ---- contract ----

def test_contract_is_published_in_secret_manager():
    document = synthesize(gcp_request())
    secret = resource(document, "google_secret_manager_secret", "contract")
    contract = json.loads(resource(document, "google_secret_manager_secret_version", "contract")["secret_data"])
    assert (secret["secret_id"], contract["resources"]["uploads"]["type"], contract["environment"]) == (
        "invoice-ingest-contract", "storage.bucket", "${var.environment_name}")


# ---- lint ----

def test_generated_documents_have_no_lint_findings():
    for payload in (gcp_request(), gcp_request(resilience=DR, attach=True),
                    gcp_request(resources=[{"id": "processor", "type": "compute.function"},
                                           {"id": "orders", "type": "database.table"},
                                           {"id": "jobs", "type": "messaging.queue"}],
                                connections=[{"kind": "access.grant", "source": "processor", "target": "orders",
                                              "access": "readwrite"},
                                             {"kind": "access.grant", "source": "processor", "target": "jobs",
                                              "access": "read"}])):
        assert gcp_linter().lint(synthesize(payload)) == []


@pytest.mark.parametrize("change, finding", [
    ({"google_project_iam_member": {"x": {"project": "p", "role": "roles/editor", "member": "user:a@b.c"}}},
     "google_project_iam_member.x: primitive role 'roles/editor'."),
    ({"google_storage_bucket_iam_member": {"x": {"bucket": "b", "role": "roles/storage.objectViewer",
                                                  "member": "allUsers"}}},
     "google_storage_bucket_iam_member.x: public member 'allUsers'."),
    ({"google_storage_bucket": {"x": {"name": "b", "location": "US"}}},
     "google_storage_bucket.x: public access prevention is not enforced."),
    ({"google_project_iam_member": {"x": {"project": "p", "role": "roles/datastore.user",
                                           "member": "serviceAccount:f@${var.project_id}.iam.gserviceaccount.com"}}},
     "google_project_iam_member.x: project-wide role 'roles/datastore.user' for a workload without a condition."),
])
def test_lint_findings(change, finding):
    assert gcp_linter().lint({"resource": change}) == [finding]


def test_schema_check_finds_unknown_and_missing_arguments():
    document = {"resource": {"google_pubsub_topic": {"x": {"nme": "t"}}}}
    assert gcp_linter().lint(document) == [
        "google_pubsub_topic.x: unknown argument 'nme'.", "google_pubsub_topic.x: missing required argument 'name'."]


def test_schema_check_knows_nested_blocks_and_meta_arguments():
    document = {"resource": {"google_cloudfunctions2_function": {"x": {
        "name": "f", "location": "us-east1", "count": 1, "service_config": {"timeot_seconds": 1}}}}}
    assert gcp_linter().lint(document) == ["google_cloudfunctions2_function.x: unknown argument 'service_config.timeot_seconds'."]


# ---- raw types (Tier 2) ----

def test_raw_google_types_are_searchable():
    found = toolkit().types.search("pubsub_schema")
    assert [entry["type"] for entry in found] == ["google_pubsub_schema"]


def test_raw_types_list_their_required_arguments():
    [entry] = toolkit().types.search("google_pubsub_topic_iam_binding")
    assert (entry["service"], entry["required"]) == ("pubsub", ["members", "role", "topic"])


def test_raw_type_passes_its_properties_through():
    payload = gcp_request(resources=[{"id": "schema", "type": "google_pubsub_schema",
                                      "config": {"properties": {"name": "orders", "type": "AVRO"}}}])
    assert resource(synthesize(payload), "google_pubsub_schema", "schema") == {"name": "orders", "type": "AVRO"}


def test_raw_type_needs_its_required_arguments():
    payload = gcp_request(resources=[{"id": "schema", "type": "google_pubsub_schema", "config": {"properties": {}}}])
    assert validate(payload) == ["google_pubsub_schema 'schema' needs property 'name'."]


@pytest.mark.parametrize("type_name", ["google_project_iam_member", "google_organization_policy",
                                       "google_service_account", "google_folder"])
def test_platform_managed_types_cannot_be_requested(type_name):
    payload = gcp_request(resources=[{"id": "x", "type": type_name, "config": {"properties": {}}}])
    assert validate(payload) == [f"'{type_name}' for 'x' is managed by the platform and cannot be requested."]


def test_curated_resource_types_point_to_the_curated_service():
    payload = gcp_request(resources=[{"id": "raw", "type": "google_storage_bucket", "config": {"properties": {}}}])
    assert validate(payload) == ["Use the curated service 'storage.bucket' instead of 'google_storage_bucket' for 'raw'."]


def test_catalog_lists_the_neutral_kinds_with_google_cloud_settings():
    entries = {entry["type"]: entry for entry in toolkit().catalog()}
    assert ([setting["name"] for setting in entries["compute.function"]["settings"]], entries["database.table"]["settings"]) == (
        ["runtime", "entry_point", "memory_mb", "timeout_sec"], [])


# ---- the schema snapshot ----

def test_snapshot_is_a_recent_google_provider():
    schema = GoogleProviderSchema.bundled()
    assert (schema.version >= "7.21.0", schema.has("google_cloudfunctions2_function")) == (True, True)


def test_snapshot_is_written_from_terraform_output(tmp_path):
    terraform_output = {"provider_schemas": {"registry.terraform.io/hashicorp/google": {"resource_schemas": {
        "google_x": {"block": {"attributes": {"name": {"type": "string", "required": True},
                                              "id": {"type": "string", "computed": True}},
                               "block_types": {"spec": {"nesting_mode": "list", "min_items": 1,
                                                        "block": {"attributes": {"size": {"optional": True}}}}}}}}}}}
    path = tmp_path / "schema.json.gz"
    GoogleProviderSchema.from_terraform(terraform_output, "9.9.9").write(path)
    assert json.loads(gzip.decompress(path.read_bytes()))["resources"]["google_x"] == {
        "arguments": ["name"], "required": ["name"],
        "blocks": {"spec": {"arguments": ["size"], "required": [], "min_items": 1}}}
