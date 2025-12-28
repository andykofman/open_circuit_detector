"""
Open circuit detection algorithms.

"""
from typing import List, Dict, Set, Optional
from dataclasses import dataclass

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
    """
    FLOATING_NODE = "floating_node"
    ISOLATED_COMPONENT = "isolated_component"
    FLOATING_PORT = "floating_port"
    CAPACITOR_ONLY = "capacitor_only"
    