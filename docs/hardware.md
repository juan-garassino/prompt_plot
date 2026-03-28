# Hardware Setup

## Supported plotters

Any pen plotter that speaks GRBL (or compatible firmware) over serial USB.
The plotter must respond with `ok` after each command.

## Connecting

1. Plug the plotter in via USB
2. Find the serial port:

```bash
promptplot plotter list-ports
```

Common port names:
- macOS: `/dev/cu.usbserial-10`, `/dev/cu.usbmodem-*`
- Linux: `/dev/ttyUSB0`, `/dev/ttyACM0`
- Windows: `COM3`, `COM4`

3. Test the connection:

```bash
promptplot plotter connect --port /dev/cu.usbserial-10
```

4. Plot a file:

```bash
promptplot plot drawing.gcode --port /dev/cu.usbserial-10
```

## Serial configuration

```yaml
serial:
  port: /dev/cu.usbserial-10
  baud_rate: 115200
  timeout: 5.0
```

## GCode commands used

| Command | Meaning |
|---------|---------|
| `G0 X_ Y_` | Rapid move (pen up, no drawing) |
| `G1 X_ Y_ F_` | Linear move (pen down, drawing) |
| `M3 S_` | Pen down (servo/spindle on) |
| `M5` | Pen up (servo/spindle off) |
| `G4 P_` | Dwell (pause) in milliseconds |
| `G28` | Home all axes |

## Paper setup

Default is A4 (210 x 297mm). For A3:

```yaml
paper:
  width: 297.0
  height: 420.0
  margin_x: 10.0
  margin_y: 10.0
pen:
  pen_down_s_value: 1000
  feed_rate: 2000
```

Margins keep the pen away from paper edges. The LLM prompt is built dynamically from these values — changing paper size automatically updates the coordinate ranges the LLM uses.

Bounds validation prevents coordinates from exceeding paper dimensions:

```yaml
bounds:
  enforce: true
  mode: clamp    # clamp | reject | warn
```

## Brush mode

For brush/ink plotters that need periodic ink reloads:

```yaml
brush:
  enabled: true
  charge_position: [10.0, 10.0]
  strokes_before_reload: 10
  dip_duration: 0.5
  drip_duration: 1.0
```

Or via CLI:

```bash
promptplot plot drawing.gcode --brush
```

## Troubleshooting

- **ALARM from the machine**: Emergency stop — pen hit the edge. Check paper bounds.
- **error:X**: Bad GCode instruction. Run `promptplot preview` to validate first.
- **Pen dragging between shapes**: Missing pen lifts. The post-processor should fix this automatically.
- **No serial ports found**: Check USB cable, drivers, permissions (`sudo chmod 666 /dev/ttyUSB0`).
- **Timeout**: Increase `serial.timeout` in config or check baud rate matches firmware.
