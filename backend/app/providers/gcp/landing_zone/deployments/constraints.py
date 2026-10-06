"""How each Org Policy constraint is set (§22.10.4): boolean constraints are enforced; list constraints take the
values the design implies. New list constraints add a rule (Open/Closed)."""

from app.landing_zone.catalog.resolver import EnabledControl
from app.landing_zone.design import OuNode

ENFORCED = [{"enforce": "TRUE"}]
CMEK_SERVICES = ["storage.googleapis.com", "sqladmin.googleapis.com", "bigquery.googleapis.com"]


def policy_name(control_id: str) -> str:
    """The constraint's name in a policy: managed constraints drop their "constraints/" prefix."""
    return control_id.removeprefix("constraints/")


class ConstraintRules:
    def __init__(self, folder_name):
        self._folder_name = folder_name
        self._rules = {
            "constraints/gcp.resourceLocations": self._locations,
            "constraints/iam.allowedPolicyMemberDomains": self._member_domains,
            "constraints/compute.vmExternalIpAccess": lambda ou, enabled: [{"deny_all": "TRUE"}],
            "constraints/gcp.restrictNonCmekServices": lambda ou, enabled: [
                {"values": {"denied_values": CMEK_SERVICES}}],
            "constraints/gcp.restrictCmekCryptoKeyProjects": self._under_folder,
            "constraints/compute.restrictSharedVpcHostProjects": self._under_folder,
            "constraints/compute.restrictVpcPeering": lambda ou, enabled: [
                {"values": {"allowed_values": ["under:organizations/${var.organization_id}"]}}],
            "constraints/compute.restrictLoadBalancerCreationForTypes": lambda ou, enabled: [
                {"values": {"allowed_values": ["in:INTERNAL"]}}],
        }

    def rules(self, ou: OuNode, enabled: EnabledControl) -> list[dict]:
        return self._rules.get(enabled.control.id, lambda ou, enabled: ENFORCED)(ou, enabled)

    def _locations(self, ou: OuNode, enabled: EnabledControl) -> list[dict]:
        regions = enabled.parameters.get("AllowedRegions", [])
        return [{"values": {"allowed_values": [f"in:{region}-locations" for region in regions]}}]

    def _member_domains(self, ou: OuNode, enabled: EnabledControl) -> list[dict]:
        return [{"values": {"allowed_values": ["${data.google_organization.organization.directory_customer_id}"]}}]

    def _under_folder(self, ou: OuNode, enabled: EnabledControl) -> list[dict]:
        return [{"values": {"allowed_values": [f"under:{self._folder_name(ou)}"]}}]


# Custom constraints the packs use, defined once at the organization (lz-foundation).
CUSTOM_CONSTRAINTS = {
    "custom.cloudinfraSqlRequireSsl": {
        "resource_types": ["sqladmin.googleapis.com/Instance"], "method_types": ["CREATE", "UPDATE"],
        "condition": "resource.settings.ipConfiguration.requireSsl == true", "action_type": "ALLOW",
        "display_name": "Require SSL for Cloud SQL connections"},
    "custom.cloudinfraDenyMultiRegionStorage": {
        "resource_types": ["storage.googleapis.com/Bucket"], "method_types": ["CREATE", "UPDATE"],
        "condition": "!(resource.location in ['US', 'EU', 'ASIA', 'NAM4', 'EUR4', 'ASIA1'])", "action_type": "ALLOW",
        "display_name": "Deny dual- and multi-region buckets"},
}

# What each IAM deny control denies, and whose groups are excepted (by the provider answers' group role).
DENY_POLICIES = {
    "iam-deny/protect-logging": {
        "permissions": ["logging.googleapis.com/sinks.delete", "logging.googleapis.com/sinks.update",
                        "logging.googleapis.com/buckets.delete"], "except": "security_admins"},
    "iam-deny/protect-production": {
        "permissions": ["cloudresourcemanager.googleapis.com/projects.delete",
                        "storage.googleapis.com/buckets.delete"], "except": "organization_admins"},
}
