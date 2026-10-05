import secrets

from sqlalchemy.orm import Session

from app.db import models
from app.errors import NotFoundError, ValidationFailedError
from app.networks.models import NetworkInput
from app.networks.repository import NetworkRepository
from app.providers.base import DEFAULT_PROVIDER
from app.provisioning.topology import RegionTopology
from app.registry.repository import RegistryRepository
from app.registry.service import require
from app.synth.request import ProjectRequest

NETWORK_ID_BYTES = 4


class NetworkService:
    """Organization networks: admin configuration, wizard options and per-environment/region resolution."""

    def __init__(self, networks: NetworkRepository, registry: RegistryRepository):
        self._networks = networks
        self._registry = registry

    @classmethod
    def for_session(cls, session: Session) -> "NetworkService":
        return cls(NetworkRepository(session), RegistryRepository(session))

    # ---- admin ----

    def networks(self, account_id: str | None = None, region: str | None = None) -> list[dict]:
        return [self.describe(network) for network in self._networks.all(account_id, region)]

    def create(self, network_input: NetworkInput) -> dict:
        network = models.Network(id=f"net-{secrets.token_hex(NETWORK_ID_BYTES)}")
        self._apply(network, network_input)
        self._networks.add(network)
        self._networks.commit()
        return self.describe(network)

    def update(self, network_id: str, network_input: NetworkInput) -> dict:
        network = require(self._networks.get(network_id), NotFoundError(f"Unknown network '{network_id}'."))
        self._apply(network, network_input)
        self._networks.commit()
        return self.describe(network)

    def register(self, network_id: str, network_input: NetworkInput) -> dict:
        """Creates or replaces a network with a known id (used for networks the landing zone created)."""
        existing = self._networks.get(network_id)
        network = existing or models.Network(id=network_id)
        self._apply(network, network_input)
        if existing is None:
            self._networks.add(network)
        self._networks.commit()
        return self.describe(network)

    def settings(self) -> dict:
        return {"attach_compute_by_default": self._registry.organization_settings().attach_compute_to_vpc}

    def update_settings(self, attach_compute_by_default: bool) -> dict:
        self._registry.organization_settings().attach_compute_to_vpc = attach_compute_by_default
        self._networks.commit()
        return self.settings()

    # ---- wizard ----

    def options(self, portfolio_id: str) -> list[dict]:
        regions = [region.id for region in self._registry.regions(DEFAULT_PROVIDER) if region.enabled]
        return [self._option(environment.id, region, account)
                for environment in self._registry.environments()
                if (account := self._registry.account_for(DEFAULT_PROVIDER, portfolio_id, environment.id)) is not None
                for region in regions]

    # ---- provisioning ----

    def resolve(self, request: ProjectRequest, topology: RegionTopology,
                accounts: dict[str, str]) -> dict[tuple[str, str], dict]:
        if not request.network.attach_compute:
            return {}
        return {(environment, region): self.describe(self._network_for(request, environment, region, accounts))
                for environment in request.environments for region in topology.regions_for(environment)}

    def describe(self, network: models.Network) -> dict:
        return {"id": network.id, "provider": network.provider, "name": network.name, "account_id": network.account_id,
                "region": network.region, "network_ref": network.network_ref, "cidr": network.cidr,
                "subnet_refs": network.subnet_refs, "firewall_refs": network.firewall_refs,
                "is_default": network.is_default}

    # ---- helpers ----

    def _apply(self, network: models.Network, network_input: NetworkInput) -> None:
        if network_input.is_default:
            self._networks.clear_default(network_input.account_id, network_input.region)
        for field, value in network_input.model_dump().items():
            setattr(network, field, value)

    def _option(self, environment_id: str, region: str, account_id: str) -> dict:
        networks = self._networks.all(account_id, region)
        default = next((network.id for network in networks if network.is_default), None)
        return {"environment": environment_id, "region": region, "account_id": account_id,
                "networks": [self.describe(network) for network in networks], "default_network_id": default}

    def _network_for(self, request: ProjectRequest, environment: str, region: str,
                     accounts: dict[str, str]) -> models.Network:
        account = accounts[environment]
        selection = request.network.selections.get(f"{environment}:{region}")
        network = self._selected(selection, account, region) if selection else self._networks.default_for(account, region)
        return require(network, ValidationFailedError(
            f"No network configured for {environment} in {region} (account {account}). Ask a platform engineer "
            "to add one in Admin → Networks."))

    def _selected(self, network_id: str, account: str, region: str) -> models.Network:
        network = require(self._networks.get(network_id), ValidationFailedError(f"Unknown network '{network_id}'."))
        if (network.account_id, network.region) != (account, region):
            raise ValidationFailedError(f"Network '{network_id}' does not belong to account {account} in {region}.")
        return network

