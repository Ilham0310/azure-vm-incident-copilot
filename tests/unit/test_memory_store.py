"""
Unit tests for IncidentMemoryStore.update_feedback method

Tests Requirements 7.2, 7.4:
- Feedback storage and retrieval
- Human verification flag
- Corrected diagnosis/next_check storage
- Missing incident_id handling
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from src.rag.memory_store import IncidentMemoryStore


@pytest.fixture
def temp_chroma_path():
    """Create a temporary directory for ChromaDB during tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Best-effort cleanup — ChromaDB may hold file locks on Windows
    try:
        shutil.rmtree(temp_dir)
    except (PermissionError, OSError):
        pass


@pytest.fixture
def memory_store(temp_chroma_path):
    """Create a memory store instance with temporary storage"""
    store = IncidentMemoryStore(persist_path=temp_chroma_path)
    yield store
    # Reset internal state so ChromaDB releases file handles
    store._collection = None
    store._client = None


@pytest.fixture
def sample_telemetry():
    """Sample telemetry data for testing"""
    return {
        "power_state": "Running",
        "provisioning_state": "Succeeded",
        "resource_health_status": "Available",
        "heartbeat_present": False,
        "cpu_percent": 22.5,
        "memory_percent": 67.0,
        "azure_vm_agent_status": "NotReporting",
        "vm_name": "test-vm-001"
    }


class TestUpdateFeedback:
    """Test suite for update_feedback method"""
    
    def test_update_feedback_correct_diagnosis(self, memory_store, sample_telemetry):
        """Test marking a diagnosis as correct"""
        # Add an incident first
        incident_id = memory_store.add_incident(
            telemetry=sample_telemetry,
            decision="diagnose",
            diagnosis="VM agent stopped reporting",
            confidence=0.85,
            pattern="vm_running_no_heartbeat",
            next_check="Restart VM agent",
            vm_name="test-vm-001"
        )
        
        assert incident_id, "Incident should be stored successfully"
        
        # Mark as correct
        result = memory_store.update_feedback(
            incident_id=incident_id,
            correct=True,
            outcome="resolved"
        )
        
        assert result is True, "Feedback update should succeed"
        
        # Verify the update
        collection = memory_store._get_collection()
        stored = collection.get(ids=[incident_id])
        
        assert stored['ids'], "Incident should exist"
        metadata = stored['metadatas'][0]
        assert metadata['human_verified'] == "True"
        assert metadata['outcome'] == "resolved"
        # Original diagnosis should remain unchanged
        assert metadata['diagnosis'] == "VM agent stopped reporting"
    
    def test_update_feedback_incorrect_with_corrections(self, memory_store, sample_telemetry):
        """Test marking a diagnosis as incorrect with corrected values"""
        # Add an incident
        incident_id = memory_store.add_incident(
            telemetry=sample_telemetry,
            decision="diagnose",
            diagnosis="VM agent stopped reporting",
            confidence=0.85,
            pattern="vm_running_no_heartbeat",
            next_check="Restart VM agent",
            vm_name="test-vm-001"
        )
        
        # Mark as incorrect with corrections
        result = memory_store.update_feedback(
            incident_id=incident_id,
            correct=False,
            corrected_diagnosis="VM agent failed due to corrupted extension",
            corrected_next_check="Remove and reinstall Azure Monitor extension",
            outcome="escalated"
        )
        
        assert result is True, "Feedback update should succeed"
        
        # Verify the corrections were stored
        collection = memory_store._get_collection()
        stored = collection.get(ids=[incident_id])
        
        metadata = stored['metadatas'][0]
        assert metadata['human_verified'] == "True"
        assert metadata['outcome'] == "escalated"
        # Original diagnosis is preserved, corrections stored separately
        assert metadata['diagnosis'] == "VM agent stopped reporting"
        assert metadata['corrected_diagnosis'] == "VM agent failed due to corrupted extension"
        assert metadata['corrected_next_check'] == "Remove and reinstall Azure Monitor extension"
    
    def test_update_feedback_missing_incident_id(self, memory_store):
        """Test handling of missing incident_id gracefully"""
        # Try to update non-existent incident
        result = memory_store.update_feedback(
            incident_id="nonexistent123",
            correct=True,
            outcome="resolved"
        )
        
        assert result is False, "Should return False for missing incident"
    
    def test_update_feedback_partial_corrections(self, memory_store, sample_telemetry):
        """Test updating only diagnosis without next_check correction"""
        # Add an incident
        incident_id = memory_store.add_incident(
            telemetry=sample_telemetry,
            decision="diagnose",
            diagnosis="Original diagnosis",
            confidence=0.85,
            pattern="test_pattern",
            next_check="Original next check",
            vm_name="test-vm-001"
        )
        
        # Update only diagnosis
        result = memory_store.update_feedback(
            incident_id=incident_id,
            correct=False,
            corrected_diagnosis="Corrected diagnosis only",
            outcome="resolved"
        )
        
        assert result is True
        
        # Verify only diagnosis correction was stored, original preserved
        collection = memory_store._get_collection()
        stored = collection.get(ids=[incident_id])
        metadata = stored['metadatas'][0]
        
        assert metadata['diagnosis'] == "Original diagnosis"  # Original preserved
        assert metadata['corrected_diagnosis'] == "Corrected diagnosis only"
        assert metadata['next_check'] == "Original next check"  # Should remain unchanged
    
    def test_update_feedback_false_positive(self, memory_store, sample_telemetry):
        """Test marking an incident as false positive"""
        # Add an incident
        incident_id = memory_store.add_incident(
            telemetry=sample_telemetry,
            decision="diagnose",
            diagnosis="False alarm",
            confidence=0.60,
            pattern="test_pattern",
            vm_name="test-vm-001"
        )
        
        # Mark as false positive
        result = memory_store.update_feedback(
            incident_id=incident_id,
            correct=False,
            corrected_diagnosis="No actual issue, monitoring glitch",
            outcome="false_positive"
        )
        
        assert result is True
        
        # Verify outcome
        collection = memory_store._get_collection()
        stored = collection.get(ids=[incident_id])
        metadata = stored['metadatas'][0]
        
        assert metadata['outcome'] == "false_positive"
        assert metadata['human_verified'] == "True"
    
    def test_verified_cases_prioritized_in_search(self, memory_store, sample_telemetry):
        """Test that verified cases appear first in similarity search"""
        # Add two similar incidents
        incident_id_1 = memory_store.add_incident(
            telemetry=sample_telemetry,
            decision="diagnose",
            diagnosis="First incident",
            confidence=0.80,
            pattern="test_pattern",
            vm_name="test-vm-001"
        )
        
        incident_id_2 = memory_store.add_incident(
            telemetry=sample_telemetry,
            decision="diagnose",
            diagnosis="Second incident",
            confidence=0.85,
            pattern="test_pattern",
            vm_name="test-vm-002"
        )
        
        # Verify only the second one
        memory_store.update_feedback(
            incident_id=incident_id_2,
            correct=True,
            outcome="resolved"
        )
        
        # Search for similar incidents
        similar = memory_store.find_similar_incidents(
            telemetry=sample_telemetry,
            top_k=5,
            min_similarity=0.5
        )
        
        # Verified case should appear first
        assert len(similar) >= 2
        assert similar[0]['incident_id'] == incident_id_2
        assert similar[0]['human_verified'] is True
        assert similar[1]['incident_id'] == incident_id_1
        assert similar[1]['human_verified'] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
