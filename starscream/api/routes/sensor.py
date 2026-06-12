import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from starscream.api.auth import API_KEY_HEADER, get_request_contributor
from starscream.db.session import get_db
from starscream.sensor.ingest import SensorEventIn, resolve_audio_bytes, submit_sensor_event
from starscream.sensor.mqtt_handler import topic_for_node
from starscream.sensor.node import (
    NodeRegisterOut,
    NodeRegistration,
    get_request_sensor_node,
    register_sensor_node,
)

router = APIRouter(prefix="/sensor", tags=["sensor"])


class SensorIngestOut(BaseModel):
    recording_id: UUID
    node_id: str
    spectral_hash: str
    mqtt_topic: str


@router.post("/register", response_model=NodeRegisterOut, status_code=201)
def register_node(
    body: NodeRegistration,
    db: Session = Depends(get_db),
):
    try:
        node, node_token = register_sensor_node(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.commit()
    return NodeRegisterOut(
        node_id=node.node_id,
        lat=node.lat,
        lng=node.lng,
        node_token=node_token,
        mqtt_topic=topic_for_node(node.node_id),
    )


@router.post("/ingest", response_model=SensorIngestOut, status_code=201)
async def ingest_sensor_event(
    request: Request,
    event_json: str = Form(..., description="Sensor event JSON (MQTT-compatible)"),
    audio: UploadFile | None = File(None, description="Optional raw audio file"),
    db: Session = Depends(get_db),
):
    try:
        event = SensorEventIn.model_validate(json.loads(event_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    contributor = get_request_contributor(request)
    sensor_node = get_request_sensor_node(request)
    if not contributor and not sensor_node:
        raise HTTPException(
            status_code=401,
            detail=(
                f"Contributor API key ({API_KEY_HEADER}) or node token "
                f"(X-Node-Token) required"
            ),
        )

    uploaded_audio = await audio.read() if audio else None
    if not uploaded_audio and not event.audio_url and not event.audio_base64:
        raise HTTPException(
            status_code=400,
            detail="Provide audio file upload, audio_url, or audio_base64",
        )

    audio_bytes = resolve_audio_bytes(event, uploaded_audio)
    recording = submit_sensor_event(
        db=db,
        event=event,
        audio_bytes=audio_bytes,
        node=sensor_node,
    )

    return SensorIngestOut(
        recording_id=recording.id,
        node_id=event.node_id,
        spectral_hash=recording.spectral_hash,
        mqtt_topic=topic_for_node(event.node_id),
    )
