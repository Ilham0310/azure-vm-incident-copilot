"""
Test harness component for Azure VM Incident Copilot.

This module provides the TestHarness class that:
- Batch processes benchmark cases
- Compares actual vs expected decisions
- Records pass/fail status and execution time
- Calculates summary statistics by incident pattern
- Generates BenchmarkResults with all metrics
"""

import time
from typing import List, Dict
from collections import defaultdict

from src.models import (
    BenchmarkCase,
    CaseResult,
    PatternSummary,
    BenchmarkResults,
    DecisionState
)
from src.validator import SchemaValidator
from src.confidence_scorer import ConfidenceScorer
from src.decision_engine import DecisionEngine
from src.explanation_formatter import ExplanationFormatter


class TestHarness:
    """
    Batch processes benchmark cases and generates test results.
    
    Responsibilities:
    - Process all benchmark cases through the pipeline
    - Compare actual vs expected decision for each case
    - Record pass/fail status and execution time
    - Calculate summary statistics by incident pattern
    - Generate BenchmarkResults with all metrics
    """
    
    def __init__(self):
        """Initialize test harness with pipeline components"""
        self.scorer = ConfidenceScorer()
        self.engine = DecisionEngine()
        self.formatter = ExplanationFormatter()
    
    def run_benchmark(self, cases: List[BenchmarkCase]) -> BenchmarkResults:
        """
        Processes all benchmark cases and returns results.
        
        For each case:
        1. Extract telemetry_input
        2. Process through pipeline
        3. Compare actual vs expected decision
        4. Record pass/fail status
        
        Args:
            cases: List of 25-50 benchmark cases
            
        Returns:
            BenchmarkResults with:
            - total_cases: Total number processed
            - passed: Number of cases where actual == expected
            - failed: Number of cases where actual != expected
            - case_results: Per-case details with actual vs expected
            - summary_by_pattern: Statistics grouped by incident pattern
        """
        start_time = time.time()
        
        case_results = []
        pattern_stats = defaultdict(lambda: {'total': 0, 'passed': 0, 'failed': 0})
        
        # Process each case
        for case in cases:
            case_start = time.time()
            
            try:
                # Run through pipeline
                completeness, confidence_score, conflicts = self.scorer.score_telemetry(
                    case.telemetry_input,
                    pattern_match="exact"
                )
                
                decision = self.engine.decide(
                    case.telemetry_input,
                    confidence_score,
                    completeness
                )
                
                output = self.formatter.format_output(
                    decision,
                    case.telemetry_input,
                    confidence_score
                )
                
                # Compare actual vs expected
                actual_decision = output.decision
                expected_decision = case.expected_decision
                passed = (actual_decision == expected_decision)
                
                case_end = time.time()
                execution_time_ms = (case_end - case_start) * 1000
                
                # Create case result
                result = CaseResult(
                    case_id=case.case_id,
                    case_name=case.case_name,
                    incident_pattern=case.incident_pattern,
                    expected_decision=expected_decision,
                    actual_decision=actual_decision,
                    passed=passed,
                    confidence_score=confidence_score,
                    execution_time_ms=execution_time_ms,
                    notes=case.notes
                )
                
                case_results.append(result)
                
                # Update pattern statistics
                pattern_stats[case.incident_pattern]['total'] += 1
                if passed:
                    pattern_stats[case.incident_pattern]['passed'] += 1
                else:
                    pattern_stats[case.incident_pattern]['failed'] += 1
            
            except Exception as e:
                # Handle processing errors
                case_end = time.time()
                execution_time_ms = (case_end - case_start) * 1000
                
                result = CaseResult(
                    case_id=case.case_id,
                    case_name=case.case_name,
                    incident_pattern=case.incident_pattern,
                    expected_decision=case.expected_decision,
                    actual_decision=DecisionState.ABSTAIN_REQUEST_NEXT_CHECK,  # Default for errors
                    passed=False,
                    confidence_score=0.0,
                    execution_time_ms=execution_time_ms,
                    notes=f"Error: {str(e)}"
                )
                
                case_results.append(result)
                pattern_stats[case.incident_pattern]['total'] += 1
                pattern_stats[case.incident_pattern]['failed'] += 1
        
        end_time = time.time()
        total_execution_time_ms = (end_time - start_time) * 1000
        
        # Calculate overall statistics
        total_cases = len(case_results)
        passed = sum(1 for r in case_results if r.passed)
        failed = total_cases - passed
        pass_rate = (passed / total_cases * 100) if total_cases > 0 else 0.0
        
        # Generate pattern summaries
        summary_by_pattern = []
        for pattern, stats in pattern_stats.items():
            pattern_pass_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0.0
            summary = PatternSummary(
                pattern=pattern,
                total_cases=stats['total'],
                passed=stats['passed'],
                failed=stats['failed'],
                pass_rate=pattern_pass_rate
            )
            summary_by_pattern.append(summary)
        
        # Sort by pattern name
        summary_by_pattern.sort(key=lambda x: x.pattern)
        
        # Create benchmark results
        results = BenchmarkResults(
            total_cases=total_cases,
            passed=passed,
            failed=failed,
            pass_rate=pass_rate,
            case_results=case_results,
            summary_by_pattern=summary_by_pattern,
            total_execution_time_ms=total_execution_time_ms
        )
        
        return results
    
    def print_results(self, results: BenchmarkResults):
        """
        Print benchmark results in human-readable format.
        
        Args:
            results: BenchmarkResults object
        """
        print("=" * 80)
        print("BENCHMARK RESULTS")
        print("=" * 80)
        print(f"\nOverall Statistics:")
        print(f"  Total Cases: {results.total_cases}")
        print(f"  Passed: {results.passed}")
        print(f"  Failed: {results.failed}")
        print(f"  Pass Rate: {results.pass_rate:.1f}%")
        print(f"  Total Execution Time: {results.total_execution_time_ms:.2f} ms")
        print(f"  Average Time per Case: {results.total_execution_time_ms / results.total_cases:.2f} ms")
        
        print(f"\nResults by Pattern:")
        print(f"  {'Pattern':<40} {'Total':>6} {'Passed':>6} {'Failed':>6} {'Pass Rate':>10}")
        print(f"  {'-'*40} {'-'*6} {'-'*6} {'-'*6} {'-'*10}")
        for summary in results.summary_by_pattern:
            print(f"  {summary.pattern:<40} {summary.total_cases:>6} {summary.passed:>6} "
                  f"{summary.failed:>6} {summary.pass_rate:>9.1f}%")
        
        # Show failed cases
        failed_cases = [r for r in results.case_results if not r.passed]
        if failed_cases:
            print(f"\nFailed Cases ({len(failed_cases)}):")
            for result in failed_cases:
                print(f"  [{result.case_id}] {result.case_name}")
                print(f"      Expected: {result.expected_decision.value}")
                print(f"      Actual: {result.actual_decision.value}")
                print(f"      Pattern: {result.incident_pattern}")
                if result.notes:
                    print(f"      Notes: {result.notes}")
        
        print("=" * 80)


if __name__ == "__main__":
    # Example usage
    from src.benchmark_loader import BenchmarkLoader
    
    loader = BenchmarkLoader()
    harness = TestHarness()
    
    try:
        # Load benchmark cases
        cases = loader.load_cases("data/benchmark_cases.csv")
        print(f"Loaded {len(cases)} benchmark cases\n")
        
        # Run benchmark
        results = harness.run_benchmark(cases)
        
        # Print results
        harness.print_results(results)
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
