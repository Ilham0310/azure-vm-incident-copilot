"""
Incident Copilot Scheduler Module

This module provides scheduled telemetry collection and triage pipeline execution.
Uses APScheduler for periodic execution with configurable intervals.
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler

from src.models import TelemetryInput, DiagnosticOutput
from src.validator import SchemaValidator
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine
from src.explanation_formatter import ExplanationFormatter
from .config import AgentConfig
from .collector import TelemetryCollectorAgent


class IncidentCopilotScheduler:
    """
    Scheduler for periodic telemetry collection and triage pipeline execution.
    
    Runs the full pipeline on a configurable interval:
    1. Collect telemetry from Azure APIs
    2. Validate telemetry
    3. Score confidence
    4. Apply decision engine
    5. Format output
    6. Append to results/output.jsonl
    7. Log to console
    
    Supports two modes:
    - Continuous mode: Runs indefinitely with interval_seconds
    - Single-run mode: Runs once and exits (--once flag)
    """
    
    def __init__(self, config: AgentConfig, collector: TelemetryCollectorAgent):
        """
        Initialize scheduler with APScheduler.
        
        Args:
            config: Agent configuration
            collector: TelemetryCollectorAgent instance
        """
        self.config = config
        self.collector = collector
        
        # Initialize pipeline components
        self.validator = SchemaValidator()
        self.scorer = ConfidenceScorer()
        self.engine = DecisionEngine()
        self.formatter = ExplanationFormatter()
        
        # Create output directory if it doesn't exist
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize scheduler (will be started in run())
        self.scheduler = None
        self.is_running = False
    
    def run(self):
        """
        Runs APScheduler with interval_seconds. Blocking call.
        
        Schedules _on_tick() to run every config.interval_seconds.
        Runs until interrupted (Ctrl+C).
        """
        print(f"Starting Incident Copilot Agent")
        print(f"VM: {self.config.vm_name}")
        print(f"Resource Group: {self.config.resource_group}")
        print(f"Interval: {self.config.interval_seconds} seconds")
        print(f"Output: {self.config.output_dir}output.jsonl")
        print()
        print("Press Ctrl+C to stop")
        print("=" * 60)
        print()
        
        # Create blocking scheduler
        self.scheduler = BlockingScheduler()
        self.is_running = True
        
        # Schedule periodic execution
        self.scheduler.add_job(
            self._on_tick,
            'interval',
            seconds=self.config.interval_seconds,
            id='triage_cycle',
            max_instances=1  # Prevent overlapping executions
        )
        
        # Run first cycle immediately
        self._on_tick()
        
        try:
            # Start scheduler (blocking)
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print()
            print("=" * 60)
            print("Agent stopped by user")
            self.is_running = False
    
    def run_once(self) -> DiagnosticOutput:
        """
        Single collection + triage cycle. Returns DiagnosticOutput.
        
        Used for --once flag (single-run mode).
        
        Returns:
            DiagnosticOutput from the triage pipeline
        
        Raises:
            Exception: If collection or triage fails
        """
        print(f"Running single triage cycle")
        print(f"VM: {self.config.vm_name}")
        print(f"Resource Group: {self.config.resource_group}")
        print("=" * 60)
        print()
        
        # Run one cycle
        start_time = time.time()
        
        try:
            # Step 1: Collect telemetry
            print("Collecting telemetry from Azure...")
            telemetry = self.collector.collect()
            print(f"✓ Collected telemetry (completeness: {telemetry.data_completeness_percent:.1f}%)")
            
            # Step 2: Run triage pipeline
            print("Running triage pipeline...")
            output = self._run_pipeline(telemetry)
            
            # Calculate duration
            cycle_duration_ms = (time.time() - start_time) * 1000
            
            # Log result
            print()
            print("=" * 60)
            print(f"Decision: {output.decision.value}")
            print(f"Diagnosis: {output.diagnosis}")
            print(f"Confidence: {output.confidence_score:.2f}")
            print(f"Duration: {cycle_duration_ms:.0f}ms")
            print("=" * 60)
            
            # Append to output file
            self._append_result(output, cycle_duration_ms)
            
            return output
        
        except Exception as e:
            print(f"✗ Error during triage cycle: {e}")
            raise
    
    def _on_tick(self):
        """
        Called every interval_seconds:
        
        1. collector.collect() → TelemetryInput
        2. pipeline.run(telemetry) → DiagnosticOutput
        3. Append to results/output.jsonl
        4. Log: [timestamp] VM=<name> decision=<state> confidence=<score>
        
        Handles exceptions and logs errors without crashing scheduler.
        """
        start_time = time.time()
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        try:
            # Step 1: Collect telemetry
            telemetry = self.collector.collect()
            
            # Step 2: Run triage pipeline
            output = self._run_pipeline(telemetry)
            
            # Calculate duration
            cycle_duration_ms = (time.time() - start_time) * 1000
            
            # Step 3: Append to output file
            self._append_result(output, cycle_duration_ms)
            
            # Step 4: Log to console
            self._log_result(timestamp, output, cycle_duration_ms)
            
            # Step 5: Check for alerts
            self._check_alerts(output)
        
        except Exception as e:
            # Log error but don't crash scheduler
            print(f"[{timestamp}] ERROR: {e}")
    
    def _run_pipeline(self, telemetry: TelemetryInput) -> DiagnosticOutput:
        """
        Run the full triage pipeline on collected telemetry.
        
        Pipeline:
        1. Validate (already done by TelemetryInput model)
        2. Score confidence
        3. Apply decision engine (LLM or rule-based)
        4. Format output
        
        Args:
            telemetry: Collected telemetry input
        
        Returns:
            DiagnosticOutput from the pipeline
        """
        # Step 1: Calculate confidence score
        completeness, confidence_score, conflicts = self.scorer.score_telemetry(
            telemetry,
            pattern_match="exact"  # Will be determined by decision engine
        )
        
        # Step 2: Check if LLM is enabled
        import os
        llm_enabled = os.getenv("LLM_ENABLED", "false").lower() == "true"
        
        # Step 3: Apply decision engine
        if llm_enabled:
            try:
                from src.llm.llm_engine import LLMDecisionEngine
                llm_engine = LLMDecisionEngine()
                decision = llm_engine.decide(telemetry, confidence_score, completeness)
                print(f"  Using LLM engine (provider: {getattr(decision, 'llm_provider', 'unknown')})")
            except Exception as e:
                print(f"  LLM engine failed: {e}")
                print(f"  Falling back to rule-based engine")
                decision = self.engine.decide(telemetry, confidence_score, completeness)
        else:
            decision = self.engine.decide(telemetry, confidence_score, completeness)
        
        # Step 4: Format output
        output = self.formatter.format_output(decision, telemetry, confidence_score)
        
        return output
    
    def _append_result(self, output: DiagnosticOutput, cycle_duration_ms: float):
        """
        Append diagnostic output to results/output.jsonl.
        
        Format (one JSON object per line):
        {
          "timestamp": "2026-03-30T12:00:00Z",
          "vm_name": "my-vm",
          "resource_group": "my-rg",
          "cycle_duration_ms": 1240,
          "diagnostic_output": { ...DiagnosticOutput fields... }
        }
        
        Args:
            output: DiagnosticOutput from the pipeline
            cycle_duration_ms: Execution time in milliseconds
        """
        output_path = Path(self.config.output_dir) / "output.jsonl"
        
        # Build output record
        record = {
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "vm_name": self.config.vm_name,
            "resource_group": self.config.resource_group,
            "cycle_duration_ms": round(cycle_duration_ms, 2),
            "diagnostic_output": output.model_dump()
        }
        
        # Append to file (one JSON object per line)
        with open(output_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
    
    def _log_result(self, timestamp: str, output: DiagnosticOutput, cycle_duration_ms: float):
        """
        Log result to console.
        
        Format:
        [2026-03-30 12:00:00] VM=my-vm decision=diagnose confidence=0.85 duration=1240ms
        
        Args:
            timestamp: ISO 8601 timestamp
            output: DiagnosticOutput from the pipeline
            cycle_duration_ms: Execution time in milliseconds
        """
        # Format timestamp for display (remove microseconds and Z)
        display_time = timestamp.replace('T', ' ').replace('Z', '').split('.')[0]
        
        # Color coding for decision states
        decision_str = output.decision.value
        
        # Log line
        print(
            f"[{display_time}] "
            f"VM={self.config.vm_name} "
            f"decision={decision_str} "
            f"confidence={output.confidence_score:.2f} "
            f"duration={cycle_duration_ms:.0f}ms"
        )
    
    def _check_alerts(self, output: DiagnosticOutput):
        """
        Check if alerts should be triggered based on decision state.
        
        Args:
            output: DiagnosticOutput from the pipeline
        """
        # Alert on diagnose decision
        if self.config.alert_on_diagnose and output.decision.value == "diagnose":
            self._trigger_alert(output, "DIAGNOSE")
        
        # Alert on low confidence decision
        if self.config.alert_on_low_confidence and output.decision.value == "diagnose_low_confidence":
            self._trigger_alert(output, "LOW_CONFIDENCE")
    
    def _trigger_alert(self, output: DiagnosticOutput, alert_type: str):
        """
        Trigger an alert (placeholder for future integration).
        
        Args:
            output: DiagnosticOutput from the pipeline
            alert_type: Type of alert (DIAGNOSE, LOW_CONFIDENCE)
        """
        # Placeholder: In production, this would send alerts via email, SMS, webhook, etc.
        # For now, just log to console
        print(f"  ⚠️  ALERT [{alert_type}]: {output.diagnosis}")
    
    def stop(self):
        """Stop the scheduler if running."""
        if self.scheduler and self.is_running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            print("Scheduler stopped")
