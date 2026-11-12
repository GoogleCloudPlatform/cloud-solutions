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

"""Tests for the framework chart tools: rendering, artifacts, and errors."""

import json
import struct
from typing import cast

import pytest
from google.adk.tools.tool_context import ToolContext
from oracle_ebs_scm_agentic_ai import charts
from tests.conftest import FakeContext

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

FORECAST_ROWS = json.dumps(
    [
        {
            "forecast_date": f"2026-10-{26 + day}",
            "projected_att_qty": round(190 - 49.92 * (day + 1), 2),
            "surged_daily_burn_qty": 49.92,
        }
        for day in range(4)
    ]
)
RESERVATION_ROWS = json.dumps(
    [
        {
            "customer_party_name": "Southeast Hospital Care Alliance SLA",
            "reserved_qty": 360,
        },
        {
            "customer_party_name": "Midwest Municipal Grid SLA",
            "reserved_qty": 280,
        },
        {
            "customer_party_name": "Southwest Data Center SLA",
            "reserved_qty": 30,
        },
    ]
)


def png_size(png: bytes) -> tuple[int, int]:
    """Read the width and height from a PNG IHDR chunk."""
    assert png.startswith(PNG_SIGNATURE)
    width, height = struct.unpack(">II", png[16:24])
    return width, height


def saved_png(context: FakeContext, filename: str) -> bytes:
    """Return the PNG bytes of the latest saved artifact version."""
    blob = context.artifacts[filename][-1].inline_data
    assert blob is not None and blob.mime_type == "image/png"
    assert blob.data is not None
    return blob.data


async def test_bar_chart_saves_high_resolution_png(hub_rows_json: str) -> None:
    context = FakeContext()
    result = await charts.render_bar_chart(
        hub_rows_json,
        "organization_code",
        "available_to_transact_qty",
        title="ATT by hub",
        sort_column="available_to_transact_qty",
        sort_order="desc",
        tool_context=cast(ToolContext, context),
    )
    assert result["status"] == "success"
    assert result["filename"] == "bar_chart_att_by_hub.png"
    assert "highest is DAL at 250" in result["summary"]
    width, height = png_size(saved_png(context, "bar_chart_att_by_hub.png"))
    assert width > 2000 and height > 1100


async def test_bar_chart_handles_negative_currency_values() -> None:
    rows = json.dumps(
        [
            {"source_org_code": "DAL", "net_financial_benefit_usd": 50700},
            {"source_org_code": "X9", "net_financial_benefit_usd": -1200.5},
        ]
    )
    context = FakeContext()
    result = await charts.render_bar_chart(
        rows,
        "source_org_code",
        "net_financial_benefit_usd",
        title="Net benefit by source hub",
        tool_context=cast(ToolContext, context),
    )
    assert result["status"] == "success"
    assert "$50,700" in result["summary"]


async def test_bar_chart_badge_shows_range_instead_of_total(
    hub_rows_json: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    frames: list[tuple[str, str]] = []

    def capture_frame(
        fig: object, title: str, subtitle: str, badge: str
    ) -> None:
        del fig, title
        frames.append((subtitle, badge))

    monkeypatch.setattr(charts, "draw_frame", capture_frame)
    result = await charts.render_bar_chart(
        hub_rows_json,
        "organization_code",
        "available_to_transact_qty",
        title="ATT by hub",
        tool_context=cast(ToolContext, FakeContext()),
    )
    assert result["status"] == "success"
    assert frames == [
        (
            "Metric: Available To Transact Qty  |  Highest: DAL (250)",
            "Range: 25 to 250",
        )
    ]


def test_chart_text_draws_dollar_signs_literally() -> None:
    fig, _ = charts.new_figure(right=0.62)
    badge = fig.text(0.96, 0.902, "Range: $49,050 to $50,700")
    assert not badge.get_parse_math()


async def test_line_chart_plots_multiple_series() -> None:
    context = FakeContext()
    result = await charts.render_line_chart(
        FORECAST_ROWS,
        "forecast_date",
        "projected_att_qty, surged_daily_burn_qty",
        title="Miami DC projected ATT",
        tool_context=cast(ToolContext, context),
    )
    assert result["status"] == "success"
    assert result["filename"] == "line_chart_miami_dc_projected_att.png"
    png_size(saved_png(context, "line_chart_miami_dc_projected_att.png"))


async def test_line_chart_shades_a_single_series() -> None:
    context = FakeContext()
    result = await charts.render_line_chart(
        FORECAST_ROWS,
        "forecast_date",
        "surged_daily_burn_qty",
        title="Miami DC daily burn",
        tool_context=cast(ToolContext, context),
    )
    assert result["status"] == "success"
    assert "peak is 49.92" in result["summary"]


async def test_line_chart_rejects_a_repeated_series() -> None:
    context = FakeContext()
    result = await charts.render_line_chart(
        FORECAST_ROWS,
        "forecast_date",
        "projected_att_qty, projected_att_qty",
        tool_context=cast(ToolContext, context),
    )
    assert result == {
        "status": "error",
        "error": "Name each y column only once.",
    }
    assert not context.artifacts


async def test_pie_chart_renders_reservation_share() -> None:
    context = FakeContext()
    result = await charts.render_pie_chart(
        RESERVATION_ROWS,
        "customer_party_name",
        "reserved_qty",
        title="SLA reservations by customer",
        tool_context=cast(ToolContext, context),
    )
    assert result["status"] == "success"
    assert "Southeast Hospital Care Alliance SLA" in result["summary"]


async def test_chart_accepts_csv_and_row_wrappers() -> None:
    context = FakeContext()
    csv_result = await charts.render_bar_chart(
        "hub,att\nD1,250\nP1,150\n",
        "hub",
        "att",
        title="CSV chart",
        tool_context=cast(ToolContext, context),
    )
    wrapped = json.dumps({"rows": [{"hub": "DAL", "att": "1,250"}]})
    wrapped_result = await charts.render_bar_chart(
        wrapped,
        "hub",
        "att",
        title="",
        tool_context=cast(ToolContext, context),
    )
    assert csv_result["status"] == "success"
    assert wrapped_result["filename"] == "bar_chart.png"


@pytest.mark.parametrize(
    ("data", "x_column", "y_column", "message"),
    [
        ("{not json", "hub", "att", "Invalid JSON"),
        ("[]", "hub", "att", "at least one row"),
        ('[{"hub": "DAL"}]', "hub", "att", "Column 'att' is missing"),
        (
            '[{"hub": "DAL", "att": null}]',
            "hub",
            "att",
            "missing or not numeric",
        ),
        ('[{"hub": "DAL", "att": "many"}]', "hub", "att", "not numeric"),
        ('[{"hub": "DAL", "att": true}]', "hub", "att", "not numeric"),
        ("[1, 2]", "hub", "att", "must be an object"),
        ('{"other": []}', "hub", "att", "at least one row"),
        ("", "hub", "att", "CSV with a header"),
    ],
)
async def test_bar_chart_rejects_invalid_data(
    data: str, x_column: str, y_column: str, message: str
) -> None:
    context = FakeContext()
    result = await charts.render_bar_chart(
        data, x_column, y_column, tool_context=cast(ToolContext, context)
    )
    assert result["status"] == "error"
    assert message in result["error"]
    assert not context.artifacts


async def test_line_and_pie_reject_invalid_series() -> None:
    context = FakeContext()
    line = await charts.render_line_chart(
        FORECAST_ROWS,
        "forecast_date",
        " ",
        tool_context=cast(ToolContext, context),
    )
    pie = await charts.render_pie_chart(
        '[{"label": "A", "value": 0}]',
        "label",
        "value",
        tool_context=cast(ToolContext, context),
    )
    negative_pie = await charts.render_pie_chart(
        '[{"label": "A", "value": 5}, {"label": "B", "value": -1}]',
        "label",
        "value",
        tool_context=cast(ToolContext, context),
    )
    assert line["status"] == "error"
    assert pie["status"] == "error"
    assert negative_pie["status"] == "error"
    assert not context.artifacts


def test_formatting_helpers() -> None:
    assert charts.format_value(1800, currency=True) == "$1,800"
    assert charts.format_value(49.92, currency=True) == "$49.92"
    assert charts.format_value(49.92) == "49.92"
    assert charts.format_value(250.0) == "250"
    assert charts.humanize("sla_reserved_qty") == "SLA Reserved Qty"
    assert charts.humanize("effective_eta_hours") == "Effective ETA Hours"
    assert charts.is_currency("Freight", "cost", [])
    assert charts.is_currency("Hubs", "value", ["$5"])
    assert not charts.is_currency("Hubs", "units", [5])
    assert charts.palette_colors("unknown", 2) == list(
        charts.COLOR_PALETTES["corporate"][:2]
    )
    assert charts.chart_filename("  !!  ", "pie_chart") == "pie_chart.png"
    assert charts.parse_numeric("$1,250.50") == 1250.5
    with pytest.raises(charts.ChartDataError):
        charts.parse_numeric(None)


def test_scores_are_not_dollars() -> None:
    assert not charts.is_currency(
        "Zone demand exposure", "exposure_score", [8.4]
    )
    assert charts.is_currency("Line stop", "line_stop_exposure_usd", [1])


@pytest.mark.parametrize("value", ["NaN", "inf", "-Infinity", float("nan")])
def test_non_finite_numbers_are_rejected(value: object) -> None:
    with pytest.raises(charts.ChartDataError, match="finite"):
        charts.parse_numeric(value)


@pytest.mark.parametrize(
    "data",
    [
        "label,value\nMiami, FL,12\n",
        "label,value\nMiami\n",
    ],
)
def test_csv_rows_with_shifted_columns_are_rejected(data: str) -> None:
    with pytest.raises(charts.ChartDataError, match="Quote every value"):
        charts.parse_rows(data)


async def test_nan_values_return_a_chart_error() -> None:
    context = FakeContext()
    result = await charts.render_bar_chart(
        '[{"hub": "MIA", "qty": NaN}]',
        "hub",
        "qty",
        title="ATT by hub",
        tool_context=cast(ToolContext, context),
    )
    assert result["status"] == "error"
    assert not context.artifacts


def test_chart_files_are_named_by_kind_and_title() -> None:
    assert (
        charts.chart_filename("ATT by hub", "bar_chart")
        == "bar_chart_att_by_hub.png"
    )
    assert (
        charts.chart_filename("ATT by hub", "line_chart")
        == "line_chart_att_by_hub.png"
    )


def test_sort_rows_orders_text_and_numbers() -> None:
    rows = [{"hub": "b", "qty": "10"}, {"hub": "a", "qty": "9"}]
    assert charts.sort_rows(rows, "qty", "desc")[0]["hub"] == "b"
    assert charts.sort_rows(rows, "hub", "asc")[0]["hub"] == "a"
    assert charts.sort_rows(rows, "", "asc") == rows
