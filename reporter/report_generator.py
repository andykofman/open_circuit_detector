"""
Report Generator Module

Generates reports of detected open circuit issues in multiple formats:
- JSON for machine processing
- Human-readable text for review
"""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from analyzer.open_detector import OpenCircuit, OpenType


class ReportGenerator:
    """
    Generates reports of detected open circuit issues.
    
    Supports multiple output formats:
    - JSON: Machine-readable format for integration
    - Text: Human-readable format for manual review
    """
    
    def __init__(self, issues: List[OpenCircuit], netlist_path: Optional[str] = None):
        """
        Initialize the report generator.
        
        Args:
            issues: List of detected open circuit issues
            netlist_path: Path to the analyzed netlist file (optional)
        """
        self.issues = issues
        self.netlist_path = netlist_path
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the report to a dictionary representation.
        
        Returns:
            Dictionary containing the full report data
        """
        # Categorize issues by type and severity
        issues_by_type: Dict[str, List[Dict]] = {}
        issues_by_severity: Dict[str, List[Dict]] = {}
        
        for issue in self.issues:
            issue_dict = {
                "node": issue.node,
                "type": issue.open_type.name,
                "severity": issue.severity,
                "description": issue.description,
                "affected_elements": issue.affected_elements,
                "affected_elements_count": len(issue.affected_elements)
            }
            
            # Group by type
            type_name = issue.open_type.name
            if type_name not in issues_by_type:
                issues_by_type[type_name] = []
            issues_by_type[type_name].append(issue_dict)
            
            # Group by severity
            if issue.severity not in issues_by_severity:
                issues_by_severity[issue.severity] = []
            issues_by_severity[issue.severity].append(issue_dict)
        
        return {
            "report_metadata": {
                "tool_name": "Open Circuit Detector",
                "version": "1.0.0",
                "timestamp": self.timestamp,
                "netlist_file": self.netlist_path
            },
            "summary": {
                "total_issues": len(self.issues),
                "issues_by_severity": {
                    sev: len(issues) for sev, issues in issues_by_severity.items()
                },
                "issues_by_type": {
                    t: len(issues) for t, issues in issues_by_type.items()
                }
            },
            "issues": [
                {
                    "node": issue.node,
                    "type": issue.open_type.name,
                    "severity": issue.severity,
                    "description": issue.description,
                    "affected_elements": issue.affected_elements
                }
                for issue in self.issues
            ],
            "issues_by_type": issues_by_type,
            "issues_by_severity": issues_by_severity
        }
    
    def to_json(self, indent: int = 2) -> str:
        """
        Generate a JSON report.
        
        Args:
            indent: Number of spaces for JSON indentation
            
        Returns:
            JSON string representation of the report
        """
        return json.dumps(self.to_dict(), indent=indent)
    
    def save_json(self, output_path: str) -> None:
        """
        Save the report as a JSON file.
        
        Args:
            output_path: Path to save the JSON report
        """
        with open(output_path, 'w') as f:
            f.write(self.to_json())
    
    def to_text(self) -> str:
        """
        Generate a human-readable text report.
        
        Returns:
            Formatted text report string
        """
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("OPEN CIRCUIT DETECTION REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Metadata
        lines.append(f"Generated: {self.timestamp}")
        if self.netlist_path:
            lines.append(f"Netlist:   {self.netlist_path}")
        lines.append("")
        
        # Summary
        lines.append("-" * 80)
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total issues found: {len(self.issues)}")
        
        # Count by severity
        severity_counts = {}
        type_counts = {}
        for issue in self.issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
            type_counts[issue.open_type.name] = type_counts.get(issue.open_type.name, 0) + 1
        
        if severity_counts:
            lines.append("")
            lines.append("By Severity:")
            for severity in ["critical", "error", "warning", "info"]:
                if severity in severity_counts:
                    lines.append(f"  {severity.upper():12} : {severity_counts[severity]}")
        
        if type_counts:
            lines.append("")
            lines.append("By Type:")
            for type_name, count in sorted(type_counts.items()):
                lines.append(f"  {type_name:25} : {count}")
        
        lines.append("")
        
        # Detailed issues
        if self.issues:
            lines.append("-" * 80)
            lines.append("DETAILED ISSUES")
            lines.append("-" * 80)
            
            # Sort by severity (critical first)
            severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
            sorted_issues = sorted(
                self.issues, 
                key=lambda x: (severity_order.get(x.severity, 99), x.open_type.name)
            )
            
            for i, issue in enumerate(sorted_issues, 1):
                lines.append("")
                lines.append(f"Issue #{i}")
                lines.append(f"  Type:     {issue.open_type.name}")
                lines.append(f"  Severity: {issue.severity.upper()}")
                lines.append(f"  Node:     {issue.node}")
                lines.append(f"  Description: {issue.description}")
                
                if issue.affected_elements:
                    lines.append(f"  Affected Elements ({len(issue.affected_elements)}):")
                    # Show up to 10 elements, then summarize
                    elements_to_show = issue.affected_elements[:10]
                    for elem in elements_to_show:
                        lines.append(f"    - {elem}")
                    if len(issue.affected_elements) > 10:
                        remaining = len(issue.affected_elements) - 10
                        lines.append(f"    ... and {remaining} more elements")
        else:
            lines.append("-" * 80)
            lines.append("No issues detected. Circuit appears to be clean.")
            lines.append("-" * 80)
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def save_text(self, output_path: str) -> None:
        """
        Save the report as a text file.
        
        Args:
            output_path: Path to save the text report
        """
        with open(output_path, 'w') as f:
            f.write(self.to_text())
    
    def print_summary(self) -> None:
        """
        Print a brief summary to stdout.
        """
        print(f"\n{'='*60}")
        print("OPEN CIRCUIT DETECTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total issues: {len(self.issues)}")
        
        if self.issues:
            severity_counts = {}
            for issue in self.issues:
                severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
            
            for severity in ["critical", "error", "warning", "info"]:
                if severity in severity_counts:
                    print(f"  {severity.upper():12} : {severity_counts[severity]}")
            
            # Highlight the most critical issues
            critical_issues = [i for i in self.issues if i.severity in ["critical", "error"]]
            if critical_issues:
                print(f"\nCritical/Error Issues:")
                for issue in critical_issues[:5]:
                    print(f"  - [{issue.open_type.name}] {issue.node[:50]}...")
                if len(critical_issues) > 5:
                    print(f"  ... and {len(critical_issues) - 5} more")
        else:
            print("No issues detected!")
        
        print(f"{'='*60}\n")
