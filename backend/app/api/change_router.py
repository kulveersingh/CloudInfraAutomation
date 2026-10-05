import uuid

from fastapi import APIRouter

from app.api.release_router import CurrentActor
from app.api.routers import Services
from app.projects.changes import ChangeRequest

BASE = "/projects/{project_name}/changes"


class ChangeRouter:
    """Change infrastructure (§21.8). Merge and close stand in for GitHub only when running locally."""

    def __init__(self, simulation_enabled: bool):
        self.router = APIRouter(prefix="/v1", tags=["projects"])
        self.router.add_api_route(f"{BASE}:preview", self.preview, methods=["POST"])
        self.router.add_api_route(BASE, self.create, methods=["POST"], status_code=202)
        self.router.add_api_route(BASE, self.changes, methods=["GET"])
        self.router.add_api_route(f"{BASE}/{{change_id}}", self.get, methods=["GET"])
        if simulation_enabled:
            self.router.add_api_route(f"{BASE}/{{change_id}}:merge", self.merge, methods=["POST"])
            self.router.add_api_route(f"{BASE}/{{change_id}}:close", self.close, methods=["POST"])

    def preview(self, project_name: str, change: ChangeRequest, services: Services) -> dict:
        return services.project_changes.preview(project_name, change)

    def create(self, project_name: str, change: ChangeRequest, services: Services, actor: CurrentActor) -> dict:
        return services.project_changes.create(project_name, change, actor.name)

    def changes(self, project_name: str, services: Services) -> list[dict]:
        return services.project_changes.changes(project_name)

    def get(self, project_name: str, change_id: uuid.UUID, services: Services) -> dict:
        return services.project_changes.get(project_name, change_id)

    def merge(self, project_name: str, change_id: uuid.UUID, services: Services) -> dict:
        return services.project_changes.merge(project_name, change_id)

    def close(self, project_name: str, change_id: uuid.UUID, services: Services) -> dict:
        return services.project_changes.close(project_name, change_id)
