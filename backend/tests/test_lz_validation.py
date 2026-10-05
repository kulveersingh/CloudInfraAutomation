from app.landing_zone.design import AccountPlan, LandingZoneDesign, OuNode
from app.landing_zone.designer import LandingZoneDesigner
from app.landing_zone.validation import DesignValidator
from app.providers.aws.landing_zone.limits import MaximumDepth
from tests.lz_factories import CATALOG, answers


def design(**overrides) -> LandingZoneDesign:
    return LandingZoneDesigner.default().design(answers(**overrides), CATALOG)


def problems(structure: LandingZoneDesign) -> list[str]:
    return DesignValidator.default().problems(structure)


def environment_ou(name: str, environment: str) -> OuNode:
    return OuNode(key=name.lower(), name=name, kind="environment", environment=environment)


def test_designer_output_is_valid():
    assert problems(design(grouping="prod_nonprod", compliance=["PCI", "HIPAA"])) == []


def test_missing_environment_ou_is_reported():
    structure = design()
    structure.root_ous = [ou for ou in structure.root_ous if ou.name != "TEST"]
    assert problems(structure) == ["Environment 'test' must have its own OU."]


def test_environment_ou_nested_in_another_is_reported():
    structure = design()
    structure.ou_named("DEV").children.append(environment_ou("Inner", "test"))
    assert "Environment OU 'Inner' must not be inside another environment OU ('DEV')." in problems(structure)


def test_compliance_children_inside_a_compliance_ou_are_allowed():
    assert problems(design(compliance=["PCI"])) == []


def test_exactly_one_security_ou():
    structure = design()
    structure.root_ous.append(OuNode(key="security2", name="Security 2", kind="security"))
    assert problems(structure) == ["There must be exactly one Security OU (found 2)."]


def test_ou_names_are_unique():
    structure = design()
    structure.root_ous.append(OuNode(key="dev2", name="DEV", kind="parent"))
    assert problems(structure) == ["OU name 'DEV' is used more than once."]


def test_depth_is_limited_to_five_levels():
    structure = design()
    parent = structure.ou_named("Exceptions")
    for level in range(5):
        child = OuNode(key=f"deep{level}", name=f"Deep {level}", kind="parent")
        parent.children.append(child)
        parent = child
    assert MaximumDepth().problems(structure, CATALOG) == ["OU 'Deep 4' is 6 levels deep; AWS Organizations allows 5."]


def test_account_names_are_unique():
    structure = design()
    structure.ou_named("DEV").accounts.append(AccountPlan(name="acme-retail-prod", email="x@acme.example"))
    assert problems(structure) == ["Account name 'acme-retail-prod' is used more than once."]


def test_accounts_stay_in_their_isolation_domain():
    structure = design()
    retail = structure.ou_named("PROD").accounts.pop()
    structure.ou_named("DEV").accounts.append(retail)
    assert problems(structure) == ["Account 'acme-retail-prod' belongs to isolation domain 'prod' but is in OU 'DEV'."]
