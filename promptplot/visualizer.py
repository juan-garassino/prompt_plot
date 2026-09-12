"""
GCode visualization for PromptPlot v3.0

Merged from:
- PromptPlot plotter/simulated.py: matplotlib visualization
- drawStream gcode_plotter.py: stats, PNG output, color-coded paths
"""

import json
import math
from pathlib import Path
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

    def preview(
        self,
        program: GCodeProgram,
        output_path: str = "preview.png",
        color_layers: Optional[bool] = None,
        palette: Optional[List[str]] = None,
    ):
        """Render program to PNG file.

        When the program has multiple pen colors (or ``color_layers=True``), each
        color layer is drawn in its own color using ``palette`` (falling back to
        a distinct color cycle) with a legend.
        """
        lines, stats = self._trace(program)
        if palette is None and self.config is not None and getattr(self.config, "color", None):
            palette = list(self.config.color.palette)
        distinct = {l[5] for l in lines if l[4] and len(l) > 5 and l[5] is not None}
        if color_layers is None:
            color_layers = len(distinct) > 1
        if color_layers and distinct:
            self._render_color_layers(lines, stats, output_path, palette or [])
        else:
            self._render(lines, stats, output_path)

    def get_stats(self, program: GCodeProgram) -> Dict[str, Any]:
        """Get drawing statistics without rendering."""
        _, stats = self._trace(program)
        return stats

    def analyze_regions(
        self,
        program: GCodeProgram,
        *,
        creative_mode: str = "figurative",
        plan: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Analyze the traced drawing by plan regions or a fallback grid."""
        lines, stats = self._trace(program)
        regions = self._build_regions(plan)
        drawing_lines = [line for line in lines if line[4]]
        region_reports: List[Dict[str, Any]] = []
        total_area = sum(region["width"] * region["height"] for region in regions) or 1.0

        for region in regions:
            draw_distance = 0.0
            segment_count = 0
            angle_sum = 0.0
            for x0, y0, x1, y1, is_draw, *_ in drawing_lines:
                mx = (x0 + x1) / 2
                my = (y0 + y1) / 2
                if self._point_in_region(mx, my, region):
                    segment_count += 1
                    dist = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
                    draw_distance += dist
                    if dist > 0.01:
                        angle_sum += abs(math.atan2(y1 - y0, x1 - x0))
            area = max(region["width"] * region["height"], 1.0)
            density = draw_distance / area
            occupancy = area / total_area
            issue = self._region_issue(region, density, segment_count, creative_mode)
            region_reports.append(
                {
                    **region,
                    "draw_distance": round(draw_distance, 3),
                    "segment_count": segment_count,
                    "density": round(density, 6),
                    "occupancy": round(occupancy, 6),
                    "avg_angle": round(angle_sum / segment_count, 6) if segment_count else 0.0,
                    "issue": issue["issue"],
                    "severity": issue["severity"],
                    "recommended_change": issue["recommended_change"],
                }
            )

        weak_regions = [
            {
                "name": region["name"],
                "issue": region["issue"],
                "severity": region["severity"],
                "recommended_change": region["recommended_change"],
            }
            for region in region_reports
            if region["severity"] > 0.35
        ]
        weak_regions.sort(key=lambda item: item["severity"], reverse=True)
        dominant_issue = weak_regions[0]["issue"] if weak_regions else "detail"
        density_values = [region["density"] for region in region_reports]
        if density_values:
            density_variation = max(density_values) - min(density_values)
        else:
            density_variation = 0.0
        analysis = {
            "creative_mode": creative_mode,
            "global": {
                "region_count": len(region_reports),
                "weak_region_count": len(weak_regions),
                "density_variation": round(density_variation, 6),
                "dominant_issue": dominant_issue,
                "center_clustering_hint": self._center_clustering_hint(drawing_lines),
            },
            "regions": region_reports,
            "weak_regions": weak_regions[:4],
            "stats": stats,
        }
        return analysis

    def save_analysis_artifacts(
        self,
        program: GCodeProgram,
        output_dir: str,
        *,
        creative_mode: str = "figurative",
        plan: Optional[Any] = None,
        prefix: str = "analysis",
    ) -> Dict[str, Any]:
        """Render preview plus region-analysis artifacts and return a summary."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        preview_path = output_path / f"{prefix}_preview.png"
        overlay_path = output_path / f"{prefix}_overlay.png"
        heatmap_path = output_path / f"{prefix}_heatmap.png"
        json_path = output_path / f"{prefix}_report.json"

        lines, stats = self._trace(program)
        analysis = self.analyze_regions(program, creative_mode=creative_mode, plan=plan)
        self._render(lines, stats, str(preview_path))
        self._render_region_overlay(lines, analysis, str(overlay_path))
        self._render_density_heatmap(lines, analysis, str(heatmap_path))
        json_path.write_text(json.dumps(analysis, indent=2))

        return {
            "preview_path": str(preview_path),
            "overlay_path": str(overlay_path),
            "heatmap_path": str(heatmap_path),
            "json_path": str(json_path),
            "analysis": analysis,
        }

    def render_region_crop(
        self, program: GCodeProgram, region: Any, out_path: Optional[str] = None
    ) -> bytes:
        """Render only the region's cropped view to PNG bytes."""
        import io

        bounds = region.bounds if hasattr(region, "bounds") else region
        x0, y0, x1, y1 = bounds
        lines, _ = self._trace(program)
        fig, ax = plt.subplots(figsize=(self.fig_w, self.fig_h))
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.add_patch(
            Rectangle(
                (x0, y0),
                x1 - x0,
                y1 - y0,
                fill=False,
                edgecolor="green",
                linestyle=":",
                linewidth=1.5,
            )
        )
        draw_segs = []
        travel_segs = []
        for lx0, ly0, lx1, ly1, is_draw, *_ in lines:
            mx = (lx0 + lx1) / 2
            my = (ly0 + ly1) / 2
            if not (x0 <= mx <= x1 and y0 <= my <= y1):
                continue
            seg = ((lx0, ly0), (lx1, ly1))
            if is_draw:
                draw_segs.append(seg)
            else:
                travel_segs.append(seg)
        if travel_segs:
            ax.add_collection(
                LineCollection(travel_segs, colors=self.travel_color, linewidths=0.4, alpha=0.3)
            )
        if draw_segs:
            ax.add_collection(
                LineCollection(draw_segs, colors=self.draw_color, linewidths=self.line_width)
            )
        ax.set_title(f"Region {getattr(region, 'name', '') or ''}")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        png_bytes = buf.getvalue()
        if out_path:
            Path(out_path).write_bytes(png_bytes)
        return png_bytes

    def _trace(self, program: GCodeProgram):
        """Trace the program and collect line segments + stats."""
        x, y = 0.0, 0.0
        pen_down = False
        pen_color = None
        lines: List[Tuple[float, float, float, float, bool, Any]] = []
        draw_dist = 0.0
        travel_dist = 0.0
        pen_cycles = 0

        for cmd in program.commands:
            if cmd.command == "M3":
                pen_down = True
                pen_cycles += 1
                pen_color = getattr(cmd, "color", None)
            elif cmd.command == "M5":
                pen_down = False
            elif cmd.command in ("G0", "G1"):
                nx = cmd.x if cmd.x is not None else x
                ny = cmd.y if cmd.y is not None else y
                is_draw = pen_down and cmd.command == "G1"
                seg_color = getattr(cmd, "color", None)
                if seg_color is None:
                    seg_color = pen_color
                lines.append((x, y, nx, ny, is_draw, seg_color))
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
        paper_w = self.config.paper.x_extent if self.config else 210
        paper_h = self.config.paper.y_extent if self.config else 297
        margin = 10

        ax.set_xlim(-margin, paper_w + margin)
        ax.set_ylim(-margin, paper_h + margin)
        ax.set_aspect("equal")

        # Paper boundary (gray dashed)
        ax.add_patch(
            Rectangle(
                (0, 0), paper_w, paper_h, fill=False, edgecolor="gray", linestyle="--", alpha=0.5
            )
        )

        # Drawable area overlay (green dotted)
        if self.config:
            dx0, dy0, dx1, dy1 = self.config.paper.get_drawable_area()
            ax.add_patch(
                Rectangle(
                    (dx0, dy0),
                    dx1 - dx0,
                    dy1 - dy0,
                    fill=False,
                    edgecolor="green",
                    linestyle=":",
                    linewidth=1.5,
                    alpha=0.6,
                )
            )

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
                    oob = (
                        l[2] < 0
                        or l[2] > paper_w
                        or l[3] < 0
                        or l[3] > paper_h
                        or l[0] < 0
                        or l[0] > paper_w
                        or l[1] < 0
                        or l[1] > paper_h
                    )
                    if oob:
                        oob_segs.append(seg)
                    else:
                        draw_segs.append(seg)

            if travel_segs:
                lc = LineCollection(
                    travel_segs, colors=self.travel_color, linewidths=0.5, alpha=0.3
                )
                ax.add_collection(lc)
            if draw_segs:
                lc = LineCollection(draw_segs, colors=self.draw_color, linewidths=self.line_width)
                ax.add_collection(lc)
            if oob_segs:
                lc = LineCollection(
                    oob_segs, colors="red", linewidths=self.line_width * 1.5, alpha=0.8
                )
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
        ax.text(
            0.02,
            0.98,
            stats_text,
            transform=ax.transAxes,
            fontsize=8,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

        # Warning if out-of-bounds segments exist
        if lines and any(
            (
                l[4]
                and (
                    l[2] < 0
                    or l[2] > paper_w
                    or l[3] < 0
                    or l[3] > paper_h
                    or l[0] < 0
                    or l[0] > paper_w
                    or l[1] < 0
                    or l[1] > paper_h
                )
            )
            for l in lines
        ):
            ax.text(
                0.5,
                0.02,
                "WARNING: Out-of-bounds segments (red)",
                transform=ax.transAxes,
                fontsize=9,
                color="red",
                ha="center",
                va="bottom",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.9),
            )

        ax.set_title("PromptPlot Preview")
        ax.legend(loc="upper right", fontsize="small")
        fig.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)

    # Fallback color cycle for pen indices when the palette entry is not a
    # matplotlib-recognizable color (or the palette is shorter than #colors).
    _FALLBACK_COLORS = [
        "black",
        "#d62728",
        "#1f77b4",
        "#2ca02c",
        "#9467bd",
        "#ff7f0e",
        "#8c564b",
        "#e377c2",
        "#17becf",
        "#bcbd22",
    ]

    # Metallic / specialty pen names matplotlib doesn't know, mapped to hex.
    _COLOR_ALIASES = {
        "copper": "#b87333",
        "bronze": "#cd7f32",
        "silver": "#c0c0c0",
        "gold": "#d4af37",
        "brass": "#b5a642",
        "cream": "#fffdd0",
        "ivory": "#fffff0",
    }

    def _color_for_index(self, idx: int, palette: List[str]) -> str:
        from matplotlib.colors import is_color_like

        if palette and 0 <= idx < len(palette):
            name = palette[idx]
            alias = self._COLOR_ALIASES.get(name.strip().lower())
            if alias:
                return alias
            if is_color_like(name):
                return name
        return self._FALLBACK_COLORS[idx % len(self._FALLBACK_COLORS)]

    def _needs_dark_bg(self, palette: List[str]) -> bool:
        """True if any pen is light/metallic (would be invisible on white)."""
        from matplotlib.colors import to_rgb

        for i in range(len(palette or [])):
            try:
                r, g, b = to_rgb(self._color_for_index(i, palette))
            except Exception:
                continue
            if 0.299 * r + 0.587 * g + 0.114 * b > 0.72:  # relative luminance
                return True
        return False

    def _render_color_layers(self, lines, stats, output_path: str, palette: List[str]):
        """Render a multi-color program with one color per pen layer + legend."""
        fig, ax = plt.subplots(figsize=(self.fig_w, self.fig_h))
        paper_w = self.config.paper.x_extent if self.config else 210
        paper_h = self.config.paper.y_extent if self.config else 297
        margin = 10
        dark = self._needs_dark_bg(palette)
        if dark:
            # Simulate dark paper so white/metallic pens are visible.
            fig.patch.set_facecolor("#333333")
            ax.set_facecolor("#2b2b2b")
        ax.set_xlim(-margin, paper_w + margin)
        ax.set_ylim(-margin, paper_h + margin)
        ax.set_aspect("equal")
        ax.add_patch(
            Rectangle(
                (0, 0), paper_w, paper_h, fill=False,
                edgecolor="lightgray" if dark else "gray", linestyle="--", alpha=0.5
            )
        )
        if self.config:
            dx0, dy0, dx1, dy1 = self.config.paper.get_drawable_area()
            ax.add_patch(
                Rectangle(
                    (dx0, dy0),
                    dx1 - dx0,
                    dy1 - dy0,
                    fill=False,
                    edgecolor="green",
                    linestyle=":",
                    linewidth=1.5,
                    alpha=0.6,
                )
            )

        travel_segs = []
        by_color: Dict[int, list] = {}
        for l in lines:
            seg = ((l[0], l[1]), (l[2], l[3]))
            if not l[4]:
                travel_segs.append(seg)
            else:
                ci = l[5] if (len(l) > 5 and l[5] is not None) else 0
                by_color.setdefault(ci, []).append(seg)

        if travel_segs:
            ax.add_collection(
                LineCollection(travel_segs, colors=self.travel_color, linewidths=0.4, alpha=0.25)
            )
        for ci in sorted(by_color):
            color = self._color_for_index(ci, palette)
            label = palette[ci] if (palette and ci < len(palette)) else f"color {ci}"
            ax.add_collection(
                LineCollection(
                    by_color[ci],
                    colors=color,
                    linewidths=self.line_width,
                    label=f"{ci}: {label}",
                )
            )

        stats_text = (
            f"Draw: {stats['drawing_distance']:.1f} mm\n"
            f"Travel: {stats['travel_distance']:.1f} mm\n"
            f"Colors: {len(by_color)}\n"
            f"Commands: {stats['total_commands']}"
        )
        ax.text(
            0.02,
            0.98,
            stats_text,
            transform=ax.transAxes,
            fontsize=8,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )
        ax.set_title("PromptPlot Preview — color layers")
        ax.legend(loc="upper right", fontsize="small", title="pen")
        fig.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)

    def _build_regions(self, plan: Optional[Any]) -> List[Dict[str, Any]]:
        paper_w = self.config.paper.x_extent if self.config else 210.0
        paper_h = self.config.paper.y_extent if self.config else 297.0
        if plan is not None and hasattr(plan, "regions"):
            built = []
            for idx, region in enumerate(plan.regions, 1):
                built.append(
                    {
                        "name": getattr(region, "name", f"region_{idx}"),
                        "role": getattr(region, "role", "support"),
                        "x": float(getattr(region, "x", 0.0)),
                        "y": float(getattr(region, "y", 0.0)),
                        "width": float(getattr(region, "width", paper_w / 2)),
                        "height": float(getattr(region, "height", paper_h / 2)),
                    }
                )
            if built:
                return built
        # Fallback 2x2 grid
        half_w = paper_w / 2
        half_h = paper_h / 2
        return [
            {
                "name": "grid_top_left",
                "role": "support",
                "x": 0.0,
                "y": half_h,
                "width": half_w,
                "height": half_h,
            },
            {
                "name": "grid_top_right",
                "role": "support",
                "x": half_w,
                "y": half_h,
                "width": half_w,
                "height": half_h,
            },
            {
                "name": "grid_bottom_left",
                "role": "support",
                "x": 0.0,
                "y": 0.0,
                "width": half_w,
                "height": half_h,
            },
            {
                "name": "grid_bottom_right",
                "role": "support",
                "x": half_w,
                "y": 0.0,
                "width": half_w,
                "height": half_h,
            },
        ]

    @staticmethod
    def _point_in_region(x: float, y: float, region: Dict[str, Any]) -> bool:
        return (
            region["x"] <= x <= region["x"] + region["width"]
            and region["y"] <= y <= region["y"] + region["height"]
        )

    @staticmethod
    def _region_issue(
        region: Dict[str, Any], density: float, segment_count: int, creative_mode: str
    ) -> Dict[str, Any]:
        role = region.get("role", "support")
        if role == "void" and density > 0.03:
            return {
                "issue": "overfilled_void",
                "severity": min(1.0, density / 0.08),
                "recommended_change": "reduce density and preserve more paper",
            }
        if role in {"focal", "subject"} and segment_count < 3:
            return {
                "issue": "weak_focal_region",
                "severity": 0.7,
                "recommended_change": "add stronger structure and contrast",
            }
        if creative_mode == "abstract" and density < 0.005 and role != "void":
            return {
                "issue": "underpowered_field",
                "severity": 0.55,
                "recommended_change": "increase density or introduce a stronger field family",
            }
        if (
            creative_mode in {"figurative", "hybrid"}
            and role in {"subject", "support"}
            and density < 0.004
        ):
            return {
                "issue": "weak_readability_region",
                "severity": 0.5,
                "recommended_change": "strengthen silhouette or contour clarity",
            }
        return {"issue": "stable", "severity": 0.0, "recommended_change": "preserve"}

    @staticmethod
    def _center_clustering_hint(
        drawing_lines: List[Tuple[float, float, float, float, bool]],
    ) -> float:
        if not drawing_lines:
            return 0.0
        center_hits = 0
        for x0, y0, x1, y1, _is_draw, *_ in drawing_lines:
            mx = (x0 + x1) / 2
            my = (y0 + y1) / 2
            if 70 <= mx <= 140 and 100 <= my <= 200:
                center_hits += 1
        return round(center_hits / len(drawing_lines), 6)

    def _setup_axes(self):
        fig, ax = plt.subplots(figsize=(self.fig_w, self.fig_h))
        paper_w = self.config.paper.x_extent if self.config else 210
        paper_h = self.config.paper.y_extent if self.config else 297
        margin = 10
        ax.set_xlim(-margin, paper_w + margin)
        ax.set_ylim(-margin, paper_h + margin)
        ax.set_aspect("equal")
        ax.add_patch(
            Rectangle(
                (0, 0), paper_w, paper_h, fill=False, edgecolor="gray", linestyle="--", alpha=0.5
            )
        )
        return fig, ax, paper_w, paper_h

    def _render_region_overlay(self, lines, analysis: Dict[str, Any], output_path: str):
        fig, ax, _, _ = self._setup_axes()
        draw_segs = [((l[0], l[1]), (l[2], l[3])) for l in lines if l[4]]
        if draw_segs:
            ax.add_collection(
                LineCollection(draw_segs, colors=self.draw_color, linewidths=self.line_width)
            )
        for region in analysis["regions"]:
            severity = region["severity"]
            color = "red" if severity > 0.5 else ("orange" if severity > 0.2 else "green")
            ax.add_patch(
                Rectangle(
                    (region["x"], region["y"]),
                    region["width"],
                    region["height"],
                    fill=False,
                    edgecolor=color,
                    linewidth=1.5,
                    alpha=0.8,
                )
            )
            ax.text(
                region["x"] + 2,
                region["y"] + region["height"] - 4,
                region["name"],
                fontsize=7,
                color=color,
            )
        ax.set_title("PromptPlot Region Overlay")
        fig.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)

    def _render_density_heatmap(self, lines, analysis: Dict[str, Any], output_path: str):
        fig, ax, _, _ = self._setup_axes()
        max_density = max((region["density"] for region in analysis["regions"]), default=1.0) or 1.0
        for region in analysis["regions"]:
            intensity = min(1.0, region["density"] / max_density)
            ax.add_patch(
                Rectangle(
                    (region["x"], region["y"]),
                    region["width"],
                    region["height"],
                    facecolor=(1.0, 0.2, 0.2, max(0.1, intensity)),
                    edgecolor="black",
                    linewidth=0.5,
                )
            )
        draw_segs = [((l[0], l[1]), (l[2], l[3])) for l in lines if l[4]]
        if draw_segs:
            ax.add_collection(
                LineCollection(
                    draw_segs, colors="white", linewidths=max(self.line_width * 0.7, 0.5), alpha=0.8
                )
            )
        ax.set_title("PromptPlot Density Heatmap")
        fig.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
