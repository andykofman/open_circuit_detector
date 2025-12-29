""" Unit tests for the OpenCircuitDetector module. """

import pytest
from analyzer.open_detector import OpenCircuitDetector, OpenType, OpenCircuit
from graph.circuit_graph import CircuitGraph
from parser.element_types import (
    ElementType, Resistor, Capacitor, CouplingCapacitor, Subcircuit
)


def make_subcircuit(name: str, ports: list, elements: list) -> Subcircuit:
    """Helper function to create a Subcircuit with elements."""
    return Subcircuit(
        name=name,
        ports=ports,
        elements=elements,
        internal_nodes=set()
    )


class TestOpenCircuitDetector:
    """ Unit tests for the OpenCircuitDetector class. """

    # ==================== FLOATING_NODE Tests ====================

    def test_detect_floating_node_no_connections(self):
        """
        Test detection of an internal node with zero connections.
        
        Scenario: Internal node 'orphan' exists but has no elements connected.
        This simulates a stale node reference or parsing artifact.
        Expected: FLOATING_NODE detected for node 'orphan'
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[Resistor(name="r1", node1="A", node2="VSS", value=100.0)]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        # Manually add an orphan internal node (NOT a port)
        # This could happen from a parsing error or stale reference
        graph.all_nodes.add("orphan")

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        floating_nodes = [i for i in issues if i.open_type == OpenType.FLOATING_NODE]
        assert len(floating_nodes) == 1
        assert floating_nodes[0].node == "orphan"
        assert floating_nodes[0].severity == "critical"

    def test_no_floating_node_when_connected(self):
        """
        Test that nodes with connections are NOT flagged as floating.
        
        Scenario: All nodes have at least one element connected.
        Expected: No FLOATING_NODE issues
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="B", node2="VSS", value=100.0),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        floating_nodes = [i for i in issues if i.open_type == OpenType.FLOATING_NODE]
        assert len(floating_nodes) == 0

    def test_ground_nodes_not_flagged_as_floating(self):
        """
        Test that ground nodes are never flagged even if isolated.
        
        Ground nodes (VSS, GND, 0) should be skipped.
        """
        graph = CircuitGraph()
        graph.all_nodes.add("vss")
        graph.all_nodes.add("gnd")
        # No elements, but these are ground nodes

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        floating_nodes = [i for i in issues if i.open_type == OpenType.FLOATING_NODE]
        assert len(floating_nodes) == 0

    # ==================== ISOLATED_COMPONENT Tests ====================

    def test_detect_isolated_component(self):
        """
        Test detection of an isolated island with no ground path.
        
        Scenario: A--R1--B forms an island, C--R2--VSS is grounded.
        Expected: ISOLATED_COMPONENT for {A, B}
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "C", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="C", node2="VSS", value=100.0),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        isolated = [i for i in issues if i.open_type == OpenType.ISOLATED_COMPONENT]
        assert len(isolated) == 1
        assert "a" in isolated[0].node or "b" in isolated[0].node
        assert isolated[0].severity == "critical"

    def test_no_isolated_component_when_grounded(self):
        """
        Test that fully connected circuits don't trigger ISOLATED_COMPONENT.
        
        Scenario: A--R1--B--R2--VSS (all connected to ground)
        Expected: No ISOLATED_COMPONENT issues
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="B", node2="VSS", value=100.0),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        isolated = [i for i in issues if i.open_type == OpenType.ISOLATED_COMPONENT]
        assert len(isolated) == 0

    def test_multiple_isolated_components(self):
        """
        Test detection of multiple isolated islands.
        
        Scenario: A--R1--B and C--R2--D (both isolated from ground)
        Expected: Two ISOLATED_COMPONENT issues
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "C"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="C", node2="D", value=100.0),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        isolated = [i for i in issues if i.open_type == OpenType.ISOLATED_COMPONENT]
        assert len(isolated) == 2

    def test_isolated_component_includes_affected_elements(self):
        """
        Test that affected_elements lists the elements in the isolated component.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                # No connection to VSS
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        isolated = [i for i in issues if i.open_type == OpenType.ISOLATED_COMPONENT]
        assert len(isolated) == 1
        assert "r1" in isolated[0].affected_elements

    # ==================== FLOATING_PORT Tests ====================

    def test_detect_floating_port(self):
        """
        Test detection of a port with no internal connections.
        
        Scenario: Port B declared but not connected inside.
        Expected: FLOATING_PORT for 'b'
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "B", "VSS"],
            elements=[Resistor(name="r1", node1="A", node2="VSS", value=100.0)]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        # Ports are added to port_nodes 
        # Compare with the first test where we manually added to all_nodes only
        graph.port_nodes.add("b")
        graph.all_nodes.add("b")

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        floating_ports = [i for i in issues if i.open_type == OpenType.FLOATING_PORT]
        assert len(floating_ports) == 1
        assert floating_ports[0].node == "b"
        assert floating_ports[0].severity == "warning"

    def test_no_floating_port_when_connected(self):
        """
        Test that connected ports are not flagged.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "B", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="B", node2="VSS", value=100.0),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        floating_ports = [i for i in issues if i.open_type == OpenType.FLOATING_PORT]
        assert len(floating_ports) == 0

    def test_ground_port_not_flagged(self):
        """
        Test that ground ports (VSS) are not flagged as floating.
        """
        graph = CircuitGraph()
        graph.port_nodes.add("vss")
        graph.all_nodes.add("vss")
        # VSS has no elements but is a ground node

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        floating_ports = [i for i in issues if i.open_type == OpenType.FLOATING_PORT]
        assert len(floating_ports) == 0

    # ==================== CAPACITOR_ONLY Tests ====================

    def test_detect_capacitor_only_node(self):
        """
        Test detection of nodes connected only via capacitors.
        
        Scenario: Node X connected to VSS only via capacitor.
        Expected: CAPACITOR_ONLY for 'x'
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="B", node2="VSS", value=100.0),
                Capacitor(name="c1", node1="B", node2="X", value=1e-12),
                Capacitor(name="c2", node1="X", node2="VSS", value=1e-12),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        cap_only = [i for i in issues if i.open_type == OpenType.CAPACITOR_ONLY]
        assert len(cap_only) == 1
        assert cap_only[0].node == "x"
        assert cap_only[0].severity == "warning"

    def test_no_capacitor_only_when_has_resistor(self):
        """
        Test that nodes with both R and C are not flagged.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Capacitor(name="c1", node1="A", node2="VSS", value=1e-12),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        cap_only = [i for i in issues if i.open_type == OpenType.CAPACITOR_ONLY]
        assert len(cap_only) == 0

    def test_capacitor_only_skips_ports(self):
        """
        Test that port nodes with only caps are NOT flagged. Might be intentional.
        
        Ports connected via caps may be intentional (AC coupling). 
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Capacitor(name="c1", node1="A", node2="VSS", value=1e-12),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        cap_only = [i for i in issues if i.open_type == OpenType.CAPACITOR_ONLY]
        assert len(cap_only) == 0  # 'a' is a port, should be skipped

    def test_capacitor_only_includes_affected_elements(self):
        """
        Test that affected_elements includes the capacitors connected.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="VSS", value=100.0),
                Capacitor(name="c1", node1="A", node2="X", value=1e-12),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        cap_only = [i for i in issues if i.open_type == OpenType.CAPACITOR_ONLY]
        assert len(cap_only) == 1
        assert "c1" in cap_only[0].affected_elements

    # ==================== detect_all() Integration Tests ====================

    def test_detect_all_empty_graph(self):
        """
        Test detect_all on an empty graph.
        
        Expected: No issues (nothing to detect)
        """
        graph = CircuitGraph()

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        assert len(issues) == 0

    def test_detect_all_clean_circuit(self):
        """
        Test detect_all on a properly connected circuit.
        
        Scenario: A--R1--B--R2--VSS with caps to ground
        Expected: No issues
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="B", node2="VSS", value=100.0),
                Capacitor(name="c1", node1="A", node2="VSS", value=1e-12),
                Capacitor(name="c2", node1="B", node2="VSS", value=1e-12),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        assert len(issues) == 0

    def test_detect_all_multiple_issue_types(self):
        """
        Test detect_all finds multiple types of issues in one circuit.
        
        Scenario:
        - Port UNUSED is floating
        - Node X has only cap connections
        - Island A--R1--B has no ground

        Expected: At least one of each issue type detected. Total = 3 issues.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["UNUSED", "C", "VSS"],
            elements=[
                # Grounded component
                Resistor(name="r2", node1="C", node2="VSS", value=100.0),
                # Isolated island
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                # Cap-only node
                Capacitor(name="c1", node1="C", node2="X", value=1e-12),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        # Add floating port
        graph.port_nodes.add("unused")
        graph.all_nodes.add("unused")

        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()

        # Should find exactly 3:
        # 1. FLOATING_PORT for 'unused'
        # 2. ISOLATED_COMPONENT for {a, b}
        # 3. CAPACITOR_ONLY for 'x'
        assert len(issues) == 3

        types_found = {i.open_type for i in issues}
        assert OpenType.FLOATING_PORT in types_found
        assert OpenType.ISOLATED_COMPONENT in types_found
        assert OpenType.CAPACITOR_ONLY in types_found

    # ==================== Helper Method Tests ====================

    def test_get_connected_elements(self):
        """
        Test _get_connected_elements returns correct element names.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="B", node2="C", value=100.0),
                Capacitor(name="c1", node1="B", node2="VSS", value=1e-12),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        
        # Node B is connected to r1, r2, c1
        connected = detector._get_connected_elements("b")
        assert len(connected) == 3
        assert "r1" in connected
        assert "r2" in connected
        assert "c1" in connected

    def test_get_elements_in_component(self):
        """
        Test _get_elements_in_component returns all elements touching the component.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="C", node2="VSS", value=100.0),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        detector = OpenCircuitDetector(graph)
        
        # Component {a, b}
        elements = detector._get_elements_in_component({"a", "b"})
        assert "r1" in elements
        assert "r2" not in elements


class TestDCFloatingNodeDetection:
    """Unit tests for DC-floating node detection in flattened netlists."""

    def test_detect_dc_floating_node_basic(self):
        """Test detection of a simple DC-floating node."""
        from parser.element_types import TopLevelNetlist, SubcircuitInstance
        
        # Subcircuit with grounded resistor
        subckt = Subcircuit(
            name="mysub",
            ports=["A"],
            elements=[Resistor("r1", "A", "0", 100.0)],
            internal_nodes=set()
        )
        
        # Node N connected only via capacitor - this is DC-floating
        netlist = TopLevelNetlist(
            subcircuits={"mysub": subckt},
            instances=[SubcircuitInstance("x0", "mysub", ["port1"])],
            top_level_elements=[
                CouplingCapacitor("cc1", "N", "port1", 1e-15)
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all_flattened()
        
        # Node N should be flagged as DC-floating (may also be flagged as CAPACITOR_ONLY)
        dc_floating_issues = [i for i in issues if i.node == 'n' and i.open_type == OpenType.DC_FLOATING_NODE]
        assert len(dc_floating_issues) == 1
        assert dc_floating_issues[0].severity == "error"

    def test_no_dc_floating_when_resistive_path_exists(self):
        """Test that nodes with resistive ground path are not flagged."""
        from parser.element_types import TopLevelNetlist, SubcircuitInstance
        
        subckt = Subcircuit(
            name="mysub",
            ports=["A"],
            elements=[Resistor("r1", "A", "0", 100.0)],
            internal_nodes=set()
        )
        
        # Node N has both capacitor AND resistor to ground
        netlist = TopLevelNetlist(
            subcircuits={"mysub": subckt},
            instances=[SubcircuitInstance("x0", "mysub", ["port1"])],
            top_level_elements=[
                CouplingCapacitor("cc1", "N", "port1", 1e-15),
                Resistor("r_bias", "N", "0", 1e6)  # Bias resistor to ground
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all_flattened()
        
        # Node N should NOT be flagged - it has resistive path to ground
        n_issues = [i for i in issues if i.node == 'n' and i.open_type == OpenType.DC_FLOATING_NODE]
        assert len(n_issues) == 0

    def test_dc_floating_with_multiple_caps(self):
        """Test DC-floating detection with multiple capacitive connections."""
        from parser.element_types import TopLevelNetlist, SubcircuitInstance
        
        subckt = Subcircuit(
            name="mysub",
            ports=["A", "B", "C"],
            elements=[
                Resistor("r1", "A", "0", 100.0),
                Resistor("r2", "B", "0", 100.0),
                Resistor("r3", "C", "0", 100.0),
            ],
            internal_nodes=set()
        )
        
        # Node N connected to 3 ports via capacitors
        netlist = TopLevelNetlist(
            subcircuits={"mysub": subckt},
            instances=[SubcircuitInstance("x0", "mysub", ["p1", "p2", "p3"])],
            top_level_elements=[
                CouplingCapacitor("cc1", "N", "p1", 1e-15),
                CouplingCapacitor("cc2", "N", "p2", 1e-15),
                CouplingCapacitor("cc3", "N", "p3", 1e-15),
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all_flattened()
        
        # Look specifically for DC_FLOATING_NODE issues for node 'n'
        dc_floating = [i for i in issues if i.node == 'n' and i.open_type == OpenType.DC_FLOATING_NODE]
        assert len(dc_floating) == 1
        assert "3 capacitive connections" in dc_floating[0].description

    def test_detect_all_flattened_returns_list(self):
        """Test that detect_all_flattened returns a list of OpenCircuit."""
        from parser.element_types import TopLevelNetlist
        
        netlist = TopLevelNetlist(
            subcircuits={},
            instances=[],
            top_level_elements=[]
        )
        
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all_flattened()
        
        assert isinstance(issues, list)

    def test_has_resistive_path_to_ground_direct(self):
        """Test _has_resistive_path_to_ground with direct ground connection."""
        subckt = Subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[Resistor("r1", "A", "VSS", 100.0)],
            internal_nodes=set()
        )
        
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        detector = OpenCircuitDetector(graph)
        
        assert detector._has_resistive_path_to_ground('a') is True

    def test_has_resistive_path_to_ground_indirect(self):
        """Test _has_resistive_path_to_ground with multi-hop path."""
        subckt = Subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor("r1", "A", "B", 100.0),
                Resistor("r2", "B", "C", 100.0),
                Resistor("r3", "C", "VSS", 100.0),
            ],
            internal_nodes={"B", "C"}
        )
        
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        detector = OpenCircuitDetector(graph)
        
        # A should reach VSS through B and C
        assert detector._has_resistive_path_to_ground('a') is True

    def test_has_resistive_path_to_ground_no_path(self):
        """Test _has_resistive_path_to_ground when no path exists."""
        subckt = Subcircuit(
            name="test",
            ports=["A", "B"],
            elements=[
                Resistor("r1", "A", "B", 100.0),
                # No connection to ground
            ],
            internal_nodes=set()
        )
        
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        detector = OpenCircuitDetector(graph)
        
        assert detector._has_resistive_path_to_ground('a') is False

    def test_has_resistive_path_ignores_capacitors(self):
        """Test that capacitor-only paths don't count as resistive paths."""
        subckt = Subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Capacitor("c1", "A", "VSS", 1e-12),  # Cap to ground - doesn't count!
            ],
            internal_nodes=set()
        )
        
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        detector = OpenCircuitDetector(graph)
        
        # A has cap to VSS but no resistive path
        assert detector._has_resistive_path_to_ground('a') is False

    def test_ground_node_is_on_ground(self):
        """Test that ground nodes themselves return True for ground path."""
        graph = CircuitGraph()
        graph.all_nodes.add('vss')
        
        detector = OpenCircuitDetector(graph)
        
        assert detector._has_resistive_path_to_ground('vss') is True

    def test_affected_elements_for_dc_floating(self):
        """Test that affected elements are correctly identified for DC-floating nodes."""
        from parser.element_types import TopLevelNetlist, SubcircuitInstance
        
        subckt = Subcircuit(
            name="mysub",
            ports=["A"],
            elements=[Resistor("r1", "A", "0", 100.0)],
            internal_nodes=set()
        )
        
        netlist = TopLevelNetlist(
            subcircuits={"mysub": subckt},
            instances=[SubcircuitInstance("x0", "mysub", ["port1"])],
            top_level_elements=[
                CouplingCapacitor("cc1", "N", "port1", 1e-15),
                CouplingCapacitor("cc2", "N", "port1", 2e-15),
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all_flattened()
        
        # Filter for DC_FLOATING_NODE issues only
        dc_floating = [i for i in issues if i.node == 'n' and i.open_type == OpenType.DC_FLOATING_NODE]
        assert len(dc_floating) == 1
        assert 'cc1' in dc_floating[0].affected_elements
        assert 'cc2' in dc_floating[0].affected_elements

