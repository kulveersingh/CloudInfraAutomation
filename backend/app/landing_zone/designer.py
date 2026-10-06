from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import replace

from app.landing_zone.answers import EnvironmentAnswer, LandingZoneAnswers
from app.landing_zone.design import AccountPlan, LandingZoneDesign, OrgCatalog, OuNode
from app.landing_zone.naming import UnitCatalog, UnitNamer

NamerFactory = Callable[[LandingZoneAnswers], UnitNamer]

OPTIONAL_OUS = {"exceptions": ("Exceptions", "exceptions"), "suspended": ("Suspended", "suspended"),
                "individual_business_users": ("Business Users", "business_users")}


class AnswerHandler(ABC):
    """Turns part of the questionnaire into OUs and accounts. New questions add a handler. Units are named through
    `design.namer`, the cloud's way."""

    @abstractmethod
    def contribute(self, answers: LandingZoneAnswers, catalog: OrgCatalog, design: LandingZoneDesign) -> None:
        ...


class SecurityHandler(AnswerHandler):
    def contribute(self, answers, catalog, design):
        units = design.units
        suffixes = [*units.security, *([units.security_tooling] if answers.security_tooling else [])]
        design.root_ous.append(OuNode(key="security", name="Security", kind="security",
                                      created_by_service="security" in units.created_by_service,
                                      accounts=[design.namer.fixed(suffix) for suffix in suffixes]))


class InfrastructureHandler(AnswerHandler):
    def contribute(self, answers, catalog, design):
        accounts = [design.namer.fixed(suffix) for key, suffix in design.units.infrastructure.items()
                    if key in answers.infrastructure]
        design.root_ous.append(OuNode(key="infrastructure", name="Infrastructure", kind="infrastructure",
                                      accounts=accounts))


class EnvironmentHandler(AnswerHandler):
    """One OU per environment, directly under the root or under Prod/NonProd parents."""

    def contribute(self, answers, catalog, design):
        environments = answers.environments()
        design.root_ous += [self._ou(answers, catalog, environment, design) for environment in environments
                            if environment.tier == "sandbox"]
        workloads = [self._ou(answers, catalog, environment, design) for environment in environments
                     if environment.tier != "sandbox"]
        design.root_ous += workloads if answers.grouping == "separate" else self._parents(workloads)

    def _ou(self, answers: LandingZoneAnswers, catalog: OrgCatalog, environment: EnvironmentAnswer,
            design: LandingZoneDesign) -> OuNode:
        sandbox = environment.tier == "sandbox"
        host = None if sandbox else design.units.host_for(environment.name)
        accounts = self._accounts(answers, catalog, environment, design.namer)
        return OuNode(key=environment.id, name=environment.name, kind="environment", environment=environment.id,
                      tier=environment.tier, created_by_service=sandbox and "sandbox" in design.units.created_by_service,
                      accounts=[*accounts, *([design.namer.fixed(host)] if host else [])])

    def _accounts(self, answers, catalog, environment, namer: UnitNamer) -> list[AccountPlan]:
        suffix = environment.name.lower()
        if environment.tier == "sandbox":
            return self._sandbox_accounts(answers, catalog, namer)
        if answers.account_model == "environment":
            return [namer.unit(suffix)]
        owners = catalog.portfolios if answers.account_model == "portfolio" else catalog.products
        return [namer.unit(f"{_short(owner)}-{suffix}") for owner in owners]

    def _sandbox_accounts(self, answers, catalog, namer) -> list[AccountPlan]:
        if answers.sandbox.model == "developer":
            return [namer.fixed("developer-sandbox-01")]
        return [namer.fixed(f"{_short(portfolio)}-sandbox") for portfolio in catalog.portfolios]

    def _parents(self, workloads: list[OuNode]) -> list[OuNode]:
        return [OuNode(key=f"parent_{tier}", name=name, kind="parent", tier=tier,
                       children=[ou for ou in workloads if ou.tier == tier])
                for tier, name in (("nonprod", "NonProd"), ("prod", "Prod"))]


class ComplianceHandler(AnswerHandler):
    """Each regulated scope gets its own OU with STAGE and PROD child OUs and stricter controls."""

    def contribute(self, answers, catalog, design):
        namer = design.namer
        for scope in answers.compliance:
            children = [OuNode(key=f"{scope.lower()}_{environment}", name=f"{scope}-{environment.upper()}",
                               kind="environment", environment=environment, tier="prod",
                               accounts=[namer.unit(f"{scope.lower()}-{environment}")])
                        for environment in ("stage", "prod")]
            design.root_ous.append(OuNode(key=scope.lower(), name=scope, kind="compliance", tier="prod",
                                          children=children))


class AutomationsHandler(AnswerHandler):
    def contribute(self, answers, catalog, design):
        if "cicd" in answers.infrastructure:
            design.root_ous.append(OuNode(key="automations", name="Automations", kind="automations",
                                          accounts=[design.namer.fixed("cicd")]))


class PolicyStagingHandler(AnswerHandler):
    def contribute(self, answers, catalog, design):
        design.root_ous.append(OuNode(key="policy_staging", name="Policy Staging", kind="policy_staging"))


class OptionalOuHandler(AnswerHandler):
    def contribute(self, answers, catalog, design):
        design.root_ous += [OuNode(key=key, name=name, kind=key)
                            for option, (name, key) in OPTIONAL_OUS.items() if option in answers.optional_ous]


class LandingZoneDesigner:
    def __init__(self, handlers: list[AnswerHandler], namer: NamerFactory, units: UnitCatalog):
        self._handlers = handlers
        self._namer = namer
        self._units = units

    @classmethod
    def default(cls, namer: NamerFactory, units: UnitCatalog) -> "LandingZoneDesigner":
        """The standard questions, with a cloud's units and way of naming them."""
        return cls([SecurityHandler(), InfrastructureHandler(), EnvironmentHandler(), ComplianceHandler(),
                    AutomationsHandler(), PolicyStagingHandler(), OptionalOuHandler()], namer, units)

    def design(self, answers: LandingZoneAnswers, catalog: OrgCatalog) -> LandingZoneDesign:
        design = LandingZoneDesign(answers=answers, namer=self._namer(answers), units=self._units)
        for handler in self._handlers:
            handler.contribute(answers, catalog, design)
        self._record_domains(design)
        return design

    def _record_domains(self, design: LandingZoneDesign) -> None:
        """Each account remembers its isolation domain, so a later move out of it is caught."""
        for ou in design.walk():
            ou.accounts = [replace(account, domain=ou.isolation_domain) for account in ou.accounts]


def _short(registry_id: str) -> str:
    return registry_id.split("-", 1)[-1]
