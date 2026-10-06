import uuid

from fastapi import APIRouter, Response

from app.api.release_router import CurrentActor, Decision
from app.api.routers import Services
from app.landing_zone.request import LandingZoneRequest
from app.providers.base import DEFAULT_PROVIDER

BASE = "/admin/landing-zone"


class LandingZoneRouter:
    def __init__(self):
        self.router = APIRouter(prefix="/v1", tags=["landing-zone"])
        self.router.add_api_route(f"{BASE}/templates", self.templates, methods=["GET"])
        self.router.add_api_route(f"{BASE}/templates/{{template_id}}", self.template, methods=["GET"])
        self.router.add_api_route(f"{BASE}/control-packs", self.control_packs, methods=["GET"])
        self.router.add_api_route(f"{BASE}/repository:read-back", self.read_back, methods=["GET"])
        self.router.add_api_route(f"{BASE}:propose", self.propose, methods=["POST"])
        self.router.add_api_route(f"{BASE}/designs", self.create, methods=["POST"], status_code=201)
        self.router.add_api_route(f"{BASE}/designs", self.designs, methods=["GET"])
        self.router.add_api_route(f"{BASE}/designs/{{design_id}}", self.get, methods=["GET"])
        self.router.add_api_route(f"{BASE}/designs/{{design_id}}/diagram.svg", self.diagram, methods=["GET"])
        self.router.add_api_route(f"{BASE}/designs/{{design_id}}:submit", self.submit, methods=["POST"])
        self.router.add_api_route(f"{BASE}/designs/{{design_id}}:approve", self.approve, methods=["POST"])
        self.router.add_api_route(f"{BASE}/designs/{{design_id}}:reject", self.reject, methods=["POST"])

    def templates(self, services: Services, actor: CurrentActor, provider: str = DEFAULT_PROVIDER) -> list[dict]:
        return services.landing_zone.templates(actor, provider)

    def template(self, template_id: str, services: Services, actor: CurrentActor,
                 provider: str = DEFAULT_PROVIDER) -> dict:
        return services.landing_zone.template(template_id, actor, provider)

    def control_packs(self, services: Services, actor: CurrentActor, provider: str = DEFAULT_PROVIDER) -> dict:
        return services.landing_zone.control_packs(actor, provider)

    def read_back(self, services: Services, actor: CurrentActor, provider: str = DEFAULT_PROVIDER) -> dict:
        return services.read_back.read(services.landing_zone.repository_subject(actor, provider)).as_dict()

    def propose(self, request: LandingZoneRequest, services: Services, actor: CurrentActor) -> dict:
        return services.landing_zone.propose(request, actor)

    def create(self, request: LandingZoneRequest, services: Services, actor: CurrentActor) -> dict:
        return services.landing_zone.create(request, actor)

    def designs(self, services: Services, actor: CurrentActor, provider: str | None = None) -> list[dict]:
        return services.landing_zone.designs(actor, provider)

    def get(self, design_id: uuid.UUID, services: Services, actor: CurrentActor) -> dict:
        return services.landing_zone.get(design_id, actor)

    def diagram(self, design_id: uuid.UUID, services: Services, actor: CurrentActor) -> Response:
        return Response(services.landing_zone.diagram(design_id, actor), media_type="image/svg+xml")

    def submit(self, design_id: uuid.UUID, services: Services, actor: CurrentActor) -> dict:
        return services.landing_zone.submit(design_id, actor)

    def approve(self, design_id: uuid.UUID, decision: Decision, services: Services, actor: CurrentActor) -> dict:
        return services.landing_zone.approve(design_id, actor, decision.comment)

    def reject(self, design_id: uuid.UUID, decision: Decision, services: Services, actor: CurrentActor) -> dict:
        return services.landing_zone.reject(design_id, actor, decision.comment)
