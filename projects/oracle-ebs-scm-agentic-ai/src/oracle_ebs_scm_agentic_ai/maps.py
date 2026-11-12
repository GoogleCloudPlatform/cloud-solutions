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

"""Google map tools drawn by the Google Maps Platform Maps Static API.

Google Maps Platform terms allow Places and Routes content only on Google
maps, so Google draws every marker, line, and cell. Each tool validates the
rows it receives, builds a Maps Static API request, signs it with the URL
signing secret, fetches the PNG server side, and saves it as an ADK artifact
that ``agent.complete_answer`` adds to the answer. The Maps Static API has no
Python client library that supports URL signing with an API key, so the tools
use the standard library HTTP client. The H3 library turns the H3 cell indexes
from Places Insights into hexagon boundaries.
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import math
import urllib.request
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from http.client import HTTPException
from typing import Any, Final
from urllib.parse import urlencode

import h3
from google.adk.tools.tool_context import ToolContext
from oracle_ebs_scm_agentic_ai import charts
from oracle_ebs_scm_agentic_ai.charts import (
    ChartDataError,
    Row,
    chart_error,
    chart_filename,
    column_values,
    parse_numeric,
    parse_rows,
    save_png,
)
from oracle_ebs_scm_agentic_ai.config import Settings

logger = logging.getLogger(__name__)

MapTool = Callable[..., Awaitable[dict[str, Any]]]
Param = tuple[str, str]


def static_color(color: str) -> str:
    """Convert a ``#RRGGBB`` brand color to the Maps Static API form.

    Args:
        color: The color in ``#RRGGBB`` form.

    Returns:
        The color in ``0xRRGGBB`` form.
    """
    return "0x" + color.removeprefix("#")


STATIC_MAP_HOST: Final[str] = "https://maps.googleapis.com"
STATIC_MAP_PATH: Final[str] = "/maps/api/staticmap"
BASE_PARAMS: Final[tuple[Param, ...]] = (
    ("size", "640x400"),
    ("scale", "2"),
    ("style", "feature:poi|visibility:off"),
)
MAX_URL_CHARS: Final[int] = 16_384
MAX_ZONES: Final[int] = 60
MAX_STORES: Final[int] = 20
MAX_LANES: Final[int] = 9
MAX_CELLS: Final[int] = 80
NUMBERED_ZONES: Final[int] = 9
MAX_RADIUS_KM: Final[float] = 1_000.0
FETCH_TIMEOUT_SECONDS: Final[float] = 20.0
# A 1280 x 800 map PNG is well under 1 MiB: anything larger isn't a map.
MAX_PNG_BYTES: Final[int] = 4 * 1024 * 1024
EARTH_RADIUS_KM: Final[float] = 6_371.0088
RED: Final[str] = static_color(charts.RED)
AMBER: Final[str] = static_color(charts.AMBER)
GREEN: Final[str] = static_color(charts.GREEN)
BLUE: Final[str] = static_color(charts.BLUE)
PURPLE: Final[str] = static_color(charts.PURPLE)
SCORE_TIERS: Final[tuple[tuple[float, str], ...]] = (
    (7.0, RED),
    (4.0, AMBER),
    (0.0, GREEN),
)
HEAT_LEGEND: Final[tuple[tuple[str, str, str], ...]] = (
    ("red", RED, "7 to 10"),
    ("amber", AMBER, "4 to 7"),
    ("green", GREEN, "below 4"),
)
RING_STYLE: Final[str] = f"color:{BLUE}CC|weight:3|fillcolor:{BLUE}14"
LANE_STYLES: Final[dict[bool, tuple[str, int]]] = {
    True: (GREEN, 5),
    False: (RED, 3),
}
BOOLEAN_TEXT: Final[dict[str, bool]] = {"true": True, "false": False}
URL_TOO_LONG: Final[str] = (
    "The map has too many points to draw. Show fewer zones or stores."
)
MAP_UNAVAILABLE: Final[str] = (
    "The map service is unavailable right now. Try again in a minute."
)


class MapServiceError(RuntimeError):
    """A Maps Static API response that isn't a PNG image."""


@dataclass(frozen=True)
class Place:
    """A labeled point on the map.

    Attributes:
        label: The place name.
        latitude: The latitude in degrees.
        longitude: The longitude in degrees.
    """

    label: str
    latitude: float
    longitude: float

    @property
    def location(self) -> str:
        """The point in the Maps Static API ``latitude,longitude`` form."""
        return f"{self.latitude:.5f},{self.longitude:.5f}"


@dataclass(frozen=True)
class MapPlan:
    """Maps Static API parameters and the text that the model receives.

    Attributes:
        params: The Maps Static API query parameters, without the key.
        summary: The one-sentence summary for the model.
        legend: The legend entries that number the markers.
    """

    params: list[Param]
    summary: str
    legend: list[dict[str, Any]]


def encode_polyline(points: Iterable[tuple[float, float]]) -> str:
    """Encode points with the Google encoded polyline algorithm.

    Args:
        points: Latitude and longitude pairs in degrees.

    Returns:
        The encoded polyline.
    """
    chunks: list[str] = []
    previous = (0, 0)
    for latitude, longitude in points:
        current = (round(latitude * 1e5), round(longitude * 1e5))
        for delta in (current[0] - previous[0], current[1] - previous[1]):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                chunks.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            chunks.append(chr(value + 63))
        previous = current
    return "".join(chunks)


def circle_points(
    latitude: float, longitude: float, radius_km: float, steps: int = 48
) -> list[tuple[float, float]]:
    """Compute a closed ring of points at a distance around a center.

    Args:
        latitude: The center latitude in degrees.
        longitude: The center longitude in degrees.
        radius_km: The ring radius in kilometers.
        steps: The number of distinct points on the ring.

    Returns:
        ``steps`` points plus the first point again, which closes the ring.
    """
    lat = math.radians(latitude)
    lng = math.radians(longitude)
    angle = radius_km / EARTH_RADIUS_KM
    ring: list[tuple[float, float]] = []
    for step in range(steps):
        bearing = 2 * math.pi * step / steps
        point_lat = math.asin(
            math.sin(lat) * math.cos(angle)
            + math.cos(lat) * math.sin(angle) * math.cos(bearing)
        )
        point_lng = lng + math.atan2(
            math.sin(bearing) * math.sin(angle) * math.cos(lat),
            math.cos(angle) - math.sin(lat) * math.sin(point_lat),
        )
        ring.append(
            (
                math.degrees(point_lat),
                (math.degrees(point_lng) + 540.0) % 360.0 - 180.0,
            )
        )
    # The Maps Static API strokes a filled path's outline only when the last
    # point repeats the first.
    return [*ring, ring[0]]


def sign_path(path_and_query: str, secret: str) -> str:
    """Sign a Maps Static API path and query with the URL signing secret.

    Google Maps Platform URL signing defines the algorithm: HMAC-SHA1 over
    the exact path and query that the request sends, keyed with the
    URL-safe Base64-decoded signing secret.

    Args:
        path_and_query: The URL path and query string, without the host.
        secret: The URL-safe Base64 signing secret.

    Returns:
        The URL-safe Base64 signature.
    """
    digest = hmac.new(
        base64.urlsafe_b64decode(secret),
        path_and_query.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def signed_url(params: Sequence[Param], api_key: str, secret: str) -> str:
    """Build a Maps Static API URL that ends with the key and the signature.

    Args:
        params: The map parameters.
        api_key: The Maps Static API key.
        secret: The URL signing secret.

    Returns:
        The signed URL.

    Raises:
        ChartDataError: If the URL exceeds the Maps Static API size limit.
    """
    query = urlencode([*params, ("key", api_key)])
    path_and_query = f"{STATIC_MAP_PATH}?{query}"
    signature = sign_path(path_and_query, secret)
    url = f"{STATIC_MAP_HOST}{path_and_query}&signature={signature}"
    if len(url) > MAX_URL_CHARS:
        raise ChartDataError(URL_TOO_LONG)
    return url


def download(url: str) -> tuple[str, bytes]:
    """Download a URL with a timeout and a size limit.

    Args:
        url: The URL.

    Returns:
        The response content type and body.

    Raises:
        MapServiceError: If the body is larger than ``MAX_PNG_BYTES``.
    """
    with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_SECONDS) as response:
        content_type: str = response.headers.get_content_type()
        body: bytes = response.read(MAX_PNG_BYTES + 1)
    if len(body) > MAX_PNG_BYTES:
        raise MapServiceError(
            f"The Maps Static API returned more than {MAX_PNG_BYTES} bytes."
        )
    return content_type, body


async def fetch_png(url: str) -> bytes:
    """Download a map PNG in a worker thread so the event loop keeps running.

    Args:
        url: The signed Maps Static API URL.

    Returns:
        The PNG image.

    Raises:
        MapServiceError: If the response isn't a PNG image or is too large.
    """
    content_type, body = await asyncio.to_thread(download, url)
    if content_type != "image/png":
        raise MapServiceError(f"The Maps Static API returned {content_type}.")
    return body


def check_range(name: str, value: object, low: float, high: float) -> float:
    """Parse a number that must lie in a closed range.

    Args:
        name: The input name for the error message.
        value: The raw value.
        low: The lowest valid value.
        high: The highest valid value.

    Returns:
        The number.

    Raises:
        ChartDataError: If the value isn't a number from ``low`` to
            ``high``.
    """
    number = parse_numeric(value)
    if not low <= number <= high:
        raise ChartDataError(
            f"{name} must be from {low:g} to {high:g}, not {number:g}."
        )
    return number


def make_place(label: object, latitude: object, longitude: object) -> Place:
    """Validate a label and its coordinates.

    Args:
        label: The place name.
        latitude: The latitude in degrees.
        longitude: The longitude in degrees.

    Returns:
        The place.

    Raises:
        ChartDataError: If the label is empty or a coordinate is invalid.
    """
    text = "" if label is None else str(label).strip()
    if not text:
        raise ChartDataError("Every place needs a non-empty label.")
    return Place(
        text,
        check_range("latitude", latitude, -90.0, 90.0),
        check_range("longitude", longitude, -180.0, 180.0),
    )


def parse_limited(data: str, limit: int, noun: str) -> list[Row]:
    """Parse rows that one map can show.

    Args:
        data: CSV text with a header row, or a JSON array of row objects.
        limit: The largest number of rows.
        noun: The plural name of the rows for the error message.

    Returns:
        The rows.

    Raises:
        ChartDataError: If the data is invalid or has more than ``limit``
            rows.
    """
    rows = parse_rows(data)
    if len(rows) > limit:
        raise ChartDataError(
            f"One map shows at most {limit} {noun}, not {len(rows)}."
        )
    return rows


def parse_places(rows: Sequence[Row]) -> list[Place]:
    """Validate the label, latitude, and longitude columns of every row.

    Args:
        rows: The parsed rows.

    Returns:
        One place per row.

    Raises:
        ChartDataError: If a column is missing or a value is invalid.
    """
    columns = [
        column_values(rows, name) for name in ("label", "latitude", "longitude")
    ]
    return [make_place(*values) for values in zip(*columns, strict=True)]


def parse_compliance(value: object) -> bool:
    """Parse an ``sla_compliant`` value.

    Args:
        value: A JSON boolean, or ``true`` or ``false`` text.

    Returns:
        The boolean value.

    Raises:
        ChartDataError: If the value isn't true or false.
    """
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text not in BOOLEAN_TEXT:
        raise ChartDataError(
            f"sla_compliant must be true or false, not {value!r}."
        )
    return BOOLEAN_TEXT[text]


def marker(style: str, places: Iterable[Place]) -> Param:
    """Build one Maps Static API markers parameter.

    Args:
        style: The marker style, such as ``size:mid|color:0xD93025``.
        places: The places that share the style.

    Returns:
        The ``markers`` parameter.
    """
    return ("markers", "|".join([style, *(place.location for place in places)]))


def tier_color(score: float) -> str:
    """Pick the color of a 0 to 10 score.

    Args:
        score: The score.

    Returns:
        Red for a score of 7 or more, amber from 4, and green below 4.
    """
    return next(color for floor, color in SCORE_TIERS if score >= floor)


def market_center(
    label: object, latitude: object, longitude: object, radius_km: object
) -> tuple[Place, float]:
    """Validate a hub and the radius of its market-area ring.

    Args:
        label: The hub name.
        latitude: The hub latitude in degrees.
        longitude: The hub longitude in degrees.
        radius_km: The ring radius in kilometers.

    Returns:
        The hub and the radius.

    Raises:
        ChartDataError: If the hub or the radius is invalid.
    """
    hub = make_place(label, latitude, longitude)
    return hub, check_range("radius_km", radius_km, 0.0, MAX_RADIUS_KM)


def hub_params(hub: Place, radius_km: float) -> list[Param]:
    """Mark the hub as H and draw its market-area ring.

    Args:
        hub: The hub.
        radius_km: The ring radius in kilometers. A radius of 0 draws no
            ring.

    Returns:
        The hub marker parameter and, for a positive radius, the ring path.
    """
    params = [marker(f"size:mid|color:{BLUE}|label:H", [hub])]
    if radius_km > 0:
        ring = circle_points(hub.latitude, hub.longitude, radius_km)
        params.append(("path", f"{RING_STYLE}|enc:{encode_polyline(ring)}"))
    return params


def zone_markers(
    zones: Sequence[Place], scores: Sequence[float]
) -> tuple[list[Param], list[dict[str, Any]]]:
    """Number the nine highest scores and group the other zones by tier.

    Args:
        zones: The zones.
        scores: One 0 to 10 score per zone.

    Returns:
        The marker parameters and the legend of the numbered zones.
    """
    ranked = sorted(
        zip(zones, scores, strict=True), key=lambda item: item[1], reverse=True
    )
    params: list[Param] = []
    legend: list[dict[str, Any]] = []
    unnumbered: dict[str, list[Place]] = {}
    for rank, (zone, score) in enumerate(ranked, start=1):
        color = tier_color(score)
        if rank > NUMBERED_ZONES:
            unnumbered.setdefault(color, []).append(zone)
            continue
        params.append(marker(f"size:mid|color:{color}|label:{rank}", [zone]))
        legend.append(
            {"marker": str(rank), "label": zone.label, "score": score}
        )
    params.extend(
        marker(f"size:small|color:{color}", group)
        for color, group in unnumbered.items()
    )
    return params, legend


def zone_plan(data: str, hub: Place, radius_km: float, stores: str) -> MapPlan:
    """Plan the zone markers, the hub marker and ring, and nearby places.

    Args:
        data: CSV text or JSON rows with label, latitude, longitude, and
            score.
        hub: The hub.
        radius_km: The market-area ring radius in kilometers.
        stores: CSV text or JSON rows of nearby places, or an empty string.

    Returns:
        The map plan.

    Raises:
        ChartDataError: If the zones or the places are invalid.
    """
    rows = parse_limited(data, MAX_ZONES, "zones")
    scores = [
        check_range("score", value, 0.0, 10.0)
        for value in column_values(rows, "score")
    ]
    zone_params, legend = zone_markers(parse_places(rows), scores)
    params = [*BASE_PARAMS, *zone_params, *hub_params(hub, radius_km)]
    summary = (
        f"Drew {len(rows)} zones around {hub.label}. Markers 1 to "
        f"{len(legend)} number the highest scores."
    )
    if stores.strip() not in {"", "[]"}:
        places = parse_places(parse_limited(stores, MAX_STORES, "stores"))
        params.append(marker(f"size:small|color:{PURPLE}", places))
        summary += f" {len(places)} nearby places appear in purple."
    return MapPlan(params, summary, legend)


def parse_cell(value: object) -> str:
    """Validate one H3 cell index, such as 8744a1b95ffffff.

    Args:
        value: The raw cell index.

    Returns:
        The cell index in lowercase.

    Raises:
        ChartDataError: If the value isn't a valid H3 cell index.
    """
    cell = "" if value is None else str(value).strip().lower()
    if not h3.is_valid_cell(cell):
        raise ChartDataError(f"{value!r} is not an H3 cell index.")
    return cell


def cell_path(cell: str, color: str) -> Param:
    """Draw one H3 cell as a translucent hexagon.

    Args:
        cell: The H3 cell index.
        color: The fill and outline color.

    Returns:
        The ``path`` parameter.
    """
    boundary: list[tuple[float, float]] = list(h3.cell_to_boundary(cell))
    ring = encode_polyline([*boundary, boundary[0]])
    return ("path", f"color:{color}99|weight:1|fillcolor:{color}66|enc:{ring}")


def heatmap_plan(data: str, hub: Place, radius_km: float) -> MapPlan:
    """Color every H3 cell by its density score around the hub and ring.

    Args:
        data: CSV text or JSON rows with h3_cell_index and score.
        hub: The hub.
        radius_km: The market-area ring radius in kilometers.

    Returns:
        The map plan.

    Raises:
        ChartDataError: If a cell or a score is invalid.
    """
    rows = parse_limited(data, MAX_CELLS, "cells")
    cells = [
        parse_cell(value) for value in column_values(rows, "h3_cell_index")
    ]
    colors = [
        tier_color(check_range("score", value, 0.0, 10.0))
        for value in column_values(rows, "score")
    ]
    params = [
        *BASE_PARAMS,
        *map(cell_path, cells, colors),
        *hub_params(hub, radius_km),
    ]
    legend = [
        {"color": name, "scores": scores, "cells": colors.count(color)}
        for name, color, scores in HEAT_LEGEND
    ]
    summary = (
        f"Drew {len(cells)} H3 cells around {hub.label}, colored by density "
        "score."
    )
    return MapPlan(params, summary, legend)


def lane_plan(data: str, destination: Place) -> MapPlan:
    """Draw a numbered source marker and a geodesic lane for every row.

    Args:
        data: CSV text or JSON rows with label, latitude, longitude, and
            sla_compliant.
        destination: The destination hub.

    Returns:
        The map plan.

    Raises:
        ChartDataError: If a source or an ``sla_compliant`` value is
            invalid.
    """
    rows = parse_limited(data, MAX_LANES, "lanes")
    sources = parse_places(rows)
    compliance = [
        parse_compliance(value)
        for value in column_values(rows, "sla_compliant")
    ]
    params = list(BASE_PARAMS)
    legend: list[dict[str, Any]] = []
    for number, (source, compliant) in enumerate(
        zip(sources, compliance, strict=True), start=1
    ):
        color, weight = LANE_STYLES[compliant]
        params.append(
            marker(f"size:mid|color:{color}|label:{number}", [source])
        )
        params.append(
            (
                "path",
                f"color:{color}CC|weight:{weight}|geodesic:true|"
                f"{source.location}|{destination.location}",
            )
        )
        legend.append(
            {
                "marker": str(number),
                "label": source.label,
                "sla_compliant": compliant,
            }
        )
    params.append(marker(f"size:mid|color:{BLUE}|label:D", [destination]))
    locked = compliance.count(False)
    summary = (
        f"Drew {len(sources)} lanes to {destination.label}: "
        f"{len(sources) - locked} SLA-compliant in green and {locked} locked "
        "by SLA reservations in red."
    )
    return MapPlan(params, summary, legend)


async def draw_map(
    tool: str, url: str, plan: MapPlan, title: str, tool_context: ToolContext
) -> dict[str, Any]:
    """Fetch the signed map, save it, and build the result for the model.

    Args:
        tool: The tool name.
        url: The signed Maps Static API URL.
        plan: The map plan.
        title: The map title.
        tool_context: The ADK tool context of the call.

    Returns:
        The status, the image file name, the summary, and the legend, or
        the status and a planner-safe error when the map service fails.
    """
    try:
        png = await fetch_png(url)
    except (OSError, HTTPException, MapServiceError) as exc:
        logger.error("%s could not fetch the map: %r", tool, exc)
        return {"status": "error", "error": MAP_UNAVAILABLE}
    filename = chart_filename(title, tool.removeprefix("render_"))
    await save_png(tool_context, png, filename)
    return {
        "status": "success",
        "filename": filename,
        "summary": plan.summary,
        "legend": plan.legend,
    }


class MapTools:
    """The map tools, bound to the Maps Static API key and signing secret."""

    def __init__(self, settings: Settings) -> None:
        """Read the Maps Static API key and signing secret.

        Args:
            settings: The agent settings.
        """
        self._api_key = settings.maps_static_api_key.get_secret_value()
        self._secret = settings.maps_static_signing_secret.get_secret_value()

    async def _render(
        self,
        tool: str,
        title: str,
        tool_context: ToolContext,
        plan_map: Callable[[], MapPlan],
    ) -> dict[str, Any]:
        """Plan and sign a map, then draw it or return the input error.

        Args:
            tool: The tool name.
            title: The map title.
            tool_context: The ADK tool context of the call.
            plan_map: Plans the map from the tool arguments.

        Returns:
            The result of ``draw_map``, or the status and the input error.
        """
        try:
            plan = plan_map()
            url = signed_url(plan.params, self._api_key, self._secret)
        except ChartDataError as exc:
            return chart_error(tool, exc)
        return await draw_map(tool, url, plan, title, tool_context)

    async def render_zone_map(
        self,
        data: str,
        title: str,
        center_label: str,
        center_latitude: float,
        center_longitude: float,
        radius_km: float,
        stores: str = "",
        *,
        tool_context: ToolContext,
    ) -> dict[str, Any]:
        """Draw zone demand exposure around a hub on a Google map.

        Google draws numbered markers 1 to 9 for the highest scores and
        small markers for the other zones: red for a score of 7 or more,
        amber from 4, and green below 4. The hub is marker H inside its
        market-area ring, and named places appear as small purple markers.
        Number the zones in the answer with the returned legend.

        Args:
            data: CSV text with a header row and at most 60 zone rows with
                label, latitude, longitude, and score (0 to 10), for example
                from ebs_scm_agentic_ai.zone_demand_exposure.
            title: Business-oriented map title.
            center_label: Hub name, for example Miami DC.
            center_latitude: Hub latitude from
                ebs_scm_agentic_ai.hub_market_areas.
            center_longitude: Hub longitude from
                ebs_scm_agentic_ai.hub_market_areas.
            radius_km: Market-area ring radius in kilometers. A radius of 0
                draws no ring.
            stores: Optional CSV text with a header row and at most 20
                places from places_search_text with label, latitude, and
                longitude.
            tool_context: The ADK tool context, which ADK passes instead of
                the model.

        Returns:
            The status, the image file name, a summary, and the legend, or
            the status and the error.
        """
        return await self._render(
            "render_zone_map",
            title,
            tool_context,
            lambda: zone_plan(
                data,
                *market_center(
                    center_label, center_latitude, center_longitude, radius_km
                ),
                stores,
            ),
        )

    async def render_heatmap(
        self,
        data: str,
        title: str,
        center_label: str,
        center_latitude: float,
        center_longitude: float,
        radius_km: float,
        *,
        tool_context: ToolContext,
    ) -> dict[str, Any]:
        """Draw a heatmap of place density by H3 cell around a hub.

        Google draws every cell as a translucent hexagon: red for a density
        score of 7 or more, amber from 4, and green below 4. The hub is
        marker H inside its market-area ring.

        Args:
            data: CSV text with a header row and at most 80 cell rows with
                h3_cell_index and score (0 to 10), for example from
                ebs_scm_agentic_ai.market_place_density.
            title: Business-oriented map title.
            center_label: Hub name, for example Miami DC.
            center_latitude: Hub latitude from
                ebs_scm_agentic_ai.hub_market_areas.
            center_longitude: Hub longitude from
                ebs_scm_agentic_ai.hub_market_areas.
            radius_km: Market-area ring radius in kilometers. A radius of 0
                draws no ring.
            tool_context: The ADK tool context, which ADK passes instead of
                the model.

        Returns:
            The status, the image file name, a summary, and the legend, or
            the status and the error.
        """
        return await self._render(
            "render_heatmap",
            title,
            tool_context,
            lambda: heatmap_plan(
                data,
                *market_center(
                    center_label, center_latitude, center_longitude, radius_km
                ),
            ),
        )

    async def render_lane_map(
        self,
        data: str,
        title: str,
        destination_label: str,
        destination_latitude: float,
        destination_longitude: float,
        *,
        tool_context: ToolContext,
    ) -> dict[str, Any]:
        """Draw transfer lanes from source hubs to a destination on a map.

        Google draws the destination as marker D, numbered markers 1 to 9
        for the source hubs in row order, and a geodesic line from each
        source: thick green when the transfer keeps every SLA reservation,
        thin red when SLA reservations lock the stock. Number the lanes in
        the answer with the returned legend.

        Args:
            data: CSV text with a header row and at most 9 source hub rows
                with label, latitude, longitude, and sla_compliant (true or
                false).
            title: Business-oriented map title.
            destination_label: Destination hub name, for example Miami DC.
            destination_latitude: Destination hub latitude.
            destination_longitude: Destination hub longitude.
            tool_context: The ADK tool context, which ADK passes instead of
                the model.

        Returns:
            The status, the image file name, a summary, and the legend, or
            the status and the error.
        """
        return await self._render(
            "render_lane_map",
            title,
            tool_context,
            lambda: lane_plan(
                data,
                make_place(
                    destination_label,
                    destination_latitude,
                    destination_longitude,
                ),
            ),
        )


def build_map_tools(settings: Settings) -> tuple[MapTool, ...]:
    """Build the map tools around the Maps Static API key and secret.

    Args:
        settings: The agent settings.

    Returns:
        The zone map, heatmap, and lane map tools.
    """
    tools = MapTools(settings)
    return tools.render_zone_map, tools.render_heatmap, tools.render_lane_map
