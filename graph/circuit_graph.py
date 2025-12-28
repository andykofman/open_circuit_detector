"""
Graph representation of the circuit connectivity analysis.

This module models a SPICE circuit as a graph to detect open circuits:
- Nodes = circuit nodes (e.g., "A", "B", "VSS")
- Edges = resistors (they conduct DC current)
- Capacitors are tracked separately (they block DC, only conduct AC)

Our Detection Strategy:
1. Build adjacency lists for resistive and capacitive connections
2. Use DFS to find connected components (groups of nodes connected via resistors)
3. Check if all nodes have a path to ground (VSS) through resistors
4. Identify isolated "islands" that cannot reach the rest of the circuit
"""

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from ..parser.element_types import Element, ElementType, Resistor, Capacitor, CouplingCapacitor, Subcircuit


class CircuitGraph:
    """
    Graph representation of an RC circuit for connectivity analysis.

    Key Concepts:
        - Resistors create DC paths between nodes (graph edges)
        - Capacitors block DC (tracked separately for AC analysis) # for completeness only
        - Ground nodes (VSS, GND, 0) are the reference point
        - All non-ground nodes should have a resistive path to ground
    
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

        # Known ground/reference node names (case-insensitive)
        self.ground_nodes: Set[str] = {'0', 'gnd', 'vss', 'ground'}

        # Dictionary for element lookup: {element_name: Element object}
        self.elements: Dict[str, Element] = {}

