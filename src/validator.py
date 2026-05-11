"""
Schema validation component for Azure VM Incident Copilot.

This module provides the SchemaValidator class that:
- Parses JSON input with detailed error reporting (line/column)
- Validates against triage schema using jsonschema library
- Returns ValidationResult with parsed TelemetryInput or detailed errors
- Ignores unknown fields for forward compatibility
"""

import json
from typing import Dict, Any
from jsonschema import validate, ValidationError as JsonSchemaValidationError, Draft7Validator
from pydantic import ValidationError as PydanticValidationError

from src.models import TelemetryInput, ValidationResult, ValidationError


class JSONParseError(Exception):
    """Exception raised when JSON parsing fails with line/column details"""
    def __init__(self, message: str, line: int = None, column: int = None):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self.format_message())
    
    def format_message(self) -> str:
        """Format error message with line/column information"""
        if self.line is not None and self.column is not None:
            return f"JSON parse error at line {self.line}, column {self.column}: {self.message}"
        return f"JSON parse error: {self.message}"


class SchemaValidationError(Exception):
    """Exception raised when schema validation fails"""
    def __init__(self, errors: list):
        self.errors = errors
        super().__init__(f"Schema validation failed with {len(errors)} error(s)")


class SchemaValidator:
    """
    Validates JSON input against the triage schema.
    
    Responsibilities:
    - Parse JSON with detailed error reporting
    - Validate data types for all 30+ telemetry fields
    - Validate enum constraints and numeric ranges
    - Ignore unknown fields (forward compatibility)
    - Return detailed validation errors with field names and constraints
    """
    
    def __init__(self, schema_path: str = "schemas/azure_vm_triage_schema.json"):
        """
        Initialize validator with schema.
        
        Args:
            schema_path: Path to JSON schema file
        """
        self.schema_path = schema_path
        self.schema = self._load_schema()
        self.validator = Draft7Validator(self.schema)
    
    def _load_schema(self) -> Dict[str, Any]:
        """
        Load JSON schema from file.
        
        Returns:
            Schema dictionary
            
        Raises:
            FileNotFoundError: If schema file doesn't exist
            JSONParseError: If schema file is not valid JSON
        """
        try:
            with open(self.schema_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
        except json.JSONDecodeError as e:
            raise JSONParseError(str(e), e.lineno, e.colno)
    
    def validate(self, json_input: str) -> ValidationResult:
        """
        Validates JSON input against triage schema.
        
        Args:
            json_input: Raw JSON string
            
        Returns:
            ValidationResult with parsed TelemetryInput or validation errors
            
        Raises:
            JSONParseError: If JSON is malformed
            
        Process:
        1. Parse JSON with detailed error reporting (raises JSONParseError if malformed)
        2. Validate against JSON schema (type/range/enum constraints)
        3. Parse into TelemetryInput Pydantic model
        4. Return ValidationResult
        """
        # Step 1: Parse JSON (raises JSONParseError if malformed)
        data = self._parse_json(json_input)
        
        # Step 2: Validate against JSON schema
        schema_errors = self._validate_against_schema(data)
        if schema_errors:
            return ValidationResult(
                valid=False,
                errors=schema_errors
            )
        
        # Step 3: Parse into Pydantic model
        try:
            telemetry = TelemetryInput(**data)
            return ValidationResult(
                valid=True,
                telemetry=telemetry,
                errors=[]
            )
        except PydanticValidationError as e:
            # Convert Pydantic errors to our ValidationError format
            errors = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error['loc'])
                errors.append(ValidationError(
                    field=field,
                    message=error['msg'],
                    value=str(error.get('input', ''))
                ))
            return ValidationResult(
                valid=False,
                errors=errors
            )
    
    def _parse_json(self, json_input: str) -> Dict[str, Any]:
        """
        Parse JSON with detailed error reporting.
        
        Args:
            json_input: Raw JSON string
            
        Returns:
            Parsed dictionary
            
        Raises:
            JSONParseError: If JSON is malformed (includes line/column details)
        """
        try:
            return json.loads(json_input)
        except json.JSONDecodeError as e:
            raise JSONParseError(
                message=e.msg,
                line=e.lineno,
                column=e.colno
            )
    
    def _validate_against_schema(self, data: Dict[str, Any]) -> list:
        """
        Validate data against JSON schema.
        
        Args:
            data: Parsed JSON dictionary
            
        Returns:
            List of ValidationError objects (empty if valid)
        """
        errors = []
        
        # Use jsonschema validator to get all errors
        for error in self.validator.iter_errors(data):
            # Extract field path
            field_path = ".".join(str(p) for p in error.path) if error.path else "root"
            
            # Extract constraint violation details
            message = error.message
            
            # Get the actual value that failed
            value = None
            if error.path:
                try:
                    current = data
                    for key in error.path:
                        current = current[key]
                    value = str(current)
                except (KeyError, TypeError, IndexError):
                    value = None
            
            errors.append(ValidationError(
                field=field_path,
                message=message,
                value=value
            ))
        
        return errors
    
    def validate_dict(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate a dictionary directly (skip JSON parsing).
        
        Useful for testing or when data is already parsed.
        
        Args:
            data: Dictionary to validate
            
        Returns:
            ValidationResult with parsed TelemetryInput or validation errors
        """
        # Validate against JSON schema
        schema_errors = self._validate_against_schema(data)
        if schema_errors:
            return ValidationResult(
                valid=False,
                errors=schema_errors
            )
        
        # Parse into Pydantic model
        try:
            telemetry = TelemetryInput(**data)
            return ValidationResult(
                valid=True,
                telemetry=telemetry,
                errors=[]
            )
        except PydanticValidationError as e:
            # Convert Pydantic errors to our ValidationError format
            errors = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error['loc'])
                errors.append(ValidationError(
                    field=field,
                    message=error['msg'],
                    value=str(error.get('input', ''))
                ))
            return ValidationResult(
                valid=False,
                errors=errors
            )


if __name__ == "__main__":
    # Example usage
    validator = SchemaValidator()
    
    # Test with valid JSON
    valid_json = '''
    {
        "power_state": "Running",
        "provisioning_state": "Succeeded",
        "resource_health_status": "Available",
        "cpu_percent": 45.5,
        "memory_percent": 60.0
    }
    '''
    
    result = validator.validate(valid_json)
    print(f"Valid: {result.valid}")
    if result.valid:
        print(f"Telemetry: {result.telemetry}")
    else:
        print(f"Errors: {result.errors}")
    
    # Test with invalid JSON (malformed)
    invalid_json = '''
    {
        "power_state": "Running",
        "provisioning_state": "Succeeded"
        "resource_health_status": "Available"
    }
    '''
    
    result = validator.validate(invalid_json)
    print(f"\nValid: {result.valid}")
    if not result.valid:
        print(f"Errors: {result.errors}")
    
    # Test with invalid enum value
    invalid_enum_json = '''
    {
        "power_state": "InvalidState",
        "provisioning_state": "Succeeded",
        "resource_health_status": "Available"
    }
    '''
    
    result = validator.validate(invalid_enum_json)
    print(f"\nValid: {result.valid}")
    if not result.valid:
        print(f"Errors: {result.errors}")
