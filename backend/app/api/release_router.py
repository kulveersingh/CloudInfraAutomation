import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from app.api.routers import Services
from app.releases.plan import PlanSubmission
from app.releases.policy import Actor


class RequestActor:
    """Resolves the acting person from headers (replaced by SSO claims in production)."""

    @classmethod
    def resolve(cls, x_actor: Annotated[str | None, Header()] = None,
                x_roles: Annotated[str | None, Header()] = None) -> Actor:
        return Actor.from_headers(x_actor, x_roles)


CurrentActor = Annotated[Actor, Depends(RequestActor.resolve)]


class Decision(BaseModel):
    comment: str = ""


class Simulation(BaseModel):
    environment: str
    high_risk: bool = False


class ReleaseRouter:
    def __init__(self, simulation_enabled: bool):
        self.router = APIRouter(prefix="/v1", tags=["releases"])
        self.router.add_api_route("/releases", self.submit_plan, methods=["POST"], status_code=201)
        self.router.add_api_route("/releases", self.releases, methods=["GET"])
        self.router.add_api_route("/releases/{release_id}", self.release, methods=["GET"])
        self.router.add_api_route("/releases/{release_id}:approve", self.approve, methods=["POST"])
        self.router.add_api_route("/releases/{release_id}:reject", self.reject, methods=["POST"])
        self.router.add_api_route("/releases/{release_id}:approve-override", self.approve_override, methods=["POST"])
        self.router.add_api_route("/approvals/inbox", self.inbox, methods=["GET"])
        self.router.add_api_route("/projects/{project_name}/pipeline", self.pipeline, methods=["GET"])
        if simulation_enabled:
            self.router.add_api_route("/projects/{project_name}/releases:simulate", self.simulate, methods=["POST"])

    def submit_plan(self, submission: PlanSubmission, services: Services) -> dict:
        return services.releases.submit_plan(submission)

    def simulate(self, project_name: str, simulation: Simulation, services: Services, actor: CurrentActor) -> dict:
        return services.releases.simulate(project_name, simulation.environment, actor, simulation.high_risk)

    def releases(self, services: Services, project: str | None = None) -> list[dict]:
        return services.releases.releases(project)

    def release(self, release_id: uuid.UUID, services: Services) -> dict:
        return services.releases.get(release_id)

    def approve(self, release_id: uuid.UUID, decision: Decision, services: Services, actor: CurrentActor) -> dict:
        return services.releases.approve(release_id, actor, decision.comment)

    def reject(self, release_id: uuid.UUID, decision: Decision, services: Services, actor: CurrentActor) -> dict:
        return services.releases.reject(release_id, actor, decision.comment)

    def approve_override(self, release_id: uuid.UUID, decision: Decision, services: Services,
                         actor: CurrentActor) -> dict:
        return services.releases.approve_override(release_id, actor, decision.comment)

    def inbox(self, services: Services, actor: CurrentActor) -> list[dict]:
        return services.releases.inbox(actor)

    def pipeline(self, project_name: str, services: Services) -> list[dict]:
        return services.releases.pipeline(project_name)
