# PromptPlot TODO List

## 🖊️ Automatic Pen Refill/Reload System

### Current Status
- ✅ **Pen change position configuration** exists in `promptplot/config/settings.py`
- ✅ **Manual pen change logic** implemented in `examples/demo_comprehensive.py`
- ✅ **Ink change notifications** available in `promptplot/utils/rich_logger.py`
- ❌ **Automatic refill intervals** - NOT IMPLEMENTED

### Missing Features

#### 1. Automatic Refill Configuration
- [ ] Add refill interval settings to configuration
  ```python
  # In promptplot/config/settings.py
  refill_interval_commands: int = 100    # Refill every N commands
  refill_interval_distance: float = 500.0  # Refill every N mm drawn
  refill_interval_time: float = 1800.0     # Refill every N seconds (30 min)
  enable_automatic_refill: bool = True
  refill_position: tuple = (0.0, 0.0, 20.0)  # XYZ coordinates for refill
  refill_pause_duration: float = 30.0      # Pause time for manual refill
  ```

#### 2. Refill Tracking Logic
- [ ] **Command counter** - Track total commands executed
- [ ] **Distance tracker** - Calculate total drawing distance
- [ ] **Time tracker** - Monitor drawing session duration
- [ ] **Ink usage estimator** - Estimate ink consumption based on drawing

#### 3. Workflow Integration
- [ ] **Refill trigger detection** in base workflows
- [ ] **Automatic refill sequence** implementation:
  1. Pen up
  2. Move to refill position
  3. Pause for manual refill (with user notification)
  4. Resume from last drawing position
- [ ] **Refill state management** - Track refill history and next refill due

#### 4. Plotter Integration
- [ ] **Refill commands** in `BasePlotter` class
- [ ] **Refill position validation** - Ensure refill position is safe
- [ ] **Resume position tracking** - Remember where to continue after refill

#### 5. User Interface
- [ ] **Refill notifications** - Visual/audio alerts when refill is needed
- [ ] **Refill progress indicators** - Show time until next refill
- [ ] **Manual refill trigger** - Allow user to force refill
- [ ] **Refill history logging** - Track all refill events

#### 6. Configuration Options
- [ ] **Multiple refill triggers** - Support OR/AND logic:
  - Every N commands OR every N mm OR every N minutes
- [ ] **Refill position profiles** - Different positions for different pen types
- [ ] **Smart refill scheduling** - Refill at natural break points in drawing

### Implementation Priority

#### Phase 1: Basic Automatic Refill
1. Add configuration settings for refill intervals
2. Implement command/distance/time tracking
3. Add refill trigger detection to workflows
4. Create basic refill sequence (move to position, pause, resume)

#### Phase 2: Enhanced Refill Features
1. Smart refill scheduling (at drawing breaks)
2. Multiple refill trigger logic
3. Refill history and analytics
4. User interface improvements

#### Phase 3: Advanced Features
1. Ink usage estimation and prediction
2. Multiple pen/brush support with different refill needs
3. Automatic refill position calibration
4. Integration with visualization system for refill tracking

### Files to Modify

#### Configuration
- `promptplot/config/settings.py` - Add refill settings
- `promptplot/config/runtime.py` - Add runtime refill configuration

#### Core Logic
- `promptplot/core/base_workflow.py` - Add refill trigger detection
- `promptplot/workflows/*.py` - Integrate refill logic into all workflows
- `promptplot/plotter/base.py` - Add refill command methods

#### User Interface
- `promptplot/utils/rich_logger.py` - Enhanced refill notifications
- `promptplot/visualization/*.py` - Refill progress indicators

#### Examples
- `examples/demo_llm_to_plotter.py` - Add refill demo options
- `examples/demo_comprehensive.py` - Add automatic refill tests

### Usage Examples (Future)

```bash
# Enable automatic refill every 50 commands
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 \
  --auto-refill --refill-commands 50 --prompt "draw a complex scene"

# Enable refill every 10 minutes of drawing
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 \
  --auto-refill --refill-time 600 --prompt "long drawing session"

# Multiple refill triggers (every 100 commands OR 500mm OR 15 minutes)
uv run python examples/demo_llm_to_plotter.py /dev/cu.usbserial-14220 \
  --auto-refill --refill-commands 100 --refill-distance 500 --refill-time 900
```

---

## 🎨 Other Enhancement Ideas

### Visualization Improvements
- [ ] Real-time ink level indicators
- [ ] Refill countdown timers
- [ ] Drawing session analytics with refill events

### Hardware Integration
- [ ] Automatic ink level sensors (if hardware supports)
- [ ] Multiple pen carousel support
- [ ] Brush cleaning station integration

### Workflow Enhancements
- [ ] Pause/resume functionality for manual interventions
- [ ] Drawing session save/restore across refills
- [ ] Batch processing with automatic refill management

---

*Last updated: December 11, 2025*