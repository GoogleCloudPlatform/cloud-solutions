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
Migrated Spark job to verify data in the target Lakehouse environment.
"""

from pyspark.sql import SparkSession


def main():
    # Initialize Spark Session
    spark = SparkSession.builder.appName("MigratedSparkJob").getOrCreate()

    print("Reading main MTA ridership from Iceberg...")
    mta_df = spark.table("lakehouse.default.mta_ridership")

    print("Reading additional dimensions from Iceberg...")
    bus_stations_df = spark.table("lakehouse.default.bus_stations")

    print("Showing sample data from ridership:")
    mta_df.show(5)

    print("Performing join (Join Ridership with Stations on Borough):")
    # This is a sample analysis joining different Iceberg tables
    joined_df = (
        mta_df.join(bus_stations_df, "borough", "inner")
        .groupBy("borough", "station_complex")
        .agg({"ridership": "sum", "bus_stop_id": "count"})
        .withColumnRenamed("sum(ridership)", "total_ridership")
        .withColumnRenamed("count(bus_stop_id)", "nearby_bus_stops")
        .orderBy("total_ridership", ascending=False)
    )

    print("Top 10 station complexes by ridership and bus connectivity:")
    joined_df.show(10)

    print("Job completed.")
    spark.stop()


if __name__ == "__main__":
    main()
