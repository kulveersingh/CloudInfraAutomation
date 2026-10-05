from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import models


class NetworkRepository:
    def __init__(self, session: Session):
        self._session = session

    def all(self, account_id: str | None = None, region: str | None = None,
            provider: str | None = None) -> list[models.Network]:
        query = select(models.Network).order_by(models.Network.account_id, models.Network.region, models.Network.name)
        filters = [(models.Network.account_id, account_id), (models.Network.region, region),
                   (models.Network.provider, provider)]
        for column, value in filters:
            if value is not None:
                query = query.where(column == value)
        return list(self._session.scalars(query))

    def get(self, network_id: str) -> models.Network | None:
        return self._session.get(models.Network, network_id)

    def default_for(self, account_id: str, region: str) -> models.Network | None:
        return self._session.scalar(select(models.Network).where(
            models.Network.account_id == account_id, models.Network.region == region, models.Network.is_default))

    def clear_default(self, account_id: str, region: str) -> None:
        self._session.execute(update(models.Network).where(
            models.Network.account_id == account_id, models.Network.region == region).values(is_default=False))

    def add(self, network: models.Network) -> None:
        self._session.add(network)

    def commit(self) -> None:
        self._session.commit()
