import uuid

from fastapi import APIRouter, Response

from app.api.release_router import CurrentActor, Decision
from app.api.routers import Services
from app.landing_zone.request import LandingZoneRequest

BASE = "/admin/landing-zone"


class LandingZoneRouter:
    def __init__(self):
        self.router = APIRouter(prefix="/v1", tags=["landing-zone"])
        self.router.add_api_route(f"{BASE}:propose", self.propose, methods=["POST"])
        self.router.add_api_route(f"{BASE}/designs", self.create, methods=["POST"], status_code=201)
        self.router.add_api_route(f"{BASE}/designs", self.designs, methods=["GET"])
        self.router.add_api_route(f"{BASE}/designs/{{design_id}}", self.get, methods=["GET"])
        self.router.add_api_route(f"{BASE}/designs/{{design_id}}/diagram.svg", self.diagram, methods=["GET"])
        self.router.add_api_route(f"{BASE}/designs/{{design_id}}:submit", self.submit, methods=["POST"])
        self.router.add_api_route(f"{BASE}/designs/{{design_id}}:approve", self.approve, methods=["POST"])
        self.router.add_api_route(f"{BASE}/designs/{{design_id}}:reject", self.reject, methods=["POST"])

    def propose(self, request: LandingZoneRequest, services: Services, actor: CurrentActor) -> dict:
        return services.landing_zone.propose(request, actor)

    def create(self, request: LandingZoneRequest, services: Services, actor: CurrentActor) -> dict:
        return services.landing_zone.create(request, actor)

    def designs(self, services: Services, actor: CurrentActor) -> list[dict]:
        return services.landing_zone.designs(actor)

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
