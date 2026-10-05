from typing import Protocol

from app.synth.blocks.base import Block
from app.synth.request import ProjectRequest, ResourceSpec


class UnknownBlockTypeError(KeyError):
    pass


class BlockResolver(Protocol):
    """Supplies block classes for whole families of types (e.g. every resource type a provider publishes)."""

    def claims(self, type_name: str) -> bool: ...

    def supports(self, type_name: str) -> bool: ...

    def block_class(self, type_name: str) -> type[Block]: ...

    def problems_for(self, resource: ResourceSpec) -> list[str]: ...


class BlockRegistry:
    """Maps type names (and aliases) to one provider's block classes: curated blocks first, then resolvers.
    Extend with register*()."""

    def __init__(self):
        self._classes: dict[str, type[Block]] = {}
        self._aliases: dict[str, str] = {}
        self._resolvers: list[BlockResolver] = []

    def register(self, block_class: type[Block], aliases: tuple[str, ...] = ()) -> None:
        self._classes[block_class.type_name] = block_class
        self._aliases.update({alias: block_class.type_name for alias in aliases})

    def register_resolver(self, resolver: BlockResolver) -> None:
        self._resolvers.append(resolver)

    def has_type(self, type_name: str) -> bool:
        if self._curated(type_name) is not None:
            return True
        return self._curated_alias(type_name) is None and any(
            resolver.supports(type_name) for resolver in self._resolvers)

    def block_class(self, type_name: str) -> type[Block]:
        if not self.has_type(type_name):
            raise UnknownBlockTypeError(type_name)
        curated = self._curated(type_name)
        if curated is not None:
            return curated
        return next(resolver for resolver in self._resolvers if resolver.supports(type_name)).block_class(type_name)

    def problems_for(self, resource: ResourceSpec) -> list[str]:
        curated = self._curated(resource.type)
        if curated is not None:
            return curated.config_problems(resource)
        alias = self._curated_alias(resource.type)
        if alias is not None:
            return [f"Use the curated service '{alias}' instead of '{resource.type}' for '{resource.id}'."]
        claiming = [resolver for resolver in self._resolvers if resolver.claims(resource.type)]
        if not claiming:
            return [f"Unknown resource type '{resource.type}' for '{resource.id}'."]
        return claiming[0].problems_for(resource)

    def create(self, spec: ResourceSpec, request: ProjectRequest) -> Block:
        return self.block_class(spec.type)(spec, request)

    def type_names(self) -> list[str]:
        return sorted(self._classes)

    def classes(self) -> list[type[Block]]:
        return [self._classes[type_name] for type_name in self.type_names()]

    def _curated(self, type_name: str) -> type[Block] | None:
        return self._classes.get(self._aliases.get(type_name, type_name))

    def _curated_alias(self, type_name: str) -> str | None:
        return next((block_class.type_name for block_class in self._classes.values()
                     if type_name in block_class.provider_types), None)
