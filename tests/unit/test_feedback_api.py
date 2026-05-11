"""
Unit tests for feedback API endpoint.

Tests the POST /api/feedback/{incident_id} endpoint functionality.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from ui.app import create_app


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_memory_store():
    """Mock IncidentMemoryStore for testing."""
    with patch('src.rag.memory_store.IncidentMemoryStore') as mock:
        yield mock


def test_feedback_endpoint_success(client, mock_memory_store):
    """Test successful feedback submission."""
    # Setup mock
    mock_instance = Mock()
    mock_instance.update_feedback.return_value = True
    mock_memory_store.return_value = mock_instance
    
    # Submit feedback
    response = client.post(
        "/api/feedback/a3f7c9d2e1b4",
        json={
            "correct": True,
            "outcome": "resolved"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["incident_id"] == "a3f7c9d2e1b4"
    assert data["human_verified"] is True
    assert "Future similar incidents" in data["message"]
    
    # Verify memory store was called correctly
    mock_instance.update_feedback.assert_called_once_with(
        incident_id="a3f7c9d2e1b4",
        correct=True,
        corrected_diagnosis=None,
        corrected_next_check=None,
        outcome="resolved"
    )


def test_feedback_endpoint_with_corrections(client, mock_memory_store):
    """Test feedback submission with corrected diagnosis."""
    # Setup mock
    mock_instance = Mock()
    mock_instance.update_feedback.return_value = True
    mock_memory_store.return_value = mock_instance
    
    # Submit feedback with corrections
    response = client.post(
        "/api/feedback/b4e8d3f1a2c5",
        json={
            "correct": False,
            "corrected_diagnosis": "The VM agent failed due to corrupted extension",
            "corrected_next_check": "Remove and reinstall the extension",
            "outcome": "resolved"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["human_verified"] is True
    
    # Verify memory store was called with corrections
    mock_instance.update_feedback.assert_called_once_with(
        incident_id="b4e8d3f1a2c5",
        correct=False,
        corrected_diagnosis="The VM agent failed due to corrupted extension",
        corrected_next_check="Remove and reinstall the extension",
        outcome="resolved"
    )


def test_feedback_endpoint_incident_not_found(client, mock_memory_store):
    """Test feedback submission for non-existent incident."""
    # Setup mock to return False (incident not found)
    mock_instance = Mock()
    mock_instance.update_feedback.return_value = False
    mock_memory_store.return_value = mock_instance
    
    # Submit feedback
    response = client.post(
        "/api/feedback/nonexistent123",
        json={
            "correct": True,
            "outcome": "resolved"
        }
    )
    
    # Verify 404 response
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "Incident not found"
    assert data["incident_id"] == "nonexistent123"


def test_feedback_endpoint_invalid_request(client):
    """Test feedback submission with invalid request body."""
    # Submit feedback with missing required field
    response = client.post(
        "/api/feedback/a3f7c9d2e1b4",
        json={
            "outcome": "resolved"
            # Missing 'correct' field
        }
    )
    
    # Verify 422 validation error
    assert response.status_code == 422


def test_feedback_endpoint_server_error(client, mock_memory_store):
    """Test feedback submission when memory store raises exception."""
    # Setup mock to raise exception
    mock_instance = Mock()
    mock_instance.update_feedback.side_effect = Exception("Database error")
    mock_memory_store.return_value = mock_instance
    
    # Submit feedback
    response = client.post(
        "/api/feedback/a3f7c9d2e1b4",
        json={
            "correct": True,
            "outcome": "resolved"
        }
    )
    
    # Verify 500 error
    assert response.status_code == 500
