"""WebSocket helpers for the ingest stream."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from starscream.events import StreamFilter, get_broadcaster


def _optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def parse_stream_filter_from_mapping(data: Mapping[str, Any]) -> StreamFilter:
    taxonomy_prefix = data.get("taxonomy_prefix") or data.get("taxonomy")
    if taxonomy_prefix is not None:
        taxonomy_prefix = str(taxonomy_prefix).strip() or None

    lat = data.get("lat")
    lng = data.get("lng")
    radius_km = data.get("radius_km", data.get("radius"))

    return StreamFilter(
        taxonomy_prefix=taxonomy_prefix,
        lat=float(lat) if lat is not None else None,
        lng=float(lng) if lng is not None else None,
        radius_km=float(radius_km) if radius_km is not None else None,
    )


def parse_stream_filter_from_query(query: Mapping[str, str]) -> StreamFilter:
    return StreamFilter(
        taxonomy_prefix=(query.get("taxonomy_prefix") or query.get("taxonomy") or None),
        lat=_optional_float(query.get("lat")),
        lng=_optional_float(query.get("lng")),
        radius_km=_optional_float(query.get("radius_km") or query.get("radius")),
    )


async def resolve_stream_filter(websocket: WebSocket) -> StreamFilter:
    stream_filter = parse_stream_filter_from_query(websocket.query_params)
    if any(
        (
            stream_filter.taxonomy_prefix,
            stream_filter.lat is not None,
            stream_filter.lng is not None,
            stream_filter.radius_km is not None,
        )
    ):
        return stream_filter

    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=2.0)
    except (TimeoutError, asyncio.TimeoutError, WebSocketDisconnect):
        return stream_filter

    if isinstance(message, dict):
        return parse_stream_filter_from_mapping(message)
    return stream_filter


async def run_ingest_stream(websocket: WebSocket, stream_filter: StreamFilter) -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    loop = asyncio.get_running_loop()

    def deliver(summary: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, summary)

    sub_id = get_broadcaster().subscribe(stream_filter, deliver)
    try:
        await websocket.send_json({"type": "subscribed", "filter": stream_filter.as_dict()})
        while True:
            summary = await queue.get()
            await websocket.send_json({"type": "ingest", "recording": summary})
    finally:
        get_broadcaster().unsubscribe(sub_id)
