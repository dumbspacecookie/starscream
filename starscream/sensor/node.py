import hashlib
import secrets
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.api.geo import point_wkt
from starscream.db.models import SensorNode

SENSOR_NODE_STATE_KEY = "sensor_node"
NODE_TOKEN_HEADER = "X-Node-Token"


def extract_node_token(request) -> str | None:
    header_token = request.headers.get(NODE_TOKEN_HEADER)
    if header_token:
        return header_token.strip()

    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer sn_"):
        return auth[7:].strip()
    return None


def get_request_sensor_node(request) -> SensorNode | None:
    return getattr(request.state, SENSOR_NODE_STATE_KEY, None)


def hash_node_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_node_token() -> tuple[str, str, str]:
    """Return (raw_token, hash, prefix)."""
    raw = f"sn_{secrets.token_urlsafe(32)}"
    return raw, hash_node_token(raw), raw[:12]


class NodeRegistration(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    public_key: str = Field(..., min_length=16, max_length=4096)

    @field_validator("node_id")
    @classmethod
    def normalize_node_id(cls, value: str) -> str:
        return value.strip()


class NodeRegisterOut(BaseModel):
    node_id: str
    lat: float
    lng: float
    node_token: str
    mqtt_topic: str


def lookup_sensor_node(db: Session, node_token: str) -> SensorNode | None:
    token_hash = hash_node_token(node_token)
    return db.execute(
        select(SensorNode).where(
            SensorNode.token_hash == token_hash,
            SensorNode.is_active.is_(True),
        )
    ).scalar_one_or_none()


def register_sensor_node(db: Session, registration: NodeRegistration) -> tuple[SensorNode, str]:
    existing = db.get(SensorNode, registration.node_id)
    if existing:
        raise ValueError(f"Node already registered: {registration.node_id}")

    raw_token, token_hash, prefix = generate_node_token()
    node = SensorNode(
        node_id=registration.node_id,
        lat=registration.lat,
        lng=registration.lng,
        location=point_wkt(registration.lat, registration.lng),
        public_key=registration.public_key,
        token_hash=token_hash,
        token_prefix=prefix,
    )
    db.add(node)
    db.flush()
    return node, raw_token


def touch_sensor_node(db: Session, node: SensorNode) -> None:
    node.last_seen_at = datetime.now(timezone.utc)
    node.event_count += 1
    db.flush()
