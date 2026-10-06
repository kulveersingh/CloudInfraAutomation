from app.providers.gcp.landing_zone.deployments.base import Deployment, FolderReferences

BASE_SERVICES = ("compute", "logging", "monitoring")
HOST_SERVICES = ("networkconnectivity", "dns")
ROLE_SERVICES = {"backup": ("storage", "backupdr"), "network": HOST_SERVICES}
SECURITY_SERVICES = ("securitycenter", "securityposture")
BUDGET_THRESHOLDS = (0.5, 0.9, 1.0)


class ProjectsDeployment(Deployment):
    """The project factory: every enabled unit as a project in its folder, with its APIs; budgets for sandboxes."""

    name = "lz-projects"
    description = "Projects in their folders, their APIs, sandbox budgets"

    def build(self, context, document):
        folders = FolderReferences(context.design, owned=False)
        folders.add_lookups(document)
        services = self._services(context)
        for ou in context.design.walk():
            for account in ou.enabled_accounts():
                document.add_resource("google_project", account.name, {
                    "name": account.name, "project_id": account.name,
                    "folder_id": f'${{trimprefix({folders.name(ou)[2:-1]}, "folders/")}}',
                    "billing_account": "${var.billing_account}", "auto_create_network": False,
                    "deletion_policy": "PREVENT",
                    "labels": {"managed_by": "cloudinfra", "environment": ou.environment or "shared"}})
                for service in services.get(account.name, BASE_SERVICES):
                    document.add_resource("google_project_service", f"{account.name}-{service}", {
                        "project": f"${{google_project.{account.name}.project_id}}",
                        "service": f"{service}.googleapis.com", "disable_on_destroy": False})
                if ou.tier == "sandbox":
                    self._budget(context, document, account.name)

    def _services(self, context) -> dict[str, tuple[str, ...]]:
        services = {context.unit(key): (*BASE_SERVICES, *extra) for key, extra in ROLE_SERVICES.items()
                    if key in context.design.answers.infrastructure}
        services[context.security_projects[1]] = (*BASE_SERVICES, *SECURITY_SERVICES)
        services.update({environment.host.name: (*BASE_SERVICES, *HOST_SERVICES)
                         for environment in context.environments})
        return services

    def _budget(self, context, document, project: str) -> None:
        sandbox = context.design.answers.sandbox
        document.add_resource("google_billing_budget", project, {
            "billing_account": "${var.billing_account}", "display_name": f"{project} monthly budget",
            "budget_filter": {"projects": [f"projects/${{google_project.{project}.number}}"]},
            "amount": {"specified_amount": {"currency_code": "USD", "units": str(sandbox.monthly_budget_usd)}},
            "threshold_rules": [{"threshold_percent": threshold} for threshold in BUDGET_THRESHOLDS]})
