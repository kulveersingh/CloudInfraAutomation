from abc import ABC, abstractmethod

from app.landing_zone.answers import EnvironmentAnswer, LandingZoneAnswers
from app.landing_zone.design import AccountPlan, LandingZoneDesign, OrgCatalog, OuNode

INFRASTRUCTURE_ACCOUNTS = {"network": "network", "shared_services": "shared-services", "identity": "identity",
                           "backup": "backup", "monitoring": "monitoring"}
OPTIONAL_OUS = {"exceptions": ("Exceptions", "exceptions"), "suspended": ("Suspended", "suspended"),
                "individual_business_users": ("Business Users", "business_users")}


class AccountNamer:
    """Account names are "<org>-<suffix>"; emails use plus addressing on the management mailbox."""

    def __init__(self, answers: LandingZoneAnswers):
        self._organization = answers.organization_name
        self._local, self._domain = answers.management_email.split("@")

    def account(self, suffix: str) -> AccountPlan:
        return AccountPlan(name=f"{self._organization}-{suffix}", email=f"{self._local}+{suffix}@{self._domain}")


class AnswerHandler(ABC):
    """Turns part of the questionnaire into OUs and accounts. New questions add a handler."""

    @abstractmethod
    def contribute(self, answers: LandingZoneAnswers, catalog: OrgCatalog, design: LandingZoneDesign) -> None:
        ...


class SecurityHandler(AnswerHandler):
    def contribute(self, answers, catalog, design):
        namer = AccountNamer(answers)
        suffixes = ["log-archive", "audit", *(["security-tooling"] if answers.security_tooling else [])]
        design.root_ous.append(OuNode(key="security", name="Security", kind="security", created_by_control_tower=True,
                                      accounts=[namer.account(suffix) for suffix in suffixes]))


class InfrastructureHandler(AnswerHandler):
    def contribute(self, answers, catalog, design):
        namer = AccountNamer(answers)
        accounts = [namer.account(suffix) for key, suffix in INFRASTRUCTURE_ACCOUNTS.items()
                    if key in answers.infrastructure]
        design.root_ous.append(OuNode(key="infrastructure", name="Infrastructure", kind="infrastructure",
                                      accounts=accounts))


class EnvironmentHandler(AnswerHandler):
    """One OU per environment, directly under the root or under Prod/NonProd parents."""

    def contribute(self, answers, catalog, design):
        environments = answers.environments()
        design.root_ous += [self._ou(answers, catalog, environment) for environment in environments
                            if environment.tier == "sandbox"]
        workloads = [self._ou(answers, catalog, environment) for environment in environments
                     if environment.tier != "sandbox"]
        design.root_ous += workloads if answers.grouping == "separate" else self._parents(workloads)

    def _ou(self, answers: LandingZoneAnswers, catalog: OrgCatalog, environment: EnvironmentAnswer) -> OuNode:
        return OuNode(key=environment.id, name=environment.name, kind="environment", environment=environment.id,
                      tier=environment.tier, created_by_control_tower=environment.tier == "sandbox",
                      accounts=self._accounts(answers, catalog, environment))

    def _accounts(self, answers, catalog, environment) -> list[AccountPlan]:
        namer = AccountNamer(answers)
        suffix = environment.name.lower()
        if environment.tier == "sandbox":
            return self._sandbox_accounts(answers, catalog, namer)
        if answers.account_model == "environment":
            return [namer.account(suffix)]
        owners = catalog.portfolios if answers.account_model == "portfolio" else catalog.products
        return [namer.account(f"{_short(owner)}-{suffix}") for owner in owners]

    def _sandbox_accounts(self, answers, catalog, namer) -> list[AccountPlan]:
        if answers.sandbox.model == "developer":
            return [namer.account("developer-sandbox-01")]
        return [namer.account(f"{_short(portfolio)}-sandbox") for portfolio in catalog.portfolios]

    def _parents(self, workloads: list[OuNode]) -> list[OuNode]:
        return [OuNode(key=f"parent_{tier}", name=name, kind="parent", tier=tier,
                       children=[ou for ou in workloads if ou.tier == tier])
                for tier, name in (("nonprod", "NonProd"), ("prod", "Prod"))]


class ComplianceHandler(AnswerHandler):
    """Each regulated scope gets its own OU with STAGE and PROD child OUs and stricter controls."""

    def contribute(self, answers, catalog, design):
        namer = AccountNamer(answers)
        for scope in answers.compliance:
            children = [OuNode(key=f"{scope.lower()}_{environment}", name=f"{scope}-{environment.upper()}",
                               kind="environment", environment=environment, tier="prod",
                               accounts=[namer.account(f"{scope.lower()}-{environment}")])
                        for environment in ("stage", "prod")]
            design.root_ous.append(OuNode(key=scope.lower(), name=scope, kind="compliance", tier="prod",
                                          children=children))


class AutomationsHandler(AnswerHandler):
    def contribute(self, answers, catalog, design):
        if "cicd" in answers.infrastructure:
            design.root_ous.append(OuNode(key="automations", name="Automations", kind="automations",
                                          accounts=[AccountNamer(answers).account("cicd")]))


class PolicyStagingHandler(AnswerHandler):
    def contribute(self, answers, catalog, design):
        design.root_ous.append(OuNode(key="policy_staging", name="Policy Staging", kind="policy_staging"))


class OptionalOuHandler(AnswerHandler):
    def contribute(self, answers, catalog, design):
        design.root_ous += [OuNode(key=key, name=name, kind=key)
                            for option, (name, key) in OPTIONAL_OUS.items() if option in answers.optional_ous]


class LandingZoneDesigner:
    def __init__(self, handlers: list[AnswerHandler]):
        self._handlers = handlers

    @classmethod
    def default(cls) -> "LandingZoneDesigner":
        return cls([SecurityHandler(), InfrastructureHandler(), EnvironmentHandler(), ComplianceHandler(),
                    AutomationsHandler(), PolicyStagingHandler(), OptionalOuHandler()])

    def design(self, answers: LandingZoneAnswers, catalog: OrgCatalog) -> LandingZoneDesign:
        design = LandingZoneDesign(answers=answers)
        for handler in self._handlers:
            handler.contribute(answers, catalog, design)
        return design


def _short(registry_id: str) -> str:
    return registry_id.split("-", 1)[-1]
