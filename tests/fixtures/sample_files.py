"""
Sample files for testing file conversion functionality.
"""
from pathlib import Path
from typing import Dict, Any


def get_sample_svg() -> str:
    """Get sample SVG content for testing."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <!-- Simple rectangle -->
  <rect x="10" y="10" width="30" height="20" fill="none" stroke="black" stroke-width="1"/>
  
  <!-- Circle -->
  <circle cx="70" cy="25" r="10" fill="none" stroke="black" stroke-width="1"/>
  
  <!-- Line -->
  <line x1="10" y1="50" x2="90" y2="50" stroke="black" stroke-width="1"/>
  
  <!-- Path with curves -->
  <path d="M 20 70 Q 50 60 80 70" fill="none" stroke="black" stroke-width="1"/>
  
  <!-- Polyline -->
  <polyline points="10,80 30,85 50,80 70,85 90,80" fill="none" stroke="black" stroke-width="1"/>
</svg>'''


def get_sample_gcode() -> str:
    """Get sample G-code content for testing."""
    return """G21 ; Set units to millimeters
G90 ; Use absolute positioning
G28 ; Home all axes

; Start drawing
G1 X10 Y10 F1000 ; Move to start position
M3 S255 ; Pen down

; Draw rectangle
G1 X40 Y10 F1000 ; Bottom edge
G1 X40 Y30 F1000 ; Right edge  
G1 X10 Y30 F1000 ; Top edge
G1 X10 Y10 F1000 ; Left edge

M5 ; Pen up

; Move to circle start
G1 X70 Y15 F1000
M3 S255 ; Pen down

; Draw circle (approximated with short segments)
G1 X75 Y17 F1000
G1 X78 Y21 F1000
G1 X80 Y25 F1000
G1 X78 Y29 F1000
G1 X75 Y33 F1000
G1 X70 Y35 F1000
G1 X65 Y33 F1000
G1 X62 Y29 F1000
G1 X60 Y25 F1000
G1 X62 Y21 F1000
G1 X65 Y17 F1000
G1 X70 Y15 F1000

M5 ; Pen up

; Draw line
G1 X10 Y50 F1000
M3 S255 ; Pen down
G1 X90 Y50 F1000
M5 ; Pen up

; Return home
G28
M84 ; Disable motors"""


def get_sample_dxf() -> str:
    """Get sample DXF content for testing."""
    return """0
SECTION
2
HEADER
9
$ACADVER
1
AC1015
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
5
100
100
AcDbEntity
8
0
100
AcDbLine
10
10.0
20
10.0
30
0.0
11
40.0
21
10.0
31
0.0
0
LINE
5
101
100
AcDbEntity
8
0
100
AcDbLine
10
40.0
20
10.0
30
0.0
11
40.0
21
30.0
31
0.0
0
LINE
5
102
100
AcDbEntity
8
0
100
AcDbLine
10
40.0
20
30.0
30
0.0
11
10.0
21
30.0
31
0.0
0
LINE
5
103
100
AcDbEntity
8
0
100
AcDbLine
10
10.0
20
30.0
30
0.0
11
10.0
21
10.0
31
0.0
0
CIRCLE
5
104
100
AcDbEntity
8
0
100
AcDbCircle
10
70.0
20
25.0
30
0.0
40
10.0
0
ENDSEC
0
EOF"""


def get_sample_hpgl() -> str:
    """Get sample HPGL content for testing."""
    return """IN;
SP1;
PU;
PA10,10;
PD;
PA40,10;
PA40,30;
PA10,30;
PA10,10;
PU;
PA70,15;
PD;
CI10;
PU;
PA10,50;
PD;
PA90,50;
PU;
SP0;"""


def get_sample_json() -> str:
    """Get sample JSON G-code content for testing."""
    return """{
  "metadata": {
    "title": "Test Drawing",
    "description": "Sample drawing for testing",
    "units": "mm",
    "created_by": "test_suite"
  },
  "commands": [
    {"command": "G28", "comment": "Home all axes"},
    {"command": "G1", "x": 10.0, "y": 10.0, "f": 1000, "comment": "Move to start"},
    {"command": "M3", "s": 255, "comment": "Pen down"},
    {"command": "G1", "x": 40.0, "y": 10.0, "f": 1000, "comment": "Draw line"},
    {"command": "G1", "x": 40.0, "y": 30.0, "f": 1000, "comment": "Draw line"},
    {"command": "G1", "x": 10.0, "y": 30.0, "f": 1000, "comment": "Draw line"},
    {"command": "G1", "x": 10.0, "y": 10.0, "f": 1000, "comment": "Draw line"},
    {"command": "M5", "comment": "Pen up"},
    {"command": "G28", "comment": "Return home"}
  ]
}"""


def get_invalid_svg() -> str:
    """Get invalid SVG content for error testing."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <!-- Missing closing tag -->
  <rect x="10" y="10" width="30" height="20" fill="none" stroke="black"
  <!-- Invalid path -->
  <path d="M 20 70 Q INVALID 80 70" fill="none" stroke="black"/>
</svg>'''


def get_invalid_gcode() -> str:
    """Get invalid G-code content for error testing."""
    return """G21 ; Set units
INVALID_COMMAND ; This is not a valid G-code command
G1 X Y10 F1000 ; Missing X coordinate value
M3 S ; Missing spindle speed value
G1 X10.5.5 Y20 F1000 ; Invalid coordinate format"""


def get_invalid_dxf() -> str:
    """Get invalid DXF content for error testing."""
    return """0
SECTION
2
ENTITIES
0
LINE
MISSING_CODE
10.0
20
10.0
11
INVALID_COORDINATE
21
10.0
0
ENDSEC"""


def create_test_files(temp_dir: Path) -> Dict[str, Path]:
    """Create all test files in a temporary directory."""
    files = {}
    
    # Valid files
    svg_file = temp_dir / "test.svg"
    svg_file.write_text(get_sample_svg())
    files["svg"] = svg_file
    
    gcode_file = temp_dir / "test.gcode"
    gcode_file.write_text(get_sample_gcode())
    files["gcode"] = gcode_file
    
    dxf_file = temp_dir / "test.dxf"
    dxf_file.write_text(get_sample_dxf())
    files["dxf"] = dxf_file
    
    hpgl_file = temp_dir / "test.hpgl"
    hpgl_file.write_text(get_sample_hpgl())
    files["hpgl"] = hpgl_file
    
    json_file = temp_dir / "test.json"
    json_file.write_text(get_sample_json())
    files["json"] = json_file
    
    # Invalid files for error testing
    invalid_svg = temp_dir / "invalid.svg"
    invalid_svg.write_text(get_invalid_svg())
    files["invalid_svg"] = invalid_svg
    
    invalid_gcode = temp_dir / "invalid.gcode"
    invalid_gcode.write_text(get_invalid_gcode())
    files["invalid_gcode"] = invalid_gcode
    
    invalid_dxf = temp_dir / "invalid.dxf"
    invalid_dxf.write_text(get_invalid_dxf())
    files["invalid_dxf"] = invalid_dxf
    
    # Empty file
    empty_file = temp_dir / "empty.txt"
    empty_file.write_text("")
    files["empty"] = empty_file
    
    # Binary file (should not be processed)
    binary_file = temp_dir / "binary.bin"
    binary_file.write_bytes(b'\x00\x01\x02\x03\x04\x05')
    files["binary"] = binary_file
    
    return files


# Expected results for validation
EXPECTED_SVG_COMMANDS = 15  # Approximate number of commands from SVG conversion
EXPECTED_GCODE_COMMANDS = 25  # Number of commands in sample G-code
EXPECTED_DXF_COMMANDS = 10  # Number of commands from DXF conversion
EXPECTED_JSON_COMMANDS = 9  # Number of commands in JSON file

EXPECTED_BOUNDS = {
    "svg": {"min_x": 10, "max_x": 90, "min_y": 10, "max_y": 85},
    "rectangle": {"min_x": 10, "max_x": 40, "min_y": 10, "max_y": 30},
    "circle": {"min_x": 60, "max_x": 80, "min_y": 15, "max_y": 35}
}