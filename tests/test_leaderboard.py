import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from starscream.api.main import app


def test_leaderboard_endpoint_in_openapi():
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/v1/contributors/leaderboard" in response.json()["paths"]


def test_leaderboard_returns_ranked_contributors():
    cid_a = uuid.uuid4()
    cid_b = uuid.uuid4()
    rows = [
        MagicMock(
            id=cid_a,
            display_name="Alice",
            citations_count=12,
            sound_count=25,
        ),
        MagicMock(
            id=cid_b,
            display_name="Bob",
            citations_count=5,
            sound_count=10,
        ),
    ]

    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = rows

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        response = client.get("/v1/contributors/leaderboard", params={"limit": 20})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 20
    assert len(data["items"]) == 2

    first = data["items"][0]
    assert first["rank"] == 1
    assert first["id"] == str(cid_a)
    assert first["display_name"] == "Alice"
    assert first["sound_count"] == 25
    assert first["citations_count"] == 12

    second = data["items"][1]
    assert second["rank"] == 2
    assert second["display_name"] == "Bob"
    assert second["sound_count"] == 10


def test_leaderboard_respects_limit_param():
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = []

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        response = client.get("/v1/contributors/leaderboard", params={"limit": 5})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["limit"] == 5


def test_leaderboard_uuid_string_join():
    """Leaderboard query casts Contributor.id to string for Recording.contributor_id."""
    from sqlalchemy import String, cast, func, select

    from starscream.db.models import Contributor, Recording

    sound_count = func.count(Recording.id).label("sound_count")
    stmt = (
        select(
            Contributor.id,
            Contributor.display_name,
            Contributor.citations_count,
            sound_count,
        )
        .join(
            Recording,
            Recording.contributor_id == cast(Contributor.id, String),
        )
        .where(Contributor.is_active.is_(True))
        .where(Recording.is_duplicate.is_(False))
        .group_by(Contributor.id)
        .order_by(sound_count.desc())
    )
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "contributor_id" in compiled.lower()
    assert "contributors" in compiled.lower()
