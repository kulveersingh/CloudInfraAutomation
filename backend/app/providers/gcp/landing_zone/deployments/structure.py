from app.providers.gcp.landing_zone.deployments.base import (
    ORGANIZATION,
    Deployment,
    FolderReferences,
    group,
    resource_name,
)
from app.providers.gcp.landing_zone.deployments.constraints import DENY_POLICIES, ConstraintRules, policy_name

ADMIN_PORTS = ["22", "3389"]
INTERNET = ["0.0.0.0/0"]


class StructureDeployment(Deployment):
    """Folders with their environment tags, the packs' Org Policy and IAM deny policies, and a firewall policy on
    each environment folder."""

    name = "lz-structure"
    description = "Folders, environment tags, Org Policy and IAM deny policies, folder firewall policies"

    def build(self, context, document):
        folders = FolderReferences(context.design, owned=True)
        environments = context.design.environment_ous()
        self._lookups(document, environments)
        for ou in context.design.walk():
            document.add_resource("google_folder", ou.key, {"display_name": ou.name, "parent": folders.parent(ou),
                                                           "deletion_protection": True})
        for ou in environments:
            document.add_resource("google_tags_tag_binding", ou.key, {
                "parent": f"//cloudresourcemanager.googleapis.com/{folders.name(ou)}",
                "tag_value": f"${{data.google_tags_tag_value.{ou.key}.id}}"})
            self._firewall(document, folders, ou)
        self._org_policies(context, document, folders)
        self._deny_policies(context, document, folders)

    def _lookups(self, document, environments) -> None:
        document.add_data("google_organization", "organization", {"organization": ORGANIZATION})
        document.add_data("google_tags_tag_key", "environment", {"parent": ORGANIZATION, "short_name": "environment"})
        for ou in environments:
            document.add_data("google_tags_tag_value", ou.key, {
                "parent": "${data.google_tags_tag_key.environment.id}", "short_name": ou.key})

    def _org_policies(self, context, document, folders) -> None:
        rules = ConstraintRules(folders.name)
        for ou, enabled in context.placed({"ORG_POLICY", "CUSTOM_CONSTRAINT"}):
            constraint = policy_name(enabled.control.id)
            document.add_resource("google_org_policy_policy", f"{ou.key}-{constraint.replace('.', '-')}", {
                "name": f"{folders.name(ou)}/policies/{constraint}", "parent": folders.name(ou),
                "spec": {"rules": rules.rules(ou, enabled)}})

    def _deny_policies(self, context, document, folders) -> None:
        groups = context.answers.groups.model_dump()
        for ou, enabled in context.placed({"IAM_DENY"}):
            policy = DENY_POLICIES[enabled.control.id]
            name = f"{enabled.control.id.removeprefix('iam-deny/')}-{resource_name(ou.key)}"
            document.add_resource("google_iam_deny_policy", name, {
                "name": name, "display_name": enabled.control.name,
                "parent": f'${{urlencode("cloudresourcemanager.googleapis.com/{folders.name(ou)}")}}',
                "rules": [{"deny_rule": {"denied_principals": ["principalSet://goog/public:all"],
                                         "exception_principals": [group(groups[policy["except"]])],
                                         "denied_permissions": policy["permissions"]}}]})

    def _firewall(self, document, folders, ou) -> None:
        policy = f"${{google_compute_firewall_policy.{ou.key}.id}}"
        document.add_resource("google_compute_firewall_policy", ou.key, {
            "parent": folders.name(ou), "short_name": f"{resource_name(ou.key)}-baseline",
            "description": f"Baseline rules for every network in {ou.name}"})
        document.add_resource("google_compute_firewall_policy_rule", f"{ou.key}-deny-admin-ports", {
            "firewall_policy": policy, "priority": 1000, "direction": "INGRESS", "action": "deny",
            "description": "SSH and RDP are never open to the internet",
            "match": {"src_ip_ranges": INTERNET, "layer4_configs": [{"ip_protocol": "tcp", "ports": ADMIN_PORTS}]}})
        document.add_resource("google_compute_firewall_policy_association", ou.key, {
            "name": f"{resource_name(ou.key)}-baseline", "firewall_policy": policy,
            "attachment_target": folders.name(ou)})
