import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from app.api.container import ServiceContainer
from app.errors import BadRequestError, NotFoundError
from app.registry.service import CostCenterChange
from app.synth.catalog import ServiceCatalog
from app.synth.request import ProjectRequest

Services = Annotated[ServiceContainer, Depends(ServiceContainer.provide)]
DEFAULT_ACTOR = "local-user"


class RegionUpdate(BaseModel):
    enabled: bool


class HealthRouter:
    def __init__(self):
        self.router = APIRouter(tags=["health"])
        self.router.add_api_route("/healthz", self.health, methods=["GET"])

    def health(self) -> dict:
        return {"status": "ok"}


class CatalogRouter:
    def __init__(self, catalog: ServiceCatalog):
        self._catalog = catalog
        self.router = APIRouter(prefix="/v1", tags=["catalog"])
        self.router.add_api_route("/catalog", self.catalog, methods=["GET"])

    def catalog(self) -> list[dict]:
        return self._catalog.entries()


class RegistryRouter:
    def __init__(self):
        self.router = APIRouter(prefix="/v1", tags=["registry"])
        self.router.add_api_route("/org-registry", self.org_registry, methods=["GET"])
        self.router.add_api_route("/environments", self.environments, methods=["GET"])
        self.router.add_api_route("/admin/regions", self.regions, methods=["GET"])
        self.router.add_api_route("/admin/regions/{region_id}", self.update_region, methods=["PUT"])
        self.router.add_api_route("/admin/cost-centers", self.cost_centers, methods=["GET"])
        self.router.add_api_route("/admin/cost-centers", self.update_cost_centers, methods=["PUT"])

    def org_registry(self, services: Services) -> list[dict]:
        return services.registry.org_registry()

    def environments(self, services: Services) -> list[dict]:
        return services.registry.environments()

    def regions(self, services: Services) -> list[dict]:
        return services.registry.regions()

    def update_region(self, region_id: str, update: RegionUpdate, services: Services) -> dict:
        return services.registry.set_region_enabled(region_id, update.enabled)

    def cost_centers(self, services: Services) -> dict:
        return services.registry.cost_centers()

    def update_cost_centers(self, change: CostCenterChange, services: Services,
                            actor: Annotated[str, Header(alias="X-Actor")] = DEFAULT_ACTOR) -> dict:
        return services.registry.update_cost_centers(change, actor=actor)


class ProjectRouter:
    def __init__(self):
        self.router = APIRouter(prefix="/v1", tags=["projects"])
        self.router.add_api_route("/projects:preview", self.preview, methods=["POST"])
        self.router.add_api_route("/projects", self.create, methods=["POST"], status_code=202)
        self.router.add_api_route("/projects", self.projects, methods=["GET"])
        self.router.add_api_route("/jobs/{job_id}", self.job, methods=["GET"])

    def preview(self, request: ProjectRequest, services: Services) -> dict:
        return services.projects.preview(request)

    def create(self, request: ProjectRequest, services: Services,
               idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> dict:
        if not idempotency_key:
            raise BadRequestError("The Idempotency-Key header is required.")
        return {"job_id": str(services.projects.create(request, idempotency_key).id)}

    def projects(self, services: Services) -> list[dict]:
        return services.projects.projects()

    def job(self, job_id: uuid.UUID, services: Services) -> dict:
        job = services.jobs.get(job_id)
        if job is None:
            raise NotFoundError(f"Unknown job '{job_id}'.")
        steps = [{"sequence": step.sequence, "name": step.name, "state": step.state, "detail": step.detail}
                 for step in services.jobs.steps(job)]
        return {"id": str(job.id), "project_name": job.project_name, "state": job.state, "error": job.error,
                "steps": steps}
