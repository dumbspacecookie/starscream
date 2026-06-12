from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from starscream.api.ws import resolve_stream_filter, run_ingest_stream

router = APIRouter(prefix="/stream", tags=["stream"])


@router.websocket("/ingest")
async def stream_ingest(websocket: WebSocket) -> None:
    await websocket.accept()
    stream_filter = await resolve_stream_filter(websocket)
    try:
        await run_ingest_stream(websocket, stream_filter)
    except WebSocketDisconnect:
        pass
