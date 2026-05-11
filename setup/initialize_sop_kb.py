"""
SOP Knowledge Base Initialization Script

Loads all 12 Standard Operating Procedures from markdown files
and populates the ChromaDB vector store.

Usage:
    python setup/initialize_sop_kb.py
"""

import sys
import os
from pathlib import Path
import re

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.sop_knowledge import SOPKnowledgeBase


def parse_sop_markdown(file_path: Path) -> dict:
    """
    Parse SOP markdown file into structured data.
    
    Args:
        file_path: Path to SOP markdown file
        
    Returns:
        Dict with sop_id, title, description, triggers, steps, warnings
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract sections using regex
    sop_id_match = re.search(r'## ID\s+(.+)', content)
    title_match = re.search(r'# SOP: (.+)', content)
    desc_match = re.search(r'## Description\s+(.+?)(?=##)', content, re.DOTALL)
    triggers_match = re.search(r'## Triggers\s+(.+?)(?=##)', content, re.DOTALL)
    steps_match = re.search(r'## Steps\s+(.+?)(?=##)', content, re.DOTALL)
    warnings_match = re.search(r'## Warnings\s+(.+?)(?=$)', content, re.DOTALL)
    
    return {
        'sop_id': sop_id_match.group(1).strip() if sop_id_match else '',
        'title': title_match.group(1).strip() if title_match else '',
        'description': desc_match.group(1).strip() if desc_match else '',
        'triggers': triggers_match.group(1).strip() if triggers_match else '',
        'steps': steps_match.group(1).strip() if steps_match else '',
        'warnings': warnings_match.group(1).strip() if warnings_match else ''
    }


def main():
    """Initialize SOP knowledge base with all SOPs"""
    print("=" * 70)
    print("SOP Knowledge Base Initialization")
    print("=" * 70)
    
    # Initialize knowledge base
    print("\n[1/3] Initializing SOP knowledge base...")
    kb = SOPKnowledgeBase()
    
    # Check if already populated
    existing_count = kb.get_sop_count()
    if existing_count > 0:
        print(f"   ⚠ Knowledge base already contains {existing_count} SOPs")
        response = input("   Clear and re-initialize? (y/N): ")
        if response.lower() == 'y':
            print("   Clearing existing SOPs...")
            kb.clear()
        else:
            print("   Keeping existing SOPs. Exiting.")
            return
    
    # Find all SOP files
    sop_dir = Path("data/sops")
    if not sop_dir.exists():
        print(f"   ✗ Error: SOP directory not found: {sop_dir}")
        sys.exit(1)
    
    sop_files = list(sop_dir.glob("sop_*.md"))
    print(f"   ✓ Found {len(sop_files)} SOP files")
    
    # Required SOPs
    required_sops = [
        'sop_start_stop_vm',
        'sop_firewall_whitelist',
        'sop_disk_cleanup',
        'sop_disk_expansion',
        'sop_ssl_renewal',
        'sop_backup',
        'sop_vm_scale',
        'sop_finops_rightsize',
        'sop_request_admin_access',
        'sop_decommission',
        'sop_url_onboarding',
        'sop_cloud_resource_access'
    ]
    
    # Load and add each SOP
    print("\n[2/3] Loading SOPs...")
    loaded_sops = []
    
    for sop_file in sop_files:
        try:
            print(f"   Loading {sop_file.name}...", end=" ")
            sop_data = parse_sop_markdown(sop_file)
            
            if not sop_data['sop_id']:
                print("✗ Missing SOP ID")
                continue
            
            success = kb.add_sop(
                sop_id=sop_data['sop_id'],
                title=sop_data['title'],
                description=sop_data['description'],
                triggers=sop_data['triggers'],
                steps=sop_data['steps'],
                warnings=sop_data['warnings']
            )
            
            if success:
                print("✓")
                loaded_sops.append(sop_data['sop_id'])
            else:
                print("✗ Failed to add")
                
        except Exception as e:
            print(f"✗ Error: {e}")
    
    # Validate all required SOPs are present
    print("\n[3/3] Validating SOPs...")
    missing_sops = [sop for sop in required_sops if sop not in loaded_sops]
    
    if missing_sops:
        print(f"   ✗ Missing required SOPs: {', '.join(missing_sops)}")
        sys.exit(1)
    
    print(f"   ✓ All {len(required_sops)} required SOPs loaded")
    
    # Final summary
    final_count = kb.get_sop_count()
    print("\n" + "=" * 70)
    print(f"✓ SOP Knowledge Base initialized successfully!")
    print(f"  Total SOPs: {final_count}")
    print("=" * 70)


if __name__ == "__main__":
    main()
