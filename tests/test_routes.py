import json

def test_status_endpoint(client):
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert "webhook_url" in data
    assert "widget_url" in data
    assert "test_url" in data
    # URLs should contain the PORT default used in config (5002)
    assert ":5002" in data["webhook_url"] or ":5002" in data["widget_url"]


def test_test_donation_get_redirect(client):
    # Test that endpoint redirects to /dashboard.
    # TestClient follows redirects by default; inspect response.history for the redirect.
    resp = client.get("/test-donation")
    # Ensure a redirect occurred
    assert resp.history, "expected redirect history"
    first = resp.history[0]
    assert first.status_code in (301, 302, 307, 308)
    # Requests uses 'Location' header for redirects
    assert first.headers.get("Location") == "/dashboard"


def test_test_donation_post_generates_video_when_above_threshold(client):
    payload = {
        "donor_name": "Alice",
        "amount": 20,       # USD in our stub will be multiplied by 70 => 1400 RUB
        "currency": "USD",
        "message": "Test",
        "generate_video": True
    }
    resp = client.post("/test-donation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    # Our VideoGeneratorStub in tests/conftest returns a video_path when generation is requested
    assert "video_path" in data
    assert data["amount_rub"] >= 1000


def test_test_donation_post_no_video_below_threshold(client):
    payload = {
        "donor_name": "Bob",
        "amount": 1,        # USD -> 70 RUB (below default threshold 1000)
        "currency": "USD",
        "generate_video": True
    }
    resp = client.post("/test-donation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    # When below threshold, no video_path should be returned
    assert "video_path" not in data
    assert data["amount_rub"] < 1000


def test_test_donation_post_bad_json_returns_error(client):
    # Send invalid JSON body (empty body with JSON content-type triggers JSON parse error)
    resp = client.post("/test-donation", data="", headers={"content-type": "application/json"})
    assert resp.status_code == 200
    data = resp.json()
    # The endpoint returns {"success": False, "error": "..."} on exceptions
    assert data.get("success") is False
    assert "error" in data
