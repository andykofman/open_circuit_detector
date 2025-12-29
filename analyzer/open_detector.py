"""
Open circuit detection algorithms.

"""
from typing import List, Dict, Set, Optional, NamedTuple
from enum import Enum

from graph.circuit_graph import CircuitGraph
from parser.element_types import Subcircuit

class OpenType(Enum):
    """
    Types of open circuit conditions.
    
    FLOATING_NODE: Node with zero connections (truly isolated)
        Example: .subckt test A B VSS
                 r1 A VSS 100
                 .ends
        Node B exists in ports but has NO elements connected to it.
        r_degree = 0, c_degree = 0
        
    ISOLATED_COMPONENT: Disconnected subnetwork (island) with no ground path
        Example: A --R1-- B    and    C --R2-- VSS
        {A, B} form one component, {C, VSS} form another.
        The {A, B} component is isolated - no path to ground.
        
    FLOATING_PORT: Port declared in .subckt but unused internally
        Example: .subckt test A B VSS
                 r1 A VSS 100
                 .ends
        Port B is declared but no element connects to it inside.
        
    CAPACITOR_ONLY: Node connected ONLY via capacitors (no resistors)
        Example: A --C1-- B --C2-- VSS
        Node A has capacitor connections (c_degree > 0) but 
        no resistor connections (r_degree = 0). Blocks DC.
        
    DC_FLOATING_NODE: Node with only capacitive connections and no DC path to ground
        Example: A --CC1-- N --CC2-- B, where N has no resistive path to ground
        Node N may have many capacitive connections (c_degree > 0) but
        if there's no resistive path from N to any ground node (0, VSS, etc.),
        it's DC-floating. This is the key open circuit type for finding nodes
        connected through coupling capacitors at the top level.


        More information about each type will be provided in the docs/README.md file.
    """
    FLOATING_NODE = "floating_node"
    ISOLATED_COMPONENT = "isolated_component"
    FLOATING_PORT = "floating_port"
    CAPACITOR_ONLY = "capacitor_only"
    DC_FLOATING_NODE = "dc_floating_node"
    

class OpenCircuit(NamedTuple):
    """
    Represents an open circuit condition detected in the circuit graph.
    
    Attributes:
        node: The node name where the open condition is detected
        open_type: The type of open circuit condition (OpenType)
        description: Human-readable description of the issue
        affected_elements: List of element names affected by this open condition
        severity: Severity level (e.g., "warning", "error")

    """
    node: str
    open_type: OpenType
    description: str
    affected_elements: List[str] 
    severity: str  # e.g., "warning", "error"

class OpenCircuitDetector:
    """
    Detects open circuit conditions in SPICE netlists using CircuitGraph module.

  Uses CircuitGraph to identify the Open Circuit Types:
    1. FLOATING_NODE: Nodes with no connections at all
    2. ISOLATED_COMPONENT: Connected subnetworks without ground path
    3. FLOATING_PORT: Ports not used inside the subcircuit
    4. CAPACITOR_ONLY: Nodes with only capacitor connections
    
    Usage:
        graph = CircuitGraph()
        graph.build_from_subcircuit(subckt)
        detector = OpenCircuitDetector(graph)
        issues = detector.detect_all()
    """

    def __init__(self, graph: CircuitGraph):
        """
        Initialize detector with a built CircuitGraph.
        Args:
            graph: CircuitGraph already populated via build_from_subcircuit()
        
        """
        self.graph = graph
        self.issues: List[OpenCircuit] = []

    def detect_all(self) -> List[OpenCircuit]:
        """
        Run all detection algorithms and return found issues.

        Returns:
            List of OpenCircuit issues detected.
        """
        self.issues = []
        self._detect_floating_nodes()
        self._detect_isolated_components()
        self._detect_floating_ports()
        self._detect_capacitor_only_nodes()

        return self.issues

    def _detect_floating_nodes(self) -> None:
        """
        Detect nodes with zero connections (r_degree = 0 and c_degree = 0).

        These nodes that exist in all_nodes but have no elements connected.

        This can happen if a node is declared but not used.
        """

        for node in self.graph.all_nodes:
            if node in self.graph.ground_nodes:
                continue
            
            # Skip ports - they are handled by _detect_floating_ports()
            if node in self.graph.port_nodes:
                continue
                
            r_degree = len(self.graph.resistive_adj[node])
            c_degree = len(self.graph.capacitive_adj[node])
            
            if r_degree == 0 and c_degree == 0:
                self.issues.append(OpenCircuit(
                    node=node,
                    open_type=OpenType.FLOATING_NODE,
                    description=f"Node '{node}' has no connections",
                    affected_elements=[],
                    severity="critical"
                ))

    def _detect_isolated_components(self) -> None:
        """
        Detect groups of nodes that form islands without ground connection.

        uses get_all_resistive_connected_components() from CircuitGraph to find all resistive connected components
        then checks which components do not have a path to ground.
        """

        components = self.graph.get_all_connected_components()
        for component in components:
            # check if any node in this component can reach ground
            has_ground = bool(component & self.graph.ground_nodes)

            if not has_ground and len(component)> 0:
                # Filter out single floating nodes (handled separately by _detect_floating_nodes)
                # Only report if nodes have connections but no ground path (isolated island not orphan)

                nodes_with_connections = [
                    n for n in component 
                    if len(self.graph.resistive_adj[n]) > 0 or len(self.graph.capacitive_adj[n]) > 0
                ]
                
                # Skip components where ALL nodes are capacitor-only (no resistive connections)
                # These are handled by _detect_capacitor_only_nodes()
                nodes_with_resistive = [
                    n for n in component
                    if len(self.graph.resistive_adj[n]) > 0
                ]

                # Only report if there are nodes with resistive connections in this component
                if len(nodes_with_resistive) > 0:
                    # Prepare a description
                    nodes_str = ", ".join(sorted(component)[:5])
                    # Truncate if too long
                    if len(component) > 5:
                        nodes_str += f"... (+{len(component) - 5} more)"

                    self.issues.append(OpenCircuit(
                        node=nodes_str,
                        open_type=OpenType.ISOLATED_COMPONENT,
                        description=f"Isolated component with {len(component)} nodes has no ground path",
                        affected_elements=self._get_elements_in_component(component),
                        severity="critical"
                    ))

    def _detect_floating_ports(self) -> None:
        """
        Detect ports declared in the subcircuit but not used internally.

        a PORT sould be connected to at least one element inside the subcircuit.
        """

        for port in self.graph.port_nodes:
            # skip ground ports
            if port in self.graph.ground_nodes:
                continue
            r_degree = len(self.graph.resistive_adj[port])
            c_degree = len(self.graph.capacitive_adj[port])

            if r_degree == 0 and c_degree == 0:
                self.issues.append(OpenCircuit(
                    node=port,
                    open_type=OpenType.FLOATING_PORT,
                    description=f"Port '{port}' is declared but not used inside the subcircuit",
                    affected_elements=[],
                    severity="warning"
                ))

    def _detect_capacitor_only_nodes(self) -> None:
        """
        Detect nodes connected only via capacitors (no resistors).
        
        These nodes have no DC path - capacitors block DC current.
        May be intentional (AC coupling) but worth flagging.
        """

        for node in self.graph.all_nodes:
            if node in self.graph.ground_nodes:
                continue
                
            if node in self.graph.port_nodes:
                continue # Ports with only caps might be intentional
                

            r_degree = len(self.graph.resistive_adj[node])
            c_degree = len(self.graph.capacitive_adj[node])

            if r_degree == 0 and c_degree > 0:
                self.issues.append(OpenCircuit(
                    node=node,
                    open_type=OpenType.CAPACITOR_ONLY,
                    description=f"Node '{node}' is connected only via capacitors (no DC path)",
                    affected_elements=self._get_connected_elements(node),
                    severity="warning"
                ))

    def _get_connected_elements(self, node: str) -> List[str]:
        """
        Get names of all elements connected to a given node.
        
        Args:
            node: The node name to query
        Returns:
            List of element names connected to this node.
        """
        connected = []
        for name, element in self.graph.elements.items():
            if element.node1.lower() == node or element.node2.lower() == node:
                connected.append(name)
        return connected

    def _get_elements_in_component(self, component: Set[str]) -> List[str]:
        """
        Get all element names that connect nodes within the given component.
        
        Args:
            component: Set of node names in the component
        Returns:
            List of element names connecting these nodes.
        """
        elements = []
        for name, element in self.graph.elements.items():
            node1 = element.node1.lower()
            node2 = element.node2.lower()
            if node1 in component or node2 in component:
                elements.append(name)
        return elements

    def detect_all_flattened(self) -> List[OpenCircuit]:
        """
        Run all detection algorithms including DC-floating node detection for flattened netlists.
        
        This is designed for analyzing netlists that include top-level coupling capacitors
        connecting subcircuit ports to external nodes. The key detection is finding nodes
        that have capacitive connections but no resistive path to ground.
        
        Returns:
            List of OpenCircuit issues detected, including DC-floating nodes.
        """
        self.issues = []
        
        # Run standard detections
        self._detect_floating_nodes()
        self._detect_isolated_components()
        self._detect_floating_ports()
        # Skip _detect_capacitor_only_nodes() - DC_FLOATING covers this case
        
        # Run DC-floating node detection (the key one for the planted bug)
        self._detect_dc_floating_nodes()
        
        return self.issues
    
    def _detect_dc_floating_nodes(self) -> None:
        """
        Detect nodes that have capacitive connections but no DC path to ground.
        
        A DC-floating node:
        - Has at least one capacitive connection (c_degree > 0)
        - Has no resistive path to any ground node (0, VSS, etc.)
        
        This is the key detection for finding the planted bug: a node connected
        through coupling capacitors at the top level with no resistive path to ground.
        
        The detection uses BFS to trace resistive paths from each node to ground.
        If no such path exists, the node is DC-floating.
        """
        for node in self.graph.all_nodes:
            # Skip ground nodes
            if node in self.graph.ground_nodes:
                continue
            
            # Get node degrees
            r_degree = self.graph.get_resistive_degree(node)
            c_degree = self.graph.get_capacitive_degree(node)
            
            # Only check nodes with capacitive connections
            if c_degree == 0:
                continue
            
            # Check if there's a resistive path to ground
            if not self._has_resistive_path_to_ground(node):
                self.issues.append(OpenCircuit(
                    node=node,
                    open_type=OpenType.DC_FLOATING_NODE,
                    description=f"Node '{node}' has {c_degree} capacitive connections but no DC path to ground (r_degree={r_degree})",
                    affected_elements=self._get_connected_elements(node),
                    severity="error"
                ))
    
    def _has_resistive_path_to_ground(self, start_node: str) -> bool:
        """
        Check if there's a resistive path from start_node to any ground node.
        
        Uses BFS traversing only through resistive connections (not capacitors).
        
        Args:
            start_node: The node to check
        Returns:
            True if there's a resistive path to ground, False otherwise.
        """
        from collections import deque
        
        visited = set()
        queue = deque([start_node.lower()])
        visited.add(start_node.lower())
        
        while queue:
            current = queue.popleft()
            
            # Check if we reached a ground node
            if current in self.graph.ground_nodes:
                return True
            
            # Explore resistive neighbors
            for neighbor in self.graph.get_resistive_neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return False