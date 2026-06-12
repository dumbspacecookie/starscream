import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.config import get_settings
from starscream.db.models import Source
from starscream.federation.freesound import FreesoundConnector
from starscream.federation.inaturalist import INaturalistConnector
from starscream.federation.ingest import IngestResult, ingest_federated_records
from starscream.federation.internet_archive import InternetArchiveConnector
from starscream.federation.nasa import NASAConnector
from starscream.federation.noaa import NOAAConnector
from starscream.federation.retry import with_retry
from starscream.federation.xeno_canto import XenoCantoConnector

logger = logging.getLogger(__name__)

CONNECTORS = {
    "freesound": FreesoundConnector,
    "xeno-canto": XenoCantoConnector,
    "inaturalist": INaturalistConnector,
    "internet-archive": InternetArchiveConnector,
    "noaa": NOAAConnector,
    "nasa": NASAConnector,
}

_QUERY_AWARE = frozenset({"xeno-canto", "internet-archive"})


def make_connector(slug: str, query: str | None = None):
    cls = CONNECTORS[slug]
    if slug in _QUERY_AWARE and query:
        return cls(query=query)
    return cls()


async def harvest_source(
    db: Session,
    slug: str,
    *,
    pages: int = 1,
    page_size: int = 50,
    download_previews: bool | None = None,
    query: str | None = None,
) -> IngestResult:
    if download_previews is None:
        download_previews = not get_settings().catalog_only
    if slug not in CONNECTORS:
        raise ValueError(f"Unknown source: {slug}. Available: {list(CONNECTORS)}")

    source = db.execute(select(Source).where(Source.slug == slug)).scalar_one_or_none()
    if not source:
        raise ValueError(f"Source '{slug}' not seeded — run python -m starscream.seed")

    connector = make_connector(slug, query)
    all_records = []
    harvest_errors: list[str] = []

    for page in range(1, pages + 1):
        try:
            batch = await with_retry(
                lambda page=page: connector.harvest_page(page, page_size)
            )
        except Exception as exc:
            msg = f"page {page}: {exc}"
            harvest_errors.append(msg)
            logger.error("Harvest page failed for %s: %s", slug, msg)
            continue

        if download_previews:
            for record in batch:
                try:
                    preview = await with_retry(
                        lambda record=record: connector.download_preview(record)
                    )
                    if preview:
                        record._preview_bytes = preview  # type: ignore[attr-defined]
                except Exception as exc:
                    msg = f"{record.external_id} download: {exc}"
                    harvest_errors.append(msg)
                    logger.warning("Preview download failed for %s: %s", slug, msg)

        all_records.extend(batch)

    result = ingest_federated_records(
        db, source, all_records, download_audio=download_previews
    )
    result.errors.extend(harvest_errors)
    return result


def harvest_source_sync(
    db: Session,
    slug: str,
    **kwargs,
) -> IngestResult:
    return asyncio.run(harvest_source(db, slug, **kwargs))
