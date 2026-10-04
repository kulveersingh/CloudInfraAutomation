from xml.etree import ElementTree

from app.landing_zone.designer import LandingZoneDesigner
from app.landing_zone.diagram import OuDiagramRenderer
from tests.lz_factories import CATALOG, answers

SVG = "{http://www.w3.org/2000/svg}"


def design(**overrides):
    return LandingZoneDesigner.default().design(answers(**overrides), CATALOG)


def svg_texts(**overrides) -> list[str]:
    root = ElementTree.fromstring(OuDiagramRenderer().svg(design(**overrides)))
    return [element.text for element in root.iter(f"{SVG}text")]


def test_mermaid_starts_with_the_root():
    assert OuDiagramRenderer().mermaid(design()).splitlines()[:2] == [
        "flowchart TD", '  root["Root · acme<br/>Management / payer account"]']


def test_mermaid_links_every_top_level_ou_to_the_root():
    assert "  root --> prod" in OuDiagramRenderer().mermaid(design())


def test_mermaid_nests_children_under_parents():
    assert "  parent_prod --> prod" in OuDiagramRenderer().mermaid(design(grouping="prod_nonprod"))


def test_mermaid_lists_accounts_in_the_ou_node():
    assert 'prod["PROD OU<br/>acme-payments-prod<br/>acme-retail-prod"]' in OuDiagramRenderer().mermaid(design())


def test_svg_is_well_formed_and_names_every_ou():
    assert {"Security OU", "PROD OU", "Policy Staging OU"} <= set(svg_texts())


def test_svg_has_foundation_and_environment_rows():
    assert {"FOUNDATION", "ENVIRONMENTS (ISOLATED)"} <= set(svg_texts())


def test_svg_shows_nested_compliance_ous():
    assert "PCI-PROD OU" in svg_texts(compliance=["PCI"])

