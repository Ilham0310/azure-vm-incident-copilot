"""
LLM Decision Engine

Core LLM-based decision engine with RAG integration.
Maintains backward compatibility with existing DecisionEngine interface.
"""

import os
import json
import logging
import time
from typing import Optional, Dict
from datetime import datetime

from src.models import Decision, DecisionState, TelemetryInput
from src.rag.memory_store import IncidentMemoryStore
from src.rag.sop_knowledge import SOPKnowledgeBase
from src.safety_guard import SafetyGuard
from src.decision_engine import DecisionEngine
from .provider_chain import ProviderChain
from .prompts import get_system_prompt, build_user_prompt
from .structured_logger import get_structured_logger, StructuredLogger

logger = logging.getLogger(__name__)


class LLMDecisionEngine:
    """
    LLM-based decision engine with RAG and self-learning.
    
    Features:
    - Multi-provider LLM support (Groq → Gemini → Ollama)
    - RAG memory for past incidents
    - SOP knowledge base for recommendations
    - Backward compatible with existing interface
    """
    
    def __init__(self):
        """Initialize LLM decision engine"""
        self._provider_chain = ProviderChain()
        self._memory_store = IncidentMemoryStore()
        self._sop_kb = SOPKnowledgeBase()
        self._structured_logger = get_structured_logger()
        
        # Configuration
        self._rag_top_k = int(os.getenv("RAG_TOP_K", "5"))
        self._sop_top_k = int(os.getenv("SOP_TOP_K", "3"))
        self._temperature = 0.1  # Near-deterministic
        
        logger.info("LLMDecisionEngine initialized")
    
    def decide(
        self,
        telemetry: TelemetryInput,
        confidence_score: float,
        completeness: float
    ) -> Decision:
        """
        Generate decision using LLM with RAG context.
        
        Maintains backward compatibility with existing interface.
        
        Args:
            telemetry: Validated telemetry input
            confidence_score: Pre-calculated confidence score
            completeness: Data completeness percentage
            
        Returns:
            Decision object with LLM-generated diagnosis
        """
        # Generate request ID for tracing
        request_id = StructuredLogger.generate_request_id()
        logger.info(f"Starting LLM decision generation (request_id={request_id})")
        
        try:
            # Step 1: Convert telemetry to text for RAG
            telemetry_text = self._memory_store._telemetry_to_text(telemetry)
            
            # Step 2: Retrieve similar incidents from memory (graceful failure)
            similar_incidents = []
            rag_start = time.time()
            try:
                similar_incidents = self._memory_store.find_similar_incidents(
                    telemetry,
                    top_k=self._rag_top_k
                )
                rag_latency = (time.time() - rag_start) * 1000
                logger.info(f"Retrieved {len(similar_incidents)} similar incidents")
                
                # Log RAG retrieval
                self._structured_logger.log_rag_retrieval(
                    request_id=request_id,
                    retrieval_type="incidents",
                    query_text=telemetry_text,
                    results_count=len(similar_incidents),
                    results=similar_incidents,
                    latency_ms=rag_latency
                )
            except Exception as rag_error:
                rag_latency = (time.time() - rag_start) * 1000
                logger.warning(f"RAG memory retrieval failed: {rag_error}. Proceeding without similar incidents.")
                
                # Log RAG failure
                self._structured_logger.log_rag_retrieval(
                    request_id=request_id,
                    retrieval_type="incidents",
                    query_text=telemetry_text,
                    results_count=0,
                    results=[],
                    latency_ms=rag_latency,
                    error=str(rag_error)
                )
            
            # Step 3: Retrieve relevant SOPs (graceful failure)
            relevant_sops = []
            sop_start = time.time()
            try:
                relevant_sops = self._sop_kb.find_relevant_sops(
                    telemetry_text,
                    top_k=self._sop_top_k
                )
                sop_latency = (time.time() - sop_start) * 1000
                logger.info(f"Retrieved {len(relevant_sops)} relevant SOPs")
                
                # Log SOP retrieval
                self._structured_logger.log_rag_retrieval(
                    request_id=request_id,
                    retrieval_type="sops",
                    query_text=telemetry_text,
                    results_count=len(relevant_sops),
                    results=relevant_sops,
                    latency_ms=sop_latency
                )
            except Exception as sop_error:
                sop_latency = (time.time() - sop_start) * 1000
                logger.warning(f"SOP knowledge base retrieval failed: {sop_error}. Proceeding without SOPs.")
                
                # Log SOP failure
                self._structured_logger.log_rag_retrieval(
                    request_id=request_id,
                    retrieval_type="sops",
                    query_text=telemetry_text,
                    results_count=0,
                    results=[],
                    latency_ms=sop_latency,
                    error=str(sop_error)
                )
            
            # Step 4: Build prompts
            system_prompt = get_system_prompt()
            user_prompt = build_user_prompt(
                telemetry=telemetry,
                telemetry_text=telemetry_text,
                completeness_percent=completeness,
                missing_signals=telemetry.missing_signals or [],
                similar_incidents=similar_incidents,
                relevant_sops=relevant_sops
            )
            
            # Step 5: Generate LLM response (with provider fallback)
            llm_start = time.time()
            try:
                response_text, provider_name = self._provider_chain.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self._temperature
                )
                llm_latency = (time.time() - llm_start) * 1000
                
                logger.info(f"LLM response received from {provider_name}")
                
                # Step 6: Parse response
                decision = self._parse_response(
                    response_text,
                    provider_name,
                    len(similar_incidents),
                    [sop['title'] for sop in relevant_sops]
                )
                
                # Log LLM decision
                self._structured_logger.log_llm_decision(
                    request_id=request_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response=response_text,
                    provider=provider_name,
                    decision_state=decision.state.value,
                    diagnosis=decision.diagnosis,
                    confidence=decision.confidence_score,
                    similar_incidents_count=len(similar_incidents),
                    sops_consulted=[sop['title'] for sop in relevant_sops],
                    latency_ms=llm_latency
                )
                
            except RuntimeError as provider_error:
                llm_latency = (time.time() - llm_start) * 1000
                
                # Log LLM failure
                self._structured_logger.log_llm_decision(
                    request_id=request_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response="",
                    provider="none",
                    decision_state="fallback",
                    diagnosis="All LLM providers failed",
                    confidence=0.0,
                    similar_incidents_count=len(similar_incidents),
                    sops_consulted=[sop['title'] for sop in relevant_sops],
                    latency_ms=llm_latency,
                    error=str(provider_error)
                )
                
                # All LLM providers failed - fallback to rule engine
                logger.critical(
                    f"All LLM providers failed: {provider_error}. "
                    "Falling back to rule-based DecisionEngine."
                )
                return self._fallback_to_rule_engine(telemetry, confidence_score, completeness)
            
            # Step 7: Apply safety guard (overrides LLM output unconditionally)
            logger.info("Applying safety guard to LLM decision")
            original_state = decision.state
            original_next_check = decision.next_check
            decision = SafetyGuard.apply_safety_override(decision, telemetry)
            
            # Log if safety rules modified the decision
            if decision.safety_rules_applied:
                logger.warning(
                    f"Safety rules applied: {decision.safety_rules_applied}. "
                    f"Original next_check: {original_next_check}, "
                    f"Sanitized next_check: {decision.next_check}"
                )
                
                # Log safety override
                self._structured_logger.log_safety_override(
                    request_id=request_id,
                    rules_applied=decision.safety_rules_applied,
                    original_decision_state=original_state.value,
                    original_next_check=original_next_check,
                    sanitized_decision_state=decision.state.value,
                    sanitized_next_check=decision.next_check,
                    telemetry_summary=telemetry_text
                )
            
            # Step 8: Store incident in memory (async, non-blocking)
            self._store_incident(telemetry, decision)
            
            return decision
            
        except Exception as e:
            logger.error(f"LLM decision generation failed: {e}")
            # Fallback to rule engine on unexpected errors
            return self._fallback_to_rule_engine(telemetry, confidence_score, completeness)

    
    def _parse_response(
        self,
        response_text: str,
        provider_name: str,
        similar_incidents_count: int,
        sop_titles: list
    ) -> Decision:
        """
        Parse LLM JSON response into Decision object.
        
        Args:
            response_text: Raw LLM response
            provider_name: Name of LLM provider used
            similar_incidents_count: Number of similar incidents retrieved
            sop_titles: List of SOP titles consulted
            
        Returns:
            Decision object
        """
        try:
            # Strip markdown fences if present
            text = response_text.strip()
            if text.startswith("```"):
                # Remove markdown code fences
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
                if text.startswith("json"):
                    text = text[4:].strip()
            
            # Parse JSON
            data = json.loads(text)
            
            # Map decision string to enum
            decision_map = {
                "diagnose": DecisionState.DIAGNOSE,
                "diagnose_low_confidence": DecisionState.DIAGNOSE_LOW_CONFIDENCE,
                "abstain_request_next_check": DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
            }
            
            state = decision_map.get(
                data.get("decision", "").lower(),
                DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
            )
            
            # Create Decision object
            decision = Decision(
                state=state,
                diagnosis=data.get("diagnosis", "Unknown issue"),
                evidence=data.get("evidence", []),
                evidence_gap=data.get("evidence_gap", []),
                next_check=data.get("next_check"),
                confidence_score=float(data.get("confidence_score", 0.0))
            )
            
            # Add LLM metadata (if Decision model supports it)
            if hasattr(decision, 'llm_provider'):
                decision.llm_provider = provider_name
            if hasattr(decision, 'similar_incidents_used'):
                decision.similar_incidents_used = similar_incidents_count
            if hasattr(decision, 'sops_consulted'):
                decision.sops_consulted = sop_titles
            if hasattr(decision, 'is_novel_incident'):
                decision.is_novel_incident = data.get("is_novel_incident", False)
            if hasattr(decision, 'pattern_matched'):
                decision.pattern_matched = data.get("pattern_matched", "unknown")
            
            logger.info(f"Parsed LLM response: {state.value}")
            return decision
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.debug(f"Raw response: {response_text[:500]}")
            raise
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            raise
    
    def _store_incident(self, telemetry: TelemetryInput, decision: Decision):
        """
        Store incident in memory (non-blocking).
        
        Args:
            telemetry: Telemetry input
            decision: Decision object
        """
        try:
            pattern = getattr(decision, 'pattern_matched', 'unknown')
            
            incident_id = self._memory_store.add_incident(
                telemetry=telemetry,
                decision=decision.state.value,
                diagnosis=decision.diagnosis,
                confidence=decision.confidence_score,
                pattern=pattern,
                next_check=decision.next_check
            )
            
            if incident_id:
                logger.info(f"Stored incident {incident_id} in memory")
        except Exception as e:
            logger.warning(f"Failed to store incident: {e}")
    
    def _fallback_to_rule_engine(
        self,
        telemetry: TelemetryInput,
        confidence_score: float,
        completeness: float
    ) -> Decision:
        """
        Fallback to rule-based DecisionEngine when all LLM providers fail.
        
        Args:
            telemetry: Telemetry input
            confidence_score: Pre-calculated confidence score
            completeness: Data completeness percentage
            
        Returns:
            Decision from rule-based engine with fallback metadata
        """
        logger.info("Using rule-based DecisionEngine as fallback")
        
        # Use the original rule-based engine
        rule_engine = DecisionEngine()
        decision = rule_engine.decide(telemetry, confidence_score, completeness)
        
        # Mark decision as rule engine fallback
        if hasattr(decision, 'llm_provider'):
            decision.llm_provider = "rule_engine_fallback"
        
        return decision
    
    def _create_fallback_decision(
        self,
        telemetry: TelemetryInput,
        confidence_score: float
    ) -> Decision:
        """
        Create safe fallback decision when LLM fails (deprecated - use _fallback_to_rule_engine).
        
        Args:
            telemetry: Telemetry input
            confidence_score: Pre-calculated confidence score
            
        Returns:
            Safe abstain decision
        """
        return Decision(
            state=DecisionState.ABSTAIN_REQUEST_NEXT_CHECK,
            diagnosis="LLM decision generation failed",
            evidence=[],
            evidence_gap=["llm_unavailable"],
            next_check="Manual review required - LLM providers unavailable",
            confidence_score=0.0
        )
    
    def get_provider_status(self) -> Dict:
        """Get status of all LLM providers"""
        return self._provider_chain.get_provider_status()
    
    def get_memory_stats(self) -> Dict:
        """Get memory store statistics"""
        return self._memory_store.get_stats()
