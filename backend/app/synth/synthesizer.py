from abc import ABC, abstractmethod

from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.base import Block
from app.synth.blocks.registry import BlockRegistry
from app.synth.request import ProjectRequest

ENGINE_VERSION = "0.1.0"
GENERATOR_NAME = "cloudinfra-synth"


class IacDialect(ABC):
    """How one cloud writes its IaC document (§22.3): what every document starts with, how a block is added, and
    what it ends with. The document itself is the dialect's own type."""

    @abstractmethod
    def start(self, request: ProjectRequest):
        ...

    @abstractmethod
    def add_block(self, document, block: Block) -> None:
        ...

    @abstractmethod
    def finish(self, document, request: ProjectRequest, blocks: dict[str, Block]) -> dict:
        ...


class TemplateSynthesizer:
    """Turns a validated project request into one provider's IaC document, using its blocks and binders."""

    def __init__(self, blocks: BlockRegistry, binders: BinderRegistry, dialect: IacDialect):
        self._block_registry = blocks
        self._binder_registry = binders
        self._dialect = dialect

    def synthesize(self, request: ProjectRequest) -> dict:
        document = self._dialect.start(request)
        blocks = {spec.id: self._block_registry.create(spec, request) for spec in request.resources}
        for connection in request.connections:  # before emitting: binders adjust the blocks they connect
            binder = self._binder_registry.binder(connection.kind)
            binder.bind(connection, blocks[connection.source], blocks[connection.target], document)
        for block in blocks.values():
            self._dialect.add_block(document, block)
        return self._dialect.finish(document, request, blocks)
