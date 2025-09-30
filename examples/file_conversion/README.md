# File Conversion Examples

This directory contains examples for converting and plotting various file formats.

## Examples

### svg_to_gcode.py
Convert SVG files to G-code and plot them.

**Features:**
- SVG path parsing
- Conversion settings
- G-code optimization
- Plotting workflow

### direct_gcode_plotting.py
Load and plot existing G-code files.

**Features:**
- G-code validation
- Direct plotting
- Error handling

### batch_file_conversion.py
Convert multiple files in batch.

**Features:**
- Multiple format support
- Batch processing
- Progress monitoring

### dxf_conversion.py
Convert CAD DXF files to plottable G-code.

**Features:**
- DXF entity parsing
- Layer selection
- CAD-specific optimizations

## Sample Files

The `../sample_files/` directory contains test files:

- `logo.svg` - Simple SVG logo
- `complex_drawing.svg` - Complex SVG with multiple paths
- `technical_drawing.dxf` - CAD technical drawing
- `simple_commands.gcode` - Basic G-code file
- `artistic_pattern.hpgl` - Legacy HPGL file

## Usage

Most examples can be run with sample files:

```bash
python svg_to_gcode.py ../sample_files/logo.svg
```

## Supported Formats

- **SVG**: Scalable Vector Graphics
- **G-code**: Direct G-code files
- **DXF**: AutoCAD Drawing Exchange Format
- **HPGL**: HP Graphics Language
- **JSON**: Programmatic G-code data
- **Images**: Basic bitmap conversion (PNG, JPG)