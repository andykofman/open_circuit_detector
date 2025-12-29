# Open Circuit Detector

This project is a complete solution for detecting open circuits in hierarchical SPICE netlists, as part of the Siemens 3D-IC QA. The codebase is designed to be robust, readable, and easy to extend. 

## What This Project Does
- **Parses SPICE netlists** (including subcircuits, instances, and all standard elements)
- **Builds a graph** of the circuit, flattening hierarchy as needed
- **Detects open circuits**: floating nodes, isolated components, capacitor-only connections, and more
- **Generates reports** in both JSON and human-readable text formats
- **Includes a full test suite** (109 tests, all passing) to ensure reliability

## Project Structure

| Folder      | Purpose                                                        |
|-------------|----------------------------------------------------------------|
| `parser/`   | SPICE netlist parsing logic (handles subcircuits, instances, elements) |
| `graph/`    | Circuit graph construction and analysis (flattening, connectivity, node degrees) |
| `analyzer/` | Open circuit detection algorithms (floating nodes, DC floating, etc.) |
| `reporter/` | Report generation (JSON and text outputs)                      |
| `data/`     | Example netlists and test data                                 |
| `tests/`    | Comprehensive unit and integration tests for all modules        |

## How It Works (Quick Overview)

1. **Parse** (`parser/`):
	- Handles SPICE netlists with all the usual quirks: continuation lines, comments, subcircuits, and even special characters in instance names (like `%`).
	- Recognizes and parses resistors, capacitors, coupling capacitors, and subcircuit instances.
	- Builds a full in-memory representation of the netlist, including all hierarchy.

2. **Graph Build** (`graph/`):
	- Flattens the netlist hierarchy into a single graph, so you can see the real connectivity at the top level.
	- Normalizes node names (case-insensitive, handles ground aliases like `0`, `gnd`, `vss`, `ground`).
	- Tracks both resistive and capacitive connections separately, so DC and AC paths are clear.
	- Implements methods to get node degrees, connected components, and check for ground connectivity.

3. **Analyze** (`analyzer/`):
	- Detects all the classic open circuit issues: floating nodes, isolated components, floating ports, and nodes that are only connected by capacitors (no DC path).
	- Includes a dedicated check for DC-floating nodes (nodes with no resistive path to ground, even if they have capacitive connections).
	- All detection logic is modular and easy to extend if you want to add more checks.

4. **Report** (`reporter/`):
	- Generates both JSON and human-readable text reports, with summaries and detailed issue breakdowns.
	- Reports include affected elements, severity, and a description for each issue.
	- Always saves both formats with a timestamp, so you can track every run.


## Running the Tool

- Make sure you have Python 3.12+ and `pytest` installed.
- Place your netlist in the `data/` folder (or point the tool to your file).
- To run all tests: `pytest tests/ -v`

### Run the Main Analysis (CLI)

You can analyze a netlist and generate both JSON and text reports using the CLI:

```sh
python main.py data/netlist\ 1.sp
```

By default, every run will save two reports in the `reports/` folder:
- A JSON report: `reports/report_<timestamp>.json`
- A text report: `reports/report_<timestamp>.txt`

The timestamp is in ISO format (date and time), so you always know which run produced which report.

You can also specify custom output paths if you want:

```sh
python main.py data/netlist\ 1.sp --output-json my_report.json --output-text my_report.txt
```

But even if you use custom paths, the timestamped reports will always be saved in `reports/` for traceability.

#### Example

```sh
# Analyze the provided netlist and generate both reports
python main.py data/netlist\ 1.sp

# Output:
#   reports/report_2025-12-29T15-30-00.json
#   reports/report_2025-12-29T15-30-00.txt
```

You can open the text report for a quick summary, or the JSON for detailed integration or post-processing.

---


## If You Want to Dive Deeper
- Check out the `tests/` folder for examples of what is detected and how
- The `reporter/` module shows how to generate and save reports
- The `analyzer/` module is where the detection logic lives
- The `parser/` and `graph/` modules handle all the heavy lifting for netlist parsing and graph construction

## Final Notes
- This project is meant to be practical and readable, if you spot something odd or want to add a feature, it should be straightforward to jump in.


---

**Created and maintained by Ahmed Ali.**

