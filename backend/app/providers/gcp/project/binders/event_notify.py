from app.providers.gcp.project.capabilities import EventSource, Workload
from app.providers.gcp.project.document import PRIMARY_ONLY
from app.synth.binders.base import Binder
from app.synth.binders.kinds import EVENT_NOTIFY

PREFIX_VARIABLE = "CLOUDINFRA_EVENT_PREFIX"
SUFFIX_VARIABLE = "CLOUDINFRA_EVENT_SUFFIX"
STORAGE_AGENT = "gcs"
STORAGE_PUBLISHER = "gcs-events-publisher"


class EventarcBinder(Binder):
    """Trigger a function from a source's events through Eventarc. Eventarc filters on exact attributes only, so a
    prefix or suffix reaches the function as environment variables for it to check (§22.9.3)."""

    kind = EVENT_NOTIFY

    def accepts(self, source_type, target_type) -> bool:
        return issubclass(source_type, EventSource) and issubclass(target_type, Workload)

    def bind(self, connection, source, target, document) -> None:
        target.add_trigger(source.event_trigger())
        filters = {PREFIX_VARIABLE: connection.prefix, SUFFIX_VARIABLE: connection.suffix}
        target.add_environment({**source.environment(), **{name: value for name, value in filters.items() if value}})
        document.add_resource(*source.read_grant(target.member(), connection.target))
        self._let_storage_publish(document, source.spans_regions)

    def _let_storage_publish(self, document, spans_regions: bool) -> None:
        """Cloud Storage's service agent publishes the object events Eventarc delivers."""
        document.add_data("google_storage_project_service_account", STORAGE_AGENT, {"project": "${var.project_id}"})
        if document.has_resource("google_project_iam_member", STORAGE_PUBLISHER):
            return
        body = {"project": "${var.project_id}", "role": "roles/pubsub.publisher",
                "member": f"serviceAccount:${{data.google_storage_project_service_account.{STORAGE_AGENT}.email_address}}"}
        document.add_resource("google_project_iam_member", STORAGE_PUBLISHER,
                              {"count": PRIMARY_ONLY, **body} if spans_regions else body)
