from abc import ABC, abstractmethod

from app.synth.request import Resilience

MULTI_REGION_ENVIRONMENTS = frozenset({"stage", "prod"})


class UnknownResilienceModeError(KeyError):
    pass


class RegionTopology(ABC):
    """Which regions each environment is deployed to, and how the secondary region behaves."""

    def __init__(self, primary_region: str, secondary_region: str | None):
        self.primary_region = primary_region
        self.secondary_region = secondary_region

    @abstractmethod
    def regions_for(self, environment_id: str) -> list[str]:
        ...

    @abstractmethod
    def secondary_activation(self) -> str | None:
        ...


class SingleRegionTopology(RegionTopology):
    def regions_for(self, environment_id):
        return [self.primary_region]

    def secondary_activation(self):
        return None


class TwoRegionTopology(RegionTopology, ABC):
    """Lower environments stay single-region to save cost; QA/STAGE and PROD use both regions."""

    def regions_for(self, environment_id):
        if environment_id in MULTI_REGION_ENVIRONMENTS:
            return [self.primary_region, self.secondary_region]
        return [self.primary_region]


class DisasterRecoveryTopology(TwoRegionTopology):
    def secondary_activation(self):
        return "standby"


class HighAvailabilityTopology(TwoRegionTopology):
    def secondary_activation(self):
        return "active"


class TopologyFactory:
    def __init__(self, topologies: dict[str, type[RegionTopology]]):
        self._topologies = topologies

    @classmethod
    def default(cls) -> "TopologyFactory":
        return cls({"single": SingleRegionTopology, "dr": DisasterRecoveryTopology,
                    "ha": HighAvailabilityTopology})

    def for_resilience(self, resilience: Resilience) -> RegionTopology:
        if resilience.mode not in self._topologies:
            raise UnknownResilienceModeError(resilience.mode)
        return self._topologies[resilience.mode](resilience.primary_region, resilience.secondary_region)
