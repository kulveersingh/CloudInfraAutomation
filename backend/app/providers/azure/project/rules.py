from app.synth.blocks.registry import BlockRegistry
from app.synth.validation import RequestRule

STORAGE = "storage.bucket"


class PairedRegionRule(RequestRule):
    """Geo-redundant storage replicates to the primary region's fixed pair (MC4-4)."""

    def __init__(self, blocks: BlockRegistry, pairs):
        self._blocks = blocks
        self._pairs = pairs

    def messages(self, request):
        resilience = request.resilience
        if not resilience.is_multi_region or resilience.secondary_region is None or not any(
                self._blocks.has_type(item.type) and self._blocks.block_class(item.type).type_name == STORAGE
                for item in request.resources):
            return []
        pair = self._pairs(resilience.primary_region)
        if pair is None:
            return [f"Azure geo-redundant storage needs a paired primary region; {resilience.primary_region} has none."]
        if pair == resilience.secondary_region:
            return []
        return [(f"Azure geo-redundant storage replicates to the primary region's pair: choose {pair} as the secondary "
                 f"region for {resilience.primary_region}.")]
