"""Federation harvest retry and per-page error isolation."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from starscream.federation.base import FederatedRecord
from starscream.federation.harvest import harvest_source
from starscream.federation.retry import with_retry


def _record(ext_id: str) -> FederatedRecord:
    from datetime import datetime, timezone

    return FederatedRecord(
        external_id=ext_id,
        external_url=f"https://example.com/sounds/{ext_id}",
        taxonomy_code="NATURAL",
        lat=0.0,
        lng=0.0,
        recorded_at=datetime.now(timezone.utc),
        license="CC0",
        title=f"Sound {ext_id}",
        source_object="test",
        source_action="test",
        duration_s=1.0,
    )


@pytest.mark.asyncio
async def test_with_retry_recovers_from_503():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            request = httpx.Request("GET", "https://example.com")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("down", request=request, response=response)
        return "ok"

    result = await with_retry(flaky, attempts=3, base_delay_s=0.01)
    assert result == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_harvest_continues_after_page_failure():
    db = MagicMock()
    source = MagicMock()
    source.slug = "noaa"
    db.execute.return_value.scalar_one_or_none.return_value = source

    connector = MagicMock()
    connector.harvest_page = AsyncMock(
        side_effect=[
            RuntimeError("upstream 503"),
            [_record("a"), _record("b")],
        ]
    )
    connector.download_preview = AsyncMock(return_value=None)

    with patch("starscream.federation.harvest.CONNECTORS", {"noaa": lambda: connector}):
        from starscream.federation.ingest import IngestResult

        with patch(
            "starscream.federation.harvest.ingest_federated_records",
            return_value=IngestResult(created=2, skipped=0, failed=0, errors=[]),
        ) as mock_ingest:
            result = await harvest_source(db, "noaa", pages=2, download_previews=False)

    assert mock_ingest.call_count == 1
    ingested = mock_ingest.call_args[0][2]
    assert len(ingested) == 2
    assert any("page 1" in err for err in result.errors)
