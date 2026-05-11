"""
Shadow Mode for Gradual LLM Rollout

This module implements shadow mode functionality that runs both rule-based
and LLM engines in parallel, compares their outputs, and logs differences.

When LLM_SHADOW_MODE=true:
1. Run both engines on the same telemetry
2. Compare decision state, diagnosis, next_check
3. Log differences to logs/shadow_mode.jsonl
4. Return rule-based result to user (LLM result logged only)

This allows validation of LLM accuracy before full deployment.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Tuple
from dataclasses import dataclass, asdict

from src.models import TelemetryInput, Decision
from src.decision_engine import DecisionEngine
from src.llm.llm_engine import LLMDecisionEngine

logger = logging.getLogger(__name__)


@dataclass
class ShadowModeComparison:
    """Comparison result between rule-based and LLM engines"""
    timestamp: str
    vm_name: str
    
    # Rule-based engine output
    rule_decision: str
    rule_diagnosis: str
    rule_next_check: str
    rule_confidence: float
    
    # LLM engine output
    llm_decision: str
    llm_diagnosis: str
    llm_next_check: str
    llm_confidence: float
    llm_provider: str
    
    # Comparison results
    decision_match: bool
    diagnosis_similarity: str  # "exact", "similar", "different"
    next_check_similarity: str  # "exact", "similar", "different"
    
    # Metadata
    completeness: float
    pattern_matched: str


class ShadowModeExecutor:
    """
    Executes both rule-based and LLM engines in parallel for comparison.
    
    Logs all differences to logs/shadow_mode.jsonl for analysis.
    Always returns the rule-based result to maintain safety.
    """
    
    def __init__(self):
        """Initialize shadow mode executor"""
        self._rule_engine = DecisionEngine()
        self._llm_engine = None  # Lazy initialization
        self._log_path = Path("logs/shadow_mode.jsonl")
        
        # Ensure logs directory exists
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("ShadowModeExecutor initialized")
    
    def _get_llm_engine(self) -> LLMDecisionEngine:
        """Lazy initialization of LLM engine"""
        if self._llm_engine is None:
            self._llm_engine = LLMDecisionEngine()
        return self._llm_engine
    
    def execute_dual(
        self,
        telemetry: TelemetryInput,
        confidence_score: float,
        completeness: float
    ) -> Tuple[Decision, ShadowModeComparison]:
        """
        Execute both engines and compare results.
        
        Args:
            telemetry: Validated telemetry input
            confidence_score: Pre-calculated confidence score
            completeness: Data completeness percentage
            
        Returns:
            Tuple of (rule_based_decision, comparison_result)
            The rule-based decision is always returned to the user
        """
        logger.info("Shadow mode: Running dual-engine execution")
        
        # Execute rule-based engine
        rule_decision = self._rule_engine.decide(
            telemetry,
            confidence_score,
            completeness
        )
        logger.info(f"Rule engine: {rule_decision.state.value}")
        
        # Execute LLM engine
        try:
            llm_engine = self._get_llm_engine()
            llm_decision = llm_engine.decide(
                telemetry,
                confidence_score,
                completeness
            )
            logger.info(f"LLM engine: {llm_decision.state.value}")
            llm_provider = getattr(llm_decision, 'llm_provider', 'unknown')
        except Exception as e:
            logger.error(f"LLM engine failed in shadow mode: {e}")
            # Create fallback LLM decision for comparison
            llm_decision = Decision(
                state=rule_decision.state,
                diagnosis="LLM engine failed",
                evidence=[],
                evidence_gap=["llm_error"],
                next_check="LLM unavailable",
                confidence_score=0.0
            )
            llm_provider = "error"
        
        # Compare results
        comparison = self._compare_decisions(
            telemetry,
            rule_decision,
            llm_decision,
            llm_provider,
            completeness
        )
        
        # Log comparison
        self._log_comparison(comparison)
        
        # Always return rule-based decision (safety first)
        return rule_decision, comparison
    
    def _compare_decisions(
        self,
        telemetry: TelemetryInput,
        rule_decision: Decision,
        llm_decision: Decision,
        llm_provider: str,
        completeness: float
    ) -> ShadowModeComparison:
        """
        Compare rule-based and LLM decisions.
        
        Args:
            telemetry: Input telemetry
            rule_decision: Rule-based engine decision
            llm_decision: LLM engine decision
            llm_provider: LLM provider name
            completeness: Data completeness percentage
            
        Returns:
            ShadowModeComparison object
        """
        # Decision state match
        decision_match = rule_decision.state == llm_decision.state
        
        # Diagnosis similarity
        diagnosis_similarity = self._compare_text(
            rule_decision.diagnosis,
            llm_decision.diagnosis
        )
        
        # Next check similarity
        next_check_similarity = self._compare_text(
            rule_decision.next_check or "",
            llm_decision.next_check or ""
        )
        
        # Extract pattern matched
        pattern_matched = "unknown"
        if hasattr(rule_decision, 'pattern_matched') and rule_decision.pattern_matched:
            pattern_matched = rule_decision.pattern_matched
        
        return ShadowModeComparison(
            timestamp=datetime.now(timezone.utc).isoformat(),
            vm_name=telemetry.vm_name or "unknown",
            
            # Rule-based output
            rule_decision=rule_decision.state.value,
            rule_diagnosis=rule_decision.diagnosis,
            rule_next_check=rule_decision.next_check or "",
            rule_confidence=rule_decision.confidence_score,
            
            # LLM output
            llm_decision=llm_decision.state.value,
            llm_diagnosis=llm_decision.diagnosis,
            llm_next_check=llm_decision.next_check or "",
            llm_confidence=llm_decision.confidence_score,
            llm_provider=llm_provider,
            
            # Comparison
            decision_match=decision_match,
            diagnosis_similarity=diagnosis_similarity,
            next_check_similarity=next_check_similarity,
            
            # Metadata
            completeness=completeness,
            pattern_matched=pattern_matched
        )
    
    def _compare_text(self, text1: str, text2: str) -> str:
        """
        Compare two text strings for similarity.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            "exact", "similar", or "different"
        """
        # Normalize for comparison
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()
        
        if t1 == t2:
            return "exact"
        
        # Check for substantial overlap (simple heuristic)
        # Split into words and check overlap
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        if not words1 or not words2:
            return "different"
        
        overlap = len(words1 & words2)
        total = len(words1 | words2)
        
        if total == 0:
            return "different"
        
        similarity_ratio = overlap / total
        
        if similarity_ratio >= 0.5:
            return "similar"
        else:
            return "different"
    
    def _log_comparison(self, comparison: ShadowModeComparison):
        """
        Log comparison to logs/shadow_mode.jsonl.
        
        Args:
            comparison: ShadowModeComparison object
        """
        try:
            with open(self._log_path, 'a', encoding='utf-8') as f:
                json.dump(asdict(comparison), f)
                f.write('\n')
            
            # Log summary to console
            if not comparison.decision_match:
                logger.warning(
                    f"Shadow mode disagreement: "
                    f"Rule={comparison.rule_decision}, "
                    f"LLM={comparison.llm_decision}"
                )
        except Exception as e:
            logger.error(f"Failed to log shadow mode comparison: {e}")
    
    def get_stats(self) -> Dict:
        """
        Calculate shadow mode statistics from log file.
        
        Returns:
            Dictionary with statistics:
            - total_decisions: Total number of comparisons
            - decision_agreement_rate: Percentage of matching decisions
            - diagnosis_exact_match_rate: Percentage of exact diagnosis matches
            - diagnosis_similar_rate: Percentage of similar diagnoses
            - next_check_exact_match_rate: Percentage of exact next_check matches
            - disagreement_cases: List of recent disagreement cases
        """
        if not self._log_path.exists():
            return {
                "total_decisions": 0,
                "decision_agreement_rate": 0.0,
                "diagnosis_exact_match_rate": 0.0,
                "diagnosis_similar_rate": 0.0,
                "next_check_exact_match_rate": 0.0,
                "disagreement_cases": []
            }
        
        try:
            comparisons = []
            with open(self._log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        comparisons.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
            
            if not comparisons:
                return {
                    "total_decisions": 0,
                    "decision_agreement_rate": 0.0,
                    "diagnosis_exact_match_rate": 0.0,
                    "diagnosis_similar_rate": 0.0,
                    "next_check_exact_match_rate": 0.0,
                    "disagreement_cases": []
                }
            
            total = len(comparisons)
            
            # Calculate agreement rates
            decision_matches = sum(1 for c in comparisons if c['decision_match'])
            diagnosis_exact = sum(1 for c in comparisons if c['diagnosis_similarity'] == 'exact')
            diagnosis_similar = sum(1 for c in comparisons if c['diagnosis_similarity'] in ['exact', 'similar'])
            next_check_exact = sum(1 for c in comparisons if c['next_check_similarity'] == 'exact')
            
            # Find recent disagreements (last 10)
            disagreements = [
                {
                    "timestamp": c['timestamp'],
                    "vm_name": c['vm_name'],
                    "rule_decision": c['rule_decision'],
                    "llm_decision": c['llm_decision'],
                    "rule_diagnosis": c['rule_diagnosis'],
                    "llm_diagnosis": c['llm_diagnosis'],
                    "pattern_matched": c.get('pattern_matched', 'unknown')
                }
                for c in comparisons
                if not c['decision_match']
            ][-10:]  # Last 10 disagreements
            
            return {
                "total_decisions": total,
                "decision_agreement_rate": round((decision_matches / total) * 100, 2),
                "diagnosis_exact_match_rate": round((diagnosis_exact / total) * 100, 2),
                "diagnosis_similar_rate": round((diagnosis_similar / total) * 100, 2),
                "next_check_exact_match_rate": round((next_check_exact / total) * 100, 2),
                "disagreement_cases": disagreements
            }
        
        except Exception as e:
            logger.error(f"Failed to calculate shadow mode stats: {e}")
            return {
                "total_decisions": 0,
                "decision_agreement_rate": 0.0,
                "diagnosis_exact_match_rate": 0.0,
                "diagnosis_similar_rate": 0.0,
                "next_check_exact_match_rate": 0.0,
                "disagreement_cases": [],
                "error": str(e)
            }
