from __future__ import annotations

import ast
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Hashable, Mapping, Sequence

from db_graph_framework import (
    DEFAULT_EXCLUDED_PLAYERS,
    RegressionResult,
    _build_axis_ticks,
    _build_discrete_bar_svg,
    _build_histogram_svg,
    _build_scatter_svg,
    _format_svg_text,
    _svg_header,
    _write_text,
    is_truthy_flag,
    iter_discard_fact_rows,
    parse_optional_float,
    parse_optional_int,
)
from db_graph_presets import DATASET_DEFINITIONS as PRESET_DATASET_DEFINITIONS

# GraphRecord の型定義。
GraphRecord = dict[str, object]

# SUPPORTED_GRAPH_KINDS の並びを定義する。
SUPPORTED_GRAPH_KINDS = (
    "scatter",
    "scatter_ci",
    "boxplot",
    "line",
    "histogram",
    "discrete_bar",
)
# SUPPORTED_LINE_AGGREGATIONS の並びを定義する。
SUPPORTED_LINE_AGGREGATIONS = ("raw", "mean", "median", "sum", "count", "min", "max")


@dataclass(frozen=True)
class RuntimeDatasetDefinition:
    """新CLIから使えるデータセット定義。"""

    # name を保持する。
    name: str
    # description を保持する。
    description: str
    # build_records を保持する。
    build_records: object


@dataclass(frozen=True)
class RuntimeGraphRequest:
    """CLI で確定した 1 回分のグラフ実行条件。"""

    # dataset_name を保持する。
    dataset_name: str
    # kind を保持する。
    kind: str
    # x_field を保持する。
    x_field: str
    # y_field を保持する。
    y_field: str | None
    # title を保持する。
    title: str
    # subtitle を保持する。
    subtitle: str
    # x_label を保持する。
    x_label: str
    # y_label を保持する。
    y_label: str
    # output_path を保持する。
    output_path: Path
    # include_regression を保持する。
    include_regression: bool
    # line_aggregation を保持する。
    line_aggregation: str
    # x_bin_width を保持する。
    x_bin_width: float | None
    # ci_confidence を保持する。
    ci_confidence: float
    # where_clauses の並びを保持する。
    where_clauses: tuple[str, ...]
    # derive_specs の並びを保持する。
    derive_specs: tuple[str, ...]
    # excluded_players の並びを保持する。
    excluded_players: tuple[str, ...]


@dataclass(frozen=True)
class GeneratedRuntimeGraph:
    """1 グラフ生成の結果メタデータ。"""

    # kind を保持する。
    kind: str
    # dataset_name を保持する。
    dataset_name: str
    # sample_count を保持する。
    sample_count: int
    # output_path を保持する。
    output_path: Path | None
    # message を保持する。
    message: str
    # regression を保持する。
    regression: RegressionResult | None = None


def _coerce_csv_value(value: object) -> object:
    """CSV セルをクエリしやすい Python 値へ寄せる。"""

    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    parsed_int = parse_optional_int(normalized)
    if parsed_int is not None:
        return parsed_int
    parsed_float = parse_optional_float(normalized)
    if parsed_float is not None:
        return parsed_float
    lowered = normalized.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return normalized


def build_discard_fact_all_dataset(
    db_dir: Path,
    excluded_players: Sequence[str],
) -> list[GraphRecord]:
    """`discard_fact` 全行を素直に読む既定データセット。"""

    excluded_name_set = {str(name).strip() for name in excluded_players if str(name).strip()}
    records: list[GraphRecord] = []
    for row in iter_discard_fact_rows(db_dir):
        player_name = str(row.get("player_name", "")).strip()
        if player_name and player_name in excluded_name_set:
            continue
        record: GraphRecord = {}
        for key, value in row.items():
            record[str(key)] = _coerce_csv_value(value)
        records.append(record)
    return records


def runtime_dataset_definitions() -> dict[str, RuntimeDatasetDefinition]:
    """raw dataset と preset dataset をまとめて返す。"""

    definitions: dict[str, RuntimeDatasetDefinition] = {
        "discard_fact_all": RuntimeDatasetDefinition(
            name="discard_fact_all",
            description="discard_fact 全行をそのまま読む既定データセット。",
            build_records=build_discard_fact_all_dataset,
        )
    }
    for dataset_name, dataset_definition in PRESET_DATASET_DEFINITIONS.items():
        definitions[dataset_name] = RuntimeDatasetDefinition(
            name=dataset_definition.name,
            description=dataset_definition.description,
            build_records=dataset_definition.build_records,
        )
    return definitions


class SafeExpressionEvaluator:
    """安全な範囲の式だけで派生列と where 条件を評価する。"""

    # _ALLOWED_FUNCTIONS の対応表。
    _ALLOWED_FUNCTIONS = {
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "len": len,
        "sum": sum,
        "str": lambda value: "" if value is None else str(value),
        "int": lambda value: 0 if value is None else int(float(value)),
        "float": lambda value: float(value),
        "num": lambda value: parse_optional_float(value),
        "flag": lambda value: is_truthy_flag(value),
        "text": lambda value: "" if value is None else str(value),
        "coalesce": lambda *values: next(
            (
                value
                for value in values
                if value is not None and (not isinstance(value, str) or value.strip())
            ),
            None,
        ),
        "contains": lambda value, part: str(part) in ("" if value is None else str(value)),
        "startswith": lambda value, prefix: ("" if value is None else str(value)).startswith(str(prefix)),
        "endswith": lambda value, suffix: ("" if value is None else str(value)).endswith(str(suffix)),
        "ceil": math.ceil,
        "floor": math.floor,
        "is_truthy": lambda value: is_truthy_flag(value),
    }

    def compile(self, expression: str) -> ast.AST:
        """式を parse して安全なノードだけに制限する。"""

        try:
            parsed = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"式の構文が不正です: {expression}") from exc
        self._validate_node(parsed)
        return parsed

    def evaluate(self, parsed: ast.AST, record: Mapping[str, object]) -> object:
        """検証済み式を 1 record に対して評価する。"""

        return self._eval_node(parsed.body, record)

    def _validate_node(self, node: ast.AST) -> None:
        """危険な AST ノードを事前に落とす。"""

        allowed_nodes = (
            ast.Expression,
            ast.Constant,
            ast.Name,
            ast.Load,
            ast.BoolOp,
            ast.BinOp,
            ast.UnaryOp,
            ast.Compare,
            ast.IfExp,
            ast.Call,
            ast.List,
            ast.Tuple,
            ast.Set,
        )
        allowed_ops = (
            ast.And,
            ast.Or,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.FloorDiv,
            ast.Mod,
            ast.Pow,
            ast.Eq,
            ast.NotEq,
            ast.Lt,
            ast.LtE,
            ast.Gt,
            ast.GtE,
            ast.In,
            ast.NotIn,
            ast.Is,
            ast.IsNot,
            ast.Not,
            ast.UAdd,
            ast.USub,
        )
        if isinstance(node, allowed_nodes):
            for child in ast.iter_child_nodes(node):
                self._validate_node(child)
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in self._ALLOWED_FUNCTIONS:
                    raise ValueError("許可されていない関数呼び出しです。")
            return
        if isinstance(node, allowed_ops):
            return
        raise ValueError(f"許可されていない式要素です: {type(node).__name__}")

    def _eval_node(self, node: ast.AST, record: Mapping[str, object]) -> object:
        """1 AST ノードを再帰評価する。"""

        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in {"True", "False", "None"}:
                return eval(node.id)
            return record.get(node.id)
        if isinstance(node, ast.List):
            return [self._eval_node(element, record) for element in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._eval_node(element, record) for element in node.elts)
        if isinstance(node, ast.Set):
            return {self._eval_node(element, record) for element in node.elts}
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(bool(self._eval_node(value, record)) for value in node.values)
            return any(bool(self._eval_node(value, record)) for value in node.values)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, record)
            if isinstance(node.op, ast.Not):
                return not bool(operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, record)
            right = self._eval_node(node.right, record)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Mod):
                return left % right
            if isinstance(node.op, ast.Pow):
                return left**right
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, record)
            for operator, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator, record)
                if isinstance(operator, ast.Eq):
                    result = left == right
                elif isinstance(operator, ast.NotEq):
                    result = left != right
                elif isinstance(operator, ast.Lt):
                    result = left < right
                elif isinstance(operator, ast.LtE):
                    result = left <= right
                elif isinstance(operator, ast.Gt):
                    result = left > right
                elif isinstance(operator, ast.GtE):
                    result = left >= right
                elif isinstance(operator, ast.In):
                    result = left in right
                elif isinstance(operator, ast.NotIn):
                    result = left not in right
                elif isinstance(operator, ast.Is):
                    result = left is right
                elif isinstance(operator, ast.IsNot):
                    result = left is not right
                else:
                    raise ValueError("未対応の比較演算子です。")
                if not result:
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return self._eval_node(node.body if bool(self._eval_node(node.test, record)) else node.orelse, record)
        if isinstance(node, ast.Call):
            function = self._ALLOWED_FUNCTIONS[node.func.id]
            args = [self._eval_node(argument, record) for argument in node.args]
            return function(*args)
        raise ValueError(f"未対応の式ノードです: {type(node).__name__}")


def _compile_assignments(assignments: Sequence[str], evaluator: SafeExpressionEvaluator) -> list[tuple[str, ast.AST]]:
    """`name=expr` 形式の派生列指定を parse する。"""

    compiled: list[tuple[str, ast.AST]] = []
    for assignment in assignments:
        if "=" not in assignment:
            raise ValueError(f"派生列指定は name=expr 形式で指定してください: {assignment}")
        field_name, expression = assignment.split("=", 1)
        normalized_name = field_name.strip()
        normalized_expression = expression.strip()
        if not normalized_name or not normalized_expression:
            raise ValueError(f"派生列指定が不正です: {assignment}")
        compiled.append((normalized_name, evaluator.compile(normalized_expression)))
    return compiled


def apply_query_pipeline(
    records: Sequence[Mapping[str, object]],
    *,
    derive_specs: Sequence[str],
    where_clauses: Sequence[str],
) -> list[GraphRecord]:
    """派生列付与と where 条件を順に適用する。"""

    evaluator = SafeExpressionEvaluator()
    compiled_derives = _compile_assignments(derive_specs, evaluator)
    compiled_wheres = [evaluator.compile(expression) for expression in where_clauses]

    output_records: list[GraphRecord] = []
    for index, record in enumerate(records):
        derived_record = dict(record)
        try:
            # 派生列は順番に評価し、後ろの式から前の派生列を参照できるようにする。
            for field_name, parsed_expression in compiled_derives:
                derived_record[field_name] = evaluator.evaluate(parsed_expression, derived_record)
            if compiled_wheres and not all(bool(evaluator.evaluate(parsed, derived_record)) for parsed in compiled_wheres):
                continue
        except Exception as exc:
            discard_id = derived_record.get("discard_id", f"row_{index}")
            raise ValueError(f"クエリ式の評価に失敗しました: record={discard_id} / {exc}") from exc
        output_records.append(derived_record)
    return output_records


def available_field_names(records: Sequence[Mapping[str, object]]) -> list[str]:
    """record 群に存在するフィールド名を返す。"""

    names: set[str] = set()
    for record in records:
        names.update(str(key) for key in record.keys())
    return sorted(names)


def _sort_key_for_value(value: Hashable) -> tuple[int, object]:
    """数値優先、その次に文字列で整列する。"""

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, float(value))
    numeric = parse_optional_float(value)
    if numeric is not None:
        return (0, numeric)
    return (1, str(value))


def _apply_bin(value: object, bin_width: float | None) -> object:
    """数値 X 軸にビン幅が指定されていれば区間キーへ丸める。"""

    if bin_width is None:
        return value
    numeric = parse_optional_float(value)
    if numeric is None:
        return value
    return math.floor(numeric / bin_width) * bin_width


def _sample_numeric_pairs(
    records: Sequence[Mapping[str, object]],
    x_field: str,
    y_field: str,
    *,
    x_bin_width: float | None = None,
) -> list[tuple[float, float]]:
    """numeric な `(x, y)` 点列を作る。"""

    pairs: list[tuple[float, float]] = []
    for record in records:
        x_value = parse_optional_float(_apply_bin(record.get(x_field), x_bin_width))
        y_value = parse_optional_float(record.get(y_field))
        if x_value is None or y_value is None:
            continue
        pairs.append((x_value, y_value))
    return pairs


def _sample_numeric_values(records: Sequence[Mapping[str, object]], field_name: str) -> list[float]:
    """1 列だけの numeric series を作る。"""

    values: list[float] = []
    for record in records:
        value = parse_optional_float(record.get(field_name))
        if value is None:
            continue
        values.append(value)
    return values


def _sample_discrete_values(records: Sequence[Mapping[str, object]], field_name: str) -> list[Hashable]:
    """カテゴリ列をそのまま拾う。"""

    values: list[Hashable] = []
    for record in records:
        value = record.get(field_name)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if not isinstance(value, Hashable):
            continue
        values.append(value)
    return values


def _group_numeric_values(
    records: Sequence[Mapping[str, object]],
    x_field: str,
    y_field: str,
    *,
    x_bin_width: float | None = None,
) -> dict[Hashable, list[float]]:
    """X ごとに Y の数値列を束ねる。"""

    grouped: dict[Hashable, list[float]] = defaultdict(list)
    for record in records:
        group_key = _apply_bin(record.get(x_field), x_bin_width)
        y_value = parse_optional_float(record.get(y_field))
        if group_key is None or y_value is None:
            continue
        if isinstance(group_key, str) and not group_key.strip():
            continue
        grouped[group_key].append(y_value)
    return grouped


def _build_regression(points: Sequence[tuple[float, float]]) -> RegressionResult | None:
    """散布図用の単回帰を作る。"""

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


def _aggregate_values(values: Sequence[float], method: str) -> float:
    """線グラフの group 集計値を返す。"""

    if method == "mean":
        return statistics.fmean(values)
    if method == "median":
        return statistics.median(values)
    if method == "sum":
        return sum(values)
    if method == "count":
        return float(len(values))
    if method == "min":
        return min(values)
    if method == "max":
        return max(values)
    raise ValueError(f"未対応の集計方法です: {method}")


def _confidence_margin(values: Sequence[float], confidence: float) -> float:
    """正規近似の両側信頼区間幅を返す。"""

    if len(values) < 2:
        return 0.0
    standard_deviation = statistics.stdev(values)
    if math.isclose(standard_deviation, 0.0):
        return 0.0
    z_value = statistics.NormalDist().inv_cdf((1.0 + confidence) / 2.0)
    return z_value * (standard_deviation / math.sqrt(len(values)))


def _build_line_svg(
    points: Sequence[tuple[float, float]],
    *,
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
) -> str:
    """折れ線グラフを描く。"""

    width = 920
    height = 560
    margin_left = 88
    margin_right = 28
    margin_top = 72
    margin_bottom = 76
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
    y_min = min(y_values)
    y_max = max(y_values)
    x_padding = 0.5 if math.isclose(x_min, x_max) else max(0.2, (x_max - x_min) * 0.05)
    y_padding = 1.0 if math.isclose(y_min, y_max) else max(0.2, (y_max - y_min) * 0.08)
    x_min -= x_padding
    x_max += x_padding
    y_min -= y_padding
    y_max += y_padding

    def _map_x(value: float) -> float:
        return plot_left + (value - x_min) / (x_max - x_min) * plot_width

    def _map_y(value: float) -> float:
        return plot_bottom - (value - y_min) / (y_max - y_min) * plot_height

    parts = [_svg_header(width, height)]
    parts.append(f'<text x="{width / 2:.1f}" y="28" font-size="22" text-anchor="middle" fill="#111827">{_format_svg_text(title)}</text>')
    parts.append(f'<text x="{width / 2:.1f}" y="50" font-size="12" text-anchor="middle" fill="#475569">{_format_svg_text(subtitle)}</text>')
    parts.append(f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" height="{plot_height}" fill="#f8fafc" stroke="#cbd5e1"/>')

    for tick in _build_axis_ticks(y_min, y_max, 6):
        y = _map_y(tick)
        parts.append(f'<line x1="{plot_left}" y1="{y:.2f}" x2="{plot_right}" y2="{y:.2f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{plot_left - 10}" y="{y + 4:.2f}" font-size="11" text-anchor="end" fill="#475569">{round(tick, 2)}</text>')

    for tick in _build_axis_ticks(x_min, x_max, 6):
        x = _map_x(tick)
        parts.append(f'<line x1="{x:.2f}" y1="{plot_top}" x2="{x:.2f}" y2="{plot_bottom}" stroke="#eef2f7"/>')
        parts.append(f'<text x="{x:.2f}" y="{plot_bottom + 24}" font-size="11" text-anchor="middle" fill="#475569">{round(tick, 2)}</text>')

    path_points = " ".join(f"L {_map_x(x_value):.2f} {_map_y(y_value):.2f}" for x_value, y_value in points[1:])
    parts.append(
        f'<path d="M {_map_x(points[0][0]):.2f} {_map_y(points[0][1]):.2f} {path_points}" '
        f'fill="none" stroke="#2563eb" stroke-width="2.4"/>'
    )
    for x_value, y_value in points:
        parts.append(f'<circle cx="{_map_x(x_value):.2f}" cy="{_map_y(y_value):.2f}" r="4.0" fill="#1d4ed8" stroke="#1e3a8a" stroke-width="1"/>')

    parts.append(f'<line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="#334155"/>')
    parts.append(f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_bottom}" stroke="#334155"/>')
    parts.append(f'<text x="{(plot_left + plot_right) / 2:.1f}" y="{height - 20}" font-size="13" text-anchor="middle" fill="#111827">{_format_svg_text(x_label)}</text>')
    parts.append(
        f'<text x="24" y="{(plot_top + plot_bottom) / 2:.1f}" font-size="13" text-anchor="middle" fill="#111827" '
        f'transform="rotate(-90 24 {(plot_top + plot_bottom) / 2:.1f})">{_format_svg_text(y_label)}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _quartiles(values: Sequence[float]) -> tuple[float, float, float]:
    """Q1 / median / Q3 を返す。"""

    if len(values) == 1:
        return values[0], values[0], values[0]
    quartiles = statistics.quantiles(values, n=4, method="inclusive")
    return quartiles[0], quartiles[1], quartiles[2]


def _build_boxplot_svg(
    grouped_values: Sequence[tuple[Hashable, Sequence[float]]],
    *,
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
) -> str:
    """min/max whisker の箱ひげ図を描く。"""

    width = 960
    height = 560
    margin_left = 88
    margin_right = 28
    margin_top = 72
    margin_bottom = 88
    plot_left = margin_left
    plot_top = margin_top
    plot_right = width - margin_right
    plot_bottom = height - margin_bottom
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    all_values = [value for _group, values in grouped_values for value in values]
    y_min = min(all_values)
    y_max = max(all_values)
    y_padding = 1.0 if math.isclose(y_min, y_max) else max(0.2, (y_max - y_min) * 0.08)
    y_min -= y_padding
    y_max += y_padding

    def _map_y(value: float) -> float:
        return plot_bottom - (value - y_min) / (y_max - y_min) * plot_height

    parts = [_svg_header(width, height)]
    parts.append(f'<text x="{width / 2:.1f}" y="28" font-size="22" text-anchor="middle" fill="#111827">{_format_svg_text(title)}</text>')
    parts.append(f'<text x="{width / 2:.1f}" y="50" font-size="12" text-anchor="middle" fill="#475569">{_format_svg_text(subtitle)}</text>')
    parts.append(f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" height="{plot_height}" fill="#f8fafc" stroke="#cbd5e1"/>')

    for tick in _build_axis_ticks(y_min, y_max, 6):
        y = _map_y(tick)
        parts.append(f'<line x1="{plot_left}" y1="{y:.2f}" x2="{plot_right}" y2="{y:.2f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{plot_left - 10}" y="{y + 4:.2f}" font-size="11" text-anchor="end" fill="#475569">{round(tick, 2)}</text>')

    column_width = plot_width / max(len(grouped_values), 1)
    box_width = min(46.0, max(18.0, column_width * 0.45))
    for index, (group_key, values) in enumerate(grouped_values):
        sorted_values = sorted(values)
        x = plot_left + index * column_width + column_width / 2
        minimum = sorted_values[0]
        maximum = sorted_values[-1]
        q1, median, q3 = _quartiles(sorted_values)
        box_top = _map_y(q3)
        box_bottom = _map_y(q1)
        median_y = _map_y(median)
        whisker_top = _map_y(maximum)
        whisker_bottom = _map_y(minimum)
        parts.append(f'<line x1="{x:.2f}" y1="{whisker_top:.2f}" x2="{x:.2f}" y2="{box_top:.2f}" stroke="#1d4ed8" stroke-width="1.6"/>')
        parts.append(f'<line x1="{x:.2f}" y1="{box_bottom:.2f}" x2="{x:.2f}" y2="{whisker_bottom:.2f}" stroke="#1d4ed8" stroke-width="1.6"/>')
        parts.append(f'<line x1="{x - 8:.2f}" y1="{whisker_top:.2f}" x2="{x + 8:.2f}" y2="{whisker_top:.2f}" stroke="#1d4ed8" stroke-width="1.6"/>')
        parts.append(f'<line x1="{x - 8:.2f}" y1="{whisker_bottom:.2f}" x2="{x + 8:.2f}" y2="{whisker_bottom:.2f}" stroke="#1d4ed8" stroke-width="1.6"/>')
        parts.append(
            f'<rect x="{x - box_width / 2:.2f}" y="{box_top:.2f}" width="{box_width:.2f}" height="{max(1.0, box_bottom - box_top):.2f}" '
            f'fill="#93c5fd" fill-opacity="0.78" stroke="#1d4ed8" stroke-width="1.4"/>'
        )
        parts.append(f'<line x1="{x - box_width / 2:.2f}" y1="{median_y:.2f}" x2="{x + box_width / 2:.2f}" y2="{median_y:.2f}" stroke="#1e3a8a" stroke-width="2"/>')
        parts.append(f'<text x="{x:.2f}" y="{plot_bottom + 22:.2f}" font-size="10" text-anchor="middle" fill="#475569">{_format_svg_text(group_key)}</text>')
        parts.append(f'<text x="{x:.2f}" y="{box_top - 8:.2f}" font-size="9" text-anchor="middle" fill="#0f172a">n={len(values)}</text>')

    parts.append(f'<line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="#334155"/>')
    parts.append(f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_bottom}" stroke="#334155"/>')
    parts.append(f'<text x="{(plot_left + plot_right) / 2:.1f}" y="{height - 24}" font-size="13" text-anchor="middle" fill="#111827">{_format_svg_text(x_label)}</text>')
    parts.append(
        f'<text x="24" y="{(plot_top + plot_bottom) / 2:.1f}" font-size="13" text-anchor="middle" fill="#111827" '
        f'transform="rotate(-90 24 {(plot_top + plot_bottom) / 2:.1f})">{_format_svg_text(y_label)}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _build_scatter_ci_svg(
    points: Sequence[tuple[float, float]],
    ci_groups: Sequence[tuple[float, float, float, float]],
    *,
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
    regression: RegressionResult | None = None,
) -> str:
    """信頼区間付き散布図を描く。"""

    width = 920
    height = 580
    margin_left = 88
    margin_right = 28
    margin_top = 78
    margin_bottom = 76
    plot_left = margin_left
    plot_top = margin_top
    plot_right = width - margin_right
    plot_bottom = height - margin_bottom
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    x_values = [point[0] for point in points] + [group[0] for group in ci_groups]
    y_values = [point[1] for point in points]
    for _x_value, mean_value, lower, upper in ci_groups:
        y_values.extend((mean_value, lower, upper))
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
    parts.append(f'<text x="{width / 2:.1f}" y="50" font-size="12" text-anchor="middle" fill="#475569">{_format_svg_text(subtitle)}</text>')
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
            f'<circle cx="{_map_x(x_value):.2f}" cy="{_map_y(y_value):.2f}" r="4.0" '
            f'fill="#2563eb" fill-opacity="0.62" stroke="#1d4ed8" stroke-width="0.8"/>'
        )

    mean_points: list[tuple[float, float]] = []
    for x_value, mean_value, lower, upper in ci_groups:
        mapped_x = _map_x(x_value)
        mapped_low = _map_y(lower)
        mapped_high = _map_y(upper)
        mapped_mean = _map_y(mean_value)
        parts.append(f'<line x1="{mapped_x:.2f}" y1="{mapped_low:.2f}" x2="{mapped_x:.2f}" y2="{mapped_high:.2f}" stroke="#b91c1c" stroke-width="1.6"/>')
        parts.append(f'<line x1="{mapped_x - 5:.2f}" y1="{mapped_low:.2f}" x2="{mapped_x + 5:.2f}" y2="{mapped_low:.2f}" stroke="#b91c1c" stroke-width="1.6"/>')
        parts.append(f'<line x1="{mapped_x - 5:.2f}" y1="{mapped_high:.2f}" x2="{mapped_x + 5:.2f}" y2="{mapped_high:.2f}" stroke="#b91c1c" stroke-width="1.6"/>')
        parts.append(f'<circle cx="{mapped_x:.2f}" cy="{mapped_mean:.2f}" r="4.2" fill="#dc2626" stroke="#991b1b" stroke-width="1"/>')
        mean_points.append((x_value, mean_value))
    mean_points.sort(key=lambda point: point[0])
    if len(mean_points) >= 2:
        path_points = " ".join(f"L {_map_x(x_value):.2f} {_map_y(y_value):.2f}" for x_value, y_value in mean_points[1:])
        parts.append(
            f'<path d="M {_map_x(mean_points[0][0]):.2f} {_map_y(mean_points[0][1]):.2f} {path_points}" '
            f'fill="none" stroke="#dc2626" stroke-width="1.8"/>'
        )

    if regression is not None:
        line_x0 = min(point[0] for point in points)
        line_x1 = max(point[0] for point in points)
        line_y0 = regression.slope * line_x0 + regression.intercept
        line_y1 = regression.slope * line_x1 + regression.intercept
        parts.append(
            f'<line x1="{_map_x(line_x0):.2f}" y1="{_map_y(line_y0):.2f}" '
            f'x2="{_map_x(line_x1):.2f}" y2="{_map_y(line_y1):.2f}" '
            f'stroke="#7c3aed" stroke-width="2.2"/>'
        )
        correlation_text = f"r={regression.correlation:.3f}" if regression.correlation is not None else "r=n/a"
        parts.append(
            f'<text x="{plot_right - 8}" y="{plot_top + 18}" font-size="12" text-anchor="end" fill="#5b21b6">'
            f'{_format_svg_text(f"y = {regression.slope:.2f}x + {regression.intercept:.2f} / {correlation_text}")}'
            "</text>"
        )

    parts.append("</svg>")
    return "".join(parts)


def _render_scatter(
    request: RuntimeGraphRequest,
    records: Sequence[Mapping[str, object]],
) -> GeneratedRuntimeGraph:
    """散布図を生成する。"""

    if request.y_field is None:
        raise ValueError("scatter では --y-field が必要です。")
    points = _sample_numeric_pairs(records, request.x_field, request.y_field, x_bin_width=request.x_bin_width)
    if not points:
        return GeneratedRuntimeGraph(request.kind, request.dataset_name, 0, None, "散布図のサンプルが 0 件でした。")
    regression = _build_regression(points) if request.include_regression else None
    svg_text = _build_scatter_svg(
        points,
        regression,
        title=request.title,
        subtitle=request.subtitle,
        x_label=request.x_label,
        y_label=request.y_label,
    )
    _write_text(request.output_path, svg_text)
    return GeneratedRuntimeGraph(request.kind, request.dataset_name, len(points), request.output_path, "散布図を生成しました。", regression)


def _render_scatter_ci(
    request: RuntimeGraphRequest,
    records: Sequence[Mapping[str, object]],
) -> GeneratedRuntimeGraph:
    """group 平均と信頼区間を重ねた散布図を生成する。"""

    if request.y_field is None:
        raise ValueError("scatter_ci では --y-field が必要です。")
    points = _sample_numeric_pairs(records, request.x_field, request.y_field)
    grouped = _group_numeric_values(records, request.x_field, request.y_field, x_bin_width=request.x_bin_width)
    if not points or not grouped:
        return GeneratedRuntimeGraph(request.kind, request.dataset_name, 0, None, "信頼区間付き散布図のサンプルが 0 件でした。")

    ci_groups: list[tuple[float, float, float, float]] = []
    for group_key in sorted(grouped.keys(), key=_sort_key_for_value):
        x_value = parse_optional_float(group_key)
        if x_value is None:
            continue
        values = grouped[group_key]
        mean_value = statistics.fmean(values)
        margin = _confidence_margin(values, request.ci_confidence)
        ci_groups.append((x_value, mean_value, mean_value - margin, mean_value + margin))
    regression = _build_regression(points) if request.include_regression else None
    svg_text = _build_scatter_ci_svg(
        points,
        ci_groups,
        title=request.title,
        subtitle=request.subtitle,
        x_label=request.x_label,
        y_label=request.y_label,
        regression=regression,
    )
    _write_text(request.output_path, svg_text)
    return GeneratedRuntimeGraph(
        request.kind,
        request.dataset_name,
        len(points),
        request.output_path,
        f"信頼区間付き散布図を生成しました。信頼水準={request.ci_confidence:.2f}",
        regression,
    )


def _render_line(
    request: RuntimeGraphRequest,
    records: Sequence[Mapping[str, object]],
) -> GeneratedRuntimeGraph:
    """線グラフを生成する。"""

    points: list[tuple[float, float]] = []
    if request.line_aggregation == "raw":
        if request.y_field is None:
            raise ValueError("line の raw モードでは --y-field が必要です。")
        points = _sample_numeric_pairs(records, request.x_field, request.y_field, x_bin_width=request.x_bin_width)
    elif request.line_aggregation == "count":
        grouped_count: dict[Hashable, int] = defaultdict(int)
        for record in records:
            group_key = _apply_bin(record.get(request.x_field), request.x_bin_width)
            if group_key is None:
                continue
            if isinstance(group_key, str) and not group_key.strip():
                continue
            grouped_count[group_key] += 1
        for group_key in sorted(grouped_count.keys(), key=_sort_key_for_value):
            x_value = parse_optional_float(group_key)
            if x_value is not None:
                points.append((x_value, float(grouped_count[group_key])))
    else:
        if request.y_field is None:
            raise ValueError("line の集計モードでは --y-field が必要です。")
        grouped = _group_numeric_values(records, request.x_field, request.y_field, x_bin_width=request.x_bin_width)
        for group_key in sorted(grouped.keys(), key=_sort_key_for_value):
            x_value = parse_optional_float(group_key)
            if x_value is not None:
                points.append((x_value, _aggregate_values(grouped[group_key], request.line_aggregation)))
    points.sort(key=lambda point: point[0])
    if not points:
        return GeneratedRuntimeGraph(request.kind, request.dataset_name, 0, None, "線グラフのサンプルが 0 件でした。")
    svg_text = _build_line_svg(
        points,
        title=request.title,
        subtitle=request.subtitle,
        x_label=request.x_label,
        y_label=request.y_label,
    )
    _write_text(request.output_path, svg_text)
    return GeneratedRuntimeGraph(
        request.kind,
        request.dataset_name,
        len(points),
        request.output_path,
        f"線グラフを生成しました。集計={request.line_aggregation}",
    )


def _render_boxplot(
    request: RuntimeGraphRequest,
    records: Sequence[Mapping[str, object]],
) -> GeneratedRuntimeGraph:
    """箱ひげ図を生成する。"""

    if request.y_field is None:
        raise ValueError("boxplot では --y-field が必要です。")
    grouped = _group_numeric_values(records, request.x_field, request.y_field, x_bin_width=request.x_bin_width)
    grouped_values = [
        (group_key, tuple(sorted(values)))
        for group_key, values in sorted(grouped.items(), key=lambda item: _sort_key_for_value(item[0]))
        if values
    ]
    if not grouped_values:
        return GeneratedRuntimeGraph(request.kind, request.dataset_name, 0, None, "箱ひげ図のサンプルが 0 件でした。")
    svg_text = _build_boxplot_svg(
        grouped_values,
        title=request.title,
        subtitle=request.subtitle,
        x_label=request.x_label,
        y_label=request.y_label,
    )
    _write_text(request.output_path, svg_text)
    sample_count = sum(len(values) for _group, values in grouped_values)
    return GeneratedRuntimeGraph(request.kind, request.dataset_name, sample_count, request.output_path, "箱ひげ図を生成しました。")


def render_runtime_graph(
    request: RuntimeGraphRequest,
    records: Sequence[Mapping[str, object]],
) -> GeneratedRuntimeGraph:
    """graph kind ごとに描画処理を振り分ける。"""

    if request.kind == "scatter":
        return _render_scatter(request, records)
    if request.kind == "scatter_ci":
        return _render_scatter_ci(request, records)
    if request.kind == "line":
        return _render_line(request, records)
    if request.kind == "boxplot":
        return _render_boxplot(request, records)
    if request.kind == "histogram":
        values = _sample_numeric_values(records, request.x_field)
        if not values:
            return GeneratedRuntimeGraph(request.kind, request.dataset_name, 0, None, "ヒストグラムのサンプルが 0 件でした。")
        bin_width = request.x_bin_width if request.x_bin_width is not None else 500.0
        svg_text = _build_histogram_svg(
            values,
            title=request.title,
            subtitle=request.subtitle,
            x_label=request.x_label,
            y_label=request.y_label,
            bin_width=bin_width,
        )
        _write_text(request.output_path, svg_text)
        return GeneratedRuntimeGraph(request.kind, request.dataset_name, len(values), request.output_path, "ヒストグラムを生成しました。")
    if request.kind == "discrete_bar":
        values = _sample_discrete_values(records, request.x_field)
        if not values:
            return GeneratedRuntimeGraph(request.kind, request.dataset_name, 0, None, "カテゴリ棒グラフのサンプルが 0 件でした。")
        counts: dict[Hashable, int] = defaultdict(int)
        for value in values:
            counts[value] += 1
        counts_by_value = sorted(counts.items(), key=lambda item: _sort_key_for_value(item[0]))
        svg_text = _build_discrete_bar_svg(
            counts_by_value,
            title=request.title,
            subtitle=request.subtitle,
            x_label=request.x_label,
            y_label=request.y_label,
        )
        _write_text(request.output_path, svg_text)
        return GeneratedRuntimeGraph(request.kind, request.dataset_name, len(values), request.output_path, "カテゴリ棒グラフを生成しました。")
    raise ValueError(f"未対応のグラフ種類です: {request.kind}")


def _default_output_path(output_root: Path, request: RuntimeGraphRequest) -> Path:
    """既定の出力ファイル名を作る。"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_root / f"{request.kind}_{request.dataset_name}_{timestamp}.svg"


def _build_summary_markdown(
    request: RuntimeGraphRequest,
    generated_graph: GeneratedRuntimeGraph,
    *,
    field_names: Sequence[str],
) -> str:
    """実行条件と結果をまとめた summary.md を返す。"""

    lines = [
        "# DBグラフ実行結果",
        "",
        f"- 実行時刻: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- データセット: `{request.dataset_name}`",
        f"- グラフ種類: `{request.kind}`",
        f"- X軸: `{request.x_field}`",
        f"- Y軸: `{request.y_field or ''}`",
        f"- 出力先: `{generated_graph.output_path}`" if generated_graph.output_path is not None else "- 出力先: `未生成`",
        f"- サンプル数: `{generated_graph.sample_count}`",
        f"- 除外プレイヤー: `{', '.join(request.excluded_players)}`",
        "",
        "## 条件",
        "",
    ]
    if request.where_clauses:
        for clause in request.where_clauses:
            lines.append(f"- `{clause}`")
    else:
        lines.append("- 追加条件なし")
    lines.extend(["", "## 派生列", ""])
    if request.derive_specs:
        for derive_spec in request.derive_specs:
            lines.append(f"- `{derive_spec}`")
    else:
        lines.append("- 追加派生列なし")
    lines.extend(
        [
            "",
            "## 描画設定",
            "",
            f"- 回帰直線: `{request.include_regression}`",
            f"- 線グラフ集計: `{request.line_aggregation}`",
            f"- X軸ビン幅: `{request.x_bin_width}`",
            f"- 信頼水準: `{request.ci_confidence}`",
            f"- メッセージ: {generated_graph.message}",
            "",
            "## 利用可能フィールド",
            "",
        ]
    )
    for field_name in field_names:
        lines.append(f"- `{field_name}`")
    if generated_graph.regression is not None:
        lines.extend(
            [
                "",
                "## 回帰直線",
                "",
                f"- 傾き: `{generated_graph.regression.slope:.4f}`",
                f"- 切片: `{generated_graph.regression.intercept:.4f}`",
                (
                    f"- 相関係数: `{generated_graph.regression.correlation:.4f}`"
                    if generated_graph.regression.correlation is not None
                    else "- 相関係数: `-`"
                ),
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def run_runtime_graph_request(
    request: RuntimeGraphRequest,
    *,
    db_dir: Path,
    output_root: Path,
) -> GeneratedRuntimeGraph:
    """dataset 読み込みから summary 出力までまとめて実行する。"""

    dataset_definitions = runtime_dataset_definitions()
    if request.dataset_name not in dataset_definitions:
        raise ValueError(f"不明なデータセットです: {request.dataset_name}")
    dataset_records = dataset_definitions[request.dataset_name].build_records(db_dir, request.excluded_players)
    filtered_records = apply_query_pipeline(
        dataset_records,
        derive_specs=request.derive_specs,
        where_clauses=request.where_clauses,
    )
    output_path = request.output_path
    if not output_path.name:
        output_path = _default_output_path(output_root, request)
    effective_request = RuntimeGraphRequest(
        dataset_name=request.dataset_name,
        kind=request.kind,
        x_field=request.x_field,
        y_field=request.y_field,
        title=request.title,
        subtitle=request.subtitle,
        x_label=request.x_label,
        y_label=request.y_label,
        output_path=output_path,
        include_regression=request.include_regression,
        line_aggregation=request.line_aggregation,
        x_bin_width=request.x_bin_width,
        ci_confidence=request.ci_confidence,
        where_clauses=request.where_clauses,
        derive_specs=request.derive_specs,
        excluded_players=request.excluded_players,
    )
    generated_graph = render_runtime_graph(effective_request, filtered_records)
    summary_path = output_path.with_name(f"{output_path.stem}_summary.md")
    _write_text(summary_path, _build_summary_markdown(effective_request, generated_graph, field_names=available_field_names(filtered_records)))
    return generated_graph
