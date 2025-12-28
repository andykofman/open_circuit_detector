""" Unit tests for the CircuitGraph module. """

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
    """ Unit tests for the CircuitGraph class. """

    def test_empty_graph_initialization(self):
        """ Test that a new graph starts empty. """
        graph = CircuitGraph()

        assert len(graph.all_nodes) == 0
        assert len(graph.resistive_adj) == 0
        assert len(graph.capacitive_adj) == 0
        assert len(graph.port_nodes) == 0
        assert len(graph.elements) == 0
        assert graph.ground_nodes == {'0', 'gnd', 'vss', 'ground'}

    def test_build_from_subcircuit_resistor(self):
        """ Test building graph from a subcircuit with resistors. """
        # Create a simple subcircuit: R1 between A and B
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
        """ Test building graph from a subcircuit with capacitors. """
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
        """ Test that node names are normalized to lowercase. """
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

    def test_get_resistive_connected_component_simple(self):
        """ Test finding connected component in a simple chain. """
        # Circuit: A -- R1 -- B -- R2 -- VSS
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
        """ Test that capacitors don't connect resistive components. """
        # Circuit: A -- R1 -- B    C -- R2 -- VSS
        #          B -- C1 -- C (capacitor bridge, doesn't count for DC)
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
        """ Test getting all components when circuit is fully connected. """
        # Fully connected: A -- R1 -- B -- R2 -- VSS
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

        # Should be exactly one component
        assert len(components) == 1
        assert components[0] == {"a", "b", "vss"}

    def test_get_all_connected_components_multiple(self):
        """ Test getting all components when there are isolated islands. """
        # Two isolated groups:
        # Group 1: A -- R1 -- B
        # Group 2: C -- R2 -- VSS
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

        # Should be two separate components
        assert len(components) == 2
        
        # Check both components exist (order may vary)
        component_sets = [frozenset(c) for c in components]
        assert frozenset({"a", "b"}) in component_sets
        assert frozenset({"c", "vss"}) in component_sets

    def test_has_ground_connection_true(self):
        """ Test node with path to ground returns True. """
        # A -- R1 -- B -- R2 -- VSS
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
        """ Test floating node returns False. """
        # A -- R1 -- B (no connection to any ground node)
        subckt = make_subcircuit(
            name="test",
            ports=["A", "B"],
            elements=[Resistor(name="r1", node1="A", node2="B", value=100.0)]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        # Neither A nor B can reach ground
        assert graph.has_ground_connection("A") is False
        assert graph.has_ground_connection("B") is False

    def test_has_ground_connection_capacitor_only(self):
        """ Test that capacitor-only path to ground returns False. """
        # A -- C1 -- VSS (capacitor blocks DC)
        subckt = make_subcircuit(
            name="test",
            ports=["A", "VSS"],
            elements=[Capacitor(name="c1", node1="A", node2="VSS", value=1e-12)]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        # A is connected to VSS only via capacitor, not resistor
        assert graph.has_ground_connection("A") is False

    def test_has_ground_connection_all_ground_variants(self):
        """ Test all ground node variants are recognized. """
        for ground_name in ["0", "GND", "VSS", "ground"]:
            subckt = make_subcircuit(
                name="test",
                ports=["A", ground_name],
                elements=[Resistor(name="r1", node1="A", node2=ground_name, value=100.0)]
            )

            graph = CircuitGraph()
            graph.build_from_subcircuit(subckt)

            assert graph.has_ground_connection("A") is True, f"Failed for ground: {ground_name}"

    def test_get_node_degree_resistors_only(self):
        """ Test node degree counting resistor connections. """
        # B is connected to A, C, and VSS via resistors (degree 3)
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
        """ Test node degree including capacitor connections. """
        # B connected to A via resistor, and to VSS via capacitor
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

        # Without capacitors: B has 1 resistor connection
        assert graph.get_node_degree("B", include_capacitors=False) == 1

        # With capacitors: B has 1 resistor + 1 capacitor = 2
        assert graph.get_node_degree("B", include_capacitors=True) == 2

    def test_get_node_degree_nonexistent_node(self):
        """ Test node degree for node not in graph returns 0. """
        graph = CircuitGraph()

        # Node doesn't exist, should return 0 (defaultdict behavior)
        assert graph.get_node_degree("nonexistent") == 0

    def test_coupling_capacitor_handling(self):
        """ Test that coupling capacitors are treated like regular capacitors. """
        subckt = make_subcircuit(
            name="test",
            ports=["A", "B", "VSS"],
            elements=[CouplingCapacitor(name="cc1", node1="A", node2="B", value=1e-15)]
        )

        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)

        # Coupling cap uses node1 and node2 for primary connection
        assert "a" in graph.all_nodes
        assert "b" in graph.all_nodes
        assert "b" in graph.capacitive_adj["a"]
        assert "a" in graph.capacitive_adj["b"]

    def test_complex_circuit(self):
        """ Test a more complex circuit topology. """
        # Circuit:
        #     A ---R1--- B ---R2--- C
        #     |         |         |
        #    C1        R3        C2
        #     |         |         |
        #    VSS       VSS       VSS
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
        assert graph.get_node_degree("B") == 3  # R1, R2, R3
        assert graph.get_node_degree("A") == 1  # R1
        assert graph.get_node_degree("C") == 1  # R2

        # With capacitors
        assert graph.get_node_degree("A", include_capacitors=True) == 2  # R1 + C1
        assert graph.get_node_degree("C", include_capacitors=True) == 2  # R2 + C2
