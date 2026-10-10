"""Connector interface. Owner: A (interface changes need lead review: other modules depend on it)."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

from app.core import clock
from app.core.ids import new_id
from app.schemas import (
    PAYLOAD_MODELS,
    ConnectorEnvelope,
    ConnectorHealth,
    ConnectorInfo,
    ContractModel,
    PayloadType,
    SourceType,
)

_MODEL_TO_PAYLOAD = {model: ptype for ptype, model in PAYLOAD_MODELS.items()}


class BaseConnector(ABC):
    name: ClassVar[str]  # unique implementation name, e.g. "email.mock"
    source: ClassVar[SourceType]
    mode: ClassVar[str]  # "mock" | "live"
    description: ClassVar[str] = ""

    def __init__(self) -> None:
        self.last_sync_at: datetime | None = None
        self.last_error: str | None = None

    @abstractmethod
    def fetch(self, since: datetime | None = None) -> list[ConnectorEnvelope]:
        """Return new/changed items since `since` (None = everything available). Must not write to the repo."""

    def health(self) -> ConnectorHealth:
        return ConnectorHealth.ok

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            source=self.source,
            connector=self.name,
            mode=self.mode,
            health=self.health(),
            description=self.description,
            last_sync_at=self.last_sync_at,
            last_error=self.last_error,
        )

    def wrap(self, payload: ContractModel, external_id: str | None = None) -> ConnectorEnvelope:
        return ConnectorEnvelope(
            envelope_id=new_id("env"),
            source=self.source,
            connector=self.name,
            fetched_at=clock.now(),
            external_id=external_id,
            payload_type=_MODEL_TO_PAYLOAD[type(payload)],
            payload=payload,
        )


def payload_type_of(obj: ContractModel) -> PayloadType:
    return _MODEL_TO_PAYLOAD[type(obj)]
