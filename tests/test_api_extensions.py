"""
Integration tests for API extensions (Task 11)

Tests the new API endpoints:
- GET /api/memory/stats
- GET /api/novel-incidents
- POST /api/memory/prune
- GET /health (extended)
- POST /api/triage (with LLM metadata)
"""

import pytest
from fastapi.testclient import TestClient
from ui.app import create_app


@pytest.fixture
def client():
    """Create test client"""
    app = create_app()
    return TestClient(app)


def test_memory_stats_endpoint(client):
    """Test GET /api/memory/stats endpoint"""
    response = client.get("/api/memory/stats")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify expected fields
    assert "total" in data
    assert "verified" in data
    assert "patterns" in data
    assert "top_patterns" in data
    assert "novel_incidents" in data
    
    # Verify types
    assert isinstance(data["total"], int)
    assert isinstance(data["verified"], int)
    assert isinstance(data["patterns"], dict)
    assert isinstance(data["top_patterns"], list)
    assert isinstance(data["novel_incidents"], int)


def test_novel_incidents_endpoint(client):
    """Test GET /api/novel-incidents endpoint"""
    response = client.get("/api/novel-incidents")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should return a list
    assert isinstance(data, list)
    
    # If there are novel incidents, verify structure
    if len(data) > 0:
        incident = data[0]
        assert "incident_id" in incident
        assert "telemetry_summary" in incident
        assert "diagnosis" in incident
        assert "confidence" in incident
        assert "timestamp" in incident
        assert "pattern" in incident
        assert "vm_name" in incident


def test_novel_incidents_with_limit(client):
    """Test GET /api/novel-incidents with limit parameter"""
    response = client.get("/api/novel-incidents?limit=10")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should return at most 10 incidents
    assert len(data) <= 10


def test_memory_prune_endpoint_invalid_date(client):
    """Test POST /api/memory/prune with invalid date"""
    response = client.post("/api/memory/prune?before=invalid-date")
    
    assert response.status_code == 400
    data = response.json()
    assert "error" in data


def test_memory_prune_endpoint_valid_date(client):
    """Test POST /api/memory/prune with valid date"""
    response = client.post("/api/memory/prune?before=2020-01-01")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert "deleted_count" in data
    assert "message" in data
    assert data["status"] == "ok"
    assert isinstance(data["deleted_count"], int)


def test_health_check_extended(client):
    """Test GET /health endpoint with LLM provider status"""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify expected fields
    assert "status" in data
    assert "providers" in data
    assert "active_provider" in data
    assert "memory_store" in data
    assert "sop_kb" in data
    
    # Verify providers structure
    assert isinstance(data["providers"], dict)
    
    # Verify memory_store structure
    assert "total_incidents" in data["memory_store"]
    assert "collection_status" in data["memory_store"]
    
    # Verify sop_kb structure
    assert "total_sops" in data["sop_kb"]
    assert "collection_status" in data["sop_kb"]


def test_triage_endpoint_returns_llm_metadata(client):
    """Test POST /api/triage returns LLM metadata fields"""
    # Create minimal valid telemetry
    telemetry = {
        "power_state": "Running",
        "provisioning_state": "Succeeded",
        "resource_health_status": "Available"
    }
    
    response = client.post("/api/triage", json={"telemetry": telemetry})
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify core fields
    assert "decision" in data
    assert "diagnosis" in data
    assert "confidence_score" in data
    
    # Verify LLM metadata fields are present
    assert "incident_id" in data
    assert "pattern_matched" in data
    assert "is_novel_incident" in data
    assert "novel_incident_description" in data
    assert "llm_provider" in data
    assert "similar_incidents_used" in data
    assert "sops_consulted" in data
    assert "safety_rules_applied" in data
    
    # Verify types
    assert isinstance(data["is_novel_incident"], bool)
    assert isinstance(data["similar_incidents_used"], int)
    assert isinstance(data["sops_consulted"], list)
    assert isinstance(data["safety_rules_applied"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
