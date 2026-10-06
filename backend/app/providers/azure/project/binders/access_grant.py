from app.providers.azure.project.capabilities import GrantTarget, Workload
from app.synth.binders.base import Binder
from app.synth.binders.kinds import ACCESS_GRANT


class RoleAssignmentBinder(Binder):
    """Give a workload's identity a role on exactly one resource (§22.11.3), and its name in the app settings."""

    kind = ACCESS_GRANT
    aliases = ("iam.access",)

    def accepts(self, source_type, target_type) -> bool:
        return issubclass(source_type, Workload) and issubclass(target_type, GrantTarget)

    def problems(self, connection, source_type, target_type) -> list[str]:
        problems = super().problems(connection, source_type, target_type)
        if problems or connection.access is not None:
            return problems
        return [f"{connection.kind} from '{connection.source}' to '{connection.target}' needs an access level."]

    def bind(self, connection, source, target, documents) -> None:
        comment = f"{connection.source} → {connection.target}"
        for assignment in target.grants(connection.access, connection.prefix, source.identity(), comment):
            documents.shared.add_resource(assignment)
        source.add_environment(target.environment())
