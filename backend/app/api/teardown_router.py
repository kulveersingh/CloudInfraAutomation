import uuid
from typing import Literal

from fastapi import APIRouter

from app.api.release_router import CurrentActor, Decision
from app.api.routers import Services
from app.teardown.service import TeardownRequest

BASE = "/projects/{project_name}/teardowns"


class TeardownRouter:
    """Teardown and restore (§21.9). Every environment is approved on its own."""

    def __init__(self):
        self.router = APIRouter(prefix="/v1", tags=["teardowns"])
        self.router.add_api_route("/teardowns", self.all, methods=["GET"])
        self.router.add_api_route(f"{BASE}:preview", self.preview, methods=["POST"])
        self.router.add_api_route(BASE, self.request, methods=["POST"], status_code=201)
        self.router.add_api_route(BASE, self.for_project, methods=["GET"])
        self.router.add_api_route(f"{BASE}/{{teardown_id}}", self.get, methods=["GET"])
        self.router.add_api_route(f"{BASE}/{{teardown_id}}/environments/{{environment}}:{{decision}}", self.decide,
                                  methods=["POST"])
        self.router.add_api_route(f"{BASE}/{{teardown_id}}:{{action}}", self.restore, methods=["POST"])

    def all(self, services: Services) -> list[dict]:
        return services.teardowns.teardowns()

    def preview(self, project_name: str, body: TeardownRequest, services: Services) -> dict:
        return services.teardowns.preview(project_name, body)

    def request(self, project_name: str, body: TeardownRequest, services: Services, actor: CurrentActor) -> dict:
        return services.teardowns.request(project_name, body, actor)

    def for_project(self, project_name: str, services: Services) -> list[dict]:
        return services.teardowns.for_project(project_name)

    def get(self, project_name: str, teardown_id: uuid.UUID, services: Services) -> dict:
        return services.teardowns.get(project_name, teardown_id)

    def decide(self, project_name: str, teardown_id: uuid.UUID, environment: str,
               decision: Literal["approve", "reject", "retry"], body: Decision, services: Services,
               actor: CurrentActor) -> dict:
        return services.teardowns.decide(project_name, teardown_id, environment, decision, actor, body.comment)

    def restore(self, project_name: str, teardown_id: uuid.UUID,
                action: Literal["restore", "approve-restore", "reject-restore"], services: Services,
                actor: CurrentActor) -> dict:
        return services.teardowns.restore(project_name, teardown_id, action, actor)
