"""Unit tests for the SpiceParser module."""

import pytest
import warnings
from parser.spice_parser import SpiceParser, SpiceParserError
from parser.element_types import ElementType, Resistor, Capacitor, CouplingCapacitor, Subcircuit


class TestSpiceParser:
    """Unit tests for the SpiceParser class."""

    # ==================== Element Parsing Tests ====================

    def test_parse_simple_resistor(self):
        """
        Test parsing a simple resistor element.
        
        Scenario: Subcircuit with single resistor r1 between nodes 1 and 2.
        Expected: Element parsed as RESISTOR with value 100.0
        """
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

    def test_parse_capacitor_to_gnd(self):
        """
        Test parsing capacitor connected to VSS.
        
        Scenario: Capacitor c1 from node 1 to VSS with femtofarad value.
        Expected: Element parsed as CAPACITOR with correct node2 = "VSS"
        """
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

    def test_coupling_capacitor(self):
        """
        Test parsing coupling capacitor (cc_XX elements).
        
        Scenario: Two coupling caps cc_1 and cc_2 in subcircuit.
        Expected: Both parsed as COUPLING_CAPACITOR type (not regular CAPACITOR).
        
        This tests the critical regex order fix - cc_* must be checked before c*.
        """
        parser = SpiceParser()
        lines = [
            ".subckt test 1 2 3",
            "cc_1 1 2 3.26013f",
            "cc_2 2 3 5.1f",
            ".ends"
        ]
        result = parser.parse_lines(lines)

        assert len(result["test"].elements) == 2
        assert all(e.element_type == ElementType.COUPLING_CAPACITOR for e in result["test"].elements)

    # ==================== Value Parsing Tests ====================

    def test_parse_value_with_suffix(self):
        """
        Test parsing values with engineering unit suffixes.
        
        Scenario: Various suffix formats (f, p, n, k) and decimal values.
        Expected: Correct float conversion with proper scaling.
        """
        parser = SpiceParser()

        assert parser._parse_value("1f") == 1e-15
        assert parser._parse_value("1p") == 1e-12
        assert parser._parse_value("1n") == 1e-9
        assert parser._parse_value("1k") == 1e3
        assert parser._parse_value("0.00538176f") == pytest.approx(5.38176e-18)

    # ==================== Line Handling Tests ====================

    def test_continuation_lines(self):
        """
        Test parsing lines with + continuation character.
        
        Scenario: Subcircuit port list split across two lines with +.
        Expected: All 6 ports correctly joined and parsed.
        """
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

    def test_skip_comment_lines(self):
        """
        Test that comment lines (starting with *) are skipped.
        
        Scenario: Comments before subcircuit and inside subcircuit.
        Expected: Only the resistor element is parsed, comments ignored.
        """
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

    # ==================== Error Handling Tests ====================

    def test_missing_end_statement(self):
        """
        Test handling of missing .ends statement.
        
        Scenario: Subcircuit without .ends terminator (like some real netlists).
        Expected: Warning issued but parsing completes successfully.
        """
        parser = SpiceParser()
        lines = [
            ".subckt test 1 2 VSS",
            "c1 1 VSS 1f",
            "r1 1 2 100",
            # NOTE: No .ends statement
        ]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parser.parse_lines(lines)

            # Check warning was issued
            assert len(w) == 1
            assert ".ends" in str(w[0].message).lower()

        # Subcircuit should still be parsed
        assert "test" in result
        assert len(result["test"].elements) == 2
