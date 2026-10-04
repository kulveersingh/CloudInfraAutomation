"""Industry templates: ready-made answers, OU edits and control packs. One YAML file per industry."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

from app.landing_zone.catalog.controls import CatalogError
from app.landing_zone.catalog.packs import UNORDERED, PackRegistry

TEMPLATES_DIRECTORY = Path(__file__).parent / "templates"


@dataclass(frozen=True)
class IndustryTemplate:
    id: str
    version: int
    name: str
    industry: str
    description: str
    frameworks: tuple[str, ...]
    answers: dict
    edits: list[dict]
    order: int = UNORDERED

    @classmethod
    def from_document(cls, document: dict) -> "IndustryTemplate":
        return cls(id=document["id"], version=document["version"], name=document["name"],
                   industry=document["industry"], description=document["description"],
                   frameworks=tuple(document["frameworks"]), answers=document["answers"], edits=document["edits"],
                   order=document.get("order", UNORDERED))


class TemplateRegistry:
    def __init__(self, templates: list[IndustryTemplate]):
        self._templates = {template.id: template
                           for template in sorted(templates, key=lambda template: (template.order, template.id))}

    @classmethod
    def load(cls, directory: Path, packs: PackRegistry) -> "TemplateRegistry":
        templates = [IndustryTemplate.from_document(yaml.safe_load(path.read_text()))
                     for path in sorted(directory.glob("*.yaml"))]
        for template in templates:
            for pack in template.answers.get("control_packs", []):
                if not packs.knows(pack):
                    raise CatalogError(f"Template '{template.id}' uses unknown control pack '{pack}'.")
        return cls(templates)

    @classmethod
    @cache
    def default(cls) -> "TemplateRegistry":
        return cls.load(TEMPLATES_DIRECTORY, PackRegistry.default())

    def all(self) -> list[IndustryTemplate]:
        return list(self._templates.values())

    def get(self, template_id: str) -> IndustryTemplate:
        if template_id not in self._templates:
            raise CatalogError(f"Unknown template '{template_id}'.")
        return self._templates[template_id]
