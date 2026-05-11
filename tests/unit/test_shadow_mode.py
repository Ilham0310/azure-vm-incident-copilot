"""
Unit tests for shadow mode functionality.

Tests the ShadowModeExecutor class that runs both rule-based and LLM engines
in parallel for comparison.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.shadow_mode import ShadowModeExecutor, ShadowModeComparison
from src.models import TelemetryInput, Decision, DecisionState, PowerState, ProvisioningState, ResourceHealthStatus


class TestShadowModeExecutor:
    """Test suite for ShadowModeExecutor"""
    
    def test_initialization(self, tmp_path, monkeypatch):
        """Test shadow mode executor initialization"""
        # Use temporary directory for logs
        log_path = tmp_path / "logs" / "shadow_mode.jsonl"
        monkeypatch.setattr("src.shadow_mode.Path", lambda x: log_path if "shadow_mode" in x else Path(x))
        
        executor = ShadowModeExecutor()
        
        assert executor._rule_engine is not None
        assert executor._llm_engine is None  # Lazy initialization
    
    def test_compare_text_exact(self):
        """Test text comparison for exact matches"""
        executor = ShadowModeExecutor()
        
        result = executor._compare_text("High CPU usage", "High CPU usage")
        assert result == "exact"
    
    def test_compare_text_similar(self):
        """Test text comparison for similar text"""
        executor = ShadowModeExecutor()
        
        result = executor._compare_text(
            "High CPU usage detected",
            "CPU usage is high"
        )
        assert result == "similar"
    
    def test_compare_text_different(self):
        """Test text comparison for different text"""
        executor = ShadowModeExecutor()
        
        result = executor._compare_text(
            "High CPU usage",
            "Network connectivity issue"
        )
        assert result == "different"
    
    @patch('src.shadow_mode.LLMDecisionEngine')
    def test_execute_dual_success(self, mock_llm_engine_class, tmp_path, monkeypatch):
        """Test dual execution with both engines succeeding"""
        # Setup
        log_path = tmp_path / "logs" / "shadow_mode.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Mock the log path
        executor = ShadowModeExecutor()
        executor._log_path = log_path
        
        # Create test telemetry
        telemetry = TelemetryInput(
            vm_name="test-vm",
            power_state=PowerState.RUNNING,
            provisioning_state=ProvisioningState.SUCCEEDED,
            resource_health_status=ResourceHealthStatus.AVAILABLE,
            cpu_percent=98.0
        )
        
        # Mock LLM engine
        mock_llm_instance = Mock()
        mock_llm_decision = Decision(
            state=DecisionState.DIAGNOSE,
            diagnosis="High CPU saturation",
            evidence=["cpu_percent=98.0"],
            evidence_gap=[],
            next_check="Identify high CPU processes",
            confidence_score=0.85
        )
        mock_llm_decision.llm_provider = "groq"
        mock_llm_instance.decide.return_value = mock_llm_decision
        mock_llm_engine_class.return_value = mock_llm_instance
        
        # Execute
        rule_decision, comparison = executor.execute_dual(
            telemetry,
            confidence_score=0.80,
            completeness=85.0
        )
        
        # Verify rule-based decision is returned
        assert rule_decision is not None
        # Rule engine returns diagnose_low_confidence for this case (completeness < 90%)
        assert rule_decision.state in [DecisionState.DIAGNOSE, DecisionState.DIAGNOSE_LOW_CONFIDENCE]
        
        # Verify comparison was created
        assert comparison is not None
        assert comparison.vm_name == "test-vm"
        assert comparison.llm_provider == "groq"
        
        # Verify log file was created
        assert log_path.exists()
        
        # Read and verify log content
        with open(log_path, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            assert log_data['vm_name'] == "test-vm"
            # Rule engine returns diagnose_low_confidence for this case
            assert log_data['rule_decision'] in ["diagnose", "diagnose_low_confidence"]
            assert log_data['llm_decision'] == "diagnose"
    
    @patch('src.shadow_mode.LLMDecisionEngine')
    def test_execute_dual_llm_failure(self, mock_llm_engine_class, tmp_path):
        """Test dual execution when LLM engine fails"""
        # Setup
        log_path = tmp_path / "logs" / "shadow_mode.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        executor = ShadowModeExecutor()
        executor._log_path = log_path
        
        # Create test telemetry
        telemetry = TelemetryInput(
            vm_name="test-vm",
            power_state=PowerState.RUNNING,
            provisioning_state=ProvisioningState.SUCCEEDED,
            resource_health_status=ResourceHealthStatus.AVAILABLE
        )
        
        # Mock LLM engine to raise exception
        mock_llm_engine_class.side_effect = Exception("LLM provider unavailable")
        
        # Execute
        rule_decision, comparison = executor.execute_dual(
            telemetry,
            confidence_score=0.70,
            completeness=80.0
        )
        
        # Verify rule-based decision is still returned
        assert rule_decision is not None
        
        # Verify comparison shows LLM error
        assert comparison.llm_provider == "error"
        assert comparison.llm_diagnosis == "LLM engine failed"
    
    def test_get_stats_empty(self, tmp_path):
        """Test getting stats when no comparisons exist"""
        log_path = tmp_path / "logs" / "shadow_mode.jsonl"
        
        executor = ShadowModeExecutor()
        executor._log_path = log_path
        
        stats = executor.get_stats()
        
        assert stats['total_decisions'] == 0
        assert stats['decision_agreement_rate'] == 0.0
        assert stats['disagreement_cases'] == []
    
    def test_get_stats_with_data(self, tmp_path):
        """Test getting stats with comparison data"""
        log_path = tmp_path / "logs" / "shadow_mode.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write test data
        test_comparisons = [
            {
                "timestamp": "2026-04-07T10:00:00Z",
                "vm_name": "vm1",
                "rule_decision": "diagnose",
                "llm_decision": "diagnose",
                "rule_diagnosis": "High CPU",
                "llm_diagnosis": "High CPU usage",
                "rule_next_check": "Scale VM",
                "llm_next_check": "Scale VM up",
                "decision_match": True,
                "diagnosis_similarity": "similar",
                "next_check_similarity": "similar",
                "pattern_matched": "high_cpu"
            },
            {
                "timestamp": "2026-04-07T11:00:00Z",
                "vm_name": "vm2",
                "rule_decision": "diagnose",
                "llm_decision": "abstain_request_next_check",
                "rule_diagnosis": "NSG blocks RDP",
                "llm_diagnosis": "Insufficient data",
                "rule_next_check": "Review NSG rules",
                "llm_next_check": "Gather more data",
                "decision_match": False,
                "diagnosis_similarity": "different",
                "next_check_similarity": "different",
                "pattern_matched": "nsg_blocks_rdp"
            }
        ]
        
        with open(log_path, 'w') as f:
            for comp in test_comparisons:
                json.dump(comp, f)
                f.write('\n')
        
        executor = ShadowModeExecutor()
        executor._log_path = log_path
        
        stats = executor.get_stats()
        
        assert stats['total_decisions'] == 2
        assert stats['decision_agreement_rate'] == 50.0  # 1 out of 2
        assert len(stats['disagreement_cases']) == 1
        assert stats['disagreement_cases'][0]['vm_name'] == "vm2"
