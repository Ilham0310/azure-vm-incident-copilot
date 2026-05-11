"""Run the agent once and write output to results/agent_once_output.json"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.makedirs('results', exist_ok=True)

from dotenv import load_dotenv; load_dotenv()
from agent.config import AgentConfig
from agent.collector import TelemetryCollectorAgent
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine
from src.explanation_formatter import ExplanationFormatter

config = AgentConfig.from_env()
print(f"VM: {config.vm_name} | RG: {config.resource_group}")
print("Collecting telemetry (this takes ~60-90s for ARG + workspace queries)...")

collector = TelemetryCollectorAgent(config)
telemetry = collector.collect()

print(f"\n--- Telemetry ---")
print(f"power_state:          {telemetry.power_state}")
print(f"provisioning_state:   {telemetry.provisioning_state}")
print(f"resource_health:      {telemetry.resource_health_status}")
print(f"heartbeat_present:    {telemetry.heartbeat_present}")
print(f"azure_vm_agent:       {telemetry.azure_vm_agent_status}")
print(f"monitor_agent:        {telemetry.monitor_agent_status}")
print(f"cpu_percent:          {telemetry.cpu_percent}")
print(f"memory_percent:       {telemetry.memory_percent}")
print(f"os_disk_percent_full: {telemetry.os_disk_percent_full}")
print(f"nsg_allow_rdp:        {telemetry.nsg_allow_rdp_3389}")
print(f"nsg_allow_ssh:        {telemetry.nsg_allow_ssh_22}")
print(f"completeness:         {telemetry.data_completeness_percent}%")
print(f"missing_signals:      {telemetry.missing_signals}")

print("\nRunning decision engine...")
scorer = ConfidenceScorer()
completeness, confidence, conflicts = scorer.score_telemetry(telemetry, pattern_match="exact")
engine = DecisionEngine()
decision = engine.decide(telemetry, confidence, completeness)
formatter = ExplanationFormatter()
output = formatter.format_output(decision, telemetry, confidence)

print(f"\n--- Decision ---")
print(f"decision:       {output.decision.value}")
print(f"diagnosis:      {output.diagnosis}")
print(f"confidence:     {output.confidence_score:.2f}")
print(f"evidence:       {output.evidence}")
print(f"evidence_gap:   {output.evidence_gap}")
print(f"next_check:     {output.next_check}")

out_path = 'results/agent_once_output.json'
with open(out_path, 'w') as f:
    json.dump(output.model_dump(), f, indent=2, default=str)
print(f"\nFull output written to {out_path}")
