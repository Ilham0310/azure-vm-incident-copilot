"""
FastAPI Web Dashboard for Azure VM Incident Copilot

This module provides a web-based dashboard for monitoring VM health and running triage operations.
Accessible at http://localhost:8000 when started with --ui flag.
"""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Load .env file so workspace IDs and other config are available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import pipeline components
from src.validator import SchemaValidator
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine
from src.explanation_formatter import ExplanationFormatter
from src.benchmark_loader import BenchmarkLoader
from src.test_harness import TestHarness


# Request/Response models
class TriageRequest(BaseModel):
    """Request model for manual triage."""
    telemetry: dict


class AgentStartRequest(BaseModel):
    """Request model for starting the agent."""
    vm_name: Optional[str] = None  # If None, scans all VMs in resource group
    resource_group: Optional[str] = None  # Defaults to .env AZURE_RESOURCE_GROUP
    subscription_id: Optional[str] = None  # Defaults to .env AZURE_SUBSCRIPTION_ID
    workspace_id: Optional[str] = None
    interval_seconds: int = 300


class AgentStatusResponse(BaseModel):
    """Response model for agent status."""
    running: bool
    config: Optional[Dict] = None
    last_run: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Request model for feedback submission."""
    correct: bool
    corrected_diagnosis: Optional[str] = None
    corrected_next_check: Optional[str] = None
    outcome: str = "resolved"


# Global agent state (for background agent control)
_agent_scheduler = None
_agent_config = None


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        FastAPI instance with all routes configured
    """
    app = FastAPI(
        title="Azure VM Incident Copilot Dashboard",
        description="Web dashboard for VM health monitoring and triage operations",
        version="1.0.0"
    )
    
    # Mount static files directory
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Root route - serve index.html
    @app.get("/")
    async def root():
        """Serve the main dashboard HTML page."""
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        else:
            return JSONResponse(
                status_code=404,
                content={"error": "Dashboard not found. Create ui/static/index.html"}
            )
    
    # API Routes
    
    @app.get("/api/status")
    async def get_status():
        """
        Get latest VM status from results/output.jsonl.
        
        Returns:
            Latest diagnostic output record
        """
        try:
            output_path = Path("results/output.jsonl")
            
            if not output_path.exists():
                return JSONResponse(
                    status_code=404,
                    content={"error": "No results found. Run agent first."}
                )
            
            # Read last line from file
            with open(output_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines:
                    return JSONResponse(
                        status_code=404,
                        content={"error": "No results found"}
                    )
                
                last_line = lines[-1].strip()
                record = json.loads(last_line)
                return record
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/feed")
    async def get_feed(decision: Optional[str] = None, limit: int = 50):
        """
        Get last N rows from results/output.jsonl with optional decision filter.
        
        Args:
            decision: Filter by decision state (optional)
            limit: Maximum number of rows to return (default: 50)
        
        Returns:
            List of diagnostic output records
        """
        try:
            output_path = Path("results/output.jsonl")
            
            if not output_path.exists():
                return []
            
            # Read all lines
            with open(output_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Parse JSON records
            records = []
            for line in lines:
                try:
                    record = json.loads(line.strip())
                    
                    # Apply decision filter if specified
                    if decision:
                        if record.get('diagnostic_output', {}).get('decision') == decision:
                            records.append(record)
                    else:
                        records.append(record)
                except json.JSONDecodeError:
                    continue
            
            # Return last N records
            return records[-limit:]
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/triage")
    async def run_triage(request: TriageRequest):
        """
        Run triage pipeline on posted telemetry JSON.
        
        Args:
            request: TriageRequest with telemetry dict
        
        Returns:
            DiagnosticOutput from the pipeline with LLM metadata
        """
        try:
            # Convert telemetry dict to JSON string
            json_input = json.dumps(request.telemetry)
            
            # Run pipeline
            validator = SchemaValidator()
            result = validator.validate(json_input)
            
            if not result.valid:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Schema validation failed",
                        "details": [e.model_dump() for e in result.errors]
                    }
                )
            
            telemetry = result.telemetry
            
            # Score confidence
            scorer = ConfidenceScorer()
            completeness, confidence_score, conflicts = scorer.score_telemetry(
                telemetry,
                pattern_match="exact"
            )
            
            # Check if LLM engine is enabled
            llm_enabled = os.getenv("LLM_ENABLED", "false").lower() == "true"
            llm_shadow_mode = os.getenv("LLM_SHADOW_MODE", "false").lower() == "true"
            
            # Shadow mode: run both engines and compare
            if llm_shadow_mode:
                try:
                    from src.shadow_mode import ShadowModeExecutor
                    executor = ShadowModeExecutor()
                    decision, comparison = executor.execute_dual(
                        telemetry,
                        confidence_score,
                        completeness
                    )
                    # Note: decision is always the rule-based result in shadow mode
                except Exception as shadow_error:
                    # Fallback to single engine on shadow mode failure
                    engine = DecisionEngine()
                    decision = engine.decide(telemetry, confidence_score, completeness)
            elif llm_enabled:
                # Use LLM decision engine
                try:
                    from src.llm.llm_engine import LLMDecisionEngine
                    engine = LLMDecisionEngine()
                    decision = engine.decide(telemetry, confidence_score, completeness)
                except Exception as llm_error:
                    # Fallback to rule-based engine on LLM failure
                    engine = DecisionEngine()
                    decision = engine.decide(telemetry, confidence_score, completeness)
            else:
                # Use rule-based decision engine
                engine = DecisionEngine()
                decision = engine.decide(telemetry, confidence_score, completeness)
            
            # Format output
            formatter = ExplanationFormatter()
            output = formatter.format_output(decision, telemetry, confidence_score)
            
            return output.model_dump()
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/agent/start")
    async def start_agent(request: AgentStartRequest):
        """
        Start agent scheduler in background thread.
        Uses preconfigured values from .env if not provided.
        
        Args:
            request: AgentStartRequest (all fields optional, defaults from .env)
        
        Returns:
            Success message
        """
        global _agent_scheduler, _agent_config
        
        try:
            # Check if agent is already running
            if _agent_scheduler and _agent_scheduler.is_running:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Agent is already running"}
                )
            
            # Add Azure CLI to PATH
            import os
            azure_cli_path = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin"
            if azure_cli_path not in os.environ.get('PATH', ''):
                os.environ['PATH'] = azure_cli_path + os.pathsep + os.environ.get('PATH', '')
            
            # Import agent components
            from agent.config import AgentConfig
            from agent.collector import TelemetryCollectorAgent
            from agent.scheduler import IncidentCopilotScheduler
            
            # Use preconfigured values from .env, override with request if provided
            sub_id = request.subscription_id or os.getenv('AZURE_SUBSCRIPTION_ID', 'be8946da-5ca2-4129-ae53-b6124a0aa2d1')
            rg = request.resource_group or os.getenv('AZURE_RESOURCE_GROUP', 'AZ26POC1-CO-LAB')
            vm = request.vm_name or os.getenv('AZURE_VM_NAME', 'testVM2')
            
            # Create config
            config = AgentConfig(
                subscription_id=sub_id,
                resource_group=rg,
                vm_name=vm,
                log_analytics_workspace_id=(
                    request.workspace_id
                    or os.getenv('LOG_ANALYTICS_WORKSPACE_ID')
                    or os.getenv('AZURE_WORKSPACE_ID')
                ),
                monitor_workspace_id=os.getenv('MONITOR_WORKSPACE_ID'),
                monitor_workspace_name=os.getenv('MONITOR_WORKSPACE_NAME', 'monitor1'),
                log_analytics_workspace_name=os.getenv('LOG_ANALYTICS_WORKSPACE_NAME', 'LogAnalytics'),
                interval_seconds=request.interval_seconds
            )
            
            # Initialize collector and scheduler
            collector = TelemetryCollectorAgent(config)
            scheduler = IncidentCopilotScheduler(config, collector)
            
            # Start scheduler in background thread
            import threading
            thread = threading.Thread(target=scheduler.run, daemon=True)
            thread.start()
            
            _agent_scheduler = scheduler
            _agent_config = config
            
            return {
                "message": "Agent started successfully",
                "config": {
                    "subscription_id": sub_id,
                    "resource_group": rg,
                    "vm_name": vm,
                    "interval_seconds": request.interval_seconds
                }
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/agent/scan-all")
    async def scan_all_vms():
        """
        Scan ALL VMs in the preconfigured resource group and run triage on each.
        No configuration needed — uses AZURE_SUBSCRIPTION_ID and AZURE_RESOURCE_GROUP from .env.
        
        Returns:
            List of triage results for each VM in the resource group
        """
        import subprocess
        
        try:
            sub_id = os.getenv('AZURE_SUBSCRIPTION_ID', 'be8946da-5ca2-4129-ae53-b6124a0aa2d1')
            rg = os.getenv('AZURE_RESOURCE_GROUP', 'AZ26POC1-CO-LAB')
            
            # List all VMs in resource group using az CLI
            cmd = ["cmd", "/c", "az", "vm", "list", "--resource-group", rg,
                   "--query", "[].{name:name, vmSize:hardwareProfile.vmSize}", "-o", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to list VMs: {result.stderr}")
            
            vms = json.loads(result.stdout) if result.stdout.strip() else []
            
            if not vms:
                return {"message": "No VMs found in resource group", "resource_group": rg, "results": []}
            
            # Triage each VM
            results = []
            scorer = ConfidenceScorer()
            engine = DecisionEngine()
            formatter = ExplanationFormatter()
            
            for vm_info in vms:
                vm_name = vm_info["name"]
                try:
                    # Get instance view
                    cmd = ["cmd", "/c", "az", "vm", "get-instance-view",
                           "--resource-group", rg, "--name", vm_name, "-o", "json"]
                    iv_result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    
                    if iv_result.returncode != 0:
                        results.append({"vm": vm_name, "error": f"Failed to get instance view: {iv_result.stderr[:200]}"})
                        continue
                    
                    iv = json.loads(iv_result.stdout)
                    instance_view = iv.get("instanceView", {})
                    statuses = instance_view.get("statuses", [])
                    
                    # Parse power state
                    power_state = "Unknown"
                    prov_state = "Succeeded"
                    for s in statuses:
                        code = s.get("code", "")
                        if code.startswith("PowerState/"):
                            ps = code.split("/")[1]
                            power_state = {"running": "Running", "stopped": "Stopped",
                                           "deallocated": "Deallocated"}.get(ps.lower(), ps.capitalize())
                        if code.startswith("ProvisioningState/"):
                            prov = code.split("/")[1].lower()
                            prov_state = {"succeeded": "Succeeded", "failed": "Failed",
                                          "updating": "Succeeded", "creating": "Succeeded"}.get(prov, "Unknown")
                    
                    # Parse agent status
                    agent_status = "Unknown"
                    vm_agent = instance_view.get("vmAgent", {})
                    if vm_agent:
                        for s in (vm_agent.get("statuses") or []):
                            display = s.get("displayStatus", "").lower()
                            msg = s.get("message", "").lower()
                            if display == "ready" or "running" in msg:
                                agent_status = "Healthy"
                                break
                            elif "not ready" in display or "not running" in msg:
                                agent_status = "NotReporting"
                                break
                    
                    heartbeat_present = agent_status == "Healthy"
                    
                    # Build telemetry with all available data from instance view
                    from src.models import TelemetryInput
                    
                    # Try to get CPU metrics from Azure Monitor (platform metrics)
                    cpu_percent = None
                    try:
                        from datetime import timedelta, timezone
                        vm_id = iv.get("id", "")
                        end_time = datetime.now(timezone.utc)
                        start_time = end_time - timedelta(minutes=10)
                        cpu_cmd = ["cmd", "/c", "az", "monitor", "metrics", "list",
                                   "--resource", vm_id,
                                   "--metric", "Percentage CPU",
                                   "--interval", "PT5M",
                                   "--start-time", start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                   "--end-time", end_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                   "-o", "json"]
                        cpu_result = subprocess.run(cpu_cmd, capture_output=True, text=True, timeout=30)
                        if cpu_result.returncode == 0 and cpu_result.stdout.strip():
                            cpu_data = json.loads(cpu_result.stdout)
                            # Extract latest non-null average
                            for ts in cpu_data.get("value", [{}])[0].get("timeseries", [{}]):
                                for dp in reversed(ts.get("data", [])):
                                    if dp.get("average") is not None:
                                        cpu_percent = round(float(dp["average"]), 1)
                                        break
                                if cpu_percent is not None:
                                    break
                    except Exception:
                        pass  # CPU metrics unavailable, continue without
                    
                    # Check NSG rules for connectivity info
                    nsg_rdp = True
                    nsg_ssh = True
                    try:
                        nic_query_cmd = ["cmd", "/c", "az", "vm", "show",
                                        "--resource-group", rg, "--name", vm_name,
                                        "--query", "networkProfile.networkInterfaces[0].id",
                                        "-o", "tsv"]
                        nic_result = subprocess.run(nic_query_cmd, capture_output=True, text=True, timeout=20)
                        if nic_result.returncode == 0 and nic_result.stdout.strip():
                            nic_name = nic_result.stdout.strip().split("/")[-1]
                            nsg_cmd = ["cmd", "/c", "az", "network", "nic", "show",
                                      "--resource-group", rg, "--name", nic_name,
                                      "--query", "networkSecurityGroup.id", "-o", "tsv"]
                            nsg_result = subprocess.run(nsg_cmd, capture_output=True, text=True, timeout=20)
                            if nsg_result.returncode == 0 and nsg_result.stdout.strip():
                                nsg_name = nsg_result.stdout.strip().split("/")[-1]
                                rules_cmd = ["cmd", "/c", "az", "network", "nsg", "rule", "list",
                                            "--resource-group", rg, "--nsg-name", nsg_name,
                                            "-o", "json"]
                                rules_result = subprocess.run(rules_cmd, capture_output=True, text=True, timeout=20)
                                if rules_result.returncode == 0 and rules_result.stdout.strip():
                                    rules = json.loads(rules_result.stdout)
                                    for rule in rules:
                                        if (rule.get("access") == "Deny" and 
                                            rule.get("direction") == "Inbound"):
                                            port = str(rule.get("destinationPortRange", ""))
                                            if "3389" in port:
                                                nsg_rdp = False
                                            if "22" in port:
                                                nsg_ssh = False
                    except Exception:
                        pass  # NSG check failed, assume open
                    
                    telemetry = TelemetryInput(
                        power_state=power_state,
                        provisioning_state=prov_state,
                        resource_health_status="Available" if power_state == "Running" else "Degraded",
                        heartbeat_present=heartbeat_present,
                        heartbeat_last_received=datetime.now().isoformat() if heartbeat_present else None,
                        azure_vm_agent_status=agent_status,
                        boot_diagnostics_status="Normal",
                        cpu_percent=cpu_percent if cpu_percent is not None else 35.0,  # Default normal if unavailable
                        memory_percent=50.0,  # Default normal — requires VM Insights for real value
                        memory_available_mb=2048.0,  # Default — requires VM Insights
                        os_disk_latency_ms=8.0,  # Default normal — requires VM Insights
                        os_disk_percent_full=45.0,  # Default normal — requires VM Insights
                        app_health_status="Unknown",
                        nsg_allow_rdp_3389=nsg_rdp,
                        nsg_allow_ssh_22=nsg_ssh,
                        connection_troubleshoot_rdp="Allow" if nsg_rdp else "Deny",
                        connection_troubleshoot_ssh="Allow" if nsg_ssh else "Deny",
                        connection_troubleshoot_verdict="Reachable" if (nsg_rdp or nsg_ssh) else "Unreachable",
                        monitor_agent_status="Healthy" if agent_status == "Healthy" else "Degraded",
                        ssl_cert_days_remaining=90,  # Default — no SSL check available
                        last_backup_status="Unknown",
                    )
                    
                    # Use pattern matching for confidence scoring (like the rule engine does)
                    pattern_hint = None
                    try:
                        match = engine._match_patterns(telemetry)
                        pattern_hint = "exact" if match else None
                    except Exception:
                        pass
                    
                    # Score and decide
                    completeness, confidence, conflicts = scorer.score_telemetry(
                        telemetry, pattern_match=pattern_hint
                    )
                    decision = engine.decide(telemetry, confidence, completeness)
                    output = formatter.format_output(decision, telemetry, confidence)
                    
                    results.append({
                        "vm": vm_name,
                        "vm_size": vm_info.get("vmSize", "?"),
                        "power_state": power_state,
                        "agent_status": agent_status,
                        "cpu_percent": cpu_percent,
                        "nsg_rdp": "Allow" if nsg_rdp else "DENY",
                        "nsg_ssh": "Allow" if nsg_ssh else "DENY",
                        "decision": decision.state.value,
                        "diagnosis": decision.diagnosis,
                        "confidence": confidence,
                        "completeness": completeness,
                        "next_check": decision.next_check,
                        "safety_rules": getattr(decision, 'safety_rules_applied', []),
                    })
                    
                except Exception as e:
                    results.append({"vm": vm_name, "error": str(e)[:300]})
            
            # Save results
            os.makedirs("results", exist_ok=True)
            scan_path = f"results/scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(scan_path, "w") as f:
                json.dump(results, f, indent=2, default=str)
            
            return {
                "message": f"Scanned {len(vms)} VMs in {rg}",
                "subscription_id": sub_id,
                "resource_group": rg,
                "scan_time": datetime.now().isoformat(),
                "results": results,
                "saved_to": scan_path
            }
        
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="Azure CLI timed out. Check network connectivity.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/agent/stop")
    async def stop_agent():
        """
        Stop running agent scheduler.
        
        Returns:
            Success message
        """
        global _agent_scheduler, _agent_config
        
        try:
            if not _agent_scheduler or not _agent_scheduler.is_running:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Agent is not running"}
                )
            
            _agent_scheduler.stop()
            _agent_scheduler = None
            _agent_config = None
            
            return {"message": "Agent stopped successfully"}
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/agent/status")
    async def get_agent_status():
        """
        Get agent running status and configuration.
        
        Returns:
            AgentStatusResponse with running status and config
        """
        global _agent_scheduler, _agent_config
        
        running = _agent_scheduler is not None and _agent_scheduler.is_running
        
        config_dict = None
        if _agent_config:
            config_dict = _agent_config.model_dump()
        
        # Get last run time from output.jsonl
        last_run = None
        try:
            output_path = Path("results/output.jsonl")
            if output_path.exists():
                with open(output_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        last_record = json.loads(lines[-1].strip())
                        last_run = last_record.get('timestamp')
        except:
            pass
        
        return AgentStatusResponse(
            running=running,
            config=config_dict,
            last_run=last_run
        )
    
    @app.post("/api/agent/scan-now")
    async def scan_now():
        """
        Trigger one collection cycle immediately.
        
        Returns:
            DiagnosticOutput from the cycle
        """
        global _agent_scheduler
        
        try:
            if not _agent_scheduler or not _agent_scheduler.is_running:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Agent is not running. Start agent first."}
                )
            
            # Trigger immediate execution
            _agent_scheduler._on_tick()
            
            return {"message": "Scan triggered successfully"}
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/benchmark")
    async def run_benchmark():
        """
        Run benchmark and return results.
        
        Returns:
            BenchmarkResults with all metrics
        """
        try:
            benchmark_path = Path("data/benchmark_cases.csv")
            
            if not benchmark_path.exists():
                return JSONResponse(
                    status_code=404,
                    content={"error": "Benchmark file not found. Run setup first."}
                )
            
            # Load and run benchmark
            loader = BenchmarkLoader()
            cases = loader.load_cases(str(benchmark_path))
            
            harness = TestHarness()
            results = harness.run_benchmark(cases)
            
            return results.model_dump()
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/logs")
    async def get_logs(lines: int = 20):
        """
        Get last N agent log lines.
        
        Args:
            lines: Number of log lines to return (default: 20)
        
        Returns:
            List of log lines
        """
        try:
            # For now, return empty list (logs are printed to console)
            # In production, this would read from a log file
            return {"logs": []}
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/feedback/{incident_id}")
    async def submit_feedback(incident_id: str, request: FeedbackRequest):
        """
        Submit engineer feedback for a past diagnosis.
        
        Args:
            incident_id: 12-character hex string from triage response
            request: FeedbackRequest with correct flag and optional corrections
        
        Returns:
            Success message with human_verified status
        """
        try:
            # Import memory store and structured logger
            from src.rag.memory_store import IncidentMemoryStore
            from src.llm.structured_logger import get_structured_logger, StructuredLogger
            
            # Initialize memory store
            memory_store = IncidentMemoryStore()
            structured_logger = get_structured_logger()
            
            # Get original incident data for logging
            try:
                collection = memory_store._get_collection()
                result = collection.get(ids=[incident_id])
                if result['ids']:
                    metadata = result['metadatas'][0]
                    original_diagnosis = metadata.get('diagnosis', '')
                    original_next_check = metadata.get('next_check', '')
                else:
                    original_diagnosis = ''
                    original_next_check = ''
            except Exception:
                original_diagnosis = ''
                original_next_check = ''
            
            # Update feedback in memory store
            success = memory_store.update_feedback(
                incident_id=incident_id,
                correct=request.correct,
                corrected_diagnosis=request.corrected_diagnosis,
                corrected_next_check=request.corrected_next_check,
                outcome=request.outcome
            )
            
            if not success:
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": "Incident not found",
                        "incident_id": incident_id
                    }
                )
            
            # Log feedback submission
            request_id = StructuredLogger.generate_request_id()
            structured_logger.log_feedback(
                request_id=request_id,
                incident_id=incident_id,
                correct=request.correct,
                corrected_diagnosis=request.corrected_diagnosis,
                corrected_next_check=request.corrected_next_check,
                outcome=request.outcome,
                original_diagnosis=original_diagnosis,
                original_next_check=original_next_check
            )
            
            return {
                "status": "ok",
                "message": "Feedback recorded. Future similar incidents will benefit from this correction.",
                "incident_id": incident_id,
                "human_verified": True
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/memory/stats")
    async def get_memory_stats():
        """
        Get memory store statistics.
        
        Returns:
            Memory statistics including total incidents, verified count, 
            novel incidents count, and patterns distribution
        """
        try:
            from src.rag.memory_store import IncidentMemoryStore
            
            memory_store = IncidentMemoryStore()
            stats = memory_store.get_stats()
            
            # Count novel incidents
            try:
                collection = memory_store._get_collection()
                results = collection.get()
                novel_count = sum(
                    1 for m in results['metadatas']
                    if m.get('pattern', '').startswith('llm_detected_') or
                       m.get('is_novel', 'False') == 'True'
                )
                stats['novel_incidents'] = novel_count
            except:
                stats['novel_incidents'] = 0
            
            return stats
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/novel-incidents")
    async def get_novel_incidents(limit: int = 50):
        """
        Get all novel incidents flagged by the LLM.
        
        Args:
            limit: Maximum number of incidents to return (default: 50)
        
        Returns:
            List of novel incidents with telemetry summary, diagnosis, 
            confidence, and timestamp
        """
        try:
            from src.rag.memory_store import IncidentMemoryStore
            
            memory_store = IncidentMemoryStore()
            collection = memory_store._get_collection()
            
            # Get all incidents
            results = collection.get()
            
            if not results['ids']:
                return []
            
            # Filter for novel incidents
            novel_incidents = []
            for i, incident_id in enumerate(results['ids']):
                metadata = results['metadatas'][i]
                document = results['documents'][i]
                
                # Check if novel (either pattern starts with llm_detected_ or is_novel flag)
                pattern = metadata.get('pattern', '')
                is_novel = metadata.get('is_novel', 'False') == 'True'
                
                if pattern.startswith('llm_detected_') or is_novel:
                    novel_incidents.append({
                        "incident_id": incident_id,
                        "telemetry_summary": document,
                        "diagnosis": metadata.get("diagnosis", ""),
                        "confidence": float(metadata.get("confidence", 0.0)),
                        "timestamp": metadata.get("timestamp", ""),
                        "pattern": pattern,
                        "vm_name": metadata.get("vm_name", "unknown")
                    })
            
            # Sort by timestamp DESC
            novel_incidents.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return novel_incidents[:limit]
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/memory/prune")
    async def prune_memory(before: str):
        """
        Prune old incidents from memory store.
        
        Args:
            before: ISO date string (e.g., "2026-01-01"). Incidents older 
                    than this date will be deleted, except human_verified=True
        
        Returns:
            Number of incidents deleted
        """
        try:
            from src.rag.memory_store import IncidentMemoryStore
            from datetime import datetime
            
            memory_store = IncidentMemoryStore()
            collection = memory_store._get_collection()
            
            # Parse date
            try:
                cutoff_date = datetime.fromisoformat(before)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid date format. Use ISO format: YYYY-MM-DD"}
                )
            
            # Get all incidents
            results = collection.get()
            
            if not results['ids']:
                return {
                    "status": "ok",
                    "deleted_count": 0,
                    "message": "No incidents to prune"
                }
            
            # Find incidents to delete
            ids_to_delete = []
            for i, incident_id in enumerate(results['ids']):
                metadata = results['metadatas'][i]
                
                # Skip human verified incidents
                if metadata.get('human_verified', 'False') == 'True':
                    continue
                
                # Check timestamp
                timestamp_str = metadata.get('timestamp', '')
                if timestamp_str:
                    try:
                        incident_date = datetime.fromisoformat(timestamp_str)
                        if incident_date < cutoff_date:
                            ids_to_delete.append(incident_id)
                    except:
                        continue
            
            # Delete incidents
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
            
            return {
                "status": "ok",
                "deleted_count": len(ids_to_delete),
                "message": f"Deleted {len(ids_to_delete)} incidents older than {before}"
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/shadow-mode/stats")
    async def get_shadow_mode_stats():
        """
        Get shadow mode statistics.
        
        Returns:
            Shadow mode statistics including total decisions, agreement rate,
            and recent disagreement cases
        """
        try:
            from src.shadow_mode import ShadowModeExecutor
            
            executor = ShadowModeExecutor()
            stats = executor.get_stats()
            
            return stats
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/logs/decision/{request_id}")
    async def get_decision_logs(request_id: str):
        """
        Get all logs for a specific request_id.
        
        Args:
            request_id: Request identifier from triage response
        
        Returns:
            All logs related to this request: LLM decision, RAG retrievals,
            safety overrides, and feedback
        """
        try:
            import json
            from pathlib import Path
            
            logs_dir = Path("logs")
            result = {
                "request_id": request_id,
                "llm_decision": None,
                "rag_retrievals": [],
                "safety_overrides": [],
                "feedback": []
            }
            
            # Read LLM decisions log
            llm_log = logs_dir / "llm_decisions.jsonl"
            if llm_log.exists():
                with open(llm_log, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if entry.get('request_id') == request_id:
                                result['llm_decision'] = entry
                                break
                        except json.JSONDecodeError:
                            continue
            
            # Read RAG retrievals log
            rag_log = logs_dir / "rag_retrievals.jsonl"
            if rag_log.exists():
                with open(rag_log, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if entry.get('request_id') == request_id:
                                result['rag_retrievals'].append(entry)
                        except json.JSONDecodeError:
                            continue
            
            # Read safety overrides log
            safety_log = logs_dir / "safety_overrides.jsonl"
            if safety_log.exists():
                with open(safety_log, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if entry.get('request_id') == request_id:
                                result['safety_overrides'].append(entry)
                        except json.JSONDecodeError:
                            continue
            
            # Read feedback log
            feedback_log = logs_dir / "feedback.jsonl"
            if feedback_log.exists():
                with open(feedback_log, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if entry.get('request_id') == request_id:
                                result['feedback'].append(entry)
                        except json.JSONDecodeError:
                            continue
            
            # Check if any logs were found
            if (result['llm_decision'] is None and 
                not result['rag_retrievals'] and 
                not result['safety_overrides'] and 
                not result['feedback']):
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": "No logs found for this request_id",
                        "request_id": request_id
                    }
                )
            
            return result
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/health")
    async def health_check():
        """
        System health check including LLM provider status.
        
        Returns:
            Health status with LLM provider availability, memory store status,
            and SOP knowledge base status
        """
        try:
            health_status = {
                "status": "healthy",
                "providers": {},
                "active_provider": "unknown",
                "memory_store": {},
                "sop_kb": {}
            }
            
            # Check LLM providers
            try:
                from src.llm.llm_engine import LLMDecisionEngine
                
                engine = LLMDecisionEngine()
                provider_status = engine.get_provider_status()
                
                health_status["providers"] = provider_status
                health_status["active_provider"] = engine._provider_chain.get_active_provider_name() or "unknown"
            except Exception as e:
                health_status["providers"] = {
                    "groq": "unavailable",
                    "gemini": "unavailable",
                    "ollama": "unavailable"
                }
                health_status["active_provider"] = "rule_engine"
            
            # Check memory store
            try:
                from src.rag.memory_store import IncidentMemoryStore
                
                memory_store = IncidentMemoryStore()
                stats = memory_store.get_stats()
                
                health_status["memory_store"] = {
                    "total_incidents": stats.get("total", 0),
                    "collection_status": "ok"
                }
            except Exception as e:
                health_status["memory_store"] = {
                    "total_incidents": 0,
                    "collection_status": "error",
                    "error": str(e)
                }
            
            # Check SOP knowledge base
            try:
                from src.rag.sop_knowledge import SOPKnowledgeBase
                
                sop_kb = SOPKnowledgeBase()
                collection = sop_kb._get_collection()
                total_sops = collection.count()
                
                health_status["sop_kb"] = {
                    "total_sops": total_sops,
                    "collection_status": "ok" if total_sops >= 12 else "incomplete"
                }
            except Exception as e:
                health_status["sop_kb"] = {
                    "total_sops": 0,
                    "collection_status": "error",
                    "error": str(e)
                }
            
            # Determine overall status
            if (health_status["memory_store"].get("collection_status") == "error" or
                health_status["sop_kb"].get("collection_status") == "error"):
                health_status["status"] = "degraded"
            
            return health_status
        
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "unhealthy",
                    "error": str(e)
                }
            )
    
    @app.get("/api/memory/similar")
    async def get_similar_incidents(telemetry_id: str, top_k: int = 5):
        """
        Find similar past incidents for a given incident ID.
        
        Args:
            telemetry_id: Incident ID to find similar incidents for
            top_k: Number of similar incidents to return (default: 5)
        
        Returns:
            List of similar incidents with similarity scores
        """
        try:
            from src.rag.memory_store import IncidentMemoryStore
            
            memory_store = IncidentMemoryStore()
            collection = memory_store._get_collection()
            
            # Get the incident's telemetry text
            result = collection.get(ids=[telemetry_id])
            if not result['ids']:
                return JSONResponse(
                    status_code=404,
                    content={"error": "Incident not found", "telemetry_id": telemetry_id}
                )
            
            document = result['documents'][0]
            
            # Find similar using the document text as query
            model = memory_store._get_embedding_model()
            query_embedding = model.encode(document).tolist()
            
            count = collection.count()
            if count <= 1:
                return []
            
            similar_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k + 1, count)
            )
            
            similar = []
            if similar_results['ids'] and similar_results['ids'][0]:
                for i, sid in enumerate(similar_results['ids'][0]):
                    if sid == telemetry_id:
                        continue
                    distance = similar_results['distances'][0][i]
                    meta = similar_results['metadatas'][0][i]
                    similar.append({
                        "incident_id": sid,
                        "similarity_score": round(1.0 - distance, 3),
                        "diagnosis": meta.get("diagnosis", ""),
                        "decision": meta.get("decision", ""),
                        "timestamp": meta.get("timestamp", ""),
                        "human_verified": meta.get("human_verified", "False") == "True"
                    })
            
            return similar[:top_k]
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/memory/clear")
    async def clear_memory():
        """
        Clear all incidents from memory store.
        
        Returns:
            Success message with count of deleted incidents
        """
        try:
            from src.rag.memory_store import IncidentMemoryStore
            
            memory_store = IncidentMemoryStore()
            collection = memory_store._get_collection()
            count_before = collection.count()
            
            # Delete and recreate collection
            client = memory_store._get_client()
            client.delete_collection("incidents")
            memory_store._collection = None
            
            return {
                "status": "ok",
                "deleted_count": count_before,
                "message": f"Cleared {count_before} incidents from memory store"
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return app


# Create app instance
app = create_app()
