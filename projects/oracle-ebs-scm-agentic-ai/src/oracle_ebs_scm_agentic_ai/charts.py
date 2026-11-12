# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Executive chart tools from the Oracle EBS Gemini Enterprise MCP framework.

Adapted from the framework EBS_Graphs_Agent. Each tool turns tabular JSON or
CSV rows returned by the SQL tools into a 180 DPI widescreen (12.0" x 6.6")
PNG chart, saves the PNG as an ADK artifact, and returns a short summary to
the model. Charts plot only the values they receive: a missing or non-numeric
value is an error instead of a silent zero.
"""

import csv
import io
import json
import logging
import math
import re
import textwrap
from collections.abc import Sequence
from typing import Any, Final

from google.adk.tools.tool_context import ToolContext
from google.genai import types
from matplotlib import rcParams
from matplotlib.axes import Axes
from matplotlib.container import BarContainer
from matplotlib.figure import Figure
from matplotlib.patches import Wedge
from matplotlib.ticker import FuncFormatter

logger = logging.getLogger(__name__)

# Chart text holds USD amounts and model-written titles: draw every dollar
# sign literally instead of as matplotlib mathtext.
rcParams["text.parse_math"] = False

Row = dict[str, Any]

FIGSIZE: Final[tuple[float, float]] = (12.0, 6.6)
DPI: Final[int] = 180
FOOTER: Final[str] = (
    "Source: Oracle E-Business Suite and Google Cloud BigQuery • "
    "VoltGuard supply chain resiliency agent"
)
# VoltGuard brand colors, which the charts and the maps share.
BLUE: Final[str] = "#0B57D0"
RED: Final[str] = "#D93025"
GREEN: Final[str] = "#188038"
AMBER: Final[str] = "#F29900"
PURPLE: Final[str] = "#7627BB"
TEAL: Final[str] = "#007B83"
NAVY: Final[str] = "#1E3A8A"
ORANGE: Final[str] = "#C2410C"
COLOR_PALETTES: Final[dict[str, tuple[str, ...]]] = {
    "corporate": (BLUE, RED, GREEN, AMBER, PURPLE, TEAL, NAVY, ORANGE),
    "vibrant": (
        "#1A73E8",
        "#EA4335",
        "#34A853",
        "#FBBC04",
        "#9334E6",
        "#00ACC1",
        "#F4511E",
        "#3949AB",
    ),
    "monochrome_blue": (
        BLUE,
        "#1D4ED8",
        "#2563EB",
        "#3B82F6",
        "#60A5FA",
        "#93C5FD",
        NAVY,
        "#1E40AF",
    ),
}
CURRENCY_KEYWORDS: Final[tuple[str, ...]] = (
    "usd",
    "$",
    "amount",
    "benefit",
    "budget",
    "cost",
    "freight",
    "margin",
    "penalty",
    "price",
    "revenue",
)
ACRONYMS: Final[tuple[str, ...]] = (
    "ATT",
    "DC",
    "EBS",
    "ETA",
    "ID",
    "MRP",
    "PO",
    "SKU",
    "SLA",
    "USD",
)
ROW_LIST_KEYS: Final[tuple[str, ...]] = ("rows", "data", "items", "results")
INK: Final[str] = "#0F172A"
MUTED: Final[str] = "#475569"
PANEL: Final[str] = "#F8FAFC"
GRID: Final[str] = "#E2E8F0"
WHITE: Final[str] = "#FFFFFF"


class ChartDataError(ValueError):
    """Chart input data that the tools can't parse or plot."""


def parse_numeric(value: object) -> float:
    """Parse a finite number, stripping currency symbols, commas, and percents.

    Args:
        value: A number, or text such as ``$1,200`` or ``12%``.

    Returns:
        The value as a finite float.

    Raises:
        ChartDataError: If the value is missing, not numeric, NaN, or
            infinite.
    """
    if isinstance(value, bool):
        raise ChartDataError(f"Value {value!r} is not numeric.")
    text = re.sub(r"[$,%\s]", "", str(value if value is not None else ""))
    try:
        number = float(value) if isinstance(value, int | float) else float(text)
    except ValueError as exc:
        raise ChartDataError(
            f"Value {value!r} is missing or not numeric."
        ) from exc
    if not math.isfinite(number):
        raise ChartDataError(f"Value {value!r} is not a finite number.")
    return number


def parse_rows(data: str) -> list[Row]:
    """Parse a JSON array, a JSON object holding rows, or CSV text.

    Args:
        data: A JSON array of row objects, a JSON object that holds the rows
            under ``rows``, ``data``, ``items``, or ``results``, or CSV text
            with a header row.

    Returns:
        The rows as dictionaries keyed by column name.

    Raises:
        ChartDataError: If the data is invalid JSON, holds no rows, or has a
            CSV row with more or fewer values than the header.
    """
    stripped = data.strip()
    if stripped.startswith(("[", "{")):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ChartDataError(f"Invalid JSON data: {exc.msg}.") from exc
        if isinstance(parsed, dict):
            parsed = next(
                (parsed[key] for key in ROW_LIST_KEYS if key in parsed),
                None,
            )
        if not isinstance(parsed, list) or not parsed:
            raise ChartDataError("The data must contain at least one row.")
        if not all(isinstance(row, dict) for row in parsed):
            raise ChartDataError("Every JSON row must be an object.")
        return parsed
    rows = list(csv.DictReader(io.StringIO(stripped)))
    if not rows:
        raise ChartDataError(
            "The data must be a JSON array of objects or CSV with a header."
        )
    for number, row in enumerate(rows, start=1):
        if None in row or None in row.values():
            raise ChartDataError(
                f"CSV row {number} has a different number of values than the "
                "header. Quote every value that contains a comma."
            )
    return rows


def column_values(rows: Sequence[Row], column: str) -> list[Any]:
    """Return the values of one column in row order.

    Args:
        rows: The parsed rows.
        column: The column name.

    Returns:
        The column's value in each row.

    Raises:
        ChartDataError: If a row doesn't have the column.
    """
    missing = [index for index, row in enumerate(rows) if column not in row]
    if missing:
        raise ChartDataError(f"Column {column!r} is missing from the data.")
    return [row[column] for row in rows]


def sort_rows(rows: list[Row], sort_column: str, sort_order: str) -> list[Row]:
    """Sort rows by a column, numerically when every value is numeric.

    Args:
        rows: The parsed rows.
        sort_column: The column to sort by, or an empty string to keep the
            row order.
        sort_order: ``desc`` for descending order, anything else for
            ascending order.

    Returns:
        The sorted rows.

    Raises:
        ChartDataError: If a row doesn't have the sort column.
    """
    if not sort_column:
        return rows
    values = column_values(rows, sort_column)
    descending = sort_order.strip().lower() == "desc"
    try:
        keys: list[Any] = [parse_numeric(value) for value in values]
    except ChartDataError:
        keys = [str(value).lower() for value in values]
    order = sorted(range(len(rows)), key=keys.__getitem__, reverse=descending)
    return [rows[index] for index in order]


def is_currency(title: str, column: str, values: Sequence[Any]) -> bool:
    """Detect whether a metric represents US dollars.

    Args:
        title: The chart title.
        column: The metric column name.
        values: The metric's raw values.

    Returns:
        True when the title or column names a dollar amount, or a value
        holds a dollar sign.
    """
    combined = f"{title} {column}".lower()
    if any(keyword in combined for keyword in CURRENCY_KEYWORDS):
        return True
    return any("$" in str(value) for value in values)


def format_value(value: float, currency: bool = False) -> str:
    """Format a number for data labels and legends.

    Args:
        value: The number.
        currency: Whether to format the number as US dollars.

    Returns:
        The number with thousands separators, and two decimals when it isn't
        whole.
    """
    whole = abs(value - round(value)) < 1e-4
    if currency:
        return (
            f"${value:,.0f}" if whole or abs(value) >= 100 else f"${value:,.2f}"
        )
    return f"{int(round(value)):,}" if whole else f"{value:,.2f}"


def humanize(text: str) -> str:
    """Turn a snake_case column name into a readable heading.

    Args:
        text: The column name.

    Returns:
        The heading, in title case with known acronyms in capitals.
    """
    cleaned = str(text).replace("_", " ").strip()
    if cleaned.islower() or cleaned.isupper():
        cleaned = cleaned.title()
    for acronym in ACRONYMS:
        cleaned = re.sub(
            rf"\b{acronym}\b", acronym, cleaned, flags=re.IGNORECASE
        )
    return cleaned


def palette_colors(palette: str, count: int) -> list[str]:
    """Return colors from a named palette, repeating it as needed.

    Args:
        palette: The palette name. An unknown name uses ``corporate``.
        count: The number of colors.

    Returns:
        ``count`` hexadecimal colors.
    """
    colors = COLOR_PALETTES.get(palette.lower(), COLOR_PALETTES["corporate"])
    return [colors[index % len(colors)] for index in range(count)]


def new_figure(right: float) -> tuple[Figure, Axes]:
    """Create a widescreen figure with room for a legend on the right.

    Args:
        right: The right edge of the plot area, as a fraction of the figure
            width.

    Returns:
        The figure and its plot area.
    """
    fig = Figure(figsize=FIGSIZE, facecolor=WHITE)
    fig.subplots_adjust(left=0.09, right=right, top=0.80, bottom=0.22)
    ax = fig.add_subplot()
    ax.set_facecolor(PANEL)
    return fig, ax


def style_axes(ax: Axes, currency: bool) -> None:
    """Apply the framework's clean executive axis styling.

    Args:
        ax: The plot area.
        currency: Whether the y axis shows US dollars.
    """
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")
    ax.spines["bottom"].set_color("#94A3B8")
    ax.grid(axis="y", linestyle="--", linewidth=0.8, color=GRID, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=10, colors="#334155")
    if currency:
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda value, _pos: format_value(value, True))
        )
    else:
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda value, _pos: format_value(value))
        )


def set_category_ticks(ax: Axes, labels: Sequence[str], width: int) -> None:
    """Write wrapped category labels under the x axis.

    Args:
        ax: The plot area.
        labels: One label per category.
        width: The maximum number of characters per label line.
    """
    rotation = 0 if len(labels) <= 6 else 15
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(
        [textwrap.fill(label, width=width) for label in labels],
        rotation=rotation,
        ha="center" if rotation == 0 else "right",
        fontsize=9.5,
        fontweight="bold",
        color="#1E293B",
    )


def draw_frame(fig: Figure, title: str, subtitle: str, badge: str) -> None:
    """Draw the title, subtitle, KPI badge, and source footer.

    Args:
        fig: The figure.
        title: The chart title.
        subtitle: The line under the title.
        badge: The text of the KPI badge in the upper right corner.
    """
    fig.suptitle(
        title,
        x=0.04,
        y=0.968,
        ha="left",
        va="top",
        fontsize=14.5,
        fontweight="bold",
        color=INK,
    )
    fig.text(0.04, 0.902, subtitle, ha="left", va="center", color=MUTED)
    fig.text(
        0.96,
        0.902,
        badge,
        ha="right",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color=BLUE,
        bbox={
            "boxstyle": "round,pad=0.40",
            "facecolor": "#EFF6FF",
            "edgecolor": "#BFDBFE",
            "linewidth": 1.2,
        },
    )
    fig.text(
        0.04,
        0.012,
        FOOTER,
        ha="left",
        va="bottom",
        fontsize=8.5,
        style="italic",
        color="#64748B",
    )


def style_legend(ax: Axes, title: str, **kwargs: Any) -> None:
    """Place a framed legend to the right of the plot.

    Args:
        ax: The plot area.
        title: The legend title.
        **kwargs: More ``Axes.legend`` arguments, such as handles and
            labels.
    """
    legend = ax.legend(
        title=title,
        bbox_to_anchor=(1.03, 1.0),
        loc="upper left",
        frameon=True,
        facecolor=PANEL,
        edgecolor="#CBD5E1",
        fontsize=9.2,
        title_fontsize=10.5,
        borderpad=0.9,
        **kwargs,
    )
    legend.get_title().set_fontweight("bold")
    legend.get_title().set_color(INK)


def render_png(fig: Figure) -> bytes:
    """Render a figure to 180 DPI PNG bytes.

    Args:
        fig: The figure.

    Returns:
        The PNG image.
    """
    buffer = io.BytesIO()
    fig.savefig(
        buffer,
        format="png",
        dpi=DPI,
        bbox_inches="tight",
        pad_inches=0.38,
        facecolor=fig.get_facecolor(),
    )
    return buffer.getvalue()


def chart_filename(title: str, kind: str) -> str:
    """Derive a stable artifact file name from the chart title.

    Args:
        title: The chart or map title.
        kind: The image kind, such as ``bar_chart`` or ``zone_map``, so two
            images with the same title keep separate names.

    Returns:
        The PNG file name.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return f"{kind}_{slug}.png" if slug else f"{kind}.png"


async def save_png(
    tool_context: ToolContext, png: bytes, filename: str
) -> None:
    """Save PNG bytes as an ADK artifact that the answer attaches.

    Args:
        tool_context: The ADK tool context of the call.
        png: The PNG image.
        filename: The artifact file name.
    """
    await tool_context.save_artifact(
        filename=filename,
        artifact=types.Part(
            inline_data=types.Blob(mime_type="image/png", data=png)
        ),
    )
    logger.info("Saved image %s (%d bytes)", filename, len(png))


async def save_chart(
    tool_context: ToolContext, fig: Figure, title: str, kind: str
) -> str:
    """Save the rendered chart as a PNG artifact.

    Args:
        tool_context: The ADK tool context of the call.
        fig: The chart figure.
        title: The chart title.
        kind: The chart kind, such as ``bar_chart``.

    Returns:
        The artifact file name.
    """
    filename = chart_filename(title, kind)
    await save_png(tool_context, render_png(fig), filename)
    return filename


def chart_error(tool: str, exc: ChartDataError) -> dict[str, Any]:
    """Log invalid chart input and return the error payload for the model.

    Args:
        tool: The tool name.
        exc: The input error.

    Returns:
        A dictionary with the error status and message.
    """
    logger.warning("%s rejected chart data: %s", tool, exc)
    return {"status": "error", "error": str(exc)}


def category_values(
    data: str,
    label_column: str,
    value_column: str,
    sort_column: str,
    sort_order: str,
) -> tuple[list[str], list[Any], list[float]]:
    """Parse the category labels and values of a bar or donut chart.

    Args:
        data: CSV text with a header row, or a JSON array of row objects.
        label_column: The column that holds the category labels.
        value_column: The column that holds the numeric values.
        sort_column: The column to sort by, or an empty string.
        sort_order: ``asc`` or ``desc``.

    Returns:
        The labels, the raw values, and the numeric values, in row order.

    Raises:
        ChartDataError: If the data, a column, or a value is invalid.
    """
    rows = sort_rows(parse_rows(data), sort_column, sort_order)
    labels = [str(value).strip() for value in column_values(rows, label_column)]
    raw_values = column_values(rows, value_column)
    return labels, raw_values, [parse_numeric(value) for value in raw_values]


def label_bars(
    ax: Axes,
    bars: BarContainer,
    labels: Sequence[str],
    values: Sequence[float],
    currency: bool,
) -> list[str]:
    """Write each bar's value next to its end and build the legend labels.

    Args:
        ax: The plot area.
        bars: The drawn bars.
        labels: One label per bar.
        values: One value per bar.
        currency: Whether the values are US dollars.

    Returns:
        One legend label per bar, with the category and its value.
    """
    legend_labels = []
    for bar, label, value in zip(bars, labels, values, strict=True):
        ax.annotate(
            format_value(value, currency),
            xy=(bar.get_x() + bar.get_width() / 2.0, bar.get_height()),
            xytext=(0, 6 if value >= 0 else -14),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
            color=INK,
        )
        legend_labels.append(
            f"{textwrap.fill(label, width=36)}\n"
            f"   {format_value(value, currency)}"
        )
    return legend_labels


async def render_bar_chart(
    data: str,
    x_column: str,
    y_column: str,
    title: str = "Category comparison",
    sort_column: str = "",
    sort_order: str = "asc",
    palette: str = "corporate",
    *,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Render rows as an executive bar chart with data labels and a legend.

    Use for comparisons across categories, such as available-to-transact
    quantity by hub or net financial benefit by source hub.

    Args:
        data: CSV text with a header row, or a JSON array of row objects.
        x_column: Column holding the category labels.
        y_column: Column holding the numeric values.
        title: Business-oriented chart title.
        sort_column: Optional column to sort by.
        sort_order: "asc" or "desc".
        palette: "corporate", "vibrant", or "monochrome_blue".
        tool_context: The ADK tool context, which ADK passes instead of the
            model.

    Returns:
        The status, the image file name, and a summary, or the status and
        the input error.
    """
    try:
        labels, raw_values, values = category_values(
            data, x_column, y_column, sort_column, sort_order
        )
    except ChartDataError as exc:
        return chart_error("render_bar_chart", exc)

    currency = is_currency(title, y_column, raw_values)
    top_index = values.index(max(values))
    fig, ax = new_figure(right=0.62)
    bars = ax.bar(
        range(len(labels)),
        values,
        color=palette_colors(palette, len(labels)),
        edgecolor=WHITE,
        linewidth=1.5,
        width=0.56,
        zorder=3,
    )
    style_axes(ax, currency)
    lower = min(0.0, min(values) * 1.25)
    upper = max(values) * 1.25 if max(values) > 0 else abs(lower) * 0.1
    ax.set_ylim(lower, upper or 1.0)
    set_category_ticks(ax, labels, width=13 if len(labels) >= 5 else 18)
    y_heading = humanize(y_column)
    ax.set_xlabel(humanize(x_column), labelpad=8, fontweight="bold")
    ax.set_ylabel(y_heading, labelpad=10, fontweight="bold")
    style_legend(
        ax,
        f"{humanize(x_column)} breakdown",
        handles=list(bars),
        labels=label_bars(ax, bars, labels, values, currency),
        labelspacing=0.8,
    )
    draw_frame(
        fig,
        title,
        f"Metric: {y_heading}  |  Highest: {labels[top_index]} "
        f"({format_value(values[top_index], currency)})",
        f"Range: {format_value(min(values), currency)} to "
        f"{format_value(max(values), currency)}",
    )
    filename = await save_chart(tool_context, fig, title, "bar_chart")
    return {
        "status": "success",
        "filename": filename,
        "summary": (
            f"Rendered bar chart '{title}' across {len(labels)} categories. "
            f"The highest is {labels[top_index]} at "
            f"{format_value(values[top_index], currency)}."
        ),
    }


def line_series(
    data: str,
    x_column: str,
    series_names: Sequence[str],
    sort_column: str,
    sort_order: str,
) -> tuple[list[str], dict[str, list[Any]], dict[str, list[float]]]:
    """Parse the x-axis labels and the series of a line chart.

    Args:
        data: CSV text with a header row, or a JSON array of row objects.
        x_column: The column that holds the x-axis labels.
        series_names: The numeric columns, one line per column.
        sort_column: The column to sort by, or an empty string.
        sort_order: ``asc`` or ``desc``.

    Returns:
        The labels, the raw values per series, and the numeric values per
        series.

    Raises:
        ChartDataError: If the list names no series or one series twice,
            or the data, a column, or a value is invalid.
    """
    if not series_names:
        raise ChartDataError("Provide at least one y column.")
    if len(set(series_names)) != len(series_names):
        raise ChartDataError("Name each y column only once.")
    rows = sort_rows(parse_rows(data), sort_column, sort_order)
    labels = [str(value).strip() for value in column_values(rows, x_column)]
    raw_series = {name: column_values(rows, name) for name in series_names}
    series = {
        name: [parse_numeric(value) for value in values]
        for name, values in raw_series.items()
    }
    return labels, raw_series, series


def plot_series(
    ax: Axes,
    series: dict[str, list[float]],
    colors: Sequence[str],
    currency: bool,
) -> None:
    """Plot each series as a line with a label on every point.

    A single series also gets a shaded area under its line.

    Args:
        ax: The plot area.
        series: The numeric values per series name.
        colors: One color per series.
        currency: Whether the values are US dollars.
    """
    for color, (name, values) in zip(colors, series.items(), strict=True):
        positions = range(len(values))
        ax.plot(
            positions,
            values,
            marker="o",
            markersize=7.5,
            markerfacecolor=WHITE,
            markeredgewidth=2.2,
            markeredgecolor=color,
            linewidth=2.8,
            color=color,
            label=(
                f"{humanize(name)} (max {format_value(max(values), currency)})"
            ),
            zorder=4,
        )
        if len(series) == 1:
            ax.fill_between(positions, values, color=color, alpha=0.1)
        for index, value in enumerate(values):
            ax.annotate(
                format_value(value, currency),
                xy=(index, value),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8.5,
                fontweight="bold",
                color=INK,
            )


async def render_line_chart(
    data: str,
    x_column: str,
    y_columns: str,
    title: str = "Trend analysis",
    sort_column: str = "",
    sort_order: str = "asc",
    palette: str = "corporate",
    *,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Render rows as an executive line chart with point labels.

    Use for trends over time, such as projected available-to-transact
    quantity or daily burn by forecast date.

    Args:
        data: CSV text with a header row, or a JSON array of row objects.
        x_column: Column holding the x-axis labels, such as dates.
        y_columns: Comma-separated numeric columns, one line per column.
        title: Business-oriented chart title.
        sort_column: Optional column to sort by.
        sort_order: "asc" or "desc".
        palette: "corporate", "vibrant", or "monochrome_blue".
        tool_context: The ADK tool context, which ADK passes instead of the
            model.

    Returns:
        The status, the image file name, and a summary, or the status and
        the input error.
    """
    series_names = [
        name.strip() for name in y_columns.split(",") if name.strip()
    ]
    try:
        labels, raw_series, series = line_series(
            data, x_column, series_names, sort_column, sort_order
        )
    except ChartDataError as exc:
        return chart_error("render_line_chart", exc)

    currency = is_currency(title, series_names[0], raw_series[series_names[0]])
    fig, ax = new_figure(right=0.64)
    plot_series(
        ax, series, palette_colors(palette, len(series_names)), currency
    )
    all_values = [value for values in series.values() for value in values]
    style_axes(ax, currency)
    peak = max(all_values)
    ax.set_ylim(
        min(0.0, min(all_values) * 1.1), peak * 1.25 if peak > 0 else 1.0
    )
    set_category_ticks(ax, labels, width=18)
    ax.set_xlabel(humanize(x_column), labelpad=8, fontweight="bold")
    ax.set_ylabel(
        humanize(series_names[0]) if len(series_names) == 1 else "Value",
        labelpad=10,
        fontweight="bold",
    )
    style_legend(ax, "Series and peak")
    draw_frame(
        fig,
        title,
        f"Trend across {len(labels)} points  |  "
        f"Peak: {format_value(peak, currency)}",
        f"{len(series_names)} series  •  {len(labels)} data points",
    )
    filename = await save_chart(tool_context, fig, title, "line_chart")
    return {
        "status": "success",
        "filename": filename,
        "summary": (
            f"Rendered line chart '{title}' with {len(labels)} points per "
            f"series. The peak is {format_value(peak, currency)}."
        ),
    }


def draw_donut(
    ax: Axes, values: Sequence[float], colors: Sequence[str], currency: bool
) -> list[Wedge]:
    """Draw the donut slices with their shares and the total in the center.

    Args:
        ax: The plot area.
        values: One non-negative value per slice, with a positive total.
        colors: One color per slice.
        currency: Whether the values are US dollars.

    Returns:
        The drawn slices, in value order.
    """
    total = sum(values)

    def slice_label(percent: float) -> str:
        """Label a slice with its share and value, if it's wide enough.

        Args:
            percent: The slice's share of the total, in percent.

        Returns:
            The label, or an empty string for a slice under 4.5%.
        """
        if percent < 4.5:
            return ""
        return (
            f"{percent:.1f}%\n({format_value(percent * total / 100, currency)})"
        )

    wedges, *text_groups = ax.pie(
        values,
        autopct=slice_label,
        pctdistance=0.74,
        startangle=140,
        colors=colors,
        wedgeprops={"width": 0.52, "edgecolor": WHITE, "linewidth": 2.5},
    )
    for text in text_groups[-1]:
        text.set_color(WHITE)
        text.set_fontsize(9.5)
        text.set_fontweight("bold")
    ax.text(0, 0.08, "TOTAL", ha="center", va="center", color="#64748B")
    ax.text(
        0,
        -0.08,
        format_value(total, currency),
        ha="center",
        va="center",
        fontsize=15,
        fontweight="bold",
        color=INK,
    )
    ax.set_aspect("equal")
    return list(wedges)


async def render_pie_chart(
    data: str,
    label_column: str,
    value_column: str,
    title: str = "Share breakdown",
    sort_column: str = "",
    sort_order: str = "desc",
    palette: str = "corporate",
    *,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Render rows as an executive donut chart with a total callout.

    Use for part-to-whole views, such as SLA-reserved quantity by customer.

    Args:
        data: CSV text with a header row, or a JSON array of row objects.
        label_column: Column holding the slice labels.
        value_column: Column holding the positive numeric values.
        title: Business-oriented chart title.
        sort_column: Optional column to sort by. Defaults to the values.
        sort_order: "asc" or "desc".
        palette: "corporate", "vibrant", or "monochrome_blue".
        tool_context: The ADK tool context, which ADK passes instead of the
            model.

    Returns:
        The status, the image file name, and a summary, or the status and
        the input error.
    """
    try:
        labels, raw_values, values = category_values(
            data,
            label_column,
            value_column,
            sort_column or value_column,
            sort_order,
        )
        if any(value < 0 for value in values) or sum(values) <= 0:
            raise ChartDataError(
                "A donut chart needs non-negative values with a positive total."
            )
    except ChartDataError as exc:
        return chart_error("render_pie_chart", exc)

    currency = is_currency(title, value_column, raw_values)
    total = sum(values)
    top_index = values.index(max(values))
    fig, ax = new_figure(right=0.54)
    ax.set_facecolor(WHITE)
    wedges = draw_donut(
        ax, values, palette_colors(palette, len(labels)), currency
    )
    style_legend(
        ax,
        f"{humanize(label_column)} and {humanize(value_column)} share",
        handles=wedges,
        labels=[
            f"{textwrap.fill(label, width=42)}\n   "
            f"{format_value(value, currency)}  ({value / total * 100:.1f}%)"
            for label, value in zip(labels, values, strict=True)
        ],
        labelspacing=0.85,
    )
    draw_frame(
        fig,
        title,
        f"Largest: {labels[top_index]} "
        f"({format_value(values[top_index], currency)}, "
        f"{values[top_index] / total * 100:.1f}% of total)",
        f"Total: {format_value(total, currency)}  •  {len(labels)} categories",
    )
    filename = await save_chart(tool_context, fig, title, "pie_chart")
    return {
        "status": "success",
        "filename": filename,
        "summary": (
            f"Rendered donut chart '{title}' across {len(labels)} "
            f"categories. The largest is {labels[top_index]}."
        ),
    }


CHART_TOOLS: Final = (
    render_bar_chart,
    render_line_chart,
    render_pie_chart,
)
