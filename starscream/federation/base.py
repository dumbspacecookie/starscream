from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FederatedRecord:
    external_id: str
    external_url: str
    taxonomy_code: str
    lat: float
    lng: float
    recorded_at: datetime
    license: str
    title: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    location_name: str | None = None
    country_code: str | None = None
    duration_s: float | None = None
    preview_url: str | None = None
    source_object: str | None = None
    source_action: str | None = None
    username: str | None = None


class FederationConnector(ABC):
    slug: str

    @abstractmethod
    async def harvest_page(self, page: int, page_size: int) -> list[FederatedRecord]:
        """Fetch a page of records from the external source."""

    @abstractmethod
    async def download_preview(self, record: FederatedRecord) -> bytes | None:
        """Download preview audio when local copy is permitted."""
