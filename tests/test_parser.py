""" UNIT test for the parser module. """

import pytest
import warnings
from parser.spice_parser import SpiceParser, SpiceParserError
from parser.element_types import ElementType, Resistor, Capacitor, CouplingCapacitor, Subcircuit

class TestSpiceParser:
    """ UNIT tests for the SpiceParser class. """

    def test_parse_simple_resistor(self):
        """ Test parsing a simple resistor element. """
        parser = SpiceParser()
        lines = [

            ".subckt test 1 2",
            "r1 1 2 100",
            ".ends"

        ]

        result = parser.parse_lines(lines)

        assert "test" in result
        assert len(result["test"].elements) == 1
        assert result["test"].elements[0].element_type == ElementType.RESISTOR
        assert result["test"].elements[0].value == 100.0


    def test_parse_value_with_suffix(self):
        """ Test parsing values with unit suffix"""
        parser = SpiceParser()
        
        assert parser._parse_value("1f") == 1e-15
        assert parser._parse_value("1p") == 1e-12
        assert parser._parse_value("1n") == 1e-9
        assert parser._parse_value("1k") == 1e3
        assert parser._parse_value("0.00538176f") == pytest.approx(5.38176e-18)

    
    def test_continuation_lines(self):
        """ Test parsing lines with + continuation"""
        parser = SpiceParser()
        lines = [
            ".subckt test 1 2 3",
            "+ 4 5 6",
            "r1 1 2 100",
            ".ends"
        ]

        result = parser.parse_lines(lines)
        assert len(result["test"].ports) == 6
        assert "6" in result["test"].ports

    def test_parse_capacitor_to_gnd(self):
        """ Test parsing capacitor to VSS """
        parser = SpiceParser()
        lines = [
            ".subckt test 1 VSS",
            "c1 1 VSS 0.00538176f",
            ".ends"
        ]
        result = parser.parse_lines(lines)
        
        assert len(result["test"].elements) == 1
        assert result["test"].elements[0].element_type == ElementType.CAPACITOR
        assert result["test"].elements[0].node2 == "VSS"

    def test_skip_lines(self): 
        """ Test the comment lines are skipped"""
        parser = SpiceParser()
        lines = [
            "* This is a comment",
            ".subckt test 1 2",
            "* Another comment",
            "r1 1 2 100",
            ".ends"
        ]
        result = parser.parse_lines(lines)
        
        assert len(result["test"].elements) == 1

    def test_missing_end_statement(self):
        """
        Test handling of missing .ends statement

        """
        parser = SpiceParser()
        lines = [
            ".subckt test 1 2 VSS",
            "c1 1 VSS 1f",
            "r1 1 2 100",
            # NOTE: No .ends statement (like in netlist 1.txt)
        ]

        # should warn but not crash

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parser.parse_lines(lines)

            # Check warning was issued
            assert len(w) == 1

            assert ".ends" in str(w[0].message).lower()

        # Sub-circuit should still be parsed
        assert "test" in result
        assert len(result["test"].elements) == 2

    def test_coupling_capacitor(self):
        """ Test parsing coupling cap (cc_XX elements)""" 
        parser = SpiceParser()
        lines = [
            ".subckt test 1 2 3",
            "cc_1 1 2 3.26013f",
            "cc_2 2 3 5.1f",
            ".ends"
        ]
        result = parser.parse_lines(lines)
        
        assert len(result["test"].elements) == 2
        # Coupling capacitors should be correctly parsed as COUPLING_CAPACITOR type
        assert all(e.element_type == ElementType.COUPLING_CAPACITOR for e in result["test"].elements)
