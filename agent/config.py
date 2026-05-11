"""
Agent Configuration Module

This module provides configuration management for the TelemetryCollectorAgent.
Configuration can be loaded from JSON files or environment variables.
"""

import os
import json
from typing import Optional
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """
    Configuration for TelemetryCollectorAgent.
    
    Can be loaded from:
    - JSON config file (--config agent_config.json)
    - Environment variables (AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, etc.)
    
    Attributes:
        subscription_id: Azure subscription ID
        resource_group: Azure resource group name
        vm_name: Azure VM name
        log_analytics_workspace_id: Log Analytics workspace ID (optional)
        app_insights_connection_string: Application Insights connection string (optional)
        interval_seconds: Collection interval in seconds (default: 300 = 5 minutes)
        output_dir: Directory for results output (default: "results/")
        alert_on_diagnose: Alert when decision is diagnose (default: True)
        alert_on_low_confidence: Alert when decision is diagnose_low_confidence (default: True)
    """
    
    subscription_id: str
    resource_group: str
    vm_name: str
    log_analytics_workspace_id: Optional[str] = None
    app_insights_connection_string: Optional[str] = None
    interval_seconds: int = Field(default=300, ge=1)
    output_dir: str = "results/"
    alert_on_diagnose: bool = True
    alert_on_low_confidence: bool = True
    
    # Dual workspace support
    # Workspace for VM Insights metrics (InsightsMetrics, VMComputer, VMProcess)
    # Get via: az monitor log-analytics workspace show --workspace-name monitor1 --query customerId -o tsv
    monitor_workspace_id: Optional[str] = None
    monitor_workspace_name: str = "monitor1"
    # Workspace for logs/heartbeat (Heartbeat, Event, Syslog, custom DCR data)
    # Get via: az monitor log-analytics workspace show --workspace-name loganalytics --query customerId -o tsv
    log_analytics_workspace_name: str = "loganalytics"
    
    def validate_workspaces(self) -> list:
        """
        Non-throwing validator for workspace configuration.
        
        Returns a list of human-readable error strings if workspace
        configuration is incomplete. Returns empty list if all good.
        Does not raise — callers decide how to handle errors.
        """
        return self.validate_workspace_mapping()
    
    def validate_workspace_mapping(self) -> list:
        """
        Strict validator: checks IDs are set, distinct, and names are not
        accidentally swapped. Returns list of human-readable error strings.
        Does not raise.
        """
        errors = []
        if not self.monitor_workspace_id:
            errors.append(
                f"MONITOR_WORKSPACE_ID not set (for '{self.monitor_workspace_name}'). "
                "Get it via: az monitor log-analytics workspace show "
                f"--workspace-name {self.monitor_workspace_name} "
                "--query customerId -o tsv"
            )
        if not self.log_analytics_workspace_id:
            errors.append(
                f"LOG_ANALYTICS_WORKSPACE_ID not set (for '{self.log_analytics_workspace_name}'). "
                "Get it via: az monitor log-analytics workspace show "
                f"--workspace-name {self.log_analytics_workspace_name} "
                "--query customerId -o tsv"
            )
        if (self.monitor_workspace_id and self.log_analytics_workspace_id
                and self.monitor_workspace_id == self.log_analytics_workspace_id):
            errors.append(
                "MONITOR_WORKSPACE_ID and LOG_ANALYTICS_WORKSPACE_ID are identical. "
                "They must be different workspaces."
            )
        if (self.monitor_workspace_name and self.log_analytics_workspace_name
                and self.monitor_workspace_name == self.log_analytics_workspace_name):
            errors.append(
                f"MONITOR_WORKSPACE_NAME and LOG_ANALYTICS_WORKSPACE_NAME are both "
                f"'{self.monitor_workspace_name}'. They should be different names."
            )
        return errors
    
    @classmethod
    def from_file(cls, config_path: str) -> 'AgentConfig':
        """
        Load configuration from JSON file.
        
        Args:
            config_path: Path to JSON configuration file
        
        Returns:
            AgentConfig instance
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If JSON is invalid or missing required fields
        
        Example JSON:
            {
                "subscription_id": "12345678-1234-1234-1234-123456789012",
                "resource_group": "my-resource-group",
                "vm_name": "my-vm",
                "monitor_workspace_id": "monitor1-workspace-customer-id",
                "log_analytics_workspace_id": "loganalytics-workspace-customer-id",
                "monitor_workspace_name": "monitor1",
                "log_analytics_workspace_name": "loganalytics",
                "interval_seconds": 300,
                "output_dir": "results/",
                "alert_on_diagnose": true,
                "alert_on_low_confidence": true
            }
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load configuration: {e}")
    
    @classmethod
    def from_env(cls) -> 'AgentConfig':
        """
        Load configuration from environment variables.
        
        Environment variables:
            AZURE_SUBSCRIPTION_ID: Azure subscription ID (required)
            AZURE_RESOURCE_GROUP: Azure resource group name (required)
            AZURE_VM_NAME: Azure VM name (required)
            AZURE_WORKSPACE_ID: Legacy single workspace ID (optional, fallback for LOG_ANALYTICS_WORKSPACE_ID)
            LOG_ANALYTICS_WORKSPACE_ID: Workspace ID for loganalytics (Heartbeat, logs)
            MONITOR_WORKSPACE_ID: Workspace ID for monitor1 (InsightsMetrics, VMComputer)
            MONITOR_WORKSPACE_NAME: Name of monitor workspace (default: monitor1)
            LOG_ANALYTICS_WORKSPACE_NAME: Name of log analytics workspace (default: loganalytics)
            AZURE_APP_INSIGHTS_CONNECTION_STRING: Application Insights connection string (optional)
            AGENT_INTERVAL_SECONDS: Collection interval in seconds (optional, default: 300)
            AGENT_OUTPUT_DIR: Directory for results output (optional, default: "results/")
            AGENT_ALERT_ON_DIAGNOSE: Alert on diagnose decision (optional, default: true)
            AGENT_ALERT_ON_LOW_CONFIDENCE: Alert on low confidence decision (optional, default: true)
        
        Returns:
            AgentConfig instance
        
        Raises:
            ValueError: If required environment variables are missing
        """
        # Required fields
        subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        resource_group = os.getenv('AZURE_RESOURCE_GROUP')
        vm_name = os.getenv('AZURE_VM_NAME')
        
        if not subscription_id:
            raise ValueError("Missing required environment variable: AZURE_SUBSCRIPTION_ID")
        if not resource_group:
            raise ValueError("Missing required environment variable: AZURE_RESOURCE_GROUP")
        if not vm_name:
            raise ValueError("Missing required environment variable: AZURE_VM_NAME")
        
        # Optional fields — prefer explicit LOG_ANALYTICS_WORKSPACE_ID;
        # fall back to legacy AZURE_WORKSPACE_ID only if it looks like a real GUID
        _legacy_ws = os.getenv('AZURE_WORKSPACE_ID', '').strip()
        _legacy_ws = _legacy_ws if (len(_legacy_ws) == 36 and '-' in _legacy_ws) else None
        log_analytics_workspace_id = os.getenv('LOG_ANALYTICS_WORKSPACE_ID') or _legacy_ws
        app_insights_connection_string = os.getenv('AZURE_APP_INSIGHTS_CONNECTION_STRING')
        
        # Dual workspace support
        monitor_workspace_id = os.getenv('MONITOR_WORKSPACE_ID')
        monitor_workspace_name = os.getenv('MONITOR_WORKSPACE_NAME', 'monitor1')
        log_analytics_workspace_name = os.getenv('LOG_ANALYTICS_WORKSPACE_NAME', 'loganalytics')
        
        # Parse interval_seconds with default
        interval_seconds = 300
        interval_env = os.getenv('AGENT_INTERVAL_SECONDS')
        if interval_env:
            try:
                interval_seconds = int(interval_env)
            except ValueError:
                raise ValueError(f"Invalid AGENT_INTERVAL_SECONDS value: {interval_env} (must be integer)")
        
        # Parse output_dir with default
        output_dir = os.getenv('AGENT_OUTPUT_DIR', 'results/')
        
        # Parse boolean flags with defaults
        alert_on_diagnose = os.getenv('AGENT_ALERT_ON_DIAGNOSE', 'true').lower() in ('true', '1', 'yes')
        alert_on_low_confidence = os.getenv('AGENT_ALERT_ON_LOW_CONFIDENCE', 'true').lower() in ('true', '1', 'yes')
        
        return cls(
            subscription_id=subscription_id,
            resource_group=resource_group,
            vm_name=vm_name,
            log_analytics_workspace_id=log_analytics_workspace_id,
            app_insights_connection_string=app_insights_connection_string,
            interval_seconds=interval_seconds,
            output_dir=output_dir,
            alert_on_diagnose=alert_on_diagnose,
            alert_on_low_confidence=alert_on_low_confidence,
            monitor_workspace_id=monitor_workspace_id,
            monitor_workspace_name=monitor_workspace_name,
            log_analytics_workspace_name=log_analytics_workspace_name
        )
