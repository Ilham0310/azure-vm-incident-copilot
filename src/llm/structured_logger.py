"""
Structured Logging for LLM Decision Engine

Provides structured JSON logging for:
- LLM decisions (prompts, responses, metadata)
- RAG retrievals (similar incidents, SOPs)
- Safety overrides (rule violations, sanitizations)
- Feedback submissions (corrections, outcomes)

All logs include request_id for tracing a single decision across components.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class StructuredLogger:
    """
    Structured logger for LLM decision engine observability.
    
    Writes JSON lines to separate log files for different event types.
    """
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize structured logger.
        
        Args:
            log_dir: Directory for log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file paths
        self.llm_decisions_log = self.log_dir / "llm_decisions.jsonl"
        self.rag_retrievals_log = self.log_dir / "rag_retrievals.jsonl"
        self.safety_overrides_log = self.log_dir / "safety_overrides.jsonl"
        self.feedback_log = self.log_dir / "feedback.jsonl"
        
        logger.info(f"StructuredLogger initialized with log_dir: {log_dir}")
    
    def _write_log(self, log_file: Path, data: Dict[str, Any]):
        """
        Write a JSON line to a log file.
        
        Args:
            log_file: Path to log file
            data: Data to log as JSON
        """
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                json.dump(data, f, default=str)
                f.write('\n')
        except Exception as e:
            logger.error(f"Failed to write to {log_file}: {e}")
    
    def log_llm_decision(
        self,
        request_id: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        provider: str,
        decision_state: str,
        diagnosis: str,
        confidence: float,
        similar_incidents_count: int,
        sops_consulted: List[str],
        latency_ms: float,
        error: Optional[str] = None
    ):
        """
        Log LLM decision with full prompt and response.
        
        Args:
            request_id: Unique request identifier
            system_prompt: System prompt sent to LLM
            user_prompt: User prompt sent to LLM
            response: Raw LLM response
            provider: LLM provider name
            decision_state: Decision state (diagnose, diagnose_low_confidence, abstain)
            diagnosis: Diagnosis text
            confidence: Confidence score
            similar_incidents_count: Number of similar incidents retrieved
            sops_consulted: List of SOP titles consulted
            latency_ms: LLM inference latency in milliseconds
            error: Error message if LLM call failed
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "event_type": "llm_decision",
            "provider": provider,
            "decision_state": decision_state,
            "diagnosis": diagnosis,
            "confidence": confidence,
            "similar_incidents_count": similar_incidents_count,
            "sops_consulted": sops_consulted,
            "latency_ms": latency_ms,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "response": response,
            "error": error
        }
        self._write_log(self.llm_decisions_log, data)
    
    def log_rag_retrieval(
        self,
        request_id: str,
        retrieval_type: str,  # "incidents" or "sops"
        query_text: str,
        results_count: int,
        results: List[Dict],
        latency_ms: float,
        error: Optional[str] = None
    ):
        """
        Log RAG retrieval (similar incidents or SOPs).
        
        Args:
            request_id: Unique request identifier
            retrieval_type: Type of retrieval ("incidents" or "sops")
            query_text: Query text used for retrieval
            results_count: Number of results returned
            results: List of retrieved results with metadata
            latency_ms: Retrieval latency in milliseconds
            error: Error message if retrieval failed
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "event_type": "rag_retrieval",
            "retrieval_type": retrieval_type,
            "query_text": query_text,
            "results_count": results_count,
            "results": results,
            "latency_ms": latency_ms,
            "error": error
        }
        self._write_log(self.rag_retrievals_log, data)
    
    def log_safety_override(
        self,
        request_id: str,
        rules_applied: List[str],
        original_decision_state: str,
        original_next_check: Optional[str],
        sanitized_decision_state: str,
        sanitized_next_check: Optional[str],
        telemetry_summary: str
    ):
        """
        Log safety guard override.
        
        Args:
            request_id: Unique request identifier
            rules_applied: List of safety rules that were applied
            original_decision_state: Original decision state from LLM
            original_next_check: Original next_check from LLM
            sanitized_decision_state: Sanitized decision state after safety guard
            sanitized_next_check: Sanitized next_check after safety guard
            telemetry_summary: Summary of telemetry that triggered override
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "event_type": "safety_override",
            "rules_applied": rules_applied,
            "original_decision_state": original_decision_state,
            "original_next_check": original_next_check,
            "sanitized_decision_state": sanitized_decision_state,
            "sanitized_next_check": sanitized_next_check,
            "telemetry_summary": telemetry_summary
        }
        self._write_log(self.safety_overrides_log, data)
    
    def log_feedback(
        self,
        request_id: str,
        incident_id: str,
        correct: bool,
        corrected_diagnosis: Optional[str],
        corrected_next_check: Optional[str],
        outcome: str,
        original_diagnosis: str,
        original_next_check: Optional[str]
    ):
        """
        Log human feedback submission.
        
        Args:
            request_id: Unique request identifier
            incident_id: Incident identifier
            correct: Whether the diagnosis was correct
            corrected_diagnosis: Corrected diagnosis if incorrect
            corrected_next_check: Corrected next_check if incorrect
            outcome: Outcome status (resolved, escalated, false_positive)
            original_diagnosis: Original diagnosis from LLM
            original_next_check: Original next_check from LLM
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "incident_id": incident_id,
            "event_type": "feedback",
            "correct": correct,
            "corrected_diagnosis": corrected_diagnosis,
            "corrected_next_check": corrected_next_check,
            "outcome": outcome,
            "original_diagnosis": original_diagnosis,
            "original_next_check": original_next_check
        }
        self._write_log(self.feedback_log, data)
    
    @staticmethod
    def generate_request_id() -> str:
        """
        Generate a unique request ID for tracing.
        
        Returns:
            Unique request ID (UUID4 hex)
        """
        return uuid.uuid4().hex[:16]


# Global instance for easy access
_structured_logger: Optional[StructuredLogger] = None


def get_structured_logger() -> StructuredLogger:
    """
    Get or create the global structured logger instance.
    
    Returns:
        StructuredLogger instance
    """
    global _structured_logger
    if _structured_logger is None:
        _structured_logger = StructuredLogger()
    return _structured_logger
