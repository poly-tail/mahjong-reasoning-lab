from __future__ import annotations

import csv
import math
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Hashable, Iterable, Mapping, Sequence

# Shared DB-analysis defaults live here so every graph preset uses the same baseline.
DEFAULT_EXCLUDED_PLAYERS = ("パシフィック", "s6u")
# THINKING_TIME_MIN_MS の定義。
THINKING_TIME_MIN_MS = 900.0
# THINKING_TIME_MAX_MS の定義。
THINKING_TIME_MAX_MS = 8000.0
# Lag shorter than this is treated as system-side delay during DB-side lag analysis.
LAG_DELAY_ANALYSIS_MIN_MS = 550.0
# DEFAULT_HISTOGRAM_BIN_WIDTH の定義。
DEFAULT_HISTOGRAM_BIN_WIDTH = 500.0

# GraphRecord の型定義。
GraphRecord = dict[str, object]
# DatasetBuilder の型定義。
DatasetBuilder = Callable[[Path, Sequence[str]], list[GraphRecord]]


@dataclass(frozen=True)
class NumericFieldFilter:
    """One numeric include-range applied before graph samples are built."""

    # field_name を保持する。
    field_name: str
    # min_exclusive を保持する。
    min_exclusive: float | None = None
    # max_exclusive を保持する。
    max_exclusive: float | None = None


@dataclass(frozen=True)
class DatasetDefinition:
    """A user-editable data-source definition.

    `build_records()` can derive any dynamic subset, such as "ryanmen-fixed discards only".
    """

    # name を保持する。
    name: str
    # description を保持する。
    description: str
    # build_records を保持する。
    build_records: DatasetBuilder


@dataclass(frozen=True)
class GraphDefinition:
    """One graph preset bound to one dataset plus x/y field names."""

    # name を保持する。
    name: str
    # description を保持する。
    description: str
    # dataset_name を保持する。
    dataset_name: str
    # kind を保持する。
    kind: str
    # x_field を保持する。
    x_field: str
    # y_field を保持する。
    y_field: str | None = None
    # output_filename を保持する。
    output_filename: str = ""
    # title を保持する。
    title: str = ""
    # subtitle を保持する。
    subtitle: str = ""
    # x_label を保持する。
    x_label: str = ""
    # y_label を保持する。
    y_label: str = ""
    # numeric_filters の並びを保持する。
    numeric_filters: tuple[NumericFieldFilter, ...] = ()
    # histogram_bin_width を保持する。
    histogram_bin_width: float = DEFAULT_HISTOGRAM_BIN_WIDTH
    # include_regression を保持する。
    include_regression: bool = False


@dataclass(frozen=True)
class AnalysisDefinition:
    """A named bundle of graph presets written to one output directory."""

    # name を保持する。
    name: str
    # description を保持する。
    description: str
    # graph_names の並びを保持する。
    graph_names: tuple[str, ...]
    # output_subdir を保持する。
    output_subdir: str


@dataclass(frozen=True)
class RegressionResult:
    """Linear regression summary for scatter plots."""

    # slope を保持する。
    slope: float
    # intercept を保持する。
    intercept: float
    # correlation を保持する。
    correlation: float | None


@dataclass(frozen=True)
class GeneratedGraph:
    """Result metadata for one rendered graph."""

    # graph_name を保持する。
    graph_name: str
    # dataset_name を保持する。
    dataset_name: str
    # kind を保持する。
    kind: str
    # sample_count を保持する。
    sample_count: int
    # output_path を保持する。
    output_path: Path | None
    # message を保持する。
    message: str
    # regression を保持する。
    regression: RegressionResult | None = None


def parse_optional_float(value: object) -> float | None:
    """Parse one CSV cell as float while treating blanks as missing values."""

    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        parsed = float(normalized)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def parse_optional_int(value: object) -> int | None:
    """Parse one CSV cell as int, accepting `2` and `2.0` only."""

    parsed = parse_optional_float(value)
    if parsed is None:
        return None
    rounded = int(parsed)
    if abs(parsed - rounded) > 1e-9:
        return None
    return rounded


def is_truthy_flag(value: object) -> bool:
    """Interpret DB flag columns such as `1` / `true` as enabled."""

    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def iter_discard_fact_paths(db_dir: Path) -> list[Path]:
    """Return monthly discard_fact CSV chunks sorted by filename."""

    return sorted(path for path in db_dir.glob("discard_fact_*.csv") if path.is_file())


def _is_round_opening_discard_id(discard_id: object) -> bool:
    """Return whether one discard_id points at the round's opening discard."""

    normalized = "" if discard_id is None else str(discard_id).strip()
    prefix, separator, suffix = normalized.rpartition("_")
    return bool(prefix and separator and suffix == "000")


def _normalize_discard_fact_row_for_analysis(row: Mapping[str, str]) -> dict[str, str]:
    """Apply shared analysis-side cleanup to one discard_fact row."""

    normalized = {key: value for key, value in row.items()}
    if _is_round_opening_discard_id(normalized.get("discard_id")):
        normalized["thinking_time_ms"] = ""
        normalized["thinking_time_before_reach_ms"] = ""
    return normalized


def iter_discard_fact_rows(db_dir: Path) -> Iterable[dict[str, str]]:
    """Yield discard_fact rows across every monthly CSV chunk."""

    for csv_path in iter_discard_fact_paths(db_dir):
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield _normalize_discard_fact_row_for_analysis(row)


def _coerce_numeric(value: object) -> float | None:
    """Return a numeric graph value as float, or None when the cell is blank/non-numeric."""

    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    return parse_optional_float(value)


def _passes_numeric_filters(
    record: Mapping[str, object],
    filters: Sequence[NumericFieldFilter],
) -> bool:
    """Apply every numeric include-range to one record."""

    for numeric_filter in filters:
        value = _coerce_numeric(record.get(numeric_filter.field_name))
        if value is None:
            return False
        if numeric_filter.min_exclusive is not None and value <= numeric_filter.min_exclusive:
            return False
        if numeric_filter.max_exclusive is not None and value >= numeric_filter.max_exclusive:
            return False
    return True


def _format_svg_text(value: object) -> str:
    """Escape plain text for inline SVG output."""

    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _svg_header(width: int, height: int) -> str:
    """Return the shared SVG header."""

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        '<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>'
    )


def _build_axis_ticks(min_value: float, max_value: float, tick_count: int) -> list[float]:
    """Return evenly spaced axis ticks while protecting zero-width ranges."""

    if tick_count <= 1:
        return [min_value]
    if math.isclose(min_value, max_value):
        return [min_value for _ in range(tick_count)]
    span = max_value - min_value
    return [min_value + span * index / (tick_count - 1) for index in range(tick_count)]


def _build_regression(points: Sequence[tuple[float, float]]) -> RegressionResult | None:
    """Return regression coefficients when the scatter has enough x variation."""

    if len(points) < 2:
        return None
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    if len(set(x_values)) < 2:
        return None
    try:
        slope, intercept = statistics.linear_regression(x_values, y_values)
    except statistics.StatisticsError:
        return None
    try:
        correlation = statistics.correlation(x_values, y_values)
    except statistics.StatisticsError:
        correlation = None
    return RegressionResult(
        slope=float(slope),
        intercept=float(intercept),
        correlation=float(correlation) if correlation is not None else None,
    )


def _build_scatter_svg(
    points: Sequence[tuple[float, float]],
    regression: RegressionResult | None,
    *,
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
) -> str:
    """Render an x/y scatter plot with an optional regression line."""

    width = 900
    height = 560
    margin_left = 88
    margin_right = 28
    margin_top = 72
    margin_bottom = 72
    plot_left = margin_left
    plot_top = margin_top
    plot_right = width - margin_right
    plot_bottom = height - margin_bottom
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = max(0.0, min(y_values) - 200.0)
    y_max = max(y_values) + 200.0
    if math.isclose(x_min, x_max):
        x_min -= 0.5
        x_max += 0.5
    if math.isclose(y_min, y_max):
        y_max = y_min + 1.0

    def _map_x(value: float) -> float:
        return plot_left + (value - x_min) / (x_max - x_min) * plot_width

    def _map_y(value: float) -> float:
        return plot_bottom - (value - y_min) / (y_max - y_min) * plot_height

    parts = [_svg_header(width, height)]
    parts.append(f'<text x="{width / 2:.1f}" y="28" font-size="22" text-anchor="middle" fill="#111827">{_format_svg_text(title)}</text>')
    parts.append(f'<text x="{width / 2:.1f}" y="50" font-size="12" text-anchor="middle" fill="#4b5563">{_format_svg_text(subtitle)}</text>')
    parts.append(f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" height="{plot_height}" fill="#f8fafc" stroke="#cbd5e1"/>')

    for tick in _build_axis_ticks(y_min, y_max, 6):
        y = _map_y(tick)
        parts.append(f'<line x1="{plot_left}" y1="{y:.2f}" x2="{plot_right}" y2="{y:.2f}" stroke="#e5e7eb" />')
        parts.append(f'<text x="{plot_left - 10}" y="{y + 4:.2f}" font-size="11" text-anchor="end" fill="#475569">{int(round(tick))}</text>')

    unique_x_ticks = sorted(set(x_values))
    for tick in unique_x_ticks:
        x = _map_x(tick)
        label = int(tick) if math.isclose(tick, round(tick)) else round(tick, 2)
        parts.append(f'<line x1="{x:.2f}" y1="{plot_top}" x2="{x:.2f}" y2="{plot_bottom}" stroke="#eef2f7" />')
        parts.append(f'<text x="{x:.2f}" y="{plot_bottom + 24}" font-size="11" text-anchor="middle" fill="#475569">{label}</text>')

    parts.append(f'<line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="#334155" />')
    parts.append(f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_bottom}" stroke="#334155" />')
    parts.append(f'<text x="{(plot_left + plot_right) / 2:.1f}" y="{height - 20}" font-size="13" text-anchor="middle" fill="#111827">{_format_svg_text(x_label)}</text>')
    parts.append(
        f'<text x="24" y="{(plot_top + plot_bottom) / 2:.1f}" font-size="13" text-anchor="middle" fill="#111827" '
        f'transform="rotate(-90 24 {(plot_top + plot_bottom) / 2:.1f})">{_format_svg_text(y_label)}</text>'
    )

    for x_value, y_value in points:
        parts.append(
            f'<circle cx="{_map_x(x_value):.2f}" cy="{_map_y(y_value):.2f}" r="4.2" '
            f'fill="#2563eb" fill-opacity="0.72" stroke="#1d4ed8" stroke-width="1"/>'
        )

    if regression is not None:
        line_x0 = min(x_values)
        line_x1 = max(x_values)
        line_y0 = regression.slope * line_x0 + regression.intercept
        line_y1 = regression.slope * line_x1 + regression.intercept
        parts.append(
            f'<line x1="{_map_x(line_x0):.2f}" y1="{_map_y(line_y0):.2f}" '
            f'x2="{_map_x(line_x1):.2f}" y2="{_map_y(line_y1):.2f}" '
            f'stroke="#dc2626" stroke-width="2.5"/>'
        )
        correlation_text = (
            f"r={regression.correlation:.3f}"
            if regression.correlation is not None
            else "r=n/a"
        )
        parts.append(
            f'<text x="{plot_right - 8}" y="{plot_top + 18}" font-size="12" text-anchor="end" fill="#991b1b">'
            f'{_format_svg_text(f"y = {regression.slope:.2f}x + {regression.intercept:.2f} / {correlation_text}")}'
            "</text>"
        )

    parts.append("</svg>")
    return "".join(parts)


def _build_histogram_svg(
    samples: Sequence[float],
    *,
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
    bin_width: float,
) -> str:
    """Render a continuous-value histogram."""

    width = 900
    height = 520
    margin_left = 72
    margin_right = 28
    margin_top = 72
    margin_bottom = 68
    plot_left = margin_left
    plot_top = margin_top
    plot_right = width - margin_right
    plot_bottom = height - margin_bottom
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    sample_min = min(samples)
    sample_max = max(samples)
    bin_start = math.floor(sample_min / bin_width) * bin_width
    bin_end = math.ceil(sample_max / bin_width) * bin_width
    if math.isclose(bin_start, bin_end):
        bin_end = bin_start + bin_width
    bin_count = max(1, int(round((bin_end - bin_start) / bin_width)))
    bins = [0] * bin_count
    for sample in samples:
        index = int((sample - bin_start) // bin_width)
        if index >= bin_count:
            index = bin_count - 1
        bins[index] += 1
    max_count = max(bins) if bins else 1

    parts = [_svg_header(width, height)]
    parts.append(f'<text x="{width / 2:.1f}" y="28" font-size="22" text-anchor="middle" fill="#111827">{_format_svg_text(title)}</text>')
    parts.append(f'<text x="{width / 2:.1f}" y="50" font-size="12" text-anchor="middle" fill="#4b5563">{_format_svg_text(subtitle)}</text>')
    parts.append(f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" height="{plot_height}" fill="#f8fafc" stroke="#cbd5e1"/>')

    for tick in range(0, max_count + 1):
        if max_count > 5 and tick not in {0, max_count} and tick % max(1, math.ceil(max_count / 5)) != 0:
            continue
        y = plot_bottom - (tick / max_count) * plot_height if max_count > 0 else plot_bottom
        parts.append(f'<line x1="{plot_left}" y1="{y:.2f}" x2="{plot_right}" y2="{y:.2f}" stroke="#e5e7eb" />')
        parts.append(f'<text x="{plot_left - 10}" y="{y + 4:.2f}" font-size="11" text-anchor="end" fill="#475569">{tick}</text>')

    bar_gap = 4.0
    bar_width = max(8.0, plot_width / max(bin_count, 1) - bar_gap)
    for index, count in enumerate(bins):
        bar_left = plot_left + index * (plot_width / max(bin_count, 1)) + bar_gap / 2
        bar_height = 0.0 if max_count <= 0 else (count / max_count) * plot_height
        bar_top = plot_bottom - bar_height
        parts.append(
            f'<rect x="{bar_left:.2f}" y="{bar_top:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" '
            f'fill="#2563eb" fill-opacity="0.78" stroke="#1d4ed8"/>'
        )
        label = f"{int(bin_start + index * bin_width)}"
        x = bar_left + bar_width / 2
        parts.append(f'<text x="{x:.2f}" y="{plot_bottom + 20:.2f}" font-size="10" text-anchor="middle" fill="#475569">{label}</text>')

    parts.append(f'<line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="#334155" />')
    parts.append(f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_bottom}" stroke="#334155" />')
    parts.append(f'<text x="{(plot_left + plot_right) / 2:.1f}" y="{height - 20}" font-size="13" text-anchor="middle" fill="#111827">{_format_svg_text(x_label)}</text>')
    parts.append(
        f'<text x="24" y="{(plot_top + plot_bottom) / 2:.1f}" font-size="13" text-anchor="middle" fill="#111827" '
        f'transform="rotate(-90 24 {(plot_top + plot_bottom) / 2:.1f})">{_format_svg_text(y_label)}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _build_discrete_bar_svg(
    counts_by_value: Sequence[tuple[Hashable, int]],
    *,
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
) -> str:
    """Render a discrete-value count chart."""

    width = 860
    height = 500
    margin_left = 72
    margin_right = 28
    margin_top = 72
    margin_bottom = 68
    plot_left = margin_left
    plot_top = margin_top
    plot_right = width - margin_right
    plot_bottom = height - margin_bottom
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top
    max_count = max(count for _value, count in counts_by_value)

    parts = [_svg_header(width, height)]
    parts.append(f'<text x="{width / 2:.1f}" y="28" font-size="22" text-anchor="middle" fill="#111827">{_format_svg_text(title)}</text>')
    parts.append(f'<text x="{width / 2:.1f}" y="50" font-size="12" text-anchor="middle" fill="#4b5563">{_format_svg_text(subtitle)}</text>')
    parts.append(f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" height="{plot_height}" fill="#f8fafc" stroke="#cbd5e1"/>')

    for tick in range(0, max_count + 1):
        if max_count > 5 and tick not in {0, max_count} and tick % max(1, math.ceil(max_count / 5)) != 0:
            continue
        y = plot_bottom - (tick / max_count) * plot_height if max_count > 0 else plot_bottom
        parts.append(f'<line x1="{plot_left}" y1="{y:.2f}" x2="{plot_right}" y2="{y:.2f}" stroke="#e5e7eb" />')
        parts.append(f'<text x="{plot_left - 10}" y="{y + 4:.2f}" font-size="11" text-anchor="end" fill="#475569">{tick}</text>')

    column_width = plot_width / max(len(counts_by_value), 1)
    bar_width = max(16.0, column_width - 12.0)
    for index, (value, count) in enumerate(counts_by_value):
        bar_left = plot_left + index * column_width + (column_width - bar_width) / 2
        bar_height = 0.0 if max_count <= 0 else (count / max_count) * plot_height
        bar_top = plot_bottom - bar_height
        parts.append(
            f'<rect x="{bar_left:.2f}" y="{bar_top:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" '
            f'fill="#0f766e" fill-opacity="0.82" stroke="#115e59"/>'
        )
        x = bar_left + bar_width / 2
        parts.append(f'<text x="{x:.2f}" y="{plot_bottom + 20:.2f}" font-size="11" text-anchor="middle" fill="#475569">{_format_svg_text(value)}</text>')
        parts.append(f'<text x="{x:.2f}" y="{bar_top - 6:.2f}" font-size="10" text-anchor="middle" fill="#0f172a">{count}</text>')

    parts.append(f'<line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="#334155" />')
    parts.append(f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_bottom}" stroke="#334155" />')
    parts.append(f'<text x="{(plot_left + plot_right) / 2:.1f}" y="{height - 20}" font-size="13" text-anchor="middle" fill="#111827">{_format_svg_text(x_label)}</text>')
    parts.append(
        f'<text x="24" y="{(plot_top + plot_bottom) / 2:.1f}" font-size="13" text-anchor="middle" fill="#111827" '
        f'transform="rotate(-90 24 {(plot_top + plot_bottom) / 2:.1f})">{_format_svg_text(y_label)}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _write_text(path: Path, text: str) -> None:
    """Write one UTF-8 text file, creating parent directories when needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sample_scatter_points(
    records: Sequence[Mapping[str, object]],
    graph_definition: GraphDefinition,
) -> list[tuple[float, float]]:
    """Build scatter samples from x/y field names plus numeric filters."""

    points: list[tuple[float, float]] = []
    for record in records:
        if not _passes_numeric_filters(record, graph_definition.numeric_filters):
            continue
        x_value = _coerce_numeric(record.get(graph_definition.x_field))
        y_value = _coerce_numeric(record.get(graph_definition.y_field or ""))
        if x_value is None or y_value is None:
            continue
        points.append((x_value, y_value))
    return points


def _sample_numeric_values(
    records: Sequence[Mapping[str, object]],
    graph_definition: GraphDefinition,
) -> list[float]:
    """Build one numeric series from one x field plus filters."""

    values: list[float] = []
    for record in records:
        if not _passes_numeric_filters(record, graph_definition.numeric_filters):
            continue
        value = _coerce_numeric(record.get(graph_definition.x_field))
        if value is None:
            continue
        values.append(value)
    return values


def _sample_discrete_values(
    records: Sequence[Mapping[str, object]],
    graph_definition: GraphDefinition,
) -> list[Hashable]:
    """Build one discrete series from one x field plus filters."""

    values: list[Hashable] = []
    for record in records:
        if not _passes_numeric_filters(record, graph_definition.numeric_filters):
            continue
        value = record.get(graph_definition.x_field)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if not isinstance(value, Hashable):
            continue
        values.append(value)
    return values


def _sort_discrete_counts(counts_by_value: Mapping[Hashable, int]) -> list[tuple[Hashable, int]]:
    """Sort discrete counts numerically when possible, otherwise by text."""

    def _sort_key(item: tuple[Hashable, int]) -> tuple[int, object]:
        value = item[0]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return (0, float(value))
        numeric = parse_optional_float(value)
        if numeric is not None:
            return (0, numeric)
        return (1, str(value))

    return sorted(counts_by_value.items(), key=_sort_key)


def render_graph_definition(
    graph_definition: GraphDefinition,
    dataset_records: Sequence[Mapping[str, object]],
    output_dir: Path,
) -> GeneratedGraph:
    """Render one graph preset into one SVG file."""

    output_filename = graph_definition.output_filename or f"{graph_definition.name}.svg"
    output_path = output_dir / output_filename
    title = graph_definition.title or graph_definition.name
    subtitle = graph_definition.subtitle or graph_definition.description
    x_label = graph_definition.x_label or graph_definition.x_field
    y_label = graph_definition.y_label or (graph_definition.y_field or "count")

    if graph_definition.kind == "scatter":
        points = _sample_scatter_points(dataset_records, graph_definition)
        if not points:
            return GeneratedGraph(
                graph_name=graph_definition.name,
                dataset_name=graph_definition.dataset_name,
                kind=graph_definition.kind,
                sample_count=0,
                output_path=None,
                message="フィルタ後に散布図サンプルが無かったため未生成。",
            )
        regression = _build_regression(points) if graph_definition.include_regression else None
        svg_text = _build_scatter_svg(
            points,
            regression,
            title=title,
            subtitle=subtitle,
            x_label=x_label,
            y_label=y_label,
        )
        _write_text(output_path, svg_text)
        return GeneratedGraph(
            graph_name=graph_definition.name,
            dataset_name=graph_definition.dataset_name,
            kind=graph_definition.kind,
            sample_count=len(points),
            output_path=output_path,
            message="散布図を生成。",
            regression=regression,
        )

    if graph_definition.kind == "histogram":
        values = _sample_numeric_values(dataset_records, graph_definition)
        if not values:
            return GeneratedGraph(
                graph_name=graph_definition.name,
                dataset_name=graph_definition.dataset_name,
                kind=graph_definition.kind,
                sample_count=0,
                output_path=None,
                message="フィルタ後にヒストグラム用サンプルが無かったため未生成。",
            )
        svg_text = _build_histogram_svg(
            values,
            title=title,
            subtitle=subtitle,
            x_label=x_label,
            y_label=y_label,
            bin_width=graph_definition.histogram_bin_width,
        )
        _write_text(output_path, svg_text)
        return GeneratedGraph(
            graph_name=graph_definition.name,
            dataset_name=graph_definition.dataset_name,
            kind=graph_definition.kind,
            sample_count=len(values),
            output_path=output_path,
            message="ヒストグラムを生成。",
        )

    if graph_definition.kind == "discrete_bar":
        values = _sample_discrete_values(dataset_records, graph_definition)
        if not values:
            return GeneratedGraph(
                graph_name=graph_definition.name,
                dataset_name=graph_definition.dataset_name,
                kind=graph_definition.kind,
                sample_count=0,
                output_path=None,
                message="フィルタ後にカテゴリ分布サンプルが無かったため未生成。",
            )
        counts_by_value = _sort_discrete_counts(Counter(values))
        svg_text = _build_discrete_bar_svg(
            counts_by_value,
            title=title,
            subtitle=subtitle,
            x_label=x_label,
            y_label=y_label,
        )
        _write_text(output_path, svg_text)
        return GeneratedGraph(
            graph_name=graph_definition.name,
            dataset_name=graph_definition.dataset_name,
            kind=graph_definition.kind,
            sample_count=len(values),
            output_path=output_path,
            message="カテゴリ分布グラフを生成。",
        )

    raise ValueError(f"未対応のグラフ種類です: {graph_definition.kind}")


def _build_summary_markdown(
    *,
    analysis_name: str,
    analysis_description: str,
    db_dir: Path,
    output_dir: Path,
    excluded_players: Sequence[str],
    dataset_counts: Mapping[str, int],
    generated_graphs: Sequence[GeneratedGraph],
) -> str:
    """1 回のグラフ分析実行に対する簡潔な markdown レポートを作る。"""

    lines = [
        f"# {analysis_name}",
        "",
        analysis_description,
        "",
        f"- 生成時刻: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- DB ディレクトリ: `{db_dir}`",
        f"- 出力先: `{output_dir}`",
        f"- 除外プレイヤー: `{', '.join(excluded_players)}`",
        "",
        "## データセット",
        "",
    ]

    for dataset_name, sample_count in dataset_counts.items():
        lines.append(f"- `{dataset_name}`: `{sample_count}` 行")

    lines.extend(["", "## グラフ", ""])
    for generated_graph in generated_graphs:
        output_text = generated_graph.output_path.name if generated_graph.output_path is not None else "未生成"
        lines.append(
            f"- `{generated_graph.graph_name}` ({generated_graph.kind} / {generated_graph.sample_count}件): "
            f"`{output_text}` - {generated_graph.message}"
        )

    regression_graphs = [graph for graph in generated_graphs if graph.regression is not None]
    if regression_graphs:
        lines.extend(["", "## 回帰直線", ""])
        for generated_graph in regression_graphs:
            regression = generated_graph.regression
            correlation_text = (
                f"{regression.correlation:.4f}"
                if regression is not None and regression.correlation is not None
                else "-"
            )
            lines.append(f"### {generated_graph.graph_name}")
            lines.append("")
            lines.append(f"- 傾き: `{regression.slope:.4f}`")
            lines.append(f"- 切片: `{regression.intercept:.4f}`")
            lines.append(f"- 相関係数: `{correlation_text}`")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def run_analysis_definition(
    analysis_definition: AnalysisDefinition,
    dataset_definitions: Mapping[str, DatasetDefinition],
    graph_definitions: Mapping[str, GraphDefinition],
    db_dir: Path,
    output_dir: Path,
    *,
    excluded_players: Sequence[str],
) -> list[GeneratedGraph]:
    """Resolve datasets once, render every graph in one analysis bundle, and write summary.md."""

    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_cache: dict[str, list[GraphRecord]] = {}
    dataset_counts: dict[str, int] = {}
    generated_graphs: list[GeneratedGraph] = []

    for graph_name in analysis_definition.graph_names:
        if graph_name not in graph_definitions:
            raise ValueError(f"不明なグラフ定義です: {graph_name}")
        graph_definition = graph_definitions[graph_name]
        if graph_definition.dataset_name not in dataset_definitions:
            raise ValueError(f"不明なデータセット定義です: {graph_definition.dataset_name}")
        if graph_definition.dataset_name not in dataset_cache:
            dataset_records = dataset_definitions[graph_definition.dataset_name].build_records(
                db_dir,
                excluded_players,
            )
            dataset_cache[graph_definition.dataset_name] = dataset_records
            dataset_counts[graph_definition.dataset_name] = len(dataset_records)
        generated_graphs.append(
            render_graph_definition(
                graph_definition,
                dataset_cache[graph_definition.dataset_name],
                output_dir,
            )
        )

    summary_markdown = _build_summary_markdown(
        analysis_name=analysis_definition.name,
        analysis_description=analysis_definition.description,
        db_dir=db_dir,
        output_dir=output_dir,
        excluded_players=excluded_players,
        dataset_counts=dataset_counts,
        generated_graphs=generated_graphs,
    )
    _write_text(output_dir / "summary.md", summary_markdown)
    return generated_graphs
