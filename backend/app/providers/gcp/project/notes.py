from app.synth.binders.kinds import EVENT_NOTIFY
from app.synth.binders.registry import BinderRegistry
from app.synth.toolkit import PreviewAdvisor


class EventFilterAdvisor(PreviewAdvisor):
    """Says which functions must filter events themselves, because Eventarc matches exact attributes only."""

    def __init__(self, binders: BinderRegistry):
        self._binders = binders

    def notes(self, request):
        return [f"{connection.source} → {connection.target}: Eventarc cannot filter by object "
                f"{self._what(connection)}, so {connection.target} must check {self._variables(connection)}."
                for connection in request.connections
                if self._binders.canonical(connection.kind) == EVENT_NOTIFY and (connection.prefix or connection.suffix)]

    def _what(self, connection) -> str:
        return " or ".join(word for word, value in (("prefix", connection.prefix), ("suffix", connection.suffix))
                           if value)

    def _variables(self, connection) -> str:
        return " and ".join(name for name, value in (("CLOUDINFRA_EVENT_PREFIX", connection.prefix),
                                                     ("CLOUDINFRA_EVENT_SUFFIX", connection.suffix)) if value)
