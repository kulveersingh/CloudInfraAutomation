from abc import ABC, abstractmethod
from typing import ClassVar

from app.synth.blocks.base import Block
from app.synth.request import ConnectionSpec
from app.synth.template import Template


class Binder(ABC):
    """Wires one connection kind between two blocks. Register new kinds in BinderRegistry."""

    kind: ClassVar[str]

    @abstractmethod
    def accepts(self, source_type: type[Block], target_type: type[Block]) -> bool:
        ...

    @abstractmethod
    def bind(self, connection: ConnectionSpec, source: Block, target: Block, template: Template) -> None:
        ...

    def problems(self, connection: ConnectionSpec, source_type: type[Block], target_type: type[Block]) -> list[str]:
        if self.accepts(source_type, target_type):
            return []
        return [f"{self.kind} cannot connect {source_type.type_name} to {target_type.type_name}."]
