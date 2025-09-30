# Sample Files

This directory contains sample files for testing PromptPlot's file conversion capabilities.

## File Types

### SVG Files
- `logo.svg` - Simple logo design with basic shapes
- `complex_drawing.svg` - Complex drawing with multiple paths and curves
- `geometric_pattern.svg` - Geometric pattern with precise measurements

### G-code Files
- `simple_commands.gcode` - Basic G-code commands for testing
- `square_pattern.gcode` - Simple square drawing
- `calibration_pattern.gcode` - Calibration and test pattern

### DXF Files
- `technical_drawing.dxf` - Technical drawing with dimensions
- `mechanical_part.dxf` - Mechanical part design
- `floor_plan.dxf` - Architectural floor plan

### HPGL Files
- `legacy_plot.hpgl` - Legacy plotter file
- `text_sample.hpgl` - Text plotting example

### Configuration Files
- `development.yaml` - Development configuration
- `production.yaml` - Production configuration
- `art_studio.yaml` - Art studio configuration

## Usage

These files can be used with the examples:

```bash
# Convert SVG to G-code
python ../file_conversion/svg_to_gcode.py logo.svg

# Plot G-code directly
python ../file_conversion/direct_gcode_plotting.py simple_commands.gcode

# Batch convert multiple files
python ../file_conversion/batch_file_conversion.py *.svg *.dxf
```

## File Descriptions

### logo.svg
Simple company logo with:
- Rectangular border
- Central circle
- Text elements
- Basic geometric shapes

Good for: Testing basic SVG conversion, learning path extraction

### complex_drawing.svg
Artistic drawing with:
- Bezier curves
- Multiple layers
- Gradients (converted to paths)
- Complex path combinations

Good for: Testing advanced SVG features, performance testing

### technical_drawing.dxf
Engineering drawing with:
- Precise dimensions
- Multiple layers
- Technical annotations
- Standard CAD elements

Good for: CAD integration testing, precision validation

### calibration_pattern.gcode
Test pattern with:
- Grid lines for accuracy
- Circles for roundness
- Diagonal lines for axis alignment
- Speed variation tests

Good for: Hardware calibration, accuracy testing