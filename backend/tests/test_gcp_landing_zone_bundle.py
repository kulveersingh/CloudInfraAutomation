"""The Google Cloud landing-zone repository (§22.10.5, MC-3c): Infrastructure Manager deployments in Terraform JSON,
the inputs, the one-time seed script, the workflow and the README."""

import ipaddress
import json

import pytest

from app.landing_zone.catalog.templates import TemplateRegistry
from app.providers.gcp.project.lint import gcp_linter
from tests.lz_factories import CATALOG, account_op, add_ou
from tests.test_gcp_landing_zone import design, pid

DEPLOYMENTS = ["lz-foundation", "lz-structure", "lz-projects", "lz-network", "lz-security", "lz-vault"]
TEMPLATES = [template.id for template in TemplateRegistry.default().all()]


def files(edits=(), **overrides) -> dict[str, str]:
    from app.providers.gcp.provider import GcpProvider

    return GcpProvider().landing_zone().bundle.render(design(edits, **overrides), CATALOG)


def deployment(name: str, edits=(), **overrides) -> dict:
    rendered = files(edits, **overrides)
    return {**json.loads(rendered[f"deployments/{name}/main.tf.json"]),
            **json.loads(rendered[f"deployments/{name}/variables.tf.json"])}


def resources(document: dict, type_name: str) -> dict:
    return document["resource"].get(type_name, {})


# ---- the repository ----

def test_the_repository_holds_every_deployment_and_its_tooling():
    rendered = set(files())
    expected = {f"deployments/{name}/{file}" for name in DEPLOYMENTS for file in ("main.tf.json", "variables.tf.json")}
    assert expected | {"config/landing-zone.tfvars", "scripts/bootstrap-seed.sh", ".github/workflows/apply.yml",
                       "README.md", "design.json", "docs/controls.md"} <= rendered


def test_inputs_come_from_the_provider_answers():
    assert files()["config/landing-zone.tfvars"] == (
        'organization_id = "123456789012"\nbilling_account = "01ABCD-23EF45-67GH89"\n'
        'seed_project = "acme-lz-seed"\nregion = "us-east1"\n')


def test_every_deployment_declares_the_inputs_and_works_at_organization_level():
    document = deployment("lz-structure")
    assert (set(document["variable"]) >= {"organization_id", "billing_account", "seed_project", "region"},
            document["provider"]["google"]) == (True, {"billing_project": "${var.seed_project}",
                                                       "user_project_override": True, "region": "${var.region}"})


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_templates_deployments_pass_the_lint_and_schema_checks(template):
    chosen = TemplateRegistry.default().get(template)
    rendered = files(chosen.edits, **chosen.answers_for("gcp"))
    findings = {name: gcp_linter().lint(json.loads(rendered[f"deployments/{name}/main.tf.json"]))
                for name in DEPLOYMENTS}
    assert findings == {name: [] for name in DEPLOYMENTS}


# ---- lz-foundation ----

def test_foundation_creates_the_environment_tag_and_a_value_per_environment():
    document = deployment("lz-foundation")
    assert (resources(document, "google_tags_tag_key")["environment"]["parent"],
            sorted(resources(document, "google_tags_tag_value"))) == (
        "organizations/${var.organization_id}", ["dev", "prod", "sandbox", "stage", "test"])


def test_custom_constraints_are_defined_once_at_the_organization():
    constraint = resources(deployment("lz-foundation", controls_profile="regulated"),
                           "google_org_policy_custom_constraint")["cloudinfraSqlRequireSsl"]
    assert (constraint["name"], constraint["resource_types"], constraint["action_type"]) == (
        "custom.cloudinfraSqlRequireSsl", ["sqladmin.googleapis.com/Instance"], "ALLOW")


def test_security_admins_are_the_essential_contact():
    contact = resources(deployment("lz-foundation"), "google_essential_contacts_contact")["security"]
    assert contact["email"] == "gcp-security-admins@acme.example"


# ---- lz-structure ----

def test_folders_nest_under_their_parents():
    folders = resources(deployment("lz-structure", [add_ou("Payments")]), "google_folder")
    assert (folders["prod"]["parent"], folders["custom_payments"]["parent"], folders["prod"]["deletion_protection"]) == (
        "organizations/${var.organization_id}", "${google_folder.prod.name}", True)


def test_environment_folders_carry_their_environment_tag():
    binding = resources(deployment("lz-structure"), "google_tags_tag_binding")["prod"]
    assert binding == {"parent": "//cloudresourcemanager.googleapis.com/${google_folder.prod.name}",
                       "tag_value": "${data.google_tags_tag_value.prod.id}"}


def test_preventive_controls_are_org_policies_on_folders():
    policy = resources(deployment("lz-structure"), "google_org_policy_policy")["prod-iam-disableServiceAccountKeyCreation"]
    assert policy == {"name": "${google_folder.prod.name}/policies/iam.disableServiceAccountKeyCreation",
                      "parent": "${google_folder.prod.name}", "spec": {"rules": [{"enforce": "TRUE"}]}}


def test_resource_locations_allow_the_governed_regions():
    policy = resources(deployment("lz-structure", control_packs=["data-residency"]),
                       "google_org_policy_policy")["prod-gcp-resourceLocations"]
    assert policy["spec"]["rules"] == [{"values": {"allowed_values": ["in:us-east1-locations",
                                                                      "in:us-east4-locations"]}}]


def test_member_domains_are_the_organizations_directory():
    policy = resources(deployment("lz-structure"), "google_org_policy_policy")["prod-iam-allowedPolicyMemberDomains"]
    assert policy["spec"]["rules"] == [
        {"values": {"allowed_values": ["${data.google_organization.organization.directory_customer_id}"]}}]


def test_iam_deny_protects_logs_except_for_the_security_admins():
    document = deployment("lz-structure", controls_profile="regulated")
    policy = resources(document, "google_iam_deny_policy")["protect-logging-prod"]
    rule = policy["rules"][0]["deny_rule"]
    assert (policy["parent"], rule["denied_principals"], rule["exception_principals"],
            "logging.googleapis.com/sinks.delete" in rule["denied_permissions"]) == (
        '${urlencode("cloudresourcemanager.googleapis.com/${google_folder.prod.name}")}',
        ["principalSet://goog/public:all"], ["principalSet://goog/group/gcp-security-admins@acme.example"], True)


def test_environment_folders_block_ssh_and_rdp_from_the_internet():
    document = deployment("lz-structure")
    rule = resources(document, "google_compute_firewall_policy_rule")["prod-deny-admin-ports"]
    assert (rule["action"], rule["match"]["src_ip_ranges"], rule["match"]["layer4_configs"],
            resources(document, "google_compute_firewall_policy_association")["prod"]["attachment_target"]) == (
        "deny", ["0.0.0.0/0"], [{"ip_protocol": "tcp", "ports": ["22", "3389"]}], "${google_folder.prod.name}")


# ---- lz-projects ----

def test_every_enabled_unit_is_a_project_in_its_folder():
    document = deployment("lz-projects")
    project = resources(document, "google_project")[pid("acme-payments-prod")]
    assert (project["project_id"], project["folder_id"], project["billing_account"], project["auto_create_network"],
            project["deletion_policy"], document["data"]["google_active_folder"]["prod"]["display_name"]) == (
        pid("acme-payments-prod"), '${trimprefix(data.google_active_folder.prod.name, "folders/")}',
        "${var.billing_account}", False, "PREVENT", "PROD")


def test_disabled_units_are_not_created():
    edits = [account_op("disable_account", pid("acme-retail-prod"))]
    assert pid("acme-retail-prod") not in resources(deployment("lz-projects", edits), "google_project")


def test_nested_folders_are_found_through_their_parents():
    folders = deployment("lz-projects", [add_ou("Payments")])["data"]["google_active_folder"]
    assert folders["custom_payments"]["parent"] == "${data.google_active_folder.prod.name}"


def test_host_projects_enable_network_connectivity():
    services = resources(deployment("lz-projects"), "google_project_service")
    assert services[f"{pid('acme-net-prod')}-networkconnectivity"]["service"] == "networkconnectivity.googleapis.com"


def test_sandbox_projects_have_a_budget():
    budget = resources(deployment("lz-projects"), "google_billing_budget")[pid("acme-payments-sandbox")]
    assert (budget["amount"], budget["budget_filter"]["projects"]) == (
        {"specified_amount": {"currency_code": "USD", "units": "500"}},
        [f"projects/${{google_project.{pid('acme-payments-sandbox')}.number}}"])


# ---- lz-network ----

def test_the_hub_is_the_center_of_a_star():
    document = deployment("lz-network")
    hub = resources(document, "google_network_connectivity_hub")["hub"]
    spokes = resources(document, "google_network_connectivity_spoke")
    assert (hub["preset_topology"], hub["project"], spokes["hub"]["group"], spokes["prod"]["group"]) == (
        "STAR", pid("acme-net-hub"), "${google_network_connectivity_hub.hub.id}/groups/center",
        "${google_network_connectivity_hub.hub.id}/groups/edge")


def test_each_environment_has_a_shared_vpc_with_its_own_ranges():
    subnets = resources(deployment("lz-network"), "google_compute_subnetwork")
    ranges = [ipaddress.ip_network(subnet["ip_cidr_range"]) for subnet in subnets.values()]
    assert (subnets["prod-us-east1"]["project"], subnets["prod-us-east1"]["private_ip_google_access"],
            any(first.overlaps(second) for index, first in enumerate(ranges) for second in ranges[index + 1:])) == (
        pid("acme-net-prod"), True, False)


def test_workload_projects_attach_to_their_environments_host():
    attachment = resources(deployment("lz-network"), "google_compute_shared_vpc_service_project")[
        pid("acme-payments-prod")]
    assert (attachment["host_project"], attachment["depends_on"]) == (
        pid("acme-net-prod"), ["google_compute_shared_vpc_host_project.prod"])


def test_each_environment_region_has_cloud_nat():
    nat = resources(deployment("lz-network"), "google_compute_router_nat")["prod-us-east4"]
    assert (nat["region"], nat["source_subnetwork_ip_ranges_to_nat"]) == ("us-east4", "ALL_SUBNETWORKS_ALL_IP_RANGES")


def test_compliance_environments_have_their_own_host():
    assert "pci_prod" in resources(deployment("lz-network", compliance=["PCI"]), "google_compute_shared_vpc_host_project")


def test_a_vpn_link_gets_an_ha_vpn_gateway_on_the_hub():
    gateways = resources(deployment("lz-network", network={"on_premises": "vpn"}), "google_compute_ha_vpn_gateway")
    assert gateways["hub"]["network"] == "${google_compute_network.hub.id}"


def test_inspection_adds_firewall_endpoints_on_the_hub():
    document = deployment("lz-network", network={"inspection": True, "egress": "local"})
    endpoint = resources(document, "google_network_security_firewall_endpoint")["us-east1"]
    assert (endpoint["parent"], endpoint["location"]) == ("organizations/${var.organization_id}", "us-east1-b")


def test_declared_flows_are_private_service_connect_endpoints():
    flow = {"source": "dev", "destination": "stage", "port": 443, "reason": "Payments API"}
    document = deployment("lz-network", network={"flows": [flow]})
    rule = resources(document, "google_compute_forwarding_rule")["flow-1"]
    assert (rule["count"], rule["target"], rule["network"], document["variable"]["flow_1_service_attachment"]) == (
        '${var.flow_1_service_attachment == "" ? 0 : 1}', "${var.flow_1_service_attachment}",
        "${google_compute_network.dev.id}", {"type": "string", "default": "",
                                             "description": "dev → stage on tcp/443: Payments API"})


# ---- lz-security ----

def test_organization_logs_go_to_a_locked_bucket():
    document = deployment("lz-security")
    sink = resources(document, "google_logging_organization_sink")["audit"]
    bucket = resources(document, "google_logging_project_bucket_config")["audit"]
    assert (sink["include_children"], bucket["project"], bucket["locked"], bucket["retention_days"]) == (
        True, pid("acme-logging"), True, 365)


def test_each_environment_is_a_dry_run_service_perimeter():
    perimeter = resources(deployment("lz-security"), "google_access_context_manager_service_perimeter")["prod"]
    assert (perimeter["use_explicit_dry_run_spec"], "status" in perimeter,
            f"projects/${{data.google_project.{pid('acme-payments-prod')}.number}}" in perimeter["spec"]["resources"],
            "storage.googleapis.com" in perimeter["spec"]["restricted_services"]) == (True, False, True, True)


def test_detective_controls_are_posture_deployments_on_premium():
    document = deployment("lz-security")
    posture = resources(document, "google_securityposture_posture")["prod"]
    modules = [policy["constraint"]["security_health_analytics_module"]["module_name"]
               for policy in posture["policy_sets"][0]["policies"]]
    target = resources(document, "google_securityposture_posture_deployment")["prod"]["target_resource"]
    assert ("MFA_NOT_ENFORCED" in modules, target) == (True, "${data.google_active_folder.prod.name}")


def test_standard_security_command_center_deploys_no_postures():
    assert resources(deployment("lz-security", provider_answers={"scc_tier": "standard"}),
                     "google_securityposture_posture") == {}


# ---- lz-vault ----

def test_the_vault_keeps_teardown_backups_locked_for_sixty_days():
    document = deployment("lz-vault")
    bucket = resources(document, "google_storage_bucket")["us-east4"]
    vault = resources(document, "google_backup_dr_backup_vault")["us-east4"]
    assert (bucket["name"], bucket["retention_policy"], bucket["project"],
            vault["backup_minimum_enforced_retention_duration"], document["output"]["vault_project"]["value"]) == (
        f"cloudinfra-teardown-us-east4-{pid('acme-vault')}", {"retention_period": 5184000, "is_locked": True},
        pid("acme-vault"), "5184000s", pid("acme-vault"))


def test_only_backup_super_users_escape_the_vault_deny_policy():
    rule = resources(deployment("lz-vault"), "google_iam_deny_policy")["vault"]["rules"][0]["deny_rule"]
    assert (rule["exception_principals"], "storage.googleapis.com/buckets.delete" in rule["denied_permissions"]) == (
        ["principalSet://goog/group/gcp-backup-super-users@acme.example"], True)


# ---- seed, workflow, README ----

def test_the_seed_script_creates_the_seed_project_and_its_identity():
    script = files()["scripts/bootstrap-seed.sh"]
    assert ('gcloud projects create "acme-lz-seed" --organization="123456789012"' in script,
            "roles/resourcemanager.folderAdmin" in script, "workload-identity-pools create" in script,
            "assertion.repository" in script) == (True, True, True, True)


def test_the_workflow_previews_then_applies_the_deployments_in_order():
    workflow = files()[".github/workflows/apply.yml"]
    positions = [workflow.index(f"deployments/{name}") for name in DEPLOYMENTS]
    assert (positions == sorted(positions), "gcloud infra-manager previews create" in workflow,
            "terraform validate" in workflow, "--inputs-file=config/landing-zone.tfvars" in workflow) == (
        True, True, True, True)


def test_the_readme_lists_the_deployments_and_what_is_left_to_a_person():
    readme = files(network={"on_premises": "dedicated"})["README.md"]
    assert (all(name in readme for name in DEPLOYMENTS), "Cloud Interconnect" in readme,
            "scripts/bootstrap-seed.sh" in readme) == (True, True, True)


# ---- checks that come with the deployments ----

def test_vault_bucket_names_fit_sixty_three_characters():
    from app.providers.gcp.provider import GcpProvider

    built = design(organization_name="acme-holdings-group", governed_regions=["us-east1", "northamerica-northeast1"])
    problems = [problem for check in GcpProvider().landing_zone().checks for problem in check.problems(built, CATALOG)]
    assert any(problem.startswith("Vault bucket 'cloudinfra-teardown-northamerica-northeast1-") for problem in problems)
