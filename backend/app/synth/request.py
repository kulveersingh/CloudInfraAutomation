from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

PROJECT_NAME_PATTERN = r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$"
RESOURCE_ID_PATTERN = r"^[a-z][a-z0-9-]{0,19}$"
MIN_PROJECT_NAME_LENGTH = 3
MAX_PROJECT_NAME_LENGTH = 30
MAX_RESOURCES = 20

Classification = Literal["public", "internal", "confidential", "restricted"]
AccessLevel = Literal["read", "write", "readwrite"]
ResilienceMode = Literal["single", "dr", "ha"]
SelectionKey = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+:[a-z0-9-]+$")]


class ResourceSpec(BaseModel):
    id: str = Field(pattern=RESOURCE_ID_PATTERN)
    type: str
    config: dict = Field(default_factory=dict)


class ConnectionSpec(BaseModel):
    kind: str
    source: str
    target: str
    access: AccessLevel | None = None
    events: list[str] = Field(default_factory=list)  # empty: the provider's default (new objects)
    prefix: str = ""
    suffix: str = ""


class Ownership(BaseModel):
    portfolio_id: str
    product_id: str
    data_classification: Classification


class Resilience(BaseModel):
    mode: ResilienceMode = "single"
    primary_region: str = "us-east-1"
    secondary_region: str | None = None

    @property
    def is_multi_region(self) -> bool:
        return self.mode != "single"

    def selected_regions(self) -> list[str]:
        return [self.primary_region, self.secondary_region] if self.is_multi_region else [self.primary_region]


class NetworkChoice(BaseModel):
    """Whether compute joins the organization VPC, and which network per "environment:region" (default otherwise)."""

    attach_compute: bool = True
    selections: dict[SelectionKey, str] = Field(default_factory=dict)


class ProjectRequest(BaseModel):
    provider: str = "aws"
    project_name: str = Field(min_length=MIN_PROJECT_NAME_LENGTH, max_length=MAX_PROJECT_NAME_LENGTH,
                              pattern=PROJECT_NAME_PATTERN)
    ownership: Ownership
    resilience: Resilience = Field(default_factory=Resilience)
    environments: list[str] = Field(min_length=1)
    resources: list[ResourceSpec] = Field(min_length=1, max_length=MAX_RESOURCES)
    connections: list[ConnectionSpec] = Field(default_factory=list)
    network: NetworkChoice = Field(default_factory=NetworkChoice)

    def resource(self, resource_id: str) -> ResourceSpec | None:
        return next((resource for resource in self.resources if resource.id == resource_id), None)
