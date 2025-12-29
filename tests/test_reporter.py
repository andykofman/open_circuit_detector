"""Unit tests for the ReportGenerator module."""

import pytest
import json
import tempfile
from pathlib import Path

from analyzer.open_detector import OpenCircuit, OpenType
from reporter.report_generator import ReportGenerator


class TestReportGenerator:
    """Unit tests for the ReportGenerator class."""

    # ==================== Initialization Tests ====================

    def test_init_with_issues_and_path(self):
        """
        Test initialization with issues and netlist path.
        
        Scenario: Create report with one issue and a path.
        Expected: Issues and path stored, timestamp set.
        """
        issues = [
            OpenCircuit(
                node="test_node",
                open_type=OpenType.FLOATING_NODE,
                description="Test description",
                affected_elements=["r1"],
                severity="warning"
            )
        ]
        
        report = ReportGenerator(issues, "test/path.sp")
        
        assert report.issues == issues
        assert report.netlist_path == "test/path.sp"
        assert report.timestamp is not None

    def test_init_without_path(self):
        """
        Test initialization without netlist path.
        
        Expected: Empty issues list, path is None.
        """
        report = ReportGenerator([], None)
        
        assert report.issues == []
        assert report.netlist_path is None

    # ==================== to_dict Tests ====================

    def test_to_dict_structure(self):
        """
        Test that to_dict returns correct structure.
        
        Expected: Keys: report_metadata, summary, issues, issues_by_type, issues_by_severity.
        """
        issues = [
            OpenCircuit(
                node="A",
                open_type=OpenType.FLOATING_NODE,
                description="Node A is floating",
                affected_elements=[],
                severity="warning"
            )
        ]
        
        report = ReportGenerator(issues, "netlist.sp")
        data = report.to_dict()
        
        assert "report_metadata" in data
        assert "summary" in data
        assert "issues" in data
        assert "issues_by_type" in data
        assert "issues_by_severity" in data

    def test_to_dict_metadata(self):
        """
        Test that metadata contains expected fields.
        
        Expected: tool_name, version, netlist_file, timestamp.
        """
        report = ReportGenerator([], "test.sp")
        data = report.to_dict()
        
        assert data["report_metadata"]["tool_name"] == "Open Circuit Detector"
        assert data["report_metadata"]["version"] == "1.0.0"
        assert data["report_metadata"]["netlist_file"] == "test.sp"
        assert "timestamp" in data["report_metadata"]

    def test_to_dict_summary_counts(self):
        """
        Test that summary contains correct counts.
        
        Scenario: 3 issues - 2 warnings, 1 critical.
        Expected: Correct counts by severity and type.
        """
        issues = [
            OpenCircuit("A", OpenType.FLOATING_NODE, "desc", [], "warning"),
            OpenCircuit("B", OpenType.FLOATING_NODE, "desc", [], "warning"),
            OpenCircuit("C", OpenType.ISOLATED_COMPONENT, "desc", [], "critical"),
        ]
        
        report = ReportGenerator(issues, None)
        data = report.to_dict()
        
        assert data["summary"]["total_issues"] == 3
        assert data["summary"]["issues_by_severity"]["warning"] == 2
        assert data["summary"]["issues_by_severity"]["critical"] == 1
        assert data["summary"]["issues_by_type"]["FLOATING_NODE"] == 2
        assert data["summary"]["issues_by_type"]["ISOLATED_COMPONENT"] == 1

    def test_to_dict_issues_content(self):
        """
        Test that issues contain all expected fields.
        
        Expected: node, type, severity, description, affected_elements.
        """
        issues = [
            OpenCircuit(
                node="test_node",
                open_type=OpenType.DC_FLOATING_NODE,
                description="Node is DC-floating",
                affected_elements=["cc1", "cc2"],
                severity="error"
            )
        ]
        
        report = ReportGenerator(issues, None)
        data = report.to_dict()
        
        issue = data["issues"][0]
        assert issue["node"] == "test_node"
        assert issue["type"] == "DC_FLOATING_NODE"
        assert issue["severity"] == "error"
        assert issue["description"] == "Node is DC-floating"
        assert issue["affected_elements"] == ["cc1", "cc2"]

    # ==================== to_json Tests ====================

    def test_to_json_valid(self):
        """
        Test that to_json returns valid JSON.
        
        Expected: Parses without error, correct issue count.
        """
        issues = [
            OpenCircuit("A", OpenType.FLOATING_NODE, "desc", ["r1"], "warning")
        ]
        
        report = ReportGenerator(issues, "test.sp")
        json_str = report.to_json()
        
        data = json.loads(json_str)
        assert data["summary"]["total_issues"] == 1

    def test_to_json_indent(self):
        """
        Test JSON indentation parameter.
        
        Expected: Indented version is longer than compact.
        """
        report = ReportGenerator([], None)
        
        json_compact = report.to_json(indent=None)
        json_indented = report.to_json(indent=4)
        
        assert len(json_indented) > len(json_compact)

    # ==================== to_text Tests ====================

    def test_to_text_contains_header(self):
        """
        Test that text report contains header.
        
        Expected: "OPEN CIRCUIT DETECTION REPORT" and filename present.
        """
        report = ReportGenerator([], "test.sp")
        text = report.to_text()
        
        assert "OPEN CIRCUIT DETECTION REPORT" in text
        assert "test.sp" in text

    def test_to_text_contains_summary(self):
        """
        Test that text report contains summary section.
        
        Scenario: 2 issues - 1 warning, 1 error.
        Expected: SUMMARY section with counts.
        """
        issues = [
            OpenCircuit("A", OpenType.FLOATING_NODE, "desc", [], "warning"),
            OpenCircuit("B", OpenType.DC_FLOATING_NODE, "desc", [], "error"),
        ]
        
        report = ReportGenerator(issues, None)
        text = report.to_text()
        
        assert "SUMMARY" in text
        assert "Total issues found: 2" in text
        assert "WARNING" in text
        assert "ERROR" in text

    def test_to_text_contains_detailed_issues(self):
        """
        Test that text report contains detailed issue information.
        
        Expected: DETAILED ISSUES section with node, type, and elements.
        """
        issues = [
            OpenCircuit(
                node="test_node",
                open_type=OpenType.DC_FLOATING_NODE,
                description="Test description",
                affected_elements=["cc1"],
                severity="error"
            )
        ]
        
        report = ReportGenerator(issues, None)
        text = report.to_text()
        
        assert "DETAILED ISSUES" in text
        assert "test_node" in text
        assert "DC_FLOATING_NODE" in text
        assert "cc1" in text

    def test_to_text_no_issues_message(self):
        """
        Test that empty report shows appropriate message.
        
        Expected: "No issues detected" appears.
        """
        report = ReportGenerator([], None)
        text = report.to_text()
        
        assert "No issues detected" in text

    def test_to_text_truncates_long_element_lists(self):
        """
        Test that very long element lists are truncated.
        
        Scenario: 20 affected elements.
        Expected: Shows first 10 and "... and 10 more elements".
        """
        affected = [f"cc_{i}" for i in range(20)]
        issues = [
            OpenCircuit("A", OpenType.DC_FLOATING_NODE, "desc", affected, "error")
        ]
        
        report = ReportGenerator(issues, None)
        text = report.to_text()
        
        assert "... and 10 more elements" in text

    # ==================== File Save Tests ====================

    def test_save_json_creates_file(self):
        """
        Test that save_json creates a valid JSON file.
        
        Expected: File exists and contains valid JSON.
        """
        issues = [
            OpenCircuit("A", OpenType.FLOATING_NODE, "desc", [], "warning")
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "report.json"
            
            report = ReportGenerator(issues, "test.sp")
            report.save_json(str(filepath))
            
            assert filepath.exists()
            
            with open(filepath) as f:
                data = json.load(f)
            
            assert data["summary"]["total_issues"] == 1

    def test_save_text_creates_file(self):
        """
        Test that save_text creates a text file.
        
        Expected: File exists and contains report header.
        """
        issues = [
            OpenCircuit("A", OpenType.FLOATING_NODE, "desc", [], "warning")
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "report.txt"
            
            report = ReportGenerator(issues, "test.sp")
            report.save_text(str(filepath))
            
            assert filepath.exists()
            
            with open(filepath) as f:
                text = f.read()
            
            assert "OPEN CIRCUIT DETECTION REPORT" in text

    # ==================== Sorting and Ordering Tests ====================

    def test_issues_sorted_by_severity(self):
        """
        Test that issues are sorted by severity in text output.
        
        Scenario: Issues with warning, critical, error.
        Expected: Critical < Error < Warning in output order.
        """
        issues = [
            OpenCircuit("A", OpenType.FLOATING_NODE, "desc", [], "warning"),
            OpenCircuit("B", OpenType.ISOLATED_COMPONENT, "desc", [], "critical"),
            OpenCircuit("C", OpenType.DC_FLOATING_NODE, "desc", [], "error"),
        ]
        
        report = ReportGenerator(issues, None)
        text = report.to_text()
        
        critical_pos = text.find("CRITICAL")
        error_pos = text.find("ERROR")
        warning_pos = text.find("WARNING")
        
        assert critical_pos < error_pos < warning_pos

    # ==================== Edge Case Tests ====================

    def test_all_open_types_handled(self):
        """
        Test that all OpenType enum values can be reported.
        
        Scenario: One of each OpenType.
        Expected: All 5 types in summary.
        """
        issues = [
            OpenCircuit("A", OpenType.FLOATING_NODE, "desc", [], "warning"),
            OpenCircuit("B", OpenType.ISOLATED_COMPONENT, "desc", [], "critical"),
            OpenCircuit("C", OpenType.FLOATING_PORT, "desc", [], "warning"),
            OpenCircuit("D", OpenType.CAPACITOR_ONLY, "desc", [], "warning"),
            OpenCircuit("E", OpenType.DC_FLOATING_NODE, "desc", [], "error"),
        ]
        
        report = ReportGenerator(issues, None)
        data = report.to_dict()
        
        assert data["summary"]["total_issues"] == 5
        assert len(data["summary"]["issues_by_type"]) == 5

    def test_empty_affected_elements(self):
        """
        Test handling of issues with no affected elements.
        
        Expected: Does not crash, empty list in output.
        """
        issues = [
            OpenCircuit("A", OpenType.FLOATING_NODE, "desc", [], "warning")
        ]
        
        report = ReportGenerator(issues, None)
        text = report.to_text()
        data = report.to_dict()
        
        assert data["issues"][0]["affected_elements"] == []

    def test_special_characters_in_node_names(self):
        """
        Test handling of special characters in node names.
        
        Scenario: Node name with %, ., and element with %.
        Expected: JSON parses correctly, text contains node name.
        """
        issues = [
            OpenCircuit(
                node="PM_CMOM1%P.internal_node",
                open_type=OpenType.FLOATING_NODE,
                description="Node with special chars",
                affected_elements=["r_special%name"],
                severity="warning"
            )
        ]
        
        report = ReportGenerator(issues, None)
        json_str = report.to_json()
        text = report.to_text()
        
        data = json.loads(json_str)
        assert data["issues"][0]["node"] == "PM_CMOM1%P.internal_node"
        assert "PM_CMOM1%P.internal_node" in text

