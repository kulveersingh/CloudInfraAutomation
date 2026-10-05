from app.synth.blocks.registry import BlockRegistry


class ServiceCatalog:
    """The services users can pick, derived from the registered blocks."""

    def __init__(self, blocks: BlockRegistry):
        self._blocks = blocks

    def entries(self) -> list[dict]:
        return [{"type": block_class.type_name, "name": block_class.display_name, "category": block_class.category,
                 "multi_region": block_class.multi_region,
                 "settings": [setting.describe() for setting in block_class.settings]}
                for block_class in self._blocks.classes()]
