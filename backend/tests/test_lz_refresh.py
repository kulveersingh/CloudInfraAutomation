import yaml

from app.landing_zone.catalog.controls import ControlCatalogSnapshot
from app.landing_zone.catalog.refresh import ControlCatalogRefresher

ROOT_USER = "5kvme4m5d2b4d7if2fs5yg2ui"
ARN = f"arn:aws:controlcatalog:::control/{ROOT_USER}"
HOOKS_ARN = "arn:aws:controlcatalog:::control/hooks0prerequisite"


class FakeControlCatalog:
    """The two Control Catalog calls the refresher makes, with the API's response shapes and pagination."""

    def __init__(self):
        self.mapping_filters = []

    def list_controls(self, **kwargs):
        pages = {None: {"Controls": [{"Arn": ARN, "Name": "Disallow actions as a root user (renamed)",
                                      "Behavior": "PREVENTIVE", "Severity": "CRITICAL", "Aliases": ["AWS-GR_RESTRICT_ROOT_USER"]}],
                        "NextToken": "page-2"},
                 "page-2": {"Controls": [{"Arn": HOOKS_ARN, "Name": "Disallow CloudFormation registry changes",
                                          "Behavior": "PREVENTIVE", "Severity": "CRITICAL",
                                          "Aliases": ["CT.CLOUDFORMATION.PR.1"]}]}}
        return pages[kwargs.get("NextToken")]

    def list_control_mappings(self, **kwargs):
        self.mapping_filters.append(kwargs["Filter"])
        pages = {None: {"ControlMappings": [{"ControlArn": ARN, "MappingType": "FRAMEWORK",
                                             "Mapping": {"Framework": {"Name": "PCI-DSS-v4.0", "Item": "8.2.2"}}}],
                        "NextToken": "page-2"},
                 "page-2": {"ControlMappings": [{"ControlArn": ARN, "MappingType": "FRAMEWORK",
                                                 "Mapping": {"Framework": {"Name": "NIST-SP-800-53-r5", "Item": "AC-6"}}},
                                                {"ControlArn": ARN, "MappingType": "FRAMEWORK",
                                                 "Mapping": {"Framework": {"Name": "PCI-DSS-v4.0", "Item": "7.2.1"}}}]}}
        return pages[kwargs.get("NextToken")]


def refreshed(tmp_path, client=None):
    path = tmp_path / "controls.yaml"
    ControlCatalogRefresher(client or FakeControlCatalog(), today="2026-10-04").refresh(
        ControlCatalogSnapshot.default(), path)
    return ControlCatalogSnapshot.load(path)


def test_refresh_records_framework_mappings_once_each(tmp_path):
    assert refreshed(tmp_path).get(ROOT_USER).frameworks == ("NIST-SP-800-53-r5", "PCI-DSS-v4.0")


def test_refresh_updates_names_and_severity_from_the_catalog(tmp_path):
    control = refreshed(tmp_path).get(ROOT_USER)
    assert (control.name, control.severity) == ("Disallow actions as a root user (renamed)", "CRITICAL")


def test_refresh_resolves_the_hooks_prerequisite_by_its_alias(tmp_path):
    prerequisite = refreshed(tmp_path).proactive_prerequisite
    assert (prerequisite.id, prerequisite.implementation) == ("hooks0prerequisite", "SCP")


def test_refresh_stamps_the_date(tmp_path):
    assert refreshed(tmp_path).mappings_refreshed == "2026-10-04"


def test_refresh_asks_only_for_framework_mappings_of_snapshot_controls(tmp_path):
    client = FakeControlCatalog()
    refreshed(tmp_path, client)
    assert (client.mapping_filters[0]["MappingTypes"], len(client.mapping_filters[0]["ControlArns"])) == (
        ["FRAMEWORK"], len(ControlCatalogSnapshot.default().controls))


def test_controls_missing_from_the_catalog_keep_their_snapshot_entry(tmp_path):
    assert refreshed(tmp_path).get("e34kieahgkm0lggs5g0s412jt").name == (
        "Detect whether storage encryption is enabled for Amazon RDS database instances")


def test_refreshed_file_keeps_its_explanatory_header(tmp_path):
    refreshed(tmp_path)
    text = (tmp_path / "controls.yaml").read_text()
    assert (text.startswith("# Control Catalog snapshot"), yaml.safe_load(text)["mappings_refreshed"]) == (
        True, "2026-10-04")
