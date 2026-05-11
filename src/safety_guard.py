"""
Safety Guard

Deterministic safety rules that override LLM output unconditionally.
Enforces 6 safety rules to prevent unsafe remediation suggestions.
"""

import logging
from typing import List

from src.models import Decision, DecisionState, TelemetryInput, PowerState, ProvisioningState, BootDiagnosticsStatus

logger = logging.getLogger(__name__)


class SafetyGuard:
    """
    Enforces 6 deterministic safety rules on all decisions.
    
    Safety rules cannot be bypassed by LLM output and are applied
    as post-processing after decision generation.
    """
    
    @staticmethod
    def apply_safety_override(decision: Decision, telemetry: TelemetryInput) -> Decision:
        """
        Apply all 6 safety rules to decision.
        
        Args:
            decision: Decision object from LLM or rule engine
            telemetry: Telemetry input
            
        Returns:
            Decision with safety overrides applied
        """
        safety_rules_applied = []
        
        # Safety Rule 1: Platform Event Safety
        if SafetyGuard._check_platform_event(telemetry):
            logger.warning("Safety Rule 1: Platform event detected")
            decision.state = DecisionState.ABSTAIN_REQUEST_NEXT_CHECK
            decision.diagnosis = "Platform-initiated event detected"
            decision.next_check = "Wait for platform maintenance to complete, then re-assess VM state"
            # Remove restart keywords
            if decision.next_check and "restart" in decision.next_check.lower():
                decision.next_check = decision.next_check.replace("restart", "review")
                decision.next_check = decision.next_check.replace("reboot", "review")
            safety_rules_applied.append("SR-1: Platform Event")
        
        # Safety Rule 2: Boot Failure Safety
        if SafetyGuard._check_boot_failure(telemetry):
            logger.warning("Safety Rule 2: Boot failure detected")
            # Remove restart suggestions
            if decision.next_check:
                next_check_lower = decision.next_check.lower()
                if "restart" in next_check_lower or "reboot" in next_check_lower:
                    decision.next_check = "Review boot diagnostics logs and serial console output (do not restart VM)"
                    safety_rules_applied.append("SR-2: Boot Failure")
        
        # Safety Rule 3: Low Confidence Destructive Action Safety
        if decision.confidence_score < 0.9:
            destructive_keywords = ["delete", "reset", "remove", "destroy", "wipe"]
            if decision.next_check and any(kw in decision.next_check.lower() for kw in destructive_keywords):
                logger.warning("Safety Rule 3: Low confidence destructive action blocked")
                decision.next_check = "Gather more data before considering destructive actions (confidence too low)"
                safety_rules_applied.append("SR-3: Low Confidence Destructive Action")
        
        # Safety Rule 4: Network Security Safety
        if decision.next_check:
            next_check_lower = decision.next_check.lower()
            if "disable nsg" in next_check_lower or "disable firewall" in next_check_lower:
                logger.warning("Safety Rule 4: Network security violation blocked")
                decision.next_check = "Review network security configuration manually (do not disable NSG or firewall rules)"
                safety_rules_applied.append("SR-4: Network Security")
        
        # Safety Rule 5: Disk Safety
        if decision.confidence_score < 0.9 and decision.next_check:
            next_check_lower = decision.next_check.lower()
            if "delete disk" in next_check_lower or "reset os" in next_check_lower:
                logger.warning("Safety Rule 5: Disk operation blocked")
                decision.next_check = "Review disk and OS state manually (confidence too low for disk operations)"
                safety_rules_applied.append("SR-5: Disk Safety")
        
        # Safety Rule 6: Failed State Safety
        if (telemetry.power_state == PowerState.FAILED and 
            telemetry.provisioning_state == ProvisioningState.FAILED):
            if decision.next_check and ("auto" in decision.next_check.lower() or "remediate" in decision.next_check.lower()):
                logger.warning("Safety Rule 6: Failed state auto-remediation blocked")
                decision.next_check = "Contact Azure support for failed VM state (do not attempt auto-remediation)"
                safety_rules_applied.append("SR-6: Failed State")
        
        # Update safety rules applied
        decision.safety_rules_applied = safety_rules_applied
        
        if safety_rules_applied:
            logger.info(f"Applied safety rules: {', '.join(safety_rules_applied)}")
        
        return decision
    
    @staticmethod
    def _check_platform_event(telemetry: TelemetryInput) -> bool:
        """Check if platform event is detected"""
        if not telemetry.resource_health_annotation:
            return False
        
        annotation_lower = telemetry.resource_health_annotation.lower()
        platform_keywords = ["platform", "maintenance", "host update", "planned maintenance", "degradation"]
        
        return any(keyword in annotation_lower for keyword in platform_keywords)
    
    @staticmethod
    def _check_boot_failure(telemetry: TelemetryInput) -> bool:
        """Check if boot failure is detected"""
        return telemetry.boot_diagnostics_status in [
            BootDiagnosticsStatus.BSOD,
            BootDiagnosticsStatus.KERNEL_PANIC
        ]
