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

"""Project Aegis - Streaming Telemetry ETL Pipeline.

PySpark Structured Streaming pipeline designed for Dataproc Serverless
execution with:
- Lightning Engine (C++ Velox/Gluten vectorized execution)
- OpenLineage native data lineage tracking
- GCP Pub/Sub & Apache Kafka ingestion sources
- 10-second Tumbling Window aggregation & anomaly detection
- Cloud Bigtable state sink for live asset status & rolling averages
- Cloud BigQuery analytical streaming sink for persistent event storage
"""

import argparse
import logging
import os
import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    StringType,
    StructField,
    StructType,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("AegisETL")

# Telemetry Schema Definition (matches TelemetryMetricEvent)
TELEMETRY_SCHEMA: StructType = StructType(
    [
        StructField("asset_id", StringType(), False),
        StructField("timestamp", StringType(), False),
        StructField("cpu_utilization", DoubleType(), False),
        StructField("temperature_c", DoubleType(), False),
        StructField("pressure_psi", DoubleType(), False),
        StructField("memory_utilization_pct", DoubleType(), False),
        StructField("status", StringType(), True),
    ]
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the Aegis PySpark ETL pipeline."""
    parser = argparse.ArgumentParser(
        description="Aegis PySpark Telemetry Structured Streaming Job"
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "")),
        help="Google Cloud Project ID",
    )
    parser.add_argument(
        "--source-type",
        type=str,
        choices=["kafka"],
        default="kafka",
        help="Streaming input source type ('kafka')",
    )
    parser.add_argument(
        "--kafka-bootstrap-servers",
        type=str,
        default="localhost:9092",
        help="Comma-separated Kafka bootstrap server addresses",
    )
    parser.add_argument(
        "--kafka-topic",
        type=str,
        default="telemetry-raw",
        help="Kafka topic name to subscribe to",
    )
    parser.add_argument(
        "--bigquery-dataset",
        type=str,
        default="analytics",
        help="BigQuery target dataset name",
    )
    parser.add_argument(
        "--bigquery-table",
        type=str,
        default="telemetry_events",
        help="BigQuery target table name",
    )
    parser.add_argument(
        "--bigtable-instance",
        type=str,
        default=os.getenv("BIGTABLE_INSTANCE_ID", ""),
        help="Cloud Bigtable instance ID",
    )
    parser.add_argument(
        "--bigtable-table",
        type=str,
        default="telemetry_metrics",
        help="Cloud Bigtable state table name",
    )
    parser.add_argument(
        "--bigtable-column-family",
        type=str,
        default="metrics",
        help="Cloud Bigtable column family name",
    )
    parser.add_argument(
        "--checkpoint-location",
        type=str,
        default="gs://aegis-spark-checkpoints/aegis_etl",
        help="GCS directory path for Spark Structured Streaming checkpoints",
    )
    parser.add_argument(
        "--watermark-delay",
        type=str,
        default="30 seconds",
        help="Allowed late data watermark threshold",
    )
    parser.add_argument(
        "--window-duration",
        type=str,
        default="10 seconds",
        help="Tumbling window size for aggregation",
    )
    return parser.parse_args()


def create_spark_session(app_name: str = "AegisTelemetryETL") -> SparkSession:
    """Initialize PySpark SparkSession configured for Dataproc Serverless."""
    logger.info("Initializing SparkSession with Lightning Engine & Lineage...")
    builder = (
        SparkSession.builder.appName(app_name)
        # OpenLineage Data Lineage Properties
        .config("spark.dataproc.lineage.enabled", "true")
        .config(
            "spark.extraListeners",
            "io.openlineage.spark.agent.OpenLineageSparkListener",
        )
        # C++ Vectorized Lightning Engine (Velox / Gluten) Properties
        .config("spark.spark.vectorized.enabled", "true")
        .config("spark.sql.execution.vectorized.enabled", "true")
        # Timezone standardization
        .config("spark.sql.session.timeZone", "UTC")
    )
    return builder.getOrCreate()


def read_input_stream(
    spark: SparkSession, args: argparse.Namespace
) -> DataFrame:
    """Construct streaming input DataFrame from Kafka streaming source."""
    if args.source_type == "kafka":
        logger.info(
            "Connecting to Kafka stream: topic='%s', servers='%s'",
            args.kafka_topic,
            args.kafka_bootstrap_servers,
        )
        jaas_module = (
            "org.apache.kafka.common.security.oauthbearer."
            "OAuthBearerLoginModule required;"
        )
        login_handler = (
            "com.google.cloud.hosted.kafka.auth.GcpLoginCallbackHandler"
        )
        raw_stream = (
            spark.readStream.format("kafka")
            .option("kafka.bootstrap.servers", args.kafka_bootstrap_servers)
            .option("subscribe", args.kafka_topic)
            .option("startingOffsets", "latest")
            .option("kafka.security.protocol", "SASL_SSL")
            .option("kafka.sasl.mechanism", "OAUTHBEARER")
            .option("kafka.sasl.jaas.config", jaas_module)
            .option(
                "kafka.sasl.login.callback.handler.class",
                login_handler,
            )
            .load()
        )
        json_stream = raw_stream.select(
            F.col("value").cast("string").alias("payload")
        )
    else:
        raise ValueError(f"Unsupported source type: {args.source_type}")

    return json_stream


def parse_telemetry_payload(
    json_stream: DataFrame, watermark_delay: str
) -> DataFrame:
    """Parse JSON message bytes and attach event-time watermarking."""
    logger.info(
        "Parsing JSON telemetry messages and applying event watermark..."
    )
    return (
        json_stream.select(
            F.from_json(F.col("payload"), TELEMETRY_SCHEMA).alias("data")
        )
        .select("data.*")
        .filter(F.col("asset_id").isNotNull())
        .withColumn("event_timestamp", F.to_timestamp(F.col("timestamp")))
        .withWatermark("event_timestamp", watermark_delay)
    )


def compute_tumbling_window_aggregations(
    parsed_df: DataFrame, window_duration: str
) -> DataFrame:
    """Compute 10-second tumbling window aggregations across metrics."""
    logger.info(
        "Configuring tumbling window aggregations (%s window)...",
        window_duration,
    )
    return (
        parsed_df.groupBy(
            F.window(F.col("event_timestamp"), window_duration),
            F.col("asset_id"),
        )
        .agg(
            F.avg("cpu_utilization").alias("avg_cpu"),
            F.avg("temperature_c").alias("avg_temp"),
            F.avg("pressure_psi").alias("avg_pressure"),
            F.avg("memory_utilization_pct").alias("avg_memory"),
            F.max("cpu_utilization").alias("max_cpu"),
            F.max("temperature_c").alias("max_temp"),
            F.count(F.lit(1)).alias("count_events"),
        )
        .select(
            F.col("asset_id"),
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            F.round(F.col("avg_cpu"), 2).alias("avg_cpu"),
            F.round(F.col("avg_temp"), 2).alias("avg_temp"),
            F.round(F.col("avg_pressure"), 2).alias("avg_pressure"),
            F.round(F.col("avg_memory"), 2).alias("avg_memory"),
            F.round(F.col("max_cpu"), 2).alias("max_cpu"),
            F.round(F.col("max_temp"), 2).alias("max_temp"),
            F.col("count_events"),
            ((F.col("avg_cpu") > 90.0) | (F.col("avg_temp") > 90.0)).alias(
                "is_anomaly"
            ),
            F.when(
                (F.col("avg_cpu") > 90.0) | (F.col("avg_temp") > 90.0),
                F.lit("CRITICAL"),
            )
            .when(
                (F.col("avg_cpu") > 75.0) | (F.col("avg_temp") > 75.0),
                F.lit("WARNING"),
            )
            .otherwise(F.lit("OK"))
            .alias("status"),
        )
    )


def write_batch_to_bigtable(
    batch_df: DataFrame,
    batch_id: int,
    project_id: str,
    instance_id: str,
    table_id: str,
    column_family: str,
) -> None:
    """ForeachBatch writer for updating live state in Cloud Bigtable."""
    records = batch_df.collect()
    if not records:
        return

    logger.info(
        "[Batch %s] Writing %d records to Bigtable table '%s'...",
        batch_id,
        len(records),
        table_id,
    )

    try:
        # pylint: disable=import-outside-toplevel
        from google.cloud import bigtable
        from google.cloud.bigtable.row import DirectRow

        client = bigtable.Client(project=project_id, admin=True)
        instance = client.instance(instance_id)
        table = instance.table(table_id)

        rows = []
        for r in records:
            row_key = str(r["asset_id"]).encode("utf-8")
            row = DirectRow(row_key=row_key)

            row.set_cell(
                column_family, b"cpu", str(r["avg_cpu"]).encode("utf-8")
            )
            row.set_cell(
                column_family, b"temp", str(r["avg_temp"]).encode("utf-8")
            )
            row.set_cell(
                column_family,
                b"pressure",
                str(r["avg_pressure"]).encode("utf-8"),
            )

            w_end = r["window_end"]
            if hasattr(w_end, "isoformat"):
                iso_ts = w_end.isoformat()
            else:
                iso_ts = str(w_end).replace(" ", "T")
            if not iso_ts.endswith("Z") and "+" not in iso_ts:
                iso_ts += "Z"

            row.set_cell(column_family, b"timestamp", iso_ts.encode("utf-8"))
            row.set_cell(
                column_family,
                b"is_anomaly",
                str(r["is_anomaly"]).encode("utf-8"),
            )

            rows.append(row)

        errors = table.mutate_rows(rows)
        if errors:
            for err in errors:
                logger.error(
                    "[Batch %s] Bigtable row mutation error: %s",
                    batch_id,
                    err,
                )
        else:
            logger.info(
                "[Batch %s] Successfully mutated %d Bigtable rows.",
                batch_id,
                len(rows),
            )

        # Hook: consult Anomaly Mitigation Agent if critical anomaly detected
        for r in records:
            is_critical = (
                str(r.get("is_anomaly", "")).lower() == "true"
                or r.get("status") == "CRITICAL"
                or (r.get("avg_cpu") is not None and float(r["avg_cpu"]) > 90.0)
                or (
                    r.get("avg_temp") is not None
                    and float(r["avg_temp"]) > 90.0
                )
            )
            if is_critical:
                asset_id = str(r["asset_id"])
                logger.warning(
                    "[Spark Streaming] Anomaly on %s (CPU: %s, Temp: %s).",
                    asset_id,
                    r.get("avg_cpu"),
                    r.get("avg_temp"),
                )
                try:
                    import json  # pylint: disable=import-outside-toplevel
                    import urllib.request  # pylint: disable=import-outside-toplevel

                    default_url = (
                        "https://hud-backend-yww5w7x2xa-uc.a.run.app"
                        "/api/agent/mitigate"
                    )
                    agent_endpoint = os.getenv("AGENT_SERVICE_URL", default_url)
                    if not agent_endpoint.endswith("/mitigate"):
                        clean_url = agent_endpoint.rstrip("/")
                        agent_endpoint = f"{clean_url}/api/agent/mitigate"

                    payload = json.dumps(
                        {
                            "asset_id": asset_id,
                            "cpu_utilization": float(r.get("avg_cpu", 95.0)),
                            "temperature_c": float(r.get("avg_temp", 94.0)),
                            "pressure_psi": float(r.get("avg_pressure", 115.0)),
                            "memory_utilization_pct": float(
                                r.get("avg_memory", 85.0)
                            ),
                            "status": "CRITICAL",
                        }
                    ).encode("utf-8")
                    req = urllib.request.Request(
                        agent_endpoint,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    urllib.request.urlopen(req, timeout=3)
                    logger.info(
                        "[Spark Streaming] Consulted Agent for %s.",
                        asset_id,
                    )
                # pylint: disable=broad-exception-caught
                except Exception as ex:
                    logger.warning(
                        "[Spark Streaming] Agent notification skipped: %s", ex
                    )

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(
            "[Batch %s] Failed writing to Cloud Bigtable: %s",
            batch_id,
            e,
            exc_info=True,
        )


def write_batch_to_bigquery(
    batch_df: DataFrame, batch_id: int, full_table_id: str, temp_bucket: str
) -> None:
    """ForeachBatch writer for analytical streaming sink into BigQuery."""
    if batch_df.rdd.isEmpty():
        return

    logger.info(
        "[Batch %s] Appending micro-batch to BigQuery '%s'...",
        batch_id,
        full_table_id,
    )
    try:
        (
            batch_df.write.format("bigquery")
            .option("table", full_table_id)
            .option("temporaryGcsBucket", temp_bucket)
            .mode("append")
            .save()
        )
        logger.info("[Batch %s] BigQuery write succeeded.", batch_id)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(
            "[Batch %s] Failed writing to BigQuery: %s",
            batch_id,
            e,
            exc_info=True,
        )


def main() -> None:
    """Main entry point for Aegis PySpark Structured Streaming Pipeline."""
    args = parse_args()
    logger.info(
        "Starting Aegis Streaming Pipeline in Project '%s'...",
        args.project_id,
    )

    spark = create_spark_session()

    try:
        json_stream = read_input_stream(spark, args)
        parsed_df = parse_telemetry_payload(json_stream, args.watermark_delay)
        agg_df = compute_tumbling_window_aggregations(
            parsed_df, args.window_duration
        )

        temp_gcs_bucket = args.checkpoint_location.replace("gs://", "").split(
            "/"
        )[0]

        bq_raw_table = (
            f"{args.project_id}.{args.bigquery_dataset}.{args.bigquery_table}"
        )
        logger.info(
            "Initializing BigQuery sink targeting table '%s'...",
            bq_raw_table,
        )

        (
            parsed_df.select(
                F.col("asset_id"),
                F.col("event_timestamp").alias("timestamp"),
                F.col("cpu_utilization"),
                F.col("temperature_c"),
                F.col("pressure_psi"),
                F.col("memory_utilization_pct"),
                F.col("status"),
            )
            .writeStream.outputMode("append")
            .foreachBatch(
                lambda df, b_id: write_batch_to_bigquery(
                    df, b_id, bq_raw_table, temp_gcs_bucket
                )
            )
            .option("checkpointLocation", f"{args.checkpoint_location}/bq_raw")
            .start()
        )

        logger.info(
            "Initializing Bigtable state sink targeting instance '%s'...",
            args.bigtable_instance,
        )
        (
            agg_df.writeStream.outputMode("update")
            .foreachBatch(
                lambda df, b_id: write_batch_to_bigtable(
                    df,
                    b_id,
                    args.project_id,
                    args.bigtable_instance,
                    args.bigtable_table,
                    args.bigtable_column_family,
                )
            )
            .option(
                "checkpointLocation", f"{args.checkpoint_location}/bt_state"
            )
            .start()
        )

        logger.info("All streaming queries initialized and actively running.")
        spark.streams.awaitAnyTermination()

    except KeyboardInterrupt:
        logger.info("Pipeline termination signal received. Cleaning up...")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.fatal("Uncaught exception in Aegis ETL Pipeline: %s", e)
        sys.exit(1)
    finally:
        spark.stop()
        logger.info("Spark session cleanly shut down.")


if __name__ == "__main__":
    main()
