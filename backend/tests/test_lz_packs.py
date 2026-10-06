from dataclasses import replace

import pytest

from app.landing_zone.catalog.mappings import (
    AllInherited,
    PackMappings,
    PreventiveInherited,
    ProviderControls,
)
from app.landing_zone.catalog.packs import PackRegistry
from app.landing_zone.catalog.resolver import PackResolver
from app.landing_zone.catalog.selectors import SelectorRegistry
from app.providers.aws.landing_zone.controls import UNRESOLVED_PREREQUISITE, aws_controls, aws_snapshot
from tests.lz_factories import add_ou, edited

ROOT_USER = "5kvme4m5d2b4d7if2fs5yg2ui"
ROOT_MFA = "24izmu4k16gv9tvd7sexnyrfy"
REGION_DENY = "ka8e3pkqefnjsxuyc26ji580"
RDS_MULTI_AZ = "avr20py8ssve39u69tyuxcanz"
PCI_NO_INTERNET = "41ngl8m5c4eb1myoz0t707n7h"
GUARDDUTY = "62smpoz33dsy0oa7u1iwa58lz"


def design(edits=(), **overrides):
    return edited(list(edits), **overrides)[0]


def resolved(structure, snapshot=None):
    return PackResolver(PackRegistry.default(), aws_controls(snapshot)).resolve(structure)


def ids_on(structure, ou_key: str, snapshot=None) -> list[str]:
    return [enabled.control.id for enabled in resolved(structure, snapshot).controls.get(ou_key, [])]


def selected(selector: str, **overrides) -> list[str]:
    return [ou.key for ou in SelectorRegistry().get(selector).select(design(**overrides))]


# ---- selectors ----

def test_workloads_are_the_isolated_ous():
    assert selected("workloads") == ["sandbox", "dev", "test", "stage", "prod"]


def test_production_tier_includes_compliance_environments():
    assert selected("production_tier", compliance=["PCI"]) == ["stage", "prod", "pci_stage", "pci_prod"]


def test_non_production_tier():
    assert selected("nonproduction_tier") == ["dev", "test"]


def test_sandbox_and_infrastructure_selectors():
    assert (selected("sandbox"), selected("infrastructure")) == (["sandbox"], ["infrastructure"])


def test_compliance_selector_picks_that_scope():
    assert selected("compliance:PCI", compliance=["PCI", "HIPAA"]) == ["pci"]


def test_custom_domains_selector():
    assert [ou.key for ou in SelectorRegistry().get("custom_domains").select(design([add_ou("Lab", parent=None)]))] == [
        "custom_lab"]


def test_unknown_selector():
    assert SelectorRegistry().knows("everywhere") is False


# ---- resolving packs onto OUs ----

def test_profile_packs_reach_every_workload_ou():
    assert ROOT_USER in ids_on(design(), "dev") and ROOT_USER in ids_on(design(), "sandbox")


def test_production_packs_reach_only_production_tier():
    structure = design()
    assert (RDS_MULTI_AZ in ids_on(structure, "prod"), RDS_MULTI_AZ in ids_on(structure, "dev")) == (True, False)


def test_a_control_from_two_packs_is_enabled_once_and_names_both(tmp_path):
    (tmp_path / "packs").mkdir()
    (tmp_path / "aws").mkdir()
    for name in ("first", "second"):
        (tmp_path / "packs" / f"{name}.yaml").write_text(f"id: {name}\nversion: 1\nname: {name}\ndescription: x\n"
                                                         "selectors: [workloads, production_tier]\n")
        (tmp_path / "aws" / f"{name}.yaml").write_text(f"pack: {name}\ncontrols: [{ROOT_MFA}]\n")
    registry = PackRegistry.load(tmp_path / "packs", profiles={"recommended": ["first", "second"]})
    controls = ProviderControls(aws_snapshot(), PackMappings.load(tmp_path / "aws", aws_snapshot(), registry),
                                PreventiveInherited())
    enabled = PackResolver(registry, controls).resolve(design()).controls["prod"]
    assert [(item.control.id, item.packs) for item in enabled] == [(ROOT_MFA, ("first", "second"))]


def test_preventive_controls_go_on_the_top_most_selected_ou_only():
    structure = design(compliance=["PCI"], control_packs=["pci-cde"])
    assert (PCI_NO_INTERNET in ids_on(structure, "pci"), PCI_NO_INTERNET in ids_on(structure, "pci_prod")) == (True, False)


def test_detective_controls_are_enabled_on_every_nested_ou():
    structure = design([add_ou("Payments")])
    assert (ROOT_MFA in ids_on(structure, "prod"), ROOT_MFA in ids_on(structure, "custom_payments")) == (True, True)


def test_preventive_controls_are_inherited_by_nested_ous():
    assert ROOT_USER not in ids_on(design([add_ou("Payments")]), "custom_payments")


def test_each_enabled_control_names_its_packs():
    enabled = next(item for item in resolved(design()).controls["prod"] if item.control.id == ROOT_USER)
    assert enabled.packs == ("foundation",)


def test_region_deny_defaults_to_the_governed_regions():
    enabled = next(item for item in resolved(design(control_packs=["data-residency"])).controls["prod"]
                   if item.control.id == REGION_DENY)
    assert enabled.parameters == {"AllowedRegions": ["us-east-1", "us-east-2"]}


def test_pack_parameters_override_the_defaults():
    structure = design(control_packs=["data-residency"],
                       pack_parameters={"data-residency": {"AllowedRegions": ["us-east-1"]}})
    enabled = next(item for item in resolved(structure).controls["prod"] if item.control.id == REGION_DENY)
    assert enabled.parameters == {"AllowedRegions": ["us-east-1"]}


def test_controls_without_parameters_have_none():
    enabled = next(item for item in resolved(design()).controls["prod"] if item.control.id == ROOT_USER)
    assert enabled.parameters == {}


def test_logging_pack_also_covers_infrastructure():
    assert GUARDDUTY in ids_on(design(controls_profile="regulated"), "infrastructure")


# ---- the CloudFormation-hooks prerequisite for proactive controls ----

@pytest.fixture
def snapshot_with_prerequisite():
    snapshot = aws_snapshot()
    hooks = replace(snapshot.get(ROOT_USER), id="hooksprerequisite", name="Disallow CloudFormation registry changes")
    return snapshot.with_proactive_prerequisite(hooks)


def test_ous_with_proactive_controls_get_the_hooks_prerequisite(snapshot_with_prerequisite):
    assert "hooksprerequisite" in ids_on(design(), "prod", snapshot_with_prerequisite)


def test_ous_without_proactive_controls_do_not(snapshot_with_prerequisite):
    assert "hooksprerequisite" not in ids_on(design(controls_profile="baseline"), "prod", snapshot_with_prerequisite)


def test_an_unknown_prerequisite_is_a_warning():
    assert resolved(design()).warnings == [UNRESOLVED_PREREQUISITE]


def test_no_warning_without_proactive_controls():
    assert resolved(design(controls_profile="baseline")).warnings == []


def test_a_pack_that_reaches_no_ou_is_a_warning():
    assert resolved(design(control_packs=["foundation", "pci-cde"])).warnings[-1] == (
        "Control pack 'PCI cardholder data environment' applies to no OU in this design.")


# ---- how each cloud's controls are inherited ----

def test_aws_inherits_preventive_controls_only():
    assert (PreventiveInherited().inherited(aws_snapshot().get(ROOT_USER)),
            PreventiveInherited().inherited(aws_snapshot().get(ROOT_MFA))) == (True, False)


def test_where_every_control_is_inherited_nested_ous_get_none_of_the_parents():
    controls = ProviderControls(aws_snapshot(), aws_controls().mappings, AllInherited())
    enabled = PackResolver(PackRegistry.default(), controls).resolve(design([add_ou("Payments")])).controls
    assert (ROOT_MFA in [item.control.id for item in enabled["prod"]], enabled.get("custom_payments", [])) == (True, [])
