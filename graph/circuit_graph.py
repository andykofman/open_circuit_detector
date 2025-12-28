"""
Graph representation of the circuit connectivity analysis.

This module models a SPICE circuit as a graph to detect open circuits:
- Nodes = circuit nodes (e.g., "A", "B", "VSS")
- Edges = resistors (they conduct DC current)
- Capacitors are tracked separately (they block DC, only conduct AC)
Key Concepts:
        - Resistors create DC paths between nodes (graph edges)
        - Capacitors block DC (tracked separately for AC analysis) # for completeness only
        - Ground nodes (VSS, GND, 0) are the reference point
        - All non-ground nodes should have a resistive path to ground
    
Our Detection Strategy:
1. Build adjacency lists for resistive and capacitive connections
2. Use DFS to find connected components (groups of nodes connected via resistors)
3. Check if all nodes have a path to ground (VSS) through resistors
4. Identify isolated "islands" that cannot reach the rest of the circuit
"""

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from parser.element_types import Element, ElementType, Subcircuit


class CircuitGraph:
    """
    Graph representation of an RC circuit for connectivity analysis.


    Attributes:
        resistive_adj: Adjacency list for resistor connections
                       {node_name: {neighbor1, neighbor2, ...}}
        capacitive_adj: Adjacency list for capacitor connections
        all_nodes: Set of all node names in the circuit
        port_nodes: Set of port node names (external connections)
        ground_nodes: Set of known ground reference names
        elements: Dictionary mapping element names to Element objects
    """

    def __init__(self):
        # Adjacency list for resistive connections
        # Example: resistive_adj["A"] = {"B", "VSS"} means node A is connected to 
        # nodes B and VSS through resistors
        self.resistive_adj: Dict[str, Set[str]] = defaultdict(set)

        # Adjacency list for capacitive connections
        # Used for AC analysis or detecting cap-only connections
        self.capacitive_adj: Dict[str, Set[str]] = defaultdict(set)

        # Set of all node names encountered in the circuit (lowercase)
        self.all_nodes: Set[str] = set()

        # Set of port node names (external connections to subcircuit)
        self.port_nodes: Set[str] = set()

        # Known ground/reference node names (case-insensitive) --> note that all node names are stored in lowercase
        self.ground_nodes: Set[str] = {'0', 'gnd', 'vss', 'ground'}

        # Dictionary for element lookup: {element_name: Element object}
        self.elements: Dict[str, Element] = {}


    def build_from_subcircuit(self, subckt: Subcircuit) -> None:
        """
        Take a parsed subcircuit and build our graph from it.
        
        Goes through each R and C, adds edges to the adjacency lists.

        Args:
            subckt: The Subcircuit object containing elements and ports
        Returns:
            None, modifies the graph in place.
        """
        # Grab the port names (lowercase for easy comparison)
        self.port_nodes = set(p.lower() for p in subckt.ports)

        # Loop through every element
        for element in subckt.elements:
            # Make everything lowercase so "VSS" == "vss" == "Vss"
            node1 = element.node1.lower()
            node2 = element.node2.lower()

            # Remember these nodes exist
            self.all_nodes.add(node1)
            self.all_nodes.add(node2)
            
            # Save the element for later
            self.elements[element.name] = element

            # For Resistor Add to resistive graph (both directions since it's bidirectional)
            if element.element_type == ElementType.RESISTOR:
                self.resistive_adj[node1].add(node2)
                self.resistive_adj[node2].add(node1)
            
            # For Capacitor Add to capacitive graph (won't help DC but good to track)
            elif element.element_type == ElementType.CAPACITOR:
                self.capacitive_adj[node1].add(node2)
                self.capacitive_adj[node2].add(node1)


    def get_resistive_connected_component(self, start_node: str) -> Set[str]:
        """
        Starting from one node, find ALL nodes you can reach via resistors.
        
        Uses DFS (stack-based). Returns the set of reachable nodes.

        Args:
            start_node: The node to start the search from (case insensitive)
        Returns:
            A set of node names reachable from start_node via resistors.
        """
        visited = set()
        stack = [start_node.lower()]

        # Keep going until we've explored everything reachable
        while stack:
            node = stack.pop()
            
            # If Already been here, Skip
            if node in visited:
                continue
            
            # Mark as visited
            visited.add(node)

            # Add neighbors we haven't seen yet
            for neighbor in self.resistive_adj[node]:
                if neighbor not in visited:
                    stack.append(neighbor)
        
        return visited

    
    def get_all_connected_components(self) -> List[Set[str]]:
        """
        Split the whole circuit into groups of connected nodes.
        
        Technically, if you get more than one group, something is probably wrong
        (isolated islands that can't reach ground).

        Args:
            None, it uses the whole graph stored in self.all_nodes
        Returns:
            A list of sets, each set is a connected component of nodes.
        """
        visited = set()
        components = []

        # Go through every node
        for node in self.all_nodes:
            # Haven't processed this one yet?
            if node not in visited:
                # Find its whole group
                component = self.get_resistive_connected_component(node)
                components.append(component)
                
                # Mark the whole group as done
                visited.update(component)
        
        return components


    def has_ground_connection(self, node: str) -> bool:
        """
        check if this node can reach ground (VSS) through resistors
        
        Args:
            node: The node to check for a ground connection (case insensitive)
        Returns:
            True if the node can reach ground, False if it's floating/isolated.
        """
        # Get everything connected to this node
        component = self.get_resistive_connected_component(node)
        
        # Check if any ground node is in there
        # The & operator finds the intersection of two sets
        return bool(component & self.ground_nodes)


    def get_node_degree(self, node: str, include_capacitors: bool = False) -> int:
        """
        How many elements are connected to this node?
        
        Degree 0 = floating (bad!)
        Degree 1 = leaf node
        Degree 2+ = internal node
        """
        node_lower = node.lower()
        
        # Count resistor connections
        degree = len(self.resistive_adj[node_lower])
        # Example: resistive_adj["b"] = {"a", "c", "d"} → len = 3

        # Optionally count capacitor connections too
        if include_capacitors:
            degree += len(self.capacitive_adj[node_lower])
                # Example: capacitive_adj["b"] = {"vss"} → len = 1
                # Total: 3 + 1 = 4
        return degree