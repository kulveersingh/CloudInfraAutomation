import pytest

from app.provisioning.topology import RegionTopology, TopologyFactory, UnknownResilienceModeError
from app.synth.request import Resilience

FACTORY = TopologyFactory.default()


def topology(mode: str, secondary: str | None = "us-east-2") -> RegionTopology:
    return FACTORY.for_resilience(Resilience(mode=mode, primary_region="us-east-1", secondary_region=secondary))


def test_single_region_everywhere():
    assert topology("single", None).regions_for("prod") == ["us-east-1"]


def test_single_region_has_no_secondary_state():
    assert topology("single", None).secondary_activation() is None


def test_dr_lower_environments_stay_single_region():
    assert topology("dr").regions_for("dev") == ["us-east-1"]


def test_dr_stage_and_prod_use_both_regions():
    assert topology("dr").regions_for("prod") == ["us-east-1", "us-east-2"]


def test_dr_secondary_is_standby():
    assert topology("dr").secondary_activation() == "standby"


def test_ha_secondary_is_active():
    assert topology("ha").secondary_activation() == "active"


def test_secondary_region_exposed():
    assert topology("ha").secondary_region == "us-east-2"


def test_unknown_mode_raises():
    with pytest.raises(UnknownResilienceModeError):
        TopologyFactory({}).for_resilience(Resilience(mode="dr", primary_region="us-east-1",
                                                      secondary_region="us-east-2"))
