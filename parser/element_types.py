""" Data classes for SPICE element types. """

from dataclasses import dataclass
from typing import Optional
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
class Subcircuit(Element):
    """ Class for subcircuit elements. """
    name: str
    ports: list[str]
    elements: list[Element]
    internal_nodes: set[str]