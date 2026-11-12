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

"""Tests for the Maps Static API map tools: signing, geometry, and errors."""

import csv
import io
import json
import math
import urllib.error
import urllib.request
from collections.abc import Callable
from email.message import Message
from typing import Any, cast
from urllib.parse import parse_qsl, urlsplit

import h3
import pytest
from google.adk.models.llm_request import LlmRequest
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from oracle_ebs_scm_agentic_ai import maps
from oracle_ebs_scm_agentic_ai.config import Settings
from tests.conftest import DOCS_URL_SIGNER, TEST_ENVIRONMENT, FakeContext

PNG_BYTES = b"\x89PNG\r\n\x1a\nmap"
# URL signing example from the Google Maps Platform documentation.
DOCS_PATH = "/maps/api/geocode/json?address=New+York&client=clientID"
DOCS_SIGNATURE = "chaRF2hTJKOScPr-RQCEhZbSzIE="
# Encoded polyline example from the Google Maps Platform documentation.
DOCS_POINTS = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
DOCS_POLYLINE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
HUB: dict[str, Any] = {
    "center_label": "Miami DC",
    "center_latitude": 25.7617,
    "center_longitude": -80.1918,
}
DESTINATION: dict[str, Any] = {
    "destination_label": "Miami DC",
    "destination_latitude": 25.7617,
    "destination_longitude": -80.1918,
}
LANE_ROWS: list[dict[str, Any]] = [
    {
        "label": "Dallas DC",
        "latitude": 32.7767,
        "longitude": -96.797,
        "sla_compliant": True,
    },
    {
        "label": "Atlanta DC",
        "latitude": 33.749,
        "longitude": -84.388,
        "sla_compliant": "false",
    },
    {
        "label": "Phoenix DC",
        "latitude": 33.4484,
        "longitude": -112.074,
        "sla_compliant": " TRUE ",
    },
]


def place_rows(count: int, label: str = "Zone") -> list[dict[str, Any]]:
    """Rows north-east of the hub with scores falling from 10."""
    return [
        {
            "label": f"{label} {index}",
            "latitude": round(25.70 + index * 0.01, 4),
            "longitude": round(-80.30 + index * 0.01, 4),
            "score": round(10 * (count - index) / count, 2),
        }
        for index in range(count)
    ]


def query(url: str, name: str) -> list[str]:
    """Return the decoded values of one map URL query parameter."""
    params = parse_qsl(urlsplit(url).query)
    return [value for key, value in params if key == name]


def haversine_km(start: tuple[float, float], end: tuple[float, float]) -> float:
    """Return the great-circle distance between two points."""
    lat1, lng1, lat2, lng2 = map(math.radians, (*start, *end))
    term = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * maps.EARTH_RADIUS_KM * math.asin(math.sqrt(term))


@pytest.fixture(name="tools")
def fixture_tools(settings: Settings) -> dict[str, maps.MapTool]:
    """Map tools built from the test settings, keyed by name."""
    return {tool.__name__: tool for tool in maps.build_map_tools(settings)}


@pytest.fixture(name="fetched")
def fixture_fetched(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record map URLs and answer with a PNG instead of calling Google."""
    urls: list[str] = []

    async def fake_fetch(url: str) -> bytes:
        urls.append(url)
        return PNG_BYTES

    monkeypatch.setattr(maps, "fetch_png", fake_fetch)
    return urls


def test_sign_path_matches_the_documented_example() -> None:
    assert maps.sign_path(DOCS_PATH, DOCS_URL_SIGNER) == DOCS_SIGNATURE


def test_encode_polyline_matches_the_documented_example() -> None:
    assert maps.encode_polyline(DOCS_POINTS) == DOCS_POLYLINE


@pytest.mark.parametrize("center", [(25.7617, -80.1918), (0.0, 179.9)])
def test_circle_points_form_a_closed_ring(center: tuple[float, float]) -> None:
    ring = maps.circle_points(*center, radius_km=50.0)
    assert len(ring) == 49
    assert ring[0] == ring[-1]
    assert all(-180.0 <= longitude < 180.0 for _, longitude in ring)
    for point in ring:
        assert math.isclose(haversine_km(center, point), 50.0, rel_tol=1e-6)


def test_map_tools_expose_adk_function_schemas(settings: Settings) -> None:
    request = LlmRequest()
    request.append_tools(
        [FunctionTool(tool) for tool in maps.build_map_tools(settings)]
    )
    assert request.config.tools is not None
    [tool] = request.config.tools
    assert isinstance(tool, types.Tool) and tool.function_declarations
    schemas = {
        declaration.name: cast(
            dict[str, Any], declaration.parameters_json_schema
        )
        for declaration in tool.function_declarations
    }
    assert schemas["render_zone_map"]["required"] == [
        "data",
        "title",
        "center_label",
        "center_latitude",
        "center_longitude",
        "radius_km",
    ]
    assert "stores" in schemas["render_zone_map"]["properties"]
    assert schemas["render_heatmap"]["required"] == list(
        schemas["render_heatmap"]["properties"]
    )
    assert list(schemas["render_heatmap"]["properties"]) == [
        "data",
        "title",
        "center_label",
        "center_latitude",
        "center_longitude",
        "radius_km",
    ]
    assert list(schemas["render_lane_map"]["properties"]) == [
        "data",
        "title",
        "destination_label",
        "destination_latitude",
        "destination_longitude",
    ]


async def test_zone_map_numbers_the_highest_scores(
    tools: dict[str, maps.MapTool], fetched: list[str]
) -> None:
    context = FakeContext()
    stores = json.dumps(place_rows(2, "Store"))
    result = await tools["render_zone_map"](
        json.dumps(place_rows(12)[::-1]),
        "Miami DC zone exposure",
        radius_km=50,
        stores=stores,
        tool_context=cast(ToolContext, context),
        **HUB,
    )
    assert result["status"] == "success"
    assert result["filename"] == "zone_map_miami_dc_zone_exposure.png"
    assert result["legend"][0] == {
        "marker": "1",
        "label": "Zone 0",
        "score": 10,
    }
    assert [item["marker"] for item in result["legend"]] == list("123456789")
    assert "2 nearby places" in result["summary"]
    blob = context.artifacts["zone_map_miami_dc_zone_exposure.png"][
        -1
    ].inline_data
    assert blob is not None and blob.mime_type == "image/png"
    assert blob.data == PNG_BYTES
    [url] = fetched
    assert query(url, "size") == ["640x400"]
    assert query(url, "scale") == ["2"]
    assert query(url, "style") == ["feature:poi|visibility:off"]
    markers = query(url, "markers")
    assert markers[0] == "size:mid|color:0xD93025|label:1|25.70000,-80.30000"
    assert markers[4].startswith("size:mid|color:0xF29900|label:5|")
    assert markers[8].startswith("size:mid|color:0x188038|label:9|")
    assert markers[9].startswith("size:small|color:0x188038|")
    assert len(markers[9].split("|")) == 5
    assert markers[10] == "size:mid|color:0x0B57D0|label:H|25.76170,-80.19180"
    assert markers[11] == (
        "size:small|color:0x7627BB|25.70000,-80.30000|25.71000,-80.29000"
    )
    [ring] = query(url, "path")
    assert ring.startswith(
        "color:0x0B57D0CC|weight:3|fillcolor:0x0B57D014|enc:"
    )


async def test_zone_map_without_ring_or_stores(
    tools: dict[str, maps.MapTool], fetched: list[str]
) -> None:
    result = await tools["render_zone_map"](
        json.dumps(place_rows(1)),
        "",
        radius_km=0,
        stores="[]",
        tool_context=cast(ToolContext, FakeContext()),
        **HUB,
    )
    assert result["filename"] == "zone_map.png"
    assert "nearby places" not in result["summary"]
    assert query(fetched[0], "path") == []
    assert len(query(fetched[0], "markers")) == 2


async def test_largest_zone_map_fits_the_url_limit(
    tools: dict[str, maps.MapTool], fetched: list[str]
) -> None:
    result = await tools["render_zone_map"](
        json.dumps(place_rows(maps.MAX_ZONES)),
        "All zones",
        radius_km=maps.MAX_RADIUS_KM,
        stores=json.dumps(place_rows(maps.MAX_STORES, "Store")),
        tool_context=cast(ToolContext, FakeContext()),
        **HUB,
    )
    assert result["status"] == "success"
    assert len(fetched[0]) <= maps.MAX_URL_CHARS


# The Places Insights heatmap cells are H3 resolution 7.
MIAMI_CELL: str = h3.latlng_to_cell(25.8195, -80.3553, 7)


def cell_rows(count: int) -> list[dict[str, Any]]:
    """Rows for distinct cells around the Miami DC cell, scores from 10."""
    cells = sorted(h3.grid_disk(MIAMI_CELL, 6))[:count]
    return [
        {"h3_cell_index": cell, "score": round(10 * (count - index) / count, 2)}
        for index, cell in enumerate(cells)
    ]


async def test_heatmap_colors_cells_by_density_score(
    tools: dict[str, maps.MapTool], fetched: list[str]
) -> None:
    rows = cell_rows(3)
    first_cell = rows[0]["h3_cell_index"]
    rows[0]["h3_cell_index"] = f" {first_cell.upper()} "
    context = FakeContext()
    result = await tools["render_heatmap"](
        json.dumps(rows),
        "Miami DC place density",
        radius_km=15,
        tool_context=cast(ToolContext, context),
        **HUB,
    )
    assert result["status"] == "success"
    assert result["filename"] == "heatmap_miami_dc_place_density.png"
    assert result["summary"].startswith("Drew 3 H3 cells around Miami DC")
    assert result["legend"] == [
        {"color": "red", "scores": "7 to 10", "cells": 1},
        {"color": "amber", "scores": "4 to 7", "cells": 1},
        {"color": "green", "scores": "below 4", "cells": 1},
    ]
    assert context.artifacts["heatmap_miami_dc_place_density.png"]
    [url] = fetched
    *cells, ring = query(url, "path")
    for path, row, color in zip(
        cells, cell_rows(3), (maps.RED, maps.AMBER, maps.GREEN), strict=True
    ):
        boundary = h3.cell_to_boundary(row["h3_cell_index"])
        encoded = maps.encode_polyline([*boundary, boundary[0]])
        style = f"color:{color}99|weight:1|fillcolor:{color}66"
        assert path == f"{style}|enc:{encoded}"
    assert ring.startswith("color:0x0B57D0CC|weight:3|fillcolor:0x0B57D014|")
    assert query(url, "markers") == [
        "size:mid|color:0x0B57D0|label:H|25.76170,-80.19180"
    ]


async def test_largest_heatmap_fits_the_url_limit(
    tools: dict[str, maps.MapTool], fetched: list[str]
) -> None:
    result = await tools["render_heatmap"](
        json.dumps(cell_rows(maps.MAX_CELLS)),
        "All cells",
        radius_km=maps.MAX_RADIUS_KM,
        tool_context=cast(ToolContext, FakeContext()),
        **HUB,
    )
    assert result["status"] == "success"
    assert len(query(fetched[0], "path")) == maps.MAX_CELLS + 1
    assert len(fetched[0]) <= maps.MAX_URL_CHARS


VALID_CELLS = json.dumps(cell_rows(3))


@pytest.mark.parametrize(
    ("data", "overrides", "message"),
    [
        (
            '[{"h3_cell_index": "nope", "score": 5}]',
            {},
            "'nope' is not an H3 cell index.",
        ),
        (
            '[{"h3_cell_index": null, "score": 5}]',
            {},
            "None is not an H3 cell index.",
        ),
        (
            json.dumps([{**cell_rows(1)[0], "score": 11}]),
            {},
            "score must be from 0 to 10, not 11.",
        ),
        ('[{"score": 5}]', {}, "Column 'h3_cell_index' is missing"),
        (json.dumps(cell_rows(81)), {}, "at most 80 cells, not 81"),
        (VALID_CELLS, {"center_longitude": 200}, "longitude must be from"),
        (VALID_CELLS, {"radius_km": 1001}, "radius_km must be from 0 to 1000"),
    ],
)
async def test_heatmap_rejects_invalid_input(
    tools: dict[str, maps.MapTool],
    fetched: list[str],
    data: str,
    overrides: dict[str, Any],
    message: str,
) -> None:
    context = FakeContext()
    result = await tools["render_heatmap"](
        data,
        "Cells",
        tool_context=cast(ToolContext, context),
        **{**HUB, "radius_km": 15.0, **overrides},
    )
    assert result["status"] == "error"
    assert message in result["error"]
    assert not context.artifacts
    assert not fetched


async def test_lane_map_colors_lanes_by_sla_compliance(
    tools: dict[str, maps.MapTool], fetched: list[str]
) -> None:
    result = await tools["render_lane_map"](
        json.dumps(LANE_ROWS),
        "Transfer lanes to Miami DC",
        tool_context=cast(ToolContext, FakeContext()),
        **DESTINATION,
    )
    assert result["status"] == "success"
    assert result["filename"] == "lane_map_transfer_lanes_to_miami_dc.png"
    assert "2 SLA-compliant in green and 1 locked" in result["summary"]
    assert result["legend"] == [
        {"marker": "1", "label": "Dallas DC", "sla_compliant": True},
        {"marker": "2", "label": "Atlanta DC", "sla_compliant": False},
        {"marker": "3", "label": "Phoenix DC", "sla_compliant": True},
    ]
    destination = "25.76170,-80.19180"
    assert query(fetched[0], "path") == [
        f"color:{style}|geodesic:true|{source}|{destination}"
        for style, source in (
            ("0x188038CC|weight:5", "32.77670,-96.79700"),
            ("0xD93025CC|weight:3", "33.74900,-84.38800"),
            ("0x188038CC|weight:5", "33.44840,-112.07400"),
        )
    ]
    assert query(fetched[0], "markers") == [
        "size:mid|color:0x188038|label:1|32.77670,-96.79700",
        "size:mid|color:0xD93025|label:2|33.74900,-84.38800",
        "size:mid|color:0x188038|label:3|33.44840,-112.07400",
        f"size:mid|color:0x0B57D0|label:D|{destination}",
    ]


def csv_text(rows: list[dict[str, Any]]) -> str:
    """Write rows as CSV text with a header row, the way Gemini passes them."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


ROW_ENCODERS: tuple[Callable[[list[dict[str, Any]]], str], ...] = (
    json.dumps,
    csv_text,
)


@pytest.mark.parametrize(
    ("tool", "tables", "arguments"),
    [
        (
            "render_zone_map",
            {
                "data": place_rows(12, "Hialeah, FL"),
                "stores": place_rows(2, "Lowe's, Hialeah"),
            },
            {**HUB, "radius_km": 15.0},
        ),
        ("render_heatmap", {"data": cell_rows(5)}, {**HUB, "radius_km": 15.0}),
        ("render_lane_map", {"data": LANE_ROWS}, DESTINATION),
    ],
)
async def test_maps_draw_the_same_map_from_csv_rows(
    tools: dict[str, maps.MapTool],
    fetched: list[str],
    tool: str,
    tables: dict[str, list[dict[str, Any]]],
    arguments: dict[str, Any],
) -> None:
    for encode in ROW_ENCODERS:
        result = await tools[tool](
            title="Map",
            tool_context=cast(ToolContext, FakeContext()),
            **{name: encode(rows) for name, rows in tables.items()},
            **arguments,
        )
        assert result["status"] == "success"
    from_json, from_csv = fetched
    assert from_csv == from_json


async def test_map_urls_end_with_the_key_and_a_valid_signature(
    tools: dict[str, maps.MapTool], fetched: list[str]
) -> None:
    await tools["render_lane_map"](
        json.dumps(LANE_ROWS),
        "Lanes",
        tool_context=cast(ToolContext, FakeContext()),
        **DESTINATION,
    )
    unsigned, signature = fetched[0].split("&signature=")
    parts = urlsplit(unsigned)
    assert f"{parts.scheme}://{parts.netloc}" == maps.STATIC_MAP_HOST
    assert parts.path == maps.STATIC_MAP_PATH
    assert parse_qsl(parts.query)[-1] == (
        "key",
        TEST_ENVIRONMENT["MAPS_STATIC_API_KEY"],
    )
    assert signature == maps.sign_path(
        f"{parts.path}?{parts.query}", DOCS_URL_SIGNER
    )


VALID_ZONES = json.dumps(place_rows(3))
ZONE: dict[str, Any] = {
    "label": "A",
    "latitude": 25.8,
    "longitude": -80.2,
    "score": 5,
}


def one_zone(**changes: Any) -> str:
    """Return one zone row as JSON with some columns changed."""
    return json.dumps([{**ZONE, **changes}])


@pytest.mark.parametrize(
    ("data", "overrides", "message"),
    [
        (
            '[{"label": "A", "latitude": 25.8, "longitude": -80.2}]',
            {},
            "Column 'score' is missing",
        ),
        (one_zone(latitude="north"), {}, "not numeric"),
        (one_zone(latitude=91), {}, "latitude must be from -90 to 90, not 91."),
        (one_zone(longitude=-181), {}, "longitude must be from -180 to 180"),
        (one_zone(score=10.5), {}, "score must be from 0 to 10"),
        (one_zone(label=" "), {}, "non-empty label"),
        (one_zone(label=None), {}, "non-empty label"),
        ("[]", {}, "at least one row"),
        (json.dumps(place_rows(61)), {}, "at most 60 zones, not 61"),
        (VALID_ZONES, {"center_latitude": 95}, "latitude must be from -90"),
        (VALID_ZONES, {"center_label": ""}, "non-empty label"),
        (VALID_ZONES, {"radius_km": -5}, "radius_km must be from 0 to 1000"),
        (
            VALID_ZONES,
            {"stores": '[{"label": "Store", "latitude": 25.8}]'},
            "Column 'longitude' is missing",
        ),
        (
            VALID_ZONES,
            {"stores": json.dumps(place_rows(21, "Store"))},
            "at most 20 stores",
        ),
    ],
)
async def test_zone_map_rejects_invalid_input(
    tools: dict[str, maps.MapTool],
    fetched: list[str],
    data: str,
    overrides: dict[str, Any],
    message: str,
) -> None:
    context = FakeContext()
    result = await tools["render_zone_map"](
        data,
        "Zones",
        tool_context=cast(ToolContext, context),
        **{**HUB, "radius_km": 50.0, **overrides},
    )
    assert result["status"] == "error"
    assert message in result["error"]
    assert not context.artifacts
    assert not fetched


def one_lane(**changes: Any) -> str:
    """Return one lane row as JSON with some columns changed."""
    return json.dumps([{**LANE_ROWS[0], **changes}])


@pytest.mark.parametrize(
    ("data", "overrides", "message"),
    [
        (
            one_lane(sla_compliant="yes"),
            {},
            "sla_compliant must be true or false, not 'yes'.",
        ),
        (one_lane(sla_compliant=1), {}, "true or false"),
        (one_lane(sla_compliant=None), {}, "true or false"),
        (
            "label,latitude,longitude,sla_compliant\nD1,32.7,-96.8,maybe",
            {},
            "true or false",
        ),
        (json.dumps(LANE_ROWS * 4), {}, "at most 9 lanes, not 12"),
        (
            '[{"label": "Dallas DC", "latitude": 32.7, "longitude": -96.8}]',
            {},
            "Column 'sla_compliant' is missing",
        ),
        (one_lane(), {"destination_longitude": "east"}, "not numeric"),
        (one_lane(), {"destination_latitude": -91}, "latitude must be from"),
    ],
)
async def test_lane_map_rejects_invalid_input(
    tools: dict[str, maps.MapTool],
    fetched: list[str],
    data: str,
    overrides: dict[str, Any],
    message: str,
) -> None:
    context = FakeContext()
    result = await tools["render_lane_map"](
        data,
        "Lanes",
        tool_context=cast(ToolContext, context),
        **{**DESTINATION, **overrides},
    )
    assert result["status"] == "error"
    assert message in result["error"]
    assert not context.artifacts
    assert not fetched


async def test_too_long_map_url_is_rejected(
    tools: dict[str, maps.MapTool],
    fetched: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maps, "MAX_URL_CHARS", 500)
    result = await tools["render_zone_map"](
        VALID_ZONES,
        "Zones",
        radius_km=50.0,
        tool_context=cast(ToolContext, FakeContext()),
        **HUB,
    )
    assert result == {"status": "error", "error": maps.URL_TOO_LONG}
    assert not fetched


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.HTTPError(
            maps.STATIC_MAP_HOST, 403, "Forbidden", Message(), None
        ),
        urllib.error.URLError("Name or service not known"),
        TimeoutError("timed out"),
        maps.MapServiceError("The Maps Static API returned text/html."),
    ],
)
async def test_map_service_failures_return_a_friendly_error(
    tools: dict[str, maps.MapTool],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    async def failing_fetch(url: str) -> bytes:
        del url
        raise error

    monkeypatch.setattr(maps, "fetch_png", failing_fetch)
    context = FakeContext()
    result = await tools["render_lane_map"](
        json.dumps(LANE_ROWS),
        "Lanes",
        tool_context=cast(ToolContext, context),
        **DESTINATION,
    )
    assert result == {"status": "error", "error": maps.MAP_UNAVAILABLE}
    assert not context.artifacts


class FakeResponse:
    """Minimal ``urlopen`` response with a content type and a body."""

    def __init__(self, content_type: str, body: bytes = PNG_BYTES) -> None:
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.body = body
        self.read_limits: list[int] = []

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        del exc_info

    def read(self, limit: int) -> bytes:
        self.read_limits.append(limit)
        return self.body[:limit]


async def test_fetch_png_uses_a_timeout_and_rejects_other_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, float]] = []
    content_types = iter(["image/png", "text/html; charset=UTF-8"])

    def fake_urlopen(url: str, timeout: float) -> FakeResponse:
        calls.append((url, timeout))
        return FakeResponse(next(content_types))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert await maps.fetch_png("https://maps.googleapis.com/a") == PNG_BYTES
    with pytest.raises(maps.MapServiceError, match="text/html"):
        await maps.fetch_png("https://maps.googleapis.com/b")
    assert calls == [
        ("https://maps.googleapis.com/a", 20.0),
        ("https://maps.googleapis.com/b", 20.0),
    ]


def test_download_stops_reading_large_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse("image/png", b"x" * (maps.MAX_PNG_BYTES + 10))
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda url, timeout: response
    )
    with pytest.raises(maps.MapServiceError, match="more than"):
        maps.download("https://maps.googleapis.com/large")
    assert response.read_limits == [maps.MAX_PNG_BYTES + 1]
