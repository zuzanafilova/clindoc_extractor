import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_api_root_status():
    """Ensure the API is living and breathing."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

def test_api_empty_text_rejection():
    """Requirement: Behavior for empty input."""
    response = client.post("/extract", json={"text": ""})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_api_missing_text_field():
    """Requirement: Behavior for bad JSON (missing mandatory field)."""
    response = client.post("/extract", json={"not_text": "hello"})
    assert response.status_code == 422

def test_api_malformed_json():
    """Requirement: Behavior for non-JSON input."""
    response = client.post(
        "/extract", 
        content="This is not JSON", 
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422

def test_api_regex_solo_mode():
    """Verify that mode switching works via API."""
    response = client.post(
        "/extract?mode=regex", 
        json={"text": "TK 120/80"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["extractor_type"] == "REGEX"
    assert data["vitals"]["bp"] == "120/80"
