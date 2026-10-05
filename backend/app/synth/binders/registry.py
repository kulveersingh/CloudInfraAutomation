from app.synth.binders.base import Binder


class UnknownConnectionKindError(KeyError):
    pass


class BinderRegistry:
    """Maps connection kinds (and their aliases) to binders. New kinds are added with register()."""

    def __init__(self):
        self._binders: dict[str, Binder] = {}
        self._aliases: dict[str, str] = {}

    def register(self, binder: Binder, aliases: tuple[str, ...] = ()) -> None:
        self._binders[binder.kind] = binder
        self._aliases.update({alias: binder.kind for alias in aliases})

    def canonical(self, kind: str) -> str:
        return self._aliases.get(kind, kind)

    def has_kind(self, kind: str) -> bool:
        return self.canonical(kind) in self._binders

    def binder(self, kind: str) -> Binder:
        try:
            return self._binders[self.canonical(kind)]
        except KeyError:
            raise UnknownConnectionKindError(kind) from None

    def kinds(self) -> list[str]:
        return sorted(self._binders)
