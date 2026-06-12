from fastapi.testclient import TestClient

from starscream.api.main import app

client = TestClient(app)


def test_explore_page_returns_200():
    response = client.get("/explore")
    assert response.status_code == 200
    assert "Starscream" in response.text
    assert "/v1/search" in response.text


def test_upload_page_returns_200():
    response = client.get("/upload")
    assert response.status_code == 200
    assert "Starscream" in response.text


def test_recording_page_returns_200():
    response = client.get("/recording")
    assert response.status_code == 200
    assert "/v1/recordings/" in response.text
    assert "/similar" in response.text


def test_stats_page_returns_200():
    response = client.get("/stats")
    assert response.status_code == 200
    assert "/v1/stats" in response.text


def test_root_redirects_to_explore():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (301, 302, 307, 308)
    assert response.headers["location"] == "/explore"


def test_contributors_page_returns_200():
    response = client.get("/contributors-page")
    assert response.status_code == 200
    assert "Starscream" in response.text
    assert "/v1/contrib/register" in response.text


def test_leaderboard_page_returns_200():
    response = client.get("/leaderboard")
    assert response.status_code == 200
    assert "Starscream" in response.text
    assert "/v1/contributors/leaderboard" in response.text


def test_batch_page_returns_200():
    response = client.get("/batch")
    assert response.status_code == 200
    assert "Starscream" in response.text
    assert "validate-batch" in response.text


def test_mobile_page_returns_200():
    response = client.get("/mobile")
    assert response.status_code == 200
    assert "Starscream" in response.text
    assert "/v1/contrib/upload" in response.text


def test_webmanifest_returns_200():
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert "Starscream Field Recorder" in response.text
