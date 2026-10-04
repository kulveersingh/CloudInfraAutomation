import ipaddress
import math
from dataclasses import dataclass

SMALLEST_POOL_PREFIX = 24


class AddressSpaceTooSmallError(ValueError):
    pass


@dataclass(frozen=True)
class IpamPlan:
    regional: dict[str, str]
    pools: dict[tuple[str, str], str]

    def pool(self, region: str, slot: str) -> str:
        return self.pools[(region, slot)]


class IpamPlanner:
    """Splits the organization CIDR into one block per region, then one pool per environment (slot)."""

    def plan(self, cidr: str, regions: list[str], slots: list[str]) -> IpamPlan:
        organization = ipaddress.ip_network(cidr)
        regional = dict(zip(regions, self._split(organization, len(regions)), strict=False))
        pools = {(region, slot): str(pool) for region, block in regional.items()
                 for slot, pool in zip(slots, self._split(block, len(slots)), strict=False)}
        return IpamPlan(regional={region: str(block) for region, block in regional.items()}, pools=pools)

    def _split(self, network, parts: int):
        new_prefix = network.prefixlen + math.ceil(math.log2(parts))
        if new_prefix > SMALLEST_POOL_PREFIX:
            raise AddressSpaceTooSmallError(f"{network} is too small to split into {parts} pools.")
        return list(network.subnets(new_prefix=new_prefix))[:parts]
