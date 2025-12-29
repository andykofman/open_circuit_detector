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


class TestCompleteNetlistParsing:
    """Unit tests for parse_file_complete and parse_lines_complete methods."""

    # ==================== TopLevelNetlist Tests ====================

    def test_parse_lines_complete_returns_toplevelnetlist(self):
        """
        Test that parse_lines_complete returns a TopLevelNetlist object.
        
        Expected: Return type is TopLevelNetlist with correct attributes.
        """
        from parser.element_types import TopLevelNetlist
        
        parser = SpiceParser()
        lines = [
            ".subckt test A VSS",
            "r1 A VSS 100",
            ".ends"
        ]
        
        result = parser.parse_lines_complete(lines)
        
        assert isinstance(result, TopLevelNetlist)
        assert hasattr(result, 'subcircuits')
        assert hasattr(result, 'instances')
        assert hasattr(result, 'top_level_elements')

    def test_parse_lines_complete_parses_subcircuits(self):
        """
        Test that subcircuits are correctly parsed into TopLevelNetlist.
        
        Scenario: Single subcircuit with resistor.
        Expected: Subcircuit appears in subcircuits dict.
        """
        parser = SpiceParser()
        lines = [
            ".subckt mysub A B VSS",
            "r1 A B 100",
            "r2 B VSS 200",
            ".ends"
        ]
        
        result = parser.parse_lines_complete(lines)
        
        assert "mysub" in result.subcircuits
        assert len(result.subcircuits["mysub"].elements) == 2

    def test_parse_lines_complete_parses_top_level_elements(self):
        """
        Test parsing of elements outside subcircuits.
        
        Scenario: Coupling capacitors at top level after .ends.
        Expected: Elements appear in top_level_elements list.
        """
        parser = SpiceParser()
        lines = [
            ".subckt mysub A VSS",
            "r1 A VSS 100",
            ".ends",
            "cc_1 node1 N 1f",
            "cc_2 node2 N 2f",
        ]
        
        result = parser.parse_lines_complete(lines)
        
        assert len(result.top_level_elements) == 2
        assert all(e.element_type == ElementType.COUPLING_CAPACITOR for e in result.top_level_elements)

    def test_parse_lines_complete_parses_top_level_resistor(self):
        """
        Test parsing resistors at top level.
        
        Scenario: Bias resistor at top level.
        Expected: Resistor in top_level_elements.
        """
        parser = SpiceParser()
        lines = [
            ".subckt mysub A VSS",
            "r1 A VSS 100",
            ".ends",
            "r_bias N 0 1meg",
        ]
        
        result = parser.parse_lines_complete(lines)
        
        assert len(result.top_level_elements) == 1
        assert result.top_level_elements[0].element_type == ElementType.RESISTOR

    # ==================== SubcircuitInstance Tests ====================

    def test_parse_lines_complete_parses_instance(self):
        """
        Test parsing of subcircuit instantiation (X line).
        
        Scenario: x0 instance of mysub subcircuit.
        Expected: Instance appears in instances list.
        """
        from parser.element_types import SubcircuitInstance
        
        parser = SpiceParser()
        lines = [
            ".subckt mysub A VSS",
            "r1 A VSS 100",
            ".ends",
            "x0 port1 port2 mysub",
        ]
        
        result = parser.parse_lines_complete(lines)
        
        assert len(result.instances) == 1
        assert isinstance(result.instances[0], SubcircuitInstance)
        assert result.instances[0].subcircuit_type == "mysub"

    def test_instance_connections_parsed_correctly(self):
        """
        Test that instance connections are correctly extracted.
        
        Scenario: Instance with 3 port connections.
        Expected: All connections in order.
        """
        parser = SpiceParser()
        lines = [
            ".subckt mysub A B C",
            "r1 A B 100",
            ".ends",
            "x0 node1 node2 node3 mysub",
        ]
        
        result = parser.parse_lines_complete(lines)
        
        assert result.instances[0].connections == ["node1", "node2", "node3"]

    def test_instance_name_parsed_correctly(self):
        """
        Test that instance name is extracted from X line.
        
        Scenario: x_myinst instance.
        Expected: instance_name = "_myinst" (after 'x').
        """
        parser = SpiceParser()
        lines = [
            ".subckt mysub A",
            "r1 A 0 100",
            ".ends",
            "x_myinst port1 mysub",
        ]
        
        result = parser.parse_lines_complete(lines)
        
        assert result.instances[0].instance_name == "_myinst"

    def test_instance_with_special_characters(self):
        """
        Test parsing instance with special characters like % in name.
        
        Scenario: Instance name contains % (like real netlist).
        Expected: Correctly parsed without error.
        """
        parser = SpiceParser()
        lines = [
            ".subckt PM_CMOM1%P A B",
            "r1 A B 100",
            ".ends",
            "x_PM_CMOM1%P port1 port2 PM_CMOM1%P",
        ]
        
        result = parser.parse_lines_complete(lines)
        
        assert len(result.instances) == 1
        assert result.instances[0].subcircuit_type == "PM_CMOM1%P"

    # ==================== Mixed Content Tests ====================

    def test_complete_netlist_with_all_elements(self):
        """
        Test parsing a complete netlist with subcircuit, instance, and top-level elements.
        
        Scenario: Full hierarchy like the real netlist.
        Expected: All components correctly parsed.
        """
        parser = SpiceParser()
        lines = [
            ".subckt mysub A B VSS",
            "r1 A B 100",
            "c1 B VSS 1f",
            ".ends",
            "x0 p1 p2 p3 mysub",
            "cc_1 p1 N 1f",
            "cc_2 p2 N 2f",
        ]
        
        result = parser.parse_lines_complete(lines)
        
        assert len(result.subcircuits) == 1
        assert len(result.instances) == 1
        assert len(result.top_level_elements) == 2

    def test_multiple_instances(self):
        """
        Test parsing multiple subcircuit instances.
        
        Scenario: Two instances of same subcircuit.
        Expected: Both instances in list.
        """
        parser = SpiceParser()
        lines = [
            ".subckt mysub A",
            "r1 A 0 100",
            ".ends",
            "x0 port1 mysub",
            "x1 port2 mysub",
        ]
        
        result = parser.parse_lines_complete(lines)
        
        assert len(result.instances) == 2
        assert result.instances[0].instance_name == "0"
        assert result.instances[1].instance_name == "1"
