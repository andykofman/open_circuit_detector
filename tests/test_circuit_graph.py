"""Unit tests for the CircuitGraph module."""

import pytest
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


class TestCircuitGraph:
    """Unit tests for the CircuitGraph class."""

    # ==================== Initialization Tests ====================

    def test_empty_graph_initialization(self):
        """
        Test that a new graph starts empty.
        
        Expected: All collections empty, ground_nodes has defaults.
        """
        graph = CircuitGraph()

        assert len(graph.all_nodes) == 0
        assert len(graph.resistive_adj) == 0
        assert len(graph.capacitive_adj) == 0
        assert len(graph.port_nodes) == 0
        assert len(graph.elements) == 0
        assert graph.ground_nodes == {'0', 'gnd', 'vss', 'ground'}

    # ==================== build_from_subcircuit Tests ====================

    def test_build_from_subcircuit_resistor(self):
        """
        Test building graph from a subcircuit with resistors.
        
        Scenario: Simple subcircuit with R1 between A and B.
        Expected: Nodes added, resistive adjacency bidirectional, ports stored.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "B"],
            elements=[Resistor(name="r1", node1="A", node2="B", value=100.0)]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        # Check nodes are added (lowercase)
        assert "a" in graph.all_nodes
        assert "b" in graph.all_nodes

        # Check resistive adjacency (bidirectional)
        assert "b" in graph.resistive_adj["a"]
        assert "a" in graph.resistive_adj["b"]

        # Check ports are stored
        assert graph.port_nodes == {"a", "b"}

        # Check element is stored
        assert "r1" in graph.elements

    def test_build_from_subcircuit_capacitor(self):
        """
        Test building graph from a subcircuit with capacitors.
        
        Scenario: Capacitor from A to VSS.
        Expected: Capacitor goes to capacitive_adj, NOT resistive_adj.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[Capacitor(name="c1", node1="A", node2="VSS", value=1e-12)]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        # Check nodes are added
        assert "a" in graph.all_nodes
        assert "vss" in graph.all_nodes

        # Capacitors go to capacitive_adj, NOT resistive_adj
        assert "vss" in graph.capacitive_adj["a"]
        assert "a" in graph.capacitive_adj["vss"]
        assert len(graph.resistive_adj["a"]) == 0

    def test_case_insensitive_nodes(self):
        """
        Test that node names are normalized to lowercase.
        
        Scenario: Mixed case node names (VSS, NodeA, NODEA, gnd).
        Expected: All stored as lowercase, connections preserved.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["VSS", "GND"],
            elements=[
                Resistor(name="r1", node1="VSS", node2="NodeA", value=100.0),
                Resistor(name="r2", node1="NODEA", node2="gnd", value=100.0),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        # All stored as lowercase
        assert "vss" in graph.all_nodes
        assert "nodea" in graph.all_nodes
        assert "gnd" in graph.all_nodes

        # VSS and GND should both connect to nodea
        assert "nodea" in graph.resistive_adj["vss"]
        assert "nodea" in graph.resistive_adj["gnd"]

    # ==================== Connected Component Tests ====================

    def test_get_resistive_connected_component_simple(self):
        """
        Test finding connected component in a simple chain.
        
        Scenario: A -- R1 -- B -- R2 -- VSS (all connected).
        Expected: All nodes in same component.
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

        # Starting from A, should reach all nodes
        component = graph.get_resistive_connected_component("A")
        assert component == {"a", "b", "vss"}

        # Starting from VSS, should also reach all
        component = graph.get_resistive_connected_component("vss")
        assert component == {"a", "b", "vss"}

    def test_get_resistive_connected_component_isolated(self):
        """
        Test that capacitors don't connect resistive components.
        
        Scenario: A -- R1 -- B   and   C -- R2 -- VSS, with B -- C1 -- C (capacitor).
        Expected: {A, B} and {C, VSS} are separate components.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Capacitor(name="c1", node1="B", node2="C", value=1e-12),
                Resistor(name="r2", node1="C", node2="VSS", value=100.0),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        # A and B are connected via resistor
        component_a = graph.get_resistive_connected_component("A")
        assert component_a == {"a", "b"}

        # C and VSS are connected via resistor
        component_c = graph.get_resistive_connected_component("C")
        assert component_c == {"c", "vss"}

        # They are separate components (capacitor doesn't bridge for DC)
        assert component_a != component_c

    def test_get_all_connected_components_single(self):
        """
        Test getting all components when circuit is fully connected.
        
        Scenario: A -- R1 -- B -- R2 -- VSS.
        Expected: Exactly one component with all nodes.
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

        components = graph.get_all_connected_components()

        assert len(components) == 1
        assert components[0] == {"a", "b", "vss"}

    def test_get_all_connected_components_multiple(self):
        """
        Test getting all components when there are isolated islands.
        
        Scenario: Group 1: A -- R1 -- B, Group 2: C -- R2 -- VSS.
        Expected: Two separate components.
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

        components = graph.get_all_connected_components()

        assert len(components) == 2
        
        component_sets = [frozenset(c) for c in components]
        assert frozenset({"a", "b"}) in component_sets
        assert frozenset({"c", "vss"}) in component_sets

    # ==================== Ground Connection Tests ====================

    def test_has_ground_connection_true(self):
        """
        Test node with path to ground returns True.
        
        Scenario: A -- R1 -- B -- R2 -- VSS.
        Expected: All nodes return True.
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

        assert graph.has_ground_connection("A") is True
        assert graph.has_ground_connection("B") is True
        assert graph.has_ground_connection("VSS") is True

    def test_has_ground_connection_false(self):
        """
        Test floating node returns False.
        
        Scenario: A -- R1 -- B (no ground node).
        Expected: Both nodes return False.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "B"],
            elements=[Resistor(name="r1", node1="A", node2="B", value=100.0)]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        assert graph.has_ground_connection("A") is False
        assert graph.has_ground_connection("B") is False

    def test_has_ground_connection_capacitor_only(self):
        """
        Test that capacitor-only path to ground returns False.
        
        Scenario: A -- C1 -- VSS (capacitor blocks DC).
        Expected: A returns False.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[Capacitor(name="c1", node1="A", node2="VSS", value=1e-12)]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        assert graph.has_ground_connection("A") is False

    def test_has_ground_connection_all_ground_variants(self):
        """
        Test all ground node variants are recognized.
        
        Scenario: Test with 0, GND, VSS, ground.
        Expected: All recognized as ground.
        """
        for ground_name in ["0", "GND", "VSS", "ground"]:
            subckt = make_subcircuit(
                name="test",
                ports=["A", ground_name],
                elements=[Resistor(name="r1", node1="A", node2=ground_name, value=100.0)]
            )

            graph = CircuitGraph()
            graph.build_from_subcircuit(subckt)

            assert graph.has_ground_connection("A") is True, f"Failed for ground: {ground_name}"

    # ==================== Node Degree Tests ====================

    def test_get_node_degree_resistors_only(self):
        """
        Test node degree counting resistor connections.
        
        Scenario: B connected to A, C, VSS via resistors.
        Expected: B has degree 3.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "C", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="B", node2="C", value=100.0),
                Resistor(name="r3", node1="B", node2="VSS", value=100.0),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        assert graph.get_node_degree("B") == 3
        assert graph.get_node_degree("A") == 1
        assert graph.get_node_degree("C") == 1
        assert graph.get_node_degree("VSS") == 1

    def test_get_node_degree_with_capacitors(self):
        """
        Test node degree including capacitor connections.
        
        Scenario: B connected to A via resistor, to VSS via capacitor.
        Expected: Degree 1 without caps, degree 2 with caps.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Capacitor(name="c1", node1="B", node2="VSS", value=1e-12),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        assert graph.get_node_degree("B", include_capacitors=False) == 1
        assert graph.get_node_degree("B", include_capacitors=True) == 2

    def test_get_node_degree_nonexistent_node(self):
        """
        Test node degree for node not in graph.
        
        Expected: Returns 0 (defaultdict behavior).
        """
        graph = CircuitGraph()

        assert graph.get_node_degree("nonexistent") == 0

    # ==================== Element Type Handling Tests ====================

    def test_coupling_capacitor_handling(self):
        """
        Test that coupling capacitors are treated like regular capacitors.
        
        Scenario: Coupling cap cc1 between A and B.
        Expected: Added to capacitive_adj, not resistive_adj.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "B", "VSS"],
            elements=[CouplingCapacitor(name="cc1", node1="A", node2="B", value=1e-15)]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        assert "a" in graph.all_nodes
        assert "b" in graph.all_nodes
        assert "b" in graph.capacitive_adj["a"]
        assert "a" in graph.capacitive_adj["b"]

    # ==================== Complex Circuit Tests ====================

    def test_complex_circuit(self):
        """
        Test a more complex circuit topology.
        
        Scenario: A--R1--B--R2--C with R3 from B to VSS, caps A-VSS and C-VSS.
        Expected: Single component, all grounded, correct degrees.
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "C", "VSS"],
            elements=[
                Resistor(name="r1", node1="A", node2="B", value=100.0),
                Resistor(name="r2", node1="B", node2="C", value=100.0),
                Resistor(name="r3", node1="B", node2="VSS", value=100.0),
                Capacitor(name="c1", node1="A", node2="VSS", value=1e-12),
                Capacitor(name="c2", node1="C", node2="VSS", value=1e-12),
            ]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        # All nodes should be in one resistive component
        components = graph.get_all_connected_components()
        assert len(components) == 1

        # All nodes should have ground connection
        for node in ["A", "B", "C"]:
            assert graph.has_ground_connection(node) is True

        # Check degrees
        assert graph.get_node_degree("B") == 3
        assert graph.get_node_degree("A") == 1
        assert graph.get_node_degree("C") == 1

        # With capacitors
        assert graph.get_node_degree("A", include_capacitors=True) == 2
        assert graph.get_node_degree("C", include_capacitors=True) == 2


class TestCircuitGraphNewMethods:
    """Unit tests for the new CircuitGraph methods added for flattened netlist support."""

    # ==================== Degree Methods Tests ====================

    def test_get_resistive_degree(self):
        """
        Test get_resistive_degree returns correct count.
        
        Scenario: Node B connected to 3 resistors.
        Expected: Resistive degree = 3
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "C", "D", "VSS"],
            elements=[
                Resistor("r1", "A", "B", 100.0),
                Resistor("r2", "B", "C", 100.0),
                Resistor("r3", "B", "D", 100.0),
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        assert graph.get_resistive_degree("b") == 3
        assert graph.get_resistive_degree("a") == 1

    def test_get_capacitive_degree(self):
        """
        Test get_capacitive_degree returns correct count.
        
        Scenario: Node X connected to 2 capacitors.
        Expected: Capacitive degree = 2
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Capacitor("c1", "X", "A", 1e-12),
                Capacitor("c2", "X", "VSS", 1e-12),
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        assert graph.get_capacitive_degree("x") == 2
        assert graph.get_capacitive_degree("a") == 1

    def test_get_resistive_degree_zero(self):
        """
        Test get_resistive_degree for node with no resistors.
        
        Scenario: Node only connected via capacitors.
        Expected: Resistive degree = 0
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Capacitor("c1", "X", "A", 1e-12),
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        assert graph.get_resistive_degree("x") == 0

    def test_get_capacitive_degree_zero(self):
        """
        Test get_capacitive_degree for node with no capacitors.
        
        Scenario: Node only connected via resistors.
        Expected: Capacitive degree = 0
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[
                Resistor("r1", "A", "VSS", 100.0),
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        assert graph.get_capacitive_degree("a") == 0

    # ==================== get_resistive_neighbors Tests ====================

    def test_get_resistive_neighbors(self):
        """
        Test get_resistive_neighbors returns correct set.
        
        Scenario: Node B connected to A, C, D via resistors.
        Expected: Neighbors = {a, c, d}
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "C", "D"],
            elements=[
                Resistor("r1", "A", "B", 100.0),
                Resistor("r2", "B", "C", 100.0),
                Resistor("r3", "B", "D", 100.0),
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        neighbors = graph.get_resistive_neighbors("b")
        assert neighbors == {"a", "c", "d"}

    def test_get_resistive_neighbors_excludes_capacitor_connections(self):
        """
        Test that capacitor connections are not in resistive neighbors.
        
        Scenario: Node A has resistor to B and capacitor to C.
        Expected: Resistive neighbors = {b} (not c)
        """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "B", "C"],
            elements=[
                Resistor("r1", "A", "B", 100.0),
                Capacitor("c1", "A", "C", 1e-12),
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        
        neighbors = graph.get_resistive_neighbors("a")
        assert "b" in neighbors
        assert "c" not in neighbors

    def test_get_resistive_neighbors_empty(self):
        """
        Test get_resistive_neighbors for isolated node.
        
        Expected: Empty set
        """
        graph = CircuitGraph()
        graph.all_nodes.add("orphan")
        
        neighbors = graph.get_resistive_neighbors("orphan")
        assert neighbors == set()

    # ==================== build_from_netlist Tests ====================

    def test_build_from_netlist_basic(self):
        """
        Test build_from_netlist creates graph from TopLevelNetlist.
        
        Scenario: Simple subcircuit with instance and top-level cap.
        Expected: All nodes and edges correctly added.
        """
        from parser.element_types import TopLevelNetlist, SubcircuitInstance
        
        subckt = make_subcircuit(
            name="mysub",
            ports=["A"],
            elements=[Resistor("r1", "A", "0", 100.0)]
        )
        
        netlist = TopLevelNetlist(
            subcircuits={"mysub": subckt},
            instances=[SubcircuitInstance("x0", "mysub", ["port1"])],
            top_level_elements=[CouplingCapacitor("cc1", "N", "port1", 1e-15)]
        )
        
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        # Check nodes exist
        assert "n" in graph.all_nodes
        assert "port1" in graph.all_nodes

    def test_build_from_netlist_maps_ports_to_connections(self):
        """
        Test that subcircuit ports are mapped to instance connections.
        
        Scenario: Subcircuit port A maps to instance connection ext_node.
        Expected: Resistor connects ext_node to prefixed ground (x0_0).
        """
        from parser.element_types import TopLevelNetlist, SubcircuitInstance
        
        subckt = make_subcircuit(
            name="mysub",
            ports=["A"],
            elements=[Resistor("r1", "A", "0", 100.0)]
        )
        
        netlist = TopLevelNetlist(
            subcircuits={"mysub": subckt},
            instances=[SubcircuitInstance("x0", "mysub", ["ext_node"])],
            top_level_elements=[]
        )
        
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        # ext_node should have resistive connection (internal node 0 gets prefixed)
        assert "ext_node" in graph.all_nodes
        assert graph.get_resistive_degree("ext_node") == 1

    def test_build_from_netlist_adds_top_level_elements(self):
        """
        Test that top-level elements are added to graph.
        
        Scenario: Two coupling caps at top level.
        Expected: Capacitive adjacency updated.
        """
        from parser.element_types import TopLevelNetlist, SubcircuitInstance
        
        subckt = make_subcircuit(
            name="mysub",
            ports=["A"],
            elements=[Resistor("r1", "A", "0", 100.0)]
        )
        
        netlist = TopLevelNetlist(
            subcircuits={"mysub": subckt},
            instances=[SubcircuitInstance("x0", "mysub", ["p1"])],
            top_level_elements=[
                CouplingCapacitor("cc1", "N", "p1", 1e-15),
                CouplingCapacitor("cc2", "N", "p2", 1e-15),
            ]
        )
        
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        # Node N should have 2 capacitive connections
        assert graph.get_capacitive_degree("n") == 2

    def test_build_from_netlist_internal_nodes_prefixed(self):
        """
        Test that internal subcircuit nodes get instance prefix.
        
        Scenario: Internal node B in subcircuit instance x0.
        Expected: Node named x0_b in flattened graph.
        """
        from parser.element_types import TopLevelNetlist, SubcircuitInstance
        
        subckt = Subcircuit(
            name="mysub",
            ports=["A", "C"],
            elements=[
                Resistor("r1", "A", "B", 100.0),
                Resistor("r2", "B", "C", 100.0),
            ],
            internal_nodes={"B"}
        )
        
        netlist = TopLevelNetlist(
            subcircuits={"mysub": subckt},
            instances=[SubcircuitInstance("x0", "mysub", ["ext_a", "ext_c"])],
            top_level_elements=[]
        )
        
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        # Internal node B should be prefixed
        assert "x0_b" in graph.all_nodes

    def test_build_from_netlist_empty(self):
        """
        Test build_from_netlist with empty netlist.
        
        Expected: Empty graph, no errors.
        """
        from parser.element_types import TopLevelNetlist
        
        netlist = TopLevelNetlist(
            subcircuits={},
            instances=[],
            top_level_elements=[]
        )
        
        graph = CircuitGraph()
        graph.build_from_netlist(netlist)
        
        assert len(graph.all_nodes) == 0
