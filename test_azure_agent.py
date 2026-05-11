"""
Test script to collect telemetry from Azure VM using Azure CLI credentials
"""
import json
import os
from agent.config import AgentConfig
from agent.collector import TelemetryCollectorAgent
from src.validator import SchemaValidator
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine
from src.explanation_formatter import ExplanationFormatter

# Add Azure CLI to PATH
azure_cli_path = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin"
if azure_cli_path not in os.environ['PATH']:
    os.environ['PATH'] = azure_cli_path + os.pathsep + os.environ['PATH']

def main():
    print("=" * 60)
    print("Azure VM Incident Copilot - Agent Test")
    print("=" * 60)
    print()
    
    # Your VM details
    vm_name = "Test-VM"
    resource_group = "AZ26POC1-CO-LAB"
    subscription_id = "be8946da-5ca2-4129-ae53-b6124a0aa2d1"
    
    print(f"VM Name: {vm_name}")
    print(f"Resource Group: {resource_group}")
    print(f"Subscription ID: {subscription_id}")
    print()
    
    # Step 1: Create agent config
    print("Step 1/5: Creating agent configuration...")
    config = AgentConfig(
        subscription_id=subscription_id,
        resource_group=resource_group,
        vm_name=vm_name,
        log_analytics_workspace_id=None,  # Optional
        interval_seconds=300
    )
    print("✓ Configuration created")
    print()
    
    # Step 2: Initialize collector
    print("Step 2/5: Initializing telemetry collector...")
    print("  (Using Azure CLI credentials via DefaultAzureCredential)")
    collector = TelemetryCollectorAgent(config)
    print("✓ Collector initialized")
    print()
    
    # Step 3: Collect telemetry
    print("Step 3/5: Collecting telemetry from Azure...")
    print("  This may take 10-15 seconds...")
    try:
        telemetry = collector.collect()
        print("✓ Telemetry collected successfully!")
        print()
        
        # Save telemetry to file
        telemetry_dict = telemetry.model_dump()
        with open("results/test_telemetry.json", "w") as f:
            json.dump(telemetry_dict, f, indent=2, default=str)
        print(f"✓ Saved to: results/test_telemetry.json")
        print()
        
        # Display key fields
        print("Key Telemetry Fields:")
        print(f"  Power State: {telemetry.power_state}")
        print(f"  Provisioning State: {telemetry.provisioning_state}")
        print(f"  Resource Health: {telemetry.resource_health_status}")
        print(f"  CPU Percent: {telemetry.cpu_percent}")
        print(f"  Memory Percent: {telemetry.memory_percent}")
        print(f"  Data Completeness: {telemetry.data_completeness_percent}%")
        print()
        
    except Exception as e:
        print(f"✗ Error collecting telemetry: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        return
    
    # Step 4: Run decision engine
    print("Step 4/5: Running decision engine...")
    try:
        # Calculate confidence
        scorer = ConfidenceScorer()
        completeness, confidence_score, conflicts = scorer.score_telemetry(
            telemetry,
            pattern_match="exact"
        )
        
        # Make decision
        engine = DecisionEngine()
        decision = engine.decide(telemetry, confidence_score, completeness)
        
        print("✓ Decision made")
        print()
        
    except Exception as e:
        print(f"✗ Error in decision engine: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 5: Format output
    print("Step 5/5: Formatting diagnostic output...")
    try:
        formatter = ExplanationFormatter()
        output = formatter.format_output(decision, telemetry, confidence_score)
        
        # Save output
        output_dict = output.model_dump()
        with open("results/test_diagnosis.json", "w") as f:
            json.dump(output_dict, f, indent=2, default=str)
        
        print("✓ Output formatted")
        print()
        
        # Display results
        print("=" * 60)
        print("DIAGNOSTIC RESULTS")
        print("=" * 60)
        print()
        print(f"Decision: {output.decision}")
        print(f"Confidence Score: {output.confidence_score}")
        print()
        print(f"Diagnosis:")
        print(f"  {output.diagnosis}")
        print()
        print(f"Evidence:")
        for evidence in output.evidence:
            print(f"  • {evidence}")
        print()
        print(f"Evidence Gap:")
        for gap in output.evidence_gap:
            print(f"  • {gap}")
        print()
        print(f"Next Check:")
        print(f"  {output.next_check}")
        print()
        print(f"Explanation:")
        print(f"  {output.explanation}")
        print()
        
        print("=" * 60)
        print("✓ Test completed successfully!")
        print("=" * 60)
        print()
        print("Files saved:")
        print("  - results/test_telemetry.json (collected telemetry)")
        print("  - results/test_diagnosis.json (diagnostic output)")
        print()
        
    except Exception as e:
        print(f"✗ Error formatting output: {str(e)}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    main()
