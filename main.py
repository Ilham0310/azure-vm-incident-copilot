#!/usr/bin/env python3
"""
Azure VM Incident Copilot - Main CLI Entry Point

This module provides the command-line interface for the Azure VM Incident Copilot.
It supports four modes:
1. Setup mode (--setup): Generate configuration files
2. Single file mode (--input): Process one telemetry file
3. Benchmark mode (--benchmark): Process batch benchmark cases
4. Output mode (--output): Write results to file instead of stdout

Exit codes:
- 0: Success
- 1: Invalid input JSON
- 2: Schema validation failed
- 3: File not found
- 4: File I/O error
- 5: Benchmark processing error
- 99: Unexpected error
"""

# Load environment variables from .env file if present
from dotenv import load_dotenv
load_dotenv()  # loads .env file silently if present

import sys
import json
import os
import click
from pathlib import Path

# Import pipeline components
from src.validator import SchemaValidator, JSONParseError, SchemaValidationError
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine
from src.explanation_formatter import ExplanationFormatter
from src.benchmark_loader import BenchmarkLoader
from src.test_harness import TestHarness


@click.command()
@click.option('--setup', is_flag=True,
              help='Run setup to generate schemas, policy, and benchmark data')
@click.option('--input', 'input_file', type=click.Path(),
              help='Path to input JSON file containing telemetry')
@click.option('--output', 'output_file', type=click.Path(),
              help='Path to output JSON file (default: stdout)')
@click.option('--benchmark', 'benchmark_file', type=click.Path(),
              help='Path to benchmark cases file for batch processing')
@click.option('--agent', is_flag=True,
              help='Run telemetry collector agent with Azure integration')
@click.option('--vm', 'vm_name', type=str,
              help='Azure VM name (required for --agent mode)')
@click.option('--rg', 'resource_group', type=str,
              help='Azure resource group (required for --agent mode)')
@click.option('--subscription', 'subscription_id', type=str,
              help='Azure subscription ID (optional, defaults to env AZURE_SUBSCRIPTION_ID)')
@click.option('--workspace', 'workspace_id', type=str,
              help='Log Analytics workspace ID (optional)')
@click.option('--interval', type=int, default=300,
              help='Collection interval in seconds (default: 300)')
@click.option('--once', is_flag=True,
              help='Run agent once and exit (single-run mode)')
@click.option('--config', 'config_file', type=click.Path(),
              help='Path to agent configuration JSON file')
@click.option('--ui', is_flag=True,
              help='Start web dashboard UI at http://localhost:8000')
@click.option('--self-test-workspaces', 'self_test_ws', is_flag=True,
              help='Run workspace wiring self-test (requires az login)')
def main(setup, input_file, output_file, benchmark_file, agent, vm_name, resource_group, 
         subscription_id, workspace_id, interval, once, config_file, ui, self_test_ws):
    """
    Azure VM Incident Copilot CLI.
    
    Processes Azure VM telemetry and returns diagnostic output.
    Supports local file processing and Azure agent mode.
    
    Examples:
        Setup mode:     python main.py --setup
        Triage mode:    python main.py --input incident.json
        Output to file: python main.py --input incident.json --output result.json
        Benchmark mode: python main.py --benchmark data/benchmark_cases.csv
        Agent mode:     python main.py --agent --vm my-vm --rg my-rg
        Agent once:     python main.py --agent --vm my-vm --rg my-rg --once
        Agent config:   python main.py --agent --config agent_config.json
        Web UI:         python main.py --ui
        Self-test:      python main.py --self-test-workspaces
    """
    try:
        # Mode 1: Setup
        if setup:
            exit_code = run_setup()
            sys.exit(exit_code)
        
        # Mode 2: Web UI
        if ui:
            exit_code = run_ui()
            sys.exit(exit_code)
        
        # Mode 2b: Workspace wiring self-test
        if self_test_ws:
            from scripts.test_workspace_wiring_cli import main as ws_test_main
            sys.exit(ws_test_main())
        
        # Mode 3: Agent mode
        if agent:
            exit_code = run_agent(vm_name, resource_group, subscription_id, workspace_id, 
                                 interval, once, config_file)
            sys.exit(exit_code)
        
        # Mode 4: Single file processing
        if input_file:
            exit_code = process_single_file(input_file, output_file)
            sys.exit(exit_code)
        
        # Mode 5: Benchmark processing
        if benchmark_file:
            exit_code = process_benchmark(benchmark_file)
            sys.exit(exit_code)
        
        # No mode specified
        click.echo("Error: No mode specified. Use --setup, --input, --benchmark, --agent, or --ui")
        click.echo("Run 'python main.py --help' for usage information")
        sys.exit(99)
    
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(99)


def run_setup():
    """
    Run setup to generate all configuration files.
    
    Calls setup/run_setup.py functions to generate:
    - schemas/azure_vm_triage_schema.json
    - schemas/output_schema.json
    - policy/decision_policy.json
    - data/benchmark_cases.csv
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    click.echo("=" * 60)
    click.echo("Azure VM Incident Copilot - Setup")
    click.echo("=" * 60)
    click.echo()
    
    try:
        # Import setup generators using absolute path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        setup_dir = os.path.join(script_dir, 'setup')
        sys.path.insert(0, setup_dir)
        from generate_schema import generate_triage_schema, write_schema_file
        from generate_output_schema import generate_output_schema, write_output_schema_file
        from generate_policy import generate_decision_policy, write_policy_file
        from generate_benchmark import generate_benchmark_cases, write_benchmark_file
        
        # Step 1: Generate triage schema
        click.echo("Step 1/4: Generating triage schema...")
        schema = generate_triage_schema()
        write_schema_file(schema)
        click.echo()
        
        # Step 2: Generate output schema
        click.echo("Step 2/4: Generating output schema...")
        output_schema = generate_output_schema()
        write_output_schema_file(output_schema)
        click.echo()
        
        # Step 3: Generate decision policy
        click.echo("Step 3/4: Generating decision policy...")
        policy = generate_decision_policy()
        write_policy_file(policy)
        click.echo()
        
        # Step 4: Generate benchmark cases
        click.echo("Step 4/4: Generating benchmark cases...")
        cases = generate_benchmark_cases()
        write_benchmark_file(cases)
        click.echo()
        
        click.echo("=" * 60)
        click.echo("Setup complete!")
        click.echo("=" * 60)
        click.echo()
        click.echo("Generated files:")
        click.echo("  - schemas/azure_vm_triage_schema.json")
        click.echo("  - schemas/output_schema.json")
        click.echo("  - policy/decision_policy.json")
        click.echo("  - data/benchmark_cases.csv")
        click.echo()
        click.echo("You can now run the system:")
        click.echo("  python main.py --input incident.json")
        click.echo()
        
        return 0
    
    except ImportError as e:
        click.echo(f"Error: Failed to import setup generators: {e}", err=True)
        click.echo("Make sure all generator scripts exist in the setup/ directory.", err=True)
        return 99
    except Exception as e:
        click.echo(f"Error during setup: {e}", err=True)
        return 99


def process_single_file(input_file, output_file):
    """
    Process a single telemetry file through the pipeline.
    
    Pipeline flow:
    1. Read JSON file
    2. SchemaValidator.validate()
    3. ConfidenceScorer.score_telemetry()
    4. DecisionEngine.decide()
    5. ExplanationFormatter.format_output()
    6. Output JSON to stdout or file
    
    Args:
        input_file: Path to input JSON file
        output_file: Path to output JSON file (None for stdout)
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Step 1: Read input file
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                json_input = f.read()
        except FileNotFoundError:
            click.echo(f"Error: File not found: {input_file}", err=True)
            return 3
        except IOError as e:
            click.echo(f"Error: Failed to read file: {e}", err=True)
            return 4
        
        # Step 2: Validate against schema
        try:
            validator = SchemaValidator()
            result = validator.validate(json_input)
            
            if not result.valid:
                click.echo("Schema validation failed:", err=True)
                for error in result.errors:
                    click.echo(f"  Field: {error.field}", err=True)
                    click.echo(f"  Error: {error.message}", err=True)
                    if error.value:
                        click.echo(f"  Value: {error.value}", err=True)
                return 2
            
            telemetry = result.telemetry
        
        except JSONParseError as e:
            click.echo(f"JSON parse error: {e.format_message()}", err=True)
            return 1
        except FileNotFoundError:
            click.echo("Error: Schema file not found. Run 'python main.py --setup' first.", err=True)
            return 3
        except Exception as e:
            click.echo(f"Validation error: {e}", err=True)
            return 2
        
        # Step 3: Calculate confidence score
        try:
            scorer = ConfidenceScorer()
            completeness, confidence_score, conflicts = scorer.score_telemetry(
                telemetry,
                pattern_match="exact"  # Will be determined by decision engine
            )
        except Exception as e:
            click.echo(f"Confidence scoring error: {e}", err=True)
            return 99
        
        # Step 4: Apply decision engine
        try:
            engine = DecisionEngine()
            decision = engine.decide(telemetry, confidence_score, completeness)
        except Exception as e:
            click.echo(f"Decision engine error: {e}", err=True)
            return 99
        
        # Step 5: Format output
        try:
            formatter = ExplanationFormatter()
            output = formatter.format_output(decision, telemetry, confidence_score)
        except Exception as e:
            click.echo(f"Output formatting error: {e}", err=True)
            return 99
        
        # Step 6: Write output
        try:
            output_json = json.dumps(output.model_dump(), indent=2)
            
            if output_file:
                # Write to file
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(output_json)
                click.echo(f"Output written to: {output_file}")
            else:
                # Write to stdout
                click.echo(output_json)
            
            return 0
        
        except IOError as e:
            click.echo(f"Error: Failed to write output: {e}", err=True)
            return 4
    
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        return 99


def process_benchmark(benchmark_file):
    """
    Process benchmark cases in batch mode.
    
    Args:
        benchmark_file: Path to benchmark cases file (CSV or JSON)
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Load benchmark cases
        try:
            loader = BenchmarkLoader()
            cases = loader.load_cases(benchmark_file)
            click.echo(f"Loaded {len(cases)} benchmark cases from {benchmark_file}")
            click.echo()
        except FileNotFoundError:
            click.echo(f"Error: Benchmark file not found: {benchmark_file}", err=True)
            return 3
        except ValueError as e:
            click.echo(f"Error: Invalid benchmark file format: {e}", err=True)
            return 5
        except Exception as e:
            click.echo(f"Error loading benchmark cases: {e}", err=True)
            return 5
        
        # Run test harness
        try:
            harness = TestHarness()
            results = harness.run_benchmark(cases)
            harness.print_results(results)
            
            # Return non-zero if any cases failed
            if results.failed > 0:
                return 5
            
            return 0
        
        except Exception as e:
            click.echo(f"Error processing benchmark: {e}", err=True)
            return 5
    
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        return 99


def run_ui():
    """
    Start web dashboard UI at http://localhost:8000.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Import FastAPI and uvicorn
        import uvicorn
        from ui.app import app
        
        click.echo("=" * 60)
        click.echo("Azure VM Incident Copilot - Web Dashboard")
        click.echo("=" * 60)
        click.echo()
        click.echo("Starting web server at http://localhost:8000")
        click.echo("Press Ctrl+C to stop")
        click.echo()
        
        # Start uvicorn server
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        
        return 0
    
    except ImportError as e:
        click.echo(f"Error: Failed to import UI components: {e}", err=True)
        click.echo("Make sure UI dependencies are installed: pip install -r requirements-ui.txt", err=True)
        return 99
    except Exception as e:
        click.echo(f"Error starting web UI: {e}", err=True)
        return 99


def run_agent(vm_name, resource_group, subscription_id, workspace_id, interval, once, config_file):
    """
    Run telemetry collector agent with Azure integration.
    
    Args:
        vm_name: Azure VM name
        resource_group: Azure resource group
        subscription_id: Azure subscription ID (optional, defaults to env)
        workspace_id: Log Analytics workspace ID (optional)
        interval: Collection interval in seconds
        once: Run once and exit (single-run mode)
        config_file: Path to agent configuration JSON file (optional)
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Import agent components
        from agent.config import AgentConfig
        from agent.collector import TelemetryCollectorAgent
        from agent.scheduler import IncidentCopilotScheduler
        
        # Load configuration
        if config_file:
            # Load from config file
            try:
                config = AgentConfig.from_file(config_file)
                click.echo(f"Loaded configuration from: {config_file}")
            except FileNotFoundError:
                click.echo(f"Error: Configuration file not found: {config_file}", err=True)
                return 3
            except ValueError as e:
                click.echo(f"Error: Invalid configuration file: {e}", err=True)
                return 99
        else:
            # Load from CLI args or environment variables
            if not vm_name or not resource_group:
                click.echo("Error: --vm and --rg are required for agent mode (or use --config)", err=True)
                return 99
            
            # Get subscription ID from CLI or environment
            if not subscription_id:
                subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
                if not subscription_id:
                    click.echo("Error: Azure subscription ID required (use --subscription or set AZURE_SUBSCRIPTION_ID)", err=True)
                    return 99
            
            # Build config from CLI args
            config = AgentConfig(
                subscription_id=subscription_id,
                resource_group=resource_group,
                vm_name=vm_name,
                log_analytics_workspace_id=workspace_id or os.getenv('LOG_ANALYTICS_WORKSPACE_ID'),
                monitor_workspace_id=os.getenv('MONITOR_WORKSPACE_ID'),
                monitor_workspace_name=os.getenv('MONITOR_WORKSPACE_NAME', 'monitor1'),
                log_analytics_workspace_name=os.getenv('LOG_ANALYTICS_WORKSPACE_NAME', 'loganalytics'),
                interval_seconds=interval
            )
        
        # Initialize collector and scheduler
        collector = TelemetryCollectorAgent(config)
        scheduler = IncidentCopilotScheduler(config, collector)
        
        # Run in single-run or continuous mode
        if once:
            # Single-run mode
            output = scheduler.run_once()
            
            # Output diagnostic result to stdout
            output_json = json.dumps(output.model_dump(), indent=2)
            click.echo()
            click.echo(output_json)
            
            return 0
        else:
            # Continuous mode
            scheduler.run()
            return 0
    
    except ImportError as e:
        click.echo(f"Error: Failed to import agent components: {e}", err=True)
        click.echo("Make sure agent dependencies are installed: pip install -r requirements-agent.txt", err=True)
        return 99
    except Exception as e:
        click.echo(f"Error running agent: {e}", err=True)
        return 99


if __name__ == "__main__":
    sys.exit(main())
