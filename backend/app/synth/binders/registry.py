from app.synth.binders.base import Binder
from app.synth.binders.event_notify import EventNotifyBinder
from app.synth.binders.iam_access import IamAccessBinder


class UnknownConnectionKindError(KeyError):
    pass


class BinderRegistry:
    """Maps connection kinds to binders. New kinds are added with register()."""

    def __init__(self):
        self._binders: dict[str, Binder] = {}

    @classmethod
    def default(cls) -> "BinderRegistry":
        registry = cls()
        for binder in (EventNotifyBinder(), IamAccessBinder()):
            registry.register(binder)
        return registry

    def register(self, binder: Binder) -> None:
        self._binders[binder.kind] = binder

    def has_kind(self, kind: str) -> bool:
        return kind in self._binders

    def binder(self, kind: str) -> Binder:
        try:
            return self._binders[kind]
        except KeyError:
            raise UnknownConnectionKindError(kind) from None

    def kinds(self) -> list[str]:
        return sorted(self._binders)
