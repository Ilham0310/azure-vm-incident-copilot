"""
Benchmark loader component for Azure VM Incident Copilot.

This module provides the BenchmarkLoader class that:
- Loads benchmark cases from CSV or JSON files
- Validates benchmark case structure
- Parses telemetry_input JSON strings
- Returns list of BenchmarkCase objects
"""

import csv
import json
from typing import List
from pathlib import Path

from src.models import BenchmarkCase, TelemetryInput, DecisionState


class BenchmarkLoader:
    """
    Loads and parses benchmark test cases from files.
    
    Responsibilities:
    - Load benchmark cases from CSV or JSON files
    - Validate benchmark case structure
    - Parse telemetry_input JSON strings into TelemetryInput objects
    - Handle file not found and invalid format errors
    """
    
    def load_cases(self, benchmark_file: str) -> List[BenchmarkCase]:
        """
        Loads benchmark cases from file.
        
        Supports JSON and CSV formats.
        Validates benchmark case structure.
        
        Args:
            benchmark_file: Path to benchmark data file (.json or .csv)
            
        Returns:
            List of 25-50 benchmark cases
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        file_path = Path(benchmark_file)
        
        # Check if file exists
        if not file_path.exists():
            raise FileNotFoundError(f"Benchmark file not found: {benchmark_file}")
        
        # Determine format from extension
        if file_path.suffix.lower() == '.json':
            return self._load_from_json(file_path)
        elif file_path.suffix.lower() == '.csv':
            return self._load_from_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}. Use .json or .csv")
    
    def _load_from_json(self, file_path: Path) -> List[BenchmarkCase]:
        """
        Load benchmark cases from JSON file.
        
        Expected format:
        [
            {
                "case_id": "001",
                "case_name": "VM Stopped by User",
                "incident_pattern": "vm_stopped_by_user",
                "telemetry_input": {...},
                "expected_decision": "diagnose",
                "expected_diagnosis": "VM Stopped by user deallocation",
                "notes": "Clean stop with successful provisioning"
            },
            ...
        ]
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            List of BenchmarkCase objects
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
        
        if not isinstance(data, list):
            raise ValueError("JSON file must contain an array of benchmark cases")
        
        cases = []
        for idx, item in enumerate(data):
            try:
                case = self._parse_case_dict(item)
                cases.append(case)
            except Exception as e:
                raise ValueError(f"Error parsing case {idx}: {e}")
        
        return cases
    
    def _load_from_csv(self, file_path: Path) -> List[BenchmarkCase]:
        """
        Load benchmark cases from CSV file.
        
        Expected columns:
        - case_id
        - case_name
        - incident_pattern
        - telemetry_input (JSON string)
        - expected_decision
        - expected_diagnosis
        - notes
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            List of BenchmarkCase objects
        """
        cases = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                
                # Validate required columns
                required_columns = ['case_id', 'case_name', 'incident_pattern', 
                                   'telemetry_input', 'expected_decision']
                if not all(col in reader.fieldnames for col in required_columns):
                    raise ValueError(f"CSV missing required columns. Required: {required_columns}")
                
                for idx, row in enumerate(reader):
                    try:
                        # Parse telemetry_input from JSON string
                        row['telemetry_input'] = json.loads(row['telemetry_input'])
                        case = self._parse_case_dict(row)
                        cases.append(case)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Error parsing telemetry_input JSON in row {idx+2}: {e}")
                    except Exception as e:
                        raise ValueError(f"Error parsing case in row {idx+2}: {e}")
        
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Error reading CSV file: {e}")
        
        return cases
    
    def _parse_case_dict(self, case_dict: dict) -> BenchmarkCase:
        """
        Parse a dictionary into a BenchmarkCase object.
        
        Args:
            case_dict: Dictionary with case data
            
        Returns:
            BenchmarkCase object
            
        Raises:
            ValueError: If case structure is invalid
        """
        # Validate required fields
        required_fields = ['case_id', 'case_name', 'incident_pattern', 
                          'telemetry_input', 'expected_decision']
        for field in required_fields:
            if field not in case_dict:
                raise ValueError(f"Missing required field: {field}")
        
        # Parse telemetry_input into TelemetryInput object
        try:
            telemetry = TelemetryInput(**case_dict['telemetry_input'])
        except Exception as e:
            raise ValueError(f"Invalid telemetry_input: {e}")
        
        # Parse expected_decision into DecisionState enum
        try:
            expected_decision = DecisionState(case_dict['expected_decision'])
        except ValueError:
            raise ValueError(f"Invalid expected_decision: {case_dict['expected_decision']}")
        
        # Create BenchmarkCase
        case = BenchmarkCase(
            case_id=case_dict['case_id'],
            case_name=case_dict['case_name'],
            incident_pattern=case_dict['incident_pattern'],
            telemetry_input=telemetry,
            expected_decision=expected_decision,
            expected_diagnosis=case_dict.get('expected_diagnosis'),
            notes=case_dict.get('notes')
        )
        
        return case


if __name__ == "__main__":
    # Example usage
    loader = BenchmarkLoader()
    
    try:
        cases = loader.load_cases("data/benchmark_cases.csv")
        print(f"Loaded {len(cases)} benchmark cases")
        
        # Show first case
        if cases:
            case = cases[0]
            print(f"\nFirst case:")
            print(f"  ID: {case.case_id}")
            print(f"  Name: {case.case_name}")
            print(f"  Pattern: {case.incident_pattern}")
            print(f"  Expected Decision: {case.expected_decision.value}")
            print(f"  Telemetry: power_state={case.telemetry_input.power_state.value}")
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ValueError as e:
        print(f"Error: {e}")
