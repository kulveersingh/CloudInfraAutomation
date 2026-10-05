from app.providers.gcp.project.capabilities import GrantTarget, Workload
from app.synth.binders.base import Binder
from app.synth.binders.kinds import ACCESS_GRANT


class ResourceBindingBinder(Binder):
    """Grant a workload's service account access to exactly one resource, bound on that resource (or conditioned
    on its name where the role is project-level)."""

    kind = ACCESS_GRANT
    aliases = ("iam.access",)

    def accepts(self, source_type, target_type) -> bool:
        return issubclass(source_type, Workload) and issubclass(target_type, GrantTarget)

    def problems(self, connection, source_type, target_type) -> list[str]:
        problems = super().problems(connection, source_type, target_type)
        if problems or connection.access is not None:
            return problems
        return [f"{connection.kind} from '{connection.source}' to '{connection.target}' needs an access level."]

    def bind(self, connection, source, target, document) -> None:
        for type_name, name, body in target.grants(connection.access, connection.prefix, source.member(),
                                                   connection.source):
            document.add_resource(type_name, name, body)
        source.add_environment(target.environment())
