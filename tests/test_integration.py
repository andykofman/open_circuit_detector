"""Integration tests for the Open Circuit Detector pipeline."""

import pytest
import json
import tempfile
from pathlib import Path

from parser.spice_parser import SpiceParser
from parser.element_types import SubcircuitInstance, TopLevelNetlist
from graph.circuit_graph import CircuitGraph
from analyzer.open_detector import OpenCircuitDetector, OpenType
from reporter.report_generator import ReportGenerator


class TestIntegrationRealNetlist:
    """Integration tests using the real netlist file."""
    
    @pytest.fixture
    def netlist_path(self) -> Path:
        """Path to the real netlist file."""
        path = Path(__file__).parent.parent / "data" / "netlist 1.sp"
        if not path.exists():
            pytest.skip(f"Real netlist not found at {path}")
        return path
    
    @pytest.fixture
    def parsed_netlist(self, netlist_path: Path) -> TopLevelNetlist:
        """Parse the real netlist."""
        parser = SpiceParser()
        return parser.parse_file_complete(str(netlist_path))
    
    @pytest.fixture
    def flattened_graph(self, parsed_netlist: TopLevelNetlist) -> CircuitGraph:
        """Build flattened graph from the netlist."""
        graph = CircuitGraph()
        graph.build_from_netlist(parsed_netlist)
        return graph
    
    # ==================== Parsing Tests ====================
    
    def test_parse_complete_netlist_structure(self, parsed_netlist: TopLevelNetlist):
        """
        Test that the netlist structure is correctly parsed.
        
        Expected: 1 subcircuit, 1 instance, 84 top-level coupling capacitors.
        """
        assert len(parsed_netlist.subcircuits) == 1
        assert len(parsed_netlist.instances) == 1
        assert len(parsed_netlist.top_level_elements) == 84
    
    def test_subcircuit_has_expected_ports(self, parsed_netlist: TopLevelNetlist):
        """
        Test that the subcircuit has the expected number of ports.
        
        Expected: 84 ports.
        """
        subcircuit = next(iter(parsed_netlist.subcircuits.values()))
        assert len(subcircuit.ports) == 84
    
    def test_subcircuit_instance_connections(self, parsed_netlist: TopLevelNetlist):
        """
        Test that the subcircuit instance has valid connections.
        
        Expected: Connections exist and instance type matches subcircuit.
        """
        instance = parsed_netlist.instances[0]
        assert len(instance.connections) > 0
        assert instance.subcircuit_type in parsed_netlist.subcircuits
    
    def test_top_level_elements_are_coupling_caps(self, parsed_netlist: TopLevelNetlist):
        """
        Test that all top-level elements are coupling capacitors.
        
        Expected: All 84 elements are CouplingCapacitor instances.
        """
        from parser.element_types import CouplingCapacitor
        
        for element in parsed_netlist.top_level_elements:
            assert isinstance(element, CouplingCapacitor), \
                f"Expected CouplingCapacitor, got {type(element).__name__}"
    
    # ==================== Graph Flattening Tests ====================
    
    def test_flattened_graph_has_top_level_nodes(self, flattened_graph: CircuitGraph):
        """
        Test that the flattened graph contains nodes from top-level elements.
        
        Expected: Node 'n' exists in the graph.
        """
        assert 'n' in flattened_graph.all_nodes
        assert len(flattened_graph.all_nodes) > 0
    
    def test_node_n_has_expected_connectivity(self, flattened_graph: CircuitGraph):
        """
        Test node 'n' connectivity pattern (THE PLANTED BUG).
        
        Scenario: Node 'n' is connected via 83 coupling capacitors.
        Expected: 83 capacitive connections, 0 resistive connections.
        """
        c_degree = len(flattened_graph.capacitive_adj.get('n', set()))
        r_degree = len(flattened_graph.resistive_adj.get('n', set()))
        
        assert c_degree == 83, f"Expected 83 capacitive connections, got {c_degree}"
        assert r_degree == 0, f"Expected 0 resistive connections, got {r_degree}"
    
    def test_node_n_has_no_ground_connection(self, flattened_graph: CircuitGraph):
        """
        Test that node 'n' has no resistive path to ground.
        
        Scenario: Node 'n' only has capacitive connections.
        Expected: has_ground_connection returns False.
        """
        assert not flattened_graph.has_ground_connection('n')
    
    # ==================== Detection Tests ====================
    
    def test_detect_node_n_as_dc_floating(self, flattened_graph: CircuitGraph):
        """
        Test that node 'n' is detected as DC-floating.
        
        Scenario: Node 'n' has 83 caps, no resistors, no path to ground.
        Expected: DC_FLOATING_NODE issue with severity "error".
        """
        detector = OpenCircuitDetector(flattened_graph)
        issues = detector.detect_all_flattened()
        
        n_issues = [i for i in issues if i.node == 'n']
        assert len(n_issues) >= 1, f"Expected at least 1 issue for node 'n', got {len(n_issues)}"
        
        dc_floating_issues = [i for i in n_issues if i.open_type == OpenType.DC_FLOATING_NODE]
        assert len(dc_floating_issues) == 1, "Expected exactly 1 DC_FLOATING_NODE issue for node 'n'"
        
        n_issue = dc_floating_issues[0]
        assert n_issue.severity == "error"
        assert "83 capacitive connections" in n_issue.description
        assert "r_degree=0" in n_issue.description
    
    def test_detect_all_flattened_finds_issues(self, flattened_graph: CircuitGraph):
        """
        Test that flattened detection finds at least one DC-floating issue.
        
        Expected: At least 1 DC_FLOATING_NODE issue.
        """
        detector = OpenCircuitDetector(flattened_graph)
        issues = detector.detect_all_flattened()
        
        assert len(issues) >= 1
        
        dc_floating_issues = [i for i in issues if i.open_type == OpenType.DC_FLOATING_NODE]
        assert len(dc_floating_issues) >= 1
    
    def test_issue_affected_elements_for_node_n(self, flattened_graph: CircuitGraph):
        """
        Test that affected elements are correctly identified for node 'n'.
        
        Expected: 83 affected elements, all starting with 'cc_'.
        """
        detector = OpenCircuitDetector(flattened_graph)
        issues = detector.detect_all_flattened()
        
        n_issue = next((i for i in issues if i.node == 'n'), None)
        assert n_issue is not None
        
        assert len(n_issue.affected_elements) == 83
        
        for elem in n_issue.affected_elements:
            assert elem.startswith('cc_'), f"Expected cc_* element, got {elem}"
    
    # ==================== Reporter Tests ====================
    
    def test_report_generator_json_output(self, flattened_graph: CircuitGraph):
        """
        Test JSON report generation.
        
        Expected: Valid JSON with report_metadata, summary, and issues sections.
        """
        detector = OpenCircuitDetector(flattened_graph)
        issues = detector.detect_all_flattened()
        
        report = ReportGenerator(issues, "test_netlist.sp")
        json_str = report.to_json()
        
        data = json.loads(json_str)
        
        assert "report_metadata" in data
        assert "summary" in data
        assert "issues" in data
        assert data["summary"]["total_issues"] == len(issues)
    
    def test_report_generator_text_output(self, flattened_graph: CircuitGraph):
        """
        Test text report generation.
        
        Expected: Contains OPEN CIRCUIT DETECTION REPORT, SUMMARY, and node 'n'.
        """
        detector = OpenCircuitDetector(flattened_graph)
        issues = detector.detect_all_flattened()
        
        report = ReportGenerator(issues, "test_netlist.sp")
        text = report.to_text()
        
        assert "OPEN CIRCUIT DETECTION REPORT" in text
        assert "SUMMARY" in text
        assert "DETAILED ISSUES" in text
        assert "Node: n" in text or "node 'n'" in text.lower()
    
    def test_report_save_files(self, flattened_graph: CircuitGraph):
        """
        Test that reports can be saved to files.
        
        Expected: Both JSON and text files created with correct content.
        """
        detector = OpenCircuitDetector(flattened_graph)
        issues = detector.detect_all_flattened()
        
        report = ReportGenerator(issues, "test_netlist.sp")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "report.json"
            text_path = Path(tmpdir) / "report.txt"
            
            report.save_json(str(json_path))
            report.save_text(str(text_path))
            
            assert json_path.exists()
            assert text_path.exists()
            
            # Verify JSON content
            with open(json_path) as f:
                data = json.load(f)
                assert "issues" in data
            
            # Verify text content
            with open(text_path) as f:
                text = f.read()
                assert "OPEN CIRCUIT DETECTION REPORT" in text


class TestIntegrationSubcircuitOnly:
    """Integration tests for subcircuit-only analysis mode (without flattening)."""
    
    @pytest.fixture
    def netlist_path(self) -> Path:
        """Path to the real netlist file."""
        path = Path(__file__).parent.parent / "data" / "netlist 1.sp"
        if not path.exists():
            pytest.skip(f"Real netlist not found at {path}")
        return path
    
    # ==================== Subcircuit-Only Detection Tests ====================
    
    def test_subcircuit_only_detection(self, netlist_path: Path):
        """
        Test detection on subcircuit only (original behavior).
        
        Scenario: Parse and analyze subcircuit without top-level elements.
        Expected: Returns a list of issues (node 'n' not visible).
        """
        parser = SpiceParser()
        subcircuits = parser.parse_file(str(netlist_path))
        
        assert len(subcircuits) == 1
        
        graph = CircuitGraph()
        subcircuit = next(iter(subcircuits.values()))
        graph.build_from_subcircuit(subcircuit)
        
        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()
        
        assert isinstance(issues, list)


class TestIntegrationEndToEnd:
    """End-to-end integration tests simulating CLI usage."""
    
    @pytest.fixture
    def netlist_path(self) -> Path:
        """Path to the real netlist file."""
        path = Path(__file__).parent.parent / "data" / "netlist 1.sp"
        if not path.exists():
            pytest.skip(f"Real netlist not found at {path}")
        return path
    
    # ==================== Complete Pipeline Tests ====================
    
    def test_complete_pipeline(self, netlist_path: Path):
        """
        Test the complete analysis pipeline end-to-end.
        
        Scenario: Parse → Build graph → Detect → Report.
        Expected: DC_FLOATING_NODE for node 'n', valid report structure.
        """
        # Step 1: Parse
        parser = SpiceParser()
        netlist = parser.parse_file_complete(str(netlist_path))
        
        # Step 2: Build graph
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        # Step 3: Detect issues
        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all_flattened()
        
        # Step 4: Generate report
        report = ReportGenerator(issues, str(netlist_path))
        
        # Verify complete pipeline output
        data = report.to_dict()
        
        n_issues = [i for i in data["issues"] if i["node"] == "n"]
        assert len(n_issues) >= 1
        
        dc_floating = [i for i in n_issues if i["type"] == "DC_FLOATING_NODE"]
        assert len(dc_floating) == 1
        
        assert data["report_metadata"]["tool_name"] == "Open Circuit Detector"
        assert data["summary"]["total_issues"] > 0
