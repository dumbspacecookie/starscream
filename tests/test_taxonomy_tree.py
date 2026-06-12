from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.api.routes import taxonomy as taxonomy_routes
from starscream.db.session import get_db

client = TestClient(app)


def _node(code: str, label: str, parent_code: str | None = None, recording_count: int = 0):
    return SimpleNamespace(
        code=code,
        label=label,
        parent_code=parent_code,
        description=None,
        recording_count=recording_count,
    )


def test_build_tree_uses_parent_index_not_nested_scan():
    nodes = [
        _node("WILDLIFE", "Wildlife"),
        _node("WILDLIFE.BIRD", "Birds", "WILDLIFE"),
        _node("WILDLIFE.MAMMAL", "Mammals", "WILDLIFE"),
        _node("URBAN", "Urban"),
        _node("URBAN.TRAFFIC", "Traffic", "URBAN"),
    ]

    tree = taxonomy_routes._build_tree(nodes)

    assert [n.code for n in tree] == ["URBAN", "WILDLIFE"]
    wildlife = next(n for n in tree if n.code == "WILDLIFE")
    assert [c.code for c in wildlife.children] == ["WILDLIFE.BIRD", "WILDLIFE.MAMMAL"]
    urban = next(n for n in tree if n.code == "URBAN")
    assert [c.code for c in urban.children] == ["URBAN.TRAFFIC"]


def test_taxonomy_tree_endpoint_returns_nested_nodes():
    nodes = [
        _node("WILDLIFE", "Wildlife"),
        _node("WILDLIFE.BIRD", "Birds", "WILDLIFE", recording_count=3),
    ]

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = nodes
    mock_db = MagicMock()
    mock_db.execute.return_value = list_result

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.get("/v1/taxonomy")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["code"] == "WILDLIFE"
    assert data[0]["children"][0]["code"] == "WILDLIFE.BIRD"
    assert data[0]["children"][0]["recording_count"] == 3


def test_taxonomy_subtree_endpoint_returns_404_for_unknown_code():
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [_node("WILDLIFE", "Wildlife")]
    mock_db = MagicMock()
    mock_db.execute.return_value = list_result

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.get("/v1/taxonomy/UNKNOWN")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
