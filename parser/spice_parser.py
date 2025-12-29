""" SPICE netlist parser. """

import re
from typing import List, Dict, Optional, Dict
from .element_types import Element, Resistor, Capacitor, CouplingCapacitor, Subcircuit, ElementType, SubcircuitInstance, TopLevelNetlist


class SpiceParserError(Exception):
    """ Custom errors exception for the current SPICE parser. """
    pass


class SpiceParser:
    """ 
    Parser for Spice netlists for parsing elements and subcircuits. 
    The parser reads a SPICE netlist file and extracts elements and subcircuits.

    The flow is as follows:
    1. Read the netlist file line by line.
    2. Identify and parse elements (resistors, capacitors, coupling capacitors).
    3. Identify and parse subcircuits, including their ports and internal elements.
    


    ### might add more details later ()
    """

    ## Regex patterns for parsing different elements
    # 1- Subcircuit  pattern
    r"""
    For the start of the string, skip the dot character, then match 'subckt' (case insensitive) followed by one or more whitespace characters.
    Next, capture the subcircuit name as a sequence of non-whitespace characters (\S+) --> that will be group 1.
    After that, capture the rest of the line (.+) as the ports of the subcircuit --> that will be group 2.
    """
    # 1.1 Subcircuit start pattern

    SUBCKT_START_PATTERN = re.compile(
        r'^\.subckt\s+(\S+)\s+(.+)$',
        re.IGNORECASE
    )

    # 1.2 Subcircuit end pattern
    SUBCKT_END_PATTERN = re.compile(
        r'^\.ends$', 
        re.IGNORECASE)

    #  2- Continuation line pattern
    CONTINUATION_PATTERN = re.compile(r'^\+\s*(.+)$')   # Matches lines starting with '+' followed by any characters

    # 3- Resistor pattern
    RESISTOR_PATTERN = re.compile(
        r'^(r\w*)\s+(\S+)\s+(\S+)\s+(\S+)',
        re.IGNORECASE
    )

    # 4- Capacitor pattern (regular capacitors, e.g., c82, c83)
    CAPACITOR_PATTERN = re.compile(
        r'^(c\w*)\s+(\S+)\s+(\S+)\s+(\S+)',
        re.IGNORECASE
    )

    # 5- Coupling capacitor pattern (e.g., cc_1, cc_84)
    COUPLING_CAP_PATTERN = re.compile(
        r'^(cc\w*)\s+(\S+)\s+(\S+)\s+(\S+)',
        re.IGNORECASE
    )

    # 6- Subcircuit instance pattern (e.g., x0 port1 port2 port3 PM_CMOM1%P)
    # The instance name starts with 'x', followed by the instance ID
    # Then one or more nodes, and finally the subcircuit type name
    # Using \S* instead of \w* to match special characters like % in names
    SUBCKT_INSTANCE_PATTERN = re.compile(
        r'^x(\S*)\s+(.+)$',
        re.IGNORECASE
    )

    # 7- Comment pattern
    COMMENT_PATTERN = re.compile(r'^\*.*$')  # Matches lines starting with '*'


    def __init__(self):
        self.subcircuits: Dict[str, Subcircuit] = {}
        self.curren_subckt: Optional[str] = None
        self.elements: List[Element] = []
        self.ports: List[str] = []
        self.top_level_elements: List[Element] = []
        self.instances: List[SubcircuitInstance] = []

    def parse_file(self, filepath: str) -> Dict[str, Subcircuit]:
        """ Parse a SPICE netlist using the provided file path. 
        Args:
            filepath (str): Path to the SPICE netlist file.
        Returns:
            Dict[str, Subcircuit]: A dictionary of parsed subcircuits.
        """

        with open(filepath, 'r') as file:
            lines = file.readlines()

        return self.parse_lines(lines)
    

    def parse_lines(self, lines: List[str]) -> Dict[str, Subcircuit]:
        """ Parse a list of lines from a SPICE netlist.
        Args:
            lines (List[str]): List of lines from the SPICE netlist.
        Returns:
            Dict[str, Subcircuit]: A dictionary of parsed subcircuits.
        """

        # First loop: join continuation lines
        joined_lines =  self._join_continuation_lines(lines)

        # Second loop: parse elements and subcircuits
        for line_num, line in enumerate(joined_lines, start=1):
            try:
                self._parse_line(line.strip())
            except Exception as e:
                raise SpiceParserError(f"Error parsing line {line_num}: {line}\n{e}")   

        # If we were in a subcircuit, make sure it terminated properly
        if self.curren_subckt is not None:
            import warnings
            warnings.warn(
                f"Subcircuit '{self.curren_subckt}' not properly terminated with .ends statement. Auto-terminating."
            )
            self._end_subcircuit()

        return self.subcircuits
    
    def parse_file_complete(self, filepath: str) -> TopLevelNetlist:
        """ Parse a complete SPICE netlist including top-level elements and instances.
        
        This method parses:
        - Subcircuit definitions (.subckt ... .ends)
        - Top-level elements (capacitors, resistors outside subcircuits)
        - Subcircuit instantiations (x lines)
        
        Args:
            filepath (str): Path to the SPICE netlist file.
        Returns:
            TopLevelNetlist: Complete netlist with subcircuits, instances, and top-level elements.
        """
        with open(filepath, 'r') as file:
            lines = file.readlines()
        return self.parse_lines_complete(lines)
    
    def parse_lines_complete(self, lines: List[str]) -> TopLevelNetlist:
        """ Parse a complete netlist including top-level elements and instances.
        
        Args:
            lines (List[str]): List of lines from the SPICE netlist.
        Returns:
            TopLevelNetlist: Complete netlist with subcircuits, instances, and top-level elements.
        """
        # Reset state for complete parsing
        self.top_level_elements = []
        self.instances = []
        
        # First, join continuation lines
        joined_lines = self._join_continuation_lines(lines)
        
        # Parse all lines
        for line_num, line in enumerate(joined_lines, start=1):
            try:
                self._parse_line_complete(line.strip())
            except Exception as e:
                raise SpiceParserError(f"Error parsing line {line_num}: {line}\n{e}")
        
        # If we were in a subcircuit, make sure it terminated properly
        if self.curren_subckt is not None:
            import warnings
            warnings.warn(
                f"Subcircuit '{self.curren_subckt}' not properly terminated with .ends statement. Auto-terminating."
            )
            self._end_subcircuit()
        
        return TopLevelNetlist(
            subcircuits=self.subcircuits,
            instances=self.instances,
            top_level_elements=self.top_level_elements
        )
    
    def _parse_line_complete(self, line: str):
        """ Parse a single line, handling both subcircuit content and top-level elements.
        
        Args:
            line (str): A single line from the SPICE netlist.
        """
        if not line:
            return
        
        # Check for subcircuit start
        subckt_start_match = self.SUBCKT_START_PATTERN.match(line)
        if subckt_start_match:
            self._start_subcircuit(subckt_start_match)
            return
        
        # Check for subcircuit end
        if self.SUBCKT_END_PATTERN.match(line):
            self._end_subcircuit()
            return
        
        # If inside a subcircuit, parse as subcircuit element
        if self.curren_subckt is not None:
            self._parse_element(line)
        else:
            # At top level - could be an instance or top-level element
            self._parse_top_level_line(line)
    
    def _parse_top_level_line(self, line: str):
        """ Parse a line at the top level (outside any subcircuit).
        
        Args:
            line (str): A single line from the SPICE netlist.
        """
        # Check for subcircuit instance first (x lines)
        instance_match = self.SUBCKT_INSTANCE_PATTERN.match(line)
        if instance_match:
            instance = self._parse_instance(instance_match)
            if instance:
                self.instances.append(instance)
            return
        
        # Check for coupling capacitor (check BEFORE regular capacitor)
        coupling_cap_match = self.COUPLING_CAP_PATTERN.match(line)
        if coupling_cap_match:
            name = coupling_cap_match.group(1)
            node1 = coupling_cap_match.group(2)
            node2 = coupling_cap_match.group(3)
            value = self._parse_value(coupling_cap_match.group(4))
            coupling_capacitor = CouplingCapacitor(name, node1, node2, value)
            self.top_level_elements.append(coupling_capacitor)
            return
        
        # Check for regular capacitor
        capacitor_match = self.CAPACITOR_PATTERN.match(line)
        if capacitor_match:
            name = capacitor_match.group(1)
            node1 = capacitor_match.group(2)
            node2 = capacitor_match.group(3)
            value = self._parse_value(capacitor_match.group(4))
            capacitor = Capacitor(name, node1, node2, value)
            self.top_level_elements.append(capacitor)
            return
        
        # Check for resistor
        resistor_match = self.RESISTOR_PATTERN.match(line)
        if resistor_match:
            name = resistor_match.group(1)
            node1 = resistor_match.group(2)
            node2 = resistor_match.group(3)
            value = self._parse_value(resistor_match.group(4))
            resistor = Resistor(name, node1, node2, value)
            self.top_level_elements.append(resistor)
            return
        
        # Ignore other top-level lines (comments already filtered, could be .option, etc.)
        # Don't raise error for unknown top-level lines
    
    def _parse_instance(self, match: re.Match) -> Optional[SubcircuitInstance]:
        """ Parse a subcircuit instance line.
        
        Format: x<instance_name> <node1> <node2> ... <nodeN> <subcircuit_type>
        Example: x0 port1 port2 port3 PM_CMOM1%P
        
        Args:
            match (re.Match): Match object from SUBCKT_INSTANCE_PATTERN
        Returns:
            SubcircuitInstance or None if invalid
        """
        instance_name = match.group(1)
        rest = match.group(2).split()
        
        if len(rest) < 2:
            # Need at least one connection and the subcircuit type
            return None
        
        # Last token is the subcircuit type, rest are connections
        subcircuit_type = rest[-1]
        connections = rest[:-1]
        
        return SubcircuitInstance(
            instance_name=instance_name,
            subcircuit_type=subcircuit_type,
            connections=connections
        )

    def _join_continuation_lines(self, lines: List[str]) -> List[str]:
        """ Join continuation lines in the SPICE netlist.
        Args:
            lines (List[str]): List of lines from the SPICE netlist.
        Returns:
            List[str]: List of lines with continuation lines joined.
        """
        result = []
        current_line = "" # Holds the current line being built and accumulates it

        for line in lines:
            line = line.strip()
            if not line:
                continue  # Skip empty lines
            if self.COMMENT_PATTERN.match(line):
                continue  # Skip comment lines

            cont_match = self.CONTINUATION_PATTERN.match(line)  # Check for continuation line
            
            if cont_match:
                # It's a continuation line (starts with +)
                # Add its content (excluding +) to current_line
                current_line += " " + cont_match.group(1).strip()
            else:
                # It's a new line (not continuation)
                # Save the previous current_line to result (if it exists)
                if current_line:
                    result.append(current_line)
                # Start building a new line
                current_line = line
            
        if current_line:
                result.append(current_line)

        return result

    def _parse_line(self, line: str):
        """ Parse a single line from the SPICE netlist.
        Args:
            line (str): A single line from the SPICE netlist.
        """

        # check for the empty line
        if not line:
            return  # Skip empty lines

        # Check for subcircuit start
        subckt_start_match = self.SUBCKT_START_PATTERN.match(line)
        # if found, start a new subcircuit
        if subckt_start_match:
            self._start_subcircuit(subckt_start_match)
            return  
        
        # Check for subcircuit end
        if self.SUBCKT_END_PATTERN.match(line):
            self._end_subcircuit()
            return

        # Parse elements (only if inside a subcircuit)
        if self.curren_subckt is not None:
            self._parse_element(line)
        # else: ignore elements outside subcircuits
        # might add a warning here in the future

    def _start_subcircuit(self, match: re.Match):
        """ Start a new subcircuit.
        Args:
            match (re.Match): Match object from the subcircuit start regex.
        """
        subckt_name = match.group(1)
        ports_str = match.group(2)
        self.ports = ports_str.split()
        self.curren_subckt = subckt_name
        self.elements = []

    def _end_subcircuit(self):
        """ End the current subcircuit and save it. """
        # check if we are in a subcircuit
        if self.curren_subckt is None:
            raise SpiceParserError("No subcircuit to end.")
        if self.curren_subckt:
            # First find all nodes used in the subcircuit
            all_nodes = set()
            for element in self.elements:
                # Add its two nodes to the set of all nodes
                # Can be generalized but kept simple for the current RC circuit we have
                all_nodes.add(element.node1)    
                all_nodes.add(element.node2)
    
            # # Internal nodes are all nodes minus the ports (those not in ports)
            port_set = set(self.ports)
            internal_nodes = all_nodes - port_set

            # Create the Subcircuit object
            self.subcircuits[self.curren_subckt] = Subcircuit(
                name=self.curren_subckt,
                ports=self.ports,  
                elements=self.elements,
                internal_nodes=internal_nodes
            )
        self.curren_subckt = None
        self.elements = []
        self.ports = []

    def _parse_element(self, line: str) -> None:
        """ Parse an element line and add it to the current subcircuit.

        name: the name of the element (e.g., r1, c2, cc_1)
        node1: the first node of the element
        node2: the second node of the element
        value: the value of the element (e.g., resistance in ohms, capacitance in femto/atto farads)
        
        Args:
            line (str): A single line from the SPICE netlist.
        Returns:
            None as the element is added to the current subcircuit.
        """

        # Check for resistor
        resistor_match = self.RESISTOR_PATTERN.match(line)
        if resistor_match:
            name = resistor_match.group(1)
            node1 = resistor_match.group(2)
            node2 = resistor_match.group(3)
            value = self._parse_value(resistor_match.group(4))
            resistor = Resistor(name, node1, node2, value)
            self.elements.append(resistor)
            return

        # IMPORTANT: Check for coupling capacitor BEFORE regular capacitor
        # because 'cc_*' would otherwise match the general 'c\w*' pattern
        coupling_cap_match = self.COUPLING_CAP_PATTERN.match(line)
        if coupling_cap_match:
            name = coupling_cap_match.group(1)
            node1 = coupling_cap_match.group(2)
            node2 = coupling_cap_match.group(3)
            value = self._parse_value(coupling_cap_match.group(4))
            coupling_capacitor = CouplingCapacitor(name, node1, node2, value)
            self.elements.append(coupling_capacitor)
            return

        # Check for regular capacitor (after coupling capacitor)
        capacitor_match = self.CAPACITOR_PATTERN.match(line)
        if capacitor_match:
            name = capacitor_match.group(1)
            node1 = capacitor_match.group(2)
            node2 = capacitor_match.group(3)
            value = self._parse_value(capacitor_match.group(4))
            capacitor = Capacitor(name, node1, node2, value)
            self.elements.append(capacitor)
            return

        # If we reach here, the line did not match any known element
        raise SpiceParserError(f"Unknown element format: {line}")
        
        return None

    def _parse_value(self, value_str: str) -> float:
        """ Parse a value string with possible suffixes into a float.
        Args:
            value_str (str): Value string with possible suffixes (e.g., '10f', '1k').
        Returns:
            float: Parsed value as a float.
        """
        suffixes = {
            'a': 1e-18,   # attofarad
            'f': 1e-15,   # femtofarad
            'p': 1e-12,   # picofarad
            'n': 1e-9,    # nanofarad
            'u': 1e-6,    # microfarad
            'm': 1e-3,    # millifarad/milliohm
            'k': 1e3,     # kilo
            'meg': 1e6,   # mega (must check before 'm')
            'g': 1e9,     # giga
            't': 1e12,    # tera
        }

        # Match number followed by optional suffix
        # Order matters: check 'meg' before single letters
        match = re.match(r'([0-9.]+)(meg|[afpnumkgt])?', value_str, re.IGNORECASE)
        if not match:
            raise SpiceParserError(f"Invalid value format: {value_str}")

        base_value = float(match.group(1))
        suffix = match.group(2).lower() if match.group(2) else ''

        if suffix and suffix in suffixes:
            return base_value * suffixes[suffix]
        else:
            return base_value
