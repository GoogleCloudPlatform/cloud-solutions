#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Project Aegis - 1st-Party Managed Streaming Pipeline (Cloud Dataflow).

Apache Beam Python streaming pipeline that:
1. Ingests IIoT telemetry events from Cloud Pub/Sub (`telemetry-raw`).
2. Sinks raw events into Google Cloud BigQuery (`analytics.telemetry_events`).
3. Computes 10s Fixed (Tumbling) Window aggregations and anomaly detection.
4. Sinks aggregated state into Google Cloud Bigtable (`telemetry_metrics`).
"""

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

try:
    import google.auth.exceptions
    from google.api_core.exceptions import GoogleAPICallError
    from google.cloud import bigtable

    HAVE_BIGTABLE = True
    _BIGTABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
        GoogleAPICallError,
        google.auth.exceptions.GoogleAuthError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        OSError,
    )
except ImportError:
    bigtable = None  # type: ignore[assignment]
    HAVE_BIGTABLE = False
    _BIGTABLE_EXCEPTIONS = (
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        OSError,
    )

try:
    import apache_beam as beam
    from apache_beam.options.pipeline_options import (
        GoogleCloudOptions,
        PipelineOptions,
        StandardOptions,
    )
    from apache_beam.transforms import trigger, window

    HAVE_BEAM = True
except ImportError:
    HAVE_BEAM = False

    class _MockDoFn:
        WindowParam = object()

    class _MockWriteToBigQuery:
        class Method:
            STREAMING_INSERTS = "STREAMING_INSERTS"

        def __new__(cls, **_kw):
            return None

    class _MockBeam:
        DoFn = _MockDoFn
        Pipeline = object
        ParDo = staticmethod(lambda fn: fn)
        Map = staticmethod(lambda fn: fn)
        GroupByKey = staticmethod(lambda: None)
        WindowInto = staticmethod(lambda *args, **kwargs: None)

        class io:
            ReadFromPubSub = staticmethod(lambda **kw: None)
            WriteToBigQuery = _MockWriteToBigQuery
            BigQueryDisposition = type(
                "BigQueryDisposition",
                (),
                {
                    "WRITE_APPEND": "WRITE_APPEND",
                    "CREATE_NEVER": "CREATE_NEVER",
                },
            )

    class _MockWindow:
        FixedWindows = staticmethod(lambda s: None)

    class _MockTrigger:
        AfterWatermark = staticmethod(lambda **kw: None)
        AfterProcessingTime = staticmethod(lambda delay=0: None)
        AccumulationMode = type(
            "AccumulationMode",
            (),
            {
                "ACCUMULATING": "ACCUMULATING",
                "DISCARDING": "DISCARDING",
            },
        )

    beam = _MockBeam()
    window = _MockWindow()
    trigger = _MockTrigger()
    PipelineOptions = object
    GoogleCloudOptions = object
    StandardOptions = object

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("AegisDataflowPipeline")

CRITICAL_CPU_THRESHOLD = 90.0
CRITICAL_TEMP_THRESHOLD = 90.0
CRITICAL_PRESSURE_THRESHOLD = 140.0
WARNING_CPU_THRESHOLD = 75.0
WARNING_TEMP_THRESHOLD = 75.0
WARNING_PRESSURE_THRESHOLD = 125.0


class ParseTelemetryJsonDoFn(beam.DoFn):
    """Parses incoming Pub/Sub messages into validated telemetry dicts."""

    def process(self, element: Any) -> Iterable[Dict[str, Any]]:
        """Parses a raw Pub/Sub message into a structured telemetry dict."""
        try:
            if isinstance(element, bytes):
                data = json.loads(element.decode("utf-8"))
            elif isinstance(element, str):
                data = json.loads(element)
            elif isinstance(element, dict):
                data = element
            else:
                logger.warning("Unrecognized message type: %s", type(element))
                return

            asset_id = str(data.get("asset_id", "")).strip()
            if not asset_id:
                return

            cpu = float(data.get("cpu_utilization", 0.0))
            temp = float(data.get("temperature_c", 0.0))
            pressure = float(data.get("pressure_psi", 0.0))
            memory = float(data.get("memory_utilization_pct", 0.0))
            status = str(data.get("status", "OK"))
            timestamp = (
                data.get("timestamp") or datetime.now(timezone.utc).isoformat()
            )
            raw_ing_ms = data.get("ingestion_timestamp_ms")
            ingestion_timestamp_ms: Optional[int] = (
                int(raw_ing_ms) if raw_ing_ms is not None else None
            )

            # Ensure UTC ISO format ending in Z
            if isinstance(timestamp, str):
                ts_str = timestamp.replace(" ", "T")
                if not ts_str.endswith("Z") and "+" not in ts_str:
                    ts_str += "Z"
            else:
                ts_str = (
                    datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                )

            yield {
                "asset_id": asset_id,
                "timestamp": ts_str,
                "cpu_utilization": cpu,
                "temperature_c": temp,
                "pressure_psi": pressure,
                "memory_utilization_pct": memory,
                "status": status,
                "ingestion_timestamp_ms": ingestion_timestamp_ms,
            }
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            ValueError,
            TypeError,
            KeyError,
        ) as exc:
            logger.warning("Failed parsing message '%s': %s", element, exc)


class FormatBigQueryRecordFn(beam.DoFn):
    """Formats telemetry records for BigQuery analytics.telemetry_events."""

    def process(self, element: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        """Formats a parsed telemetry dict for BigQuery streaming insertion."""
        cpu = float(element.get("cpu_utilization", 0.0))
        temp = float(element.get("temperature_c", 0.0))
        pressure = float(element.get("pressure_psi", 0.0))
        status = element.get("status", "OK")

        is_anomaly = (
            status == "CRITICAL"
            or cpu > CRITICAL_CPU_THRESHOLD
            or temp > CRITICAL_TEMP_THRESHOLD
            or pressure > CRITICAL_PRESSURE_THRESHOLD
        )

        yield {
            "asset_id": element["asset_id"],
            "timestamp": element["timestamp"],
            "cpu_utilization": cpu,
            "temperature_c": temp,
            "pressure_psi": pressure,
            "memory_utilization_pct": float(
                element.get("memory_utilization_pct", 0.0)
            ),
            "status": status,
            "is_anomaly": is_anomaly,
        }


def extract_asset_key(element: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Key selector for grouping telemetry events by asset_id."""
    return element["asset_id"], element


class ComputeWindowAggregatesDoFn(beam.DoFn):
    """Aggregates a 10-second tumbling window of telemetry records per asset."""

    def process(
        self,
        element: Tuple[str, Iterable[Dict[str, Any]]],
        window_param: Any = beam.DoFn.WindowParam,
    ) -> Iterable[Dict[str, Any]]:
        """Computes 10s window averages and anomaly status for an asset."""
        asset_id, records_iter = element
        records = list(records_iter)
        if not records:
            return

        count = len(records)
        sum_cpu = sum(r["cpu_utilization"] for r in records)
        sum_temp = sum(r["temperature_c"] for r in records)
        sum_pressure = sum(r["pressure_psi"] for r in records)
        sum_memory = sum(r["memory_utilization_pct"] for r in records)

        avg_cpu = round(sum_cpu / count, 2)
        avg_temp = round(sum_temp / count, 2)
        avg_pressure = round(sum_pressure / count, 2)
        avg_memory = round(sum_memory / count, 2)

        ingested_vals = [
            int(r["ingestion_timestamp_ms"])
            for r in records
            if r.get("ingestion_timestamp_ms") is not None
        ]
        max_ingestion_ms: Optional[int] = (
            max(ingested_vals) if ingested_vals else None
        )

        # Anomaly evaluation rules matching Project Aegis baseline
        if (
            avg_cpu > CRITICAL_CPU_THRESHOLD
            or avg_temp > CRITICAL_TEMP_THRESHOLD
            or avg_pressure > CRITICAL_PRESSURE_THRESHOLD
        ):
            status = "CRITICAL"
            is_anomaly = True
        elif (
            avg_cpu > WARNING_CPU_THRESHOLD
            or avg_temp > WARNING_TEMP_THRESHOLD
            or avg_pressure > WARNING_PRESSURE_THRESHOLD
        ):
            status = "WARNING"
            is_anomaly = False
        else:
            status = "OK"
            is_anomaly = False

        # Format window end as ISO 8601 UTC timestamp
        end_dt = window_param.end.to_utc_datetime()
        iso_end = end_dt.isoformat().replace("+00:00", "Z")

        yield {
            "asset_id": asset_id,
            "avg_cpu": avg_cpu,
            "avg_temp": avg_temp,
            "avg_pressure": avg_pressure,
            "avg_memory": avg_memory,
            "status": status,
            "is_anomaly": is_anomaly,
            "window_end": iso_end,
            "ingestion_timestamp_ms": max_ingestion_ms,
            "record_count": count,
        }


class WriteToBigtableDoFn(beam.DoFn):
    """Mutates live operational state rows in Cloud Bigtable."""

    def __init__(
        self,
        project_id: str,
        instance_id: str,
        table_id: str = "telemetry_metrics",
        column_family: str = "metrics",
    ) -> None:
        self.project_id = project_id
        self.instance_id = instance_id
        self.table_id = table_id
        self.column_family = column_family
        self.client = None
        self.table = None
        self._pending_records: Dict[str, Dict[str, Any]] = {}
        self._last_committed: Dict[str, Tuple[str, int, int]] = {}

    @staticmethod
    def _record_sort_key(
        record: Dict[str, Any],
    ) -> Tuple[str, int, int]:
        """Returns (window_end, ingestion_timestamp_ms, record_count)."""
        return (
            str(record.get("window_end", "")),
            int(record.get("ingestion_timestamp_ms") or 0),
            int(record.get("record_count") or 0),
        )

    def setup(self) -> None:
        """Initializes the Cloud Bigtable client and table handle per worker."""
        if not HAVE_BIGTABLE or bigtable is None:
            logger.warning("google-cloud-bigtable package unavailable.")
            self.client = None
            self.table = None
            return
        try:
            self.client = bigtable.Client(project=self.project_id, admin=False)
            instance = self.client.instance(self.instance_id)
            self.table = instance.table(self.table_id)
            logger.info(
                "Initialized Cloud Bigtable client for %s:%s",
                self.instance_id,
                self.table_id,
            )
        except _BIGTABLE_EXCEPTIONS as exc:
            logger.warning("Bigtable client initialization skipped: %s", exc)
            self.client = None
            self.table = None

    def start_bundle(self) -> None:
        """Resets the per-bundle record buffer before processing a bundle."""
        self._pending_records = {}

    def process(self, element: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        """Buffers the freshest pane per asset within the current bundle."""
        asset_id = str(element["asset_id"])
        candidate_key = self._record_sort_key(element)
        existing = self._pending_records.get(asset_id)
        if existing is None or candidate_key >= self._record_sort_key(existing):
            self._pending_records[asset_id] = element
        yield element

    def _build_direct_row(
        self,
        asset_id: str,
        element: Dict[str, Any],
        db_insert_timestamp_ms: int,
    ) -> Any:
        """Constructs a Bigtable DirectRow mutation for a single asset."""
        row = self.table.direct_row(asset_id.encode("utf-8"))
        row.set_cell(
            self.column_family,
            b"cpu",
            str(element["avg_cpu"]).encode("utf-8"),
        )
        row.set_cell(
            self.column_family,
            b"temp",
            str(element["avg_temp"]).encode("utf-8"),
        )
        row.set_cell(
            self.column_family,
            b"pressure",
            str(element["avg_pressure"]).encode("utf-8"),
        )
        row.set_cell(
            self.column_family,
            b"memory",
            str(element["avg_memory"]).encode("utf-8"),
        )
        row.set_cell(
            self.column_family,
            b"status",
            str(element["status"]).encode("utf-8"),
        )
        row.set_cell(
            self.column_family,
            b"is_anomaly",
            str(element["is_anomaly"]).encode("utf-8"),
        )
        row.set_cell(
            self.column_family,
            b"timestamp",
            str(element["window_end"]).encode("utf-8"),
        )
        ingested_ms = element.get("ingestion_timestamp_ms")
        if ingested_ms is not None:
            row.set_cell(
                self.column_family,
                b"ingestion_timestamp_ms",
                str(int(ingested_ms)).encode("utf-8"),
            )
        row.set_cell(
            self.column_family,
            b"db_insert_timestamp_ms",
            str(db_insert_timestamp_ms).encode("utf-8"),
        )
        return row

    def finish_bundle(self) -> None:
        """Flushes the buffered asset rows to Cloud Bigtable in a single RPC."""
        if not self._pending_records:
            return
        pending = self._pending_records
        self._pending_records = {}
        if not self.table:
            return

        rows = []
        committed_keys: Dict[str, Tuple[str, int, int]] = {}
        db_insert_timestamp_ms = int(time.time() * 1000)

        for asset_id, element in pending.items():
            cand_win, cand_ing_ms, cand_count = self._record_sort_key(element)
            last = self._last_committed.get(asset_id)
            if last is not None:
                last_win, last_ing_ms, last_count = last
                if cand_win < last_win:
                    continue
                if (
                    cand_win == last_win
                    and cand_ing_ms <= last_ing_ms
                    and cand_count <= last_count
                ):
                    continue

            rows.append(
                self._build_direct_row(
                    asset_id, element, db_insert_timestamp_ms
                )
            )
            committed_keys[asset_id] = (cand_win, cand_ing_ms, cand_count)

        if not rows:
            return

        try:
            statuses = self.table.mutate_rows(rows)
            failed_errors = [
                err for err in (statuses or []) if getattr(err, "code", 0) != 0
            ]
            if failed_errors:
                for err in failed_errors:
                    logger.warning("Bigtable batch mutation error: %s", err)
            else:
                self._last_committed.update(committed_keys)
        except _BIGTABLE_EXCEPTIONS as exc:
            logger.warning("Error mutating Bigtable rows batch: %s", exc)


def build_pipeline(
    pipeline: beam.Pipeline,
    input_topic: str = "",
    input_subscription: str = "",
    bigtable_project: str = "",
    bigtable_instance: str = "aegis-bigtable",
    bigtable_table: str = "telemetry_metrics",
    bigtable_column_family: str = "metrics",
    bigquery_table: str = "",
    window_seconds: int = 10,
    trigger_interval_seconds: int = 1,
    source_pcollection: Any = None,
) -> Any:
    """Constructs the Apache Beam streaming pipeline graph."""
    if source_pcollection is not None:
        raw_events = source_pcollection
    elif input_subscription:
        raw_events = pipeline | "ReadFromPubSubSub" >> beam.io.ReadFromPubSub(
            subscription=input_subscription
        )
    elif input_topic:
        raw_events = pipeline | "ReadFromPubSubTopic" >> beam.io.ReadFromPubSub(
            topic=input_topic
        )
    else:
        raise ValueError(
            "Either input_topic, input_subscription, or source_pcollection "
            "must be specified."
        )

    parsed_events = raw_events | "ParseTelemetryJson" >> beam.ParDo(
        ParseTelemetryJsonDoFn()
    )

    # Sink 1: Analytical Warehouse Sink to BigQuery
    if bigquery_table:
        bq_rows = parsed_events | "FormatForBigQuery" >> beam.ParDo(
            FormatBigQueryRecordFn()
        )
        _ = bq_rows | "WriteToBigQuery" >> beam.io.WriteToBigQuery(
            table=bigquery_table,
            schema=(
                "asset_id:STRING,timestamp:TIMESTAMP,cpu_utilization:FLOAT,"
                "temperature_c:FLOAT,pressure_psi:FLOAT,"
                "memory_utilization_pct:FLOAT,status:STRING,is_anomaly:BOOLEAN"
            ),
            method=beam.io.WriteToBigQuery.Method.STREAMING_INSERTS,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
        )

    # Sink 2: 10-Second Tumbling Window Aggregation to Cloud Bigtable
    # Uses an early processing-time trigger (default 1s) with ACCUMULATING mode
    # so Bigtable receives sub-2s real-time pane updates throughout each 10s
    # window rather than waiting for the end-of-window watermark lag.
    windowed_aggregates = (
        parsed_events
        | "10sFixedWindow"
        >> beam.WindowInto(
            window.FixedWindows(window_seconds),
            trigger=trigger.AfterWatermark(
                early=trigger.AfterProcessingTime(trigger_interval_seconds)
            ),
            accumulation_mode=trigger.AccumulationMode.ACCUMULATING,
            allowed_lateness=0,
        )
        | "KeyByAssetId" >> beam.Map(extract_asset_key)
        | "GroupPerAsset" >> beam.GroupByKey()
        | "ComputeAggregates" >> beam.ParDo(ComputeWindowAggregatesDoFn())
    )

    if bigtable_project and bigtable_instance:
        _ = windowed_aggregates | "WriteToBigtable" >> beam.ParDo(
            WriteToBigtableDoFn(
                project_id=bigtable_project,
                instance_id=bigtable_instance,
                table_id=bigtable_table,
                column_family=bigtable_column_family,
            )
        )

    return windowed_aggregates


def run(argv: Optional[list[str]] = None) -> None:
    """Main CLI entry point for deploying the Cloud Dataflow streaming job."""
    parser = argparse.ArgumentParser(
        description="Project Aegis - Cloud Dataflow Streaming Pipeline"
    )
    parser.add_argument(
        "--input_topic",
        default="",
        help=(
            "Pub/Sub topic to read from "
            "(e.g. projects/PROJECT_ID/topics/telemetry-raw)"
        ),
    )
    parser.add_argument(
        "--input_subscription",
        default="",
        help="Pub/Sub subscription to read from (optional alternative)",
    )
    parser.add_argument(
        "--bigtable_project",
        default="",
        help="Google Cloud project ID for Cloud Bigtable instance",
    )
    parser.add_argument(
        "--bigtable_instance",
        default="aegis-bigtable",
        help="Cloud Bigtable instance ID",
    )
    parser.add_argument(
        "--bigtable_table",
        default="telemetry_metrics",
        help="Cloud Bigtable table ID",
    )
    parser.add_argument(
        "--bigtable_column_family",
        default="metrics",
        help="Cloud Bigtable column family name",
    )
    parser.add_argument(
        "--bigquery_table",
        default="",
        help="Cloud BigQuery table (PROJECT_ID:analytics.telemetry_events)",
    )
    parser.add_argument(
        "--window_seconds",
        type=int,
        default=10,
        help="Fixed tumbling window size in seconds (default: 10)",
    )
    parser.add_argument(
        "--trigger_interval_seconds",
        type=int,
        default=1,
        help="Early processing-time trigger interval in seconds (default: 1)",
    )

    known_args, pipeline_args = parser.parse_known_args(argv)

    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(StandardOptions).streaming = True

    gcp_opts = pipeline_options.view_as(GoogleCloudOptions)
    if not known_args.bigtable_project and gcp_opts.project:
        known_args.bigtable_project = gcp_opts.project

    with beam.Pipeline(options=pipeline_options) as p:
        build_pipeline(
            pipeline=p,
            input_topic=known_args.input_topic,
            input_subscription=known_args.input_subscription,
            bigtable_project=known_args.bigtable_project,
            bigtable_instance=known_args.bigtable_instance,
            bigtable_table=known_args.bigtable_table,
            bigtable_column_family=known_args.bigtable_column_family,
            bigquery_table=known_args.bigquery_table,
            window_seconds=known_args.window_seconds,
            trigger_interval_seconds=known_args.trigger_interval_seconds,
        )


if __name__ == "__main__":
    run()
