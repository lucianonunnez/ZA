"""The HTTP surface: web UI + the quote endpoint."""

from fastapi.testclient import TestClient

from copilot.api import app

client = TestClient(app)


def test_index_serves_web_ui():
    r = client.get("/")
    assert r.status_code == 200
    assert "Ascend Concierge Copilot" in r.text
    assert "Get recommendation" in r.text


def test_health_reports_provider():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "provider" in body


def test_quote_endpoint_returns_recommendation():
    r = client.post("/quote", json={"message": "NYC to London thursday business morning arrival"})
    assert r.status_code == 200
    d = r.json()
    assert d["brief"]["origin"] == "JFK"
    assert d["recommendation"]["recommended_index"] >= 0
    assert d["trace"]["calls"] > 0
