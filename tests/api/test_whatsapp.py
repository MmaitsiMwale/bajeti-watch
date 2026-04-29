from fastapi.testclient import TestClient

from api.main import app
from api.routes import whatsapp


def test_whatsapp_webhook_returns_twiml(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SKIP_TWILIO_AUTH", "true")
    monkeypatch.setattr(
        whatsapp,
        "run_agent",
        lambda message, channel: f"Reply for {message} on {channel}",
    )

    client = TestClient(app)
    response = client.post(
        "/webhook/whatsapp",
        data={
            "Body": "Kisumu roads",
            "From": "whatsapp:+254700000000",
            "ProfileName": "Test Citizen",
        },
    )

    assert response.status_code == 200
    assert "<Response>" in response.text
    assert "<Message>Reply for Kisumu roads on whatsapp</Message>" in response.text


def test_whatsapp_webhook_handles_empty_message(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SKIP_TWILIO_AUTH", "true")

    client = TestClient(app)
    response = client.post(
        "/webhook/whatsapp",
        data={
            "Body": "   ",
            "From": "whatsapp:+254700000000",
        },
    )

    assert response.status_code == 200
    assert "Send a county name" in response.text
