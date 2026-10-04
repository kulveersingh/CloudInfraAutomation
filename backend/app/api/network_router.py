from fastapi import APIRouter
from pydantic import BaseModel

from app.api.routers import Services
from app.networks.models import NetworkInput


class NetworkSettings(BaseModel):
    attach_compute_by_default: bool


class NetworkRouter:
    def __init__(self):
        self.router = APIRouter(prefix="/v1", tags=["networks"])
        self.router.add_api_route("/admin/networks", self.networks, methods=["GET"])
        self.router.add_api_route("/admin/networks", self.create, methods=["POST"], status_code=201)
        self.router.add_api_route("/admin/networks/{network_id}", self.update, methods=["PUT"])
        self.router.add_api_route("/admin/network-settings", self.settings, methods=["GET"])
        self.router.add_api_route("/admin/network-settings", self.update_settings, methods=["PUT"])
        self.router.add_api_route("/networks/options", self.options, methods=["GET"])

    def networks(self, services: Services, account_id: str | None = None, region: str | None = None) -> list[dict]:
        return services.networks.networks(account_id, region)

    def create(self, network: NetworkInput, services: Services) -> dict:
        return services.networks.create(network)

    def update(self, network_id: str, network: NetworkInput, services: Services) -> dict:
        return services.networks.update(network_id, network)

    def settings(self, services: Services) -> dict:
        return services.networks.settings()

    def update_settings(self, settings: NetworkSettings, services: Services) -> dict:
        return services.networks.update_settings(settings.attach_compute_by_default)

    def options(self, portfolio_id: str, services: Services) -> list[dict]:
        return services.networks.options(portfolio_id)
