import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "AI Trip Checklist API is running"}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "checks" in data
    assert data["version"] == "1.0.0"
    assert data["status"] in ["healthy", "degraded", "unhealthy"]


def test_liveness_check():
    response = client.get("/health/live")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert data["status"] == "alive"


def test_readiness_check():
    response = client.get("/health/ready")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert data["status"] == "ready"