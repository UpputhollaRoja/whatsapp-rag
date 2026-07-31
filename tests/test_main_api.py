import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from config import settings

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "WhatsApp RAG" in response.text


def test_verify_webhook_endpoint():
    response = client.get("/webhook", headers={"X-Webhook-Signature": "c5a947c0608d10de88108854e8c4d483"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_receive_webhook_endpoint():
    payload = {
        "event": "messages.received",
        "data": {
            "key": {"remoteJid": "919876543210@s.whatsapp.net", "fromMe": False},
            "messageBody": "@hello"
        }
    }
    response = client.post("/webhook", json=payload, headers={"X-Webhook-Signature": "c5a947c0608d10de88108854e8c4d483"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_receive_webhook_unauthorized():
    payload = {"event": "messages.received", "data": {}}
    response = client.post("/webhook", json=payload, headers={"X-Webhook-Secret": "invalid_secret_key"})
    assert response.status_code == 401
    assert "Unauthorized webhook request" in response.json()["detail"]


def test_web_chat_missing_phone():
    response = client.post("/api/chat", json={"message": "@hello"})
    assert response.status_code == 400
    assert "Phone number is required" in response.json()["detail"]


def test_internal_api_key_authentication():
    with patch.object(settings, "internal_api_key", "secret123"):
        # Without header -> 401
        res1 = client.get("/api/documents")
        assert res1.status_code == 401
        assert "Unauthorized" in res1.json()["detail"]

        # With wrong header -> 401
        res2 = client.get("/api/documents", headers={"X-API-Key": "wrong"})
        assert res2.status_code == 401

        # With correct header -> 200
        with patch("main.supabase") as mock_supabase:
            mock_query = MagicMock()
            mock_query.execute.return_value.data = []
            mock_supabase.table.return_value.select.return_value.order.return_value = mock_query
            res3 = client.get("/api/documents", headers={"X-API-Key": "secret123"})
            assert res3.status_code == 200


def test_get_user_conversations_invalid_phone():
    response = client.get("/api/conversations/invalid_no_digits")
    assert response.status_code == 400
    assert "Invalid phone number" in response.json()["detail"]


def test_get_user_conversations_pagination():
    with patch("main.supabase") as mock_supabase:
        mock_query = MagicMock()
        mock_query.execute.return_value.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value = mock_query
        
        response = client.get("/api/conversations/%2B919876543210?limit=10&offset=5")
        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_upload_document_invalid_type():
    files = {"file": ("test.exe", b"binary content", "application/octet-stream")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]

def test_upload_document_empty_file():
    files = {"file": ("empty.txt", b"", "text/plain")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "Uploaded file is empty" in response.json()["detail"]
