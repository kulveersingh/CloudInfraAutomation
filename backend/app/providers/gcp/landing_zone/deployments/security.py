from app.providers.gcp.landing_zone.deployments.base import ORGANIZATION, Deployment, FolderReferences

AUDIT_FILTER = 'logName:"cloudaudit.googleapis.com"'
RESTRICTED_SERVICES = ["storage.googleapis.com", "bigquery.googleapis.com", "sqladmin.googleapis.com",
                       "firestore.googleapis.com", "pubsub.googleapis.com", "secretmanager.googleapis.com",
                       "cloudfunctions.googleapis.com", "run.googleapis.com"]
DEPLOYED_TIERS = ("premium", "enterprise")


class SecurityDeployment(Deployment):
    """Organization audit logs into a locked bucket, a VPC Service Controls perimeter per environment (dry-run
    first, MC3-4), and Security Command Center postures for the detective controls (Premium/Enterprise, MC3-5)."""

    name = "lz-security"
    description = "Audit log sink and locked bucket, VPC Service Controls perimeters, SCC postures"

    def build(self, context, document):
        folders = FolderReferences(context.design, owned=False)
        folders.add_lookups(document)
        self._logs(context, document)
        self._perimeters(context, document)
        if context.answers.scc_tier in DEPLOYED_TIERS:
            self._postures(context, document, folders)

    def _logs(self, context, document) -> None:
        logging_project, _ = context.security_projects
        bucket = f"{context.design.answers.organization_name}-audit"
        document.add_resource("google_logging_project_bucket_config", "audit", {
            "project": logging_project, "location": "global", "bucket_id": bucket,
            "retention_days": context.design.answers.log_retention_days, "locked": True})
        document.add_resource("google_logging_organization_sink", "audit", {
            "name": bucket, "org_id": "${var.organization_id}", "include_children": True, "filter": AUDIT_FILTER,
            "destination": f"logging.googleapis.com/projects/{logging_project}/locations/global/buckets/{bucket}",
            "depends_on": ["google_logging_project_bucket_config.audit"]})
        document.add_resource("google_project_iam_member", "audit-sink-writer", {
            "project": logging_project, "role": "roles/logging.bucketWriter",
            "member": "${google_logging_organization_sink.audit.writer_identity}"})

    def _perimeters(self, context, document) -> None:
        document.add_resource("google_access_context_manager_access_policy", "organization", {
            "parent": ORGANIZATION, "title": f"{context.design.answers.organization_name} environments"})
        policy = "accessPolicies/${google_access_context_manager_access_policy.organization.name}"
        for environment in context.environments:
            key = environment.ou.key
            projects = [environment.host, *environment.workloads]
            for project in projects:
                document.add_data("google_project", project.name, {"project_id": project.name})
            document.add_resource("google_access_context_manager_service_perimeter", key, {
                "parent": policy, "name": f"{policy}/servicePerimeters/{key}", "title": environment.ou.name,
                "use_explicit_dry_run_spec": True,
                "spec": {"resources": [f"projects/${{data.google_project.{project.name}.number}}"
                                       for project in projects], "restricted_services": RESTRICTED_SERVICES}})

    def _postures(self, context, document, folders) -> None:
        detective = {}
        for ou, enabled in context.placed({"SCC_DETECTOR"}):
            detective.setdefault(ou.key, (ou, []))[1].append(enabled.control)
        for key, (ou, controls) in detective.items():
            posture_id = f"cloudinfra_{key}"
            document.add_resource("google_securityposture_posture", key, {
                "parent": ORGANIZATION, "location": "global", "posture_id": posture_id, "state": "ACTIVE",
                "description": f"Detective controls for {ou.name}",
                "policy_sets": [{"policy_set_id": "detectors", "policies": [
                    {"policy_id": control.id.lower(), "description": control.name,
                     "constraint": {"security_health_analytics_module": {
                         "module_name": control.id, "module_enablement_state": "ENABLED"}}}
                    for control in controls]}]})
            document.add_resource("google_securityposture_posture_deployment", key, {
                "parent": ORGANIZATION, "location": "global", "posture_deployment_id": posture_id,
                "posture_id": f"${{google_securityposture_posture.{key}.name}}",
                "posture_revision_id": f"${{google_securityposture_posture.{key}.revision_id}}",
                "target_resource": folders.name(ou)})
