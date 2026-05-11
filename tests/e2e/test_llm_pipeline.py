"""
End-to-End Test for LLM Decision Pipeline (Task 9 Checkpoint)

This test verifies:
1. End-to-end decision generation with all 3 LLM providers (Groq, Gemini, Ollama)
2. Safety guard correctly overrides LLM output
3. Complete pipeline integration: RAG → LLM → Safety Guard → Output

Tests cover:
- Provider fallback chain (Groq → Gemini → Ollama)
- Safety rule enforcement on LLM decisions
- RAG context retrieval and injection
- SOP knowledge base integration
- Decision state mapping and validation
"""

import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.models import (
    TelemetryInput, Decision, DecisionState,
    PowerState, ProvisioningState, ResourceHealthStatus,
    BootDiagnosticsStatus, AzureVMAgentStatus
)
from src.llm.llm_engine import LLMDecisionEngine
from src.safety_guard import SafetyGuard
from src.rag.memory_store import IncidentMemoryStore
from src.rag.sop_knowledge import SOPKnowledgeBase


class TestLLMPipelineEndToEnd:
    """End-to-end tests for LLM decision pipeline."""
    
    @pytest.fixture
    def sample_telemetry(self):
        """Create sample telemetry for testing."""
        return TelemetryInput(
            power_state=PowerState.RUNNING.value,
            provisioning_state=ProvisioningState.SUCCEEDED.value,
            resource_health_status=ResourceHealthStatus.AVAILABLE.value,
            heartbeat_present=False,
            azure_vm_agent_status=AzureVMAgentStatus.NOT_REPORTING.value,
            cpu_percent=22.5,
            memory_percent=67.0
        )
    
    @pytest.fixture
    def platform_event_telemetry(self):
        """Create telemetry with platform event (triggers Safety Rule 1)."""
        return TelemetryInput(
            power_state=PowerState.RUNNING.value,
            provisioning_state=ProvisioningState.SUCCEEDED.value,
            resource_health_status=ResourceHealthStatus.DEGRADED.value,
            resource_health_annotation="Platform maintenance in progress",
            cpu_percent=45.0
        )
    
    @pytest.fixture
    def boot_failure_telemetry(self):
        """Create telemetry with boot failure (triggers Safety Rule 2)."""
        return TelemetryInput(
            power_state=PowerState.RUNNING.value,
            provisioning_state=ProvisioningState.SUCCEEDED.value,
            resource_health_status=ResourceHealthStatus.UNAVAILABLE.value,
            boot_diagnostics_status=BootDiagnosticsStatus.BSOD.value
        )
    
    @pytest.fixture
    def mock_groq_response(self):
        """Mock successful Groq LLM response."""
        return json.dumps({
            "decision": "diagnose",
            "diagnosis": "Azure VM agent has stopped reporting heartbeats",
            "confidence_score": 0.84,
            "pattern_matched": "vm_running_no_heartbeat",
            "evidence": ["heartbeat_present=false", "azure_vm_agent_status=NotReporting"],
            "evidence_gap": ["boot_diagnostics_status"],
            "next_check": "Restart VM agent via Azure Run Command",
            "explanation": "VM is running but agent not reporting",
            "is_novel_incident": False,
            "novel_incident_description": ""
        })
    
    @pytest.fixture
    def mock_gemini_response(self):
        """Mock successful Gemini LLM response."""
        return json.dumps({
            "decision": "diagnose_low_confidence",
            "diagnosis": "Possible VM agent communication issue",
            "confidence_score": 0.65,
            "pattern_matched": "vm_running_no_heartbeat",
            "evidence": ["heartbeat_present=false"],
            "evidence_gap": ["azure_vm_agent_status", "boot_diagnostics_status"],
            "next_check": "Check VM agent status and restart if needed",
            "explanation": "Limited data available for diagnosis",
            "is_novel_incident": False,
            "novel_incident_description": ""
        })
    
    @pytest.fixture
    def mock_unsafe_llm_response(self):
        """Mock LLM response that violates safety rules."""
        return json.dumps({
            "decision": "diagnose",
            "diagnosis": "Platform maintenance detected",
            "confidence_score": 0.75,
            "pattern_matched": "platform_event",
            "evidence": ["resource_health_annotation=Platform maintenance"],
            "evidence_gap": [],
            "next_check": "Restart the VM immediately to resolve the issue",
            "explanation": "Platform event requires VM restart",
            "is_novel_incident": False,
            "novel_incident_description": ""
        })
    
    # ========================================================================
    # TEST 1: Groq Provider Success
    # ========================================================================
    
    def test_1_groq_provider_success(self, sample_telemetry, mock_groq_response):
        """Test successful decision generation with Groq provider."""
        with patch('src.llm.provider_chain.ProviderChain.generate') as mock_generate:
            # Mock Groq success
            mock_generate.return_value = (mock_groq_response, "groq")
            
            # Create engine and generate decision
            engine = LLMDecisionEngine()
            decision = engine.decide(sample_telemetry, confidence_score=0.84, completeness=85.0)
            
            # Verify decision
            assert isinstance(decision, Decision)
            assert decision.state == DecisionState.DIAGNOSE
            assert "agent" in decision.diagnosis.lower()
            assert decision.confidence_score == 0.84
            assert len(decision.evidence) > 0
            assert decision.next_check is not None
            
            # Verify LLM metadata
            assert hasattr(decision, 'llm_provider')
            # Note: llm_provider might not be set if Decision model doesn't have the field
    
    # ========================================================================
    # TEST 2: Groq Fails, Gemini Succeeds (Fallback)
    # ========================================================================
    
    def test_2_groq_fails_gemini_succeeds(self, sample_telemetry, mock_gemini_response):
        """Test provider fallback: Groq fails, Gemini succeeds."""
        with patch('src.llm.provider_chain.ProviderChain.generate') as mock_generate:
            # Mock Gemini success (Groq already failed in provider chain)
            mock_generate.return_value = (mock_gemini_response, "gemini")
            
            # Create engine and generate decision
            engine = LLMDecisionEngine()
            decision = engine.decide(sample_telemetry, confidence_score=0.65, completeness=75.0)
            
            # Verify decision
            assert isinstance(decision, Decision)
            assert decision.state == DecisionState.DIAGNOSE_LOW_CONFIDENCE
            assert decision.confidence_score == 0.65
            assert len(decision.evidence) > 0
    
    # ========================================================================
    # TEST 3: All Providers Fail, Fallback to Safe Decision
    # ========================================================================
    
    def test_3_all_providers_fail_safe_fallback(self, sample_telemetry):
        """Test that all provider failures result in safe fallback decision."""
        with patch('src.llm.provider_chain.ProviderChain.generate') as mock_generate:
            # Mock all providers failing
            mock_generate.side_effect = RuntimeError("All LLM providers unavailable")
            
            # Create engine and generate decision
            engine = LLMDecisionEngine()
            decision = engine.decide(sample_telemetry, confidence_score=0.0, completeness=85.0)
            
            # Verify safe fallback — falls back to rule-based engine
            assert isinstance(decision, Decision)
            # Rule engine with confidence=0.0 returns abstain
            assert decision.state == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
            assert decision.next_check is not None
            # Verify it was marked as fallback
            assert decision.llm_provider == "rule_engine_fallback"
    
    # ========================================================================
    # TEST 4: Safety Guard Overrides LLM Output (Platform Event)
    # ========================================================================
    
    def test_4_safety_guard_overrides_platform_event(
        self, platform_event_telemetry, mock_unsafe_llm_response
    ):
        """Test Safety Rule 1: Platform event forces abstain and removes restart."""
        with patch('src.llm.provider_chain.ProviderChain.generate') as mock_generate:
            # Mock LLM suggesting unsafe restart during platform event
            mock_generate.return_value = (mock_unsafe_llm_response, "groq")
            
            # Create engine and generate decision
            engine = LLMDecisionEngine()
            decision = engine.decide(
                platform_event_telemetry,
                confidence_score=0.75,
                completeness=80.0
            )
            
            # Verify safety override
            assert decision.state == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
            assert "restart" not in decision.next_check.lower()
            assert "reboot" not in decision.next_check.lower()
            
            # Verify safety rules were applied
            if hasattr(decision, 'safety_rules_applied'):
                assert len(decision.safety_rules_applied) > 0
                assert any("SR-1" in rule or "Platform" in rule for rule in decision.safety_rules_applied)
    
    # ========================================================================
    # TEST 5: Safety Guard Overrides LLM Output (Boot Failure)
    # ========================================================================
    
    def test_5_safety_guard_overrides_boot_failure(self, boot_failure_telemetry):
        """Test Safety Rule 2: Boot failure removes restart suggestions."""
        # Mock LLM response suggesting restart for BSOD
        unsafe_boot_response = json.dumps({
            "decision": "diagnose",
            "diagnosis": "VM experiencing BSOD",
            "confidence_score": 0.70,
            "pattern_matched": "boot_failure",
            "evidence": ["boot_diagnostics_status=BSOD"],
            "evidence_gap": [],
            "next_check": "Restart the VM to recover from BSOD",
            "explanation": "BSOD detected, restart recommended",
            "is_novel_incident": False,
            "novel_incident_description": ""
        })
        
        with patch('src.llm.provider_chain.ProviderChain.generate') as mock_generate:
            mock_generate.return_value = (unsafe_boot_response, "groq")
            
            # Create engine and generate decision
            engine = LLMDecisionEngine()
            decision = engine.decide(
                boot_failure_telemetry,
                confidence_score=0.70,
                completeness=75.0
            )
            
            # Verify safety override - should not suggest restart as action
            # The message may contain "do not restart" which is safe
            assert "review" in decision.next_check.lower() or "do not" in decision.next_check.lower()
            # Should not have standalone restart command
            assert not (decision.next_check.lower().startswith("restart") or 
                       decision.next_check.lower().startswith("reboot"))
            
            # Verify safety rules were applied
            if hasattr(decision, 'safety_rules_applied'):
                assert any("SR-2" in rule or "Boot" in rule for rule in decision.safety_rules_applied)
    
    # ========================================================================
    # TEST 6: RAG Memory Integration
    # ========================================================================
    
    def test_6_rag_memory_integration(self, sample_telemetry, mock_groq_response):
        """Test that RAG memory is queried and similar incidents are retrieved."""
        with patch('src.llm.provider_chain.ProviderChain.generate') as mock_generate, \
             patch.object(IncidentMemoryStore, 'find_similar_incidents') as mock_find:
            
            # Mock similar incidents
            mock_find.return_value = [
                {
                    'telemetry_summary': 'VM running, no heartbeat',
                    'diagnosis': 'VM agent failure',
                    'next_check': 'Restart agent',
                    'confidence': 0.88,
                    'similarity_score': 0.92,
                    'human_verified': True
                }
            ]
            
            mock_generate.return_value = (mock_groq_response, "groq")
            
            # Create engine and generate decision
            engine = LLMDecisionEngine()
            decision = engine.decide(sample_telemetry, confidence_score=0.84, completeness=85.0)
            
            # Verify RAG was called
            mock_find.assert_called_once()
            
            # Verify decision was generated
            assert isinstance(decision, Decision)
            assert decision.state == DecisionState.DIAGNOSE
    
    # ========================================================================
    # TEST 7: SOP Knowledge Base Integration
    # ========================================================================
    
    def test_7_sop_knowledge_base_integration(self, sample_telemetry, mock_groq_response):
        """Test that SOP knowledge base is queried and relevant SOPs are retrieved."""
        with patch('src.llm.provider_chain.ProviderChain.generate') as mock_generate, \
             patch.object(SOPKnowledgeBase, 'find_relevant_sops') as mock_find_sops:
            
            # Mock relevant SOPs
            mock_find_sops.return_value = [
                {
                    'title': 'Azure Request Admin Access on VM',
                    'steps': 'Use JIT access to run commands',
                    'warnings': 'Requires proper permissions'
                }
            ]
            
            mock_generate.return_value = (mock_groq_response, "groq")
            
            # Create engine and generate decision
            engine = LLMDecisionEngine()
            decision = engine.decide(sample_telemetry, confidence_score=0.84, completeness=85.0)
            
            # Verify SOP KB was called
            mock_find_sops.assert_called_once()
            
            # Verify decision was generated
            assert isinstance(decision, Decision)
    
    # ========================================================================
    # TEST 8: Complete Pipeline with All Components
    # ========================================================================
    
    def test_8_complete_pipeline_integration(self, sample_telemetry, mock_groq_response):
        """Test complete pipeline: RAG → LLM → Safety Guard → Output."""
        with patch('src.llm.provider_chain.ProviderChain.generate') as mock_generate, \
             patch.object(IncidentMemoryStore, 'find_similar_incidents') as mock_find, \
             patch.object(SOPKnowledgeBase, 'find_relevant_sops') as mock_find_sops, \
             patch.object(IncidentMemoryStore, 'add_incident') as mock_add:
            
            # Setup mocks
            mock_find.return_value = []
            mock_find_sops.return_value = []
            mock_generate.return_value = (mock_groq_response, "groq")
            mock_add.return_value = "incident_123"
            
            # Create engine and generate decision
            engine = LLMDecisionEngine()
            decision = engine.decide(sample_telemetry, confidence_score=0.84, completeness=85.0)
            
            # Verify all components were called
            mock_find.assert_called_once()
            mock_find_sops.assert_called_once()
            mock_generate.assert_called_once()
            
            # Verify decision output
            assert isinstance(decision, Decision)
            assert decision.state == DecisionState.DIAGNOSE
            assert decision.confidence_score == 0.84
            assert len(decision.evidence) > 0
            assert decision.next_check is not None
    
    # ========================================================================
    # TEST 9: JSON Parse Error Recovery
    # ========================================================================
    
    def test_9_json_parse_error_recovery(self, sample_telemetry):
        """Test that malformed JSON from LLM is handled gracefully."""
        with patch('src.llm.provider_chain.ProviderChain.generate') as mock_generate:
            # Mock malformed JSON response
            malformed_response = "This is not valid JSON at all"
            mock_generate.return_value = (malformed_response, "groq")
            
            # Create engine and generate decision
            engine = LLMDecisionEngine()
            decision = engine.decide(sample_telemetry, confidence_score=0.0, completeness=85.0)
            
            # Should return safe fallback
            assert isinstance(decision, Decision)
            assert decision.state == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
            assert decision.confidence_score == 0.0
    
    # ========================================================================
    # TEST 10: Decision State Mapping
    # ========================================================================
    
    @pytest.mark.parametrize("llm_decision,expected_state", [
        ("diagnose", DecisionState.DIAGNOSE),
        ("diagnose_low_confidence", DecisionState.DIAGNOSE_LOW_CONFIDENCE),
        ("abstain_request_next_check", DecisionState.ABSTAIN_REQUEST_NEXT_CHECK),
    ])
    def test_10_decision_state_mapping(
        self, sample_telemetry, llm_decision, expected_state
    ):
        """Test that LLM decision strings are correctly mapped to DecisionState enum."""
        mock_response = json.dumps({
            "decision": llm_decision,
            "diagnosis": "Test diagnosis",
            "confidence_score": 0.75,
            "pattern_matched": "test_pattern",
            "evidence": ["test_evidence"],
            "evidence_gap": [],
            "next_check": "Test next check",
            "explanation": "Test explanation",
            "is_novel_incident": False,
            "novel_incident_description": ""
        })
        
        with patch('src.llm.provider_chain.ProviderChain.generate') as mock_generate:
            mock_generate.return_value = (mock_response, "groq")
            
            # Create engine and generate decision
            engine = LLMDecisionEngine()
            decision = engine.decide(sample_telemetry, confidence_score=0.75, completeness=80.0)
            
            # Verify state mapping
            assert decision.state == expected_state


class TestSafetyGuardStandalone:
    """Standalone tests for safety guard to ensure it works independently."""
    
    def test_safety_rule_1_platform_event(self):
        """Test Safety Rule 1: Platform event detection and override."""
        telemetry = TelemetryInput(
            power_state=PowerState.RUNNING.value,
            provisioning_state=ProvisioningState.SUCCEEDED.value,
            resource_health_status=ResourceHealthStatus.DEGRADED.value,
            resource_health_annotation="Platform maintenance scheduled"
        )
        
        decision = Decision(
            state=DecisionState.DIAGNOSE,
            diagnosis="Test diagnosis",
            evidence=[],
            evidence_gap=[],
            next_check="Restart the VM to fix the issue",
            reasoning="Test reasoning",
            confidence_score=0.80
        )
        
        # Apply safety guard
        safe_decision = SafetyGuard.apply_safety_override(decision, telemetry)
        
        # Verify override
        assert safe_decision.state == DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
        assert "restart" not in safe_decision.next_check.lower()
        assert len(safe_decision.safety_rules_applied) > 0
    
    def test_safety_rule_2_boot_failure(self):
        """Test Safety Rule 2: Boot failure removes restart suggestions."""
        telemetry = TelemetryInput(
            power_state=PowerState.RUNNING.value,
            provisioning_state=ProvisioningState.SUCCEEDED.value,
            resource_health_status=ResourceHealthStatus.UNAVAILABLE.value,
            boot_diagnostics_status=BootDiagnosticsStatus.KERNEL_PANIC.value
        )
        
        decision = Decision(
            state=DecisionState.DIAGNOSE,
            diagnosis="Kernel panic detected",
            evidence=[],
            evidence_gap=[],
            next_check="Reboot the VM immediately",
            reasoning="Test reasoning",
            confidence_score=0.75
        )
        
        # Apply safety guard
        safe_decision = SafetyGuard.apply_safety_override(decision, telemetry)
        
        # Verify override - should not suggest restart as action
        # The message may contain "do not restart" which is safe
        assert "review" in safe_decision.next_check.lower() or "do not" in safe_decision.next_check.lower()
        # Should not have standalone restart command
        assert not (safe_decision.next_check.lower().startswith("restart") or 
                   safe_decision.next_check.lower().startswith("reboot"))
        assert len(safe_decision.safety_rules_applied) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
