from app.synth.binders.base import Binder
from app.synth.blocks.base import (
    FunctionNotification,
    InvocableFunction,
    NotificationSource,
    RuntimePrincipal,
)


class EventNotifyBinder(Binder):
    """Push events from a source (e.g. S3) to a function, without a dependency cycle.

    The invoke permission uses the source's built ARN, and the source waits for the permission.
    """

    kind = "event.notify"

    def accepts(self, source_type, target_type) -> bool:
        return issubclass(source_type, NotificationSource) and issubclass(target_type, InvocableFunction)

    def bind(self, connection, source, target, template) -> None:
        permission_id = f"{target.logical_id}InvokeFrom{source.logical_id}"
        template.add_resource(permission_id, {"Type": "AWS::Lambda::Permission", "Properties": {
            "FunctionName": target.arn(),
            "Action": "lambda:InvokeFunction",
            "Principal": source.notification_principal,
            "SourceArn": source.source_arn(),
            "SourceAccount": {"Ref": "AWS::AccountId"}}})
        source.add_notification(FunctionNotification(
            events=connection.events, function_arn=target.arn(), prefix=connection.prefix,
            suffix=connection.suffix, permission_id=permission_id))
        self._give_function_access(connection, source, target)

    def _give_function_access(self, connection, source, target: RuntimePrincipal) -> None:
        target.grant(source.notification_read_statement(connection.prefix))
        target.bind_environment(*source.environment_binding())
