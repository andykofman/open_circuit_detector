#!/usr/bin/env python3
"""
Open Circuit Detector - Main Entry Point

Developer: Ahmed Ali

Description:
A tool for detecting open circuits and DC-floating nodes in SPICE netlists.
Parses hierarchical netlists, flattens subcircuit instantiations, and identifies
connectivity issues that could cause circuit failures.

Usage:
    python main.py <netlist_file> [options]

Example:
    python main.py data/netlist.sp --output-json report.json --output-text report.txt
"""

import argparse
import sys
from pathlib import Path

from parser.spice_parser import SpiceParser
from graph.circuit_graph import CircuitGraph
from analyzer.open_detector import OpenCircuitDetector
from reporter.report_generator import ReportGenerator


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="open_circuit_detector",
        description="Detect open circuits and DC-floating nodes in SPICE netlists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s netlist.sp
        Analyze netlist and print summary to stdout

    %(prog)s netlist.sp --output-json report.json
        Save detailed JSON report

    %(prog)s netlist.sp --output-text report.txt
        Save human-readable text report

    %(prog)s netlist.sp --verbose
        Print detailed analysis progress
        """
    )
    
    parser.add_argument(
        "netlist",
        type=str,
        help="Path to the SPICE netlist file to analyze"
    )
    
    parser.add_argument(
        "--output-json", "-j",
        type=str,
        metavar="FILE",
        help="Save JSON report to specified file"
    )
    
    parser.add_argument(
        "--output-text", "-t",
        type=str,
        metavar="FILE",
        help="Save text report to specified file"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output during analysis"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress output except for errors"
    )
    
    parser.add_argument(
        "--subcircuit-only",
        action="store_true",
        help="Analyze only the first subcircuit (skip top-level flattening)"
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the open circuit detector.
    
    Returns:
        Exit code: 0 for success, 1 for errors, 2 for issues found
    """
    args = parse_args()
    
    # Validate input file
    netlist_path = Path(args.netlist)
    if not netlist_path.exists():
        print(f"Error: Netlist file not found: {args.netlist}", file=sys.stderr)
        return 1
    
    if not netlist_path.is_file():
        print(f"Error: Not a file: {args.netlist}", file=sys.stderr)
        return 1
    
    try:
        # Step 1: Parse the netlist
        if args.verbose:
            print(f"Parsing netlist: {args.netlist}")
        
        parser = SpiceParser()
        
        if args.subcircuit_only:
            # Parse only the first subcircuit
            subcircuits = parser.parse_file(str(netlist_path))
            if not subcircuits:
                print("Error: No subcircuits found in netlist", file=sys.stderr)
                return 1
            
            if args.verbose:
                print(f"Found {len(subcircuits)} subcircuit(s)")
                for name, subckt in subcircuits.items():
                    print(f"  - {name}: {len(subckt.ports)} ports, {len(subckt.elements)} elements")
            
            # Build graph from first subcircuit
            graph = CircuitGraph()
            subcircuit = next(iter(subcircuits.values()))
            graph.build_from_subcircuit(subcircuit)
            
            # Run standard detection
            detector = OpenCircuitDetector(graph)
            issues = detector.detect_all()
            
        else:
            # Parse complete netlist with top-level elements
            netlist = parser.parse_file_complete(str(netlist_path))
            
            if args.verbose:
                print(f"Found {len(netlist.subcircuits)} subcircuit(s)")
                print(f"Found {len(netlist.instances)} instance(s)")
                print(f"Found {len(netlist.top_level_elements)} top-level element(s)")
            
            # Build flattened graph
            graph = CircuitGraph()
            graph.build_from_netlist(netlist)
            
            if args.verbose:
                print(f"Flattened graph: {len(graph.all_nodes)} nodes, {len(graph.elements)} elements")
                print(f"Top-level nodes: {len(graph.top_level_nodes)}")
            
            # Run flattened detection
            detector = OpenCircuitDetector(graph)
            issues = detector.detect_all_flattened()
        
        # Step 2: Generate reports
        report = ReportGenerator(issues, str(netlist_path))
        
        # Save JSON report if requested
        if args.output_json:
            report.save_json(args.output_json)
            if args.verbose:
                print(f"JSON report saved to: {args.output_json}")
        
        # Save text report if requested
        if args.output_text:
            report.save_text(args.output_text)
            if args.verbose:
                print(f"Text report saved to: {args.output_text}")
        
        # Print summary unless quiet mode
        if not args.quiet:
            report.print_summary()
        
        # Return appropriate exit code
        if issues:
            # Check severity - exit 2 for critical/error issues
            has_critical = any(i.severity in ["critical", "error"] for i in issues)
            return 2 if has_critical else 0
        return 0
        
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
