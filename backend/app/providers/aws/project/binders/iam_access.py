from app.providers.aws.project.capabilities import AccessTarget, RuntimePrincipal
from app.synth.binders.base import Binder
from app.synth.binders.kinds import ACCESS_GRANT


class IamAccessBinder(Binder):
    """Grant a runtime principal exact-ARN access to a target at a read/write level."""

    kind = ACCESS_GRANT
    aliases = ("iam.access",)

    def accepts(self, source_type, target_type) -> bool:
        return issubclass(source_type, RuntimePrincipal) and issubclass(target_type, AccessTarget)

    def problems(self, connection, source_type, target_type) -> list[str]:
        problems = super().problems(connection, source_type, target_type)
        if problems or connection.access is not None:
            return problems
        return [f"{connection.kind} from '{connection.source}' to '{connection.target}' needs an access level."]

    def bind(self, connection, source, target, template) -> None:
        for statement in target.access_statements(connection.access, connection.prefix):
            source.grant(statement)
        source.bind_environment(*target.environment_binding())
