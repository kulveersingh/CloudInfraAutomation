from app.providers.gcp.landing_zone.deployments.base import ORGANIZATION, Deployment
from app.providers.gcp.landing_zone.deployments.constraints import CUSTOM_CONSTRAINTS

CONTACT_CATEGORIES = ["SECURITY", "TECHNICAL", "SUSPENSION"]


class FoundationDeployment(Deployment):
    """The environment tag and its values, the custom constraints the packs use, and the essential contact."""

    name = "lz-foundation"
    description = "Environment tag and values, custom Org Policy constraints, essential contact"

    def build(self, context, document):
        document.add_resource("google_tags_tag_key", "environment", {
            "parent": ORGANIZATION, "short_name": "environment",
            "description": "The environment a folder belongs to; policies and IAM conditions test it."})
        for ou in context.design.environment_ous():
            document.add_resource("google_tags_tag_value", ou.key, {
                "parent": "${google_tags_tag_key.environment.id}", "short_name": ou.key, "description": ou.name})
        used = {enabled.control.id for _, enabled in context.placed({"CUSTOM_CONSTRAINT"})}
        for constraint_id in sorted(used):
            document.add_resource("google_org_policy_custom_constraint", constraint_id.removeprefix("custom."), {
                "name": constraint_id, "parent": ORGANIZATION, **CUSTOM_CONSTRAINTS[constraint_id]})
        document.add_resource("google_essential_contacts_contact", "security", {
            "parent": ORGANIZATION, "email": context.answers.groups.security_admins, "language_tag": "en",
            "notification_category_subscriptions": CONTACT_CATEGORIES})
