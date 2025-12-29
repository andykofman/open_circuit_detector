""" Data classes for SPICE element types. """

from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum

class ElementType(Enum):
    RESISTOR = "R"
    CAPACITOR = "C"
    COUPLING_CAPACITOR = "CC"
    # not found in the current netlist but included for completeness
    INDUCTOR = "L"          
    VOLTAGE_SOURCE = "V"
    CURRENT_SOURCE = "I" 

@dataclass
class Element:
    """ Base class for SPICE elements. """
    name: str
    node1: str
    node2: str
    value: Optional[float] = None
    element_type: ElementType = None

@dataclass
class Resistor(Element):
    """ Class for resistor elements. """
    def __init__(self, name: str, node1: str, node2: str, value: float):
        super().__init__(name, node1, node2, value, ElementType.RESISTOR)

@dataclass
class Capacitor(Element):
    """ Class for capacitor elements. """
    def __init__(self, name: str, node1: str, node2: str, value: float):
        super().__init__(name, node1, node2, value, ElementType.CAPACITOR)
@dataclass
class CouplingCapacitor(Element):
    """ Class for coupling capacitor elements. """
    def __init__(self, name: str, node1: str, node2: str, value: float):
        super().__init__(name, node1, node2, value, ElementType.COUPLING_CAPACITOR)
@dataclass
class Subcircuit:
    """ Class for subcircuit elements. """
    name: str
    ports: list[str]
    elements: list[Element]
    internal_nodes: set[str]


@dataclass
class SubcircuitInstance:
    """
    Represents an instantiation of a subcircuit (X line in SPICE).
    
    Format: x<instance_name> <node1> <node2> ... <nodeN> <subcircuit_type>
    Example: x0 port1 port2 port3 PM_CMOM1%P
    
    Attributes:
        instance_name: Name of this instance (e.g., "0" from "x0")
        subcircuit_type: Name of the subcircuit being instantiated (e.g., "PM_CMOM1%P")
        connections: List of nodes connected to the subcircuit ports in order
    """
    instance_name: str
    subcircuit_type: str
    connections: List[str]


@dataclass
class TopLevelNetlist:
    """
    Complete netlist with subcircuits, instances, and top-level elements.
    
    This represents the full hierarchical structure of a SPICE netlist:
    - subcircuits: Dictionary of subcircuit definitions
    - instances: List of subcircuit instantiations
    - top_level_elements: Elements defined outside any subcircuit (at top level)
    """
    subcircuits: Dict[str, Subcircuit]
    instances: List['SubcircuitInstance']
    top_level_elements: List[Element]