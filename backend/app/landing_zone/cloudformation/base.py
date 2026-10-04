from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.landing_zone.cloudformation.guardrails import GuardrailPlan
from app.landing_zone.cloudformation.references import OuReferences
from app.landing_zone.design import LandingZoneDesign, OrgCatalog

FORMAT_VERSION = "2010-09-09"


@dataclass
class StackContext:
    design: LandingZoneDesign
    catalog: OrgCatalog
    references: OuReferences
    guardrails: GuardrailPlan

    @classmethod
    def build(cls, design: LandingZoneDesign, catalog: OrgCatalog) -> "StackContext":
        return cls(design, catalog, OuReferences(design), GuardrailPlan.for_design(design, catalog))


class StackRenderer(ABC):
    """One CloudFormation stack of the landing zone. New stacks plug into LandingZoneBundle."""

    name: str
    description: str

    @abstractmethod
    def sections(self, context: StackContext) -> dict:
        """Parameters/Mappings/Conditions/Resources/Outputs for this stack."""

    def render(self, context: StackContext) -> dict:
        return {"AWSTemplateFormatVersion": FORMAT_VERSION, "Description": self.description, **self.sections(context)}


def export(context: StackContext, suffix: str, value) -> dict:
    return {"Value": value, "Export": {"Name": context.references.exports.name(suffix)}}
