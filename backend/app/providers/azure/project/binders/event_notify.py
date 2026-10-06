from app.providers.azure.project.capabilities import EventSource, Workload
from app.synth.binders.base import Binder
from app.synth.binders.kinds import EVENT_NOTIFY


class EventGridBinder(Binder):
    """Deliver a source's events to a function through an Event Grid system topic. Prefix and suffix are native
    subject filters (MC4-6), so the function needs no checks of its own."""

    kind = EVENT_NOTIFY

    def accepts(self, source_type, target_type) -> bool:
        return issubclass(source_type, EventSource) and issubclass(target_type, Workload)

    def bind(self, connection, source, target, documents) -> None:
        comment = f"{connection.source} → {connection.target}"
        if not documents.data.has_resource(connection.source, "Microsoft.EventGrid/systemTopics"):
            source.add_topic(documents)
        documents.data.add_resource(source.read_grant(target.identity(), comment))
        target.add_subscription(source, connection.prefix, connection.suffix)
        target.add_environment(source.environment())
