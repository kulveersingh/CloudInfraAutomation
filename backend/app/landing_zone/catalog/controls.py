"""The Control Catalog snapshot: the Control Tower controls the packs use, with their framework mappings."""

from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).with_name("controls.yaml")
HEADER = ("# Control Catalog snapshot: the controls the packs use. Refresh with\n"
          "#   uv run --with boto3 python -m app.providers.aws.landing_zone.refresh\n"
          "# which also fills each control's framework mappings (ListControlMappings) and the id of the\n"
          "# CloudFormation-hooks prerequisite (CT.CLOUDFORMATION.PR.1) that proactive controls need.\n")


class CatalogError(ValueError):
    """The catalog files reference something that doesn't exist."""


@dataclass(frozen=True)
class CatalogControl:
    id: str
    name: str
    behavior: str
    severity: str
    implementation: str
    frameworks: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ()

    @property
    def is_scp(self) -> bool:
        return self.implementation == "SCP"

    @property
    def is_preventive(self) -> bool:
        return self.behavior == "PREVENTIVE"

    @property
    def is_proactive(self) -> bool:
        return self.behavior == "PROACTIVE"

    @classmethod
    def from_document(cls, control_id: str, document: dict) -> "CatalogControl":
        return cls(id=control_id, name=document["name"], behavior=document["behavior"], severity=document["severity"],
                   implementation=document["implementation"], frameworks=tuple(document.get("frameworks", ())),
                   parameters=tuple(document.get("parameters", ())))

    def to_document(self) -> dict:
        document = {"name": self.name, "behavior": self.behavior, "severity": self.severity,
                    "implementation": self.implementation}
        optional = {"frameworks": list(self.frameworks), "parameters": list(self.parameters)}
        return {**document, **{key: value for key, value in optional.items() if value}}


class ControlCatalogSnapshot:
    def __init__(self, controls: dict[str, CatalogControl], mappings_refreshed: str | None,
                 proactive_prerequisite: CatalogControl | None, source: str = ""):
        self.controls = controls
        self.mappings_refreshed = mappings_refreshed
        self.proactive_prerequisite = proactive_prerequisite
        self.source = source

    @classmethod
    def load(cls, path: Path) -> "ControlCatalogSnapshot":
        document = yaml.safe_load(path.read_text())
        controls = {control_id: CatalogControl.from_document(control_id, body)
                    for control_id, body in document["controls"].items()}
        prerequisite = document["prerequisites"]["proactive"]
        return cls(controls, document["mappings_refreshed"], controls[prerequisite] if prerequisite else None,
                   document.get("source", ""))

    @classmethod
    @cache
    def default(cls) -> "ControlCatalogSnapshot":
        return cls.load(DEFAULT_PATH)

    def get(self, control_id: str) -> CatalogControl:
        if control_id not in self.controls:
            raise CatalogError(f"Unknown control '{control_id}'.")
        return self.controls[control_id]

    def with_proactive_prerequisite(self, control: CatalogControl) -> "ControlCatalogSnapshot":
        return ControlCatalogSnapshot({**self.controls, control.id: control}, self.mappings_refreshed, control,
                                      self.source)

    def refreshed(self, controls: dict[str, CatalogControl], prerequisite: CatalogControl | None, today: str,
                  source: str) -> "ControlCatalogSnapshot":
        merged = {**self.controls, **controls, **({prerequisite.id: prerequisite} if prerequisite else {})}
        return ControlCatalogSnapshot(merged, today, prerequisite or self.proactive_prerequisite, source)

    def write(self, path: Path) -> None:
        prerequisite = self.proactive_prerequisite.id if self.proactive_prerequisite else None
        document = {"source": self.source, "mappings_refreshed": self.mappings_refreshed,
                    "prerequisites": {"proactive": prerequisite},
                    "controls": {control_id: control.to_document() for control_id, control in self.controls.items()}}
        path.write_text(HEADER + yaml.safe_dump(document, sort_keys=False, width=120, allow_unicode=True))


def renamed(control: CatalogControl, summary: dict, frameworks: set[str]) -> CatalogControl:
    """The snapshot entry updated from a ListControls summary and its ListControlMappings frameworks."""
    return replace(control, name=summary["Name"], severity=summary["Severity"],
                   frameworks=tuple(sorted(frameworks)) or control.frameworks)
