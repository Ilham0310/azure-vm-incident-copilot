"""
Quick script to check agent status and recent results
"""
import json
from pathlib import Path
from datetime import datetime

print("=" * 60)
print("Agent Status Check")
print("=" * 60)
print()

# Check if output file exists
output_path = Path("results/output.jsonl")

if not output_path.exists():
    print("❌ No results yet!")
    print()
    print("The agent hasn't completed its first scan yet.")
    print()
    print("What to do:")
    print("1. Wait 10-15 seconds for first scan to complete")
    print("2. Or click 'Scan Now' button in Dashboard tab")
    print("3. Check the terminal where you ran 'python main.py --ui' for errors")
    print()
else:
    print("✅ Results file found!")
    print()
    
    # Read last 5 results
    with open(output_path, 'r') as f:
        lines = f.readlines()
    
    print(f"Total scans: {len(lines)}")
    print()
    
    if lines:
        print("Last 5 scans:")
        print("-" * 60)
        
        for line in lines[-5:]:
            try:
                record = json.loads(line)
                timestamp = record.get('timestamp', 'Unknown')
                vm_name = record.get('vm_name', 'Unknown')
                decision = record.get('diagnostic_output', {}).get('decision', 'Unknown')
                confidence = record.get('diagnostic_output', {}).get('confidence_score', 0)
                duration = record.get('cycle_duration_ms', 0)
                
                print(f"[{timestamp}]")
                print(f"  VM: {vm_name}")
                print(f"  Decision: {decision}")
                print(f"  Confidence: {confidence:.2f}")
                print(f"  Duration: {duration:.0f}ms")
                print()
            except:
                continue
        
        print("-" * 60)
        print()
        print("✅ Agent is working!")
        print()
        print("View results in web UI:")
        print("  - Dashboard tab: Latest status")
        print("  - Live Feed tab: All results")
    else:
        print("❌ Results file is empty")
        print()
        print("The agent hasn't completed any scans yet.")

print("=" * 60)
