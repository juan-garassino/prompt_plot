"""
GCode visualization for PromptPlot v3.0

Merged from:
- PromptPlot plotter/simulated.py: matplotlib visualization
- drawStream gcode_plotter.py: stats, PNG output, color-coded paths
"""

import math
from typing import Optional, Dict, Any, List, Tuple

from .models import GCodeCommand, GCodeProgram
from .config import PromptPlotConfig, VisualizationConfig

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.collections import LineCollection
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class GCodeVisualizer:
    """Render GCode programs to PNG with stats."""

    def __init__(self, config: Optional[PromptPlotConfig] = None):
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib required for visualization")
        self.config = config
        viz = config.visualization if config else VisualizationConfig()
        self.fig_w = viz.figure_width
        self.fig_h = viz.figure_height
        self.dpi = viz.figure_dpi
        self.draw_color = viz.drawing_color
        self.travel_color = viz.travel_color
        self.line_width = viz.line_width

    def preview(self, program: GCodeProgram, output_path: str = "preview.png"):
        """Render program to PNG file."""
        lines, stats = self._trace(program)
        self._render(lines, stats, output_path)

    def get_stats(self, program: GCodeProgram) -> Dict[str, Any]:
        """Get drawing statistics without rendering."""
        _, stats = self._trace(program)
        return stats

    def _trace(self, program: GCodeProgram):
        """Trace the program and collect line segments + stats."""
        x, y = 0.0, 0.0
        pen_down = False
        lines: List[Tuple[float, float, float, float, bool]] = []
        draw_dist = 0.0
        travel_dist = 0.0
        pen_cycles = 0

        for cmd in program.commands:
            if cmd.command == "M3":
                pen_down = True
                pen_cycles += 1
            elif cmd.command == "M5":
                pen_down = False
            elif cmd.command in ("G0", "G1"):
                nx = cmd.x if cmd.x is not None else x
                ny = cmd.y if cmd.y is not None else y
                is_draw = pen_down and cmd.command == "G1"
                lines.append((x, y, nx, ny, is_draw))
                d = math.sqrt((nx - x) ** 2 + (ny - y) ** 2)
                if is_draw:
                    draw_dist += d
                else:
                    travel_dist += d
                x, y = nx, ny

        stats = {
            "drawing_distance": round(draw_dist, 2),
            "travel_distance": round(travel_dist, 2),
            "total_distance": round(draw_dist + travel_dist, 2),
            "pen_cycles": pen_cycles,
            "total_commands": len(program.commands),
            "drawing_segments": sum(1 for l in lines if l[4]),
            "travel_segments": sum(1 for l in lines if not l[4]),
        }

        bounds = program.get_bounds()
        if bounds:
            stats["bounds"] = bounds

        return lines, stats

    def _render(self, lines, stats, output_path: str):
        fig, ax = plt.subplots(figsize=(self.fig_w, self.fig_h))

        # Paper outline
        paper_w = self.config.paper.width if self.config else 210
        paper_h = self.config.paper.height if self.config else 297
        margin = 10

        ax.set_xlim(-margin, paper_w + margin)
        ax.set_ylim(-margin, paper_h + margin)
        ax.set_aspect("equal")

        # Paper boundary (gray dashed)
        ax.add_patch(Rectangle((0, 0), paper_w, paper_h,
                               fill=False, edgecolor="gray", linestyle="--", alpha=0.5))

        # Drawable area overlay (green dotted)
        if self.config:
            dx0, dy0, dx1, dy1 = self.config.paper.get_drawable_area()
            ax.add_patch(Rectangle(
                (dx0, dy0), dx1 - dx0, dy1 - dy0,
                fill=False, edgecolor="green", linestyle=":", linewidth=1.5, alpha=0.6,
            ))

        # Classify segments: in-bounds draw, out-of-bounds draw, travel
        if lines:
            draw_segs = []
            oob_segs = []
            travel_segs = []

            for l in lines:
                seg = ((l[0], l[1]), (l[2], l[3]))
                if not l[4]:
                    travel_segs.append(seg)
                else:
                    # Check if either endpoint is out of paper bounds
                    oob = (l[2] < 0 or l[2] > paper_w or l[3] < 0 or l[3] > paper_h
                           or l[0] < 0 or l[0] > paper_w or l[1] < 0 or l[1] > paper_h)
                    if oob:
                        oob_segs.append(seg)
                    else:
                        draw_segs.append(seg)

            if travel_segs:
                lc = LineCollection(travel_segs, colors=self.travel_color,
                                    linewidths=0.5, alpha=0.3)
                ax.add_collection(lc)
            if draw_segs:
                lc = LineCollection(draw_segs, colors=self.draw_color,
                                    linewidths=self.line_width)
                ax.add_collection(lc)
            if oob_segs:
                lc = LineCollection(oob_segs, colors="red",
                                    linewidths=self.line_width * 1.5, alpha=0.8)
                ax.add_collection(lc)

            # Mark start/end
            if lines:
                ax.plot(lines[0][0], lines[0][1], "ro", markersize=5, label="Start")
                ax.plot(lines[-1][2], lines[-1][3], "go", markersize=5, label="End")

        # Stats text
        stats_text = (
            f"Draw: {stats['drawing_distance']:.1f} mm\n"
            f"Travel: {stats['travel_distance']:.1f} mm\n"
            f"Pen cycles: {stats['pen_cycles']}\n"
            f"Commands: {stats['total_commands']}"
        )
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=8,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

        # Warning if out-of-bounds segments exist
        if lines and any(
            (l[4] and (l[2] < 0 or l[2] > paper_w or l[3] < 0 or l[3] > paper_h
                       or l[0] < 0 or l[0] > paper_w or l[1] < 0 or l[1] > paper_h))
            for l in lines
        ):
            ax.text(0.5, 0.02, "WARNING: Out-of-bounds segments (red)",
                    transform=ax.transAxes, fontsize=9, color="red",
                    ha="center", va="bottom",
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.9))

        ax.set_title("PromptPlot Preview")
        ax.legend(loc="upper right", fontsize="small")
        fig.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
