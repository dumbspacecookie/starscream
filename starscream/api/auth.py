import hashlib
import secrets
import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.config import get_settings
from starscream.db.models import Contributor
from starscream.db.session import get_db

API_KEY_HEADER = "X-API-Key"
CONTRIBUTOR_STATE_KEY = "contributor"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return (raw_key, hash, prefix)."""
    raw = f"ss_{secrets.token_urlsafe(32)}"
    return raw, hash_api_key(raw), raw[:12]


def extract_api_key(request: Request) -> str | None:
    header_key = request.headers.get(API_KEY_HEADER)
    if header_key:
        return header_key.strip()

    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def lookup_contributor(db: Session, api_key: str) -> Contributor | None:
    key_hash = hash_api_key(api_key)
    return db.execute(
        select(Contributor).where(
            Contributor.api_key_hash == key_hash,
            Contributor.is_active.is_(True),
        )
    ).scalar_one_or_none()


def get_request_contributor(request: Request) -> Contributor | None:
    return getattr(request.state, CONTRIBUTOR_STATE_KEY, None)


def client_ip(request: Request) -> str:
    """Client IP for rate limiting and anonymous review keys."""
    settings = get_settings()
    if settings.api_trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def reviewer_key(request: Request) -> str:
    contributor = get_request_contributor(request)
    if contributor:
        return f"contrib:{contributor.id}"
    return f"ip:{client_ip(request)}"


def require_reviewer(
    request: Request,
    db: Session = Depends(get_db),
) -> Contributor | None:
    """Require contributor or admin API key for peer-review actions."""
    api_key = extract_api_key(request)
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail=f"Contributor API key required (header {API_KEY_HEADER})",
        )

    contributor = lookup_contributor(db, api_key)
    if contributor:
        setattr(request.state, CONTRIBUTOR_STATE_KEY, contributor)
        return contributor

    settings = get_settings()
    if settings.admin_api_key and secrets.compare_digest(api_key, settings.admin_api_key):
        return None

    raise HTTPException(status_code=401, detail="Invalid or inactive API key")


def require_admin(request: Request) -> None:
    settings = get_settings()
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="Admin API not configured")
    provided = extract_api_key(request)
    if not provided or provided != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin API key")


def create_contributor(
    db: Session,
    display_name: str,
    github_username: str | None = None,
) -> tuple[Contributor, str]:
    raw_key, key_hash, prefix = generate_api_key()
    contributor = Contributor(
        id=uuid.uuid4(),
        display_name=display_name,
        github_username=github_username,
        api_key_hash=key_hash,
        api_key_prefix=prefix,
    )
    db.add(contributor)
    db.flush()
    return contributor, raw_key
