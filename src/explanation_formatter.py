"""
Explanation formatter component for Azure VM Incident Copilot.

This module provides the ExplanationFormatter class that:
- Formats decision into structured diagnostic output with 7 required fields
- Generates human-readable explanations
- Formats evidence list from telemetry signals
- Identifies evidence_gap from missing fields
- Ensures next_check is populated for abstain decisions
"""

from typing import List
from src.models import (
    Decision,
    DiagnosticOutput,
    TelemetryInput,
    DecisionState
)


class ExplanationFormatter:
    """
    Formats decision into structured diagnostic output.
    
    Responsibilities:
    - Generate all 7 required output fields
    - Format evidence list from telemetry signals
    - Identify evidence_gap from missing fields
    - Generate human-readable explanation text
    - Ensure next_check is populated for abstain decisions
    """
    
    def format_output(
        self,
        decision: Decision,
        telemetry: TelemetryInput,
        confidence_score: float
    ) -> DiagnosticOutput:
        """
        Formats decision into structured diagnostic output.
        
        Args:
            decision: Decision from decision engine
            telemetry: Original telemetry input
            confidence_score: Calculated confidence score
            
        Returns:
            DiagnosticOutput with all 7 required fields:
            - decision: diagnose | diagnose_low_confidence | abstain_request_next_check
            - diagnosis: Human-readable description
            - confidence_score: Float 0.0-1.0
            - evidence: List of supporting signals
            - evidence_gap: List of missing/incomplete signals
            - next_check: Specific diagnostic action (required for abstain)
            - explanation: Reasoning for the decision
        """
        # Generate explanation text
        explanation = self._generate_explanation(decision, telemetry, confidence_score)
        
        # Create diagnostic output
        output = DiagnosticOutput(
            decision=decision.state,
            diagnosis=decision.diagnosis,
            confidence_score=confidence_score,
            evidence=decision.evidence,
            evidence_gap=decision.evidence_gap,
            next_check=decision.next_check,
            explanation=explanation
        )
        
        return output
    
    def _generate_explanation(
        self,
        decision: Decision,
        telemetry: TelemetryInput,
        confidence_score: float
    ) -> str:
        """
        Generate human-readable explanation for the decision.
        
        Args:
            decision: Decision from decision engine
            telemetry: Original telemetry input
            confidence_score: Calculated confidence score
            
        Returns:
            Multi-sentence explanation text
        """
        explanation_parts = []
        
        # Part 1: State the decision and diagnosis
        if decision.state == DecisionState.DIAGNOSE:
            explanation_parts.append(
                f"High confidence diagnosis: {decision.diagnosis}. "
                f"Confidence score is {confidence_score:.2f}, indicating strong evidence for this assessment."
            )
        elif decision.state == DecisionState.DIAGNOSE_LOW_CONFIDENCE:
            explanation_parts.append(
                f"Low confidence diagnosis: {decision.diagnosis}. "
                f"Confidence score is {confidence_score:.2f}, indicating partial evidence but some uncertainty."
            )
        else:  # ABSTAIN_REQUEST_NEXT_CHECK
            explanation_parts.append(
                f"Insufficient data for diagnosis: {decision.diagnosis}. "
                f"Confidence score is {confidence_score:.2f}, which is below the threshold for diagnosis."
            )
        
        # Part 2: Explain the evidence
        if decision.evidence and len(decision.evidence) > 0:
            evidence_summary = self._summarize_evidence(decision.evidence)
            explanation_parts.append(
                f"Supporting evidence includes: {evidence_summary}."
            )
        
        # Part 3: Explain the gaps
        if decision.evidence_gap and len(decision.evidence_gap) > 0:
            gap_summary = self._summarize_gaps(decision.evidence_gap)
            explanation_parts.append(
                f"Missing or incomplete data: {gap_summary}."
            )
        
        # Part 4: Explain next steps
        if decision.next_check:
            explanation_parts.append(
                f"Recommended next step: {decision.next_check}"
            )
        
        # Part 5: Add safety context if applicable
        safety_context = self._get_safety_context(decision, telemetry)
        if safety_context:
            explanation_parts.append(safety_context)
        
        return " ".join(explanation_parts)
    
    def _summarize_evidence(self, evidence: List[str]) -> str:
        """
        Summarize evidence list into readable text.
        
        Args:
            evidence: List of evidence signals
            
        Returns:
            Human-readable summary
        """
        if len(evidence) == 0:
            return "no specific signals"
        elif len(evidence) <= 3:
            return ", ".join(evidence)
        else:
            # Show first 3 and count the rest
            first_three = ", ".join(evidence[:3])
            remaining = len(evidence) - 3
            return f"{first_three}, and {remaining} other signal(s)"
    
    def _summarize_gaps(self, gaps: List[str]) -> str:
        """
        Summarize evidence gaps into readable text.
        
        Args:
            gaps: List of missing signals
            
        Returns:
            Human-readable summary
        """
        if len(gaps) == 0:
            return "none"
        elif len(gaps) <= 3:
            return ", ".join(gaps)
        else:
            # Show first 3 and count the rest
            first_three = ", ".join(gaps[:3])
            remaining = len(gaps) - 3
            return f"{first_three}, and {remaining} other field(s)"
    
    def _get_safety_context(self, decision: Decision, telemetry: TelemetryInput) -> str:
        """
        Add safety context to explanation if applicable.
        
        Args:
            decision: Decision from decision engine
            telemetry: Original telemetry input
            
        Returns:
            Safety context text or empty string
        """
        # Check for platform event
        if telemetry.resource_health_annotation:
            annotation_lower = telemetry.resource_health_annotation.lower()
            platform_keywords = ["platform", "maintenance", "host update", "planned maintenance"]
            if any(keyword in annotation_lower for keyword in platform_keywords):
                return "Note: Platform-initiated event detected. Avoid VM restart during maintenance."
        
        # Check for boot failure
        if telemetry.boot_diagnostics_status:
            boot_status = str(telemetry.boot_diagnostics_status)
            if boot_status in ["BSOD", "KernelPanic"]:
                return f"Note: Boot failure ({boot_status}) detected. Do not restart VM without investigating root cause."
        
        # Check for failed state
        if (str(telemetry.power_state) == "Failed" and
            str(telemetry.provisioning_state) == "Failed"):
            return "Note: VM in failed state. Contact Azure support before attempting remediation."
        
        return ""


if __name__ == "__main__":
    # Example usage
    from src.models import Decision, DecisionState, PowerState, ProvisioningState, ResourceHealthStatus
    
    formatter = ExplanationFormatter()
    
    # Example: High CPU diagnosis
    telemetry = TelemetryInput(
        power_state=PowerState.RUNNING,
        provisioning_state=ProvisioningState.SUCCEEDED,
        resource_health_status=ResourceHealthStatus.DEGRADED,
        cpu_percent=98.0,
        memory_percent=45.0
    )
    
    decision = Decision(
        state=DecisionState.DIAGNOSE,
        diagnosis="High CPU saturation",
        evidence=["power_state=Running", "cpu_percent=98.0", "memory_percent=45.0"],
        evidence_gap=["heartbeat_present", "boot_diagnostics_status"],
        next_check="Identify high CPU processes and optimize or scale VM",
        confidence_score=0.85
    )
    
    output = formatter.format_output(decision, telemetry, 0.85)
    
    print("Diagnostic Output:")
    print(f"Decision: {output.decision}")
    print(f"Diagnosis: {output.diagnosis}")
    print(f"Confidence: {output.confidence_score}")
    print(f"Evidence: {output.evidence}")
    print(f"Evidence Gap: {output.evidence_gap}")
    print(f"Next Check: {output.next_check}")
    print(f"Explanation: {output.explanation}")
