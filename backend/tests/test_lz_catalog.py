import pytest

from app.landing_zone.catalog.controls import CatalogError, ControlCatalogSnapshot
from app.landing_zone.catalog.packs import PackRegistry
from app.landing_zone.catalog.templates import TemplateRegistry

ROOT_USER = "5kvme4m5d2b4d7if2fs5yg2ui"
REGION_DENY = "ka8e3pkqefnjsxuyc26ji580"
RDS_ENCRYPTED = "e34kieahgkm0lggs5g0s412jt"


def write(path, text: str):
    path.write_text(text)
    return path


# ---- control catalog snapshot ----

def test_controls_use_global_identifiers():
    assert ControlCatalogSnapshot.default().get(ROOT_USER).arn == f"arn:aws:controlcatalog:::control/{ROOT_USER}"


def test_snapshot_records_behavior_severity_and_implementation():
    control = ControlCatalogSnapshot.default().get(RDS_ENCRYPTED)
    assert (control.behavior, control.severity, control.implementation, control.is_scp) == (
        "DETECTIVE", "HIGH", "CONFIG_RULE", False)


def test_scp_based_controls_are_recognised():
    assert ControlCatalogSnapshot.default().get(ROOT_USER).is_scp is True


def test_parameterized_controls_list_their_parameters():
    assert ControlCatalogSnapshot.default().get(REGION_DENY).parameters == (
        "AllowedRegions", "ExemptedPrincipalArns", "ExemptedActions")


def test_framework_mappings_are_unverified_until_refreshed():
    snapshot = ControlCatalogSnapshot.default()
    assert (snapshot.mappings_refreshed, snapshot.get(ROOT_USER).frameworks) == (None, ())


def test_proactive_prerequisite_is_unknown_until_refreshed():
    assert ControlCatalogSnapshot.default().proactive_prerequisite is None


def test_unknown_control_is_an_error():
    with pytest.raises(CatalogError, match="Unknown control 'nope'"):
        ControlCatalogSnapshot.default().get("nope")


def test_snapshot_loads_refreshed_mappings(tmp_path):
    path = write(tmp_path / "controls.yaml", """
mappings_refreshed: '2026-10-04'
prerequisites: {proactive: abc}
controls:
  abc: {name: Hooks, behavior: PREVENTIVE, severity: HIGH, implementation: SCP, frameworks: [PCI-DSS-v4.0]}
""")
    snapshot = ControlCatalogSnapshot.load(path)
    assert (snapshot.mappings_refreshed, snapshot.proactive_prerequisite.id, snapshot.get("abc").frameworks) == (
        "2026-10-04", "abc", ("PCI-DSS-v4.0",))


# ---- control packs ----

def test_every_pack_control_is_in_the_snapshot():
    snapshot = ControlCatalogSnapshot.default()
    assert all(snapshot.get(control_id) for pack in PackRegistry.default().all() for control_id in pack.control_ids)


def test_packs_are_listed_in_a_stable_order():
    assert [pack.id for pack in PackRegistry.default().all()] == [
        "foundation", "data-protection", "network-hardening", "production-resilience", "logging-integrity",
        "key-management", "pci-cde", "data-residency", "strict-residency"]


def test_strict_residency_is_optional():
    assert [pack.id for pack in PackRegistry.default().all() if pack.optional] == ["strict-residency"]


def test_unknown_pack_is_an_error():
    with pytest.raises(CatalogError, match="Unknown control pack 'nope'"):
        PackRegistry.default().get("nope")


def test_pack_with_an_unknown_control_fails_to_load(tmp_path):
    write(tmp_path / "bad.yaml", "id: bad\nversion: 1\nname: Bad\ndescription: x\nselectors: [workloads]\ncontrols: [nope]\n")
    with pytest.raises(CatalogError, match="Pack 'bad' uses unknown control 'nope'"):
        PackRegistry.load(tmp_path, ControlCatalogSnapshot.default())


def test_pack_with_an_unknown_selector_fails_to_load(tmp_path):
    write(tmp_path / "bad.yaml", f"id: bad\nversion: 1\nname: Bad\ndescription: x\nselectors: [everywhere]\n"
                                 f"controls: [{ROOT_USER}]\n")
    with pytest.raises(CatalogError, match="Pack 'bad' uses unknown selector 'everywhere'"):
        PackRegistry.load(tmp_path, ControlCatalogSnapshot.default())


def test_profiles_are_packs():
    assert PackRegistry.default().for_profile("baseline") == ["foundation"]


# ---- industry templates ----

def test_six_industry_templates():
    assert [template.id for template in TemplateRegistry.default().all()] == [
        "financial-services", "healthcare", "public-sector", "retail", "saas", "eu-sovereignty"]


def test_template_carries_answers_edits_and_frameworks():
    saas = TemplateRegistry.default().get("saas")
    assert (saas.version, saas.answers["environment_ids"], saas.edits, saas.frameworks[0]) == (
        1, ["sandbox", "dev", "stage", "prod"], [{"op": "add_ou", "parent": "prod", "name": "Tenants"}],
        "SSAE-18-SOC-2-Oct-2023")


def test_unknown_template_is_an_error():
    with pytest.raises(CatalogError, match="Unknown template 'nope'"):
        TemplateRegistry.default().get("nope")


def test_template_with_an_unknown_pack_fails_to_load(tmp_path):
    write(tmp_path / "bad.yaml", "id: bad\nversion: 1\nname: Bad\nindustry: x\ndescription: x\nframeworks: []\n"
                                 "answers: {control_packs: [nope]}\nedits: []\n")
    with pytest.raises(CatalogError, match="Template 'bad' uses unknown control pack 'nope'"):
        TemplateRegistry.load(tmp_path, PackRegistry.default())
