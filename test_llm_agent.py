"""
Test LLM-based decision engine with Azure VM telemetry
"""
import json
import os
from agent.config import AgentConfig
from agent.collector import TelemetryCollectorAgent
from src.llm.llm_engine import LLMDecisionEngine
from src.confidence_scorer import ConfidenceScorer
from src.explanation_formatter import ExplanationFormatter

# Add Azure CLI to PATH
azure_cli_path = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin"
if azure_cli_path not in os.environ['PATH']:
    os.environ['PATH'] = azure_cli_path + os.pathsep + os.environ['PATH']

def main():
    print("=" * 60)
    print("Azure VM Incident Copilot - LLM Test")
    print("=" * 60)
    print()
    
    # Your VM details
    vm_name = "Test-VM"
    resource_group = "AZ26POC1-CO-LAB"
    subscription_id = "be8946da-5ca2-4129-ae53-b6124a0aa2d1"
    
    print(f"VM Name: {vm_name}")
    print(f"Resource Group: {resource_group}")
    print(f"LLM Enabled: {os.getenv('LLM_ENABLED', 'false')}")
    print()
    
    # Step 1: Collect telemetry
    print("Step 1/3: Collecting telemetry from Azure...")
    config = AgentConfig(
        subscription_id=subscription_id,
        resource_group=resource_group,
        vm_name=vm_name
    )
    
    collector = TelemetryCollectorAgent(config)
    telemetry = collector.collect()
    print("✓ Telemetry collected")
    print()
    
    # Step 2: Run LLM decision engine
    print("Step 2/3: Running LLM decision engine...")
    print("  (Using Groq API with llama-3.3-70b-versatile)")
    try:
        scorer = ConfidenceScorer()
        completeness, confidence_score, conflicts = scorer.score_telemetry(
            telemetry,
            pattern_match="exact"
        )
        
        engine = LLMDecisionEngine()
        decision = engine.decide(telemetry, confidence_score, completeness)
        
        print("✓ LLM decision made")
        print()
        
        # Display LLM metadata
        if hasattr(decision, 'llm_provider'):
            print(f"LLM Provider: {decision.llm_provider}")
        if hasattr(decision, 'similar_incidents_used'):
            print(f"Similar Incidents Retrieved: {decision.similar_incidents_used}")
        if hasattr(decision, 'sops_consulted'):
            print(f"SOPs Consulted: {', '.join(decision.sops_consulted) if decision.sops_consulted else 'None'}")
        if hasattr(decision, 'is_novel_incident'):
            print(f"Novel Incident: {decision.is_novel_incident}")
        print()
        
    except Exception as e:
        print(f"✗ Error in LLM engine: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 3: Format output
    print("Step 3/3: Formatting output...")
    formatter = ExplanationFormatter()
    output = formatter.format_output(decision, telemetry, confidence_score)
    
    # Save output
    output_dict = output.model_dump()
    with open("results/test_llm_diagnosis.json", "w") as f:
        json.dump(output_dict, f, indent=2, default=str)
    
    print("✓ Output saved to: results/test_llm_diagnosis.json")
    print()
    
    # Display results
    print("=" * 60)
    print("LLM DIAGNOSTIC RESULTS")
    print("=" * 60)
    print()
    print(f"Decision: {output.decision}")
    print(f"Confidence: {output.confidence_score}")
    print()
    print(f"Diagnosis:")
    print(f"  {output.diagnosis}")
    print()
    print(f"Evidence:")
    for evidence in output.evidence:
        print(f"  • {evidence}")
    print()
    print(f"Next Check:")
    print(f"  {output.next_check}")
    print()
    print("=" * 60)
    print("✓ LLM test completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
