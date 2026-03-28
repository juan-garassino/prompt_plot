# Post-Processing Pipeline

Every GCode program passes through five stages before reaching the plotter.
The order is critical — bounds must be first, dwells must be last.

## Pipeline order

```
Raw GCode → bounds validation → pen safety → stroke optimization → paint dips → pen dwells → plotter
```

## 0. Bounds validation (`validate_bounds`)

Checks all X/Y coordinates against paper dimensions. Runs before everything else to prevent hardware damage.

Three modes:
- **clamp** (default): Coordinates outside `[0, paper.width]` / `[0, paper.height]` are clamped to the nearest valid value
- **reject**: Out-of-bounds commands are removed entirely
- **warn**: Commands are kept but violations are logged

```yaml
bounds:
  enforce: true
  mode: clamp
```

Set `enforce: false` to skip bounds checking entirely.

## 1. Pen safety (`ensure_pen_safety`)

Fixes pen state violations in LLM-generated GCode:

- Starts with `M5` (pen up)
- Inserts `M5` before any `G0` rapid move if pen is down
- Inserts `M3 S{value}` before any `G1` draw move if pen is up
- Ends with `M5` and `G0 X0 Y0` (return home)

The S-value for M3 is configurable via `pen.pen_down_s_value` (default 1000).

## 2. Stroke optimization (`optimize_gcode_program`)

Reduces pen lifts and travel distance:

1. Extracts individual strokes (M3 → G1s → M5)
2. Reorders using nearest-neighbor heuristic
3. Rebuilds with G0 repositioning between strokes

## 3. Paint dips (`insert_paint_dips`)

Only active when `brush.enabled = true`. Inserts ink reload sequences
every N strokes:

```
M5              ; pen up
G0 X10 Y10     ; move to ink station
G0 Z0          ; dip into ink
G4 P500        ; hold in ink (dip_duration)
G0 Z5          ; lift
G4 P1000       ; drip (drip_duration)
; resume drawing
```

## 4. Pen dwells (`insert_pen_dwells`)

Inserts G4 dwell commands after every M3 and M5 to let the pen servo settle:

```
M3 S1000        ; pen down
G4 P200         ; wait 200ms (pen_down_delay)
...
M5              ; pen up
G4 P200         ; wait 200ms (pen_up_delay)
```

Set delays to 0 to skip.

## Using the pipeline in code

```python
from promptplot.postprocess import run_pipeline
from promptplot import get_config

config = get_config()
processed = run_pipeline(program, config)
```

Individual stages can be called separately:

```python
from promptplot.postprocess import (
    validate_bounds,
    ensure_pen_safety,
    optimize_gcode_program,
    insert_paint_dips,
    insert_pen_dwells,
)
```

## Visualization

The visualizer shows bounds information in the preview:

- **Gray dashed rectangle**: Paper boundary
- **Green dotted rectangle**: Drawable area (paper minus margins)
- **Red segments**: Out-of-bounds drawing commands (if any remain after validation)
- **Warning text**: Displayed when out-of-bounds segments are detected
