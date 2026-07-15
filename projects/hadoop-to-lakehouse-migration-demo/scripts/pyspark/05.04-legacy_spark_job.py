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

"""
Legacy Spark job to verify data in the source Hadoop cluster.
"""

from pyspark.sql import SparkSession


def main():
    # Initialize Spark Session with Hive support
    spark = (
        SparkSession.builder.appName("LegacySparkJob")
        .enableHiveSupport()
        .getOrCreate()
    )

    print("Reading ridership from Hive...")
    mta_df = spark.table("default.mta_ridership")

    print("Reading bus stations from Hive...")
    bus_stations_df = spark.table("default.bus_stations")

    print("Showing sample ridership data:")
    mta_df.show(5)

    print("Performing join in Hive...")
    joined_df = (
        mta_df.join(bus_stations_df, "borough", "inner")
        .groupBy("borough", "station_complex")
        .agg({"ridership": "sum", "bus_stop_id": "count"})
        .withColumnRenamed("sum(ridership)", "total_ridership")
        .withColumnRenamed("count(bus_stop_id)", "nearby_bus_stops")
        .orderBy("total_ridership", ascending=False)
    )

    print("Top 10 results from Hive join:")
    joined_df.show(10)

    print("Job completed.")
    spark.stop()


if __name__ == "__main__":
    main()
